from __future__ import annotations

from services.semantic_state_read_contract import (
    ATTENTION_ELIGIBLE,
    ASSESSMENT_FOLLOWUP_COLLAPSE,
    COMMAND_CENTER,
    CURRENT_VALID,
    DECLARATION_VERIFICATION_COLLAPSE,
    EXPIRED,
    EXPIRY_REVIEW_COLLAPSE,
    INCOMPLETE_VISIBLE,
    HIGH_IMPACT,
    LEGACY_COMPATIBILITY,
    LEGACY_STATUS_PRIMARY,
    MIXED_UNDEFINED,
    NOT_CURRENT,
    NOT_VERIFIED,
    PARTIAL_COMPLETENESS_RISK,
    PHASE2_TARGET_CONSUMERS,
    PORTFOLIO_SCORE,
    REMINDER_ENGINE,
    REPORT_EXPORT,
    RISK_BEARING,
    SAFE,
    SCORING_ENGINE,
    SEMANTIC_COLLAPSE_RISK,
    USES_COMBINED_MODEL,
    USES_LEGACY_STATUS_ONLY,
    WORKFLOW_OUTCOME_HARNESS,
    WIDESPREAD_COLLAPSE_DEPENDENCY,
    DECLARED_PRECEDENCE_CONTRACTS,
    SEMANTIC_STATE_PRIMARY,
    SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK,
    audit_consumer_precedence_diff,
    audit_consumer_expected_interpretation,
    audit_consumer_semantic_precedence,
    audit_semantic_state_interpretation_diff,
    audit_semantic_state_consumer,
    audit_semantic_state_consumer_batch,
)


def test_semantic_state_aware_consumer_classified_safe():
    out = audit_semantic_state_consumer(WORKFLOW_OUTCOME_HARNESS)
    assert out["semantic_state_awareness"] is True
    assert out["risk_classifications"] == [SAFE]
    assert out["non_blocking"] is True


def test_legacy_only_consumers_are_identified():
    scoring = audit_semantic_state_consumer(SCORING_ENGINE)
    reminder = audit_semantic_state_consumer(REMINDER_ENGINE)
    assert scoring["interpretation_mode"] == USES_LEGACY_STATUS_ONLY
    assert reminder["interpretation_mode"] == USES_LEGACY_STATUS_ONLY
    assert scoring["semantic_state_awareness"] is False
    assert reminder["semantic_state_awareness"] is False


def test_semantic_collapse_risks_are_surfaced():
    out = audit_semantic_state_consumer(PORTFOLIO_SCORE)
    assert out["interpretation_mode"] == USES_COMBINED_MODEL
    assert SEMANTIC_COLLAPSE_RISK in out["risk_classifications"]
    assert LEGACY_COMPATIBILITY in out["risk_classifications"]


def test_operational_and_partial_completeness_risks_surfaced_for_legacy_paths():
    out = audit_semantic_state_consumer(REMINDER_ENGINE)
    assert PARTIAL_COMPLETENESS_RISK in out["risk_classifications"]
    assert DECLARATION_VERIFICATION_COLLAPSE in out["risk_classifications"]
    assert ASSESSMENT_FOLLOWUP_COLLAPSE in out["risk_classifications"]
    assert EXPIRY_REVIEW_COLLAPSE in out["risk_classifications"]


def test_targeted_scoring_report_reminder_audits():
    score = audit_semantic_state_consumer(PORTFOLIO_SCORE)
    report = audit_semantic_state_consumer(REPORT_EXPORT)
    reminder = audit_semantic_state_consumer(REMINDER_ENGINE)
    assert score["semantic_state_awareness"] is False
    assert report["semantic_state_awareness"] is False
    assert reminder["semantic_state_awareness"] is False
    assert SEMANTIC_COLLAPSE_RISK in score["risk_classifications"]
    assert SEMANTIC_COLLAPSE_RISK in report["risk_classifications"]
    assert SEMANTIC_COLLAPSE_RISK in reminder["risk_classifications"]


