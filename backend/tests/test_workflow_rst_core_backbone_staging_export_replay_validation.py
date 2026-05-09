"""Export capture, replay through verification stack, divergence & Phase 2B gate (fixtures only)."""

from __future__ import annotations

import json
from pathlib import Path

from services.requirement_transition_observability import ENQUEUE_DUPLICATE_SUPPRESSED
from services.workflow_rst_core_backbone_staging_evidence_validation import (
    load_staging_evidence_bundle_from_json_file,
)
from services.workflow_rst_core_backbone_staging_export_replay_validation import (
    CRITICAL_RUNTIME_DIVERGENCE,
    EXPORT_REPLAY_VALIDATION_SCHEMA_VERSION,
    HOLD_PENDING_RUNTIME_REALISM,
    HOLD_PENDING_REPLAY_ALIGNMENT,
    NO_RUNTIME_DIVERGENCE,
    OPERATIONAL_TRUTH_CONFIRMED,
    OPERATIONAL_TRUTH_SYNTHETIC_DOMINANT,
    READY_FOR_PHASE2B_REVIEW,
    build_rst_core_backbone_staging_export_replay_validation_report,
    classify_runtime_divergence_from_replay_signals,
    coalesce_staging_export_roots,
    export_replay_capture_supported_envelope_keys,
    replay_staging_export_through_verification_stack,
    validate_staging_export_replay_realism,
)
from services.workflow_runtime_activation_validation import VALIDATION_CONFIRMED, VALIDATION_PARTIAL

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "staging_evidence"
HIGH_REALISM = FIXTURE_DIR / "rst_core_backbone_staging_bundle_high_realism.json"


def test_coalesce_raw_staging_export_top_level_wins():
    inner = {"transition_traces": [{"transition_id": "from_raw", "correlation_id": "c1"}], "note": "inner"}
    outer_trace = [{"transition_id": "winner", "correlation_id": "c2"}]
    coalesced, applied = coalesce_staging_export_roots(
        {"raw_staging_export": inner, "transition_traces": outer_trace}
    )
    assert applied is True
    assert coalesced["transition_traces"] == outer_trace
    assert coalesced.get("note") == "inner"


def test_coalesce_convergence_export_alias():
    conv = {"convergence_evidence_matrix": {"matrix_rows": []}}
    coalesced, applied = coalesce_staging_export_roots({"convergence_export": conv})
    assert applied is True
    assert coalesced["convergence_snapshot"] == conv


def test_export_replay_report_deterministic_on_fixture():
    bundle = load_staging_evidence_bundle_from_json_file(HIGH_REALISM)
    r1 = build_rst_core_backbone_staging_export_replay_validation_report(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-08T15:00:00Z",
    )
    r2 = build_rst_core_backbone_staging_export_replay_validation_report(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-08T15:00:00Z",
    )
    assert r1["schema_version"] == EXPORT_REPLAY_VALIDATION_SCHEMA_VERSION
    j1 = json.dumps(r1, sort_keys=True, default=str)
    j2 = json.dumps(r2, sort_keys=True, default=str)
    assert j1 == j2


def test_export_replay_operational_truth_and_gate_high_realism():
    bundle = load_staging_evidence_bundle_from_json_file(HIGH_REALISM)
    r = build_rst_core_backbone_staging_export_replay_validation_report(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-08T15:00:00Z",
    )
    assert r["runtime_divergence"]["runtime_divergence_classification"] == NO_RUNTIME_DIVERGENCE
    assert r["operational_truth_classification"] == OPERATIONAL_TRUTH_CONFIRMED
    assert r["readiness_gate_phase2b_export_replay"]["readiness_classification"] == READY_FOR_PHASE2B_REVIEW


def test_export_replay_synthetic_fixture_gate_runtime_realism():
    bundle = load_staging_evidence_bundle_from_json_file(
        FIXTURE_DIR / "rst_core_backbone_staging_bundle_synthetic_dominant.json"
    )
    r = build_rst_core_backbone_staging_export_replay_validation_report(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-08T15:00:00Z",
    )
    assert r["operational_truth_classification"] == OPERATIONAL_TRUTH_SYNTHETIC_DOMINANT
    assert r["readiness_gate_phase2b_export_replay"]["readiness_classification"] == HOLD_PENDING_RUNTIME_REALISM


def test_replay_realism_duplicate_suppression_requires_propagation_stage():
    tr = [
        {
            "transition_id": "d1",
            "correlation_id": "c1",
            "downstream_trigger_targets": [
                {
                    "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                    "enqueue_outcome": ENQUEUE_DUPLICATE_SUPPRESSED,
                    "propagation_stage": "",
                }
            ],
        }
    ]
    v = validate_staging_export_replay_realism(
        transition_traces=tr,
        convergence_snapshot={},
        propagation_continuity={"coexistence": {"has_recalc_downstream": True, "has_regen_downstream": True}},
    )
    assert v["activation_validation"] == VALIDATION_PARTIAL
    assert "replay_realism_duplicate_suppression_missing_propagation_stage" in v["finding_codes"]


def test_replay_realism_replay_flag_without_downstream_hold_gate_path():
    tr = [{"transition_id": "r1", "correlation_id": "c1", "replay_chain_detected": True, "downstream_trigger_targets": []}]
    propagation = {"coexistence": {"has_recalc_downstream": False, "has_regen_downstream": False}}
    v = validate_staging_export_replay_realism(
        transition_traces=tr,
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"reconciliation_visibility": "RECONCILIATION_OBSERVED"}]}},
        propagation_continuity=propagation,
    )
    assert "replay_realism_replay_chain_collapse_empty_downstream" in v["finding_codes"]
    bundle = load_staging_evidence_bundle_from_json_file(HIGH_REALISM)
    verification = replay_staging_export_through_verification_stack(
        staging_export_bundle=bundle,
        generated_at_iso="2026-05-08T15:00:00Z",
    )
    div = classify_runtime_divergence_from_replay_signals(verification_report=verification, replay_realism=v)
    assert div["runtime_divergence_classification"] != CRITICAL_RUNTIME_DIVERGENCE


def test_governance_fork_elevates_cross_artifact_and_divergence():
    bundle = load_staging_evidence_bundle_from_json_file(HIGH_REALISM)
    fork = dict(bundle)
    fork["evidence_pack"] = dict(fork["evidence_pack"])
    fork["evidence_pack"]["activation_governance_version"] = "workflow_runtime_activation_registry_invalid_stub"
    r = build_rst_core_backbone_staging_export_replay_validation_report(
        staging_capture_bundle=fork,
        generated_at_iso="2026-05-08T15:00:00Z",
    )
    assert r["replay_validation"]["replay_ordered_verification_report"]["cross_artifact_alignment"]["activation_validation"] == VALIDATION_PARTIAL
    assert r["runtime_divergence"]["runtime_divergence_classification"] != NO_RUNTIME_DIVERGENCE


def test_backward_compatible_empty_capture_bundle():
    r = build_rst_core_backbone_staging_export_replay_validation_report(
        staging_capture_bundle={},
        generated_at_iso="2026-05-08T15:00:00Z",
    )
    assert r["replay_validation"]["replay_ordered_verification_report"]["trace_sample_count"] == 0
    assert "operational_summaries" in r


def test_export_envelope_keys_documented():
    keys = export_replay_capture_supported_envelope_keys()
    assert "raw_staging_export" in keys
    assert "convergence_export" in keys
