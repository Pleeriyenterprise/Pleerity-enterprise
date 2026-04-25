"""
One-off / periodic convergence: persist compliance_gaps for all active requirements.

Uses the same inference + sync path as runtime so Command Centre / dashboard counts match
live gap truth after a run. Idempotent: re-runs only touch ``updated_at`` on existing open rows
and emit lifecycle audits only when configured (see ``audit_lifecycle`` on sync).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from models import AuditAction
from utils.audit import create_audit_log

from services.compliance_gap_engine import GAP_AUTHORITY_UNSYNCED, infer_compliance_gaps_for_requirement
from services.compliance_gap_sync import sync_compliance_gaps_for_requirement

logger = logging.getLogger(__name__)


def _policy_signature(pol: Any) -> str:
    """Stable short key for aggregate counts (policy dimensions differ by gap kind)."""
    if not isinstance(pol, dict) or not pol:
        return "default"
    parts: List[str] = []
    for k in sorted(pol.keys()):
        v = pol[k]
        if isinstance(v, bool):
            parts.append(f"{k}={'y' if v else 'n'}")
        elif v is None:
            parts.append(f"{k}=null")
        else:
            parts.append(f"{k}={v}")
    return "|".join(parts) if parts else "default"


def _jurisdiction_for(requirement: Dict[str, Any], property_doc: Optional[Dict[str, Any]]) -> str:
    for src in (property_doc, requirement):
        if not isinstance(src, dict):
            continue
        j = (src.get("jurisdiction") or "").strip()
        if j:
            return j
    return "unknown"


def _property_label(property_doc: Optional[Dict[str, Any]], property_id: str) -> str:
    if not isinstance(property_doc, dict):
        return property_id or "unknown"
    return (
        (property_doc.get("nickname") or "").strip()
        or (property_doc.get("address_line_1") or "").strip()
        or (property_doc.get("postcode") or "").strip()
        or property_id
        or "unknown"
    )


def _requirement_active(r: Dict[str, Any]) -> bool:
    if (r.get("applicability") or "").upper() == "NOT_REQUIRED":
        return False
    if (r.get("status") or "").upper() == "NOT_REQUIRED":
        return False
    return True


def _desired_open_gap_keys(requirement: Dict[str, Any], *, property_doc: Optional[Dict[str, Any]]) -> Tuple[Set[str], bool]:
    """Return (gap_key set from inference, whether any AUTHORITY_UNSYNCED gap is present)."""
    gaps = infer_compliance_gaps_for_requirement(requirement, property_doc=property_doc)
    cid = str(requirement.get("client_id") or "")
    pid = str(requirement.get("property_id") or "")
    rid = str(requirement.get("requirement_id") or "")
    code = str(requirement.get("requirement_code") or requirement.get("code") or requirement.get("requirement_type") or "")
    keys: Set[str] = set()
    unsynced = False
    for g in gaps:
        row = g.to_mongo(client_id=cid, property_id=pid, requirement_id=rid, requirement_code=code)
        keys.add(str(row["gap_key"]))
        if g.gap_kind == GAP_AUTHORITY_UNSYNCED:
            unsynced = True
    return keys, unsynced


async def _existing_open_gap_keys(db, client_id: str, requirement_id: str) -> Set[str]:
    cur = await db.compliance_gaps.find(
        {"client_id": client_id, "requirement_id": str(requirement_id), "status": "open"},
        {"_id": 0, "gap_key": 1},
    ).to_list(500)
    return {str(x["gap_key"]) for x in cur if x.get("gap_key")}


def transition_counts(existing: Set[str], desired: Set[str]) -> Tuple[int, int, int]:
    """Returns (would_open, would_resolve, unchanged_open)."""
    opened = len(desired - existing)
    resolved = len(existing - desired)
    unchanged = len(existing & desired)
    return opened, resolved, unchanged


async def preview_gap_persistence_delta(
    db,
    requirement: Dict[str, Any],
    *,
    property_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compare persisted open gap_keys with inference (no writes).
    """
    cid = str(requirement.get("client_id") or "")
    rid = str(requirement.get("requirement_id") or "")
    existing = await _existing_open_gap_keys(db, cid, rid) if cid and rid else set()
    desired, unsynced = _desired_open_gap_keys(requirement, property_doc=property_doc)
    o, r, u = transition_counts(existing, desired)
    return {
        "existing_open_gap_keys": sorted(existing),
        "desired_gap_keys": sorted(desired),
        "gaps_opened": o,
        "gaps_resolved": r,
        "unchanged_gaps": u,
        "authority_unsynced": bool(unsynced),
    }


