"""
Monthly compliance snapshots for digest delta truth (score, counts, per-requirement fingerprints).
Persisted only after a successful digest delivery so retries do not advance comparison baseline.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.requirement_evidence_authority import AUTHORITY_VERSION
from utils.expiry_utils import get_computed_status, get_effective_expiry_date


def requirement_fingerprint(req: Dict[str, Any]) -> str:
    """Compact state for comparison (computed status + authority evidence + effective due)."""
    eff = get_effective_expiry_date(req)
    if eff is not None and hasattr(eff, "isoformat"):
        due = eff.isoformat()
    else:
        due = str(req.get("due_date") or "")
    st = str(get_computed_status(req) or req.get("status") or "")
    ea = req.get("evidence_authority") or {}
    if req.get("evidence_authority_synced_at") and int(ea.get("version") or 0) >= AUTHORITY_VERSION:
        ev = str(ea.get("state") or req.get("evidence_state") or "")
    else:
        ev = str(req.get("evidence_state") or "")
    rid = str(req.get("requirement_id") or "")
    return f"{rid}|{st}|{ev}|{due}"


def build_fingerprint_map(requirements: List[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for r in requirements:
        rid = str(r.get("requirement_id") or "").strip()
        if rid:
            out[rid] = requirement_fingerprint(r)
    return out


async def load_latest_snapshot(db, client_id: str) -> Optional[Dict[str, Any]]:
    """Most recent stored snapshot for client (any month)."""
    doc = await db.monthly_compliance_snapshots.find_one(
        {"client_id": client_id},
        sort=[("report_month_key", -1)],
        projection={"_id": 0},
    )
    return doc


async def load_snapshot_for_month(db, client_id: str, report_month_key: str) -> Optional[Dict[str, Any]]:
    return await db.monthly_compliance_snapshots.find_one(
        {"client_id": client_id, "report_month_key": report_month_key},
        {"_id": 0},
    )


def compute_deltas(
    prev: Optional[Dict[str, Any]],
    current_fps: Dict[str, str],
    current_reqs: List[Dict[str, Any]],
    *,
    current_score: int,
    current_missing_evidence: int,
    documents_uploaded_period: int,
) -> Dict[str, Any]:
    """
    Real deltas from fingerprint map vs previous snapshot.
    If prev is None: caller should show first-report copy (no fabricated numbers).
    """
    if not prev:
        return {
            "has_prior_snapshot": False,
            "score_delta": None,
            "newly_overdue_ids": [],
            "newly_overdue_labels": [],
            "resolved_improved_ids": [],
            "resolved_improved_labels": [],
            "newly_expiring_ids": [],
            "newly_expiring_labels": [],
            "newly_missing_evidence_delta": None,
            "documents_uploaded_prev_period": None,
            "documents_uploaded_delta_vs_prev_period": None,
        }

    prev_fps: Dict[str, str] = prev.get("requirement_fingerprints") or {}
    prev_score = prev.get("compliance_score")
    score_delta = None
    if prev_score is not None:
        try:
            score_delta = int(current_score) - int(prev_score)
        except (TypeError, ValueError):
            score_delta = None

    newly_overdue: List[str] = []
    resolved_improved: List[str] = []
    newly_expiring: List[str] = []

    def _status_from_fp(fp: str) -> str:
        parts = fp.split("|")
        return parts[1] if len(parts) > 1 else ""

    overdue_like = frozenset({"OVERDUE", "EXPIRED"})
    ok_like = frozenset({"COMPLIANT"})
    expiring = "EXPIRING_SOON"

    for r in current_reqs:
        rid = str(r.get("requirement_id") or "").strip()
        if not rid:
            continue
        cur_fp = current_fps.get(rid) or requirement_fingerprint(r)
        pr_fp = prev_fps.get(rid)
        if not pr_fp:
            continue
        c_st = _status_from_fp(cur_fp)
        p_st = _status_from_fp(pr_fp)
        if c_st in overdue_like and p_st not in overdue_like:
            newly_overdue.append(rid)
        if c_st in ok_like and p_st in overdue_like:
            resolved_improved.append(rid)
        if c_st == expiring and p_st not in (expiring,) and p_st not in overdue_like:
            newly_expiring.append(rid)

    prev_missing = prev.get("missing_evidence_count")
    newly_missing_delta = None
    if prev_missing is not None:
        try:
            newly_missing_delta = int(current_missing_evidence) - int(prev_missing)
        except (TypeError, ValueError):
            newly_missing_delta = None

    prev_docs = prev.get("documents_uploaded_in_report_period")
    docs_delta = None
    if prev_docs is not None:
        try:
            docs_delta = int(documents_uploaded_period) - int(prev_docs)
        except (TypeError, ValueError):
            docs_delta = None

    return {
        "has_prior_snapshot": True,
        "score_delta": score_delta,
        "newly_overdue_ids": newly_overdue,
        "newly_overdue_labels": [],
        "resolved_improved_ids": resolved_improved,
        "resolved_improved_labels": [],
        "newly_expiring_ids": newly_expiring,
        "newly_expiring_labels": [],
        "newly_missing_evidence_delta": newly_missing_delta,
        "documents_uploaded_prev_period": prev_docs,
        "documents_uploaded_delta_vs_prev_period": docs_delta,
    }


async def persist_snapshot(
    db,
    *,
    client_id: str,
    digest_id: str,
    report_month_key: str,
    compliance_score: int,
    risk_level: str,
    total_requirements: int,
    valid_count: int,
    expiring_soon_count: int,
    overdue_count: int,
    missing_evidence_count: int,
    open_compliance_jobs: int,
    open_maintenance_jobs: int,
    documents_uploaded_in_report_period: int,
    requirement_fingerprints: Dict[str, str],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "snapshot_id": digest_id,
        "client_id": client_id,
        "digest_id": digest_id,
        "report_month_key": report_month_key,
        "created_at": now,
        "compliance_score": compliance_score,
        "risk_level": risk_level,
        "total_requirements": total_requirements,
        "valid_count": valid_count,
        "expiring_soon_count": expiring_soon_count,
        "overdue_count": overdue_count,
        "missing_evidence_count": missing_evidence_count,
        "open_compliance_jobs": open_compliance_jobs,
        "open_maintenance_jobs": open_maintenance_jobs,
        "documents_uploaded_in_report_period": documents_uploaded_in_report_period,
        "requirement_fingerprints": requirement_fingerprints,
    }
    await db.monthly_compliance_snapshots.update_one(
        {"client_id": client_id, "report_month_key": report_month_key},
        {"$set": doc},
        upsert=True,
    )
