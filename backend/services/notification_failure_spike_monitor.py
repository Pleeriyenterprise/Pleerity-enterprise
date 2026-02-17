"""
Notification failure spike monitor: run every 5 minutes.
Count FAILED message_logs in last 15 minutes; if >= WARN/CRIT threshold, send OPS alert via orchestrator.
Respects NOTIFICATION_SPIKE_COOLDOWN_SECONDS between alerts.
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

LOOKBACK_MINUTES = 15
NOTIFICATION_FAIL_WARN_THRESHOLD = int(os.getenv("NOTIFICATION_FAIL_WARN_THRESHOLD", "10"))
NOTIFICATION_FAIL_CRIT_THRESHOLD = int(os.getenv("NOTIFICATION_FAIL_CRIT_THRESHOLD", "25"))
NOTIFICATION_SPIKE_COOLDOWN_SECONDS = int(os.getenv("NOTIFICATION_SPIKE_COOLDOWN_SECONDS", "3600"))
OPS_ALERT_EMAIL = (os.getenv("OPS_ALERT_EMAIL") or "").strip()
ADMIN_ALERT_EMAILS_RAW = (os.getenv("ADMIN_ALERT_EMAILS") or "").strip()


def _admin_recipients() -> List[str]:
    """Recipients for admin/ops alerts: ADMIN_ALERT_EMAILS if set, else OPS_ALERT_EMAIL."""
    if ADMIN_ALERT_EMAILS_RAW:
        return [e.strip() for e in ADMIN_ALERT_EMAILS_RAW.split(",") if e.strip()]
    if OPS_ALERT_EMAIL:
        return [OPS_ALERT_EMAIL]
    return []


async def run_notification_failure_spike_monitor() -> Dict[str, Any]:
    """
    Count FAILED message_logs in last 15 minutes. If >= CRIT or >= WARN threshold,
    send OPS_ALERT_NOTIFICATION_SPIKE to admin recipients (respecting cooldown) and audit.
    Returns dict with breached, severity, failed_count, top_templates, alert_sent.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=LOOKBACK_MINUTES)

    failed_count = await db.message_logs.count_documents({
        "status": "FAILED",
        "created_at": {"$gte": since},
    })

    severity = None
    if failed_count >= NOTIFICATION_FAIL_CRIT_THRESHOLD:
        severity = "CRIT"
    elif failed_count >= NOTIFICATION_FAIL_WARN_THRESHOLD:
        severity = "WARN"

    if not severity:
        return {"breached": False, "failed_count": failed_count, "alert_sent": False}

    # Cooldown: only send one alert per cooldown window
    cooldown_cursor = await db.notification_spike_cooldown.find_one({"_id": "spike_alert"})
    last_sent = cooldown_cursor.get("last_sent_at") if cooldown_cursor else None
    if isinstance(last_sent, str):
        try:
            last_sent = datetime.fromisoformat(last_sent.replace("Z", "+00:00"))
        except Exception:
            last_sent = None
    if last_sent and (now - last_sent).total_seconds() < NOTIFICATION_SPIKE_COOLDOWN_SECONDS:
        logger.info(
            f"Notification failure spike: {severity} ({failed_count} failures) but within cooldown"
        )
        return {
            "breached": True,
            "severity": severity,
            "failed_count": failed_count,
            "alert_sent": False,
            "cooldown": True,
        }

    # Top failed templates
    pipeline = [
        {"$match": {"status": "FAILED", "created_at": {"$gte": since}}},
        {"$group": {"_id": "$template_key", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_templates = []
    async for doc in db.message_logs.aggregate(pipeline):
        top_templates.append({"template_key": doc["_id"] or "unknown", "count": doc["count"]})

    # Top failure reasons (error_message snippet)
    pipeline_reasons = [
        {"$match": {"status": "FAILED", "created_at": {"$gte": since}, "error_message": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": {"$substr": ["$error_message", 0, 100]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    top_reasons = []
    async for doc in db.message_logs.aggregate(pipeline_reasons):
        top_reasons.append({"reason": doc["_id"], "count": doc["count"]})

    await create_audit_log(
        action=AuditAction.NOTIFICATION_FAILURE_SPIKE_DETECTED,
        client_id=None,
        metadata={
            "severity": severity,
            "failed_count": failed_count,
            "window_minutes": LOOKBACK_MINUTES,
            "top_templates": top_templates,
            "top_reasons": top_reasons,
        },
    )

    recipients = _admin_recipients()
    alert_sent = False
    if recipients:
        subject = f"[{severity}] Notification failure spike: {failed_count} failures in last {LOOKBACK_MINUTES} min"
        body_lines = [
            f"Severity: {severity}",
            f"Failed count (last {LOOKBACK_MINUTES} min): {failed_count}",
            "Top templates:",
        ]
        for t in top_templates:
            body_lines.append(f"  - {t['template_key']}: {t['count']}")
        body_lines.append("Top reasons:")
        for r in top_reasons:
            body_lines.append(f"  - {r['reason'][:80]}: {r['count']}")
        message = "\n".join(body_lines)

        from services.notification_orchestrator import notification_orchestrator
        for recipient in recipients:
            idempotency_key = f"OPS_ALERT_NOTIFICATION_SPIKE_{now.strftime('%Y%m%d%H%M')}_{severity}_{hash(recipient) % 10**8}"
            result = await notification_orchestrator.send(
                template_key="OPS_ALERT_NOTIFICATION_SPIKE",
                client_id=None,
                context={"recipient": recipient, "subject": subject, "message": message},
                idempotency_key=idempotency_key,
                event_type="notification_failure_spike",
            )
            if result.outcome in ("sent", "duplicate_ignored"):
                alert_sent = True

        if alert_sent:
            await db.notification_spike_cooldown.update_one(
                {"_id": "spike_alert"},
                {"$set": {"last_sent_at": now, "severity": severity, "failed_count": failed_count}},
                upsert=True,
            )
    else:
        logger.warning("OPS_ALERT_EMAIL / ADMIN_ALERT_EMAILS not set; notification spike alert not sent")

    return {
        "breached": True,
        "severity": severity,
        "failed_count": failed_count,
        "top_templates": top_templates,
        "top_reasons": top_reasons,
        "alert_sent": alert_sent,
    }
