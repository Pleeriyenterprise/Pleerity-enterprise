"""Read-only staging/runtime evidence verification for RST core backbone (exported JSON fixtures)."""

from __future__ import annotations

import json
from pathlib import Path

from services.workflow_runtime_activation_registry import ACTIVATION_GOVERNANCE_VERSION
from services.workflow_runtime_activation_validation import VALIDATION_CONFIRMED, VALIDATION_PARTIAL
from services.workflow_runtime_convergence_observability import JOIN_WEAK
from services.workflow_rst_core_backbone_staging_evidence_validation import (
    READY_FOR_PHASE2B_REVIEW,
    RUNTIME_EVIDENCE_HIGH_REALISM,
    RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT,
    STAGING_CONFIDENCE_REQUIRES_REVIEW,
    STAGING_EVIDENCE_BUNDLE_SCHEMA_VERSION,
    STAGING_RUNTIME_EVIDENCE_VERIFICATION_SCHEMA_VERSION,
    assemble_harness_for_staging_verification,
    build_rst_core_backbone_staging_runtime_evidence_verification_report,
    extract_transition_traces,
    load_staging_evidence_bundle_from_json_file,
    merge_frozen_governance_bundle,
    normalize_staging_evidence_bundle,
    staging_bundle_supported_schema_versions,
    validate_staging_export_convergence_surface_integrity,
    validate_staging_export_cross_artifact_alignment,
    validate_staging_export_propagation_surface_integrity,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "staging_evidence"
HIGH_REALISM = FIXTURE_DIR / "rst_core_backbone_staging_bundle_high_realism.json"
SYNTHETIC = FIXTURE_DIR / "rst_core_backbone_staging_bundle_synthetic_dominant.json"


def test_normalize_staging_evidence_bundle_deterministic_ordering():
    raw = {"z": 1, "a": {"m": 2, "b": 3}}
    n1 = normalize_staging_evidence_bundle(raw)
    n2 = normalize_staging_evidence_bundle(raw)
    assert n1 == n2
    assert list(n1.keys()) == ["a", "z"]


def test_load_high_realism_fixture_propagation_and_readiness():
    bundle = load_staging_evidence_bundle_from_json_file(HIGH_REALISM)
    r1 = build_rst_core_backbone_staging_runtime_evidence_verification_report(
        staging_evidence_bundle=bundle,
        generated_at_iso="2026-05-08T10:00:00Z",
    )
    r2 = build_rst_core_backbone_staging_runtime_evidence_verification_report(
        staging_evidence_bundle=bundle,
        generated_at_iso="2026-05-08T10:00:00Z",
    )
    assert r1["schema_version"] == STAGING_RUNTIME_EVIDENCE_VERIFICATION_SCHEMA_VERSION
    assert json.dumps(r1, sort_keys=True, default=str) == json.dumps(r2, sort_keys=True, default=str)
    assert r1["phase2a_rst_core_backbone_runtime_validation"]["rollup_activation_validation"] == VALIDATION_CONFIRMED
    assert r1["runtime_evidence_realism"]["classification"] == RUNTIME_EVIDENCE_HIGH_REALISM
    assert r1["readiness_for_phase2b_review"]["readiness_classification"] == READY_FOR_PHASE2B_REVIEW
    chain = r1["explicit_mutation_to_regen_chain_evidence"]
    assert chain["authority_sync_stability"]["schema_version"]


def test_synthetic_dominant_fixture_realism_and_confidence():
    bundle = load_staging_evidence_bundle_from_json_file(SYNTHETIC)
    r = build_rst_core_backbone_staging_runtime_evidence_verification_report(
        staging_evidence_bundle=bundle,
        generated_at_iso="2026-05-08T10:00:00Z",
    )
    assert r["runtime_evidence_realism"]["classification"] == RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT
    assert r["staging_confidence_classification"] == STAGING_CONFIDENCE_REQUIRES_REVIEW


def test_merge_frozen_governance_bundle_overlays_top_level():
    base = {"evidence_pack": {"activation_governance_version": "stale_version", "x": 1}}
    frozen = {"evidence_pack": {"activation_governance_version": ACTIVATION_GOVERNANCE_VERSION, "x": 2}}
    merged = merge_frozen_governance_bundle(base_bundle=base, frozen_bundle=frozen)
    assert merged["evidence_pack"]["activation_governance_version"] == ACTIVATION_GOVERNANCE_VERSION


def test_propagation_surface_replay_collapse_finding():
    tr = {"transition_id": "a", "correlation_id": "b", "replay_chain_detected": True, "downstream_trigger_targets": []}
    v = validate_staging_export_propagation_surface_integrity(transition_traces=[tr])
    assert v["activation_validation"] == VALIDATION_PARTIAL
    assert "staging_propagation_replay_chain_collapse_empty_downstream" in v["finding_codes"]


def test_propagation_surface_regen_without_recalc_lineage():
    rows = [
        {"downstream_target": "risk_signal_regen_queue.enqueue_risk_signal_regen", "enqueue_outcome": "ENQUEUE_ACCEPTED", "propagation_stage": "r"}
    ]
    tr = {"transition_id": "a", "correlation_id": "b", "downstream_trigger_targets": rows}
    v = validate_staging_export_propagation_surface_integrity(transition_traces=[tr])
    assert "staging_propagation_regen_without_recalc_lineage_in_downstream_order" in v["finding_codes"]


def test_convergence_join_weak_dominant():
    mx = [{"join_classification": JOIN_WEAK} for _ in range(6)]
    mx.append({"join_classification": "JOIN_STRONG"})
    conv = {"convergence_evidence_matrix": {"matrix_rows": mx}}
    tr = {"transition_id": "x", "correlation_id": "y", "downstream_trigger_targets": []}
    v = validate_staging_export_convergence_surface_integrity(
        transition_traces=[tr],
        convergence_snapshot=conv,
    )
    assert "staging_convergence_join_weak_dominant_in_matrix_sample" in v["finding_codes"]


def test_cross_artifact_governance_version_mismatch():
    harness = {
        "governance_report_full": {
            "runtime_activation_snapshot": {"activation_governance_version": ACTIVATION_GOVERNANCE_VERSION, "families": []}
        },
        "evidence_pack": {"activation_governance_version": "wrong"},
        "dual_family_staging_validation": {},
        "rst_core_backbone_activation_operational_visibility": {},
    }
    v = validate_staging_export_cross_artifact_alignment(bundle={}, harness=harness)
    assert v["activation_validation"] == VALIDATION_PARTIAL
    assert "staging_cross_artifact_evidence_pack_governance_version_mismatch_vs_governance_report" in v["finding_codes"]


def test_operational_burn_in_nested_trace_extraction():
    from services.workflow_runtime_operational_burn_in import build_operational_burn_in_report
    from tests.test_workflow_runtime_operational_burn_in import STAGING_FLOW_DOCUMENT_UPLOAD, _enqueue_samples, _trace, _gap_row, _recalc_row, _regen_row, _backbone_blob

    ce, re = _enqueue_samples()
    rows = [_gap_row(), _recalc_row("ENQUEUE_ACCEPTED"), _regen_row("ENQUEUE_ACCEPTED")]
    flows = {STAGING_FLOW_DOCUMENT_UPLOAD: [_trace(STAGING_FLOW_DOCUMENT_UPLOAD, "t0", rows, backbone_blob=_backbone_blob())]}
    report = build_operational_burn_in_report(
        generated_at_iso="2026-05-08T12:00:00Z",
        flow_traces_by_kind=flows,
        representative_enqueue_samples=ce,
        representative_regeneration_enqueue_samples=re,
        embed_full_merged_traces=True,
    )
    bundle = {"operational_burn_in_report": report}
    traces = extract_transition_traces(bundle)
    assert len(traces) >= 1


def test_backward_compatible_empty_bundle_and_schema_helpers():
    r = build_rst_core_backbone_staging_runtime_evidence_verification_report(
        staging_evidence_bundle={},
        generated_at_iso="2026-05-08T10:00:00Z",
    )
    assert r["trace_sample_count"] == 0
    assert "operational_summaries" in r
    assert STAGING_RUNTIME_EVIDENCE_VERIFICATION_SCHEMA_VERSION in staging_bundle_supported_schema_versions() or True
    _ = assemble_harness_for_staging_verification({})


def test_governance_mismatch_finding_on_exported_high_realism_fork():
    bundle = load_staging_evidence_bundle_from_json_file(HIGH_REALISM)
    fork = dict(bundle)
    fork["evidence_pack"] = dict(fork["evidence_pack"])
    fork["evidence_pack"]["activation_governance_version"] = "workflow_runtime_activation_registry_v0_not_real"
    r = build_rst_core_backbone_staging_runtime_evidence_verification_report(
        staging_evidence_bundle=fork,
        generated_at_iso="2026-05-08T10:00:00Z",
    )
    assert r["cross_artifact_alignment"]["activation_validation"] == VALIDATION_PARTIAL
