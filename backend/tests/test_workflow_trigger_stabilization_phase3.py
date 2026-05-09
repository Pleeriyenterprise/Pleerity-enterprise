"""Phase 3 workflow trigger stabilization planning — matrix and snapshot determinism (planning-only)."""

from __future__ import annotations

import json

from services.workflow_trigger_reliability_audit import (
    PHASE2_HIGH_PRIORITY_FAMILIES,
    PHASE2_OPTIONAL_FAMILIES,
    build_workflow_trigger_stabilization_matrix_phase3,
    build_workflow_trigger_stabilization_phase3_snapshot,
    stable_phase3_snapshot_for_tests,
)
from services.workflow_trigger_stabilization_planning import (
    ARCHITECTURE_REDESIGN_REQUIRED,
    CACHE_BOUNDARY_UNDEFINED,
    CACHE_GOVERNANCE_REQUIRED,
    DEFER_UNTIL_ARCHITECTURE_REVIEW,
    DEGRADED_STATE_VISIBILITY,
    DO_NOT_IMPLEMENT_YET,
    EVENT_MODEL_REQUIRED,
    HARD_BLOCKER,
    IDEMPOTENCY_HARDENING,
    INSUFFICIENT_RUNTIME_EVIDENCE,
    MIXED_SYNC_ASYNC_CHAIN,
    NON_BLOCKING,
    NOT_SAFE_TO_MODIFY,
    OBSERVABILITY_HARDENING,
    OBSERVATION_ONLY,
    OBSERVE_ONLY,
    P0_CRITICAL_RUNTIME_RISK,
    P1_HIGH_TRUST_SURFACE,
    P2_HIGH_DUPLICATE_RISK,
    P3_HIGH_STALE_STATE_RISK,
    P4_OBSERVABILITY_GAP,
    P5_LOW_RISK_ALIGNMENT,
    P6_OBSERVE_ONLY,
    PARTIAL_PROPAGATION_RISK,
    QUEUE_PATTERN_ALIGNMENT,
    READY_FOR_STABILIZATION,
    READY_WITH_GOVERNANCE_REVIEW,
    REFERENCE_STABILIZATION_PATTERNS,
    REQUIRES_ARCHITECTURE_DECISION,
    REQUIRES_CACHE_OWNERSHIP,
    REQUIRES_EVENT_MODEL,
    REQUIRES_IDEMPOTENCY_FIRST,
    REQUIRES_OBSERVABILITY_FIRST,
    RETRY_RECOVERY_HARDENING,
    SAFE_ENGINEERING_STABILIZATION,
    SAFE_FOR_INCREMENTAL_STABILIZATION,
    SAFE_FOR_OBSERVABILITY_ONLY,
    SAFE_FOR_READ_PATH_IMPROVEMENT,
    SOFT_BLOCKER,
    UNSAFE_FOR_AUTOMATION_EXPANSION,
    UNSAFE_FOR_RUNTIME_ENFORCEMENT,
)


_TRACKS = frozenset(
    {
        SAFE_ENGINEERING_STABILIZATION,
        QUEUE_PATTERN_ALIGNMENT,
        IDEMPOTENCY_HARDENING,
        RETRY_RECOVERY_HARDENING,
        OBSERVABILITY_HARDENING,
        DEGRADED_STATE_VISIBILITY,
        CACHE_GOVERNANCE_REQUIRED,
        ARCHITECTURE_REDESIGN_REQUIRED,
        EVENT_MODEL_REQUIRED,
        DO_NOT_IMPLEMENT_YET,
        OBSERVE_ONLY,
    }
)

_READINESS = frozenset(
    {
        READY_FOR_STABILIZATION,
        READY_WITH_GOVERNANCE_REVIEW,
        REQUIRES_ARCHITECTURE_DECISION,
        REQUIRES_EVENT_MODEL,
        REQUIRES_CACHE_OWNERSHIP,
        REQUIRES_OBSERVABILITY_FIRST,
        REQUIRES_IDEMPOTENCY_FIRST,
        NOT_SAFE_TO_MODIFY,
        INSUFFICIENT_RUNTIME_EVIDENCE,
    }
)

_URGENCY = frozenset(
    {
        P0_CRITICAL_RUNTIME_RISK,
        P1_HIGH_TRUST_SURFACE,
        P2_HIGH_DUPLICATE_RISK,
        P3_HIGH_STALE_STATE_RISK,
        P4_OBSERVABILITY_GAP,
        P5_LOW_RISK_ALIGNMENT,
        P6_OBSERVE_ONLY,
    }
)

_BLOCKER_TAGS = frozenset(
    {
        "NO_SINGLE_OWNER",
        "FRAGMENTED_REFRESH_MODEL",
        "READ_REBUILD_HEAVY",
        "CACHE_BOUNDARY_UNDEFINED",
        "NO_RETRY_CONTRACT",
        "NO_RECONCILIATION_CONTRACT",
        "NO_DEGRADED_STATE_SIGNALING",
        "MIXED_SYNC_ASYNC_CHAIN",
        "PARTIAL_PROPAGATION_RISK",
        "SILENT_FAILURE_EXPOSURE",
    }
)

_BLOCKER_SEVERITIES = frozenset({HARD_BLOCKER, SOFT_BLOCKER, OBSERVATION_ONLY, NON_BLOCKING})

