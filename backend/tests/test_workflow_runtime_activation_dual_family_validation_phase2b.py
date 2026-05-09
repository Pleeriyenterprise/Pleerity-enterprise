"""Phase 2B: dual-family staging evidence validation (mocked; no DB)."""

from __future__ import annotations

import json
from unittest.mock import patch

import services.workflow_runtime_activation_registry as reg
from services.compliance_recalc_queue import EnqueueComplianceRecalcResult
from services.workflow_activation_governance_report import build_workflow_activation_governance_report
from services.workflow_activation_readiness import FAMILY_COMPLIANCE_SCORE_RECALC, FAMILY_REGENERATION_RECALC
from services.workflow_runtime_convergence_observability import build_runtime_convergence_snapshot
from services.workflow_runtime_activation_dual_family_validation import (
    DUAL_FAMILY_STAGING_CONFIRMED,
    DUAL_FAMILY_STAGING_OBSERVE_ONLY,
    DUAL_FAMILY_STAGING_PARTIAL,
    build_dual_family_staging_validation_snapshot,
    build_dual_family_staging_validation_from_evidence_pack,
    validate_dual_family_downstream_coexistence,
    validate_dual_family_gate_alignment,
)
from services.workflow_runtime_activation_evidence_pack import build_runtime_activation_evidence_pack
from services.workflow_runtime_activation_registry import (
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
    resolve_compliance_recalc_activation_gate,
    resolve_regeneration_recalc_activation_gate,
)


def _gov_kw():
    return dict(
        generated_at_iso="2026-05-12T10:00:00Z",
        convergence_snapshot={
            "convergence_evidence_matrix": {
                "matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE", "workflow_family": "REQ"}],
            },
            "joined_rows": [],
        },
        transition_traces=[
            {
                "correlation_id": "c1",
                "downstream_trigger_targets": [
                    {
                        "activation_family": FAMILY_COMPLIANCE_SCORE_RECALC,
                        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
                        "activation_guard_result": "GUARD_RESULT_PERMITTED",
                        "activation_reason": "x",
                        "activation_scope": "compliance_recalc_enqueue_only",
                        "activation_state": ACTIVATION_LIMITED,
                        "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                        "enqueue_outcome": "ENQUEUE_ACCEPTED",
                    },
                    {
                        "activation_family": FAMILY_REGENERATION_RECALC,
                        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
                        "activation_guard_result": "GUARD_RESULT_PERMITTED",
                        "activation_reason": "y",
                        "activation_scope": "risk_signal_regen_enqueue_only",
                        "activation_state": ACTIVATION_LIMITED,
                        "downstream_target": "risk_signal_regen_queue.enqueue_risk_signal_regen",
                        "enqueue_outcome": "ENQUEUE_DEGRADED",
                    },
                ],
                "transition_id": "t1",
            }
        ],
        queue_visibility={"diagnostics": {"returned_count": 2, "skipped_unbounded_scan": False}},
        observability_summary={
            "reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}
        },
    )


def _compliance_enqueue_sample():
    g = resolve_compliance_recalc_activation_gate()
    return {
        "enqueue": {
            "activation_family": g["activation_family"],
            "activation_governance_version": g["activation_governance_version"],
            "activation_guard_result": g["activation_guard_result"],
            "activation_reason": g["activation_reason"],
            "activation_scope": g["activation_scope"],
            "activation_skipped": False,
            "activation_state": g["activation_state"],
            "correlation_id": "cid-dual",
            "enqueued": True,
            "regeneration_error": None,
            "regeneration_requeued": True,
        },
        "gate": g,
    }


def _regen_enqueue_sample():
    g = resolve_regeneration_recalc_activation_gate()
    return {
        "enqueue": {
            "activation_family": g["activation_family"],
            "activation_governance_version": g["activation_governance_version"],
            "activation_guard_result": g["activation_guard_result"],
            "activation_reason": g["activation_reason"],
            "activation_scope": g["activation_scope"],
            "activation_skipped": False,
            "activation_state": g["activation_state"],
            "merged": False,
            "property_id": "p-dual",
            "queued": True,
        },
        "gate": g,
    }


def test_dual_family_snapshot_determinism():
    gov = build_workflow_activation_governance_report(**_gov_kw())
    traces = list(_gov_kw()["transition_traces"])
    conv = build_runtime_convergence_snapshot(transition_traces=traces, generated_at_iso="2026-05-12T10:00:00Z")
    cg = resolve_compliance_recalc_activation_gate()
    rg = resolve_regeneration_recalc_activation_gate()
    er = EnqueueComplianceRecalcResult(
        enqueued=True,
        correlation_id="cid-dual",
        activation_skipped=False,
        activation_state=cg["activation_state"],
        activation_reason=cg["activation_reason"],
        activation_scope=cg["activation_scope"],
        activation_family=cg["activation_family"],
        activation_guard_result=cg["activation_guard_result"],
        activation_governance_version=cg["activation_governance_version"],
        regeneration_requeued=True,
        regeneration_error=None,
    )
    regen_body = dict(_regen_enqueue_sample()["enqueue"])
    kw = dict(
        generated_at_iso="2026-05-12T10:00:00Z",
        governance_report=gov,
        convergence_snapshot=conv,
        transition_traces=traces,
        compliance_enqueue_samples=[(cg, er)],
        regeneration_enqueue_samples=[(rg, regen_body)],
    )
    s1 = build_dual_family_staging_validation_snapshot(**kw)
    s2 = build_dual_family_staging_validation_snapshot(**kw)
    assert json.dumps(s1, sort_keys=True, default=str) == json.dumps(s2, sort_keys=True, default=str)


