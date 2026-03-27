"""
Risk signal regeneration queue health: when DEAD jobs exist or FAILED backlog is high,
create a single open incident (deduped) and send OPS email. Recovery when queue is healthy again.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services.incident_service import (
    create_incident,
    SOURCE_RISK_REGEN_QUEUE,
    SEVERITY_P2,
)
from services.notification_failure_spike_monitor import _admin_recipients
from services.risk_signal_regen_queue import get_regen_queue_summary

logger = logging.getLogger(__name__)


async def run_risk_signal_regen_alert_monitor() -> Dict[str, Any]:
    """
    1) Resolve open risk_regen_queue incidents if attention_required is false.
    2) If attention_required and no open incident, create P2 incident + OPS email (ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL).
    """
    from services.incident_recovery import check_and_resolve_risk_regen_queue_incidents

    resolved = 0
    try:
        resolved = await check_and_resolve_risk_regen_queue_incidents()
    except Exception as e:
        logger.warning("risk regen alert monitor: recovery pass failed: %s", e)

    summary = await get_regen_queue_summary(
        int(os.getenv("RISK_REGEN_ALERT_SAMPLE_LIMIT", "25"))
    )
    attention = bool(summary.get("attention_required"))
    counts = summary.get("counts_by_status") or {}

    if not attention:
        return {
            "attention_required": False,
            "counts_by_status": counts,
            "incidents_created": 0,
            "incidents_resolved": resolved,
            "alert_sent": False,
        }

    db = database.get_db()
    existing = await db.incidents.find_one(
        {"status": "open", "source": SOURCE_RISK_REGEN_QUEUE},
        {"_id": 1},
    )
    if existing:
        return {
            "attention_required": True,
            "counts_by_status": counts,
            "incidents_created": 0,
            "already_open": True,
            "incidents_resolved": resolved,
            "alert_sent": False,
        }

    dead = summary.get("recent_dead") or []
    failed = summary.get("recent_failed") or []
    oldest = summary.get("oldest_pending_job") or {}
    lines = [
        "Risk signal regeneration queue reports attention_required.",
        f"Counts by status: {counts}",
        f"Oldest pending job: {oldest.get('property_id')} / client {oldest.get('client_id')} next_run_at={oldest.get('next_run_at')}",
    ]
    if dead:
        lines.append("Recent DEAD (sample):")
        for d in dead[:5]:
            lines.append(
                f"  - property={d.get('property_id')} attempts={d.get('attempts')} err={(d.get('last_error') or '')[:120]}"
            )
    if failed:
        lines.append("Recent FAILED (sample):")
        for f in failed[:5]:
            lines.append(
                f"  - property={f.get('property_id')} attempts={f.get('attempts')} next={f.get('next_run_at')}"
            )
    lines.append("See GET /api/admin/ops/risk-signal-regen-queue-summary and audit_logs RISK_SIGNAL_REGEN_FAILED.")
    description = "\n".join(lines)

    incident_id = await create_incident(
        severity=SEVERITY_P2,
        title="Risk signal regeneration queue needs attention",
        description=description,
        source=SOURCE_RISK_REGEN_QUEUE,
        metadata={
            "triggering_reason": "queue_health",
            "counts_by_status": counts,
            "sample_limit": summary.get("sample_limit"),
        },
    )

    await create_audit_log(
        action=AuditAction.RISK_REGEN_QUEUE_HEALTH_INCIDENT,
        client_id=None,
        resource_type="risk_signal_regen_queue",
        resource_id="attention",
        metadata={
            "incident_id": incident_id,
            "counts_by_status": counts,
        },
    )

    alert_sent = False
    recipients = _admin_recipients()
    if recipients:
        now = datetime.now(timezone.utc)
        subject = "[P2] Risk signal regeneration queue needs attention"
        try:
            from services.notification_orchestrator import notification_orchestrator

            for recipient in recipients:
                idempotency_key = f"OPS_RISK_REGEN_QUEUE_{incident_id}_{hash(recipient) % 10**8}"
                result = await notification_orchestrator.send(
                    template_key="OPS_ALERT_NOTIFICATION_SPIKE",
                    client_id=None,
                    context={
                        "recipient": recipient,
                        "subject": subject,
                        "message": description,
                    },
                    idempotency_key=idempotency_key,
                    event_type="risk_regen_queue_attention",
                )
                if result.outcome in ("sent", "duplicate_ignored"):
                    alert_sent = True
        except Exception as e:
            logger.exception("Risk regen queue OPS email failed: %s", e)
    else:
        logger.warning("ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL not set; risk regen queue alert email skipped")

    return {
        "attention_required": True,
        "counts_by_status": counts,
        "incidents_created": 1,
        "incident_id": incident_id,
        "incidents_resolved": resolved,
        "alert_sent": alert_sent,
    }
