"""
Month-to-date ROI-style metrics for client dashboard (v1 approximations).
Read-only aggregates; safe to call on a separate request so main dashboard stays fast.

Maintainability notes (v1 watch items):
- Compliance count: blends "compliant requirements touched this calendar month" with a fallback to
  current portfolio compliant count when the monthly count is zero. UI/label may need splitting if
  users expect a strict month-to-date-only number.
- Jobs "on time": completion with no sla_complete_by is treated as on-time (v1). If many jobs lack
  SLA targets, jobs_on_time may be inflated; see diagnostics.jobs_on_time_without_sla_deadline.
- "SLA breaches avoided": descriptive count only — jobs that had sla_breach_risk_at, no
  sla_breached_at, and completed by deadline. Does not prove Pleerity caused the avoidance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_COMPLIANT_STATUSES = frozenset({"COMPLIANT", "VALID"})
_TERMINAL_JOB_STATUSES = frozenset({"COMPLETED", "VERIFIED", "CLOSED"})


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str) and val.strip():
        try:
            s = val.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _month_start_utc(now: Optional[datetime] = None) -> datetime:
    n = now or datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    return datetime(n.year, n.month, 1, tzinfo=timezone.utc)


def _has_sla_deadline(wo: Dict[str, Any]) -> bool:
    s = wo.get("sla_complete_by")
    return bool(s and str(s).strip())


def _job_completed_on_time(wo: Dict[str, Any]) -> bool:
    """
    True if completed without a recorded breach and by sla_complete_by when that field exists.
    v1: missing sla_complete_by counts as on-time (may inflate the headline metric if many jobs have no SLA).
    """
    if wo.get("sla_breached_at"):
        return False
    c_at = _parse_dt(wo.get("completed_at"))
    s_at = _parse_dt(wo.get("sla_complete_by"))
    if c_at and s_at:
        return c_at <= s_at
    if s_at is None:
        return True
    return False


def _job_sla_breach_avoided(wo: Dict[str, Any]) -> bool:
    """
    Eligible for "SLA breaches avoided" tally: had near-breach signal, no breach recorded.
    Caller must also require completion on time — see get_roi_summary_month_to_date.
    """
    risk = wo.get("sla_breach_risk_at")
    if not risk or not str(risk).strip():
        return False
    breached = wo.get("sla_breached_at")
    if breached and str(breached).strip():
        return False
    return True


async def get_roi_summary_month_to_date(client_id: str, db) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    month_start = _month_start_utc(now)
    # Work orders store completed_at as ISO strings; compare as string for index-friendly query.
    month_start_iso = month_start.isoformat().replace("+00:00", "Z")

    compliance_month = 0
    compliance_snapshot = 0
    requirements_scan_ok = True
    try:
        cursor = db.requirements.find(
            {"client_id": client_id},
            {"_id": 0, "status": 1, "updated_at": 1},
        )
        async for r in cursor:
            st = (r.get("status") or "").upper()
            if st not in _COMPLIANT_STATUSES:
                continue
            compliance_snapshot += 1
            u_at = _parse_dt(r.get("updated_at"))
            if u_at and u_at >= month_start:
                compliance_month += 1
    except Exception:
        logger.exception("ROI requirements scan failed client_id=%s", client_id)
        requirements_scan_ok = False

    if not requirements_scan_ok:
        compliance_items = 0
        compliance_basis = "unavailable"
    elif compliance_month > 0:
        compliance_items = compliance_month
        compliance_basis = "month_updates"
    else:
        compliance_items = compliance_snapshot
        compliance_basis = "portfolio_snapshot"

    jobs_on_time = 0
    jobs_in_period = 0
    sla_avoided = 0
    jobs_in_period_without_sla_deadline = 0
    jobs_on_time_without_sla_deadline = 0
    work_orders_scan_ok = True
    try:
        q = {
            "client_id": client_id,
            "status": {"$in": list(_TERMINAL_JOB_STATUSES)},
            "completed_at": {"$gte": month_start_iso},
        }
        proj = {
            "_id": 0,
            "completed_at": 1,
            "sla_complete_by": 1,
            "sla_breached_at": 1,
            "sla_breach_risk_at": 1,
        }
        cursor = db.work_orders.find(q, proj)
        async for wo in cursor:
            c_at = _parse_dt(wo.get("completed_at"))
            if c_at is None or c_at < month_start:
                continue
            jobs_in_period += 1
            has_deadline = _has_sla_deadline(wo)
            if not has_deadline:
                jobs_in_period_without_sla_deadline += 1
            on_time = _job_completed_on_time(wo)
            if on_time:
                jobs_on_time += 1
                if not has_deadline:
                    jobs_on_time_without_sla_deadline += 1
            if _job_sla_breach_avoided(wo) and on_time:
                sla_avoided += 1
    except Exception:
        logger.exception("ROI work orders scan failed client_id=%s", client_id)
        work_orders_scan_ok = False

    return {
        "period_label": "This month",
        "period_start": month_start_iso,
        "period_end": now.isoformat().replace("+00:00", "Z"),
        "compliance_items_up_to_date": compliance_items,
        "compliance_basis": compliance_basis,
        "jobs_completed_on_time": jobs_on_time,
        "jobs_completed_in_period": jobs_in_period,
        "sla_breaches_avoided": sla_avoided,
        "approximate": True,
        "diagnostics": {
            "requirements_scan_ok": requirements_scan_ok,
            "work_orders_scan_ok": work_orders_scan_ok,
            "jobs_in_period_without_sla_deadline": jobs_in_period_without_sla_deadline,
            "jobs_on_time_without_sla_deadline": jobs_on_time_without_sla_deadline,
        },
    }
