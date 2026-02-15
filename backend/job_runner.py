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


async def run_expiry_rollover_recalc():
    """Daily job: recalc compliance score for properties whose requirements' due_date
    crossed expiry/expiring_soon thresholds (e.g. expired today or entered 30-day window).
    Writes history snapshot + AuditLog per property (EXPIRY_ROLLOVER).
    """
    try:
        from database import database
        from datetime import datetime, timezone, timedelta
        from services.compliance_scoring_service import recalculate_and_persist, REASON_EXPIRY_ROLLOVER

        db = database.get_db()
        now = datetime.now(timezone.utc)
        window_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        window_end = (now + timedelta(days=31)).replace(hour=23, minute=59, second=59, microsecond=999000)
        window_start_iso = window_start.isoformat()
        window_end_iso = window_end.isoformat()

        cursor = db.requirements.find(
            {"due_date": {"$gte": window_start_iso, "$lte": window_end_iso}},
            {"property_id": 1}
        )
        property_ids = set()
        async for doc in cursor:
            property_ids.add(doc["property_id"])

        actor = {"id": "system", "role": "SYSTEM"}
        count = 0
        for property_id in property_ids:
            try:
                await recalculate_and_persist(property_id, REASON_EXPIRY_ROLLOVER, actor, {"job": "expiry_rollover"})
                count += 1
            except Exception as e:
                logger.warning(f"Expiry rollover recalc failed for property {property_id}: {e}")

        logger.info(f"Expiry rollover recalc completed: {count} properties updated")
        return {"message": f"Expiry rollover: {count} properties updated", "count": count}
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


# Map scheduler job id -> run function (for admin manual run)
JOB_RUNNERS = {
    "daily_reminders": run_daily_reminders,
    "pending_verification_digest": run_pending_verification_digest,
    "monthly_digest": run_monthly_digests,
    "compliance_check_morning": run_compliance_status_check,
    "compliance_check_evening": run_compliance_status_check,
    "scheduled_reports": run_scheduled_reports,
    "compliance_score_snapshots": run_compliance_score_snapshots,
    "expiry_rollover_recalc": run_expiry_rollover_recalc,
    "order_delivery_processing": run_order_delivery_processing,
    "sla_monitoring": run_sla_monitoring,
    "stuck_order_detection": run_stuck_order_detection,
    "queued_order_processing": run_queued_order_processing,
    "abandoned_intake_detection": run_abandoned_intake_detection,
    "lead_followup_processing": run_lead_followup_processing,
    "lead_sla_check": run_lead_sla_check,
}
