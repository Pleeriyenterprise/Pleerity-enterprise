"""Requirement-state transition observability (correlation, trace, snapshots)."""

from __future__ import annotations

from services.requirement_transition_observability import (
    TRANSITION_APPLIED,
    TRANSITION_DEGRADED_DOWNSTREAM,
    TRANSITION_NOOP,
    TRANSITION_PARTIAL_PROPAGATION,
    TRANSITION_PENDING_RECONCILIATION,
    build_requirement_transition_operational_snapshot,
    build_requirement_transition_trace,
    build_transition_health_summary,
    build_transition_reconciliation_markers,
    classify_transition_outcome,
    ensure_requirement_transition_correlation_id,
    merge_pre_authority_optimistic_requirement_promotion_marker,
    normalize_requirement_transition_context,
)


def test_ensure_correlation_explicit():
    c = ensure_requirement_transition_correlation_id(
        requirement_id="r1", property_id="p1", client_id="c1", correlation_id="  x  "
    )
    assert c == "x"


def test_ensure_correlation_generates():
    c = ensure_requirement_transition_correlation_id(
        requirement_id="r1", property_id="p1", client_id="c1", correlation_id=None
    )
    assert "r1" in c and "p1" in c


def test_normalize_context():
    n = normalize_requirement_transition_context(
        correlation_id="z",
        transition_origin="doc_upload",
        requirement_id="r1",
        property_id="p1",
        client_id="c1",
    )
    assert n["correlation_id"] == "z"
    assert n["transition_origin"] == "doc_upload"


def test_classify_outcomes():
    before = ("PENDING", "d1", "MISSING", 1, "EA_MISSING")
    after_same = {"status": "PENDING", "due_date": "d1", "evidence_state": "MISSING", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    assert classify_transition_outcome(
        before_sig=before,
        after_requirement=after_same,
        gap_errors=[],
        gap_exception=None,
    ) == TRANSITION_NOOP
    assert (
        classify_transition_outcome(
            before_sig=before,
            after_requirement=after_same,
            gap_errors=[{"e": 1}],
            gap_exception=None,
        )
        == TRANSITION_PENDING_RECONCILIATION
    )
    after_changed = {**after_same, "status": "COMPLIANT"}
    assert (
        classify_transition_outcome(
            before_sig=before,
            after_requirement=after_changed,
            gap_errors=[{"e": 1}],
            gap_exception=None,
        )
        == TRANSITION_PARTIAL_PROPAGATION
    )
    assert (
        classify_transition_outcome(
            before_sig=before,
            after_requirement=after_changed,
            gap_errors=[],
            gap_exception=None,
        )
        == TRANSITION_APPLIED
    )
    assert (
        classify_transition_outcome(
            before_sig=before,
            after_requirement=after_changed,
            gap_errors=[],
            gap_exception=RuntimeError("x"),
        )
        == TRANSITION_DEGRADED_DOWNSTREAM
    )


def test_build_trace_and_snapshots():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before, "status": "COMPLIANT", "semantic_state": None, "state_reason": None}
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
        downstream_propagation=[
            {
                "downstream_target": "gap",
                "trigger_mode": "sync",
                "enqueue_attempted": True,
                "enqueue_succeeded": True,
                "propagation_degraded_possible": False,
                "reconciliation_recommended": False,
            }
        ],
    )
    assert tr["transition_outcome"] == TRANSITION_APPLIED
    snap = build_requirement_transition_operational_snapshot(
        transition_traces=[tr],
        generated_at_iso="2020-01-01T00:00:00+00:00",
    )
    snap2 = build_requirement_transition_operational_snapshot(
        transition_traces=[tr],
        generated_at_iso="2020-01-01T00:00:00+00:00",
    )
    assert snap == snap2
    h = build_transition_health_summary([tr])
    assert h["health_posture"] == "NON_BLOCKING_OBSERVABILITY_ONLY"
    m = build_transition_reconciliation_markers(
        [{**tr, "transition_outcome": TRANSITION_PENDING_RECONCILIATION}]
    )
    assert m["markers"]


def test_merge_pre_authority_optimistic_requirement_promotion_marker():
    trace: dict = {}
    merge_pre_authority_optimistic_requirement_promotion_marker(
        trace,
        applied=True,
        basis="TEST_BASIS",
        transition_origin="test.origin",
        requirement_id="r1",
    )
    block = trace.get("pre_authority_optimistic_requirement_promotion") or {}
    assert block.get("applied") is True
    assert block.get("basis") == "TEST_BASIS"
    assert block.get("requirement_id") == "r1"
    assert block.get("authority_reconciliation_expected") is True
