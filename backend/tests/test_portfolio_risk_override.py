from services.policy_reason_codes import PolicyReasonCode
from services.portfolio_risk_override import (
    derive_policy_portfolio_risk_override,
    derive_portfolio_risk_override,
    select_effective_portfolio_risk_override,
)


def test_override_escalates_on_critical_gaps():
    out = derive_portfolio_risk_override(
        base_portfolio_risk_state="Low Risk",
        properties=[
            {"property_id": "p1", "compliance_score": 92, "risk_level": "Low Risk", "overdue_count": 0},
        ],
        property_breakdown=[
            {"property_id": "p1", "score": 92, "risk_level": "Low Risk", "overdue": 0, "score_status": "ok"},
        ],
        gap_engine={"by_severity": {"CRITICAL": 1, "HIGH": 0}},
    )
    assert out["base_portfolio_risk_state"] == "Low Risk"
    assert out["effective_portfolio_risk_state"] == "Critical Risk"
    assert out["attention_required"] is True
    assert out["critical_property_escalation"] is True
    assert out["suppress_positive_headline"] is True
    assert out["high_risk_gap_count"] == 1
    assert PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value in out["risk_override_reasons"]


def test_override_escalates_with_severe_overdue_property():
    out = derive_portfolio_risk_override(
        base_portfolio_risk_state="Moderate Risk",
        properties=[
            {"property_id": "p1", "compliance_score": 35, "overdue_count": 2},
        ],
        property_breakdown=[
            {"property_id": "p1", "score": 35, "overdue": 2, "score_status": "ok"},
        ],
        gap_engine={"by_severity": {"CRITICAL": 0, "HIGH": 0}},
    )
    assert out["critical_property_count"] == 1
    assert out["effective_portfolio_risk_state"] == "High Risk"
    assert PolicyReasonCode.CRITICAL_PROPERTY_ESCALATION.value in out["risk_override_reasons"]


def test_override_suppresses_positive_headline_when_stale_signals():
    out = derive_portfolio_risk_override(
        base_portfolio_risk_state="Low Risk",
        properties=[
            {"property_id": "p1", "compliance_score": None, "compliance_score_pending": True},
        ],
        property_breakdown=[
            {"property_id": "p1", "score": None, "score_status": "stale", "overdue": 0},
        ],
        gap_engine={"by_severity": {}},
    )
    assert out["unknown_or_stale_property_count"] == 1
    assert out["suppress_positive_headline"] is True
    assert out["effective_portfolio_risk_state"] == "Moderate Risk"
    assert PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value in out["risk_override_reasons"]


def test_policy_override_uses_policy_counters_not_severity():
    out = derive_policy_portfolio_risk_override(
        base_portfolio_risk_state="Low Risk",
        gap_engine={
            "by_severity": {"CRITICAL": 9, "HIGH": 9},
            "policy": {
                "critical_mandatory_breach_count": 0,
                "high_risk_gap_count": 1,
                "attention_only_gap_count": 0,
                "unknown_or_stale_signal_count": 0,
            },
        },
    )
    assert out["effective_portfolio_risk_state"] == "High Risk"
    assert PolicyReasonCode.UNRESOLVED_HIGH_RISK_GAP.value in out["risk_override_reasons"]
    assert PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value not in out["risk_override_reasons"]


def test_policy_override_critical_without_breach_adds_headline_dominance_code():
    """Base headline Critical + policy high-risk only → effective Critical with explicit codes (not empty)."""
    out = derive_policy_portfolio_risk_override(
        base_portfolio_risk_state="Critical Risk",
        gap_engine={
            "policy": {
                "critical_mandatory_breach_count": 0,
                "high_risk_gap_count": 1,
                "attention_only_gap_count": 0,
                "unknown_or_stale_signal_count": 0,
            },
        },
    )
    assert out["effective_portfolio_risk_state"] == "Critical Risk"
    reasons = out["risk_override_reasons"]
    assert reasons
    assert PolicyReasonCode.UNRESOLVED_HIGH_RISK_GAP.value in reasons
    assert PolicyReasonCode.PERSISTED_PORTFOLIO_HEADLINE_DOMINATES_EFFECTIVE.value in reasons


def test_policy_override_never_critical_with_empty_reasons():
    out = derive_policy_portfolio_risk_override(
        base_portfolio_risk_state="Critical Risk",
        gap_engine={
            "policy": {
                "critical_mandatory_breach_count": 1,
                "high_risk_gap_count": 0,
                "attention_only_gap_count": 0,
                "unknown_or_stale_signal_count": 0,
            },
        },
    )
    assert out["effective_portfolio_risk_state"] == "Critical Risk"
    assert out["risk_override_reasons"]
    assert PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value in out["risk_override_reasons"]


def test_effective_selector_flag_off_keeps_legacy():
    legacy = {
        "effective_portfolio_risk_state": "High Risk",
        "risk_override_reasons": [PolicyReasonCode.UNRESOLVED_HIGH_RISK_GAP.value],
    }
    policy = {
        "effective_portfolio_risk_state": "Moderate Risk",
        "risk_override_reasons": [PolicyReasonCode.ATTENTION_ONLY_GAP.value],
    }
    out = select_effective_portfolio_risk_override(
        legacy_override_output=legacy,
        policy_override_output=policy,
        policy_switch_enabled=False,
        policy_coverage_percent=100.0,
        policy_coverage_threshold_percent=99.5,
        drift_detected=False,
        reconciliation_in_progress=False,
        policy_aggregate_unavailable=False,
    )
    assert out["effective_portfolio_risk_state"] == "High Risk"
    assert out["override_output_source"] == "legacy"


def test_effective_selector_flag_on_uses_policy_unless_fallback_needed():
    legacy = {"effective_portfolio_risk_state": "High Risk", "risk_override_reasons": []}
    policy = {"effective_portfolio_risk_state": "Moderate Risk", "risk_override_reasons": []}
    out = select_effective_portfolio_risk_override(
        legacy_override_output=legacy,
        policy_override_output=policy,
        policy_switch_enabled=True,
        policy_coverage_percent=80.0,
        policy_coverage_threshold_percent=99.5,
        drift_detected=False,
        reconciliation_in_progress=False,
        policy_aggregate_unavailable=False,
    )
    assert out["effective_portfolio_risk_state"] == "High Risk"
    assert out["override_output_source"] == "legacy_fallback"
    assert PolicyReasonCode.POLICY_FIELDS_INCOMPLETE.value in out["fallback_reason_codes"]
