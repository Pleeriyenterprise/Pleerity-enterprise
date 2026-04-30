"""
Frozen predicate contract for policy-backed portfolio risk classification.
"""
from __future__ import annotations

from typing import Any, Dict

from services.policy_reason_codes import PolicyReasonCode


POLICY_CLASSIFICATION_VERSION = "v1"

_HARD_FAILURE_KINDS = frozenset({"EXPIRED", "MISMATCHED_EVIDENCE", "MISSING_EVIDENCE"})
_ATTENTION_ONLY_KINDS = frozenset(
    {
        "EVIDENCE_UPLOADED_UNCONFIRMED",
        "EXPIRING_SOON",
        "DELIVERY_PROOF_MISSING",
        "TENANT_DELIVERY_PROOF_MISSING",
        "ACTION_REQUIRED",
        "AUTHORITY_UNSYNCED",
    }
)
_BAD_EVIDENCE_STATES = frozenset({"MISSING", "REJECTED", "MISMATCH_FLAGGED", "VERIFIED_EXPIRED"})
_PENDING_EVIDENCE_STATES = frozenset(
    {"UPLOADED_UNCONFIRMED", "EXTRACTION_COMPLETE_PENDING_CONFIRMATION", "PENDING_ADMIN_REVIEW"}
)


def policy_contract_metadata() -> Dict[str, Any]:
    return {
        "policy_classification_version": POLICY_CLASSIFICATION_VERSION,
        "predicate_freeze_rule": (
            "After rollout cohorts start, predicate logic changes require version bump, migration note, "
            "rollout review, and rollback review."
        ),
        "severity_only_critical_breach_forbidden": True,
    }


def _bool(x: Any) -> bool:
    return bool(x)


def classify_gap_policy_predicates(gap: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Exact predicate contract (PR1): no runtime consumers switched yet.
    """
    applicability = str(facts.get("applicability_state") or "UNKNOWN").upper()
    mandatory = applicability == "REQUIRED" and _bool(facts.get("is_mandatory"))
    policy_criticality = str(facts.get("policy_criticality") or "MEDIUM").upper()
    critical_policy = policy_criticality in {"HIGH", "CRITICAL"}
    high_policy = policy_criticality in {"MEDIUM", "HIGH", "CRITICAL"}

    gap_kind = str(gap.get("gap_kind") or "").upper()
    evidence_state = str(facts.get("evidence_state_normalized") or "").upper()
    gap_hard_failure = gap_kind in _HARD_FAILURE_KINDS
    gap_attention = gap_kind in _ATTENTION_ONLY_KINDS
    ea_bad = evidence_state in _BAD_EVIDENCE_STATES
    ea_pending = evidence_state in _PENDING_EVIDENCE_STATES
    delivery_proof_required = _bool(gap.get("delivery_proof_required"))

    critical_mandatory_breach = mandatory and critical_policy and gap_hard_failure and ea_bad
    high_risk_gap = mandatory and high_policy and (
        gap_hard_failure
        or (gap_kind in {"DELIVERY_PROOF_MISSING", "TENANT_DELIVERY_PROOF_MISSING"} and delivery_proof_required)
    )
    attention_only_gap = (
        not critical_mandatory_breach
        and not high_risk_gap
        and (
            gap_attention
            or ea_pending
            or (gap_kind == "EXPIRING_SOON" and gap.get("days_to_expiry") is not None and int(gap["days_to_expiry"]) >= 0)
        )
    )
    unknown_or_stale_suppression = _bool(gap.get("unknown_or_stale_property_count", 0) > 0) or gap_kind in {
        "AUTHORITY_UNSYNCED",
        "ACTION_REQUIRED",
    }

    reason_codes = []
    if critical_mandatory_breach:
        reason_codes.append(PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value)
    elif high_risk_gap:
        reason_codes.append(PolicyReasonCode.UNRESOLVED_HIGH_RISK_GAP.value)
    elif attention_only_gap:
        reason_codes.append(PolicyReasonCode.ATTENTION_ONLY_GAP.value)
    if unknown_or_stale_suppression:
        reason_codes.append(PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value)

    return {
        "policy_classification_version": POLICY_CLASSIFICATION_VERSION,
        "critical_mandatory_breach": critical_mandatory_breach,
        "high_risk_gap": high_risk_gap,
        "attention_only_gap": attention_only_gap,
        "unknown_or_stale_suppression": unknown_or_stale_suppression,
        "reason_codes": reason_codes,
    }
