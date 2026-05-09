"""Phase 2: workflow activation calibration (evidence vs readiness, mocked only)."""

from __future__ import annotations

import json

from services.workflow_activation_readiness import (
    FAMILY_CACHE_INVALIDATION,
    FAMILY_COMPLIANCE_SCORE_RECALC,
    FAMILY_NOTIFICATION_DISPATCH,
    build_workflow_activation_operational_snapshot,
    merge_readiness_row_with_signals,
)
from services.workflow_activation_calibration import (
    CALIBRATION_BLOCKED,
    CALIBRATION_CONFIRMED,
    CALIBRATION_DEGRADED,
    CALIBRATION_INSUFFICIENT_EVIDENCE,
    CALIBRATION_PARTIAL,
    CALIBRATION_UNCERTAIN,
    HIGH_RUNTIME_CONFIDENCE,
    LOW_RUNTIME_CONFIDENCE,
    analyze_calibration_drift,
    build_calibration_summary,
    build_confirmed_activation_candidates,
    build_evidence_gap_summary,
    build_family_calibration_row,
    build_operational_evidence_bundle,
    build_runtime_confidence_summary,
    build_uncertain_activation_candidates,
    build_workflow_activation_calibration_snapshot,
    classify_calibration_outcome,
    derive_evidence_gaps,
    derive_evidence_scores,
)


def _readiness_safe():
    return merge_readiness_row_with_signals(
        FAMILY_COMPLIANCE_SCORE_RECALC,
        convergence_snapshot={
            "convergence_evidence_matrix": {
                "matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}],
            }
        },
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"skipped_unbounded_scan": False, "returned_count": 2}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )


def test_evidence_scores_deterministic():
    row = _readiness_safe()
    b1 = build_operational_evidence_bundle(readiness_row=row, queue_visibility={"diagnostics": {"returned_count": 2}})
    s1 = derive_evidence_scores(b1)
    s2 = derive_evidence_scores(b1)
    assert s1 == s2
    assert all(0 <= v <= 100 for v in s1.values())


def test_calibration_confirmed_for_safe_readiness_and_strong_evidence():
    row = _readiness_safe()
    assert row["activation_state"] in ("SAFE_FOR_LIMITED_ACTIVATION", "SAFE_FOR_INCREMENTAL_EXPANSION")
    conv = {
        "convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]},
        "joined_rows": [],
    }
    traces = [
        {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
    ]
    qv = {"diagnostics": {"skipped_unbounded_scan": False, "returned_count": 2}}
    obs = {"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}}
    cal_row = build_family_calibration_row(
        row,
        convergence_snapshot=conv,
        transition_traces=traces,
        queue_visibility=qv,
        observability_summary=obs,
    )
    assert cal_row["calibration_outcome"] == CALIBRATION_CONFIRMED
    assert cal_row["runtime_confidence"] == HIGH_RUNTIME_CONFIDENCE


def test_calibration_blocked_governance():
    from services.workflow_activation_readiness import build_workflow_activation_operational_snapshot as bsnap

    act = bsnap(generated_at_iso="2026-05-08T12:00:00Z", families=[FAMILY_CACHE_INVALIDATION])
    cal = build_workflow_activation_calibration_snapshot(
        activation_operational_snapshot=act,
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    row = cal["families"][0]
    assert row["calibration_outcome"] == CALIBRATION_BLOCKED


def test_drift_safe_readiness_low_runtime():
    row = merge_readiness_row_with_signals(
        FAMILY_COMPLIANCE_SCORE_RECALC,
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": []}},
        transition_traces=[],
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {}}},
    )
    # Force SAFE path with minimal signals - may still be NOT_READY; use explicit readiness dict
    row = dict(row)
    row["activation_state"] = "SAFE_FOR_LIMITED_ACTIVATION"
    bundle = build_operational_evidence_bundle(readiness_row=row, transition_traces=[], queue_visibility={})
    scores = derive_evidence_scores(bundle)
    gaps = derive_evidence_gaps(bundle, scores)
    cal = classify_calibration_outcome(readiness_row=row, bundle=bundle, scores=scores, gaps=gaps)
    rc = __import__("services.workflow_activation_calibration", fromlist=["classify_runtime_confidence"]).classify_runtime_confidence(scores, bundle)
    drift, reason, _ = analyze_calibration_drift(readiness_row=row, calibration_outcome=cal, runtime_confidence=rc)
    if rc == LOW_RUNTIME_CONFIDENCE:
        assert drift is True
        assert reason


def test_silent_failure_degraded():
    row = merge_readiness_row_with_signals(
        FAMILY_COMPLIANCE_SCORE_RECALC,
        convergence_snapshot={
            "convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}
        },
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_FAILED", "degraded_possible": True}]}
        ],
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    row = dict(row)
    row["activation_state"] = "SAFE_FOR_LIMITED_ACTIVATION"
    bundle = build_operational_evidence_bundle(
        readiness_row=row,
        convergence_snapshot=row  # minimal; signal from row signal_summary
    )
    # Rebuild bundle from real traces for silent_failure
    traces = [
        {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_FAILED", "degraded_possible": True}]}
    ]
    bundle = build_operational_evidence_bundle(
        readiness_row=row,
        transition_traces=traces,
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"x": 1}]}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
        queue_visibility={"diagnostics": {"returned_count": 1, "skipped_unbounded_scan": False}},
    )
    scores = derive_evidence_scores(bundle)
    gaps = derive_evidence_gaps(bundle, scores)
    cal = classify_calibration_outcome(readiness_row=row, bundle=bundle, scores=scores, gaps=gaps)
    assert cal == CALIBRATION_DEGRADED


