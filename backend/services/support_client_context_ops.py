"""
Read-only operational reconstruction slice for admin support context.

Fixes INV-SU-001 (degrade-not-fail) and INV-SU-002 (ops summary).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def sanitize_for_json(value: Any) -> Any:
    """Recursively coerce Mongo/BSON values for FastAPI JSON responses (INV-SU-001)."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_for_json(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    type_name = type(value).__name__
    if type_name == "ObjectId":
        return str(value)
    if type_name == "Decimal128":
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return value

OPEN_ISSUE_STATUSES = (
    "open",
    "new",
    "triaged",
    "monitoring",
    "investigating",
    "ready_for_work_order",
    "in_progress",
)

ACTIVE_RISK_STATUSES = ("active", "acknowledged", "remediation_in_progress")

TERMINAL_WO_STATUSES = frozenset({"COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"})
OPEN_WO_STATUSES = frozenset({"OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS", "AWAITING_PARTS", "DRAFT"})


def _iso_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


async def _safe_property_ids(db, client_id: str) -> List[str]:
    ids: List[str] = []
    try:
        async for p in db.properties.find({"client_id": client_id}, {"property_id": 1, "_id": 0}):
            pid = p.get("property_id")
            if pid:
                ids.append(str(pid))
    except Exception as exc:
        logger.warning("support.context.ops property_ids failed client_id=%s: %s", client_id, exc)
    return ids


