"""Phase 2A burn-in: RST core backbone runtime validation (mocked traces only; no DB)."""

from __future__ import annotations

import json

from services.workflow_runtime_activation_validation import (
    VALIDATION_CONFIRMED,
    VALIDATION_FAILED,
    VALIDATION_PARTIAL,
)
from services.workflow_runtime_operational_burn_in import (
    BURN_IN_DEGRADED,
    BURN_IN_PARTIAL,
    PHASE2A_RST_CORE_BACKBONE_BURN_IN_VALIDATION_SCHEMA_VERSION,
    build_operational_burn_in_report,
    build_phase2a_rst_core_backbone_runtime_validation_bundle,
    build_staging_runtime_evidence_harness,
    classify_operational_burn_in,
    merge_staging_flow_traces_for_harness,
    validate_authority_sync_stability_phase2a_burn_in,
    validate_code_only_rollback_posture_phase2a_burn_in,
    validate_propagation_continuity_burn_in,
    validate_rst_core_backbone_propagation_chain_phase2a_burn_in,
)
from services.requirement_transition_observability import ENQUEUE_ACCEPTED
from tests.test_workflow_runtime_operational_burn_in import (
    STAGING_FLOW_DOCUMENT_UPLOAD,
    _backbone_blob,
    _enqueue_samples,
    _full_flow_map,
    _gap_row,
    _recalc_row,
    _regen_row,
    _trace,
)


def test_phase2a_bundle_schema_and_propagation_chain_confirmed():
    flows = _full_flow_map()
    ce, re = _enqueue_samples()
    h = build_staging_runtime_evidence_harness(
        generated_at_iso="2026-05-14T12:00:00Z",
        flow_traces_by_kind=flows,
        representative_enqueue_samples=ce,
        representative_regeneration_enqueue_samples=re,
        embed_full_merged_traces=False,
    )
    merged = merge_staging_flow_traces_for_harness(flows)
    propagation = validate_propagation_continuity_burn_in(transition_traces=merged)
    from services.workflow_runtime_operational_burn_in import classify_stale_degraded_runtime_visibility

    visibility = classify_stale_degraded_runtime_visibility(
        transition_traces=merged, convergence_snapshot=h["convergence_snapshot"]
    )
    bundle = build_phase2a_rst_core_backbone_runtime_validation_bundle(
        harness=h,
        merged_traces=merged,
        convergence_snapshot=h["convergence_snapshot"],
        propagation=propagation,
        visibility=visibility,
    )
    assert bundle["schema_version"] == PHASE2A_RST_CORE_BACKBONE_BURN_IN_VALIDATION_SCHEMA_VERSION
    assert bundle["rollup_activation_validation"] == VALIDATION_CONFIRMED
    assert bundle["propagation_chain"]["activation_validation"] == VALIDATION_CONFIRMED


def test_authority_skip_inconsistent_with_permitted_backbone_partial():
    rows = [
        _gap_row(),
        {
            "downstream_target": "requirement_state_transition.core_backbone.authority_sync",
            "enqueue_outcome": "ENQUEUE_SKIPPED",
            "propagation_stage": "rst_core_backbone_blocked_pre_authority_sync",
        },
        _recalc_row("ENQUEUE_ACCEPTED"),
        _regen_row("ENQUEUE_ACCEPTED"),
    ]
    tr = _trace(STAGING_FLOW_DOCUMENT_UPLOAD, "bad", rows, backbone_blob=_backbone_blob(permitted=True))
    v = validate_authority_sync_stability_phase2a_burn_in(transition_traces=[tr])
    assert v["activation_validation"] == VALIDATION_PARTIAL
    assert "phase2a_inconsistent_backbone_permitted_with_authority_skip_row" in v["finding_codes"]


def test_propagation_chain_fails_without_backbone_blob():
    rows = [_gap_row(), _recalc_row("ENQUEUE_ACCEPTED"), _regen_row("ENQUEUE_ACCEPTED")]
    tr = _trace(STAGING_FLOW_DOCUMENT_UPLOAD, "nb", rows, backbone_blob=None)
    v = validate_rst_core_backbone_propagation_chain_phase2a_burn_in(transition_traces=[tr])
    assert v["activation_validation"] == VALIDATION_PARTIAL


def test_code_only_rollback_posture_validated():
    r = validate_code_only_rollback_posture_phase2a_burn_in()
    assert r["activation_validation"] == VALIDATION_CONFIRMED
    assert len(r["rollback_transition_validations"]) == 3


