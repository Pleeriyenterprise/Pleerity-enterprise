"""Phase 5: document-path transition fanout (observability completion)."""

from __future__ import annotations

from services.requirement_transition_observability import (
    attach_downstream_trigger_observation,
    build_document_replay_visibility_summary,
    build_document_transition_health_summary,
    build_document_transition_operational_snapshot,
    build_requirement_transition_trace,
    document_path_transition_traces,
    merge_document_path_lineage_flags,
)
from routes.documents import _document_verification_replay_heuristic


def test_merge_document_path_lineage_flags():
    tr: dict = {"correlation_id": "c1", "transition_id": "t1"}
    merge_document_path_lineage_flags(
        tr,
        document_id="d1",
        document_replacement_detected=True,
        verification_replay_possible=True,
        revert_retrigger_possible=False,
        stale_document_transition_possible=True,
    )
    assert tr["document_id"] == "d1"
    assert tr["document_replacement_detected"] is True
    assert tr["verification_replay_possible"] is True
    assert tr["revert_retrigger_possible"] is False


def test_document_path_transition_traces_filter():
    a = {"document_id": "x", "transition_origin": "other"}
    b = {"transition_origin": "routes.documents.verify_document"}
    c = {"transition_origin": "routes.properties.patch_requirement"}
    assert len(document_path_transition_traces([a, b, c])) == 2


def test_downstream_row_carries_document_lineage_snapshot():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before, "status": "COMPLIANT"}
    tr = build_requirement_transition_trace(
        transition_id="t1",
        correlation_id="c1",
        transition_origin="routes.documents.verify_document",
        requirement_id="r1",
        property_id="p1",
        client_id="cl1",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    merge_document_path_lineage_flags(
        tr,
        document_id="doc-1",
        verification_replay_possible=True,
        stale_document_transition_possible=True,
    )
    attach_downstream_trigger_observation(
        tr,
        downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
        trigger_mode="async_queue",
        propagation_stage="post_verify",
        trigger_origin="routes.documents.verify_document",
        enqueue_result=True,
    )
    row = (tr.get("downstream_trigger_targets") or [])[-1]
    assert row.get("document_id") == "doc-1"
    assert row.get("verification_replay_possible") is True
    assert row.get("stale_document_transition_possible") is True


def test_document_operational_snapshot_determinism():
    before = {"status": "PENDING", "due_date": "d", "evidence_state": "X", "evidence_authority": {"version": 1, "state": "EA_MISSING"}}
    after = {**before}
    t = build_requirement_transition_trace(
        transition_id="b",
        correlation_id="c",
        transition_origin="routes.documents.delete_document",
        requirement_id="r1",
        property_id="p",
        client_id="c",
        before_requirement=before,
        after_requirement=after,
        gap_errors=[],
        gap_exception=None,
        downstream_propagation=[],
    )
    merge_document_path_lineage_flags(t, document_id="d9", revert_retrigger_possible=True)
    iso = "2026-05-08T12:00:00+00:00"
    s1 = build_document_transition_operational_snapshot(transition_traces=[t], generated_at_iso=iso)
    s2 = build_document_transition_operational_snapshot(transition_traces=[t], generated_at_iso=iso)
    assert s1 == s2
    assert s1["schema_version"] == "document_transition_operational_snapshot_v1"
    h = build_document_transition_health_summary([t])
    assert h["document_trace_count"] == 1
    rv = build_document_replay_visibility_summary([t])
    assert rv["revert_retrigger_possible_count"] == 1


def test_verification_replay_heuristic():
    assert _document_verification_replay_heuristic("VERIFIED") is True
    assert _document_verification_replay_heuristic("UPLOADED") is False