def test_batch_audit_produces_consumer_interpretation_matrix_and_non_blocking():
    out = audit_semantic_state_consumer_batch([PORTFOLIO_SCORE, COMMAND_CENTER, REMINDER_ENGINE, WORKFLOW_OUTCOME_HARNESS])
    assert out["non_blocking"] is True
    matrix = out["consumer_interpretation_matrix"]
    assert len(matrix) == 4
    row = {r["consumer"]: r for r in matrix}
    assert row[WORKFLOW_OUTCOME_HARNESS]["semantic_state_aware"] is True
    assert "SAFE" in row[WORKFLOW_OUTCOME_HARNESS]["risk"]


def test_precedence_classifications_are_deterministic_for_phase2_targets():
    assert PHASE2_TARGET_CONSUMERS == (REMINDER_ENGINE, PORTFOLIO_SCORE, REPORT_EXPORT)
    rem = audit_consumer_semantic_precedence(REMINDER_ENGINE)
    score = audit_consumer_semantic_precedence(PORTFOLIO_SCORE)
    report = audit_consumer_semantic_precedence(REPORT_EXPORT)
    assert rem["precedence_model"] == LEGACY_STATUS_PRIMARY
    assert score["precedence_model"] == MIXED_UNDEFINED
    assert report["precedence_model"] == MIXED_UNDEFINED
    assert rem["non_blocking"] is True


def test_expected_interpretation_snapshots_are_generated_correctly():
    s1 = audit_consumer_expected_interpretation(PORTFOLIO_SCORE, "PARTIALLY_COMPLETE")
    s2 = audit_consumer_expected_interpretation(REPORT_EXPORT, "EXPIRY_REVIEW_REQUIRED")
    s3 = audit_consumer_expected_interpretation(REMINDER_ENGINE, "OPERATIONALLY_OPEN")
    assert s1["expected_behavior"] == INCOMPLETE_VISIBLE
    assert s2["expected_behavior"] == NOT_CURRENT
    assert s3["expected_behavior"] == ATTENTION_ELIGIBLE


def test_collapse_patterns_are_surfaced_for_unsafe_precedence():
    rem = audit_consumer_semantic_precedence(REMINDER_ENGINE)
    assert "legacy_status_checked_before_semantic_state" in rem["unsafe_precedence_patterns"]
    assert "semantic_state_ignored" in rem["unsafe_precedence_patterns"]
    snap = audit_consumer_expected_interpretation(REMINDER_ENGINE, "PARTIALLY_COMPLETE")
    assert snap["collapse_detected"] is True
    assert PARTIAL_COMPLETENESS_RISK in snap["risk"]


def test_operational_open_and_followup_states_remain_risk_bearing_in_expectations():
    r1 = audit_consumer_expected_interpretation(PORTFOLIO_SCORE, "ASSESSMENT_FOLLOWUP_REQUIRED")
    r2 = audit_consumer_expected_interpretation(PORTFOLIO_SCORE, "OPERATIONALLY_OPEN")
    assert r1["expected_behavior"] == RISK_BEARING
    assert r2["expected_behavior"] == RISK_BEARING


def test_declaration_registration_delivery_remain_distinct_from_verified_expectations():
    d = audit_consumer_expected_interpretation(REPORT_EXPORT, "DECLARATION_RECORDED")
    r = audit_consumer_expected_interpretation(REPORT_EXPORT, "REGISTRATION_RECORDED")
    t = audit_consumer_expected_interpretation(REPORT_EXPORT, "TENANT_DELIVERY_RECORDED")
    v = audit_consumer_expected_interpretation(REPORT_EXPORT, "VERIFIED_CURRENT")
    e = audit_consumer_expected_interpretation(REPORT_EXPORT, "VERIFIED_EXPIRED")
    assert d["expected_behavior"] == NOT_VERIFIED
    assert r["expected_behavior"] == NOT_VERIFIED
    assert t["expected_behavior"] == NOT_VERIFIED
    assert v["expected_behavior"] == CURRENT_VALID
    assert e["expected_behavior"] == EXPIRED


