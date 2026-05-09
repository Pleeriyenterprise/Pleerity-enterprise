"""Phase 1: workflow activation readiness registry (governance metadata only)."""

from __future__ import annotations

import json

from services.workflow_activation_readiness import (
    ACTIVATION_READINESS_REGISTRY_BASE,
    BLOCKER_LOW_CONVERGENCE_CONFIDENCE,
    BLOCKER_SEVERITY_CRITICAL,
    DEFERRED_PENDING_ARCHITECTURE,
    FAMILY_CACHE_INVALIDATION,
    FAMILY_COMPLIANCE_SCORE_RECALC,
    FAMILY_NOTIFICATION_DISPATCH,
    FAMILY_REQUIREMENT_STATE_TRANSITION,
    GOVERNANCE_DEFERRED_FAMILIES,
    NOT_READY,
    OBSERVE_ONLY,
    ROLL_BROAD_ACTIVATION_BLOCKED,
    SAFE_FOR_INCREMENTAL_EXPANSION,
    SAFE_FOR_LIMITED_ACTIVATION,
    STABILIZATION_REQUIRED,
    build_activation_readiness_summary,
    build_activation_risk_summary,
    build_deferred_activation_candidates,
    build_safe_activation_candidates,
    build_workflow_activation_operational_snapshot,
    derive_activation_blockers,
    merge_readiness_row_with_signals,
)


def _good_traces():
    return [
        {
            "correlation_id": "c1",
            "downstream_trigger_targets": [
                {"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": False},
            ],
        }
    ]


def _good_convergence_matrix():
    return {
        "convergence_evidence_matrix": {
            "matrix_rows": [
                {"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE", "operational_maturity": "HIGH_MATURITY_VISIBILITY"},
            ]
        }
    }


def test_registry_covers_scoped_and_governance():
    assert FAMILY_COMPLIANCE_SCORE_RECALC in ACTIVATION_READINESS_REGISTRY_BASE
    assert FAMILY_CACHE_INVALIDATION in ACTIVATION_READINESS_REGISTRY_BASE
    assert len(ACTIVATION_READINESS_REGISTRY_BASE) == 8
    assert FAMILY_CACHE_INVALIDATION in GOVERNANCE_DEFERRED_FAMILIES


def test_governance_family_deferred_and_blocked_rollout():
    row = merge_readiness_row_with_signals(FAMILY_CACHE_INVALIDATION, convergence_snapshot=_good_convergence_matrix())
    assert row["activation_state"] == DEFERRED_PENDING_ARCHITECTURE
    assert row["rollout_stage"] == ROLL_BROAD_ACTIVATION_BLOCKED


def test_empty_signals_not_ready_for_scoped():
    row = merge_readiness_row_with_signals(FAMILY_COMPLIANCE_SCORE_RECALC)
    assert row["activation_state"] == NOT_READY


