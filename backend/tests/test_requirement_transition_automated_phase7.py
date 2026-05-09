"""Phase 7: automated outcome + generic touch + backfill observability parity (additive only)."""

from __future__ import annotations

from services.compliance_recalc_queue import EnqueueComplianceRecalcResult
from services.requirement_transition_observability import (
    TRANSITION_NOOP,
    attach_downstream_trigger_observation,
    automated_outcome_engine_traces,
    backfill_authority_traces,
    build_automated_transition_operational_snapshot,
    build_backfill_transition_operational_snapshot,
    build_generic_touch_operational_snapshot,
    build_requirement_transition_trace,
    build_system_reentry_visibility_summary,
    generic_document_touch_traces,
    merge_automated_system_lineage_flags,
    transition_origin_backfill,
    transition_origin_document_touch,
    transition_origin_outcome_engine,
)


def _minimal_before_after():
    before = {
        "status": "PENDING",
        "due_date": "d",
        "evidence_state": "X",
        "evidence_authority": {"version": 1, "state": "EA_MISSING"},
    }
    after = {**before, "status": "COMPLIANT"}
    return before, after


def test_transition_origin_families_are_distinct_prefixes():
    assert transition_origin_outcome_engine("x").startswith("OUTCOME_ENGINE_SYNC:")
    assert transition_origin_document_touch("y").startswith("DOCUMENT_TOUCH_SYNC:")
    assert transition_origin_backfill("z").startswith("BACKFILL_AUTHORITY_SYNC:")


def test_merge_automated_system_lineage_flags_additive():
    tr: dict = {"transition_id": "t1"}
    merge_automated_system_lineage_flags(
        tr,
        generic_touch_sync=True,
        automated_transition_possible=True,
        reconciliation_sync_possible=True,
        system_reentry_possible=False,
        backfill_replay_possible=True,
    )
    assert tr["generic_touch_sync"] is True
    assert tr["automated_transition_possible"] is True
    assert tr["reconciliation_sync_possible"] is True
    assert tr["system_reentry_possible"] is False
    assert tr["backfill_replay_possible"] is True


def test_attach_downstream_row_carries_automated_lineage_fields():
    before, after = _minimal_before_after()
    tr = build_requirement_transition_trace(
        transition_id="tid",
        correlation_id="cid",
        transition_origin=transition_origin_outcome_engine("test"),
        requirement_id="r1",
        property_id="p1",
        client_id="c1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    merge_automated_system_lineage_flags(tr, automated_transition_possible=True, generic_touch_sync=False)
    attach_downstream_trigger_observation(
        tr,
        downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
        trigger_mode="async_queue",
        propagation_stage="test_stage",
        downstream_correlation_id="down-cid",
        enqueue_result=EnqueueComplianceRecalcResult(
            enqueued=True,
            correlation_id="down-cid",
            duplicate_suppression_reason=None,
            regeneration_requeued=False,
            regeneration_error=None,
        ),
    )
    row = (tr.get("downstream_trigger_targets") or [])[0]
    assert row.get("automated_transition_possible") is True
    assert row.get("generic_touch_sync") is False
    assert "enqueue_outcome" in row
    assert row.get("downstream_correlation_id") == "down-cid"


def test_automated_snapshot_filters_and_sorts():
    traces = [
        {
            "requirement_id": "b",
            "transition_id": "t2",
            "transition_origin": transition_origin_document_touch("x"),
        },
        {
            "requirement_id": "a",
            "transition_id": "t1",
            "transition_origin": transition_origin_outcome_engine("y"),
        },
    ]
    auto = automated_outcome_engine_traces(traces)
    assert len(auto) == 1
    assert auto[0]["requirement_id"] == "a"
    snap = build_automated_transition_operational_snapshot(
        transition_traces=traces,
        generated_at_iso="2026-05-08T00:00:00Z",
    )
    assert snap["schema_version"] == "automated_transition_operational_snapshot_v1"
    assert len(snap["transition_traces"]) == 1
    assert snap["transition_traces"][0]["requirement_id"] == "a"


def test_generic_touch_snapshot_and_noise_indicators():
    traces = [
        {
            "requirement_id": "r1",
            "transition_id": "t1",
            "transition_origin": transition_origin_document_touch("admin_reject"),
            "transition_outcome": TRANSITION_NOOP,
        },
    ]
    assert len(generic_document_touch_traces(traces)) == 1
    g = build_generic_touch_operational_snapshot(
        transition_traces=traces,
        generated_at_iso="2026-05-08T00:00:00Z",
    )
    assert g["generic_touch_trace_count"] == 1
    assert g["generic_touch_noise_indicators"]["noop_transition_count"] == 1


def test_backfill_snapshot_schema():
    traces = [
        {
            "requirement_id": "r9",
            "transition_id": "t9",
            "transition_origin": transition_origin_backfill("batch:abc"),
            "backfill_replay_possible": True,
            "replay_possible": True,
        },
    ]
    assert len(backfill_authority_traces(traces)) == 1
    b = build_backfill_transition_operational_snapshot(
        transition_traces=traces,
        generated_at_iso="2026-05-08T00:00:00Z",
    )
    assert b["schema_version"] == "backfill_transition_operational_snapshot_v1"
    assert b["backfill_replay_visibility"]["backfill_replay_marked_count"] == 1


def test_system_reentry_visibility_summary_counts():
    tr = {
        "system_reentry_possible": True,
        "automated_transition_possible": True,
        "downstream_trigger_targets": [
            {"enqueue_outcome": "ENQUEUE_DUPLICATE_SUPPRESSED", "degraded_possible": False},
            {"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True},
        ],
    }
    s = build_system_reentry_visibility_summary([tr])
    assert s["system_reentry_possible_count"] == 1
    assert s["downstream_duplicate_enqueue_row_count"] == 1
    assert s["downstream_degraded_row_count"] == 1


def test_backward_compat_trace_without_automated_flags():
    before, after = _minimal_before_after()
    tr = build_requirement_transition_trace(
        transition_id="tid",
        correlation_id="cid",
        transition_origin="routes.documents:legacy",
        requirement_id="r1",
        property_id="p1",
        client_id="c1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    assert "automated_transition_possible" not in tr
    snap = build_automated_transition_operational_snapshot(
        transition_traces=[tr],
        generated_at_iso="2026-05-08T00:00:00Z",
    )
    assert snap["automated_sync_trace_count"] == 0
