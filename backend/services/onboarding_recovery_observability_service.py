"""Onboarding recovery audit trail, metrics, and completion detection (Phase 4)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database
from models import AuditAction, OnboardingStatus, PasswordStatus
from services.onboarding_recovery_service import (
    _is_paid_or_active,
    detect_stranded_onboarding,
)
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

COL_AUDIT = "onboarding_recovery_audit"
COL_METRICS = "onboarding_recovery_metrics"

EVENT_RECOVERY_EXECUTED = "recovery_executed"
EVENT_CONTINUATION_DELIVERED = "continuation_delivered"
EVENT_CONTINUATION_FAILED = "continuation_failed"
EVENT_CONTINUATION_CHECKOUT = "continuation_checkout_created"
EVENT_RECOVERY_OUTCOME_DETECTED = "recovery_outcome_detected"

METRIC_KEYS = frozenset(
    {
        "recovery_initiated",
        "continuation_delivered",
        "continuation_failed",
        "payment_checkout_regenerated",
        "activation_resent",
        "continuation_checkout_created",
        "recovery_outcome_paid",
        "recovery_outcome_activated",
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def derive_recovery_completion_status(
    client: Dict[str, Any],
    portal_user: Optional[Dict[str, Any]],
    *,
    billing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Observable recovery completion — not internal waiver success.
    """
    paid = _is_paid_or_active(client, billing)
    password_set = bool(portal_user and portal_user.get("password_status") == PasswordStatus.SET.value)
    onboarding = (client.get("onboarding_status") or "").upper()
    continuation_at = client.get("continuation_delivered_at")

    if password_set and onboarding == OnboardingStatus.PROVISIONED.value:
        status = "activation_complete"
        message = "Customer has set a password and can use the portal."
    elif paid and onboarding == OnboardingStatus.PROVISIONED.value:
        status = "payment_recovered_pending_activation"
        message = "Payment is active; portal activation may still be required."
    elif paid:
        status = "payment_recovered"
        message = "Subscription payment is active."
    elif continuation_at:
        status = "continuation_delivered_awaiting_action"
        message = "Continuation was delivered; awaiting customer payment or activation."
    elif client.get("last_recovery_at"):
        status = "recovery_in_progress"
        message = "Recovery was initiated; continuation outcome not yet confirmed."
    else:
        status = "no_governed_recovery"
        message = "No governed recovery execution recorded for this account."

    return {
        "status": status,
        "message": message,
        "paid_or_active": paid,
        "password_set": password_set,
        "continuation_delivered_at": continuation_at,
        "last_recovery_at": client.get("last_recovery_at"),
        "last_recovery_mode": client.get("last_recovery_mode"),
    }


async def _increment_metric(metric_key: str, *, client_id: Optional[str] = None) -> None:
    if metric_key not in METRIC_KEYS:
        return
    db = database.get_db()
    now = _now().isoformat()
    scopes = [("global", "global")]
    if client_id:
        scopes.append((client_id, client_id))
    for scope_key, scope_val in scopes:
        await db[COL_METRICS].update_one(
            {"scope": scope_key, "client_id": scope_val},
            {
                "$inc": {metric_key: 1, "event_count": 1},
                "$set": {"last_event_at": now, "last_metric": metric_key},
            },
            upsert=True,
        )