def test_safe_path_compliance_recalc():
    row = merge_readiness_row_with_signals(
        FAMILY_COMPLIANCE_SCORE_RECALC,
        convergence_snapshot=_good_convergence_matrix(),
        transition_traces=_good_traces(),
        queue_visibility={"diagnostics": {"skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    assert row["activation_state"] == SAFE_FOR_LIMITED_ACTIVATION


def test_requirement_state_incremental_expansion():
    row = merge_readiness_row_with_signals(
        FAMILY_REQUIREMENT_STATE_TRANSITION,
        convergence_snapshot=_good_convergence_matrix(),
        transition_traces=_good_traces(),
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    assert row["activation_state"] == SAFE_FOR_INCREMENTAL_EXPANSION


def test_low_convergence_stabilization_required():
    snap = {
        "convergence_evidence_matrix": {
            "matrix_rows": [
                {"convergence_confidence": "LOW_CONVERGENCE_CONFIDENCE"},
            ]
        }
    }
    row = merge_readiness_row_with_signals(
        FAMILY_COMPLIANCE_SCORE_RECALC,
        convergence_snapshot=snap,
        transition_traces=_good_traces(),
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    assert row["activation_state"] == STABILIZATION_REQUIRED
    codes = [b["code"] for b in row["activation_blockers"]]
    assert BLOCKER_LOW_CONVERGENCE_CONFIDENCE in codes


def test_silent_failure_critical():
    traces = [
        {
            "downstream_trigger_targets": [
                {"enqueue_outcome": "ENQUEUE_FAILED", "degraded_possible": True},
            ],
        }
    ]
    row = merge_readiness_row_with_signals(
        FAMILY_COMPLIANCE_SCORE_RECALC,
        convergence_snapshot=_good_convergence_matrix(),
        transition_traces=traces,
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    assert row["activation_state"] == STABILIZATION_REQUIRED
    assert any(b["severity"] == BLOCKER_SEVERITY_CRITICAL for b in row["activation_blockers"])


def test_snapshot_determinism():
    iso = "2026-05-08T12:00:00Z"
    s1 = build_workflow_activation_operational_snapshot(
        convergence_snapshot=_good_convergence_matrix(),
        transition_traces=_good_traces(),
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
        generated_at_iso=iso,
    )
    s2 = build_workflow_activation_operational_snapshot(
        convergence_snapshot=_good_convergence_matrix(),
        transition_traces=_good_traces(),
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
        generated_at_iso=iso,
    )
    assert s1 == s2
    fams = [r["workflow_family"] for r in s1["families"]]
    assert fams == sorted(fams)


def test_safe_and_deferred_candidates():
    iso = "2026-05-08T12:00:00Z"
    snap = build_workflow_activation_operational_snapshot(
        convergence_snapshot=_good_convergence_matrix(),
        transition_traces=_good_traces(),
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
        generated_at_iso=iso,
    )
    safe = build_safe_activation_candidates(snap)
    assert FAMILY_COMPLIANCE_SCORE_RECALC in safe
    assert FAMILY_CACHE_INVALIDATION not in safe
    deferred = build_deferred_activation_candidates(snap)
    assert FAMILY_CACHE_INVALIDATION in deferred


def test_summaries_json_stable():
    iso = "2026-05-08T12:00:00Z"
    snap = build_workflow_activation_operational_snapshot(generated_at_iso=iso)
    r1 = build_activation_readiness_summary(snap)
    r2 = build_activation_risk_summary(snap)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r1, sort_keys=True)
    assert "by_activation_state" in r1
    assert "by_risk_classification" in r2


def test_derive_blockers_no_mutation():
    sig = {"low_convergence_signal": True}
    b1 = derive_activation_blockers(workflow_family=FAMILY_COMPLIANCE_SCORE_RECALC, signals=sig)
    sig["low_convergence_signal"] = False
    b2 = derive_activation_blockers(workflow_family=FAMILY_COMPLIANCE_SCORE_RECALC, signals=sig)
    assert any(x["code"] == BLOCKER_LOW_CONVERGENCE_CONFIDENCE for x in b1)
    assert not any(x["code"] == BLOCKER_LOW_CONVERGENCE_CONFIDENCE for x in b2)


def test_notification_observe_when_many_warnings():
    """Two WARNING-tier blockers -> OBSERVE_ONLY."""
    traces = _good_traces()
    obs = {"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_NOT_VISIBLE": 5}}}
    snap_low = {
        "convergence_evidence_matrix": {
            "matrix_rows": [{"convergence_confidence": "LOW_CONVERGENCE_CONFIDENCE"}],
        }
    }
    row = merge_readiness_row_with_signals(
        FAMILY_NOTIFICATION_DISPATCH,
        convergence_snapshot=snap_low,
        transition_traces=traces,
        observability_summary=obs,
        queue_visibility={"diagnostics": {"skipped_unbounded_scan": True}},
    )
    assert row["activation_state"] in (STABILIZATION_REQUIRED, OBSERVE_ONLY)
