"""
Delivery reconciliation: enrich job run outcome_metrics with provider/delivery status from message_logs.
For reminder and digest jobs, distinguishes attempted, provider_accepted, delivered, bounced, unknown.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from database import database
from services.lifecycle_reminder_template_registry import all_lifecycle_reminder_template_keys

logger = logging.getLogger(__name__)

# Job names and their template_keys for message_log matching (email/report delivery)
RECONCILIATION_JOBS: Dict[str, List[str]] = {
    "daily_reminders": [
        "COMPLIANCE_EXPIRY_REMINDER",
        "COMPLIANCE_EXPIRY_REMINDER_SMS",
        *sorted(all_lifecycle_reminder_template_keys()),
    ],
    "monthly_digest": ["MONTHLY_DIGEST"],
    "pending_verification_digest": ["PENDING_VERIFICATION_DIGEST"],
    "compliance_check_morning": ["COMPLIANCE_ALERT"],
    "compliance_check_evening": ["COMPLIANCE_ALERT"],
    "scheduled_reports": ["SCHEDULED_REPORT"],
}

# Hours after a run finishes: if delivery_unknown > 0 still, consider it "stale" and surface a warning
DELIVERY_UNKNOWN_STALE_HOURS = 6


def _parse_iso(s):
    if s is None:
        return None
    if hasattr(s, "isoformat"):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


async def reconcile_delivery_for_run(db, run: dict) -> bool:
    """
    For a single job run (reminder, digest, verification digest, compliance check, scheduled reports),
    aggregate message_logs in the run's time window by status and update outcome_metrics with delivery_* counts.
    Returns True if outcome_metrics was updated.
    """
    job_name = run.get("job_name")
    templates = RECONCILIATION_JOBS.get(job_name)
    if not templates:
        return False

    started = _parse_iso(run.get("started_at"))
    finished = _parse_iso(run.get("finished_at"))
    if not started or not finished:
        return False

    # Window: started to finished + 2h (allow for async webhooks)
    if hasattr(finished, "timestamp"):
        window_end = finished + timedelta(hours=2)
    else:
        try:
            window_end = _parse_iso(finished)
            if window_end:
                window_end = window_end + timedelta(hours=2)
            else:
                window_end = finished
        except Exception:
            window_end = finished

    # Aggregate message_logs by status (created_at may be datetime or string in DB)
    match: Dict[str, Any] = {"template_key": {"$in": templates}}
    try:
        match["created_at"] = {"$gte": started, "$lte": window_end}
    except Exception:
        start_str = started.isoformat() if hasattr(started, "isoformat") else str(started)
        end_str = window_end.isoformat() if hasattr(window_end, "isoformat") else str(window_end)
        match["created_at"] = {"$gte": start_str, "$lte": end_str}
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    cursor = db.message_logs.aggregate(pipeline)
    counts = {}
    async for doc in cursor:
        status = (doc.get("_id") or "").upper().strip()
        counts[status] = doc.get("count", 0)

    sent_count = counts.get("SENT", 0) + counts.get("sent", 0)
    delivered_count = counts.get("DELIVERED", 0)
    bounced_count = counts.get("BOUNCED", 0)
    failed_count = counts.get("FAILED", 0)
    # Provider accepted = we got 200 from provider (SENT, DELIVERED, BOUNCED all count as accepted)
    provider_accepted = sent_count + delivered_count + bounced_count
    # Unknown = accepted by provider but delivery not yet confirmed (still SENT)
    unknown_count = sent_count

    outcome_metrics = dict(run.get("outcome_metrics") or {})
    outcome_metrics["delivery_provider_accepted"] = provider_accepted
    outcome_metrics["delivery_delivered"] = delivered_count
    outcome_metrics["delivery_bounced"] = bounced_count
    outcome_metrics["delivery_unknown"] = unknown_count
    outcome_metrics["delivery_failed"] = failed_count

    from bson import ObjectId
    oid = run.get("_id")
    if isinstance(oid, str):
        try:
            oid = ObjectId(oid)
        except Exception:
            return False
    await db.job_runs.update_one(
        {"_id": oid},
        {"$set": {"outcome_metrics": outcome_metrics}},
    )
    return True


async def run_delivery_reconciliation(hours_back: int = 48) -> Dict[str, Any]:
    """
    For recent notification/report job runs (reminders, digests, verification digest, compliance check, scheduled reports),
    enrich outcome_metrics with delivery_provider_accepted, delivery_delivered, delivery_bounced, delivery_unknown, delivery_failed.
    """
    db = database.get_db()
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    since_str = since.isoformat()
    updated = 0
    cursor = db.job_runs.find(
        {"job_name": {"$in": list(RECONCILIATION_JOBS.keys())}, "started_at": {"$gte": since_str}, "finished_at": {"$ne": None}},
        {"_id": 1, "job_name": 1, "started_at": 1, "finished_at": 1, "outcome_metrics": 1},
    ).sort("finished_at", -1).limit(100)
    runs = await cursor.to_list(100)
    for run in runs:
        if await reconcile_delivery_for_run(db, run):
            updated += 1
    logger.info("Delivery reconciliation: %s run(s) updated", updated)
    tenant_summary: Dict[str, Any] = {}
    try:
        from services.tenant_delivery_reconciliation import reconcile_stale_tenant_delivery_proofs_from_message_logs

        tenant_summary = await reconcile_stale_tenant_delivery_proofs_from_message_logs(hours_back=max(hours_back, 96), limit=500)
    except Exception as e:
        logger.warning("tenant_delivery proof stale reconcile failed: %s", e)
        tenant_summary = {"error": str(e)}
    return {
        "message": f"Delivery reconciliation: {updated} run(s) updated",
        "count": updated,
        "runs_processed": len(runs),
        "tenant_delivery_reconcile": tenant_summary,
    }


async def get_message_logs_for_run(db, run: dict, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Return message_logs that fall within the run's time window and match the job's template_keys.
    Used for drill-down / export when inspecting a degraded or failed automation run.
    """
    job_name = run.get("job_name")
    templates = RECONCILIATION_JOBS.get(job_name)
    if not templates:
        return []

    started = _parse_iso(run.get("started_at"))
    finished = _parse_iso(run.get("finished_at"))
    if not started or not finished:
        return []

    if hasattr(finished, "timestamp"):
        window_end = finished + timedelta(hours=2)
    else:
        window_end = _parse_iso(finished)
        if window_end:
            window_end = window_end + timedelta(hours=2)
        else:
            window_end = finished

    match: Dict[str, Any] = {"template_key": {"$in": templates}}
    try:
        match["created_at"] = {"$gte": started, "$lte": window_end}
    except Exception:
        start_str = started.isoformat() if hasattr(started, "isoformat") else str(started)
        end_str = window_end.isoformat() if hasattr(window_end, "isoformat") else str(window_end)
        match["created_at"] = {"$gte": start_str, "$lte": end_str}

    cursor = db.message_logs.find(
        match,
        {"_id": 0, "message_id": 1, "template_key": 1, "channel": 1, "status": 1, "client_id": 1, "recipient": 1, "error_message": 1, "created_at": 1, "sent_at": 1, "delivered_at": 1, "bounced_at": 1},
    ).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    for it in items:
        for k in ("created_at", "sent_at", "delivered_at", "bounced_at"):
            if it.get(k) and hasattr(it[k], "isoformat"):
                it[k] = it[k].isoformat()
    return items