def build_requirements_query(
    *,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    q: Dict[str, Any] = {
        "requirement_id": {"$exists": True, "$nin": [None, ""]},
        "client_id": {"$exists": True, "$nin": [None, ""]},
    }
    if client_id:
        q["client_id"] = str(client_id)
    if property_id:
        q["property_id"] = str(property_id)
    return q


async def run_compliance_gaps_backfill(
    db,
    *,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    dry_run: bool = False,
    audit_lifecycle: bool = True,
    run_operational_bridge: bool = True,
    batch_size: int = 250,
    limit: Optional[int] = None,
    emit_batch_summary_audit: bool = False,
) -> Dict[str, Any]:
    """
    Walk active requirements and sync persisted compliance gaps.

    ``emit_batch_summary_audit``: when True and ``audit_lifecycle`` is False and not ``dry_run``,
    emit a single COMPLIANCE_GAP_BACKFILL_COMPLETED audit with aggregate counters (use to cap audit volume).

    Returns aggregate summary dict (see script / tests for fields).
    """
    q = build_requirements_query(client_id=client_id, property_id=property_id)
    summary: Dict[str, Any] = {
        "dry_run": dry_run,
        "scoped_client_id": client_id,
        "scoped_property_id": property_id,
        "requirements_scanned": 0,
        "requirements_active": 0,
        "gaps_opened": 0,
        "gaps_resolved": 0,
        "unchanged_gaps": 0,
        "authority_unsynced_requirements": 0,
        "errors": [],
    }

    prop_cache: Dict[str, Optional[Dict[str, Any]]] = {}

    async def _prop(pid: Optional[str], req_client: str) -> Optional[Dict[str, Any]]:
        if not pid:
            return None
        ck = f"{req_client}:{pid}"
        if ck not in prop_cache:
            try:
                prop_cache[ck] = await db.properties.find_one(
                    {"property_id": pid, "client_id": req_client},
                    {"_id": 0},
                )
            except Exception:
                prop_cache[ck] = None
        return prop_cache.get(ck)

    offset = 0
    while True:
        take = batch_size
        if limit is not None:
            take = min(batch_size, max(0, limit - offset))
            if take <= 0:
                break
        try:
            batch = await db.requirements.find(q, {"_id": 0}).skip(offset).limit(take).to_list(take)
        except Exception as e:
            summary["errors"].append({"stage": "fetch", "error": str(e)})
            break
        if not batch:
            break
        offset += len(batch)
        for requirement in batch:
            summary["requirements_scanned"] += 1
            if not _requirement_active(requirement):
                continue
            rid = requirement.get("requirement_id")
            cid = requirement.get("client_id")
            if not rid or not cid:
                continue
            summary["requirements_active"] += 1
            pid = requirement.get("property_id")
            try:
                pdoc = await _prop(str(pid) if pid else "", str(cid))
            except Exception as pe:
                summary["errors"].append({"requirement_id": str(rid), "stage": "property_load", "error": str(pe)})
                pdoc = None

            try:
                delta = await preview_gap_persistence_delta(db, requirement, property_doc=pdoc)
            except Exception as e:
                summary["errors"].append({"requirement_id": str(rid), "stage": "preview", "error": str(e)})
                continue

            summary["gaps_opened"] += int(delta["gaps_opened"])
            summary["gaps_resolved"] += int(delta["gaps_resolved"])
            summary["unchanged_gaps"] += int(delta["unchanged_gaps"])
            if delta.get("authority_unsynced"):
                summary["authority_unsynced_requirements"] += 1

            if dry_run:
                continue

            try:
                sync_out = await sync_compliance_gaps_for_requirement(
                    db,
                    requirement,
                    property_doc=pdoc,
                    audit_lifecycle=audit_lifecycle,
                    run_operational_bridge=run_operational_bridge,
                )
                for err in sync_out.get("errors") or []:
                    summary["errors"].append(dict(err))
            except Exception as e:
                summary["errors"].append({"requirement_id": str(rid), "stage": "sync", "error": str(e)})

        if len(batch) < take:
            break

    if emit_batch_summary_audit and (not dry_run) and (not audit_lifecycle):
        try:
            await create_audit_log(
                action=AuditAction.COMPLIANCE_GAP_BACKFILL_COMPLETED,
                client_id=str(client_id or "system"),
                resource_type="compliance_gap_backfill",
                resource_id=f"bf_{uuid.uuid4().hex[:16]}",
                metadata={
                    "dry_run": False,
                    "scoped_client_id": client_id,
                    "scoped_property_id": property_id,
                    "requirements_scanned": summary["requirements_scanned"],
                    "requirements_active": summary["requirements_active"],
                    "gaps_opened": summary["gaps_opened"],
                    "gaps_resolved": summary["gaps_resolved"],
                    "unchanged_gaps": summary["unchanged_gaps"],
                    "authority_unsynced_requirements": summary["authority_unsynced_requirements"],
                    "error_count": len(summary["errors"]),
                    "audit_lifecycle": False,
                },
            )
        except Exception as e:
            logger.warning("backfill summary audit failed: %s", e)
            summary["errors"].append({"stage": "summary_audit", "error": str(e)})

    summary["authority_unsynced_count"] = int(summary.get("authority_unsynced_requirements") or 0)
    summary["delta_basis"] = "preview_vs_persisted_open_keys_before_each_sync"
    summary["error_count"] = len(summary.get("errors") or [])
    return summary


async def inspect_proposed_gap_composition(
    db,
    *,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    batch_size: int = 250,
    limit: Optional[int] = None,
    net_new_only: bool = True,
) -> Dict[str, Any]:
    """
    Pre-apply distribution report: walk the same requirement scope as the backfill, infer gaps,
    and aggregate **without writing**.

    When ``net_new_only`` is True (default), only counts gaps whose ``gap_key`` is not already
    ``status: open`` in ``compliance_gaps`` — i.e. the same set as backfill ``gaps_opened`` totals.
    When False, counts every inferred gap row (full engine output per requirement).
    """
    q = build_requirements_query(client_id=client_id, property_id=property_id)
    by_kind: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    by_jurisdiction: Dict[str, int] = {}
    by_property: Dict[str, int] = {}
    property_labels: Dict[str, str] = {}
    by_action_type: Dict[str, int] = {}
    by_policy_signature: Dict[str, int] = {}
    by_action_type_and_policy: Dict[str, int] = {}
    per_requirement_counts: Dict[str, int] = {}
    requirement_meta: Dict[str, Dict[str, Any]] = {}
    errors: List[Dict[str, Any]] = []
    total_rows = 0
    requirements_scanned = 0
    requirements_active = 0

    prop_cache: Dict[str, Optional[Dict[str, Any]]] = {}

    async def _prop(pid: Optional[str], req_client: str) -> Optional[Dict[str, Any]]:
        if not pid:
            return None
        ck = f"{req_client}:{pid}"
        if ck not in prop_cache:
            try:
                prop_cache[ck] = await db.properties.find_one(
                    {"property_id": pid, "client_id": req_client},
                    {"_id": 0},
                )
            except Exception:
                prop_cache[ck] = None
        return prop_cache.get(ck)

    offset = 0
    while True:
        take = batch_size
        if limit is not None:
            take = min(batch_size, max(0, limit - offset))
            if take <= 0:
                break
        try:
            batch = await db.requirements.find(q, {"_id": 0}).skip(offset).limit(take).to_list(take)
        except Exception as e:
            errors.append({"stage": "fetch", "error": str(e)})
            break
        if not batch:
            break
        offset += len(batch)
        for requirement in batch:
            requirements_scanned += 1
            if not _requirement_active(requirement):
                continue
            rid = requirement.get("requirement_id")
            cid = requirement.get("client_id")
            if not rid or not cid:
                continue
            requirements_active += 1
            pid = str(requirement.get("property_id") or "")
            rids = str(rid)
            cids = str(cid)
            code = str(
                requirement.get("requirement_code")
                or requirement.get("code")
                or requirement.get("requirement_type")
                or ""
            )
            try:
                pdoc = await _prop(pid, cids)
            except Exception as pe:
                errors.append({"requirement_id": rids, "stage": "property_load", "error": str(pe)})
                pdoc = None

            if pid and pid not in property_labels:
                property_labels[pid] = _property_label(pdoc, pid)

            try:
                gaps = infer_compliance_gaps_for_requirement(requirement, property_doc=pdoc)
            except Exception as e:
                errors.append({"requirement_id": rids, "stage": "infer", "error": str(e)})
                continue

            existing: Set[str] = set()
            if net_new_only:
                try:
                    existing = await _existing_open_gap_keys(db, cids, rids)
                except Exception as e:
                    errors.append({"requirement_id": rids, "stage": "existing_gaps", "error": str(e)})

            juris = _jurisdiction_for(requirement, pdoc)
            inc = 0
            for g in gaps:
                row = g.to_mongo(client_id=cids, property_id=pid, requirement_id=rids, requirement_code=code)
                gk = str(row.get("gap_key") or "")
                if net_new_only and gk in existing:
                    continue
                inc += 1
                k = str(g.gap_kind or "UNKNOWN")
                by_kind[k] = by_kind.get(k, 0) + 1
                sv = str(g.severity or "UNKNOWN").upper()
                by_severity[sv] = by_severity.get(sv, 0) + 1
                by_jurisdiction[juris] = by_jurisdiction.get(juris, 0) + 1
                pk = pid or "none"
                by_property[pk] = by_property.get(pk, 0) + 1
                at = str(g.action_type or "unknown")
                by_action_type[at] = by_action_type.get(at, 0) + 1
                psig = _policy_signature(g.policy)
                by_policy_signature[psig] = by_policy_signature.get(psig, 0) + 1
                combo = f"{at}::{psig}"
                by_action_type_and_policy[combo] = by_action_type_and_policy.get(combo, 0) + 1

            if inc:
                per_requirement_counts[rids] = per_requirement_counts.get(rids, 0) + inc
                if rids not in requirement_meta:
                    requirement_meta[rids] = {
                        "requirement_id": rids,
                        "client_id": cids,
                        "property_id": pid or None,
                        "property_label": property_labels.get(pid, pid or "unknown"),
                        "requirement_code": code or None,
                        "jurisdiction": juris,
                    }
                total_rows += inc

        if len(batch) < take:
            break

    top_req = sorted(per_requirement_counts.items(), key=lambda x: -x[1])[:20]
    top_requirements_generating_gaps: List[Dict[str, Any]] = []
    for rid, cnt in top_req:
        meta = dict(requirement_meta.get(rid, {}))
        meta["proposed_gap_rows"] = cnt
        top_requirements_generating_gaps.append(meta)

    by_property_sorted = sorted(
        (
            {
                "property_id": pid,
                "proposed_gap_rows": n,
                "property_label": property_labels.get(pid, pid),
            }
            for pid, n in by_property.items()
        ),
        key=lambda x: -x["proposed_gap_rows"],
    )[:50]

    return {
        "inspect_mode": "net_new_only" if net_new_only else "all_inferred",
        "scoped_client_id": client_id,
        "scoped_property_id": property_id,
        "requirements_scanned": requirements_scanned,
        "requirements_active": requirements_active,
        "proposed_gap_rows_total": total_rows,
        "requirements_with_any_proposed_gap": len(per_requirement_counts),
        "by_gap_kind": dict(sorted(by_kind.items(), key=lambda x: -x[1])),
        "by_severity": dict(sorted(by_severity.items(), key=lambda x: -x[1])),
        "by_jurisdiction": dict(sorted(by_jurisdiction.items(), key=lambda x: -x[1])),
        "by_property": dict(sorted(by_property.items(), key=lambda x: -x[1])[:50]),
        "by_property_sorted": by_property_sorted,
        "by_action_type": dict(sorted(by_action_type.items(), key=lambda x: -x[1])),
        "by_policy_signature": dict(sorted(by_policy_signature.items(), key=lambda x: -x[1])[:40]),
        "by_action_type_and_policy": dict(sorted(by_action_type_and_policy.items(), key=lambda x: -x[1])[:40]),
        "top_20_requirements_generating_gaps": top_requirements_generating_gaps,
        "errors": errors,
        "error_count": len(errors),
    }


__all__ = [
    "build_requirements_query",
    "inspect_proposed_gap_composition",
    "preview_gap_persistence_delta",
    "run_compliance_gaps_backfill",
    "transition_counts",
    "_desired_open_gap_keys",
]
