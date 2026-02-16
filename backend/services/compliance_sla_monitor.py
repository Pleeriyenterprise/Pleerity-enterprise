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

# Alert types and severity
ALERT_PENDING_STUCK = "PENDING_STUCK"
ALERT_RUNNING_STUCK = "RUNNING_STUCK"
ALERT_FAILING_REPEATEDLY = "FAILING_REPEATEDLY"
ALERT_DEAD_JOB = "DEAD_JOB"
ALERT_PROPERTY_PENDING_TOO_LONG = "PROPERTY_PENDING_TOO_LONG"
SEVERITY_WARN = "WARN"
SEVERITY_CRIT = "CRIT"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


async def _send_alert_email(alert_type: str, severity: str, property_id: str, body: str, subject: str) -> bool:
    """Send email to OPS_ALERT_EMAIL via Postmark if configured. Returns True if sent."""
    if not OPS_ALERT_EMAIL:
        logger.warning("OPS_ALERT_EMAIL not set; compliance SLA alert not sent by email")
        return False
    token = os.getenv("POSTMARK_SERVER_TOKEN")
    if not token:
        logger.warning("POSTMARK_SERVER_TOKEN not set; compliance SLA alert logged only")
        return False
    try:
        from postmarker.core import PostmarkClient
        client = PostmarkClient(server_token=token)
        client.emails.send(
            From=os.getenv("EMAIL_SENDER", "info@pleerityenterprise.co.uk"),
            To=OPS_ALERT_EMAIL,
            Subject=subject,
            HtmlBody=body,
            Tag="compliance-sla-alert",
        )
        return True
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
) -> None:
    cooldown_end = (now - timedelta(seconds=ALERT_COOLDOWN_SECONDS)).isoformat()
    existing = await db.compliance_sla_alerts.find_one(
        {"property_id": property_id, "alert_type": alert_type}
    )
    if existing and existing.get("active") and (existing.get("last_sent_at") or "") > cooldown_end:
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
    subject = f"[{severity}] Compliance recalc SLA: {alert_type} — {property_id}"
    try:
        body_text = str(details)
    except Exception:
        body_text = repr(details)
    body_html = f"<p>Compliance recalc SLA alert.</p><pre>{body_text}</pre>"
    await _send_alert_email(alert_type, severity, property_id, body_html, subject)


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
    db = database.get_db()
    now = datetime.now(timezone.utc)
    cutoff_pending = (now - timedelta(seconds=SLA_PENDING_SECONDS)).isoformat()
    cutoff_running = (now - timedelta(seconds=SLA_RUNNING_SECONDS)).isoformat()

    stats = {"breaches": 0, "resolved": 0}

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
            db, property_id, client_id, ALERT_PENDING_STUCK, SEVERITY_WARN, details, now
        )
        stats["breaches"] += 1

    # B) RUNNING stuck: updated_at <= cutoff_running
    cursor = db.compliance_recalc_queue.find(
        {"status": STATUS_RUNNING, "updated_at": {"$lte": cutoff_running}}
    )
    async for job in cursor:
        property_id = job.get("property_id")
        client_id = job.get("client_id", "")
        updated = _parse_iso(job.get("updated_at"))
        age_sec = (now - updated).total_seconds() if updated else 0
        details = {
            "job_id": str(job.get("_id")),
            "status": job.get("status"),
            "attempts": job.get("attempts", 0),
            "updated_at": job.get("updated_at"),
            "age_seconds": round(age_sec),
            "last_error": job.get("last_error"),
        }
        await _upsert_alert_and_maybe_send(
            db, property_id, client_id, ALERT_RUNNING_STUCK, SEVERITY_CRIT, details, now
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
        await _upsert_alert_and_maybe_send(db, property_id, client_id, alert_type, severity, details, now)
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
            db, property_id, client_id, ALERT_PROPERTY_PENDING_TOO_LONG, SEVERITY_WARN, details, now
        )
        stats["breaches"] += 1

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
                {"property_id": property_id, "status": STATUS_RUNNING, "updated_at": {"$lte": cutoff_running}}
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