async def record_onboarding_recovery_event(
    *,
    event_type: str,
    client_id: str,
    mode: Optional[str] = None,
    classification: Optional[str] = None,
    actor_id: Optional[str] = None,
    continuation_delivered: Optional[bool] = None,
    email_sent: Optional[bool] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Append auditable recovery event and update counters."""
    db = database.get_db()
    event_id = str(uuid.uuid4())
    now = _now().isoformat()
    meta = dict(metadata or {})
    doc = {
        "event_id": event_id,
        "event_type": event_type,
        "client_id": client_id,
        "mode": mode,
        "classification": classification,
        "actor_id": actor_id,
        "continuation_delivered": continuation_delivered,
        "email_sent": email_sent,
        "created_at": now,
        "metadata": meta,
    }
    await db[COL_AUDIT].insert_one(doc)

    metric_map = {
        EVENT_RECOVERY_EXECUTED: "recovery_initiated",
        EVENT_CONTINUATION_DELIVERED: "continuation_delivered",
        EVENT_CONTINUATION_FAILED: "continuation_failed",
        EVENT_CONTINUATION_CHECKOUT: "continuation_checkout_created",
    }
    if event_type == EVENT_RECOVERY_EXECUTED and mode == "regenerate_payment":
        await _increment_metric("payment_checkout_regenerated", client_id=client_id)
    elif event_type == EVENT_RECOVERY_EXECUTED and mode == "resend_activation":
        await _increment_metric("activation_resent", client_id=client_id)
    elif event_type in metric_map:
        await _increment_metric(metric_map[event_type], client_id=client_id)

    if continuation_delivered is False and email_sent is False:
        await _increment_metric("continuation_failed", client_id=client_id)

    audit_action = AuditAction.ADMIN_ACTION
    if event_type == EVENT_RECOVERY_EXECUTED:
        audit_action = AuditAction.ONBOARDING_RECOVERY_EXECUTED
    elif event_type in (EVENT_CONTINUATION_DELIVERED, EVENT_CONTINUATION_CHECKOUT):
        audit_action = AuditAction.ONBOARDING_RECOVERY_CONTINUATION_RECORDED

    try:
        await create_audit_log(
            action=audit_action,
            actor_id=actor_id,
            client_id=client_id,
            resource_type="onboarding_recovery",
            resource_id=client_id,
            metadata={
                "event_type": event_type,
                "event_id": event_id,
                "mode": mode,
                "classification": classification,
                "continuation_delivered": continuation_delivered,
                "email_sent": email_sent,
                **meta,
            },
            reason_code="onboarding_recovery_observability",
        )
    except Exception as exc:
        logger.warning("onboarding recovery audit log failed client_id=%s: %s", client_id, exc)

    return event_id


async def reconcile_recovery_outcome(client_id: str) -> Optional[Dict[str, Any]]:
    """Detect paid/activated outcomes after recovery and record once per client outcome."""
    signals = await detect_stranded_onboarding(client_id)
    if not signals.get("found"):
        return None
    client = signals["client"]
    if not client.get("last_recovery_at") and not client.get("continuation_delivered_at"):
        return None

    completion = derive_recovery_completion_status(client, signals.get("portal_user"), billing=signals.get("billing"))
    status = completion["status"]
    if status not in ("payment_recovered", "payment_recovered_pending_activation", "activation_complete"):
        return None

    db = database.get_db()
    outcome_key = f"outcome:{status}"
    existing = await db[COL_AUDIT].find_one(
        {
            "client_id": client_id,
            "event_type": EVENT_RECOVERY_OUTCOME_DETECTED,
            "metadata.outcome_status": status,
        },
        {"_id": 0, "event_id": 1},
    )
    if existing:
        return None

    metric = "recovery_outcome_paid" if "payment" in status else "recovery_outcome_activated"
    await record_onboarding_recovery_event(
        event_type=EVENT_RECOVERY_OUTCOME_DETECTED,
        client_id=client_id,
        classification=client.get("last_recovery_classification"),
        metadata={"outcome_status": status, "outcome_key": outcome_key},
    )
    await _increment_metric(metric, client_id=client_id)
    return completion


async def list_client_recovery_events(client_id: str, *, limit: int = 25) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = (
        db[COL_AUDIT]
        .find({"client_id": client_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    rows = await cursor.to_list(length=limit)
    return rows


async def get_client_onboarding_recovery_observability(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return {"found": False, "client_id": client_id}

    portal_user = await db.portal_users.find_one(
        {"client_id": client_id},
        {"_id": 0, "password_status": 1},
    )
    await reconcile_recovery_outcome(client_id)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or client

    completion = derive_recovery_completion_status(client, portal_user)
    events = await list_client_recovery_events(client_id, limit=20)

    return {
        "found": True,
        "client_id": client_id,
        "completion": completion,
        "events": events,
        "delivery": {
            "continuation_delivered_at": client.get("continuation_delivered_at"),
            "last_recovery_at": client.get("last_recovery_at"),
            "last_recovery_mode": client.get("last_recovery_mode"),
            "last_recovery_classification": client.get("last_recovery_classification"),
            "recovery_attempt_count": client.get("recovery_attempt_count"),
            "last_recovery_checkout_id": client.get("last_recovery_checkout_id"),
        },
    }


async def get_fleet_onboarding_recovery_metrics(*, days: int = 30) -> Dict[str, Any]:
    """Aggregate fleet-level recovery counters for admin ops."""
    db = database.get_db()
    cutoff = _now() - timedelta(days=max(1, min(days, 365)))
    global_row = await db[COL_METRICS].find_one({"scope": "global"}, {"_id": 0}) or {}

    recent_events = (
        await db[COL_AUDIT]
        .find({"created_at": {"$gte": cutoff.isoformat()}}, {"_id": 0, "event_type": 1, "continuation_delivered": 1})
        .to_list(length=5000)
    )

    by_type: Dict[str, int] = {}
    delivered = 0
    failed = 0
    for ev in recent_events:
        et = ev.get("event_type") or "unknown"
        by_type[et] = by_type.get(et, 0) + 1
        if ev.get("continuation_delivered") is True:
            delivered += 1
        if ev.get("event_type") == EVENT_CONTINUATION_FAILED or ev.get("continuation_delivered") is False:
            failed += 1

    initiated = global_row.get("recovery_initiated") or by_type.get(EVENT_RECOVERY_EXECUTED, 0)
    continuation_delivered = global_row.get("continuation_delivered") or delivered
    payment_regenerated = global_row.get("payment_checkout_regenerated") or 0
    activation_resent = global_row.get("activation_resent") or 0
    outcome_paid = global_row.get("recovery_outcome_paid") or 0
    outcome_activated = global_row.get("recovery_outcome_activated") or 0

    def _rate(num: int, denom: int) -> Optional[float]:
        if not denom:
            return None
        return round(num / denom, 4)

    return {
        "period_days": days,
        "cutoff_at": cutoff.isoformat(),
        "counters": {
            "recovery_initiated": initiated,
            "continuation_delivered": continuation_delivered,
            "continuation_failed": global_row.get("continuation_failed") or failed,
            "payment_checkout_regenerated": payment_regenerated,
            "activation_resent": activation_resent,
            "recovery_outcome_paid": outcome_paid,
            "recovery_outcome_activated": outcome_activated,
        },
        "rates": {
            "continuation_delivery_rate": _rate(continuation_delivered, initiated),
            "payment_recovery_rate": _rate(outcome_paid, initiated),
            "activation_completion_rate": _rate(outcome_activated, initiated),
        },
        "recent_events_by_type": by_type,
        "recent_event_count": len(recent_events),
    }
