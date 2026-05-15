"""
SLA Watchdog: detects missed job runs, stale heartbeat, and delivery_unknown buildup; creates incidents.
Runs every 10 minutes. Uses job_schedule_registry for single source of truth on critical jobs.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from database import database
from services.incident_service import (
    SOURCE_JOB_MONITOR,
    SOURCE_HEARTBEAT,
    SOURCE_DELIVERY_UNKNOWN,
    SEVERITY_P0,
    SEVERITY_P1,
    SEVERITY_P2,
)
from services.incident_lifecycle_service import (
    mark_open_alert_sent,
    record_operational_detection,
)
from services.job_run_service import COLLECTION as JOB_RUNS_COLLECTION, STATUS_SUCCESS, STATUS_DEGRADED
from services.job_schedule_registry import CRITICAL_JOB_REGISTRY, HEARTBEAT_STALE_SECONDS
from services.delivery_reconciliation import RECONCILIATION_JOBS, DELIVERY_UNKNOWN_STALE_HOURS
from services.internal_alert_registry import (
    get_alert_config,
    SCHEDULER_HEARTBEAT_STALE,
    JOB_MISSED_SLA,
    JOB_DEGRADED,
    DELIVERY_UNKNOWN_STALE,
)

logger = logging.getLogger(__name__)


async def _detect_and_alert(
    severity: str,
    title: str,
    description: str,
    source: str,
    *,
    related_job_name: Optional[str] = None,
    related_job_run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, bool]:
    """
    Upsert incident via lifecycle service; send email only when dedupe/suppression allows.
    Returns (incident_created, alert_email_sent).
    """
    outcome = await record_operational_detection(
        severity,
        title,
        description,
        source,
        related_job_name=related_job_name,
        related_job_run_id=related_job_run_id,
        metadata=metadata,
    )
    alert_sent = False
    if outcome.should_send_open_alert:
        meta = metadata or {}
        if await _send_incident_alert_email(
            outcome.incident_id,
            title,
            description,
            severity,
            source=source,
            metadata=meta,
            related_job_name=related_job_name,
        ):
            await mark_open_alert_sent(outcome.incident_id)
            alert_sent = True
    return outcome.created, alert_sent


async def _touch_persistent_incident_ticks(
    db,
    incident_oid,
    now: datetime,
    *,
    snapshot: Optional[Dict[str, Any]] = None,
) -> None:
    """Backward-compatible tick helper (tests + legacy callers)."""
    from bson import ObjectId
    from services.incident_service import STATUS_OPEN

    oid = incident_oid if isinstance(incident_oid, ObjectId) else ObjectId(str(incident_oid))
    set_doc: Dict[str, Any] = {
        "updated_at": now.isoformat(),
        "last_detected_at": now.isoformat(),
    }
    if snapshot:
        for k, v in snapshot.items():
            set_doc[f"metadata.{k}"] = v
    await db.incidents.update_one(
        {"_id": oid, "status": STATUS_OPEN},
        {"$set": set_doc, "$inc": {"metadata.sla_watchdog_condition_ticks": 1}},
    )


def _alert_type_from_incident(source: str, title: str) -> str:
    if source == SOURCE_HEARTBEAT:
        return SCHEDULER_HEARTBEAT_STALE
    if source == SOURCE_DELIVERY_UNKNOWN:
        return DELIVERY_UNKNOWN_STALE
    if source == SOURCE_JOB_MONITOR:
        return JOB_DEGRADED if "degraded" in (title or "").lower() else JOB_MISSED_SLA
    return JOB_MISSED_SLA

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

# If next_run is within this many seconds, treat as "not yet due" (grace period)
GRACE_PERIOD_NEXT_RUN_FUTURE_SEC = 60


def _get_scheduler_next_runs() -> Dict[str, datetime]:
    """Return dict job_id -> next_run_time (datetime) from in-process scheduler, or {} if unavailable."""
    try:
        from server import scheduler
        jobs = scheduler.get_jobs()
        out = {}
        for j in jobs:
            jid = getattr(j, "id", None)
            next_run = getattr(j, "next_run_time", None)
            if jid and next_run:
                if next_run.tzinfo is None:
                    from datetime import timezone
                    next_run = next_run.replace(tzinfo=timezone.utc)
                out[jid] = next_run
        return out
    except Exception:
        return {}


def _get_admin_alert_emails() -> List[str]:
    raw = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    if not raw:
        return []
    return [e.strip() for e in raw.split(",") if e.strip()]


async def _send_incident_alert_email(
    incident_id: str,
    title: str,
    description: str,
    severity: str,
    *,
    source: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    related_job_name: Optional[str] = None,
) -> bool:
    """Send structured internal alert email for new incident. Returns True if sent."""
    emails = _get_admin_alert_emails()
    if not emails:
        logger.warning("ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL not set; SLA incident alert not sent")
        return False
    try:
        from services.notification_orchestrator import notification_orchestrator
        from services.operational_alert_presentation import build_internal_alert_email_context

        alert_type = _alert_type_from_incident(source, title)
        config = get_alert_config(alert_type) or {}
        meta = metadata or {}
        last_finished_at = meta.get("last_finished_at") or meta.get("last_heartbeat_at")
        is_degraded_alert = bool(meta.get("degraded_run"))
        last_success_at = meta.get("last_successful_at")
        expected_interval = None
        if meta.get("max_delay_minutes") is not None:
            expected_interval = f"every {int(meta['max_delay_minutes'])} min"
        component = config.get("component") or related_job_name or "Monitoring"
        suggested_action = config.get("suggested_action", "")

        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        context = build_internal_alert_email_context(
            incident_id=incident_id,
            stored_severity=severity,
            title=title,
            description=description,
            source=source or "",
            metadata=meta,
            related_job_name=related_job_name,
            related_job_run_id=None,
            last_finished_at=last_finished_at,
            last_successful_at=last_success_at,
            is_degraded_alert=is_degraded_alert,
            expected_interval=expected_interval,
            current_status=description,
            suggested_action=suggested_action or "View Observability and resolve the incident.",
            component=component,
            possible_impact=config.get("description", description),
            timestamp=ts,
        )
        idempotency_key = f"SLA_INCIDENT_{incident_id}"
        for addr in emails[:3]:
            context["recipient"] = addr
            result = await notification_orchestrator.send(
                template_key="INTERNAL_ALERT",
                client_id=None,
                context=dict(context),
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
    Recovery pass: resolve heartbeat/delivery_unknown incidents when condition is cleared.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    incidents_created = 0
    alerts_sent = 0
    recovered = 0

    # Recovery pass: resolve incidents whose condition is now cleared (heartbeat fresh, no delivery_unknown stale)
    try:
        from services.incident_recovery import (
            check_and_resolve_heartbeat_incidents,
            check_and_resolve_delivery_unknown_incidents,
            check_and_resolve_risk_regen_queue_incidents,
        )
        recovered += await check_and_resolve_heartbeat_incidents()
        recovered += await check_and_resolve_delivery_unknown_incidents()
        recovered += await check_and_resolve_risk_regen_queue_incidents()
        if recovered:
            logger.info("SLA watchdog recovery pass: resolved %s incident(s)", recovered)
    except Exception as e:
        logger.warning("SLA watchdog recovery pass failed: %s", e)

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
        existing = await db.incidents.find_one({"status": STATUS_OPEN, "source": SOURCE_HEARTBEAT}, {"_id": 1})
        if existing:
            await _touch_persistent_incident_ticks(
                db,
                existing["_id"],
                now,
                snapshot={
                    "last_heartbeat_at_seen": str(last_hb),
                    "last_watchdog_tick_reason": "heartbeat_stale",
                },
            )
        if not existing:
            incident_id = await create_incident(
                severity=SEVERITY_P1,
                title="Scheduler heartbeat stale",
                description="The background scheduler has not updated the heartbeat within the expected window. Jobs may not be running. Check server process and logs.",
                source=SOURCE_HEARTBEAT,
                metadata={"last_heartbeat_at": str(last_hb), "triggering_reason": "heartbeat_stale"},
            )
            incidents_created += 1
            if await _send_incident_alert_email(
                incident_id, "Scheduler heartbeat stale", "Scheduler heartbeat is stale; jobs may not be running.", SEVERITY_P1,
                source=SOURCE_HEARTBEAT, metadata={"last_heartbeat_at": str(last_hb)},
            ):
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
        created, sent = await _detect_and_alert(
            SEVERITY_P2,
            "Delivery unknown unresolved",
            f"{delivery_stale_count} run(s) still have delivery_unknown beyond {DELIVERY_UNKNOWN_STALE_HOURS}h. Check provider webhooks and Message logs.",
            SOURCE_DELIVERY_UNKNOWN,
            metadata={
                "stale_run_count": delivery_stale_count,
                "stale_hours": DELIVERY_UNKNOWN_STALE_HOURS,
                "triggering_reason": "delivery_unknown_stale",
            },
        )
        if created:
            incidents_created += 1
        if sent:
            alerts_sent += 1

    # 3) Per-job SLA (grace period: do not create incident if next run is still in the future)
    next_runs = _get_scheduler_next_runs()
    for job_name, _expected_min, max_delay_minutes, severity, description in DEFAULT_SLA_CONFIG:
        # Consider both success and degraded as "job ran" so we don't incident when only degraded
        last_success = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": job_name, "status": {"$in": [STATUS_SUCCESS, STATUS_DEGRADED]}},
            {"_id": 0, "finished_at": 1, "status": 1},
            sort=[("finished_at", -1)],
        )
        if not last_success or not last_success.get("finished_at"):
            # Never completed - apply grace period: if next scheduled run is in the future, skip incident
            next_run = next_runs.get(job_name)
            if next_run and (next_run - now).total_seconds() > GRACE_PERIOD_NEXT_RUN_FUTURE_SEC:
                continue  # Not yet due since startup; no incident
            created, sent = await _detect_and_alert(
                severity,
                f"Job {job_name} has not succeeded",
                description + " No successful run found. Job is overdue.",
                SOURCE_JOB_MONITOR,
                related_job_name=job_name,
                metadata={"max_delay_minutes": max_delay_minutes, "triggering_reason": "job_never_succeeded"},
            )
            if created:
                incidents_created += 1
            if sent:
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
                last_pure_success = await db[JOB_RUNS_COLLECTION].find_one(
                    {"job_name": job_name, "status": STATUS_SUCCESS},
                    {"_id": 0, "finished_at": 1},
                    sort=[("finished_at", -1)],
                )
                last_success_at = last_pure_success.get("finished_at") if last_pure_success else None
                created, sent = await _detect_and_alert(
                    SEVERITY_P2,
                    f"Job {job_name} last run was degraded",
                    f"Job completed but some outputs failed or were skipped. {description} Last run: {finished_str}. Check Automation Centre outcome_metrics.",
                    SOURCE_JOB_MONITOR,
                    related_job_name=job_name,
                    metadata={
                        "last_finished_at": finished_str,
                        "last_successful_at": last_success_at,
                        "degraded_run": True,
                        "triggering_reason": "degraded_run",
                    },
                )
                if created:
                    incidents_created += 1
                if sent:
                    alerts_sent += 1
            continue

        created, sent = await _detect_and_alert(
            severity,
            f"Job {job_name} missed SLA",
            description + f" Last success: {finished_str}. Delay: {delay_minutes:.0f} min.",
            SOURCE_JOB_MONITOR,
            related_job_name=job_name,
            metadata={
                "last_finished_at": finished_str,
                "delay_minutes": delay_minutes,
                "max_delay_minutes": max_delay_minutes,
                "triggering_reason": "missed_sla",
            },
        )
        if created:
            incidents_created += 1
        if sent:
            alerts_sent += 1

    return {
        "message": f"SLA watchdog: {incidents_created} incident(s) created, {alerts_sent} alert(s) sent, {recovered} recovered",
        "incidents_created": incidents_created,
        "alerts_sent": alerts_sent,
        "incidents_recovered": recovered,
        "outcome_metrics": {
            "checks_run": 1,
            "incidents_created": incidents_created,
            "alerts_sent": alerts_sent,
            "recovered": recovered,
            "attempted_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "outcome_kind": "SLA_CHECK_COMPLETED",
        },
    }