async def build_ops_summary_v1(db, client_id: str) -> Dict[str, Any]:
    """
    Operational reconstruction for support. Never raises — returns degraded payload on failure.
    """
    out: Dict[str, Any] = {
        "available": True,
        "degraded_sections": [],
        "counts": {},
        "recent_issues": [],
        "recent_work_orders": [],
        "recent_risk_signals": [],
        "lifecycle_highlights": [],
    }
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    try:
        open_issues = await db.maintenance_issues.count_documents(
            {"client_id": client_id, "status": {"$in": list(OPEN_ISSUE_STATUSES)}}
        )
        out["counts"]["open_issues"] = open_issues
    except Exception as exc:
        out["degraded_sections"].append({"section": "open_issues_count", "error": str(exc)[:200]})
        logger.warning("support.context.ops open_issues_count failed: %s", exc)

    try:
        open_wos = await db.work_orders.count_documents(
            {"client_id": client_id, "status": {"$in": list(OPEN_WO_STATUSES)}}
        )
        out["counts"]["open_work_orders"] = open_wos
    except Exception as exc:
        out["degraded_sections"].append({"section": "open_work_orders_count", "error": str(exc)[:200]})

    try:
        active_risk = await db.risk_signals.count_documents(
            {"client_id": client_id, "status": {"$in": list(ACTIVE_RISK_STATUSES)}}
        )
        out["counts"]["active_risk_signals"] = active_risk
    except Exception as exc:
        out["degraded_sections"].append({"section": "active_risk_signals_count", "error": str(exc)[:200]})

    try:
        stale = 0
        cursor = db.maintenance_issues.find(
            {"client_id": client_id, "status": {"$in": ["triaged", "monitoring", "investigating"]}},
            {"_id": 0, "updated_at": 1, "created_at": 1},
        )
        async for row in cursor:
            ts = _parse_dt(row.get("updated_at") or row.get("created_at"))
            if ts and ts < stale_cutoff:
                stale += 1
        out["counts"]["stale_issues_over_7d"] = stale
    except Exception as exc:
        out["degraded_sections"].append({"section": "stale_issues_over_7d", "error": str(exc)[:200]})

    try:
        no_ctr = await db.work_orders.count_documents(
            {
                "client_id": client_id,
                "status": {"$in": ["OPEN", "ASSIGNED", "SCHEDULED"]},
                "$or": [{"contractor_id": None}, {"contractor_id": ""}],
            }
        )
        out["counts"]["jobs_open_without_contractor"] = no_ctr
    except Exception as exc:
        out["degraded_sections"].append({"section": "jobs_open_without_contractor", "error": str(exc)[:200]})

    try:
        issue_rows = await db.maintenance_issues.find(
            {"client_id": client_id},
            {
                "_id": 0,
                "issue_id": 1,
                "status": 1,
                "severity": 1,
                "description": 1,
                "property_id": 1,
                "updated_at": 1,
                "resolved_at": 1,
                "closed_at": 1,
            },
        ).sort("updated_at", -1).limit(12).to_list(length=12)
        out["recent_issues"] = [
            {
                "issue_id": r.get("issue_id"),
                "status": r.get("status"),
                "severity": r.get("severity"),
                "description": (r.get("description") or "")[:120],
                "property_id": r.get("property_id"),
                "updated_at": _iso_ts(r.get("updated_at")),
                "resolved_at": _iso_ts(r.get("resolved_at")),
                "closed_at": _iso_ts(r.get("closed_at")),
            }
            for r in issue_rows
        ]
    except Exception as exc:
        out["degraded_sections"].append({"section": "recent_issues", "error": str(exc)[:200]})

    try:
        wo_rows = await db.work_orders.find(
            {"client_id": client_id},
            {
                "_id": 0,
                "work_order_id": 1,
                "status": 1,
                "description": 1,
                "property_id": 1,
                "contractor_id": 1,
                "operational_exception": 1,
                "completed_at": 1,
                "verified_at": 1,
                "updated_at": 1,
                "issue_id": 1,
            },
        ).sort("updated_at", -1).limit(12).to_list(length=12)
        out["recent_work_orders"] = [
            {
                "work_order_id": r.get("work_order_id"),
                "status": r.get("status"),
                "description": (r.get("description") or "")[:120],
                "property_id": r.get("property_id"),
                "contractor_id": r.get("contractor_id"),
                "operational_exception": r.get("operational_exception"),
                "issue_id": r.get("issue_id"),
                "completed_at": _iso_ts(r.get("completed_at")),
                "verified_at": _iso_ts(r.get("verified_at")),
                "updated_at": _iso_ts(r.get("updated_at")),
            }
            for r in wo_rows
        ]
    except Exception as exc:
        out["degraded_sections"].append({"section": "recent_work_orders", "error": str(exc)[:200]})

    try:
        rs_rows = await db.risk_signals.find(
            {"client_id": client_id},
            {
                "_id": 0,
                "signal_id": 1,
                "status": 1,
                "risk_type": 1,
                "risk_level": 1,
                "property_id": 1,
                "acknowledged_at": 1,
                "resolved_at": 1,
                "updated_at": 1,
                "dismiss_reason": 1,
            },
        ).sort("updated_at", -1).limit(12).to_list(length=12)
        out["recent_risk_signals"] = [
            {
                "signal_id": r.get("signal_id"),
                "status": r.get("status"),
                "risk_type": r.get("risk_type"),
                "risk_level": r.get("risk_level"),
                "property_id": r.get("property_id"),
                "acknowledged_at": _iso_ts(r.get("acknowledged_at")),
                "resolved_at": _iso_ts(r.get("resolved_at")),
                "updated_at": _iso_ts(r.get("updated_at")),
                "dismiss_reason": r.get("dismiss_reason"),
            }
            for r in rs_rows
        ]
    except Exception as exc:
        out["degraded_sections"].append({"section": "recent_risk_signals", "error": str(exc)[:200]})

    highlights: List[Dict[str, Any]] = []
    for wo in out["recent_work_orders"][:5]:
        if (wo.get("status") or "").upper() in OPEN_WO_STATUSES and not wo.get("contractor_id"):
            highlights.append(
                {
                    "kind": "job_deadlock_unassigned",
                    "work_order_id": wo.get("work_order_id"),
                    "status": wo.get("status"),
                }
            )
        if wo.get("operational_exception"):
            highlights.append(
                {
                    "kind": "operational_hold",
                    "work_order_id": wo.get("work_order_id"),
                    "hold": wo.get("operational_exception"),
                }
            )
    for iss in out["recent_issues"][:5]:
        st = (iss.get("status") or "").lower()
        if st in ("triaged", "monitoring", "investigating"):
            ts = _parse_dt(iss.get("updated_at"))
            if ts and ts < stale_cutoff:
                highlights.append(
                    {"kind": "stale_issue", "issue_id": iss.get("issue_id"), "status": st, "updated_at": iss.get("updated_at")}
                )
    out["lifecycle_highlights"] = highlights[:15]

    if out["degraded_sections"]:
        out["available"] = len(out["degraded_sections"]) < 4
        logger.info(
            "support.context.ops degraded client_id=%s sections=%s",
            client_id,
            [s.get("section") for s in out["degraded_sections"]],
        )

    try:
        from services.operational_value_compression_service import build_operational_value_bundle_v1

        out["operational_value_v1"] = await build_operational_value_bundle_v1(client_id)
    except Exception as exc:
        logger.warning("support ops operational_value_v1 degraded client_id=%s: %s", client_id, exc)
        out["operational_value_v1"] = {"available": False, "error": str(exc)[:200]}

    return out
