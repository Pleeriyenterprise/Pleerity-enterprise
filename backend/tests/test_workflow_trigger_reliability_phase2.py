"""Phase 2 workflow trigger reliability — evidence matrix determinism (read-only)."""

from __future__ import annotations

import json

from services.workflow_trigger_reliability_audit import (
    PHASE2_HIGH_PRIORITY_FAMILIES,
    PHASE2_OPTIONAL_FAMILIES,
    build_workflow_trigger_reliability_evidence_matrix_phase2,
    build_workflow_trigger_reliability_phase2_snapshot,
    stable_phase2_snapshot_for_tests,
)
from services.workflow_trigger_reliability_audit_phase2 import (
    CALL_PATH_READ_DERIVED,
    NO_IDEMPOTENCY_EVIDENCE,
    ORCHESTRATION_FRAGMENTED,
    RETRY_PRESENT,
    STRONG_IDEMPOTENCY_EVIDENCE,
)


def test_evidence_matrix_determinism_and_scope():
    a = build_workflow_trigger_reliability_evidence_matrix_phase2()
    b = build_workflow_trigger_reliability_evidence_matrix_phase2()
    assert a == b
    families = {r["workflow_family"] for r in a}
    assert families == set(PHASE2_HIGH_PRIORITY_FAMILIES) | set(PHASE2_OPTIONAL_FAMILIES)
    assert len(a) == len(PHASE2_HIGH_PRIORITY_FAMILIES) + len(PHASE2_OPTIONAL_FAMILIES)


def test_runtime_classification_values():
    allowed_cp = {
        "CALL_PATH_SYNCHRONOUS",
        "CALL_PATH_ASYNC",
        "CALL_PATH_PERIODIC",
        "CALL_PATH_READ_DERIVED",
        "CALL_PATH_MIXED",
        "CALL_PATH_UNKNOWN",
    }
    allowed_orch = {
        "ORCHESTRATION_DETERMINISTIC",
        "ORCHESTRATION_PARTIAL",
        "ORCHESTRATION_FRAGMENTED",
        "ORCHESTRATION_READ_REBUILD_HEAVY",
        "ORCHESTRATION_UNKNOWN",
    }
    for r in build_workflow_trigger_reliability_evidence_matrix_phase2():
        assert r["orchestration_maturity"] in allowed_orch
        for p in r["runtime_call_paths"]:
            assert p["call_path_classification"] in allowed_cp


def test_idempotency_retry_recovery_enumerations():
    allowed_idem = {
        "STRONG_IDEMPOTENCY_EVIDENCE",
        "PARTIAL_IDEMPOTENCY_EVIDENCE",
        "WEAK_IDEMPOTENCY_EVIDENCE",
        "NO_IDEMPOTENCY_EVIDENCE",
    }
    allowed_retry = {"RETRY_PRESENT", "RETRY_PARTIAL", "RETRY_UNKNOWN", "NO_RETRY_EVIDENCE"}
    allowed_rec = {"RECONCILIATION_PRESENT", "RECONCILIATION_PARTIAL", "NO_RECONCILIATION_EVIDENCE"}
    for r in build_workflow_trigger_reliability_evidence_matrix_phase2():
        assert r["idempotency_evidence_class"] in allowed_idem
        assert r["retry_evidence_class"] in allowed_retry
        assert r["reconciliation_evidence_class"] in allowed_rec


def test_command_center_read_derived_paths():
    r = next(x for x in build_workflow_trigger_reliability_evidence_matrix_phase2() if x["workflow_family"] == "COMMAND_CENTER_REFRESH")
    assert r["orchestration_maturity"] == "ORCHESTRATION_READ_REBUILD_HEAVY"
    assert all(p["call_path_classification"] == CALL_PATH_READ_DERIVED for p in r["runtime_call_paths"])


def test_notification_strong_idempotency_and_retry():
    r = next(x for x in build_workflow_trigger_reliability_evidence_matrix_phase2() if x["workflow_family"] == "NOTIFICATION_DISPATCH")
    assert r["idempotency_evidence_class"] == STRONG_IDEMPOTENCY_EVIDENCE
    assert r["retry_evidence_class"] == RETRY_PRESENT


def test_cache_invalidation_fragmented():
    r = next(x for x in build_workflow_trigger_reliability_evidence_matrix_phase2() if x["workflow_family"] == "CACHE_INVALIDATION")
    assert r["orchestration_maturity"] == ORCHESTRATION_FRAGMENTED
    assert r["idempotency_evidence_class"] == NO_IDEMPOTENCY_EVIDENCE


def test_snapshot_stability_and_audit_flags():
    s1 = stable_phase2_snapshot_for_tests()
    s2 = stable_phase2_snapshot_for_tests()
    assert s1 == s2
    assert s1["audit_only"] is True
    assert s1["non_blocking"] is True
    assert s1["runtime_behavior_changed"] is False


def test_snapshot_json_roundtrip():
    snap = stable_phase2_snapshot_for_tests()
    assert json.loads(json.dumps(snap, sort_keys=True)) == snap


def test_rollups_contain_expected_hotspots():
    snap = stable_phase2_snapshot_for_tests()
    assert "CACHE_INVALIDATION" in snap["silent_failure_hotspots"]
    assert "COMMAND_CENTER_REFRESH" in snap["unsafe_stabilization_candidates"]
    assert "REGENERATION_RECALC" in snap["safest_stabilization_candidates"]
    assert snap["cache_ownership_ambiguity_findings"]


def test_non_mutating_double_build():
    m1 = build_workflow_trigger_reliability_evidence_matrix_phase2()
    build_workflow_trigger_reliability_phase2_snapshot(generated_at="2000-01-01T00:00:00+00:00")
    m2 = build_workflow_trigger_reliability_evidence_matrix_phase2()
    assert m1 == m2