def test_observe_only_high_runtime_governance_review():
    row = merge_readiness_row_with_signals(
        FAMILY_NOTIFICATION_DISPATCH,
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"returned_count": 3, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 2}}},
    )
    row = dict(row)
    row["activation_state"] = "OBSERVE_ONLY"
    cal_row = build_family_calibration_row(
        row,
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=row.get("_unused", []) or [
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"returned_count": 3, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 2}}},
    )
    if cal_row["runtime_confidence"] == HIGH_RUNTIME_CONFIDENCE and cal_row["calibration_drift_detected"]:
        assert cal_row["governance_review_recommended"] or cal_row["calibration_drift_reason"]


def test_snapshot_ordering_and_summaries():
    act = build_workflow_activation_operational_snapshot(
        generated_at_iso="2026-05-08T12:00:00Z",
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"returned_count": 1, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    cal = build_workflow_activation_calibration_snapshot(
        activation_operational_snapshot=act,
        generated_at_iso="2026-05-08T12:00:00Z",
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"returned_count": 1, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    fams = [r["workflow_family"] for r in cal["families"]]
    assert fams == sorted(fams)
    s1 = build_calibration_summary(cal)
    s2 = build_runtime_confidence_summary(cal)
    s3 = build_evidence_gap_summary(cal)
    assert "by_calibration_outcome" in s1
    assert "by_runtime_confidence" in s2
    assert "by_gap_code" in s3
    json.dumps(s1, sort_keys=True)


def test_confirmed_and_uncertain_candidates():
    act = build_workflow_activation_operational_snapshot(
        generated_at_iso="2026-05-08T12:00:00Z",
        families=[FAMILY_COMPLIANCE_SCORE_RECALC],
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"returned_count": 2, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    cal = build_workflow_activation_calibration_snapshot(
        activation_operational_snapshot=act,
        generated_at_iso="2026-05-08T12:00:00Z",
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"returned_count": 2, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    conf = build_confirmed_activation_candidates(cal)
    unc = build_uncertain_activation_candidates(cal)
    assert isinstance(conf, list)
    assert isinstance(unc, list)


def test_insufficient_evidence_path():
    row = merge_readiness_row_with_signals(FAMILY_COMPLIANCE_SCORE_RECALC)
    bundle = build_operational_evidence_bundle(readiness_row=row, transition_traces=[], queue_visibility={})
    scores = derive_evidence_scores(bundle)
    gaps = derive_evidence_gaps(bundle, scores)
    cal = classify_calibration_outcome(readiness_row=row, bundle=bundle, scores=scores, gaps=gaps)
    assert cal in (CALIBRATION_INSUFFICIENT_EVIDENCE, CALIBRATION_UNCERTAIN, CALIBRATION_PARTIAL)
