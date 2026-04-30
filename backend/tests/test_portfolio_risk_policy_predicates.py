from services.portfolio_risk_policy import classify_gap_policy_predicates
from services.policy_reason_codes import PolicyReasonCode


def test_critical_mandatory_breach_requires_all_signals():
    gap = {"gap_kind": "EXPIRED", "days_to_expiry": None}
    facts = {
        "applicability_state": "REQUIRED",
        "is_mandatory": True,
        "policy_criticality": "HIGH",
        "evidence_state_normalized": "VERIFIED_EXPIRED",
    }
    out = classify_gap_policy_predicates(gap, facts)
    assert out["critical_mandatory_breach"] is True
    assert PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value in out["reason_codes"]


def test_severity_only_cannot_trigger_critical_breach():
    gap = {"gap_kind": "EXPIRED", "severity": "CRITICAL"}
    facts = {
        "applicability_state": "UNKNOWN",
        "is_mandatory": False,
        "policy_criticality": "LOW",
        "evidence_state_normalized": "VERIFIED_EXPIRED",
    }
    out = classify_gap_policy_predicates(gap, facts)
    assert out["critical_mandatory_breach"] is False


def test_attention_only_gap_when_pending_confirmation():
    gap = {"gap_kind": "EVIDENCE_UPLOADED_UNCONFIRMED", "days_to_expiry": 10}
    facts = {
        "applicability_state": "REQUIRED",
        "is_mandatory": True,
        "policy_criticality": "MEDIUM",
        "evidence_state_normalized": "UPLOADED_UNCONFIRMED",
    }
    out = classify_gap_policy_predicates(gap, facts)
    assert out["critical_mandatory_breach"] is False
    assert out["attention_only_gap"] is True
    assert PolicyReasonCode.ATTENTION_ONLY_GAP.value in out["reason_codes"]
