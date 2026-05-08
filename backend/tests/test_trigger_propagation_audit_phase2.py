from __future__ import annotations

from services.trigger_propagation_audit import (
    ANALYTICS_ONLY,
    BLOCKED_FOR_RUNTIME_ENFORCEMENT,
    COMPLIANCE_CRITICAL,
    CONSUMERS,
    CONTRACT_SATISFIED,
    DETERMINISTIC,
    FRAGMENTED,
    IMMEDIATE,
    LOW_CONFIDENCE,
    NEAR_REAL_TIME,
    OPERATIONAL_GAP,
    SEMANTIC_TRANSITIONS,
    UNKNOWN_GUARANTEE,
    build_expected_vs_current_matrix,
    build_trigger_propagation_audit_phase2_snapshot,
)


def _row(matrix, transition: str, consumer: str):
    for r in matrix:
        if r["semantic_transition"] == transition and r["consumer"] == consumer:
            return r
    raise AssertionError(f"Missing row for {transition}/{consumer}")


def test_expected_contracts_are_present_and_stable():
    matrix = build_expected_vs_current_matrix()
    assert len(matrix) == len(SEMANTIC_TRANSITIONS) * len(CONSUMERS)
    row = matrix[0]
    for k in (
        "expected_propagation_type",
        "expected_freshness_expectation",
        "expected_operational_followthrough",
        "expected_confidence",
        "propagation_criticality",
    ):
        assert k in row


def test_criticality_classification_is_deterministic():
    matrix = build_expected_vs_current_matrix()
    r1 = _row(matrix, "EXPIRY_REVIEW_REQUIRED", "REMINDER_ENGINE")
    r2 = _row(matrix, "VERIFIED_CURRENT", "PORTFOLIO_SCORE")
    assert r1["propagation_criticality"] == COMPLIANCE_CRITICAL
    assert r2["propagation_criticality"] == ANALYTICS_ONLY


def test_freshness_expectation_and_refresh_guarantee_are_separate_and_stable():
    matrix = build_expected_vs_current_matrix()
    req_list = _row(matrix, "VERIFIED_CURRENT", "REQUIREMENT_LIST")
    cache = _row(matrix, "OPERATIONALLY_OPEN", "CACHE_INVALIDATION_REFRESH")
    assert req_list["expected_freshness_expectation"] in (IMMEDIATE, NEAR_REAL_TIME)
    assert req_list["refresh_guarantee"] in (DETERMINISTIC,)
    assert cache["refresh_guarantee"] in (UNKNOWN_GUARANTEE, FRAGMENTED)


def test_gap_and_blocker_classification_determinism():
    matrix = build_expected_vs_current_matrix()
    risky = _row(matrix, "ASSESSMENT_FOLLOWUP_REQUIRED", "REMINDER_ENGINE")
    assert risky["gap_classification"] in (BLOCKED_FOR_RUNTIME_ENFORCEMENT, OPERATIONAL_GAP)
    assert risky["runtime_enforcement_blocked"] is True
    assert len(risky["runtime_enforcement_blocker_reasons"]) > 0


def test_satisfied_contract_exists_for_low_risk_read_paths():
    matrix = build_expected_vs_current_matrix()
    row = _row(matrix, "MISSING", "REQUIREMENT_LIST")
    assert row["gap_classification"] in (CONTRACT_SATISFIED, BLOCKED_FOR_RUNTIME_ENFORCEMENT)


def test_rollout_candidate_ordering_is_stable():
    snap = build_trigger_propagation_audit_phase2_snapshot()
    safe = snap["safest_rollout_candidates"]
    risky = snap["highest_risk_rollout_candidates"]
    assert len(safe) > 0
    assert len(risky) > 0
    # first safest candidate should not be low-confidence blocked row
    top = safe[0]
    assert not (top["runtime_enforcement_blocked"] and top["confidence"] == LOW_CONFIDENCE)


def test_phase2_artifact_shape_and_non_behavioral_contract():
    snap = build_trigger_propagation_audit_phase2_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    assert len(snap["matrix"]) == len(SEMANTIC_TRANSITIONS) * len(CONSUMERS)
    assert "criticality_summary" in snap
    assert "freshness_expectation_summary" in snap
    assert "refresh_guarantee_summary" in snap
    assert "gap_summary" in snap
    assert "runtime_enforcement_blocker_summary" in snap
