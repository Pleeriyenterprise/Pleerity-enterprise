from __future__ import annotations

from services.trigger_propagation_audit import (
    CONSUMERS,
    SEMANTIC_TRANSITIONS,
    FRAGMENTED_PROPAGATION,
    LOW_CONFIDENCE,
    NO_KNOWN_PROPAGATION,
    PARTIAL_PROPAGATION,
    UNKNOWN_CONFIDENCE,
    build_grouped_summary,
    build_refresh_dependency_summary,
    build_semantic_without_operational_followthrough,
    build_trigger_propagation_audit_snapshot,
    build_trigger_propagation_matrix,
)


def _row(matrix, transition: str, consumer: str):
    for r in matrix:
        if r["semantic_transition"] == transition and r["consumer"] == consumer:
            return r
    raise AssertionError(f"Missing row for {transition}/{consumer}")


def test_matrix_is_deterministic_and_complete_shape():
    matrix = build_trigger_propagation_matrix()
    assert len(matrix) == len(SEMANTIC_TRANSITIONS) * len(CONSUMERS)
    sample = matrix[0]
    for k in (
        "semantic_transition",
        "consumer",
        "propagation_type",
        "confidence",
        "reaction_source_of_truth",
        "trigger_source",
        "known_gaps",
        "operational_followthrough",
        "refresh_recalc_dependency",
    ):
        assert k in sample


def test_classification_determinism_for_known_weak_paths():
    matrix = build_trigger_propagation_matrix()
    row = _row(matrix, "EXPIRY_REVIEW_REQUIRED", "REMINDER_ENGINE")
    assert row["propagation_type"] in (PARTIAL_PROPAGATION, FRAGMENTED_PROPAGATION)
    assert row["confidence"] == LOW_CONFIDENCE
    assert row["reaction_source_of_truth"] in ("LIVE_READ_PROJECTION", "PERIODIC_JOB")

    cache_row = _row(matrix, "OPERATIONALLY_OPEN", "CACHE_INVALIDATION_REFRESH")
    assert cache_row["propagation_type"] == NO_KNOWN_PROPAGATION
    assert cache_row["confidence"] == UNKNOWN_CONFIDENCE
    assert cache_row["reaction_source_of_truth"] == "UNKNOWN"


def test_source_of_truth_classification_present_for_every_row():
    matrix = build_trigger_propagation_matrix()
    allowed = {
        "AUTHORITY_WRITE",
        "LIVE_READ_PROJECTION",
        "SCHEDULED_RECALC",
        "TASK_REBUILD",
        "SCORE_REGENERATION",
        "UI_DERIVATION",
        "PERIODIC_JOB",
        "MANUAL_REFRESH",
        "UNKNOWN",
    }
    assert all(r["reaction_source_of_truth"] in allowed for r in matrix)


def test_grouped_summary_stability():
    matrix = build_trigger_propagation_matrix()
    grouped = build_grouped_summary(matrix)
    assert len(grouped) == len(matrix)
    g = grouped[0]
    assert set(g.keys()) == {
        "semantic_transition",
        "consumer",
        "propagation",
        "confidence",
        "reaction_source_of_truth",
        "gap_risk",
    }


def test_semantic_without_operational_followthrough_findings_present():
    matrix = build_trigger_propagation_matrix()
    findings = build_semantic_without_operational_followthrough(matrix)
    assert any(r["semantic_transition"] == "ASSESSMENT_FOLLOWUP_REQUIRED" for r in findings)
    assert any(r["semantic_transition"] == "EXPIRY_REVIEW_REQUIRED" for r in findings)
    assert all(r["operational_followthrough"] is False for r in findings)


def test_refresh_dependency_summary_is_stable():
    matrix = build_trigger_propagation_matrix()
    summary = build_refresh_dependency_summary(matrix)
    assert isinstance(summary, dict)
    assert len(summary) > 0
    assert sum(summary.values()) == len(matrix)


def test_snapshot_generation_is_deterministic_and_audit_only():
    snap = build_trigger_propagation_audit_snapshot()
    assert snap["runtime_behavior_changed"] is False
    assert snap["audit_only"] is True
    assert snap["non_blocking"] is True
    assert len(snap["matrix"]) == len(SEMANTIC_TRANSITIONS) * len(CONSUMERS)
    assert len(snap["grouped_summary"]) == len(snap["matrix"])


def test_no_runtime_behavior_change_side_effect_contract():
    snap = build_trigger_propagation_audit_snapshot()
    # Contract marker for this phase: visibility only.
    assert snap["runtime_behavior_changed"] is False
    # Ensure weak paths are surfaced, not hidden.
    weak = snap["weakest_or_missing_paths"]
    assert any(r["propagation_type"] in (FRAGMENTED_PROPAGATION, NO_KNOWN_PROPAGATION) for r in weak)
    assert any(r["confidence"] in (LOW_CONFIDENCE, UNKNOWN_CONFIDENCE) for r in weak)
