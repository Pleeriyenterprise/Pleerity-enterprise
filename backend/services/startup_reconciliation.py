"""
Startup reconciliation for critical scheduled jobs.
Runs once after scheduler start: for each configured critical job, if the last expected run
was missed but still within a recovery window, trigger exactly one catch-up run (run_type=startup_recovery).
If overdue beyond the window, create an incident. Prevents jobs from silently never running after
container restart or scheduler misfire.
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from database import database
from services.job_run_service import (
    COLLECTION as JOB_RUNS_COLLECTION,
    STATUS_SUCCESS,
    STATUS_DEGRADED,
    RUN_TYPE_STARTUP_RECOVERY,
)
from services.incident_service import create_incident, SOURCE_JOB_MONITOR, SEVERITY_P2
from services.job_schedule_registry import get_registry_by_id

logger = logging.getLogger(__name__)

# Jobs included in startup reconciliation (infrequent critical jobs; high-freq jobs like compliance_recalc_worker
# are not included so startup stays fast and their next run is seconds away).
STARTUP_RECOVERY_JOB_IDS: List[str] = [
    "sla_watchdog",
    "daily_reminders",
    "scheduled_reports",
    "monthly_digest",
    "compliance_check_morning",
    "compliance_check_evening",
]

# Interval between scheduled runs (minutes). Used to compute "last expected run" from next_run_time.
INTERVAL_MINUTES: Dict[str, int] = {
    "sla_watchdog": 10,
    "daily_reminders": 24 * 60,
    "scheduled_reports": 60,
    "monthly_digest": 30 * 24 * 60,  # ~1 month
    "compliance_check_morning": 24 * 60,
    "compliance_check_evening": 24 * 60,
}

# If a run was missed, we allow catch-up only within this many minutes. Beyond that, create incident.
# Configurable via STARTUP_RECOVERY_WINDOW_MINUTES (default 10).
RECOVERY_WINDOW_MINUTES = int(os.environ.get("STARTUP_RECOVERY_WINDOW_MINUTES", "10").strip() or "10")


def _get_scheduler_next_runs() -> Dict[str, datetime]:
    """Job id -> next_run_time (datetime, UTC). Returns {} if scheduler unavailable."""
    try:
        from server import scheduler
        jobs = scheduler.get_jobs()
        out = {}
        for j in jobs:
            jid = getattr(j, "id", None)
            next_run = getattr(j, "next_run_time", None)
            if jid and next_run:
                if getattr(next_run, "tzinfo", None) is None:
                    next_run = next_run.replace(tzinfo=timezone.utc)
                out[jid] = next_run
        return out
    except Exception:
        return {}


def _parse_iso(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        if isinstance(ts, datetime):
            t = ts
        else:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t
    except Exception:
        return None


async def run_startup_reconciliation() -> Dict[str, Any]:
    """
    Run once after scheduler.start(). For each job in STARTUP_RECOVERY_JOB_IDS:
    - not yet due: next run in future and no missed run => log "not yet due"
    - healthy: last success at or after last expected run => log "healthy"
    - recovered: missed run but within RECOVERY_WINDOW_MINUTES => trigger one catch-up (run_type=startup_recovery)
    - overdue: missed run beyond recovery window => create incident, log "overdue and incident created"

    Duplicate protection: each job is at most one catch-up or one incident per invocation; we do not
    trigger the same job twice in this run. Process runs this only once at startup.
    """
    db = database.get_db()
    if db is None:
        logger.warning("Startup reconciliation skipped: database not connected")
        return {"skipped": True, "reason": "db_not_connected"}

    now = datetime.now(timezone.utc)
    next_runs = _get_scheduler_next_runs()
    registry = get_registry_by_id()
    recovered: List[str] = []
    incidents_created: List[str] = []
    healthy: List[str] = []
    not_yet_due: List[str] = []
    skipped: List[str] = []

    for job_id in STARTUP_RECOVERY_JOB_IDS:
        if job_id not in next_runs:
            logger.info("Startup reconciliation: %s - job not in scheduler, skip", job_id)
            skipped.append(job_id)
            continue

        next_run = next_runs[job_id]
        interval_min = INTERVAL_MINUTES.get(job_id)
        if interval_min is None:
            logger.info("Startup reconciliation: %s - no interval configured, skip", job_id)
            skipped.append(job_id)
            continue

        last_expected = next_run - timedelta(minutes=interval_min)
        if now < last_expected:
            logger.info("Startup reconciliation: %s - not yet due (next run %s)", job_id, next_run.isoformat())
            not_yet_due.append(job_id)
            continue

        last_success = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": job_id, "status": {"$in": [STATUS_SUCCESS, STATUS_DEGRADED]}},
            {"_id": 0, "finished_at": 1},
            sort=[("finished_at", -1)],
        )
        last_success_at = _parse_iso(last_success.get("finished_at") if last_success else None)
        if last_success_at is not None and last_success_at >= last_expected:
            logger.info("Startup reconciliation: %s - healthy (last success %s)", job_id, last_success_at.isoformat())
            healthy.append(job_id)
            continue

        minutes_since_missed = (now - last_expected).total_seconds() / 60
        recovery_window = RECOVERY_WINDOW_MINUTES
        if minutes_since_missed <= recovery_window:
            try:
                from job_runner import run_instrumented
                await run_instrumented(job_id, RUN_TYPE_STARTUP_RECOVERY, triggered_by=None)
                logger.info(
                    "Startup reconciliation: %s - recovered on startup (triggered one catch-up run, run_type=startup_recovery)",
                    job_id,
                )
                recovered.append(job_id)
            except Exception as e:
                logger.exception("Startup reconciliation: %s - catch-up run failed: %s", job_id, e)
                existing = await db.incidents.find_one(
                    {"status": "open", "related_job_name": job_id, "source": SOURCE_JOB_MONITOR},
                    {"_id": 1},
                )
                if not existing:
                    await create_incident(
                        severity=SEVERITY_P2,
                        title=f"Job {job_id} startup recovery failed",
                        description=f"Startup reconciliation triggered a catch-up run but it failed: {e}",
                        source=SOURCE_JOB_MONITOR,
                        related_job_name=job_id,
                        metadata={"startup_recovery_failed": True},
                    )
                    incidents_created.append(job_id)
            continue

        existing = await db.incidents.find_one(
            {"status": "open", "related_job_name": job_id, "source": SOURCE_JOB_MONITOR},
            {"_id": 1},
        )
        if not existing:
            entry = registry.get(job_id)
            description = f"Job {job_id} did not run by expected time (startup reconciliation). Last expected run: {last_expected.isoformat()}. Overdue by {minutes_since_missed:.0f} min."
            if entry:
                description += f" Max delay from registry: {entry.max_delay_minutes} min."
            await create_incident(
                severity=SEVERITY_P2,
                title=f"Job {job_id} overdue at startup",
                description=description,
                source=SOURCE_JOB_MONITOR,
                related_job_name=job_id,
                metadata={"last_expected_run": last_expected.isoformat(), "overdue_minutes": minutes_since_missed},
            )
            incidents_created.append(job_id)
        logger.info(
            "Startup reconciliation: %s - overdue and incident %s",
            job_id,
            "created" if job_id in incidents_created else "already exists",
        )

    summary = {
        "recovered": recovered,
        "incidents_created": incidents_created,
        "healthy": healthy,
        "not_yet_due": not_yet_due,
        "skipped": skipped,
        "recovery_window_minutes": RECOVERY_WINDOW_MINUTES,
    }
    logger.info(
        "Startup reconciliation complete: recovered=%s incidents=%s healthy=%s not_yet_due=%s skipped=%s (window=%s min)",
        len(recovered), len(incidents_created), len(healthy), len(not_yet_due), len(skipped), RECOVERY_WINDOW_MINUTES,
    )
    return summary
