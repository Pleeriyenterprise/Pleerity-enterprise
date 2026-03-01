"""
SLA Watchdog: detects missed job runs and creates incidents.
Runs every 10 minutes; for each critical job checks last successful run.
If last success is older than max_delay_minutes, creates an incident (deduped by job_name)
and sends admin alert email. Does not replace compliance_recalc_sla_monitor or
notification_failure_spike_monitor; runs in addition.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple

from database import database
from services.incident_service import create_incident, SOURCE_JOB_MONITOR, SEVERITY_P0, SEVERITY_P1
from services.job_run_service import COLLECTION as JOB_RUNS_COLLECTION, STATUS_SUCCESS

logger = logging.getLogger(__name__)

# job_name -> (expected_frequency_minutes, max_delay_minutes, severity, description)
DEFAULT_SLA_CONFIG: List[Tuple[str, int, int, str, str]] = [
    ("daily_reminders", 24 * 60, 26 * 60, SEVERITY_P1, "Daily reminders must run at least every 26h"),
    ("monthly_digest", 30 * 24 * 60, 36 * 60, SEVERITY_P2, "Monthly digest must run within 36h of due time"),
    ("compliance_score_snapshots", 24 * 60, 26 * 60, SEVERITY_P2, "Score snapshots must run at least every 26h"),
    ("expiry_rollover_recalc", 24 * 60, 26 * 60, SEVERITY_P1, "Expiry rollover recalc must run at least every 26h"),
    ("compliance_recalc_worker", 1, 5, SEVERITY_P0, "Compliance recalc worker must succeed at least every 5 min"),
]


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
    Check last success time for each configured job; create incident if over max_delay.
    Dedupe: do not create a new incident if one is already open for the same job_name.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    incidents_created = 0
    alerts_sent = 0

    for job_name, _expected_min, max_delay_minutes, severity, description in DEFAULT_SLA_CONFIG:
        last_success = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": job_name, "status": STATUS_SUCCESS},
            {"_id": 0, "finished_at": 1},
            sort=[("finished_at", -1)],
        )
        if not last_success or not last_success.get("finished_at"):
            # Never succeeded (e.g. new deployment) - create incident after first delay window
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
