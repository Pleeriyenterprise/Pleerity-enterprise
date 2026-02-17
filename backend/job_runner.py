"""
Shared job runner for scheduled background jobs.
Used by server (scheduler) and admin (manual run).
Each run_* returns a dict with "message" (and optionally "count") for admin toast.
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


async def run_daily_reminders():
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        count = await job_scheduler.send_daily_reminders()
        await job_scheduler.close()
        logger.info(f"Daily reminders job completed: {count} reminders sent")
        return {"message": f"Daily reminders sent: {count}", "count": count}
    except Exception as e:
        logger.error(f"Daily reminders job failed: {e}")
        raise


async def run_pending_verification_digest():
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        sent = await job_scheduler.send_pending_verification_digest()
        await job_scheduler.close()
        logger.info(f"Pending verification digest job completed: {sent} emails sent")
        return {"message": f"Pending verification digest sent: {sent} emails", "count": sent}
    except Exception as e:
        logger.error(f"Pending verification digest job failed: {e}")
        raise


async def run_monthly_digests():
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        count = await job_scheduler.send_monthly_digests()
        await job_scheduler.close()
        logger.info(f"Monthly digest job completed: {count} digests sent")
        return {"message": f"Monthly digests sent: {count}", "count": count}
    except Exception as e:
        logger.error(f"Monthly digest job failed: {e}")
        raise


async def run_compliance_status_check():
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        count = await job_scheduler.check_compliance_status_changes()
        await job_scheduler.close()
        logger.info(f"Compliance status check completed: {count} alerts sent")
        return {"message": f"Compliance alerts sent: {count}", "count": count}
    except Exception as e:
        logger.error(f"Compliance status check failed: {e}")
        raise


async def run_scheduled_reports():
    try:
        from services.jobs import run_scheduled_reports as process_reports
        count = await process_reports()
        logger.info(f"Scheduled reports job completed: {count} reports sent")
        return {"message": f"Scheduled reports sent: {count}", "count": count}
    except Exception as e:
        logger.error(f"Scheduled reports job failed: {e}")
        raise


async def run_compliance_score_snapshots():
    try:
        from services.compliance_trending import capture_all_client_snapshots
        result = await capture_all_client_snapshots()
        logger.info(f"Compliance score snapshots completed: {result['success_count']}/{result['total_clients']} clients")
        return {"message": f"Compliance score snapshots: {result['success_count']}/{result['total_clients']} clients"}
    except Exception as e:
        logger.error(f"Compliance score snapshots job failed: {e}")
        raise


# Backoff seconds: attempt 1 => +10s, 2 => +30s, 3 => +2m, 4 => +10m, >=5 => DEAD
COMPLIANCE_RECALC_BACKOFF = [10, 30, 120, 600]


async def run_compliance_recalc_worker():
    """
    Process compliance_recalc_queue: claim PENDING jobs, run recalculate_and_persist,
    optional drift audit, retry with backoff or mark DEAD.
    """
    try:
        from database import database
        from services.compliance_recalc_queue import (
            STATUS_PENDING,
            STATUS_RUNNING,
            STATUS_DONE,
            STATUS_FAILED,
            STATUS_DEAD,
        )
        from services.compliance_scoring_service import recalculate_and_persist
        from models import AuditAction
        from utils.audit import create_audit_log

        db = database.get_db()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        cursor = db.compliance_recalc_queue.find(
            {"status": STATUS_PENDING, "next_run_at": {"$lte": now_iso}}
        ).sort("next_run_at", 1).limit(10)
        jobs = await cursor.to_list(10)
        processed = 0
        for job in jobs:
            jid = job["_id"]
            property_id = job["property_id"]
            client_id = job.get("client_id")
            trigger_reason = job.get("trigger_reason", "")
            correlation_id = job.get("correlation_id", "")
            actor_type = job.get("actor_type", "SYSTEM")
            actor_id = job.get("actor_id")
            attempts = job.get("attempts", 0)
            # Atomic claim
            r = await db.compliance_recalc_queue.update_one(
                {"_id": jid, "status": STATUS_PENDING},
                {"$set": {"status": STATUS_RUNNING, "updated_at": now_iso}},
            )
            if r.modified_count == 0:
                continue
            actor = {"id": actor_id or "system", "role": actor_type}
            context = {"correlation_id": correlation_id, "trigger_reason": trigger_reason}
            old_prop = await db.properties.find_one(
                {"property_id": property_id},
                {"_id": 0, "compliance_score": 1, "compliance_version": 1},
            )
            old_score = old_prop.get("compliance_score") if old_prop else None
            try:
                await recalculate_and_persist(property_id, trigger_reason, actor, context)
                prop_after = await db.properties.find_one(
                    {"property_id": property_id},
                    {"_id": 0, "compliance_score": 1},
                )
                new_score = prop_after.get("compliance_score") if prop_after else None
                if old_score is not None and new_score is not None and old_score != new_score:
                    await create_audit_log(
                        action=AuditAction.COMPLIANCE_SCORE_DRIFT_DETECTED,
                        actor_id=actor_id,
                        client_id=client_id,
                        resource_type="property",
                        resource_id=property_id,
                        before_state={"compliance_score": old_score},
                        after_state={"compliance_score": new_score},
                        metadata={
                            "correlation_id": correlation_id,
                            "trigger_reason": trigger_reason,
                        },
                    )
                await db.compliance_recalc_queue.update_one(
                    {"_id": jid},
                    {"$set": {"status": STATUS_DONE, "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                processed += 1
            except Exception as e:
                next_attempts = attempts + 1
                if next_attempts >= 5:
                    new_status = STATUS_DEAD
                    next_run_at = now_iso
                else:
                    new_status = STATUS_FAILED
                    delta = COMPLIANCE_RECALC_BACKOFF[min(next_attempts - 1, len(COMPLIANCE_RECALC_BACKOFF) - 1)]
                    next_run_at = (now + timedelta(seconds=delta)).isoformat()
                err_str = str(e)
                await db.compliance_recalc_queue.update_one(
                    {"_id": jid},
                    {"$set": {
                        "status": new_status,
                        "attempts": next_attempts,
                        "next_run_at": next_run_at,
                        "last_error": err_str,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                await create_audit_log(
                    action=AuditAction.COMPLIANCE_RECALC_FAILED,
                    actor_id=actor_id,
                    client_id=client_id,
                    resource_type="property",
                    resource_id=property_id,
                    metadata={
                        "attempts": next_attempts,
                        "error": err_str,
                        "correlation_id": correlation_id,
                        "trigger_reason": trigger_reason,
                    },
                )
                logger.warning(f"Compliance recalc failed property_id={property_id} attempts={next_attempts} err={err_str}")
        return {"message": f"Compliance recalc worker: {processed} processed", "count": processed}
    except Exception as e:
        logger.error(f"Compliance recalc worker failed: {e}")
        raise


async def run_expiry_rollover_recalc():
    """Daily job: enqueue compliance recalc for properties whose requirements' due_date
    crossed expiry/expiring_soon thresholds. Worker will run recalc.
    """
    try:
        from database import database
        from datetime import timedelta
        from services.compliance_recalc_queue import (
            enqueue_compliance_recalc,
            TRIGGER_EXPIRY_JOB,
            ACTOR_SYSTEM,
        )

        db = database.get_db()
        now = datetime.now(timezone.utc)
        window_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        window_end = (now + timedelta(days=31)).replace(hour=23, minute=59, second=59, microsecond=999000)
        window_start_iso = window_start.isoformat()
        window_end_iso = window_end.isoformat()
        date_str = now.strftime("%Y-%m-%d")

        cursor = db.requirements.find(
            {"due_date": {"$gte": window_start_iso, "$lte": window_end_iso}},
            {"property_id": 1}
        )
        property_ids = set()
        async for doc in cursor:
            property_ids.add(doc["property_id"])

        count = 0
        for property_id in property_ids:
            prop = await db.properties.find_one({"property_id": property_id}, {"client_id": 1})
            if not prop:
                continue
            correlation_id = f"EXPIRY_JOB:{property_id}:{date_str}"
            enqueued = await enqueue_compliance_recalc(
                property_id=property_id,
                client_id=prop["client_id"],
                trigger_reason=TRIGGER_EXPIRY_JOB,
                actor_type=ACTOR_SYSTEM,
                actor_id=None,
                correlation_id=correlation_id,
            )
            if enqueued:
                count += 1

        logger.info(f"Expiry rollover enqueued: {count} properties")
        return {"message": f"Expiry rollover: {count} properties enqueued", "count": count}
    except Exception as e:
        logger.error(f"Expiry rollover job failed: {e}")
        raise


async def run_order_delivery_processing():
    try:
        from services.order_delivery_service import order_delivery_service
        result = await order_delivery_service.process_finalising_orders()
        if result.get("processed", 0) > 0:
            logger.info(
                f"Order delivery job: {result['processed']} processed, "
                f"{result['delivered']} delivered, {result['failed']} failed"
            )
            return {"message": f"Order delivery: {result['processed']} processed, {result['delivered']} delivered"}
        logger.debug("Order delivery job: No orders to process")
        return {"message": "Order delivery: no orders to process"}
    except Exception as e:
        logger.error(f"Order delivery job failed: {e}")
        raise


async def run_sla_monitoring():
    try:
        from services.workflow_automation_service import workflow_automation_service
        result = await workflow_automation_service.wf9_sla_check()
        results = result.get("results", {})
        checked = results.get("checked", 0)
        warnings = results.get("warnings_sent", 0)
        breaches = results.get("breaches_sent", 0)
        if warnings > 0 or breaches > 0:
            return {"message": f"SLA monitoring: {checked} checked, {warnings} warnings, {breaches} breaches"}
        return {"message": f"SLA monitoring completed: {checked} orders checked"}
    except Exception as e:
        logger.error(f"SLA monitoring job failed: {e}")
        raise


async def run_stuck_order_detection():
    try:
        from services.order_workflow import OrderStatus
        from database import database
        db = database.get_db()
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        stuck_orders = await db.orders.find({
            "status": OrderStatus.FINALISING.value,
            "updated_at": {"$lt": one_hour_ago},
            "$or": [
                {"document_versions": {"$size": 0}},
                {"version_locked": {"$ne": True}},
                {"approved_document_version": {"$exists": False}},
                {"approved_document_version": None}
            ]
        }, {"_id": 0, "order_id": 1}).to_list(100)
        if stuck_orders:
            logger.warning(f"STUCK ORDER ALERT: {len(stuck_orders)} orders")
            return {"message": f"Stuck order detection: {len(stuck_orders)} orders need attention"}
        return {"message": "Stuck order detection: no stuck orders found"}
    except Exception as e:
        logger.error(f"Stuck order detection job failed: {e}")
        raise


async def run_queued_order_processing():
    try:
        from services.workflow_automation_service import workflow_automation_service
        result = await workflow_automation_service.process_queued_orders(limit=5)
        results = result.get("results", {})
        processed = results.get("processed", 0)
        if processed > 0:
            return {"message": f"Queued order processing: {processed} processed"}
        return {"message": "Queued order processing: no orders to process"}
    except Exception as e:
        logger.error(f"Queue processing job failed: {e}")
        raise


async def run_abandoned_intake_detection():
    try:
        from services.lead_service import AbandonedIntakeService
        created = await AbandonedIntakeService.detect_abandoned_intakes(timeout_hours=1.0)
        n = len(created) if created else 0
        logger.info(f"Created {n} leads from abandoned intakes")
        return {"message": f"Abandoned intake detection: {n} leads created"}
    except Exception as e:
        logger.error(f"Abandoned intake detection failed: {e}")
        raise


async def run_lead_followup_processing():
    try:
        from services.lead_followup_service import LeadFollowUpService
        await LeadFollowUpService.process_followup_queue()
        return {"message": "Lead follow-up processing completed"}
    except Exception as e:
        logger.error(f"Lead follow-up processing failed: {e}")
        raise


async def run_lead_sla_check():
    try:
        from services.lead_followup_service import LeadSLAService
        breaches = await LeadSLAService.check_sla_breaches(sla_hours=24)
        n = breaches or 0
        if n:
            logger.warning(f"Detected {n} lead SLA breaches")
        return {"message": f"Lead SLA check: {n} breaches detected"}
    except Exception as e:
        logger.error(f"Lead SLA check failed: {e}")
        raise


async def run_compliance_recalc_sla_monitor():
    """Compliance recalc SLA: detect stuck PENDING/RUNNING, repeated failures, property pending too long; dedupe alerts, audit, optional email."""
    try:
        from services.compliance_sla_monitor import run_compliance_recalc_sla_monitor as _run
        result = await _run()
        logger.info(f"Compliance recalc SLA monitor: {result.get('breaches', 0)} breaches, {result.get('resolved', 0)} resolved")
        return result
    except Exception as e:
        logger.error(f"Compliance recalc SLA monitor failed: {e}")
        raise


async def run_notification_failure_spike_monitor():
    """Notification failure spike: count FAILED in last 15 min; if >= WARN/CRIT threshold, send OPS alert (cooldown applied)."""
    try:
        from services.notification_failure_spike_monitor import run_notification_failure_spike_monitor as _run
        result = await _run()
        if result.get("breached"):
            logger.info(
                f"Notification failure spike: {result.get('severity')} ({result.get('failed_count')} failures), alert_sent={result.get('alert_sent')}"
            )
        return result
    except Exception as e:
        logger.error(f"Notification failure spike monitor failed: {e}")
        raise


async def run_notification_retry_worker():
    """Process notification retry queue (outbox pattern). Picks items with next_run_at <= now and re-attempts send."""
    from database import database
    from datetime import datetime, timezone
    try:
        db = database.get_db()
        now = datetime.now(timezone.utc)
        cursor = db.notification_retry_queue.find(
            {"status": "PENDING", "next_run_at": {"$lte": now}},
        ).limit(50)
        items = await cursor.to_list(50)
        from services.notification_orchestrator import notification_orchestrator
        processed = 0
        for item in items:
            try:
                await notification_orchestrator.process_retry(item["message_id"])
                processed += 1
            except Exception as e:
                logger.warning(f"Notification retry for {item.get('message_id')} failed: {e}")
        return {"message": f"Processed {processed} notification retries", "count": processed}
    except Exception as e:
        logger.error(f"Notification retry worker failed: {e}")
        raise


# Map scheduler job id -> run function (for admin manual run)
JOB_RUNNERS = {
    "daily_reminders": run_daily_reminders,
    "pending_verification_digest": run_pending_verification_digest,
    "monthly_digest": run_monthly_digests,
    "compliance_check_morning": run_compliance_status_check,
    "compliance_check_evening": run_compliance_status_check,
    "scheduled_reports": run_scheduled_reports,
    "compliance_score_snapshots": run_compliance_score_snapshots,
    "compliance_recalc_worker": run_compliance_recalc_worker,
    "expiry_rollover_recalc": run_expiry_rollover_recalc,
    "order_delivery_processing": run_order_delivery_processing,
    "sla_monitoring": run_sla_monitoring,
    "stuck_order_detection": run_stuck_order_detection,
    "queued_order_processing": run_queued_order_processing,
    "abandoned_intake_detection": run_abandoned_intake_detection,
    "lead_followup_processing": run_lead_followup_processing,
    "lead_sla_check": run_lead_sla_check,
    "compliance_recalc_sla_monitor": run_compliance_recalc_sla_monitor,
    "notification_failure_spike_monitor": run_notification_failure_spike_monitor,
    "notification_retry_worker": run_notification_retry_worker,
}
