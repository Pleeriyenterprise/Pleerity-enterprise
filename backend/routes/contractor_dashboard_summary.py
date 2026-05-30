"""
Aggregated contractor portal dashboard metrics (work queues + earnings).
Keeps computation server-side so the UI stays thin and consistent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from database import database
from services.compliance_workflow_service import (
    apply_contractor_job_enrichment,
    contractor_next_job_actions,
    contractor_portal_waiting_on_others,
)

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


def _invoice_rank(inv: Dict[str, Any]) -> int:
    s = (inv.get("status") or "").lower()
    return {"paid": 5, "approved": 4, "pending": 3, "needs_info": 2, "rejected": 1}.get(s, 0)


def _best_invoice_by_work_order(contractor_id: str, invoices: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    cid = (contractor_id or "").strip()
    for inv in invoices:
        if (inv.get("contractor_id") or "").strip() != cid:
            continue
        w = (inv.get("work_order_id") or "").strip()
        if not w:
            continue
        prev = best.get(w)
        if not prev or _invoice_rank(inv) > _invoice_rank(prev):
            best[w] = inv
    return best


def _scheduled_today_utc(wo: Dict[str, Any], now: datetime) -> bool:
    st = (wo.get("status") or "").strip().upper()
    if st in _TERMINAL:
        return False
    sat = wo.get("scheduled_at")
    if not sat:
        return False
    d = _parse_iso(sat)
    if not d:
        return False
    # Compare calendar dates in UTC only: `now` is UTC; naive .date() on `d` would use the
    # offset-local calendar day (e.g. +05:30 can be "tomorrow" vs UTC same instant).
    d_utc = d.astimezone(timezone.utc)
    return d_utc.date() == now.date()


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

    inv_by_wo = _best_invoice_by_work_order(contractor_id, invoices)
    wf_action = {
        "visit_confirmation": 0,
        "proof_upload": 0,
        "invoice_submission": 0,
        "invoice_correction": 0,
    }
    jobs_active = 0
    jobs_execution_active = 0
    jobs_waiting_on_client = 0
    jobs_scheduled_today = 0
    for wo in work_orders:
        st = (wo.get("status") or "").strip().upper()
        wid = (wo.get("work_order_id") or "").strip()
        if _work_order_active(st):
            jobs_active += 1
        inv = inv_by_wo.get(wid) if wid else None
        wo_view = dict(wo)
        apply_contractor_job_enrichment(wo_view, invoice=inv)
        waiting = contractor_portal_waiting_on_others(wo_view)
        if _work_order_active(st) and not waiting:
            jobs_execution_active += 1
        if waiting:
            jobs_waiting_on_client += 1
        if _work_order_active(st) and not waiting and _scheduled_today_utc(wo, now):
            jobs_scheduled_today += 1
        acts = wo_view.get("next_actions") or contractor_next_job_actions(wo, invoice=inv)
        ids = {a.get("id") for a in acts if a.get("id")}
        if "confirm_visit" in ids:
            wf_action["visit_confirmation"] += 1
        if "upload_completion_proof" in ids:
            wf_action["proof_upload"] += 1
        if "submit_invoice" in ids:
            wf_action["invoice_submission"] += 1
        if "edit_invoice" in ids:
            wf_action["invoice_correction"] += 1

    awaiting_approval_jobs = 0
    for inv in inv_by_wo.values():
        ist = (inv.get("status") or "").lower()
        if ist in ("pending", "needs_info"):
            awaiting_approval_jobs += 1

    submit_invoice_primary_cta = wf_action["invoice_submission"] > 0

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
        "workflow": {
            "action_needed": wf_action,
            "payments": {
                "ready_to_invoice_jobs": ready_to_invoice_jobs,
                "awaiting_approval_jobs": awaiting_approval_jobs,
                "paid_this_month_total": round(paid_month_total, 2),
            },
            "jobs": {
                "active": jobs_active,
                "execution_active": jobs_execution_active,
                "waiting_on_client": jobs_waiting_on_client,
                "scheduled_today": jobs_scheduled_today,
                "overdue_at_risk": overdue,
            },
            "submit_invoice_primary_cta": submit_invoice_primary_cta,
        },
        "notes": {
            "ready_to_invoice": "ready_to_invoice_jobs = completed work orders with no invoice. "
            "ready_to_invoice_estimated_total sums cost_estimate_max/min where present — indicative only.",
        },
    }
