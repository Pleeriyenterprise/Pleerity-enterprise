"""
Persist compliance gaps and resolve stale rows when evidence truth changes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models import AuditAction
from utils.audit import create_audit_log

from services.compliance_gap_engine import infer_compliance_gaps_for_requirement
from services.compliance_gap_operational_bridge import apply_gap_operational_bridge
from services.compliance_gap_policy_aggregate import aggregate_policy_gap_counts_for_client

logger = logging.getLogger(__name__)


async def sync_compliance_gaps_for_requirement(
    db,
    requirement: Dict[str, Any],
    *,
    property_doc: Optional[Dict[str, Any]] = None,
    audit_lifecycle: bool = True,
    run_operational_bridge: bool = True,
) -> Dict[str, Any]:
    """
    Recompute gaps from the requirement row, upsert open documents, resolve removed gaps,
    then run operational bridge (idempotent issues / audit).

    ``audit_lifecycle``: when False, skip COMPLIANCE_GAP_OPENED / COMPLIANCE_GAP_RESOLVED logs
    (e.g. bulk backfill with a single summary audit).

    ``run_operational_bridge``: when False, skip issue bridge (writes to compliance_gaps only).

    Returns ``{"rows": [...], "errors": [...]}`` — failures are listed in ``errors`` (``gap_key`` when applicable).
    """
    rid = requirement.get("requirement_id")
    cid = requirement.get("client_id")
    if not rid or not cid:
        return {"rows": [], "errors": []}
    from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces
    runtime_visible = await requirement_row_eligible_on_client_runtime_surfaces(
        db,
        client_id=str(cid),
        row=requirement,
        property_doc=property_doc,
    )
    if not runtime_visible:
        now = datetime.now(timezone.utc).isoformat()
        await db.compliance_gaps.update_many(
            {"requirement_id": str(rid), "client_id": str(cid), "status": "open"},
            {"$set": {"status": "resolved", "resolved_at": now, "updated_at": now, "resolved_reason": "runtime_excluded"}},
        )
        return {"rows": [], "errors": []}

    sync_errors: List[Dict[str, Any]] = []
    gaps = infer_compliance_gaps_for_requirement(requirement, property_doc=property_doc)
    now = datetime.now(timezone.utc).isoformat()
    open_keys: List[str] = []
    rows: List[Dict[str, Any]] = []

    for g in gaps:
        row = g.to_mongo(
            client_id=str(cid),
            property_id=str(requirement.get("property_id") or ""),
            requirement_id=str(rid),
            requirement_code=(
                str(requirement.get("requirement_code") or requirement.get("code") or requirement.get("requirement_type") or "")
            ),
            requirement_row=requirement,
        )
        row["status"] = "open"
        row["updated_at"] = now
        gap_key = str(row.get("gap_key") or "")
        # MongoDB forbids the same path in $set and $setOnInsert — keep created_at only in $setOnInsert.
        set_doc = {k: v for k, v in row.items() if k != "created_at"}
        try:
            res = await db.compliance_gaps.update_one(
                {"gap_key": gap_key},
                {"$set": set_doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            open_keys.append(gap_key)
            rows.append(row)
            if audit_lifecycle and getattr(res, "upserted_id", None) is not None:
                try:
                    await create_audit_log(
                        action=AuditAction.COMPLIANCE_GAP_OPENED,
                        client_id=str(cid),
                        resource_type="compliance_gap",
                        resource_id=str(row.get("gap_key") or ""),
                        metadata={
                            "requirement_id": str(rid),
                            "gap_kind": row.get("gap_kind"),
                            "severity": row.get("severity"),
                            "property_id": str(requirement.get("property_id") or ""),
                        },
                    )
                except Exception as aud_e:
                    logger.warning("compliance_gap open audit failed gap_key=%s: %s", row.get("gap_key"), aud_e)
        except Exception as e:
            err = {
                "stage": "upsert",
                "gap_key": gap_key,
                "requirement_id": str(rid),
                "client_id": str(cid),
                "error": str(e),
            }
            sync_errors.append(err)
            logger.error("compliance_gaps upsert failed gap_key=%s: %s", gap_key, e)

    skip_resolve = bool(gaps) and not open_keys and bool(sync_errors)
    if skip_resolve:
        sync_errors.append(
            {
                "stage": "resolve_skipped",
                "requirement_id": str(rid),
                "client_id": str(cid),
                "reason": "all_upserts_failed",
            }
        )
        logger.error(
            "compliance_gaps resolve skipped for requirement_id=%s (all upserts failed; count=%s)",
            rid,
            len(sync_errors) - 1,
        )
    else:
        # Resolve gaps that are no longer emitted for this requirement
        try:
            q: Dict[str, Any] = {"requirement_id": str(rid), "client_id": str(cid), "status": "open"}
            if open_keys:
                q["gap_key"] = {"$nin": open_keys}
            stale = await db.compliance_gaps.find(q, {"_id": 0, "gap_key": 1, "gap_kind": 1}).to_list(500)
            res = await db.compliance_gaps.update_many(
                q,
                {"$set": {"status": "resolved", "resolved_at": now, "updated_at": now}},
            )
            if audit_lifecycle and res.modified_count and stale:
                logger.debug("Resolved %s stale compliance gaps for requirement %s", res.modified_count, rid)
                try:
                    await create_audit_log(
                        action=AuditAction.COMPLIANCE_GAP_RESOLVED,
                        client_id=str(cid),
                        resource_type="requirement",
                        resource_id=str(rid),
                        metadata={
                            "property_id": str(requirement.get("property_id") or ""),
                            "resolved_gap_count": len(stale),
                            "resolved_gaps": [{"gap_key": s.get("gap_key"), "gap_kind": s.get("gap_kind")} for s in stale],
                        },
                    )
                except Exception as aud_e:
                    logger.warning("compliance_gap resolve audit failed requirement_id=%s: %s", rid, aud_e)
        except Exception as e:
            sync_errors.append(
                {
                    "stage": "resolve",
                    "requirement_id": str(rid),
                    "client_id": str(cid),
                    "error": str(e),
                }
            )
            logger.error("compliance_gaps resolve failed requirement_id=%s: %s", rid, e)

    if run_operational_bridge:
        try:
            await apply_gap_operational_bridge(db, rows, requirement)
        except Exception as e:
            sync_errors.append(
                {
                    "stage": "operational_bridge",
                    "requirement_id": str(rid),
                    "client_id": str(cid),
                    "error": str(e),
                }
            )
            logger.error("gap operational bridge failed requirement_id=%s: %s", rid, e)

    return {"rows": rows, "errors": sync_errors}


async def aggregate_gap_counts_for_client(db, client_id: str, property_id: Optional[str] = None) -> Dict[str, Any]:
    """Dashboard / Command Centre summary counts (persisted open gaps)."""
    match: Dict[str, Any] = {"client_id": client_id, "status": "open"}
    if property_id:
        match["property_id"] = property_id
    pipeline = [
        {"$match": match},
        {"$group": {"_id": {"kind": "$gap_kind", "sev": "$severity"}, "c": {"$sum": 1}}},
    ]
    try:
        cur = db.compliance_gaps.aggregate(pipeline)
        rows = await cur.to_list(200)
    except Exception:
        policy = await aggregate_policy_gap_counts_for_client(db, client_id, property_id=property_id)
        return {"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": policy}
    by_kind: Dict[str, int] = {}
    by_sev: Dict[str, int] = {}
    total = 0
    for r in rows:
        key = r.get("_id") or {}
        k = str(key.get("kind") or "UNKNOWN")
        s = str(key.get("sev") or "UNKNOWN")
        c = int(r.get("c") or 0)
        total += c
        by_kind[k] = by_kind.get(k, 0) + c
        by_sev[s] = by_sev.get(s, 0) + c
    policy = await aggregate_policy_gap_counts_for_client(db, client_id, property_id=property_id)
    return {"by_kind": by_kind, "by_severity": by_sev, "total_open": total, "policy": policy}
