"""
Aggregated contractor portal dashboard metrics (work queues + earnings).
Keeps computation server-side so the UI stays thin and consistent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from database import database

# Align with maintenance_service terminal / active semantics
_TERMINAL = frozenset({"CANCELLED", "COMPLETED", "CLOSED", "VERIFIED"})
_ACTIVE = frozenset({"OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS", "AWAITING_PARTS"})


def _parse_iso(dt_raw: Any) -> Optional[datetime]:
    if not dt_raw:
        return None
    try:
        s = dt_raw if isinstance(dt_raw, str) else str(dt_raw)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except (ValueError, TypeError):
        return None


def _work_order_active(st: str) -> bool:
    return st in _ACTIVE


def _is_pending_schedule(wo: Dict[str, Any]) -> bool:
    st = (wo.get("status") or "").strip().upper()
    if st in _TERMINAL:
        return False
    if not _work_order_active(st):
        return False
    ss = (wo.get("schedule_status") or "").strip().lower()
    if ss == "confirmed" and wo.get("scheduled_at"):
        return False
    return True


def _is_overdue_sla(wo: Dict[str, Any], now: datetime) -> bool:
    st = (wo.get("status") or "").strip().upper()
    if st in _TERMINAL:
        return False
    if not _work_order_active(st):
        return False
    due = _parse_iso(wo.get("sla_complete_by"))
    if not due:
        return False
    return due < now


async def build_contractor_dashboard_summary(contractor_id: str) -> Dict[str, Any]:
    db = database.get_db()
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    q = {"contractor_id": contractor_id}
    cursor = db.work_orders.find(q, {"_id": 0})
    work_orders: List[Dict[str, Any]] = await cursor.to_list(length=5000)

    overdue = 0
    pending_schedule = 0
    completed = 0

    for wo in work_orders:
        st = (wo.get("status") or "").strip().upper()
        if st in ("COMPLETED", "VERIFIED", "CLOSED"):
            completed += 1
        if _is_overdue_sla(wo, now):
            overdue += 1
        if _is_pending_schedule(wo):
            pending_schedule += 1

    inv_cursor = db.invoices.find({"contractor_id": contractor_id}, {"_id": 0})
    invoices: List[Dict[str, Any]] = await inv_cursor.to_list(length=2000)

    wo_with_invoice: Set[str] = set()
    pending_approval_total = 0.0
    ready_to_invoice_estimated = 0.0
    paid_month_total = 0.0

    for inv in invoices:
        wid = (inv.get("work_order_id") or "").strip()
        if wid:
            wo_with_invoice.add(wid)
        status = (inv.get("status") or "").strip().lower()
        amt = inv.get("submitted_amount")
        try:
            amt_f = float(amt) if amt is not None else 0.0
        except (TypeError, ValueError):
            amt_f = 0.0

        if status in ("pending", "needs_info"):
            pending_approval_total += amt_f
        paid_at = _parse_iso(inv.get("paid_at"))
        if status == "paid" and paid_at and paid_at >= month_start:
            paid_month_total += amt_f

    ready_to_invoice_jobs = 0
    for wo in work_orders:
        st = (wo.get("status") or "").strip().upper()
        wid = (wo.get("work_order_id") or "").strip()
        if not wid or wid in wo_with_invoice:
            continue
        if st not in ("COMPLETED", "VERIFIED", "CLOSED"):
            continue
        ready_to_invoice_jobs += 1
        mx = wo.get("cost_estimate_max")
        mn = wo.get("cost_estimate_min")
        try:
            if mx is not None:
                ready_to_invoice_estimated += float(mx)
            elif mn is not None:
                ready_to_invoice_estimated += float(mn)
        except (TypeError, ValueError):
            pass

    return {
        "generated_at": now.isoformat(),
        "work_orders": {
            "overdue": overdue,
            "pending_scheduling": pending_schedule,
            "completed": completed,
            "total_assigned": len(work_orders),
        },
        "earnings_gbp": {
            "pending_approval_total": round(pending_approval_total, 2),
            "ready_to_invoice_jobs": ready_to_invoice_jobs,
            "ready_to_invoice_estimated_total": round(ready_to_invoice_estimated, 2),
            "paid_this_month_total": round(paid_month_total, 2),
        },
        "notes": {
            "ready_to_invoice": "ready_to_invoice_jobs = completed work orders with no invoice. "
            "ready_to_invoice_estimated_total sums cost_estimate_max/min where present — indicative only.",
        },
    }
