"""Phase 6: admin + evidence review authority mutation fanout parity."""

from __future__ import annotations

from services.requirement_transition_observability import (
    attach_downstream_trigger_observation,
    build_admin_transition_operational_snapshot,
    build_requirement_transition_trace,
    build_review_reentry_visibility_summary,
    build_review_transition_operational_snapshot,
    merge_review_admin_lineage_flags,
    review_transition_traces,
    admin_transition_traces,
)


def test_merge_review_admin_lineage_flags():
    tr: dict = {"correlation_id": "c1", "transition_id": "t1"}
    merge_review_admin_lineage_flags(
        tr,
        review_id="rev-1",
        admin_override_possible=True,
        review_reversal_possible=False,
        reviewer_retrigger_possible=True,
        reassignment_replay_possible=True,
        review_chain_reentry_detected=True,
        authority_override_replay_possible=True,
    )
    assert tr["review_id"] == "rev-1"
    assert tr["admin_override_possible"] is True
    assert tr["review_chain_reentry_detected"] is True


def test_review_and_admin_trace_filters():
    r = {"transition_origin": "routes.evidence_review.start_evidence_review"}
    a = {"transition_origin": "routes.admin.admin_link_document_requirement"}
    o = {"transition_origin": "routes.properties.patch_requirement"}
    assert len(review_transition_traces([r, a, o])) == 1
    assert len(admin_transition_traces([r, a, o])) == 1


def test_downstream_row_review_admin_snapshots():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before, "status": "COMPLIANT"}
    tr = build_requirement_transition_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin="routes.evidence_review.reject_evidence_review",
        requirement_id="r1",
        property_id="p1",
        client_id="cl1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    merge_review_admin_lineage_flags(tr, review_id="rid-a", review_chain_reentry_detected=True, admin_override_possible=True)
    attach_downstream_trigger_observation(
        tr,
        downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
        trigger_mode="async_queue",
        propagation_stage="post_review",
        trigger_origin="routes.evidence_review.reject_evidence_review",
        enqueue_result=True,
    )
    row = (tr.get("downstream_trigger_targets") or [])[-1]
    assert row.get("review_chain_reentry_detected") is True
    assert row.get("review_id") == "rid-a"

    iso = "2026-05-08T00:00:00+00:00"
    rs = build_review_transition_operational_snapshot(transition_traces=[tr], generated_at_iso=iso)
    assert rs["schema_version"] == "review_transition_operational_snapshot_v1"
    adm = build_admin_transition_operational_snapshot(
        transition_traces=[
            {
                **build_requirement_transition_trace(
                    transition_id="ta",
                    correlation_id="ca",
                    transition_origin="routes.admin.admin_resolve_evidence_match",
                    requirement_id="r2",
                    property_id="p",
                    client_id="c",
                    before_requirement=before,
                    after_requirement=after,
                    gap_errors=[],
                    gap_exception=None,
                    downstream_propagation=[],
                )
            }
        ],
        generated_at_iso=iso,
    )
    assert adm["schema_version"] == "admin_transition_operational_snapshot_v1"
    rv = build_review_reentry_visibility_summary([tr])
    assert rv["review_chain_reentry_trace_count"] >= 1


def test_review_snapshot_determinism():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before}
    tr = build_requirement_transition_trace(
        transition_id="b",
        correlation_id="c",
        transition_origin="routes.evidence_review.verify_external",
        requirement_id="r1",
        property_id="p",
        client_id="c",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    iso = "2026-05-08T12:00:00+00:00"
    s1 = build_review_transition_operational_snapshot(transition_traces=[tr], generated_at_iso=iso)
    s2 = build_review_transition_operational_snapshot(transition_traces=[tr], generated_at_iso=iso)
    assert s1 == s2
