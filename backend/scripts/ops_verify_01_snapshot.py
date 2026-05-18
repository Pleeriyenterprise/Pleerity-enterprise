"""
OPS-VERIFY-01 read-only Mongo snapshots (observational only).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from scripts.c2_snapshot import (  # noqa: E402
    dashboard_tasks_snapshot,
    fp,
    fp32,
    property_score_snapshot,
)
from scripts.e1a_snapshot import normalize_evidence_authority_semantic  # noqa: E402


def _authority_snapshot(requirement: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    auth = normalize_evidence_authority_semantic((requirement or {}).get("evidence_authority"))
    return {
        "evidence_authority": auth,
        "fingerprint": fp32(auth or {}),
    }


async def queue_snapshot(db, *, property_id: str, limit: int = 25) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    pipeline = [
        {"$match": {"property_id": property_id}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]
    async for row in db.compliance_recalc_queue.aggregate(pipeline):
        counts[str(row.get("_id") or "unknown").upper()] = int(row.get("n") or 0)
    counts["TOTAL"] = sum(counts.values())
    recent: List[Dict[str, Any]] = []
    cursor = db.compliance_recalc_queue.find(
        {"property_id": property_id},
        {
            "_id": 0,
            "status": 1,
            "correlation_id": 1,
            "created_at": 1,
            "updated_at": 1,
            "completed_at": 1,
            "reason": 1,
        },
    ).sort("updated_at", -1).limit(limit)
    async for row in cursor:
        recent.append(row)
    pending = counts.get("PENDING", 0) + counts.get("RUNNING", 0)
    return {
        "counts_by_status": counts,
        "pending_or_running": pending,
        "recent_rows": recent,
        "fingerprint": fp({"counts": counts, "recent_ids": [r.get("correlation_id") for r in recent[:10]]}),
    }


async def requirement_row_snapshot(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
) -> Dict[str, Any]:
    req = await db.requirements.find_one(
        {"client_id": client_id, "property_id": property_id, "requirement_id": requirement_id},
        {"_id": 0},
    )
    if not req:
        return {"found": False, "requirement_id": requirement_id}
    return {
        "found": True,
        "requirement_id": requirement_id,
        "requirement_type": req.get("requirement_type"),
        "status": req.get("status"),
        "lifecycle_state": req.get("lifecycle_state"),
        "evidence_status": req.get("evidence_status"),
        "client_surface_visible": req.get("client_surface_visible"),
        "updated_at": req.get("updated_at"),
        "authority": _authority_snapshot(req),
        "row_fingerprint": fp32(
            {
                "status": req.get("status"),
                "lifecycle_state": req.get("lifecycle_state"),
                "authority_fp": _authority_snapshot(req)["fingerprint"],
            }
        ),
    }


async def cer_rows_for_requirement(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cursor = db.compliance_evidence_records.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "requirement_id": requirement_id,
            "archived": {"$ne": True},
        },
        {
            "_id": 0,
            "compliance_evidence_id": 1,
            "evidence_mode": 1,
            "verification_status": 1,
            "created_at": 1,
            "updated_at": 1,
            "linked_document_ids": 1,
        },
    ).sort("created_at", -1).limit(limit)
    async for row in cursor:
        rows.append(row)
    return rows


async def documents_for_requirement(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cursor = db.documents.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "requirement_id": requirement_id,
        },
        {
            "_id": 0,
            "document_id": 1,
            "filename": 1,
            "source": 1,
            "uploaded_at": 1,
            "evidence_review_state": 1,
            "extraction_status": 1,
        },
    ).sort("uploaded_at", -1).limit(limit)
    async for row in cursor:
        rows.append(row)
    return rows


async def capture_baseline(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    phase: str = "baseline",
) -> Dict[str, Any]:
    return {
        "unit_id": "OPS-VERIFY-01",
        "phase": phase,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "requirement": await requirement_row_snapshot(
            db, client_id=client_id, property_id=property_id, requirement_id=requirement_id
        ),
        "property_score": await property_score_snapshot(db, cid=client_id, pid=property_id),
        "queue": await queue_snapshot(db, property_id=property_id),
        "dashboard_tasks": await dashboard_tasks_snapshot(db, cid=client_id, pid=property_id),
        "cer_rows": await cer_rows_for_requirement(
            db, client_id=client_id, property_id=property_id, requirement_id=requirement_id
        ),
        "documents": await documents_for_requirement(
            db, client_id=client_id, property_id=property_id, requirement_id=requirement_id
        ),
    }


async def capture_post_action(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    baseline: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    baseline = baseline or {}
    base_req = (baseline.get("requirement") or {}).get("authority", {}).get("fingerprint")
    req_snap = await requirement_row_snapshot(
        db, client_id=client_id, property_id=property_id, requirement_id=requirement_id
    )
    post_auth = (req_snap.get("authority") or {}).get("fingerprint")
    cer_rows = await cer_rows_for_requirement(
        db, client_id=client_id, property_id=property_id, requirement_id=requirement_id
    )
    docs = await documents_for_requirement(
        db, client_id=client_id, property_id=property_id, requirement_id=requirement_id
    )
    queue = await queue_snapshot(db, property_id=property_id)
    queue_match = None
    if correlation_id:
        queue_match = await db.compliance_recalc_queue.find_one(
            {"property_id": property_id, "correlation_id": correlation_id},
            {"_id": 0},
        )
    baseline_cer_count = len(baseline.get("cer_rows") or [])
    return {
        "unit_id": "OPS-VERIFY-01",
        "phase": "post_submit",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "correlation_id": correlation_id,
        "requirement": req_snap,
        "authority_changed_from_baseline": bool(base_req and post_auth and base_req != post_auth),
        "cer_rows": cer_rows,
        "cer_count_delta_from_baseline": len(cer_rows) - baseline_cer_count,
        "documents": docs,
        "queue": queue,
        "queue_row_for_correlation": queue_match,
        "property_score": await property_score_snapshot(db, cid=client_id, pid=property_id),
    }


async def capture_convergence(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    baseline: Optional[Dict[str, Any]] = None,
    post_submit: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    baseline = baseline or {}
    post_submit = post_submit or {}
    base_score = (baseline.get("property_score") or {})
    now_score = await property_score_snapshot(db, cid=client_id, pid=property_id)
    queue = await queue_snapshot(db, property_id=property_id)
    queue_row = None
    if correlation_id:
        queue_row = await db.compliance_recalc_queue.find_one(
            {"property_id": property_id, "correlation_id": correlation_id},
            {"_id": 0},
        )
    score_pending = bool(now_score.get("compliance_score_pending"))
    base_pending = bool(base_score.get("compliance_score_pending"))
    base_calc = base_score.get("compliance_last_calculated_at")
    now_calc = now_score.get("compliance_last_calculated_at")
    score_advanced = base_calc != now_calc or base_score.get("compliance_score") != now_score.get(
        "compliance_score"
    )
    queue_terminal = str((queue_row or {}).get("status") or "").upper() == "DONE"
    stale_window_notes = {
        "score_pending_stuck": score_pending and base_pending,
        "score_timestamp_advanced": score_advanced,
        "queue_terminal_for_correlation": queue_terminal,
    }
    return {
        "unit_id": "OPS-VERIFY-01",
        "phase": "convergence",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "correlation_id": correlation_id,
        "property_score": now_score,
        "queue": queue,
        "queue_row_for_correlation": queue_row,
        "dashboard_tasks": await dashboard_tasks_snapshot(db, cid=client_id, pid=property_id),
        "requirement": await requirement_row_snapshot(
            db, client_id=client_id, property_id=property_id, requirement_id=requirement_id
        ),
        "cer_rows": await cer_rows_for_requirement(
            db, client_id=client_id, property_id=property_id, requirement_id=requirement_id
        ),
        "stale_state_window": stale_window_notes,
        "score_converged_observable": score_advanced and not score_pending,
        "async_convergence_partial_signals": {
            "pending_flag": score_pending,
            "queue_pending_or_running": queue.get("pending_or_running", 0) > 0,
            "no_terminal_queue_row": correlation_id and not queue_terminal,
        },
        "baseline_score_fingerprint": base_score.get("fingerprint"),
        "post_submit_score_fingerprint": (post_submit.get("property_score") or {}).get("fingerprint"),
        "convergence_score_fingerprint": now_score.get("fingerprint"),
    }
