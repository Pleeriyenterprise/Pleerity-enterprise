"""
Operational incident lifecycle: dedupe, suppression, recovery, flap protection, deploy awareness.

Additive layer on top of incident_service. Preserves existing status workflow (open/acknowledged/resolved)
and adds lifecycle_state (OPEN, DEGRADED, RECOVERED, RESOLVED) plus operational telemetry fields.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from database import database

from services.incident_service import (
    COLLECTION,
    STATUS_OPEN,
    STATUS_ACKNOWLEDGED,
    STATUS_RESOLVED,
    SEVERITY_P0,
    SEVERITY_P1,
    SEVERITY_P2,
    create_incident,
)

logger = logging.getLogger(__name__)

LIFECYCLE_OPEN = "OPEN"
LIFECYCLE_DEGRADED = "DEGRADED"
LIFECYCLE_RECOVERED = "RECOVERED"
LIFECYCLE_RESOLVED = "RESOLVED"

OPEN_LIFECYCLE_STATES = (LIFECYCLE_OPEN, LIFECYCLE_DEGRADED)
ACTIVE_INCIDENT_STATUSES = (STATUS_OPEN, STATUS_ACKNOWLEDGED)

DEFAULT_DEGRADED_AFTER_SECONDS = int(os.getenv("INCIDENT_DEGRADED_AFTER_SECONDS", "600"))
DEFAULT_RECOVERY_STABLE_SECONDS = int(os.getenv("INCIDENT_RECOVERY_STABLE_SECONDS", "300"))
DEFAULT_AUTO_RESOLVE_AFTER_RECOVERY_SECONDS = int(
    os.getenv("INCIDENT_AUTO_RESOLVE_AFTER_RECOVERY_SECONDS", "900")
)
DEFAULT_FLAP_WINDOW_SECONDS = int(os.getenv("INCIDENT_FLAP_WINDOW_SECONDS", "1800"))
DEFAULT_FLAP_TRANSITION_THRESHOLD = int(os.getenv("INCIDENT_FLAP_TRANSITION_THRESHOLD", "4"))

SUPPRESSION_SECONDS_BY_SEVERITY = {
    SEVERITY_P0: int(os.getenv("INCIDENT_SUPPRESSION_P0_SECONDS", "900")),
    SEVERITY_P1: int(os.getenv("INCIDENT_SUPPRESSION_P1_SECONDS", "1800")),
    SEVERITY_P2: int(os.getenv("INCIDENT_SUPPRESSION_P2_SECONDS", "3600")),
    "P3": int(os.getenv("INCIDENT_SUPPRESSION_P3_SECONDS", "7200")),
}

SEVERITY_RANK = {SEVERITY_P0: 0, SEVERITY_P1: 1, SEVERITY_P2: 2, "P3": 3}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            t = value
        else:
            t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t
    except Exception:
        return None


def compute_incident_fingerprint(
    source: str,
    *,
    related_job_name: Optional[str] = None,
    triggering_reason: Optional[str] = None,
    signature: Optional[str] = None,
) -> str:
    """Stable fingerprint for deduplicating repeated detections into one incident."""
    parts = [
        source or "",
        related_job_name or "",
        triggering_reason or "",
        signature or "",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def suppression_window_seconds(severity: str) -> int:
    return SUPPRESSION_SECONDS_BY_SEVERITY.get(severity, SUPPRESSION_SECONDS_BY_SEVERITY[SEVERITY_P2])


def is_deployment_suppression_active(now: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
    """
    Returns (active, note). Uses PLATFORM_DEPLOY_SUPPRESSION_UNTIL (ISO) when set by ops/deploy hook.
    Does not disable monitoring — only informs suppression of low-priority transient delay alerts.
    """
    until_raw = (os.getenv("PLATFORM_DEPLOY_SUPPRESSION_UNTIL") or "").strip()
    if not until_raw:
        return False, None
    now = now or _now()
    until = _parse_iso(until_raw)
    if until and now < until:
        return True, (
            "Delay may be related to active deployment or worker restart "
            f"(suppression active until {until.isoformat()})."
        )
    return False, None


def _severity_escalated(previous: str, new: str) -> bool:
    prev_rank = SEVERITY_RANK.get(previous, 99)
    new_rank = SEVERITY_RANK.get(new, 99)
    return new_rank < prev_rank


def _append_lifecycle_history(
    history: Optional[List[Dict[str, Any]]],
    from_state: str,
    to_state: str,
    *,
    reason: str,
    at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    out = list(history or [])
    out.append(
        {
            "from": from_state,
            "to": to_state,
            "at": (at or _now()).isoformat(),
            "reason": reason,
        }
    )
    return out[-50:]


def _open_incident_query(
    source: str,
    *,
    related_job_name: Optional[str] = None,
    fingerprint: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Find open/ack incident for dedupe (fingerprint first, then legacy source/job match)."""
    base = {"status": {"$in": list(ACTIVE_INCIDENT_STATUSES)}}
    if fingerprint:
        q = {**base, "incident_fingerprint": fingerprint}
        return q
    q = {**base, "source": source}
    if related_job_name:
        q["related_job_name"] = related_job_name
    if extra_metadata and extra_metadata.get("degraded_run") is True:
        q["metadata.degraded_run"] = True
    elif extra_metadata and extra_metadata.get("degraded_run") is False:
        q["metadata.degraded_run"] = {"$ne": True}
    return q