def test_phase2a_rollup_failed_yields_burn_in_degraded():
    dual = {"dual_family_staging_readiness_classification": "DUAL_FAMILY_STAGING_CONFIRMED"}
    propagation = {"activation_validation": VALIDATION_CONFIRMED, "finding_codes": []}
    visibility = {"visibility_band": "visible"}
    findings = {"representative_trace_coverage_ratio": 1.0}
    validation_snapshot = {"drift": {"drift_classification": "LOW_VALIDATION_DRIFT"}, "overall_activation_validation": VALIDATION_CONFIRMED}
    phase2a = {"rollup_activation_validation": VALIDATION_FAILED}
    cls = classify_operational_burn_in(
        dual_family_snapshot=dual,
        propagation=propagation,
        visibility=visibility,
        findings=findings,
        validation_snapshot=validation_snapshot,
        phase2a_rst_core_backbone_runtime_validation=phase2a,
    )
    assert cls == BURN_IN_DEGRADED


def test_skipped_gated_row_missing_metadata_partial():
    rows = [
        _gap_row(),
        {
            "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
            "enqueue_outcome": "ENQUEUE_SKIPPED",
            "propagation_stage": "recalc_skip_without_activation_metadata",
        },
        _regen_row("ENQUEUE_ACCEPTED"),
    ]
    tr = _trace(STAGING_FLOW_DOCUMENT_UPLOAD, "sk", rows, backbone_blob=_backbone_blob())
    from services.workflow_runtime_operational_burn_in import validate_recalc_regen_metadata_phase2a_burn_in

    v = validate_recalc_regen_metadata_phase2a_burn_in(transition_traces=[tr])
    assert v["activation_validation"] == VALIDATION_PARTIAL
    assert v["skipped_rows_missing_activation_metadata_count"] >= 1


def test_phase2a_bundle_snapshot_stable_json():
    flows = {
        STAGING_FLOW_DOCUMENT_UPLOAD: [
            _trace(
                STAGING_FLOW_DOCUMENT_UPLOAD,
                "z",
                [_gap_row(), _recalc_row("ENQUEUE_ACCEPTED"), _regen_row("ENQUEUE_ACCEPTED")],
                backbone_blob=_backbone_blob(),
            )
        ]
    }
    ce, re = _enqueue_samples()
    h = build_staging_runtime_evidence_harness(
        generated_at_iso="2026-05-14T14:00:00Z",
        flow_traces_by_kind=flows,
        representative_enqueue_samples=ce,
        representative_regeneration_enqueue_samples=re,
        embed_full_merged_traces=False,
    )
    merged = merge_staging_flow_traces_for_harness(flows)
    propagation = validate_propagation_continuity_burn_in(transition_traces=merged)
    from services.workflow_runtime_operational_burn_in import classify_stale_degraded_runtime_visibility

    visibility = classify_stale_degraded_runtime_visibility(
        transition_traces=merged, convergence_snapshot=h["convergence_snapshot"]
    )
    b1 = build_phase2a_rst_core_backbone_runtime_validation_bundle(
        harness=h,
        merged_traces=merged,
        convergence_snapshot=h["convergence_snapshot"],
        propagation=propagation,
        visibility=visibility,
    )
    b2 = build_phase2a_rst_core_backbone_runtime_validation_bundle(
        harness=h,
        merged_traces=merged,
        convergence_snapshot=h["convergence_snapshot"],
        propagation=propagation,
        visibility=visibility,
    )
    assert json.dumps(b1, sort_keys=True, default=str) == json.dumps(b2, sort_keys=True, default=str)


def test_classify_operational_burn_in_phase2a_partial_downgrade():
    """Rollup PARTIAL forces BURN_IN_PARTIAL when other signals would confirm."""
    dual = {"dual_family_staging_readiness_classification": "DUAL_FAMILY_STAGING_CONFIRMED"}
    propagation = {"activation_validation": VALIDATION_CONFIRMED, "finding_codes": []}
    visibility = {"visibility_band": "visible"}
    findings = {"representative_trace_coverage_ratio": 1.0}
    validation_snapshot = {"drift": {"drift_classification": "LOW_VALIDATION_DRIFT"}, "overall_activation_validation": VALIDATION_CONFIRMED}
    phase2a = {"rollup_activation_validation": VALIDATION_PARTIAL}
    cls = classify_operational_burn_in(
        dual_family_snapshot=dual,
        propagation=propagation,
        visibility=visibility,
        findings=findings,
        validation_snapshot=validation_snapshot,
        phase2a_rst_core_backbone_runtime_validation=phase2a,
    )
    assert cls == BURN_IN_PARTIAL
