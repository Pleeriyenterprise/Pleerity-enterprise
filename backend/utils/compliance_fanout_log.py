"""Structured ``extra`` for compliance fan-out observability (Stream E phase 3)."""
from __future__ import annotations

from typing import Any, Dict, Optional


def compliance_fanout_extra(
    *,
    op: str,
    stage: str,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    trigger_reason: Optional[str] = None,
    error_count: Optional[int] = None,
    exc_type: Optional[str] = None,
    dedupe: Optional[bool] = None,
    duplicate_suppression_reason: Optional[str] = None,
    surface_name: Optional[str] = None,
    section_name: Optional[str] = None,
    degraded_reason: Optional[str] = None,
    fallback_used: Optional[bool] = None,
    stale_possible: Optional[bool] = None,
    downstream_dependency: Optional[str] = None,
    transition_id: Optional[str] = None,
    transition_origin: Optional[str] = None,
    propagation_stage: Optional[str] = None,
    transition_outcome: Optional[str] = None,
    previous_state: Optional[str] = None,
    resulting_state: Optional[str] = None,
    semantic_state: Optional[str] = None,
    state_reason: Optional[str] = None,
    replay_possible: Optional[bool] = None,
    duplicate_transition_possible: Optional[bool] = None,
    downstream_target: Optional[str] = None,
    enqueue_outcome: Optional[str] = None,
    replay_chain_detected: Optional[bool] = None,
    degraded_possible: Optional[bool] = None,
    review_id: Optional[str] = None,
    admin_override_possible: Optional[bool] = None,
    review_reversal_possible: Optional[bool] = None,
    reviewer_retrigger_possible: Optional[bool] = None,
    automated_transition_possible: Optional[bool] = None,
    generic_touch_sync: Optional[bool] = None,
    reconciliation_sync_possible: Optional[bool] = None,
    backfill_replay_possible: Optional[bool] = None,
    system_reentry_possible: Optional[bool] = None,
    activation_state: Optional[str] = None,
    activation_guard_result: Optional[str] = None,
    activation_governance_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a consistent ``logging`` ``extra`` payload. Values omitted when unknown.
    Callers pass ``extra=compliance_fanout_extra(...)`` — do not merge with other extras
    that reuse these keys unless intentional.
    """
    out: Dict[str, Any] = {
        "event": "compliance_fanout",
        "op": op,
        "stage": stage,
    }
    if dedupe is not None:
        out["dedupe"] = dedupe
    if client_id is not None:
        out["client_id"] = client_id
    if property_id is not None:
        out["property_id"] = property_id
    if requirement_id is not None:
        out["requirement_id"] = requirement_id
    if document_id is not None:
        out["document_id"] = document_id
    if correlation_id is not None:
        out["correlation_id"] = correlation_id
    if trigger_reason is not None:
        out["trigger_reason"] = trigger_reason
    if error_count is not None:
        out["error_count"] = error_count
    if exc_type is not None:
        out["exc_type"] = exc_type
    if duplicate_suppression_reason is not None:
        out["duplicate_suppression_reason"] = duplicate_suppression_reason
    if surface_name is not None:
        out["surface_name"] = surface_name
    if section_name is not None:
        out["section_name"] = section_name
    if degraded_reason is not None:
        out["degraded_reason"] = degraded_reason[:2000] if isinstance(degraded_reason, str) else degraded_reason
    if fallback_used is not None:
        out["fallback_used"] = fallback_used
    if stale_possible is not None:
        out["stale_possible"] = stale_possible
    if downstream_dependency is not None:
        out["downstream_dependency"] = downstream_dependency
    if transition_id is not None:
        out["transition_id"] = transition_id
    if transition_origin is not None:
        out["transition_origin"] = transition_origin
    if propagation_stage is not None:
        out["propagation_stage"] = propagation_stage
    if transition_outcome is not None:
        out["transition_outcome"] = transition_outcome
    if previous_state is not None:
        out["previous_state"] = previous_state
    if resulting_state is not None:
        out["resulting_state"] = resulting_state
    if semantic_state is not None:
        out["semantic_state"] = semantic_state
    if state_reason is not None:
        out["state_reason"] = state_reason
    if replay_possible is not None:
        out["replay_possible"] = replay_possible
    if duplicate_transition_possible is not None:
        out["duplicate_transition_possible"] = duplicate_transition_possible
    if downstream_target is not None:
        out["downstream_target"] = downstream_target
    if enqueue_outcome is not None:
        out["enqueue_outcome"] = enqueue_outcome
    if replay_chain_detected is not None:
        out["replay_chain_detected"] = replay_chain_detected
    if degraded_possible is not None:
        out["degraded_possible"] = degraded_possible
    if review_id is not None:
        out["review_id"] = review_id
    if admin_override_possible is not None:
        out["admin_override_possible"] = admin_override_possible
    if review_reversal_possible is not None:
        out["review_reversal_possible"] = review_reversal_possible
    if reviewer_retrigger_possible is not None:
        out["reviewer_retrigger_possible"] = reviewer_retrigger_possible
    if automated_transition_possible is not None:
        out["automated_transition_possible"] = automated_transition_possible
    if generic_touch_sync is not None:
        out["generic_touch_sync"] = generic_touch_sync
    if reconciliation_sync_possible is not None:
        out["reconciliation_sync_possible"] = reconciliation_sync_possible
    if backfill_replay_possible is not None:
        out["backfill_replay_possible"] = backfill_replay_possible
    if system_reentry_possible is not None:
        out["system_reentry_possible"] = system_reentry_possible
    if activation_state is not None:
        out["activation_state"] = activation_state
    if activation_guard_result is not None:
        out["activation_guard_result"] = activation_guard_result
    if activation_governance_version is not None:
        out["activation_governance_version"] = activation_governance_version
    return out
