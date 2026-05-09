"""Phase 1 workflow trigger reliability audit — deterministic read-only catalog."""

from __future__ import annotations

import json

from services.workflow_trigger_reliability_audit import (
    BLACK_BOX_BEHAVIOR,
    FRAGMENTED_TRIGGER_CHAIN,
    HIGH_RELIABILITY,
    IDEMPOTENT,
    NO_KNOWN_RECOVERY,
    POTENTIAL_DUPLICATE_TRIGGER,
    RECOVERY_READY,
    TRIGGER_DIRECT_SYNCHRONOUS,
    TRIGGER_PERIODIC,
    build_workflow_trigger_reliability_matrix,
    build_workflow_trigger_reliability_phase1_snapshot,
    stable_snapshot_for_tests,
)


def _matrix_family(family: str):
    m = build_workflow_trigger_reliability_matrix()
    for r in m:
        if r["workflow_family"] == family:
            return r
    raise AssertionError(family)


def test_matrix_row_count_and_determinism():
    a = build_workflow_trigger_reliability_matrix()
    b = build_workflow_trigger_reliability_matrix()
    assert a == b
    assert len(a) == 18
    keys = {
        "workflow_family",
        "trigger_source",
        "trigger_activation_type",
        "downstream_consumers",
        "orchestration_path",
        "refresh_model",
        "operational_owner",
        "propagation_failure_flags",
        "idempotency_posture",
        "recovery_posture",
        "observability_posture",
        "reliability_class",
        "stale_state_exposure",
        "orphan_risk_exposure",
        "duplicate_trigger_exposure",
        "runtime_activation_confidence",
        "operational_maturity_level",
    }
    for r in a:
        assert set(r.keys()) == keys


def test_idempotency_recovery_observability_classifications_are_valid():
    allowed_idem = {"IDEMPOTENT", "PARTIALLY_IDEMPOTENT", "NON_IDEMPOTENT", "UNKNOWN_IDEMPOTENCY"}
    allowed_rec = {"RECOVERY_READY", "PARTIAL_RECOVERY", "MANUAL_RECOVERY_HEAVY", "NO_KNOWN_RECOVERY", "UNKNOWN_RECOVERY"}
    allowed_obs = {"FULL_OBSERVABILITY", "PARTIAL_OBSERVABILITY", "LIMITED_OBSERVABILITY", "BLACK_BOX_BEHAVIOR"}
    for r in build_workflow_trigger_reliability_matrix():
        assert r["idempotency_posture"] in allowed_idem
        assert r["recovery_posture"] in allowed_rec
        assert r["observability_posture"] in allowed_obs


def test_report_generation_high_reliability_and_idempotent():
    r = _matrix_family("REPORT_GENERATION")
    assert r["reliability_class"] == HIGH_RELIABILITY
    assert r["idempotency_posture"] == IDEMPOTENT
    assert r["recovery_posture"] == RECOVERY_READY


def test_cache_invalidation_weakest_recovery_and_black_box():
    r = _matrix_family("CACHE_INVALIDATION")
    assert r["recovery_posture"] == NO_KNOWN_RECOVERY
    assert r["observability_posture"] == BLACK_BOX_BEHAVIOR


def test_reminder_trigger_periodic():
    r = _matrix_family("REMINDER_TRIGGER")
    assert r["trigger_activation_type"] == TRIGGER_PERIODIC


def test_document_upload_synchronous_model():
    r = _matrix_family("DOCUMENT_UPLOAD")
    assert r["trigger_activation_type"] == TRIGGER_DIRECT_SYNCHRONOUS


def test_strongest_families_include_high_reliability_catalog():
    snap = stable_snapshot_for_tests()
    assert "REPORT_GENERATION" in snap["strongest_workflow_families"]


def test_snapshot_stability_without_generated_at():
    s1 = stable_snapshot_for_tests()
    s2 = stable_snapshot_for_tests()
    assert s1 == s2
    assert s1["audit_only"] is True
    assert s1["non_blocking"] is True
    assert s1["runtime_behavior_changed"] is False
    assert "workflow_reliability_matrix" in s1
    assert len(s1["unsafe_activation_candidates"]) >= 1


def test_snapshot_json_roundtrip():
    snap = stable_snapshot_for_tests()
    dumped = json.dumps(snap, sort_keys=True)
    loaded = json.loads(dumped)
    assert loaded == snap


def test_duplicate_trigger_hotspots_include_document_upload():
    snap = stable_snapshot_for_tests()
    assert "DOCUMENT_UPLOAD" in snap["duplicate_trigger_hotspots"]


def test_orchestration_fragmentation_flags_command_center():
    snap = stable_snapshot_for_tests()
    frag = snap["orchestration_fragmentation_findings"]
    assert any("COMMAND_CENTER_REFRESH" in x for x in frag)


def test_non_blocking_no_side_effects_on_matrix():
    snap = build_workflow_trigger_reliability_phase1_snapshot()
    assert snap["non_blocking"] is True
    m1 = build_workflow_trigger_reliability_matrix()
    m2 = build_workflow_trigger_reliability_matrix()
    assert m1 == m2


def test_fragmented_chain_implies_fragmented_or_flags():
    r = _matrix_family("REQUIREMENT_STATE_TRANSITION")
    assert FRAGMENTED_TRIGGER_CHAIN in r["propagation_failure_flags"] or r["trigger_activation_type"].startswith(
        "TRIGGER_FRAGMENTED"
    )
