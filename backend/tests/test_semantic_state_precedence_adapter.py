from __future__ import annotations

from services.semantic_state_precedence_adapter import (
    BEHAVIORALLY_SIGNIFICANT_DELTA,
    HIGH_DELTA,
    HYBRID_AUDIT_INTERPRETATION,
    LEGACY_RUNTIME_INTERPRETATION,
    NO_DELTA,
    SEMANTIC_AWARE_INTERPRETATION,
    SEMANTIC_STATE_ADAPTER_AUDIT_MODE,
    SEMANTIC_STATE_RUNTIME_ENFORCEMENT,
    WIDESPREAD_COLLAPSE_DELTA,
    adapt_portfolio_score_semantic_interpretation,
    adapt_reminder_semantic_interpretation,
    adapt_report_export_semantic_interpretation,
    build_semantic_adapter_snapshot,
    classify_delta_impact,
)


def test_adapter_controls_are_audit_only_by_default():
    assert SEMANTIC_STATE_ADAPTER_AUDIT_MODE is True
    assert SEMANTIC_STATE_RUNTIME_ENFORCEMENT is False


def test_adapters_preserve_legacy_runtime_output_by_default():
    out = adapt_report_export_semantic_interpretation("EXPIRY_REVIEW_REQUIRED")
    assert out["mode"] == LEGACY_RUNTIME_INTERPRETATION
    assert out["runtime_selected_interpretation"] == out["legacy_interpretation"]
    assert out["non_blocking"] is True


def test_semantic_aware_interpretation_is_generated_deterministically():
    out = adapt_portfolio_score_semantic_interpretation("PARTIALLY_COMPLETE", mode=SEMANTIC_AWARE_INTERPRETATION)
    assert out["semantic_interpretation"] == "INCOMPLETE_VISIBLE"
    assert out["legacy_interpretation"] in ("PENDING_LIKE", "CURRENT_LIKE")
    # still audit-only in phase 4
    assert out["runtime_selected_interpretation"] == out["legacy_interpretation"]


def test_delta_detection_and_impact_classification_work():
    out = adapt_report_export_semantic_interpretation("EXPIRY_REVIEW_REQUIRED", mode=HYBRID_AUDIT_INTERPRETATION)
    assert out["delta_detected"] is True
    assert out["delta_impact"] == "HIGH_IMPACT"
    assert out["delta_classification"] == HIGH_DELTA


def test_operational_open_states_produce_visible_deltas():
    out = adapt_reminder_semantic_interpretation("OPERATIONALLY_OPEN", mode=HYBRID_AUDIT_INTERPRETATION)
    assert out["delta_detected"] is True
    assert out["delta_classification"] == WIDESPREAD_COLLAPSE_DELTA


def test_declaration_registration_delivery_states_remain_distinct():
    d = adapt_report_export_semantic_interpretation("DECLARATION_RECORDED", mode=HYBRID_AUDIT_INTERPRETATION)
    r = adapt_report_export_semantic_interpretation("REGISTRATION_RECORDED", mode=HYBRID_AUDIT_INTERPRETATION)
    t = adapt_report_export_semantic_interpretation("TENANT_DELIVERY_RECORDED", mode=HYBRID_AUDIT_INTERPRETATION)
    assert d["semantic_interpretation"] == "NOT_VERIFIED"
    assert r["semantic_interpretation"] == "NOT_VERIFIED"
    assert t["semantic_interpretation"] == "NOT_VERIFIED"


def test_classify_delta_impact_is_deterministic():
    assert classify_delta_impact({"delta_detected": False, "delta_impact": "HIGH_IMPACT"}) == NO_DELTA
    assert classify_delta_impact({"delta_detected": True, "delta_impact": "HIGH_IMPACT"}) == HIGH_DELTA
    assert classify_delta_impact({"delta_detected": True, "delta_impact": "MEDIUM_IMPACT"}) == BEHAVIORALLY_SIGNIFICANT_DELTA


def test_snapshot_matrix_is_generated_and_non_blocking():
    snap = build_semantic_adapter_snapshot()
    assert snap["non_blocking"] is True
    assert snap["audit_mode"] is True
    assert snap["runtime_enforcement"] is False
    assert len(snap["matrix"]) >= 3
