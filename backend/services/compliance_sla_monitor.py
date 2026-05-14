"""
Compliance recalc SLA monitor: detect stuck PENDING/RUNNING, repeated failures, property pending too long.
Dedupe alerts by (property_id, alert_type) with cooldown; persist to compliance_sla_alerts; audit + optional email.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

# Env config with safe defaults
SLA_PENDING_SECONDS = int(os.getenv("COMPLIANCE_RECALC_SLA_PENDING_SECONDS", "120"))
SLA_RUNNING_SECONDS = int(os.getenv("COMPLIANCE_RECALC_SLA_RUNNING_SECONDS", "300"))
SLA_MAX_FAILURES_WARN = int(os.getenv("COMPLIANCE_RECALC_SLA_MAX_FAILURES_WARN", "3"))
SLA_MAX_FAILURES_CRIT = int(os.getenv("COMPLIANCE_RECALC_SLA_MAX_FAILURES_CRIT", "5"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("COMPLIANCE_RECALC_ALERT_COOLDOWN_SECONDS", "3600"))
OPS_ALERT_EMAIL = os.getenv("OPS_ALERT_EMAIL", "").strip()

# Fallback when env resolves to a non-positive or non-int value for email idempotency chunking only.
DEFAULT_COMPLIANCE_RECALC_ALERT_IDEMPOTENCY_COOLDOWN_SECONDS = 3600

# Alert types and severity
ALERT_PENDING_STUCK = "PENDING_STUCK"
ALERT_RUNNING_STUCK = "RUNNING_STUCK"
ALERT_FAILING_REPEATEDLY = "FAILING_REPEATEDLY"
ALERT_DEAD_JOB = "DEAD_JOB"
ALERT_PROPERTY_PENDING_TOO_LONG = "PROPERTY_PENDING_TOO_LONG"
# Grouped email only (not persisted as its own alert_type row)
ALERT_QUEUE_PROPERTY_COMPOSITE = "QUEUE_PROPERTY_COMPOSITE"
SEVERITY_WARN = "WARN"
SEVERITY_CRIT = "CRIT"

# Same-property queue + property-flag SLA: one email per monitor tick when both fire.
GROUPABLE_QUEUE_PROPERTY_ALERT_TYPES = frozenset({ALERT_PENDING_STUCK, ALERT_PROPERTY_PENDING_TOO_LONG})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cooldown_seconds_for_email_idempotency() -> int:
    """
    Cooldown used only for COMPLIANCE_SLA_ALERT idempotency chunking.
    Must be a positive int before dividing into now.timestamp(); otherwise DB dedupe and email keys could diverge.
    """
    cd = ALERT_COOLDOWN_SECONDS
    if type(cd) is not int or cd <= 0:
        logger.warning(
            "Invalid COMPLIANCE_RECALC_ALERT_COOLDOWN_SECONDS for email idempotency (%r); "
            "using fallback %s seconds",
            cd,
            DEFAULT_COMPLIANCE_RECALC_ALERT_IDEMPOTENCY_COOLDOWN_SECONDS,
        )
        return DEFAULT_COMPLIANCE_RECALC_ALERT_IDEMPOTENCY_COOLDOWN_SECONDS
    return cd


def compliance_sla_alert_email_idempotency_key(
    property_id: str, alert_type: str, severity: str, now: datetime
) -> str:
    """
    Deterministic idempotency for COMPLIANCE_SLA_ALERT sends: scoped to property + alert + severity
    and aligned to the same cooldown window used for DB dedupe (avoids cross-property hash collisions).
    """
    cooldown = _cooldown_seconds_for_email_idempotency()
    chunk = int(now.timestamp() // cooldown)
    return f"COMPLIANCE_SLA_ALERT_{property_id}_{alert_type}_{severity}_{chunk}"


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # Use datetime submodule so tests can patch module-level `datetime` for `now()` without breaking parsing.
        import datetime as dt_mod

        return dt_mod.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


async def _send_alert_email(
    alert_type: str,
    severity: str,
    property_id: str,
    client_id: str,
    details: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    idempotency_alert_type: Optional[str] = None,
) -> bool:
    """Send operator-structured COMPLIANCE_SLA_ALERT to OPS_ALERT_EMAIL. Returns True if sent."""
    if not OPS_ALERT_EMAIL:
        logger.warning("OPS_ALERT_EMAIL not set; compliance SLA alert not sent by email")
        return False
    try:
        from services.notification_orchestrator import notification_orchestrator
        from services.operational_alert_presentation import enrich_compliance_sla_alert_email_context
        from datetime import datetime, timezone

        now_dt = now or datetime.now(timezone.utc)
        idem_type = idempotency_alert_type or alert_type
        idempotency_key = compliance_sla_alert_email_idempotency_key(
            property_id, idem_type, severity, now_dt
        )
        ctx = enrich_compliance_sla_alert_email_context(
            recipient=OPS_ALERT_EMAIL,
            alert_type=alert_type,
            severity=severity,
            property_id=property_id,
            client_id=client_id,
            details=details,
        )
        result = await notification_orchestrator.send(
            template_key="COMPLIANCE_SLA_ALERT",
            client_id=None,
            context=ctx,
            idempotency_key=idempotency_key,
            event_type="compliance_sla_alert",
        )
        return result.outcome in ("sent", "duplicate_ignored")
    except Exception as e:
        logger.exception("Failed to send compliance SLA alert email: %s", e)
        return False


async def _upsert_alert_and_maybe_send(
    db,
    property_id: str,
    client_id: str,
    alert_type: str,
    severity: str,
    details: Dict[str, Any],
    now: datetime,
    *,
    groupable_email_buffer: Optional[List[Dict[str, Any]]] = None,
) -> None:
    cooldown_boundary = now - timedelta(seconds=ALERT_COOLDOWN_SECONDS)
    existing = await db.compliance_sla_alerts.find_one(
        {"property_id": property_id, "alert_type": alert_type}
    )
    last_sent_dt = _parse_iso(existing.get("last_sent_at")) if existing else None
    if existing and existing.get("active") and last_sent_dt and last_sent_dt > cooldown_boundary:
        # Within cooldown: only update last_detected_at and count
        await db.compliance_sla_alerts.update_one(
            {"property_id": property_id, "alert_type": alert_type},
            {"$set": {"last_detected_at": now.isoformat(), "details": details}, "$inc": {"count": 1}},
        )
        return
    # New or outside cooldown: upsert active alert, set last_sent_at, send email, write audit
    doc = {
        "property_id": property_id,
        "client_id": client_id,
        "alert_type": alert_type,
        "severity": severity,
        "last_sent_at": now.isoformat(),
        "last_detected_at": now.isoformat(),
        "count": (existing.get("count", 0) + 1) if existing else 1,
        "active": True,
        "details": details,
    }
    await db.compliance_sla_alerts.update_one(
        {"property_id": property_id, "alert_type": alert_type},
        {"$set": doc},
        upsert=True,
    )
    await create_audit_log(
        action=AuditAction.COMPLIANCE_RECALC_SLA_BREACH,
        client_id=client_id,
        resource_type="property",
        resource_id=property_id,
        metadata={
            "property_id": property_id,
            "client_id": client_id,
            "alert_type": alert_type,
            "severity": severity,
            **details,
        },
    )
    will_send_email = True
    if groupable_email_buffer is not None and alert_type in GROUPABLE_QUEUE_PROPERTY_ALERT_TYPES:
        groupable_email_buffer.append(
            {
                "property_id": property_id,
                "client_id": client_id,
                "alert_type": alert_type,
                "severity": severity,
                "details": details,
            }
        )
        will_send_email = False
    if will_send_email:
        await _send_alert_email(alert_type, severity, property_id, client_id, details, now=now)


async def _flush_groupable_queue_property_emails(
    buffer: List[Dict[str, Any]],
    *,
    now: datetime,
) -> None:
    """One email per property when both queue PENDING and property-pending SLA fire the same tick."""
    if not buffer:
        return
    by_prop: Dict[str, List[Dict[str, Any]]] = {}
    for item in buffer:
        pid = str(item.get("property_id") or "")
        by_prop.setdefault(pid, []).append(item)
    for property_id, items in by_prop.items():
        types = {str(i.get("alert_type") or "") for i in items}
        if len(items) > 1 and types <= set(GROUPABLE_QUEUE_PROPERTY_ALERT_TYPES):
            max_sev = SEVERITY_CRIT if any(i.get("severity") == SEVERITY_CRIT for i in items) else SEVERITY_WARN
            client_id = str((items[0].get("client_id") or ""))
            details = {
                "grouped_signals": [
                    {
                        "alert_type": i.get("alert_type"),
                        "severity": i.get("severity"),
                        "details": i.get("details") or {},
                    }
                    for i in sorted(items, key=lambda x: str(x.get("alert_type")))
                ],
                "what_to_check_first": (
                    "Automation Control Centre queue for this property_id, then Admin → client property flags "
                    "(compliance_score_pending, last_calculated_at)."
                ),
                "likely_shared_cause": (
                    "Worker backlog, a wedged queue row, or pending flag not cleared after a completed recalculation."
                ),
                "when_to_escalate": (
                    "Escalate to platform engineering if the queue does not drain within 30 minutes after deploy "
                    "or if multiple tenants show the same signature."
                ),
            }
            await _send_alert_email(
                ALERT_QUEUE_PROPERTY_COMPOSITE,
                max_sev,
                property_id,
                client_id,
                details,
                now=now,
                idempotency_alert_type=ALERT_QUEUE_PROPERTY_COMPOSITE,
            )
        else:
            for i in items:
                await _send_alert_email(
                    str(i.get("alert_type")),
                    str(i.get("severity") or SEVERITY_WARN),
                    str(i.get("property_id") or ""),
                    str(i.get("client_id") or ""),
                    dict(i.get("details") or {}),
                    now=now,
                )


async def _resolve_alert(db, property_id: str, alert_type: str, client_id: str, now: datetime) -> None:
    """Mark alert active=false and write RESOLVED audit."""
    r = await db.compliance_sla_alerts.update_one(
        {"property_id": property_id, "alert_type": alert_type, "active": True},
        {"$set": {"active": False}},
    )
    if r.modified_count:
        await create_audit_log(
            action=AuditAction.COMPLIANCE_RECALC_SLA_RESOLVED,
            client_id=client_id,
            resource_type="property",
            resource_id=property_id,
            metadata={"property_id": property_id, "alert_type": alert_type},
        )


async def run_compliance_recalc_sla_monitor() -> Dict[str, Any]:
    """
    Scan queue and properties for SLA breaches; upsert alerts with cooldown; resolve when clear.
    Returns summary counts.
    """
    from services.compliance_recalc_queue import (
        STATUS_PENDING,
        STATUS_RUNNING,
        STATUS_FAILED,
        STATUS_DEAD,
        STATUS_DONE,
    )
    from services.compliance_recalc_running_reclaim import mongo_running_liveness_stale_filter

    db = database.get_db()
    now = datetime.now(timezone.utc)
    cutoff_pending = (now - timedelta(seconds=SLA_PENDING_SECONDS)).isoformat()
    cutoff_running = (now - timedelta(seconds=SLA_RUNNING_SECONDS)).isoformat()
    running_stale_filter = mongo_running_liveness_stale_filter(cutoff_running)

    stats = {"breaches": 0, "resolved": 0}
    groupable_email_buffer: List[Dict[str, Any]] = []

    # A) PENDING stuck: next_run_at or created_at <= cutoff_pending
    cursor = db.compliance_recalc_queue.find(
        {"status": STATUS_PENDING, "next_run_at": {"$lte": cutoff_pending}}
    )
    async for job in cursor:
        property_id = job.get("property_id")
        client_id = job.get("client_id", "")
        created = _parse_iso(job.get("created_at"))
        age_sec = (now - created).total_seconds() if created else 0
        details = {
            "job_id": str(job.get("_id")),
            "status": job.get("status"),
            "attempts": job.get("attempts", 0),
            "created_at": job.get("created_at"),
            "next_run_at": job.get("next_run_at"),
            "age_seconds": round(age_sec),
            "last_error": job.get("last_error"),
        }
        await _upsert_alert_and_maybe_send(
            db, property_id, client_id, ALERT_PENDING_STUCK, SEVERITY_WARN, details, now,
            groupable_email_buffer=groupable_email_buffer,
        )
        stats["breaches"] += 1

    # B) RUNNING stuck: liveness (heartbeat_at vs updated_at) older than cutoff_running
    cursor = db.compliance_recalc_queue.find(running_stale_filter)
    async for job in cursor:
        property_id = job.get("property_id")
        client_id = job.get("client_id", "")
        updated = _parse_iso(job.get("updated_at"))
        hb = _parse_iso(job.get("heartbeat_at"))
        liveness_candidates = [d for d in (updated, hb) if d is not None]
        liveness = max(liveness_candidates) if liveness_candidates else None
        age_sec = (now - liveness).total_seconds() if liveness else 0
        details = {
            "job_id": str(job.get("_id")),
            "status": job.get("status"),
            "attempts": job.get("attempts", 0),
            "updated_at": job.get("updated_at"),
            "heartbeat_at": job.get("heartbeat_at"),
            "age_seconds": round(age_sec),
            "last_error": job.get("last_error"),
        }
        await _upsert_alert_and_maybe_send(
            db, property_id, client_id, ALERT_RUNNING_STUCK, SEVERITY_CRIT, details, now,
            groupable_email_buffer=groupable_email_buffer,
        )
        stats["breaches"] += 1

    # C) FAILED with attempts >= WARN; CRIT when >= CRIT or DEAD
    cursor = db.compliance_recalc_queue.find(
        {"status": {"$in": [STATUS_FAILED, STATUS_DEAD]}}
    )
    async for job in cursor:
        property_id = job.get("property_id")
        client_id = job.get("client_id", "")
        attempts = job.get("attempts", 0)
        status = job.get("status")
        if status == STATUS_DEAD or attempts >= SLA_MAX_FAILURES_CRIT:
            alert_type = ALERT_DEAD_JOB if status == STATUS_DEAD else ALERT_FAILING_REPEATEDLY
            severity = SEVERITY_CRIT
        elif attempts >= SLA_MAX_FAILURES_WARN:
            alert_type = ALERT_FAILING_REPEATEDLY
            severity = SEVERITY_WARN
        else:
            continue
        details = {
            "job_id": str(job.get("_id")),
            "status": status,
            "attempts": attempts,
            "updated_at": job.get("updated_at"),
            "last_error": job.get("last_error"),
        }
        await _upsert_alert_and_maybe_send(
            db, property_id, client_id, alert_type, severity, details, now,
            groupable_email_buffer=groupable_email_buffer,
        )
        stats["breaches"] += 1

    # D) Property pending too long: compliance_score_pending=true and (no last_calculated or very old)
    cutoff_prop = (now - timedelta(seconds=SLA_PENDING_SECONDS)).isoformat()
    cursor = db.properties.find(
        {"compliance_score_pending": True},
        {"_id": 0, "property_id": 1, "client_id": 1, "compliance_last_calculated_at": 1},
    )
    async for prop in cursor:
        property_id = prop.get("property_id")
        client_id = prop.get("client_id", "")
        last_calc = prop.get("compliance_last_calculated_at")
        if last_calc and last_calc > cutoff_prop:
            continue
        # Pending and (never calculated or last calculated too long ago)
        details = {
            "compliance_score_pending": True,
            "compliance_last_calculated_at": last_calc,
            "sla_pending_seconds": SLA_PENDING_SECONDS,
        }
        await _upsert_alert_and_maybe_send(
            db, property_id, client_id, ALERT_PROPERTY_PENDING_TOO_LONG, SEVERITY_WARN, details, now,
            groupable_email_buffer=groupable_email_buffer,
        )
        stats["breaches"] += 1

    await _flush_groupable_queue_property_emails(groupable_email_buffer, now=now)

    # Resolutions: mark active=false where condition no longer holds
    # PENDING_STUCK: job no longer PENDING (DONE/FAILED/DEAD) or next_run_at fresh
    alerts_active = await db.compliance_sla_alerts.find({"active": True}).to_list(1000)
    for alert in alerts_active:
        property_id = alert.get("property_id")
        alert_type = alert.get("alert_type")
        client_id = alert.get("client_id", "")
        if alert_type == ALERT_PENDING_STUCK:
            job = await db.compliance_recalc_queue.find_one(
                {"property_id": property_id, "status": STATUS_PENDING, "next_run_at": {"$lte": cutoff_pending}}
            )
            if not job:
                await _resolve_alert(db, property_id, alert_type, client_id, now)
                stats["resolved"] += 1
        elif alert_type == ALERT_RUNNING_STUCK:
            job = await db.compliance_recalc_queue.find_one(
                {"property_id": property_id, **running_stale_filter}
            )
            if not job:
                await _resolve_alert(db, property_id, alert_type, client_id, now)
                stats["resolved"] += 1
        elif alert_type in (ALERT_FAILING_REPEATEDLY, ALERT_DEAD_JOB):
            # Resolve if no FAILED (attempts>=WARN) or DEAD job for this property
            job = await db.compliance_recalc_queue.find_one({
                "property_id": property_id,
                "$or": [
                    {"status": STATUS_DEAD},
                    {"status": STATUS_FAILED, "attempts": {"$gte": SLA_MAX_FAILURES_WARN}},
                ],
            })
            if not job:
                await _resolve_alert(db, property_id, alert_type, client_id, now)
                stats["resolved"] += 1
        elif alert_type == ALERT_PROPERTY_PENDING_TOO_LONG:
            prop = await db.properties.find_one(
                {"property_id": property_id},
                {"compliance_score_pending": 1, "compliance_last_calculated_at": 1},
            )
            if not prop or not prop.get("compliance_score_pending"):
                await _resolve_alert(db, property_id, alert_type, client_id, now)
                stats["resolved"] += 1
            elif prop.get("compliance_last_calculated_at") and prop.get("compliance_last_calculated_at") > cutoff_prop:
                await _resolve_alert(db, property_id, alert_type, client_id, now)
                stats["resolved"] += 1

    return {"message": "Compliance recalc SLA monitor run", "breaches": stats["breaches"], "resolved": stats["resolved"]}