def test_partial_completeness_remains_distinct_from_current_expectation():
    p = audit_consumer_expected_interpretation(PORTFOLIO_SCORE, "PARTIALLY_COMPLETE")
    c = audit_consumer_expected_interpretation(PORTFOLIO_SCORE, "VERIFIED_CURRENT")
    assert p["expected_behavior"] == INCOMPLETE_VISIBLE
    assert c["expected_behavior"] == CURRENT_VALID
    assert p["expected_behavior"] != c["expected_behavior"]


def test_phase2_audit_interfaces_remain_non_blocking():
    p1 = audit_consumer_semantic_precedence(PORTFOLIO_SCORE)
    p2 = audit_consumer_expected_interpretation(REPORT_EXPORT, "EXPIRY_REVIEW_REQUIRED")
    assert p1["non_blocking"] is True
    assert p2["non_blocking"] is True


def test_declared_precedence_contracts_are_deterministic_for_target_consumers():
    assert DECLARED_PRECEDENCE_CONTRACTS[REMINDER_ENGINE] == SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK
    assert DECLARED_PRECEDENCE_CONTRACTS[PORTFOLIO_SCORE] == SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK
    assert DECLARED_PRECEDENCE_CONTRACTS[REPORT_EXPORT] == SEMANTIC_STATE_PRIMARY


def test_current_vs_declared_precedence_diffs_are_deterministic():
    rem = audit_consumer_precedence_diff(REMINDER_ENGINE)
    score = audit_consumer_precedence_diff(PORTFOLIO_SCORE)
    report = audit_consumer_precedence_diff(REPORT_EXPORT)
    assert rem["current_precedence"] == LEGACY_STATUS_PRIMARY
    assert rem["declared_precedence"] == SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK
    assert rem["precedence_mismatch"] is True
    assert score["precedence_mismatch"] is True
    assert report["precedence_mismatch"] is True


def test_interpretation_diff_surfaces_flattening_exposure_and_impact_levels():
    report_expiry = audit_semantic_state_interpretation_diff(REPORT_EXPORT, "EXPIRY_REVIEW_REQUIRED")
    score_partial = audit_semantic_state_interpretation_diff(PORTFOLIO_SCORE, "PARTIALLY_COMPLETE")
    rem_open = audit_semantic_state_interpretation_diff(REMINDER_ENGINE, "OPERATIONALLY_OPEN")
    assert report_expiry["collapse_detected"] is True
    assert report_expiry["impact_level"] == HIGH_IMPACT
    assert score_partial["impact_level"] == HIGH_IMPACT
    assert rem_open["impact_level"] == WIDESPREAD_COLLAPSE_DEPENDENCY


def test_operational_open_expected_risk_bearing_and_current_diff_visible():
    diff = audit_semantic_state_interpretation_diff(PORTFOLIO_SCORE, "OPERATIONALLY_OPEN")
    assert diff["expected_interpretation"] == RISK_BEARING
    assert diff["flattening_exposure_detected"] is True


def test_declaration_registration_delivery_remain_distinct_in_diffs():
    d = audit_semantic_state_interpretation_diff(REPORT_EXPORT, "DECLARATION_RECORDED")
    r = audit_semantic_state_interpretation_diff(REPORT_EXPORT, "REGISTRATION_RECORDED")
    t = audit_semantic_state_interpretation_diff(REPORT_EXPORT, "TENANT_DELIVERY_RECORDED")
    assert d["expected_interpretation"] == NOT_VERIFIED
    assert r["expected_interpretation"] == NOT_VERIFIED
    assert t["expected_interpretation"] == NOT_VERIFIED
    assert d["current_interpretation"] != d["expected_interpretation"]


def test_phase3_audit_interfaces_are_non_blocking():
    d1 = audit_consumer_precedence_diff(PORTFOLIO_SCORE)
    d2 = audit_semantic_state_interpretation_diff(REPORT_EXPORT, "PARTIALLY_COMPLETE")
    assert d1["non_blocking"] is True
    assert d2["non_blocking"] is True
