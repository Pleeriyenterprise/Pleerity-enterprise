"""
Account Background Runtime Authority (ILP-6).

Central guard for background jobs, queues, and notification dispatch.
Decisions consume Runtime Contract background_policy and communication_policy only.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import (
    CONTRACT_VERSION,
    resolve_runtime_contract_for_client,
)

logger = logging.getLogger(__name__)

POLICY_VERSION = "account_background_runtime_v1"


class BackgroundJobDecision(str, Enum):
    CONTINUE = "CONTINUE"
    PAUSE = "PAUSE"
    SKIP = "SKIP"
    TERMINATE = "TERMINATE"
    RETENTION_ONLY = "RETENTION_ONLY"


# job_type → background_policy key on Runtime Contract
JOB_BACKGROUND_POLICY_KEYS: Dict[str, str] = {
    "reminders": "reminders",
    "daily_reminders": "reminders",
    "monthly_digest": "digest",
    "digest": "digest",
    "scheduled_reports": "scheduled_reports",
    "compliance_check": "compliance_monitoring",
    "compliance_monitoring": "compliance_monitoring",
    "compliance_status_check": "compliance_monitoring",
    "score_recalculation": "score_recalculation",
    "compliance_recalc": "score_recalculation",
    "compliance_score_snapshots": "score_recalculation",
    "compliance_recalc_queue": "queue_processing",
    "risk_recalculation": "risk_recalculation",
    "risk_signals": "risk_recalculation",
    "predictive_insights": "risk_recalculation",
    "risk_signal_regen_queue": "queue_processing",
    "queue_processing": "queue_processing",
    "rent_operations": "queue_processing",
    "work_order_nudge": "queue_processing",
    "operational_recovery": "queue_processing",
    "renewal_reminders": "reminders",
    "subscription_lifecycle": "reminders",
    "lifecycle_sync": "queue_processing",
}

# Optional capability enforcement (existing contract rows — not CAP_BG_* schema extension)
JOB_CAPABILITY_REQUIREMENTS: Dict[str, str] = {
    "reminders": "CAP_NOTIF_EMAIL",
    "daily_reminders": "CAP_NOTIF_EMAIL",
    "monthly_digest": "CAP_NOTIF_EMAIL",
    "digest": "CAP_NOTIF_EMAIL",
    "scheduled_reports": "CAP_REPORT_SCHEDULE",
    "renewal_reminders": "CAP_NOTIF_EMAIL",
}

# Communication channel requirements per job type
JOB_COMMUNICATION_REQUIREMENTS: Dict[str, str] = {
    "reminders": "email_operational",
    "daily_reminders": "email_operational",
    "monthly_digest": "email_operational",
    "digest": "email_operational",
    "compliance_check": "email_operational",
    "compliance_monitoring": "email_operational",
    "compliance_status_check": "email_operational",
    "scheduled_reports": "email_operational",
    "renewal_reminders": "email_billing",
    "subscription_lifecycle": "email_billing",
}

NOTIFICATION_TEMPLATE_JOB_TYPES: Dict[str, str] = {
    "COMPLIANCE_EXPIRY_REMINDER": "daily_reminders",
    "MONTHLY_COMPLIANCE_DIGEST": "monthly_digest",
    "SCHEDULED_REPORT": "scheduled_reports",
    "SUBSCRIPTION_GRACE_REMINDER": "renewal_reminders",
    "SUBSCRIPTION_RENEWAL_7D": "renewal_reminders",
    "SUBSCRIPTION_RENEWAL_3D": "renewal_reminders",
    "RENT_REMINDER": "daily_reminders",
}

_QUEUE_RESCHEDULE_MINUTES: Dict[BackgroundJobDecision, int] = {
    BackgroundJobDecision.SKIP: 30,
    BackgroundJobDecision.PAUSE: 60,
    BackgroundJobDecision.RETENTION_ONLY: 60,
}

_POLICY_ACTION_TO_DECISION: Dict[str, BackgroundJobDecision] = {
    "CONTINUE": BackgroundJobDecision.CONTINUE,
    "PAUSE": BackgroundJobDecision.SKIP,
    "TERMINATE": BackgroundJobDecision.TERMINATE,
    "REVOKE": BackgroundJobDecision.SKIP,
    "DRAIN_PAUSE": BackgroundJobDecision.PAUSE,
}


@dataclass(frozen=True)
class BackgroundRuntimeDecision:
    decision: BackgroundJobDecision
    client_id: str
    job_type: str
    lifecycle_state: str
    portal_mode: str
    background_policy_key: str
    background_policy_action: str
    reason: str
    runtime_version: Optional[int] = None
    policy_version: str = POLICY_VERSION
    required_capability: Optional[str] = None
    capability_grant: Optional[str] = None
    safe_to_retry: bool = True
    idempotency_key: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision == BackgroundJobDecision.CONTINUE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "client_id": self.client_id,
            "job_type": self.job_type,
            "lifecycle_state": self.lifecycle_state,
            "portal_mode": self.portal_mode,
            "background_policy_key": self.background_policy_key,
            "background_policy_action": self.background_policy_action,
            "reason": self.reason,
            "runtime_version": self.runtime_version,
            "policy_version": self.policy_version,
            "required_capability": self.required_capability,
            "capability_grant": self.capability_grant,
            "safe_to_retry": self.safe_to_retry,
            "idempotency_key": self.idempotency_key,
            "diagnostics": dict(self.diagnostics),
        }


def _policy_decision(action: str) -> BackgroundJobDecision:
    return _POLICY_ACTION_TO_DECISION.get(str(action or "").upper(), BackgroundJobDecision.SKIP)


def _retention_only(lifecycle_state: str) -> bool:
    return lifecycle_state in ("ARCHIVED", "ACCOUNT_DELETED", "READ_ONLY")


class BackgroundRuntimeAuthority:
    """Evaluate whether a background job may run for a client."""

    def __init__(self, db):
        self.db = db
        self._enforcement = CapabilityEnforcementService(db)

    async def evaluate(
        self,
        client_id: str,
        job_type: str,
        *,
        contract: Optional[Mapping[str, Any]] = None,
        channel: Optional[str] = None,
        idempotency_suffix: Optional[str] = None,
    ) -> BackgroundRuntimeDecision:
        if not client_id:
            return BackgroundRuntimeDecision(
                decision=BackgroundJobDecision.SKIP,
                client_id="",
                job_type=job_type,
                lifecycle_state="UNKNOWN",
                portal_mode="FULL_ACCESS",
                background_policy_key="",
                background_policy_action="",
                reason="missing_client_id",
                safe_to_retry=False,
            )

        if contract is None:
            contract = await resolve_runtime_contract_for_client(self.db, client_id)

        lifecycle_state = str(contract.get("lifecycle_state") or "UNKNOWN")
        portal_mode = str(contract.get("portal_mode") or "FULL_ACCESS")
        runtime_version = contract.get("runtime_version")
        bg_policy = dict(contract.get("background_policy") or {})
        comm_policy = dict(contract.get("communication_policy") or {})
        policy_key = JOB_BACKGROUND_POLICY_KEYS.get(job_type, "queue_processing")
        policy_action = str(bg_policy.get(policy_key) or "PAUSE").upper()
        base_decision = _policy_decision(policy_action)

        if lifecycle_state == "UNKNOWN":
            return self._build(
                BackgroundJobDecision.SKIP,
                client_id,
                job_type,
                lifecycle_state,
                portal_mode,
                policy_key,
                policy_action,
                "lifecycle_unknown_safe_skip",
                runtime_version,
                safe_to_retry=True,
                idempotency_suffix=idempotency_suffix,
            )

        if _retention_only(lifecycle_state) and base_decision == BackgroundJobDecision.CONTINUE:
            base_decision = BackgroundJobDecision.RETENTION_ONLY

        if base_decision != BackgroundJobDecision.CONTINUE:
            return self._build(
                base_decision,
                client_id,
                job_type,
                lifecycle_state,
                portal_mode,
                policy_key,
                policy_action,
                f"background_policy_{policy_key}_{policy_action.lower()}",
                runtime_version,
                safe_to_retry=base_decision in (BackgroundJobDecision.SKIP, BackgroundJobDecision.PAUSE),
                idempotency_suffix=idempotency_suffix,
            )

        comm_key = JOB_COMMUNICATION_REQUIREMENTS.get(job_type)
        if comm_key and not comm_policy.get(comm_key, False):
            return self._build(
                BackgroundJobDecision.SKIP,
                client_id,
                job_type,
                lifecycle_state,
                portal_mode,
                policy_key,
                policy_action,
                f"communication_policy_{comm_key}_denied",
                runtime_version,
                idempotency_suffix=idempotency_suffix,
            )

        if channel == "sms" and not comm_policy.get("sms", False):
            return self._build(
                BackgroundJobDecision.SKIP,
                client_id,
                job_type,
                lifecycle_state,
                portal_mode,
                policy_key,
                policy_action,
                "communication_policy_sms_denied",
                runtime_version,
                idempotency_suffix=idempotency_suffix,
            )

        cap_id = JOB_CAPABILITY_REQUIREMENTS.get(job_type)
        cap_grant = None
        if cap_id:
            cap_result = self._enforcement.evaluate_from_contract(contract, cap_id, "read")
            cap_grant = cap_result.grant
            if not cap_result.allowed:
                return self._build(
                    BackgroundJobDecision.SKIP,
                    client_id,
                    job_type,
                    lifecycle_state,
                    portal_mode,
                    policy_key,
                    policy_action,
                    f"capability_{cap_id}_denied",
                    runtime_version,
                    required_capability=cap_id,
                    capability_grant=cap_grant,
                    idempotency_suffix=idempotency_suffix,
                )

        return self._build(
            BackgroundJobDecision.CONTINUE,
            client_id,
            job_type,
            lifecycle_state,
            portal_mode,
            policy_key,
            policy_action,
            "background_runtime_continue",
            runtime_version,
            required_capability=cap_id,
            capability_grant=cap_grant,
            idempotency_suffix=idempotency_suffix,
        )

    def _build(
        self,
        decision: BackgroundJobDecision,
        client_id: str,
        job_type: str,
        lifecycle_state: str,
        portal_mode: str,
        policy_key: str,
        policy_action: str,
        reason: str,
        runtime_version: Optional[int],
        *,
        required_capability: Optional[str] = None,
        capability_grant: Optional[str] = None,
        safe_to_retry: bool = True,
        idempotency_suffix: Optional[str] = None,
    ) -> BackgroundRuntimeDecision:
        suffix = idempotency_suffix or "default"
        idempotency_key = f"bg:{client_id}:{job_type}:{runtime_version}:{suffix}"
        result = BackgroundRuntimeDecision(
            decision=decision,
            client_id=client_id,
            job_type=job_type,
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            background_policy_key=policy_key,
            background_policy_action=policy_action,
            reason=reason,
            runtime_version=runtime_version,
            required_capability=required_capability,
            capability_grant=capability_grant,
            safe_to_retry=safe_to_retry,
            idempotency_key=idempotency_key,
            diagnostics={
                "contract_version": CONTRACT_VERSION,
                "policy_version": POLICY_VERSION,
            },
        )
        if decision != BackgroundJobDecision.CONTINUE:
            logger.info(
                "background_runtime_decision client_id=%s job_type=%s decision=%s reason=%s lifecycle=%s runtime_version=%s",
                client_id,
                job_type,
                decision.value,
                reason,
                lifecycle_state,
                runtime_version,
            )
        return result


async def evaluate_background_runtime(
    db,
    client_id: str,
    job_type: str,
    **kwargs,
) -> BackgroundRuntimeDecision:
    return await BackgroundRuntimeAuthority(db).evaluate(client_id, job_type, **kwargs)


def resolve_notification_job_type(
    template_key: str,
    template: Optional[Mapping[str, Any]] = None,
    event_type: Optional[str] = None,
) -> str:
    """Map notification template / event to background_policy job_type."""
    key = str(template_key or "").upper()
    if key in NOTIFICATION_TEMPLATE_JOB_TYPES:
        return NOTIFICATION_TEMPLATE_JOB_TYPES[key]
    template = template or {}
    category = str(template.get("email_category") or "").lower()
    if category in ("compliance_notification", "compliance"):
        return "compliance_monitoring"
    if category in ("billing", "subscription"):
        return "renewal_reminders"
    evt = str(event_type or "").lower()
    if "digest" in evt:
        return "monthly_digest"
    if "renewal" in evt or "grace" in evt or "subscription" in evt:
        return "renewal_reminders"
    if "scheduled_report" in evt:
        return "scheduled_reports"
    if "compliance" in evt or "reminder" in evt:
        return "daily_reminders"
    return "daily_reminders"


def queue_runtime_action(decision: BackgroundRuntimeDecision) -> str:
    """Return process | reschedule | terminate for queue consumers."""
    if decision.decision == BackgroundJobDecision.CONTINUE:
        return "process"
    if decision.decision == BackgroundJobDecision.TERMINATE:
        return "terminate"
    return "reschedule"


async def apply_queue_runtime_suppression(
    db,
    *,
    collection_name: str,
    item_id: Any,
    decision: BackgroundRuntimeDecision,
    status_pending: str = "PENDING",
    status_dead: str = "DEAD",
) -> None:
    """
    Auditable queue semantics when background runtime denies processing.
    Does not silently drop: reschedule with reason or mark dead for TERMINATE.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    action = queue_runtime_action(decision)
    coll = getattr(db, collection_name)
    base_meta = {
        "runtime_pause_reason": decision.reason,
        "runtime_pause_decision": decision.decision.value,
        "runtime_version": decision.runtime_version,
        "lifecycle_state": decision.lifecycle_state,
        "background_policy_key": decision.background_policy_key,
        "updated_at": now_iso,
    }
    if action == "terminate":
        await coll.update_one(
            {"_id": item_id},
            {
                "$set": {
                    **base_meta,
                    "status": status_dead,
                    "runtime_terminated_at": now_iso,
                }
            },
        )
        return
    delay = _QUEUE_RESCHEDULE_MINUTES.get(decision.decision, 30)
    next_run = (now + timedelta(minutes=delay)).isoformat()
    await coll.update_one(
        {"_id": item_id},
        {
            "$set": {
                **base_meta,
                "status": status_pending,
                "runtime_paused_at": now_iso,
                "next_run_at": next_run,
            }
        },
    )


async def gate_client_background_job(
    db,
    client_id: str,
    job_type: str,
    **kwargs,
) -> Tuple[bool, BackgroundRuntimeDecision]:
    """Evaluate runtime authority; log and return (allowed, decision)."""
    decision = await evaluate_background_runtime(db, client_id, job_type, **kwargs)
    log_background_decision(decision)
    return decision.allowed, decision


def log_background_decision(decision: BackgroundRuntimeDecision) -> None:
    """Structured diagnostic log for suppressed background work."""
    if decision.allowed:
        return
    logger.info(
        "background_job_suppressed",
        extra={"background_decision": decision.to_dict()},
    )