_ROLLOUT = frozenset(
    {
        SAFE_FOR_INCREMENTAL_STABILIZATION,
        SAFE_FOR_OBSERVABILITY_ONLY,
        SAFE_FOR_READ_PATH_IMPROVEMENT,
        UNSAFE_FOR_RUNTIME_ENFORCEMENT,
        UNSAFE_FOR_AUTOMATION_EXPANSION,
        DEFER_UNTIL_ARCHITECTURE_REVIEW,
    }
)


def test_matrix_determinism_and_scope():
    a = build_workflow_trigger_stabilization_matrix_phase3()
    b = build_workflow_trigger_stabilization_matrix_phase3()
    assert a == b
    families = {r["workflow_family"] for r in a}
    assert families == set(PHASE2_HIGH_PRIORITY_FAMILIES) | set(PHASE2_OPTIONAL_FAMILIES)


def test_stabilization_track_and_readiness_rollout_urgency():
    for r in build_workflow_trigger_stabilization_matrix_phase3():
        assert r["stabilization_track"] in _TRACKS
        assert r["implementation_readiness"] in _READINESS
        assert r["urgency_class"] in _URGENCY
        assert r["rollout_safety_posture"] in _ROLLOUT
        for b in r["architecture_blockers"]:
            assert b["blocker"] in _BLOCKER_TAGS
            assert b["severity"] in _BLOCKER_SEVERITIES
        assert r["blocker_severity_summary"] in _BLOCKER_SEVERITIES


def test_blocker_derivation_cache_and_requirement():
    rows = {r["workflow_family"]: r for r in build_workflow_trigger_stabilization_matrix_phase3()}
    cache_blockers = {b["blocker"] for b in rows["CACHE_INVALIDATION"]["architecture_blockers"]}
    assert CACHE_BOUNDARY_UNDEFINED in cache_blockers
    req_blockers = {b["blocker"] for b in rows["REQUIREMENT_STATE_TRANSITION"]["architecture_blockers"]}
    assert MIXED_SYNC_ASYNC_CHAIN in req_blockers
    assert PARTIAL_PROPAGATION_RISK in req_blockers


def test_sequencing_determinism():
    m = build_workflow_trigger_stabilization_matrix_phase3()
    seq = [r["workflow_family"] for r in sorted(m, key=lambda x: (x["recommended_stabilization_order"], x["workflow_family"]))]
    assert seq[0] == "COMPLIANCE_SCORE_RECALC"
    assert seq[1] == "REGENERATION_RECALC"
    assert seq[-1] == "CACHE_INVALIDATION"
    snap = stable_phase3_snapshot_for_tests()
    assert snap["recommended_stabilization_sequencing"] == seq


def test_snapshot_audit_only_guarantees():
    s1 = stable_phase3_snapshot_for_tests()
    s2 = stable_phase3_snapshot_for_tests()
    assert s1 == s2
    assert s1["audit_only"] is True
    assert s1["non_blocking"] is True
    assert s1["runtime_behavior_changed"] is False


def test_snapshot_json_roundtrip():
    snap = stable_phase3_snapshot_for_tests()
    assert json.loads(json.dumps(snap, sort_keys=True)) == snap


def test_reference_patterns_keys_and_reusability():
    assert set(REFERENCE_STABILIZATION_PATTERNS) == {"COMPLIANCE_SCORE_RECALC", "REGENERATION_RECALC", "NOTIFICATION_DISPATCH"}
    for _k, v in REFERENCE_STABILIZATION_PATTERNS.items():
        assert v["reusability"] in ("reusable", "partially_reusable", "unsafe_to_generalize")


def test_rollups_trust_surfaces_and_unsafe_automation():
    snap = stable_phase3_snapshot_for_tests()
    assert "COMMAND_CENTER_REFRESH" in snap["observability_first_candidates"]
    assert "TODAY_TASK_REBUILD" in snap["observability_first_candidates"]
    assert "PORTFOLIO_SUMMARY_REFRESH" in snap["observability_first_candidates"]
    for f in ("COMMAND_CENTER_REFRESH", "TODAY_TASK_REBUILD", "PORTFOLIO_SUMMARY_REFRESH", "CACHE_INVALIDATION"):
        assert f in snap["unsafe_for_automation_expansion_families"]
    assert "COMPLIANCE_SCORE_RECALC" in snap["safest_stabilization_candidates"]
    assert "REGENERATION_RECALC" in snap["safest_stabilization_candidates"]
    assert snap["highest_risk_workflow_families"][0] == "CACHE_INVALIDATION"
    assert "CACHE_INVALIDATION" in snap["architecture_redesign_candidates"]
    assert set(snap["queue_reference_pattern_candidates"]) >= {"COMPLIANCE_SCORE_RECALC", "REGENERATION_RECALC", "NOTIFICATION_DISPATCH"}
    assert "REQUIREMENT_STATE_TRANSITION" in snap["idempotency_hardening_candidates"]
    assert set(snap["degraded_state_visibility_candidates"]) == {"COMMAND_CENTER_REFRESH", "TODAY_TASK_REBUILD"}


def test_non_mutating_double_build():
    m1 = build_workflow_trigger_stabilization_matrix_phase3()
    build_workflow_trigger_stabilization_phase3_snapshot(generated_at="2000-01-01T00:00:00+00:00")
    m2 = build_workflow_trigger_stabilization_matrix_phase3()
    assert m1 == m2
