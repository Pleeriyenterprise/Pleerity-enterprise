"""Phase 4: high-fanout transition trace propagation (observability only)."""

from __future__ import annotations

from services.compliance_recalc_queue import EnqueueComplianceRecalcResult
from services.requirement_transition_observability import (
    ENQUEUE_ACCEPTED,
    ENQUEUE_DEGRADED,
    ENQUEUE_DUPLICATE_SUPPRESSED,
    ENQUEUE_FAILED,
    ENQUEUE_PARTIAL_FAILURE,
    ENQUEUE_SKIPPED,
    attach_downstream_trigger_observation,
    build_fanout_health_summary,
    build_requirement_transition_trace,
    build_transition_enqueue_distribution,
    build_transition_fanout_operational_snapshot,
    build_transition_fanout_trace,
    classify_enqueue_outcome,
    merge_fanout_lineage_flags,
    normalize_transition_fanout_context,
)


def test_downstream_lists_share_identity_after_trace_build():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before, "status": "COMPLIANT"}
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
    assert tr["downstream_trigger_targets"] is tr["downstream_propagation"]


def test_build_transition_fanout_trace_alias_matches():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before}
    a = build_requirement_transition_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin="o",
        requirement_id="r1",
        property_id="p1",
        client_id="c1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    b = build_transition_fanout_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin="o",
        requirement_id="r1",
        property_id="p1",
        client_id="c1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    assert set(a.keys()) == set(b.keys())


def test_classify_enqueue_compliance_recalc_result():
    oc, ok, dup = classify_enqueue_outcome(
        attempted=True,
        enqueue_result=EnqueueComplianceRecalcResult(
            enqueued=True,
            correlation_id="x",
            duplicate_suppression_reason=None,
            regeneration_requeued=True,
            regeneration_error=None,
        ),
    )
    assert oc == ENQUEUE_ACCEPTED and ok is True and dup is None

    oc, ok, dup = classify_enqueue_outcome(
        attempted=True,
        enqueue_result=EnqueueComplianceRecalcResult(
            enqueued=True,
            correlation_id="x",
            duplicate_suppression_reason=None,
            regeneration_requeued=False,
            regeneration_error="regen_failed",
        ),
    )
    assert oc == ENQUEUE_PARTIAL_FAILURE and ok is True and dup == "regen_failed"

    oc, ok, dup = classify_enqueue_outcome(
        attempted=True,
        enqueue_result=EnqueueComplianceRecalcResult(
            enqueued=False,
            correlation_id="x",
            duplicate_suppression_reason="pending_duplicate",
            regeneration_requeued=False,
            regeneration_error=None,
        ),
    )
    assert oc == ENQUEUE_DUPLICATE_SUPPRESSED and ok is False and dup == "pending_duplicate"


def test_classify_enqueue_bool_and_mapping():
    assert classify_enqueue_outcome(attempted=False) == (ENQUEUE_SKIPPED, None, None)
    assert classify_enqueue_outcome(attempted=True, enqueue_result=True) == (ENQUEUE_ACCEPTED, True, None)
    assert classify_enqueue_outcome(attempted=True, enqueue_result=False, duplicate_suppression_reason="x") == (
        ENQUEUE_DUPLICATE_SUPPRESSED,
        False,
        "x",
    )
    assert classify_enqueue_outcome(attempted=True, enqueue_result={"queued": True, "merged": True}) == (
        ENQUEUE_DEGRADED,
        True,
        "risk_regen_debounce_merge",
    )
    assert classify_enqueue_outcome(attempted=True, enqueue_result={"queued": True, "merged": False}) == (
        ENQUEUE_ACCEPTED,
        True,
        None,
    )


def test_classify_enqueue_exception():
    oc, ok, dup = classify_enqueue_outcome(attempted=True, enqueue_result=None, enqueue_exc=RuntimeError("x"))
    assert oc == ENQUEUE_FAILED and ok is False and dup is None


