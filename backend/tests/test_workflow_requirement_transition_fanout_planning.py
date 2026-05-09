"""Planning-only: Requirement-State Transition fanout metadata (no activation / no DB)."""

from __future__ import annotations

import json
from unittest.mock import patch

import services.workflow_requirement_transition_fanout_planning as fp

FIXED_ISO = "2026-05-09T12:00:00Z"


def test_surface_keys_sorted_and_complete():
    keys = fp.FANOUT_PLANNING_SURFACE_KEYS
    assert keys == tuple(sorted(keys))
    assert len(keys) == 12


def test_activation_sequencing_matches_spec_advisory():
    seq = fp.build_activation_sequencing_planning_snapshot(generated_at_iso=FIXED_ISO)
    assert seq["phase_2a_surfaces"] == list(fp.PHASE_2A_SURFACES)
    assert seq["phase_2b_surfaces"] == list(fp.PHASE_2B_SURFACES)
    assert seq["phase_2c_surfaces"] == list(fp.PHASE_2C_SURFACES)
    assert seq["deferred_surfaces"] == list(fp.DEFERRED_FANOUT_SURFACES)
    assert seq["sequencing_advisory_only"] is True


def test_participation_postures_expected():
    assert fp._PARTICIPATION_BY_SURFACE[fp.SURFACE_NOTIFICATIONS] == fp.FANOUT_PARTICIPANT_BLOCKED
    assert fp._PARTICIPATION_BY_SURFACE[fp.SURFACE_CACHE_INVALIDATION] == fp.FANOUT_PARTICIPANT_BLOCKED
    assert fp._PARTICIPATION_BY_SURFACE[fp.SURFACE_COMMAND_CENTER] == fp.FANOUT_PARTICIPANT_DEFERRED
    assert fp._PARTICIPATION_BY_SURFACE[fp.SURFACE_REMINDERS] == fp.FANOUT_PARTICIPANT_OBSERVE_ONLY


def test_convergence_expectation_classification():
    assert fp._CONVERGENCE_EXPECTATION_BY_SURFACE[fp.SURFACE_COMPLIANCE_RECALC] == fp.CONVERGENCE_REQUIRED
    assert fp._CONVERGENCE_EXPECTATION_BY_SURFACE[fp.SURFACE_REPORTING] == fp.CONVERGENCE_OBSERVE_ONLY
    assert fp._CONVERGENCE_EXPECTATION_BY_SURFACE[fp.SURFACE_NOTIFICATIONS] == fp.CONVERGENCE_BLOCKED


def test_rollback_posture_classification():
    assert fp._ROLLBACK_POSTURE_BY_SURFACE[fp.SURFACE_AUTHORITY_SYNC] == fp.ROLLBACK_CONTROLLED
    assert fp._ROLLBACK_POSTURE_BY_SURFACE[fp.SURFACE_NOTIFICATIONS] == fp.ROLLBACK_UNSAFE_FOR_PHASE2


def test_observability_readiness_classification():
    for s in fp.FANOUT_PLANNING_SURFACE_KEYS:
        p = fp._PARTICIPATION_BY_SURFACE[s]
        r = fp._derive_risk_band(s, p)
        o = fp._derive_observability_readiness(s, p, r)
        assert o in (fp.OBSERVABILITY_READY, fp.OBSERVABILITY_PARTIAL, fp.OBSERVABILITY_INSUFFICIENT)


def test_highest_risk_ordering_critical_blocked_surfaces_first_alpha():
    part = fp.build_fanout_participation_planning_snapshot(generated_at_iso=FIXED_ISO)
    hi = fp.highest_risk_propagation_surfaces(part)
    assert hi[0] == fp.SURFACE_CACHE_INVALIDATION
    assert hi[1] == fp.SURFACE_NOTIFICATIONS
    assert set(hi[:2]) == {fp.SURFACE_CACHE_INVALIDATION, fp.SURFACE_NOTIFICATIONS}


def test_safest_activation_candidates_sorted_low_risk_then_alpha():
    part = fp.build_fanout_participation_planning_snapshot(generated_at_iso=FIXED_ISO)
    safe = fp.safest_future_activation_candidates(part)
    assert safe[0] == fp.SURFACE_AUTHORITY_SYNC
    assert fp.SURFACE_NOTIFICATIONS not in safe


def test_bundle_snapshot_determinism():
    b1 = fp.build_requirement_transition_fanout_planning_bundle(generated_at_iso=FIXED_ISO)
    b2 = fp.build_requirement_transition_fanout_planning_bundle(generated_at_iso=FIXED_ISO)
    assert b1 == b2
    j1 = json.dumps(b1, sort_keys=True)
    j2 = json.dumps(b2, sort_keys=True)
    assert j1 == j2


def test_summarize_stable():
    b = fp.build_requirement_transition_fanout_planning_bundle(generated_at_iso=FIXED_ISO)
    assert fp.summarize_planning_bundle(b) == fp.summarize_planning_bundle(b)


def test_backward_compatibility_bundle_keys():
    b = fp.build_requirement_transition_fanout_planning_bundle(generated_at_iso=FIXED_ISO)
    required = {
        "activation_sequencing",
        "convergence_expectations",
        "fanout_participation",
        "fanout_risk",
        "highest_risk_propagation_surfaces",
        "observability_readiness",
        "planning_schema_version",
        "propagation_boundaries",
        "rollback_posture",
        "safest_future_activation_candidates",
        "schema_version",
    }
    assert required <= set(b.keys())


def test_propagation_boundary_chain_keys_sorted():
    snap = fp.build_propagation_boundary_planning_snapshot(generated_at_iso=FIXED_ISO)
    keys = [c["key"] for c in snap["boundary_chains"]]
    assert keys == sorted(keys)


def test_mocked_override_participation_only_affects_derived_fields():
    with patch.dict(fp._PARTICIPATION_BY_SURFACE, {fp.SURFACE_REMINDERS: fp.FANOUT_PARTICIPANT_BLOCKED}, clear=False):
        assert fp._derive_risk_band(fp.SURFACE_REMINDERS, fp.FANOUT_PARTICIPANT_BLOCKED) == fp.FANOUT_RISK_CRITICAL
        part = fp.build_fanout_participation_planning_snapshot(generated_at_iso=FIXED_ISO)
        row = next(r for r in part["surfaces"] if r["surface"] == fp.SURFACE_REMINDERS)
        assert row["fanout_risk_band"] == fp.FANOUT_RISK_CRITICAL
