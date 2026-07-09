"""
Account Lifecycle Event Authority (ILP-9).

Single publication point for authoritative lifecycle platform events.
No service may invent ad-hoc lifecycle event payloads.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Tuple

from services.account_lifecycle_runtime_contract import CONTRACT_VERSION

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "account_lifecycle_event_v1"
POLICY_VERSION = "account_lifecycle_event_v1"
EVENTS_COLLECTION = "account_lifecycle_events"

LifecycleEventHandler = Callable[[Mapping[str, Any]], Awaitable[None]]


class LifecycleEventCategory(str, Enum):
    LIFECYCLE = "lifecycle"
    RUNTIME = "runtime"
    SESSION = "session"
    BACKGROUND = "background"
    COMMUNICATION = "communication"
    REACTIVATION = "reactivation"
    RECOVERY = "recovery"
    AUDIT = "audit"


class LifecycleEventType(str, Enum):
    ACCOUNT_ACTIVATED = "AccountActivated"
    TRIAL_STARTED = "TrialStarted"
    TRIAL_EXPIRED = "TrialExpired"
    GRACE_PERIOD_STARTED = "GracePeriodStarted"
    PAYMENT_RECOVERED = "PaymentRecovered"
    CANCELLATION_SCHEDULED = "CancellationScheduled"
    CANCELLATION_CANCELLED = "CancellationCancelled"
    SUBSCRIPTION_EXPIRED = "SubscriptionExpired"
    SUBSCRIPTION_REACTIVATED = "SubscriptionReactivated"
    ACCOUNT_SUSPENDED = "AccountSuspended"
    ACCOUNT_ARCHIVED = "AccountArchived"
    ACCOUNT_DELETED = "AccountDeleted"
    PORTAL_MODE_CHANGED = "PortalModeChanged"
    RUNTIME_CONTRACT_CHANGED = "RuntimeContractChanged"
    LIFECYCLE_STATE_CHANGED = "LifecycleStateChanged"
    CAPABILITIES_CHANGED = "CapabilitiesChanged"
    SESSION_RUNTIME_CHANGED = "SessionRuntimeChanged"
    BACKGROUND_POLICY_CHANGED = "BackgroundPolicyChanged"
    COMMUNICATION_SUPPRESSED = "CommunicationSuppressed"
    COMMUNICATION_SENT = "CommunicationSent"
    REACTIVATION_STARTED = "ReactivationStarted"
    REACTIVATION_COMPLETED = "ReactivationCompleted"
    REACTIVATION_FAILED = "ReactivationFailed"
    RECOVERY_JOURNEY_STARTED = "RecoveryJourneyStarted"
    RECOVERY_JOURNEY_COMPLETED = "RecoveryJourneyCompleted"
    RECOVERY_JOURNEY_ABANDONED = "RecoveryJourneyAbandoned"


# Transition (previous_state, new_state) → canonical event (when unambiguous)
_STATE_TRANSITION_EVENT: Dict[Tuple[str, str], LifecycleEventType] = {
    ("UNKNOWN", "ACTIVE"): LifecycleEventType.ACCOUNT_ACTIVATED,
    ("PAYMENT_PENDING", "ACTIVE"): LifecycleEventType.ACCOUNT_ACTIVATED,
    ("TRIAL", "ACTIVE"): LifecycleEventType.SUBSCRIPTION_REACTIVATED,
    ("TRIAL_EXPIRED", "PAYMENT_REQUIRED"): LifecycleEventType.TRIAL_EXPIRED,
    ("GRACE_PERIOD", "ACTIVE"): LifecycleEventType.PAYMENT_RECOVERED,
    ("ACTIVE", "GRACE_PERIOD"): LifecycleEventType.GRACE_PERIOD_STARTED,
    ("ACTIVE", "CANCELLATION_SCHEDULED"): LifecycleEventType.CANCELLATION_SCHEDULED,
    ("CANCELLATION_SCHEDULED", "ACTIVE"): LifecycleEventType.CANCELLATION_CANCELLED,
    ("ACTIVE", "CANCELLED_IMMEDIATE"): LifecycleEventType.SUBSCRIPTION_EXPIRED,
    ("CANCELLATION_SCHEDULED", "CANCELLED_IMMEDIATE"): LifecycleEventType.SUBSCRIPTION_EXPIRED,
    ("ACTIVE", "SUBSCRIPTION_EXPIRED"): LifecycleEventType.SUBSCRIPTION_EXPIRED,
    ("CANCELLED_IMMEDIATE", "ACTIVE"): LifecycleEventType.SUBSCRIPTION_REACTIVATED,
    ("SUBSCRIPTION_EXPIRED", "ACTIVE"): LifecycleEventType.SUBSCRIPTION_REACTIVATED,
    ("READ_ONLY", "ACTIVE"): LifecycleEventType.SUBSCRIPTION_REACTIVATED,
    ("ACTIVE", "SUSPENDED"): LifecycleEventType.ACCOUNT_SUSPENDED,
    ("GRACE_PERIOD", "SUSPENDED"): LifecycleEventType.ACCOUNT_SUSPENDED,
    ("ACTIVE", "ARCHIVED"): LifecycleEventType.ACCOUNT_ARCHIVED,
    ("ACTIVE", "ACCOUNT_DELETED"): LifecycleEventType.ACCOUNT_DELETED,
}


_EVENT_CATEGORY: Dict[LifecycleEventType, LifecycleEventCategory] = {
    LifecycleEventType.ACCOUNT_ACTIVATED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.TRIAL_STARTED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.TRIAL_EXPIRED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.GRACE_PERIOD_STARTED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.PAYMENT_RECOVERED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.CANCELLATION_SCHEDULED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.CANCELLATION_CANCELLED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.SUBSCRIPTION_EXPIRED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.SUBSCRIPTION_REACTIVATED: LifecycleEventCategory.REACTIVATION,
    LifecycleEventType.ACCOUNT_SUSPENDED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.ACCOUNT_ARCHIVED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.ACCOUNT_DELETED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.PORTAL_MODE_CHANGED: LifecycleEventCategory.RUNTIME,
    LifecycleEventType.RUNTIME_CONTRACT_CHANGED: LifecycleEventCategory.RUNTIME,
    LifecycleEventType.LIFECYCLE_STATE_CHANGED: LifecycleEventCategory.LIFECYCLE,
    LifecycleEventType.CAPABILITIES_CHANGED: LifecycleEventCategory.RUNTIME,
    LifecycleEventType.SESSION_RUNTIME_CHANGED: LifecycleEventCategory.SESSION,
    LifecycleEventType.BACKGROUND_POLICY_CHANGED: LifecycleEventCategory.BACKGROUND,
    LifecycleEventType.COMMUNICATION_SUPPRESSED: LifecycleEventCategory.COMMUNICATION,
    LifecycleEventType.COMMUNICATION_SENT: LifecycleEventCategory.COMMUNICATION,
    LifecycleEventType.REACTIVATION_STARTED: LifecycleEventCategory.REACTIVATION,
    LifecycleEventType.REACTIVATION_COMPLETED: LifecycleEventCategory.REACTIVATION,
    LifecycleEventType.REACTIVATION_FAILED: LifecycleEventCategory.REACTIVATION,
    LifecycleEventType.RECOVERY_JOURNEY_STARTED: LifecycleEventCategory.RECOVERY,
    LifecycleEventType.RECOVERY_JOURNEY_COMPLETED: LifecycleEventCategory.RECOVERY,
    LifecycleEventType.RECOVERY_JOURNEY_ABANDONED: LifecycleEventCategory.RECOVERY,
}

_consumers: Dict[LifecycleEventCategory, List[LifecycleEventHandler]] = {
    cat: [] for cat in LifecycleEventCategory
}


@dataclass(frozen=True)
class LifecycleEventPayload:
    event_type: str
    client_id: str
    lifecycle_state: Optional[str] = None
    lifecycle_state_before: Optional[str] = None
    lifecycle_state_after: Optional[str] = None
    portal_mode: Optional[str] = None
    portal_mode_before: Optional[str] = None
    portal_mode_after: Optional[str] = None
    runtime_version: Optional[Any] = None
    runtime_version_before: Optional[Any] = None
    contract_version: str = CONTRACT_VERSION
    session_version: Optional[Any] = None
    capability_version: Optional[str] = None
    source_service: str = "account_lifecycle_event_authority"
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    event_category: str = LifecycleEventCategory.RUNTIME.value
    severity: str = "info"
    schema_version: str = SCHEMA_VERSION
    policy_version: str = POLICY_VERSION
    trigger: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "event_id": f"lev_{uuid.uuid4().hex[:24]}",
            "event_type": self.event_type,
            "event_category": self.event_category,
            "client_id": self.client_id,
            "lifecycle_state": self.lifecycle_state,
            "lifecycle_state_before": self.lifecycle_state_before,
            "lifecycle_state_after": self.lifecycle_state_after,
            "portal_mode": self.portal_mode,
            "portal_mode_before": self.portal_mode_before,
            "portal_mode_after": self.portal_mode_after,
            "runtime_version": self.runtime_version,
            "runtime_version_before": self.runtime_version_before,
            "contract_version": self.contract_version,
            "session_version": self.session_version,
            "capability_version": self.capability_version,
            "source_service": self.source_service,
            "correlation_id": self.correlation_id or f"corr_{self.client_id}",
            "causation_id": self.causation_id,
            "idempotency_key": self.idempotency_key,
            "severity": self.severity,
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "trigger": self.trigger,
            "metadata": dict(self.metadata or {}),
            "occurred_at": now,
            "created_at": now,
        }


def register_lifecycle_event_consumer(
    category: LifecycleEventCategory,
    handler: LifecycleEventHandler,
) -> None:
    _consumers.setdefault(category, []).append(handler)


def _capabilities_fingerprint(contract: Mapping[str, Any]) -> str:
    caps = contract.get("capabilities") or {}
    material = "|".join(f"{k}:{caps[k]}" for k in sorted(caps.keys()))
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def detect_runtime_contract_events(
    previous: Optional[Mapping[str, Any]],
    current: Mapping[str, Any],
    *,
    source_service: str = "account_lifecycle_runtime_contract",
    trigger: Optional[str] = None,
    correlation_id: Optional[str] = None,
    causation_id: Optional[str] = None,
) -> List[LifecycleEventPayload]:
    """Derive authoritative lifecycle events from runtime contract material change."""
    client_id = str(current.get("client_id") or "")
    if not client_id:
        return []

    prev = previous or {}
    events: List[LifecycleEventPayload] = []
    ls_before = str(prev.get("lifecycle_state") or "")
    ls_after = str(current.get("lifecycle_state") or "")
    pm_before = str(prev.get("portal_mode") or "")
    pm_after = str(current.get("portal_mode") or "")
    rv_before = prev.get("runtime_version")
    rv_after = current.get("runtime_version")

    base = {
        "client_id": client_id,
        "lifecycle_state": ls_after,
        "portal_mode": pm_after,
        "runtime_version": rv_after,
        "source_service": source_service,
        "trigger": trigger,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
    }

    if ls_before and ls_before != ls_after:
        specific = _STATE_TRANSITION_EVENT.get((ls_before, ls_after))
        if specific:
            events.append(
                LifecycleEventPayload(
                    event_type=specific.value,
                    lifecycle_state_before=ls_before,
                    lifecycle_state_after=ls_after,
                    portal_mode_before=pm_before,
                    portal_mode_after=pm_after,
                    runtime_version_before=rv_before,
                    event_category=_EVENT_CATEGORY[specific].value,
                    idempotency_key=f"{client_id}:{specific.value}:{ls_before}:{ls_after}:{rv_after}",
                    **base,
                )
            )
        events.append(
            LifecycleEventPayload(
                event_type=LifecycleEventType.LIFECYCLE_STATE_CHANGED.value,
                lifecycle_state_before=ls_before,
                lifecycle_state_after=ls_after,
                portal_mode_before=pm_before,
                portal_mode_after=pm_after,
                runtime_version_before=rv_before,
                event_category=LifecycleEventCategory.LIFECYCLE.value,
                idempotency_key=f"{client_id}:LifecycleStateChanged:{ls_before}:{ls_after}:{rv_after}",
                **base,
            )
        )

    if pm_before and pm_before != pm_after:
        events.append(
            LifecycleEventPayload(
                event_type=LifecycleEventType.PORTAL_MODE_CHANGED.value,
                portal_mode_before=pm_before,
                portal_mode_after=pm_after,
                runtime_version_before=rv_before,
                event_category=LifecycleEventCategory.RUNTIME.value,
                idempotency_key=f"{client_id}:PortalModeChanged:{pm_before}:{pm_after}:{rv_after}",
                **base,
            )
        )

    if prev and _capabilities_fingerprint(prev) != _capabilities_fingerprint(current):
        events.append(
            LifecycleEventPayload(
                event_type=LifecycleEventType.CAPABILITIES_CHANGED.value,
                runtime_version_before=rv_before,
                capability_version=_capabilities_fingerprint(current),
                event_category=LifecycleEventCategory.RUNTIME.value,
                idempotency_key=f"{client_id}:CapabilitiesChanged:{rv_after}",
                metadata={"capability_fingerprint": _capabilities_fingerprint(current)},
                **base,
            )
        )

    bg_before = dict(prev.get("background_policy") or {})
    bg_after = dict(current.get("background_policy") or {})
    if prev and bg_before != bg_after:
        events.append(
            LifecycleEventPayload(
                event_type=LifecycleEventType.BACKGROUND_POLICY_CHANGED.value,
                runtime_version_before=rv_before,
                event_category=LifecycleEventCategory.BACKGROUND.value,
                idempotency_key=f"{client_id}:BackgroundPolicyChanged:{rv_after}",
                **base,
            )
        )

    if not prev or rv_before != rv_after:
        events.append(
            LifecycleEventPayload(
                event_type=LifecycleEventType.RUNTIME_CONTRACT_CHANGED.value,
                runtime_version_before=rv_before,
                event_category=LifecycleEventCategory.RUNTIME.value,
                idempotency_key=f"{client_id}:RuntimeContractChanged:{rv_before}:{rv_after}",
                **base,
            )
        )
        events.append(
            LifecycleEventPayload(
                event_type=LifecycleEventType.SESSION_RUNTIME_CHANGED.value,
                runtime_version_before=rv_before,
                event_category=LifecycleEventCategory.SESSION.value,
                idempotency_key=f"{client_id}:SessionRuntimeChanged:{rv_before}:{rv_after}",
                metadata={"session_refresh_recommended": True},
                **base,
            )
        )

    return events


class LifecycleEventAuthority:
    """Publish and dispatch authoritative lifecycle events."""

    def __init__(self, db):
        self.db = db

    async def publish(self, payload: LifecycleEventPayload) -> Dict[str, Any]:
        doc = payload.to_document()
        idem = doc.get("idempotency_key")
        if idem:
            existing = await self.db[EVENTS_COLLECTION].find_one(
                {"idempotency_key": idem},
                {"_id": 0, "event_id": 1},
            )
            if existing:
                logger.info(
                    "lifecycle_event_duplicate_skipped client_id=%s event_type=%s idempotency_key=%s",
                    payload.client_id,
                    payload.event_type,
                    idem,
                )
                return {"status": "duplicate", "event_id": existing.get("event_id"), "duplicate": True}

        await self.db[EVENTS_COLLECTION].insert_one(doc)
        await _dispatch_event(doc)
        await _audit_lifecycle_event(self.db, doc)
        log_lifecycle_event_published(doc)
        return {"status": "published", "event_id": doc["event_id"], "duplicate": False}

    async def publish_many(self, payloads: List[LifecycleEventPayload]) -> List[Dict[str, Any]]:
        results = []
        for payload in payloads:
            results.append(await self.publish(payload))
        return results


async def publish_lifecycle_event(db, payload: LifecycleEventPayload) -> Dict[str, Any]:
    return await LifecycleEventAuthority(db).publish(payload)


async def publish_runtime_contract_transition(
    db,
    previous: Optional[Mapping[str, Any]],
    current: Mapping[str, Any],
    *,
    source_service: str = "account_lifecycle_runtime_contract",
    trigger: Optional[str] = None,
    correlation_id: Optional[str] = None,
    causation_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    payloads = detect_runtime_contract_events(
        previous,
        current,
        source_service=source_service,
        trigger=trigger,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
    if not payloads:
        return []
    authority = LifecycleEventAuthority(db)
    return await authority.publish_many(payloads)


async def _dispatch_event(event_doc: Mapping[str, Any]) -> None:
    category_str = str(event_doc.get("event_category") or LifecycleEventCategory.RUNTIME.value)
    try:
        category = LifecycleEventCategory(category_str)
    except ValueError:
        category = LifecycleEventCategory.RUNTIME
    handlers = _consumers.get(category, []) + _consumers.get(LifecycleEventCategory.RUNTIME, [])
    seen = set()
    for handler in handlers:
        key = id(handler)
        if key in seen:
            continue
        seen.add(key)
        try:
            await handler(event_doc)
        except Exception as exc:
            logger.warning(
                "lifecycle_event_consumer_failed event_type=%s category=%s error=%s",
                event_doc.get("event_type"),
                category_str,
                exc,
            )


async def _audit_lifecycle_event(db, event_doc: Mapping[str, Any]) -> None:
    try:
        from models import AuditAction
        from utils.audit import create_audit_log

        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            client_id=event_doc.get("client_id"),
            metadata={
                "action_type": "LIFECYCLE_EVENT_PUBLISHED",
                "event_type": event_doc.get("event_type"),
                "event_id": event_doc.get("event_id"),
                "lifecycle_state_before": event_doc.get("lifecycle_state_before"),
                "lifecycle_state_after": event_doc.get("lifecycle_state_after"),
                "portal_mode_after": event_doc.get("portal_mode_after"),
                "runtime_version": event_doc.get("runtime_version"),
                "correlation_id": event_doc.get("correlation_id"),
                "trigger": event_doc.get("trigger"),
            },
        )
    except Exception as exc:
        logger.debug("lifecycle_event_audit_skipped: %s", exc)


def log_lifecycle_event_published(event_doc: Mapping[str, Any]) -> None:
    logger.info(
        "lifecycle_event_published client_id=%s event_type=%s category=%s lifecycle=%s "
        "runtime_version=%s correlation_id=%s schema=%s",
        event_doc.get("client_id"),
        event_doc.get("event_type"),
        event_doc.get("event_category"),
        event_doc.get("lifecycle_state_after") or event_doc.get("lifecycle_state"),
        event_doc.get("runtime_version"),
        event_doc.get("correlation_id"),
        event_doc.get("schema_version"),
    )


async def _consumer_runtime_cache_invalidation(event_doc: Mapping[str, Any]) -> None:
    from services.account_lifecycle_runtime_contract import invalidate_runtime_cache_for_client

    client_id = event_doc.get("client_id")
    if client_id:
        invalidate_runtime_cache_for_client(str(client_id))


def _register_builtin_consumers() -> None:
    register_lifecycle_event_consumer(LifecycleEventCategory.RUNTIME, _consumer_runtime_cache_invalidation)
    register_lifecycle_event_consumer(LifecycleEventCategory.LIFECYCLE, _consumer_runtime_cache_invalidation)
    register_lifecycle_event_consumer(LifecycleEventCategory.SESSION, _consumer_runtime_cache_invalidation)


_register_builtin_consumers()