@dataclass
class DetectionOutcome:
    incident_id: str
    created: bool
    should_send_open_alert: bool
    lifecycle_state: str
    repeat_count: int
    suppressed_reason: Optional[str] = None
    escalation_level_changed: bool = False
    deployment_related_possible: bool = False


async def find_open_incident(
    source: str,
    *,
    related_job_name: Optional[str] = None,
    fingerprint: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    fp = fingerprint or compute_incident_fingerprint(
        source,
        related_job_name=related_job_name,
        triggering_reason=(metadata or {}).get("triggering_reason"),
    )
    doc = await db[COLLECTION].find_one(_open_incident_query(source, related_job_name=related_job_name, fingerprint=fp))
    if doc:
        doc["id"] = str(doc.pop("_id"))
        return doc
    # Legacy fallback (pre-fingerprint incidents)
    legacy = await db[COLLECTION].find_one(
        _open_incident_query(source, related_job_name=related_job_name, extra_metadata=metadata)
    )
    if legacy:
        legacy["id"] = str(legacy.pop("_id"))
        return legacy
    return None


async def record_operational_detection(
    severity: str,
    title: str,
    description: str,
    source: str,
    *,
    related_job_name: Optional[str] = None,
    related_job_run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    presentation_severity: Optional[str] = None,
) -> DetectionOutcome:
    """
    Upsert operational incident: one row per fingerprint while active.
    Returns whether an OPEN alert email should be sent (new incident or severity escalation).
    """
    db = database.get_db()
    now = _now()
    meta = dict(metadata or {})
    triggering_reason = meta.get("triggering_reason") or "detected"
    fingerprint = compute_incident_fingerprint(
        source,
        related_job_name=related_job_name,
        triggering_reason=triggering_reason,
        signature=meta.get("failure_signature"),
    )
    deploy_active, deploy_note = is_deployment_suppression_active(now)
    if deploy_active:
        meta["deployment_related_possible"] = True
        if deploy_note:
            meta["deployment_note"] = deploy_note

    existing = await find_open_incident(
        source,
        related_job_name=related_job_name,
        fingerprint=fingerprint,
        metadata=meta,
    )

    if existing:
        outcome = await _record_repeat(
            db,
            existing,
            now=now,
            severity=severity,
            metadata=meta,
            snapshot=meta,
        )
        return outcome

    # New incident
    first_detected = now.isoformat()
    lifecycle_state = LIFECYCLE_OPEN
    suppression_sec = suppression_window_seconds(severity)
    doc_meta = {
        **meta,
        "triggering_reason": triggering_reason,
        "presentation_severity": presentation_severity,
        "sla_watchdog_condition_ticks": 0,
    }
    incident_id = await create_incident(
        severity=severity,
        title=title,
        description=description,
        source=source,
        related_job_run_id=related_job_run_id,
        related_job_name=related_job_name,
        metadata=doc_meta,
    )
    from bson import ObjectId

    oid = ObjectId(incident_id)
    await db[COLLECTION].update_one(
        {"_id": oid},
        {
            "$set": {
                "incident_fingerprint": fingerprint,
                "lifecycle_state": lifecycle_state,
                "first_detected_at": first_detected,
                "last_detected_at": first_detected,
                "repeat_count": 1,
                "last_repeat_at": first_detected,
                "consecutive_failures": 1,
                "recovery_count": 0,
                "suppression_window_seconds": suppression_sec,
                "flapping": False,
                "lifecycle_history": _append_lifecycle_history(
                    [],
                    "",
                    lifecycle_state,
                    reason="initial_detection",
                    at=now,
                ),
                "deployment_related_possible": deploy_active,
            }
        },
    )

    should_send = True
    suppressed_reason = None
    if deploy_active and severity == SEVERITY_P2 and triggering_reason in (
        "missed_sla",
        "job_never_succeeded",
    ):
        should_send = False
        suppressed_reason = "deployment_window_p2_transient"

    return DetectionOutcome(
        incident_id=incident_id,
        created=True,
        should_send_open_alert=should_send,
        lifecycle_state=lifecycle_state,
        repeat_count=1,
        suppressed_reason=suppressed_reason,
        deployment_related_possible=deploy_active,
    )


async def _record_repeat(
    db,
    existing: Dict[str, Any],
    *,
    now: datetime,
    severity: str,
    metadata: Dict[str, Any],
    snapshot: Optional[Dict[str, Any]] = None,
) -> DetectionOutcome:
    from bson import ObjectId

    incident_id = existing.get("id") or ""
    oid = ObjectId(incident_id)
    prev_severity = existing.get("severity", SEVERITY_P2)
    escalation = _severity_escalated(prev_severity, severity)
    repeat_count = int(existing.get("repeat_count") or 0) + 1
    consecutive = int(existing.get("consecutive_failures") or 0) + 1
    first_detected = existing.get("first_detected_at") or existing.get("created_at")
    first_dt = _parse_iso(first_detected) or now
    impact_seconds = int((now - first_dt).total_seconds())

    degraded_after = DEFAULT_DEGRADED_AFTER_SECONDS
    prev_lifecycle = existing.get("lifecycle_state") or LIFECYCLE_OPEN
    lifecycle_state = prev_lifecycle
    degraded_transition = False
    if impact_seconds >= degraded_after and prev_lifecycle == LIFECYCLE_OPEN:
        lifecycle_state = LIFECYCLE_DEGRADED
        degraded_transition = True

    suppression_sec = suppression_window_seconds(severity)
    last_alert_at = existing.get("last_alert_email_at")
    should_send = False
    suppressed_reason = "repeat_within_suppression_window"

    meta_existing = existing.get("metadata") or {}
    trig = (metadata.get("triggering_reason") or meta_existing.get("triggering_reason") or "").strip()

    if escalation:
        should_send = True
        suppressed_reason = None
    elif degraded_transition:
        # One worsening notification when OPEN → DEGRADED; no hourly re-email for unchanged condition.
        should_send = True
        suppressed_reason = None
    elif not last_alert_at:
        # Initial alert never recorded (deploy-window suppression, muted recipients, send failure): retry —
        # but preserve deploy-only suppression for eligible P2 transients while window is active.
        deploy_now, _ = is_deployment_suppression_active(now)
        if deploy_now and severity == SEVERITY_P2 and trig in ("missed_sla", "job_never_succeeded"):
            should_send = False
            suppressed_reason = "deployment_window_p2_transient"
        else:
            should_send = True
            suppressed_reason = None
    # Persistent repeats with last_alert_email_at set: in-app incident updates only (no periodic re-email).

    # Flap detection
    flap_window = DEFAULT_FLAP_WINDOW_SECONDS
    transitions = list(existing.get("health_transitions") or [])
    transitions.append({"at": now.isoformat(), "state": "unhealthy"})
    cutoff = now - timedelta(seconds=flap_window)
    recent = [t for t in transitions if _parse_iso(t.get("at")) and _parse_iso(t.get("at")) >= cutoff]
    flapping = len(recent) >= DEFAULT_FLAP_TRANSITION_THRESHOLD

    set_doc: Dict[str, Any] = {
        "updated_at": now.isoformat(),
        "last_detected_at": now.isoformat(),
        "last_repeat_at": now.isoformat(),
        "repeat_count": repeat_count,
        "consecutive_failures": consecutive,
        "total_impact_duration_seconds": impact_seconds,
        "lifecycle_state": lifecycle_state,
        "suppression_window_seconds": suppression_sec,
        "flapping": flapping,
        "health_transitions": recent[-20:],
    }
    if escalation:
        set_doc["severity"] = severity
    if snapshot:
        for k, v in snapshot.items():
            set_doc[f"metadata.{k}"] = v

    inc_update: Dict[str, Any] = {"$set": set_doc, "$inc": {"metadata.sla_watchdog_condition_ticks": 1}}
    if lifecycle_state != prev_lifecycle:
        history = _append_lifecycle_history(
            existing.get("lifecycle_history"),
            prev_lifecycle,
            lifecycle_state,
            reason="persistent_condition",
            at=now,
        )
        set_doc["lifecycle_history"] = history

    await db[COLLECTION].update_one({"_id": oid, "status": {"$in": list(ACTIVE_INCIDENT_STATUSES)}}, inc_update)

    return DetectionOutcome(
        incident_id=incident_id,
        created=False,
        should_send_open_alert=should_send,
        lifecycle_state=lifecycle_state,
        repeat_count=repeat_count,
        suppressed_reason=None if should_send else suppressed_reason,
        escalation_level_changed=escalation,
        deployment_related_possible=bool(existing.get("deployment_related_possible")),
    )


async def mark_open_alert_sent(incident_id: str) -> None:
    db = database.get_db()
    from bson import ObjectId

    now = _now().isoformat()
    await db[COLLECTION].update_one(
        {"_id": ObjectId(incident_id)},
        {"$set": {"last_alert_email_at": now, "updated_at": now}},
    )


async def record_healthy_observation(incident_id: str) -> None:
    """Track healthy observations for recovery stability window."""
    db = database.get_db()
    from bson import ObjectId

    now = _now()
    doc = await db[COLLECTION].find_one(
        {"_id": ObjectId(incident_id)},
        {"lifecycle_state": 1, "first_healthy_at": 1, "health_transitions": 1},
    )
    if not doc:
        return
    transitions = list(doc.get("health_transitions") or [])
    transitions.append({"at": now.isoformat(), "state": "healthy"})
    set_doc = {
        "updated_at": now.isoformat(),
        "health_transitions": transitions[-20:],
    }
    if not doc.get("first_healthy_at"):
        set_doc["first_healthy_at"] = now.isoformat()
    await db[COLLECTION].update_one({"_id": ObjectId(incident_id)}, {"$set": set_doc})


async def try_transition_to_recovered(
    incident_id: str,
    *,
    recovery_note: str,
    queue_health: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, bool]:
    """
    If healthy stability window met, set lifecycle RECOVERED.
    Returns (transitioned, should_send_recovery_email).
    """
    db = database.get_db()
    from bson import ObjectId

    now = _now()
    doc = await db[COLLECTION].find_one({"_id": ObjectId(incident_id)})
    if not doc or doc.get("status") == STATUS_RESOLVED:
        return False, False
    if doc.get("lifecycle_state") == LIFECYCLE_RESOLVED:
        return False, False

    first_healthy = _parse_iso(doc.get("first_healthy_at"))
    if not first_healthy:
        return False, False
    stable_seconds = (now - first_healthy).total_seconds()
    if stable_seconds < DEFAULT_RECOVERY_STABLE_SECONDS:
        return False, False

    if doc.get("lifecycle_state") == LIFECYCLE_RECOVERED and doc.get("recovery_email_sent_at"):
        return True, False

    recovered_at = now.isoformat()
    first_detected = _parse_iso(doc.get("first_detected_at") or doc.get("created_at"))
    impact_seconds = int((now - first_detected).total_seconds()) if first_detected else 0
    recovery_count = int(doc.get("recovery_count") or 0) + 1

    history = _append_lifecycle_history(
        doc.get("lifecycle_history"),
        doc.get("lifecycle_state") or LIFECYCLE_OPEN,
        LIFECYCLE_RECOVERED,
        reason=recovery_note,
        at=now,
    )

    set_doc = {
        "lifecycle_state": LIFECYCLE_RECOVERED,
        "recovered_at": recovered_at,
        "updated_at": recovered_at,
        "recovery_count": recovery_count,
        "total_impact_duration_seconds": impact_seconds,
        "lifecycle_history": history,
        "metadata.recovery_note": recovery_note,
    }
    if queue_health:
        set_doc["metadata.queue_health_at_recovery"] = queue_health

    should_send = not bool(doc.get("recovery_email_sent_at"))
    if should_send:
        set_doc["recovery_email_sent_at"] = recovered_at

    await db[COLLECTION].update_one(
        {"_id": ObjectId(incident_id), "status": {"$in": list(ACTIVE_INCIDENT_STATUSES)}},
        {"$set": set_doc},
    )
    return True, should_send


async def try_auto_resolve_after_recovery(incident_id: str, resolution_note: str) -> bool:
    """After RECOVERED + stability window, close incident (RESOLVED)."""
    db = database.get_db()
    from bson import ObjectId

    doc = await db[COLLECTION].find_one({"_id": ObjectId(incident_id)})
    if not doc or doc.get("lifecycle_state") != LIFECYCLE_RECOVERED:
        return False
    recovered_at = _parse_iso(doc.get("recovered_at"))
    if not recovered_at:
        return False
    now = _now()
    if (now - recovered_at).total_seconds() < DEFAULT_AUTO_RESOLVE_AFTER_RECOVERY_SECONDS:
        return False

    from services.incident_service import resolve_incident_auto_recovery

    ok = await resolve_incident_auto_recovery(incident_id, resolution_note)
    if ok:
        await db[COLLECTION].update_one(
            {"_id": ObjectId(incident_id)},
            {
                "$set": {
                    "lifecycle_state": LIFECYCLE_RESOLVED,
                    "resolved_at": now.isoformat(),
                    "lifecycle_history": _append_lifecycle_history(
                        doc.get("lifecycle_history"),
                        LIFECYCLE_RECOVERED,
                        LIFECYCLE_RESOLVED,
                        reason="auto_close_after_stable_recovery",
                        at=now,
                    ),
                }
            },
        )
    return ok


async def send_operational_recovery_email(incident_id: str) -> bool:
    """Send one recovery notification per incident lifecycle. Returns True if sent."""
    from services.incident_service import get_incident

    incident = await get_incident(incident_id)
    if not incident:
        return False
    emails = [
        e.strip()
        for e in (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").split(",")
        if e.strip()
    ]
    if not emails:
        logger.warning("Recovery email skipped: ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL not set")
        return False
    try:
        from services.notification_orchestrator import notification_orchestrator
        from services.operational_alert_presentation import build_operational_recovery_email_context

        ctx = build_operational_recovery_email_context(incident)
        ts = _now().strftime("%Y-%m-%d %H:%M:%S UTC")
        ctx["timestamp"] = ts
        for addr in emails[:3]:
            ctx["recipient"] = addr
            result = await notification_orchestrator.send(
                template_key="INTERNAL_ALERT",
                client_id=None,
                context=dict(ctx),
                idempotency_key=f"SLA_RECOVERY_{incident_id}_{addr}",
                event_type="sla_incident_recovery",
            )
            if result.outcome in ("sent", "duplicate_ignored"):
                return True
        return False
    except Exception as e:
        logger.exception("Failed to send recovery email incident_id=%s: %s", incident_id, e)
        return False


async def process_incident_recovery_lifecycle(
    incident_id: str,
    recovery_note: str,
    *,
    queue_health: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Record healthy observation, transition to RECOVERED when stable, send recovery email once,
    auto-resolve after post-recovery window.
    """
    await record_healthy_observation(incident_id)
    _transitioned, should_send = await try_transition_to_recovered(
        incident_id,
        recovery_note=recovery_note,
        queue_health=queue_health,
    )
    recovery_email_sent = False
    if should_send:
        recovery_email_sent = await send_operational_recovery_email(incident_id)
    auto_resolved = await try_auto_resolve_after_recovery(
        incident_id,
        f"{recovery_note} Auto-closed after stable recovery window.",
    )
    return {
        "recovery_email_sent": recovery_email_sent,
        "auto_resolved": auto_resolved,
    }


async def touch_persistent_incident(
    incident_oid,
    *,
    snapshot: Optional[Dict[str, Any]] = None,
    tick_field: str = "metadata.sla_watchdog_condition_ticks",
) -> None:
    """Backward-compatible tick bump used by monitors."""
    db = database.get_db()
    from bson import ObjectId

    now = _now()
    oid = incident_oid if isinstance(incident_oid, ObjectId) else ObjectId(str(incident_oid))
    set_doc: Dict[str, Any] = {"updated_at": now.isoformat(), "last_detected_at": now.isoformat()}
    if snapshot:
        for k, v in snapshot.items():
            set_doc[f"metadata.{k}"] = v
    await db[COLLECTION].update_one(
        {"_id": oid, "status": STATUS_OPEN},
        {"$set": set_doc, "$inc": {tick_field: 1}},
    )
