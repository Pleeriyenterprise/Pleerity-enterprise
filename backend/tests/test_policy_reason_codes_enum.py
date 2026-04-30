from services.policy_reason_codes import PolicyReasonCode, policy_reason_code_values


def test_policy_reason_codes_are_canonical_enums():
    vals = policy_reason_code_values()
    assert PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value in vals
    assert PolicyReasonCode.UNRESOLVED_HIGH_RISK_GAP.value in vals
    assert PolicyReasonCode.ATTENTION_ONLY_GAP.value in vals
    assert PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value in vals
    assert PolicyReasonCode.CRITICAL_PROPERTY_ESCALATION.value in vals
    assert PolicyReasonCode.ANTI_FLAPPING_RECONCILIATION_HOLD.value in vals
    assert PolicyReasonCode.PERSISTED_PORTFOLIO_HEADLINE_DOMINATES_EFFECTIVE.value in vals
    assert PolicyReasonCode.HIGH_IMPACT_UNRESOLVED_APPLICABILITY.value in vals
    assert "free_form_reason" not in vals


def test_policy_reason_codes_unique():
    vals = [c.value for c in PolicyReasonCode]
    assert len(vals) == len(set(vals))
