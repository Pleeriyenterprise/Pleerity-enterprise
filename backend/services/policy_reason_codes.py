"""
Canonical reason-code enums for policy-backed portfolio risk overrides.

These codes are a frozen contract once rollout cohorts are active.
"""
from __future__ import annotations

from enum import Enum
from typing import Set


class PolicyReasonCode(str, Enum):
    # Breach / gap reasons
    UNRESOLVED_CRITICAL_MANDATORY_BREACH = "UNRESOLVED_CRITICAL_MANDATORY_BREACH"
    UNRESOLVED_HIGH_RISK_GAP = "UNRESOLVED_HIGH_RISK_GAP"
    ATTENTION_ONLY_GAP = "ATTENTION_ONLY_GAP"
    UNKNOWN_OR_STALE_SUPPRESSION = "UNKNOWN_OR_STALE_SUPPRESSION"
    CRITICAL_PROPERTY_ESCALATION = "CRITICAL_PROPERTY_ESCALATION"
    ANTI_FLAPPING_RECONCILIATION_HOLD = "ANTI_FLAPPING_RECONCILIATION_HOLD"
    # Effective headline is capped to the persisted portfolio headline (e.g. base Critical with policy high-risk only).
    PERSISTED_PORTFOLIO_HEADLINE_DOMINATES_EFFECTIVE = "PERSISTED_PORTFOLIO_HEADLINE_DOMINATES_EFFECTIVE"

    # Operational uncertainty (Phase 1): not a confirmed mandatory breach or strict high_risk_gap.
    HIGH_IMPACT_UNRESOLVED_APPLICABILITY = "HIGH_IMPACT_UNRESOLVED_APPLICABILITY"

    # Runtime/operational reasons
    POLICY_FIELDS_INCOMPLETE = "POLICY_FIELDS_INCOMPLETE"
    POLICY_AGGREGATE_UNAVAILABLE = "POLICY_AGGREGATE_UNAVAILABLE"
    RECONCILIATION_IN_PROGRESS = "RECONCILIATION_IN_PROGRESS"
    POLICY_DRIFT_DETECTED = "POLICY_DRIFT_DETECTED"


def policy_reason_code_values() -> Set[str]:
    return {c.value for c in PolicyReasonCode}
