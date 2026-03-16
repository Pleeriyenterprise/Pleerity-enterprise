"""
Contractor Intelligence Layer: compute performance metrics and overall score from operational data.
Metrics: reliability_score, average_response_time, average_completion_time, sla_success_rate, invoice_approval_rate.
Overall score (0-100): 40% reliability, 25% SLA, 20% response time, 15% invoice approval.
Stored on contractor doc; used by recommendation and admin analytics.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import logging

from database import database

logger = logging.getLogger(__name__)

# Weights for overall score (must sum to 1.0)
WEIGHT_RELIABILITY = 0.40
WEIGHT_SLA = 0.25
WEIGHT_RESPONSE_TIME = 0.20
WEIGHT_INVOICE_APPROVAL = 0.15

# Response time: 0–24h = 1.0, 24–72h = linear decay, 72h+ = 0. Response component uses this.
RESPONSE_HOURS_FULL_SCORE = 24.0
RESPONSE_HOURS_ZERO_SCORE = 72.0


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _hours_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[float]:
    if start is None or end is None:
        return None
    try:
        delta = end - start
        return delta.total_seconds() / 3600.0
    except Exception:
        return None


async def compute_metrics_for_contractor(contractor_id: str) -> Dict[str, Any]:
    """
    Compute all performance metrics for one contractor from work_orders, contractor_performance, invoices.
    Returns dict: reliability_score (0-1), average_response_time_hours, average_completion_time_hours,
    sla_success_rate (0-1), invoice_approval_rate (0-1), assigned_jobs, completed_jobs.
    """
    db = database.get_db()

    # Assigned jobs: work orders ever assigned to this contractor (contractor_assignments or work_orders)
    assigned_count = await db.work_orders.count_documents({"contractor_id": contractor_id})

    # Completed jobs and SLA: from contractor_performance (aggregate across clients)
    cursor = db.contractor_performance.find({"contractor_id": contractor_id}, {"_id": 0, "jobs_completed": 1, "jobs_on_time": 1})
    total_completed = 0
    total_on_time = 0
    async for row in cursor:
        total_completed += row.get("jobs_completed") or 0
        total_on_time += row.get("jobs_on_time") or 0

    reliability_score = (total_completed / assigned_count) if assigned_count else None

    # Response time: assigned_at -> accepted_at for WOs that have both
    wo_cursor = db.work_orders.find(
        {"contractor_id": contractor_id, "assigned_at": {"$exists": True, "$ne": None}, "accepted_at": {"$exists": True, "$ne": None}},
        {"_id": 0, "assigned_at": 1, "accepted_at": 1},
    )
    response_hours_list: List[float] = []
    async for wo in wo_cursor:
        a = _parse_dt(wo.get("assigned_at"))
        b = _parse_dt(wo.get("accepted_at"))
        h = _hours_between(a, b)
        if h is not None and h >= 0:
            response_hours_list.append(h)
    average_response_time_hours = round(sum(response_hours_list) / len(response_hours_list), 2) if response_hours_list else None

    # Completion time: (accepted_at or assigned_at) -> completed_at
    wo_cursor2 = db.work_orders.find(
        {"contractor_id": contractor_id, "status": "COMPLETED", "completed_at": {"$exists": True, "$ne": None}},
        {"_id": 0, "assigned_at": 1, "accepted_at": 1, "completed_at": 1},
    )
    completion_hours_list: List[float] = []
    async for wo in wo_cursor2:
        start = _parse_dt(wo.get("accepted_at") or wo.get("assigned_at"))
        end = _parse_dt(wo.get("completed_at"))
        h = _hours_between(start, end)
        if h is not None and h >= 0:
            completion_hours_list.append(h)
    average_completion_time_hours = round(sum(completion_hours_list) / len(completion_hours_list), 2) if completion_hours_list else None

    sla_success_rate = (total_on_time / total_completed) if total_completed else None

    # Invoice approval: contractor-submitted invoices, approved (or paid) / total
    inv_cursor = db.invoices.find(
        {"contractor_id": contractor_id},
        {"_id": 0, "status": 1},
    )
    submitted = 0
    approved = 0
    async for inv in inv_cursor:
        submitted += 1
        s = (inv.get("status") or "").strip().lower()
        if s in ("approved", "paid"):
            approved += 1
    invoice_approval_rate = (approved / submitted) if submitted else None

    return {
        "reliability_score": round(reliability_score, 4) if reliability_score is not None else None,
        "average_response_time_hours": average_response_time_hours,
        "average_completion_time_hours": average_completion_time_hours,
        "sla_success_rate": round(sla_success_rate, 4) if sla_success_rate is not None else None,
        "invoice_approval_rate": round(invoice_approval_rate, 4) if invoice_approval_rate is not None else None,
        "assigned_jobs": assigned_count,
        "completed_jobs": total_completed,
    }


def _response_time_component(average_response_time_hours: Optional[float]) -> float:
    """Map response time (hours) to 0-1 score: faster = higher. 24h = 1, 72h+ = 0."""
    if average_response_time_hours is None:
        return 0.0
    if average_response_time_hours <= RESPONSE_HOURS_FULL_SCORE:
        return 1.0
    if average_response_time_hours >= RESPONSE_HOURS_ZERO_SCORE:
        return 0.0
    return 1.0 - (average_response_time_hours - RESPONSE_HOURS_FULL_SCORE) / (RESPONSE_HOURS_ZERO_SCORE - RESPONSE_HOURS_FULL_SCORE)


def compute_overall_score(metrics: Dict[str, Any]) -> Optional[float]:
    """
    Combine metrics into overall score 0-100.
    Weights: reliability 40%, SLA 25%, response time 20%, invoice approval 15%.
    """
    r = metrics.get("reliability_score")
    s = metrics.get("sla_success_rate")
    resp = metrics.get("average_response_time_hours")
    inv = metrics.get("invoice_approval_rate")
    # If no data at all, return None
    if r is None and s is None and resp is None and inv is None:
        return None
    score = 0.0
    weight_used = 0.0
    if r is not None:
        score += WEIGHT_RELIABILITY * r
        weight_used += WEIGHT_RELIABILITY
    if s is not None:
        score += WEIGHT_SLA * s
        weight_used += WEIGHT_SLA
    if resp is not None:
        score += WEIGHT_RESPONSE_TIME * _response_time_component(resp)
        weight_used += WEIGHT_RESPONSE_TIME
    if inv is not None:
        score += WEIGHT_INVOICE_APPROVAL * inv
        weight_used += WEIGHT_INVOICE_APPROVAL
    if weight_used == 0:
        return None
    # Normalize to 0-100 if we only had partial data
    return round((score / weight_used) * 100.0, 2)


async def update_contractor_performance_score(contractor_id: str, audit: bool = True) -> Optional[Dict[str, Any]]:
    """
    Compute metrics and overall score for one contractor and persist to contractor doc.
    Sets: reliability_score, average_response_time_hours, average_completion_time_hours,
    sla_success_rate, invoice_approval_rate, performance_score, performance_score_updated_at,
    assigned_jobs, completed_jobs (for display).
    """
    from utils.audit import create_audit_log
    from models import AuditAction

    metrics = await compute_metrics_for_contractor(contractor_id)
    score = compute_overall_score(metrics)
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {
        "reliability_score": metrics.get("reliability_score"),
        "average_response_time_hours": metrics.get("average_response_time_hours"),
        "average_completion_time_hours": metrics.get("average_completion_time_hours"),
        "sla_success_rate": metrics.get("sla_success_rate"),
        "invoice_approval_rate": metrics.get("invoice_approval_rate"),
        "performance_score": score,
        "performance_score_updated_at": now,
        "assigned_jobs": metrics.get("assigned_jobs", 0),
        "completed_jobs": metrics.get("completed_jobs", 0),
    }
    result = await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": set_fields},
    )
    if not result.modified_count and not result.matched_count:
        return None
    if audit:
        try:
            await create_audit_log(
                action=AuditAction.CONTRACTOR_PERFORMANCE_SCORE_UPDATED,
                actor_id="system",
                resource_type="contractor",
                resource_id=contractor_id,
                metadata={"performance_score": score, "reliability_score": metrics.get("reliability_score"), "completed_jobs": metrics.get("completed_jobs")},
            )
        except Exception as e:
            logger.warning("Audit log for contractor score update failed: %s", e)
    logger.info("contractor_intelligence contractor_id=%s performance_score=%s reliability=%s", contractor_id, score, metrics.get("reliability_score"))
    return {**metrics, "performance_score": score}


async def recalculate_all_contractors(audit: bool = True) -> Tuple[int, int]:
    """
    Recalculate metrics and score for all contractors. Returns (processed_count, error_count).
    """
    db = database.get_db()
    cursor = db.contractors.find({}, {"_id": 0, "contractor_id": 1})
    ids = [doc["contractor_id"] async for doc in cursor]
    processed = 0
    errors = 0
    for cid in ids:
        try:
            await update_contractor_performance_score(cid, audit=audit)
            processed += 1
        except Exception as e:
            logger.warning("contractor_intelligence recalc failed for %s: %s", cid, e)
            errors += 1
    return processed, errors


async def list_contractor_analytics(
    view: str = "top_performers",
    client_id: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Admin analytics: list contractors by performance view.
    view: top_performers (by performance_score desc), sla_issues (low sla_success_rate), high_rejection (low invoice_approval_rate).
    """
    db = database.get_db()
    q = {}
    if client_id:
        q["client_id"] = client_id
    # Only contractors that have been assigned at least one job (have assigned_jobs or performance_score)
    cursor = db.contractors.find(q, {
        "_id": 0,
        "contractor_id": 1,
        "name": 1,
        "company_name": 1,
        "trade_types": 1,
        "status": 1,
        "performance_score": 1,
        "reliability_score": 1,
        "sla_success_rate": 1,
        "invoice_approval_rate": 1,
        "assigned_jobs": 1,
        "completed_jobs": 1,
        "average_response_time_hours": 1,
        "average_completion_time_hours": 1,
    })
    contractors = await cursor.to_list(2000)
    if view == "top_performers":
        contractors = [c for c in contractors if c.get("performance_score") is not None]
        contractors.sort(key=lambda c: (c.get("performance_score") or 0), reverse=True)
    elif view == "sla_issues":
        contractors = [c for c in contractors if c.get("sla_success_rate") is not None and (c.get("sla_success_rate") or 0) < 0.8]
        contractors.sort(key=lambda c: (c.get("sla_success_rate") or 1))
    elif view == "high_rejection":
        contractors = [c for c in contractors if c.get("invoice_approval_rate") is not None and (c.get("invoice_approval_rate") or 1) < 0.8]
        contractors.sort(key=lambda c: (c.get("invoice_approval_rate") or 1))
    else:
        contractors = [c for c in contractors if c.get("performance_score") is not None]
        contractors.sort(key=lambda c: (c.get("performance_score") or 0), reverse=True)
    return {"contractors": contractors[:limit], "total": len(contractors), "view": view}