def test_attach_downstream_extends_shared_propagation_list():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before, "status": "COMPLIANT"}
    tr = build_requirement_transition_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin="caller",
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
            }
        ],
    )
    attach_downstream_trigger_observation(
        tr,
        downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
        trigger_mode="async_queue",
        propagation_stage="post_authority_sync",
        downstream_correlation_id="c1",
        trigger_origin="caller",
        enqueue_result=EnqueueComplianceRecalcResult(
            enqueued=False,
            correlation_id="c1",
            duplicate_suppression_reason="dup",
            regeneration_requeued=False,
            regeneration_error=None,
        ),
    )
    assert len(tr["downstream_trigger_targets"]) == 2
    assert tr["downstream_trigger_targets"] is tr["downstream_propagation"]
    row = tr["downstream_trigger_targets"][-1]
    assert row["enqueue_outcome"] == ENQUEUE_DUPLICATE_SUPPRESSED
    assert row["enqueue_succeeded"] is False
    assert row["duplicate_suppression_reason"] == "dup"


def test_attach_downstream_replay_support_context_merged():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before}
    tr = build_transition_fanout_trace(
        transition_id="t-replay",
        correlation_id="c-base",
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
    attach_downstream_trigger_observation(
        tr,
        downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
        trigger_mode="async_queue",
        propagation_stage="post_authority_sync",
        downstream_correlation_id="c1",
        trigger_origin="caller",
        enqueue_result=EnqueueComplianceRecalcResult(
            enqueued=True,
            correlation_id="c-resolved",
            duplicate_suppression_reason=None,
            regeneration_requeued=False,
            regeneration_error=None,
        ),
        replay_support_context={
            "idempotency_boundary": "test-boundary",
            "enqueue_property_id": "prop-x",
            "resolved_queue_correlation_id": "corr-y",
            "replay_duplicate_enqueue_safe": True,
            "ignored_unknown_key": "should-not-appear",
        },
    )
    row = tr["downstream_trigger_targets"][-1]
    assert row["idempotency_boundary"] == "test-boundary"
    assert row["enqueue_property_id"] == "prop-x"
    assert row["resolved_queue_correlation_id"] == "corr-y"
    assert row["replay_duplicate_enqueue_safe"] is True
    assert "ignored_unknown_key" not in row


def test_merge_fanout_lineage_flags():
    tr: dict = {"replay_chain_detected": False}
    merge_fanout_lineage_flags(
        tr,
        replay_chain_detected=True,
        repeated_correlation_seen=True,
        downstream_retrigger_possible=True,
    )
    assert tr["replay_chain_detected"] is True
    assert tr["repeated_correlation_seen"] is True
    assert tr["downstream_retrigger_possible"] is True


def test_normalize_transition_fanout_context():
    n = normalize_transition_fanout_context(
        base_correlation_id="cid",
        transition_origin="o",
        requirement_id="r",
        property_id="p",
        client_id="c",
    )
    assert n["correlation_id"] == "cid" and n["transition_origin"] == "o"


def test_fanout_operational_snapshot_determinism():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before}
    t1 = build_requirement_transition_trace(
        transition_id="b",
        correlation_id="c",
        transition_origin="o",
        requirement_id="r1",
        property_id="p",
        client_id="c",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    t2 = build_requirement_transition_trace(
        transition_id="a",
        correlation_id="c",
        transition_origin="o",
        requirement_id="r2",
        property_id="p",
        client_id="c",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    attach_downstream_trigger_observation(
        t1,
        downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
        trigger_mode="async_queue",
        propagation_stage="post_authority_sync",
        enqueue_result=True,
    )
    iso = "2026-05-08T00:00:00+00:00"
    s1 = build_transition_fanout_operational_snapshot(transition_traces=[t2, t1], generated_at_iso=iso)
    s2 = build_transition_fanout_operational_snapshot(transition_traces=[t2, t1], generated_at_iso=iso)
    assert s1 == s2
    assert "fanout_health" in s1 and "enqueue_distribution" in s1
    fh = build_fanout_health_summary([t1])
    assert fh["enqueue_accepted_count"] >= 1
    dist = build_transition_enqueue_distribution([t1])
    assert "compliance_recalc_queue.enqueue_compliance_recalc" in dist["by_downstream_target"]
