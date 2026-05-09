"""Phase 1: workflow runtime convergence audit (propagation + reconciliation evidence)."""

from __future__ import annotations

from services.requirement_transition_observability import (
    TRANSITION_APPLIED,
    TRANSITION_DEGRADED_DOWNSTREAM,
    TRANSITION_NOOP,
    TRANSITION_PARTIAL_PROPAGATION,
    TRANSITION_PENDING_RECONCILIATION,
    build_requirement_transition_trace,
    transition_origin_outcome_engine,
)
from services.workflow_runtime_convergence_observability import (
    HIGH_CONVERGENCE_CONFIDENCE,
    LOW_CONVERGENCE_CONFIDENCE,
    MODERATE_CONVERGENCE_CONFIDENCE,
    PROPAGATION_DEGRADED,
    PROPAGATION_PARTIAL,
    PROPAGATION_PENDING,
    PROPAGATION_RECONCILIATION_REQUIRED,
    PROPAGATION_RETRYING,
    PROPAGATION_SETTLED,
    PROPAGATION_STALE_VISIBLE,
    PROPAGATION_UNKNOWN,
    RECONCILIATION_OBSERVED,
    RECONCILIATION_PENDING,
    RECONCILIATION_UNKNOWN,
    UNKNOWN_CONVERGENCE_CONFIDENCE,
    build_convergence_evidence_matrix,
    build_propagation_completion_summary,
    build_reconciliation_visibility_summary,
    build_runtime_convergence_snapshot,
    build_stale_state_recovery_summary,
    classify_convergence_confidence,
    classify_propagation_completion_from_recalc_queue_job,
    classify_propagation_completion_from_transition_trace,
    classify_reconciliation_evidence_from_transition_trace,
    detect_runtime_convergence_hotspots,
    trace_to_convergence_matrix_row,
)


def _base_req():
    return {
        "status": "PENDING",
        "due_date": "d",
        "evidence_state": "X",
        "evidence_authority": {"version": 1, "state": "EA_MISSING"},
    }


def test_classify_propagation_settled_applied_no_downstream():
    before, after = _base_req(), {**_base_req(), "status": "COMPLIANT"}
    tr = build_requirement_transition_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin=transition_origin_outcome_engine("x"),
        requirement_id="r1",
        property_id="p1",
        client_id="cl1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[
            {
                "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
                "trigger_mode": "sync",
                "enqueue_succeeded": True,
                "propagation_degraded_possible": False,
                "reconciliation_recommended": False,
            }
        ],
    )
    assert classify_propagation_completion_from_transition_trace(tr) == PROPAGATION_SETTLED


def test_classify_propagation_degraded():
    before, after = _base_req(), _base_req()
    tr = build_requirement_transition_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin="test",
        requirement_id="r1",
        property_id="p1",
        client_id="cl1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    tr["transition_outcome"] = TRANSITION_DEGRADED_DOWNSTREAM
    assert classify_propagation_completion_from_transition_trace(tr) == PROPAGATION_DEGRADED


def test_classify_propagation_reconciliation_required():
    before, after = _base_req(), _base_req()
    tr = build_requirement_transition_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin="test",
        requirement_id="r1",
        property_id="p1",
        client_id="cl1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=["e1"],
        gap_exception=None,
        downstream_propagation=[],
    )
    tr["transition_outcome"] = TRANSITION_PENDING_RECONCILIATION
    assert classify_propagation_completion_from_transition_trace(tr) == PROPAGATION_RECONCILIATION_REQUIRED


def test_reconciliation_evidence_pending():
    before, after = _base_req(), _base_req()
    tr = build_requirement_transition_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin="test",
        requirement_id="r1",
        property_id="p1",
        client_id="cl1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=["e"],
        gap_exception=None,
        downstream_propagation=[
            {
                "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
                "propagation_degraded_possible": True,
            }
        ],
    )
    tr["transition_outcome"] = TRANSITION_PENDING_RECONCILIATION
    assert classify_reconciliation_evidence_from_transition_trace(tr) == RECONCILIATION_PENDING