def test_gate_alignment_and_downstream_coexistence():
    gov = build_workflow_activation_governance_report(**_gov_kw())
    traces = list(_gov_kw()["transition_traces"])
    conv = build_runtime_convergence_snapshot(transition_traces=traces, generated_at_iso="2026-05-12T10:00:00Z")
    snap = build_dual_family_staging_validation_snapshot(
        generated_at_iso="2026-05-12T10:00:00Z",
        governance_report=gov,
        convergence_snapshot=conv,
        transition_traces=traces,
    )
    ga = snap["dual_family_gate_alignment"]
    assert ga["activation_validation"] == "VALIDATION_CONFIRMED"
    cx = snap["dual_family_downstream_coexistence"]
    assert cx["has_recalc_downstream"] and cx["has_regen_downstream"]


def test_staging_readiness_confirmed_strong_inputs():
    gov = build_workflow_activation_governance_report(**_gov_kw())
    traces = list(_gov_kw()["transition_traces"])
    conv = build_runtime_convergence_snapshot(transition_traces=traces, generated_at_iso="2026-05-12T10:00:00Z")
    cg = resolve_compliance_recalc_activation_gate()
    rg = resolve_regeneration_recalc_activation_gate()
    er = EnqueueComplianceRecalcResult(
        enqueued=True,
        correlation_id="cid-dual",
        activation_skipped=False,
        activation_state=cg["activation_state"],
        activation_reason=cg["activation_reason"],
        activation_scope=cg["activation_scope"],
        activation_family=cg["activation_family"],
        activation_guard_result=cg["activation_guard_result"],
        activation_governance_version=cg["activation_governance_version"],
        regeneration_requeued=True,
        regeneration_error=None,
    )
    regen_body = dict(_regen_enqueue_sample()["enqueue"])
    snap = build_dual_family_staging_validation_snapshot(
        generated_at_iso="2026-05-12T10:00:00Z",
        governance_report=gov,
        convergence_snapshot=conv,
        transition_traces=traces,
        compliance_enqueue_samples=[(cg, er)],
        regeneration_enqueue_samples=[(rg, regen_body)],
    )
    assert snap["dual_family_staging_readiness_classification"] == DUAL_FAMILY_STAGING_CONFIRMED


def test_staging_readiness_observe_only_registry_patch():
    gov = build_workflow_activation_governance_report(**_gov_kw())
    traces = list(_gov_kw()["transition_traces"])
    conv = build_runtime_convergence_snapshot(transition_traces=traces, generated_at_iso="2026-05-12T10:00:00Z")
    with patch.dict(
        reg._REGISTRY_CEILING,
        {FAMILY_COMPLIANCE_SCORE_RECALC: ACTIVATION_OBSERVE_ONLY, FAMILY_REGENERATION_RECALC: ACTIVATION_OBSERVE_ONLY},
        clear=False,
    ):
        snap = build_dual_family_staging_validation_snapshot(
            generated_at_iso="2026-05-12T10:00:00Z",
            governance_report=gov,
            convergence_snapshot=conv,
            transition_traces=traces,
        )
    assert snap["dual_family_staging_readiness_classification"] == DUAL_FAMILY_STAGING_OBSERVE_ONLY


def test_evidence_pack_dual_family_bridge():
    pack = build_runtime_activation_evidence_pack(
        generated_at="2026-05-12T11:00:00Z",
        governance_families=(FAMILY_COMPLIANCE_SCORE_RECALC, FAMILY_REGENERATION_RECALC),
        transition_traces=_gov_kw()["transition_traces"],
        representative_enqueue_samples=[_compliance_enqueue_sample()],
        representative_regeneration_enqueue_samples=[_regen_enqueue_sample()],
    )
    gov = build_workflow_activation_governance_report(**_gov_kw())
    traces = list(_gov_kw()["transition_traces"])
    conv = pack["convergence_evidence_snapshot"]
    dual = build_dual_family_staging_validation_from_evidence_pack(
        pack,
        governance_report_full=gov,
        convergence_snapshot=conv,
        transition_traces=traces,
    )
    assert "combined_activation_rollback_summary" in dual
    assert dual["dual_family_staging_readiness_classification"] in (
        DUAL_FAMILY_STAGING_CONFIRMED,
        DUAL_FAMILY_STAGING_PARTIAL,
    )


def test_downstream_coexistence_partial_single_surface():
    d = validate_dual_family_downstream_coexistence(
        transition_traces=[
            {
                "downstream_trigger_targets": [
                    {"downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc"},
                ],
            }
        ],
    )
    assert d["activation_validation"] == "VALIDATION_PARTIAL"


def test_gate_alignment_detects_missing_row():
    vs = {
        "gate_validation": {"activation_validation": "VALIDATION_CONFIRMED", "gate": {}},
        "regeneration_recalc_gate_validation": {"activation_validation": "VALIDATION_CONFIRMED", "gate": {}},
        "runtime_activation_snapshot": {"activation_governance_version": ACTIVATION_GOVERNANCE_VERSION, "families": []},
    }
    r = validate_dual_family_gate_alignment(validation_snapshot=vs)
    assert r["activation_validation"] == "VALIDATION_FAILED"
