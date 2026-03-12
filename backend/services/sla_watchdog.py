"""
SLA Watchdog: detects missed job runs, stale heartbeat, and delivery_unknown buildup; creates incidents.
Runs every 10 minutes. Uses job_schedule_registry for single source of truth on critical jobs.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple

from database import database
from services.incident_service import (
    create_incident,
    SOURCE_JOB_MONITOR,
    SOURCE_HEARTBEAT,
    SOURCE_DELIVERY_UNKNOWN,
    SEVERITY_P0,
    SEVERITY_P1,
    SEVERITY_P2,
)
from services.job_run_service import COLLECTION as JOB_RUNS_COLLECTION, STATUS_SUCCESS, STATUS_DEGRADED
from services.job_schedule_registry import CRITICAL_JOB_REGISTRY, HEARTBEAT_STALE_SECONDS
from services.delivery_reconciliation import RECONCILIATION_JOBS, DELIVERY_UNKNOWN_STALE_HOURS

logger = logging.getLogger(__name__)

# Build from registry: (job_id, expected_min, max_delay_minutes, severity, description)
def _build_sla_config() -> List[Tuple[str, int, int, str, str]]:
    config = []
    for e in CRITICAL_JOB_REGISTRY:
        if e.job_id == "scheduler_heartbeat":
            continue  # heartbeat checked separately
        severity = SEVERITY_P2
        if e.max_delay_minutes <= 10:
            severity = SEVERITY_P0
        elif e.max_delay_minutes <= 60:
            severity = SEVERITY_P1
        config.append((e.job_id, max(1, e.max_delay_minutes // 2), e.max_delay_minutes, severity, f"{e.job_id} must run at least every {e.max_delay_minutes} min"))
    return config

DEFAULT_SLA_CONFIG: List[Tuple[str, int, int, str, str]] = _build_sla_config()


def _get_admin_alert_emails() -> List[str]:
    raw = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    if not raw:
        return []
    return [e.strip() for e in raw.split(",") if e.strip()]


async def _send_incident_alert_email(incident_id: str, title: str, description: str, severity: str) -> bool:
    """Send admin alert email for new incident. Returns True if sent."""
    emails = _get_admin_alert_emails()
    if not emails:
        logger.warning("ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL not set; SLA incident alert not sent")
        return False
    try:
        from services.notification_orchestrator import notification_orchestrator
        # Use admin-manual template with subject/body; recipient from env
        body = f"Incident: {title}\n\n{description}\n\nSeverity: {severity}. View in admin Observability."
        subject = f"[{severity}] {title}"
        idempotency_key = f"SLA_INCIDENT_{incident_id}"
        for addr in emails[:3]:  # cap at 3 recipients
            result = await notification_orchestrator.send(
                template_key="ADMIN_MANUAL",
                client_id=None,
                context={"recipient": addr, "subject": subject, "body": body},
                idempotency_key=f"{idempotency_key}_{addr}",
                event_type="sla_incident_alert",
            )
            if result.outcome in ("sent", "duplicate_ignored"):
                return True
        return False
    except Exception as e:
        logger.exception("Failed to send SLA incident alert email: %s", e)
        return False


async def run_sla_watchdog() -> Dict[str, Any]:
    """
    Check: (1) scheduler heartbeat stale -> P1 incident; (2) delivery_unknown stale -> P2 incident;
    (3) each critical job last success; create incident if over max_delay. Dedupe by source/related_job_name.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    incidents_created = 0
    alerts_sent = 0

    # 1) Heartbeat stale -> P1 incident (scheduler may be down)
    heartbeat_doc = await db.scheduler_heartbeat.find_one({"_id": "default"}, {"_id": 0, "last_heartbeat_at": 1})
    last_hb = heartbeat_doc.get("last_heartbeat_at") if heartbeat_doc else None
    heartbeat_stale = False
    if last_hb:
        try:
            t = datetime.fromisoformat(str(last_hb).replace("Z", "+00:00")) if isinstance(last_hb, str) else last_hb
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            heartbeat_stale = (now - t).total_seconds() > HEARTBEAT_STALE_SECONDS
        except Exception:
            heartbeat_stale = True
    if heartbeat_stale:
        existing = await db.incidents.find_one({"status": "open", "source": SOURCE_HEARTBEAT}, {"_id": 1})
        if not existing:
            incident_id = await create_incident(
                severity=SEVERITY_P1,
                title="Scheduler heartbeat stale",
                description="The background scheduler has not updated the heartbeat within the expected window. Jobs may not be running. Check server process and logs.",
                source=SOURCE_HEARTBEAT,
                metadata={"last_heartbeat_at": str(last_hb)},
            )
            incidents_created += 1
            if await _send_incident_alert_email(incident_id, "Scheduler heartbeat stale", "Scheduler heartbeat is stale; jobs may not be running.", SEVERITY_P1):
                alerts_sent += 1

    # 2) Delivery unknown stale -> P2 incident
    stale_cutoff = now - timedelta(hours=DELIVERY_UNKNOWN_STALE_HOURS)
    stale_cutoff_str = stale_cutoff.isoformat()
    delivery_stale_count = await db.job_runs.count_documents({
        "job_name": {"$in": list(RECONCILIATION_JOBS.keys())},
        "finished_at": {"$lt": stale_cutoff_str},
        "outcome_metrics.delivery_unknown": {"$gt": 0},
    })
    if delivery_stale_count > 0:
        existing = await db.incidents.find_one({"status": "open", "source": SOURCE_DELIVERY_UNKNOWN}, {"_id": 1})
        if not existing:
            incident_id = await create_incident(
                severity=SEVERITY_P2,
                title="Delivery unknown unresolved",
                description=f"{delivery_stale_count} run(s) still have delivery_unknown beyond {DELIVERY_UNKNOWN_STALE_HOURS}h. Check provider webhooks and Message logs.",
                source=SOURCE_DELIVERY_UNKNOWN,
                metadata={"stale_run_count": delivery_stale_count, "stale_hours": DELIVERY_UNKNOWN_STALE_HOURS},
            )
            incidents_created += 1
            if await _send_incident_alert_email(incident_id, "Delivery unknown unresolved", f"{delivery_stale_count} runs have delivery_unknown unresolved. Check webhooks.", SEVERITY_P2):
                alerts_sent += 1

    # 3) Per-job SLA
    for job_name, _expected_min, max_delay_minutes, severity, description in DEFAULT_SLA_CONFIG:
        # Consider both success and degraded as "job ran" so we don't incident when only degraded
        last_success = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": job_name, "status": {"$in": [STATUS_SUCCESS, STATUS_DEGRADED]}},
            {"_id": 0, "finished_at": 1, "status": 1},
            sort=[("finished_at", -1)],
        )
        if not last_success or not last_success.get("finished_at"):
            # Never completed (success or degraded) - create incident after first delay window
            cutoff = now - timedelta(minutes=max_delay_minutes)
            # Only create if we have no open incident for this job
            existing = await db.incidents.find_one(
                {"status": "open", "related_job_name": job_name, "source": SOURCE_JOB_MONITOR},
                {"_id": 1},
            )
            if not existing:
                incident_id = await create_incident(
                    severity=severity,
                    title=f"Job {job_name} has not succeeded",
                    description=description + " No successful run found.",
                    source=SOURCE_JOB_MONITOR,
                    related_job_name=job_name,
                    metadata={"max_delay_minutes": max_delay_minutes},
                )
                incidents_created += 1
                if await _send_incident_alert_email(incident_id, f"Job {job_name} has not succeeded", description, severity):
                    alerts_sent += 1
            continue

        finished_str = last_success["finished_at"]
        try:
            if isinstance(finished_str, str):
                finished_at = datetime.fromisoformat(finished_str.replace("Z", "+00:00"))
            else:
                finished_at = finished_str
            if finished_at.tzinfo is None:
                finished_at = finished_at.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        delay_minutes = (now - finished_at).total_seconds() / 60
        if delay_minutes <= max_delay_minutes:
            # Within SLA window: if last run was degraded, create incident so admin sees repeated degraded runs
            if last_success.get("status") == STATUS_DEGRADED:
                existing_degraded = await db.incidents.find_one(
                    {"status": "open", "related_job_name": job_name, "source": SOURCE_JOB_MONITOR, "metadata.degraded_run": True},
                    {"_id": 1},
                )
                if not existing_degraded:
                    incident_id = await create_incident(
                        severity=SEVERITY_P2,
                        title=f"Job {job_name} last run was degraded",
                        description=f"Job completed but some outputs failed or were skipped. {description} Last run: {finished_str}. Check Automation Centre outcome_metrics.",
                        source=SOURCE_JOB_MONITOR,
                        related_job_name=job_name,
                        metadata={"last_finished_at": finished_str, "degraded_run": True},
                    )
                    incidents_created += 1
                    if await _send_incident_alert_email(incident_id, f"Job {job_name} last run was degraded", f"Job completed with degraded outcome. Last run: {finished_str}. Check outcome_metrics in Automation Centre.", SEVERITY_P2):
                        alerts_sent += 1
            continue

        existing = await db.incidents.find_one(
            {"status": "open", "related_job_name": job_name, "source": SOURCE_JOB_MONITOR},
            {"_id": 1},
        )
        if existing:
            continue

        incident_id = await create_incident(
            severity=severity,
            title=f"Job {job_name} missed SLA",
            description=description + f" Last success: {finished_str}. Delay: {delay_minutes:.0f} min.",
            source=SOURCE_JOB_MONITOR,
            related_job_name=job_name,
            metadata={"last_finished_at": finished_str, "delay_minutes": delay_minutes, "max_delay_minutes": max_delay_minutes},
        )
        incidents_created += 1
        if await _send_incident_alert_email(incident_id, f"Job {job_name} missed SLA", description, severity):
            alerts_sent += 1

    return {"message": f"SLA watchdog: {incidents_created} incident(s) created, {alerts_sent} alert(s) sent", "incidents_created": incidents_created, "alerts_sent": alerts_sent}
