"""
SLA actionability for compliance recalculation — thin mapping over ILP-6 authority.

Does not invent a second lifecycle state machine. Queue SLA evaluation must use the same
``compliance_recalc_queue`` job type the worker uses.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from services.account_background_runtime_authority import (
    BackgroundJobDecision,
    BackgroundRuntimeDecision,
    evaluate_background_runtime,
)

logger = logging.getLogger(__name__)

COMPLIANCE_RECALC_QUEUE_JOB_TYPE = "compliance_recalc_queue"


class ComplianceRecalcSlaClass(str, Enum):
    """Operational treatment of a client for compliance recalc SLA pages."""

    ACTIONABLE = "ACTIONABLE"
    LIFECYCLE_SUPPRESSED = "LIFECYCLE_SUPPRESSED"
    TERMINATED = "TERMINATED"
    UNKNOWN_SAFE_SKIP = "UNKNOWN_SAFE_SKIP"


@dataclass(frozen=True)
class ComplianceRecalcSlaEligibility:
    sla_class: ComplianceRecalcSlaClass
    lifecycle_state: str
    decision: str
    reason: str

    @property
    def operationally_actionable(self) -> bool:
        return self.sla_class == ComplianceRecalcSlaClass.ACTIONABLE


def classify_compliance_recalc_sla_decision(
    decision: BackgroundRuntimeDecision,
) -> ComplianceRecalcSlaEligibility:
    """Map a background-runtime decision onto SLA actionability. Pure; no I/O."""
    lifecycle = str(decision.lifecycle_state or "UNKNOWN")
    reason = str(decision.reason or "")
    if decision.decision == BackgroundJobDecision.CONTINUE:
        sla_class = ComplianceRecalcSlaClass.ACTIONABLE
    elif reason in ("lifecycle_unknown_safe_skip", "missing_client_id") or lifecycle == "UNKNOWN":
        sla_class = ComplianceRecalcSlaClass.UNKNOWN_SAFE_SKIP
    elif decision.decision == BackgroundJobDecision.TERMINATE:
        sla_class = ComplianceRecalcSlaClass.TERMINATED
    else:
        sla_class = ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED
    return ComplianceRecalcSlaEligibility(
        sla_class=sla_class,
        lifecycle_state=lifecycle,
        decision=decision.decision.value,
        reason=reason,
    )


async def resolve_compliance_recalc_sla_eligibility(
    db,
    client_id: str,
    *,
    cache: Optional[Dict[str, ComplianceRecalcSlaEligibility]] = None,
) -> ComplianceRecalcSlaEligibility:
    """
    Resolve SLA class via canonical runtime contract + background authority.

    Loads facts read-only and passes a pre-built contract so monitor ticks do not
    emit lifecycle transition events. Worker decisions remain the authority.

    Pending-flag presentation (compliance_score_pending → score_status calculating)
    is intentionally unchanged here: clearing the flag would make a parked stale
    score look authoritative. Parked vs actively-pending is Phase 2.
    """
    key = str(client_id or "")
    if cache is not None and key in cache:
        return cache[key]

    if not key:
        decision = await evaluate_background_runtime(db, "", COMPLIANCE_RECALC_QUEUE_JOB_TYPE)
    else:
        from services.account_lifecycle_runtime_contract import build_runtime_contract
        from services.account_lifecycle_state_resolver import load_client_and_billing

        client, billing = await load_client_and_billing(db, key)
        client_doc: Optional[Dict[str, Any]]
        if client is not None:
            client_doc = {**client, "client_id": key}
        elif key:
            client_doc = {"client_id": key}
        else:
            client_doc = None
        contract = build_runtime_contract(client=client_doc, billing=billing)
        decision = await evaluate_background_runtime(
            db, key, COMPLIANCE_RECALC_QUEUE_JOB_TYPE, contract=contract
        )

    eligibility = classify_compliance_recalc_sla_decision(decision)
    if cache is not None:
        cache[key] = eligibility
    return eligibility


def automatic_enqueue_skip_bucket(eligibility: ComplianceRecalcSlaEligibility) -> Optional[str]:
    """Metric key when automatic enqueue must not mutate queue/pending. None if eligible."""
    if eligibility.operationally_actionable:
        return None
    if eligibility.sla_class == ComplianceRecalcSlaClass.TERMINATED:
        return "terminal_skipped"
    if eligibility.sla_class == ComplianceRecalcSlaClass.UNKNOWN_SAFE_SKIP:
        return "unknown_safe_skip"
    return "lifecycle_suppressed"


@dataclass(frozen=True)
class AutomaticEnqueueAttempt:
    """Result of a lifecycle-gated automatic enqueue. ``enqueued`` is True only on a new/regenerated row."""

    enqueued: bool
    outcome: str
    eligibility: ComplianceRecalcSlaEligibility


async def enqueue_automatic_compliance_recalc_if_eligible(
    db,
    *,
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    cache: Optional[Dict[str, ComplianceRecalcSlaEligibility]] = None,
) -> AutomaticEnqueueAttempt:
    """
    Automatic/scheduled enqueue gate: authority first, then queue/pending mutation.

    Does not invent a second lifecycle machine. Customer/admin callers must keep using
    ``enqueue_compliance_recalc`` directly.
    """
    eligibility = await resolve_compliance_recalc_sla_eligibility(db, client_id, cache=cache)
    skip = automatic_enqueue_skip_bucket(eligibility)
    if skip:
        logger.info(
            "compliance_recalc automatic enqueue skipped property_id=%s client_id=%s "
            "sla_class=%s lifecycle=%s trigger=%s",
            property_id,
            client_id,
            eligibility.sla_class.value,
            eligibility.lifecycle_state,
            trigger_reason,
        )
        return AutomaticEnqueueAttempt(enqueued=False, outcome=skip, eligibility=eligibility)

    from services.compliance_recalc_queue import enqueue_compliance_recalc

    result = await enqueue_compliance_recalc(
        property_id=property_id,
        client_id=client_id,
        trigger_reason=trigger_reason,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )
    return AutomaticEnqueueAttempt(
        enqueued=bool(result),
        outcome="enqueued" if result else "deduplicated",
        eligibility=eligibility,
    )