def test_convergence_confidence_mapping():
    assert classify_convergence_confidence(PROPAGATION_SETTLED, RECONCILIATION_OBSERVED) == HIGH_CONVERGENCE_CONFIDENCE
    assert classify_convergence_confidence(PROPAGATION_PENDING, RECONCILIATION_OBSERVED) == MODERATE_CONVERGENCE_CONFIDENCE
    assert classify_convergence_confidence(PROPAGATION_DEGRADED, RECONCILIATION_OBSERVED) == LOW_CONVERGENCE_CONFIDENCE
    assert classify_convergence_confidence(PROPAGATION_UNKNOWN, RECONCILIATION_UNKNOWN) == UNKNOWN_CONVERGENCE_CONFIDENCE


def test_recalc_queue_job_classification():
    assert classify_propagation_completion_from_recalc_queue_job({"status": "DONE"}) == PROPAGATION_SETTLED
    assert classify_propagation_completion_from_recalc_queue_job({"status": "FAILED"}) == PROPAGATION_RETRYING
    assert classify_propagation_completion_from_recalc_queue_job({"status": "DEAD"}) == PROPAGATION_DEGRADED


def test_matrix_determinism_and_strongest_weakest():
    rows = [
        trace_to_convergence_matrix_row(
            {
                "transition_origin": transition_origin_outcome_engine("a"),
                "transition_outcome": TRANSITION_APPLIED,
                "requirement_id": "b",
                "correlation_id": "c2",
                "downstream_propagation": [
                    {
                        "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
                        "propagation_degraded_possible": False,
                    }
                ],
                "downstream_trigger_targets": [],
                "partial_downstream_failure": False,
            }
        ),
        trace_to_convergence_matrix_row(
            {
                "transition_origin": transition_origin_outcome_engine("a"),
                "transition_outcome": TRANSITION_APPLIED,
                "requirement_id": "a",
                "correlation_id": "c1",
                "downstream_propagation": [
                    {
                        "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
                        "propagation_degraded_possible": False,
                    }
                ],
                "downstream_trigger_targets": [],
                "partial_downstream_failure": False,
            }
        ),
    ]
    m1 = build_convergence_evidence_matrix(matrix_rows=rows)
    m2 = build_convergence_evidence_matrix(matrix_rows=list(reversed(rows)))
    assert m1["matrix_rows"] == m2["matrix_rows"]
    assert "automated_outcome_authority" in m1["strongest_settlement_families"]


def test_hotspots_partial_family():
    row = trace_to_convergence_matrix_row(
        {
            "transition_origin": "routes.admin:test",
            "transition_outcome": TRANSITION_PARTIAL_PROPAGATION,
            "requirement_id": "r1",
            "correlation_id": "x",
            "downstream_propagation": [],
            "downstream_trigger_targets": [],
            "partial_downstream_failure": True,
        }
    )
    h = detect_runtime_convergence_hotspots([row])
    assert "admin_mutation:r1" in h["partial_propagation_persistence"]


def test_runtime_snapshot_backward_compat_empty():
    snap = build_runtime_convergence_snapshot(
        transition_traces=[],
        generated_at_iso="2026-05-08T12:00:00Z",
        recalc_queue_jobs=None,
    )
    assert snap["propagation_completion"]["by_propagation_completion"] == {}
    assert snap["convergence_evidence_matrix"]["matrix_rows"] == []


def test_propagation_and_reconciliation_summaries():
    traces = [
        {
            "transition_outcome": TRANSITION_APPLIED,
            "transition_origin": transition_origin_outcome_engine("z"),
            "downstream_propagation": [
                {
                    "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
                    "propagation_degraded_possible": False,
                }
            ],
            "downstream_trigger_targets": [],
            "partial_downstream_failure": False,
        },
        {
            "transition_outcome": TRANSITION_NOOP,
            "stale_transition_replayed": True,
            "transition_origin": "routes.documents:x",
            "downstream_propagation": [],
            "downstream_trigger_targets": [],
        },
    ]
    ps = build_propagation_completion_summary(traces)
    assert ps["settled_count"] >= 1
    assert ps["by_propagation_completion"].get(PROPAGATION_STALE_VISIBLE, 0) >= 1
    rs = build_reconciliation_visibility_summary(traces)
    assert isinstance(rs["by_reconciliation_evidence"], dict)
    ss = build_stale_state_recovery_summary(traces)
    assert ss["stale_surface_trace_count"] >= 1
