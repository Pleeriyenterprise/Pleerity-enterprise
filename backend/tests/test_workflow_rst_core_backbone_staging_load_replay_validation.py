"""Controlled staging load replay validation (fixtures only; read-only)."""

from __future__ import annotations

import json
from pathlib import Path

from services.workflow_rst_core_backbone_staging_evidence_validation import load_staging_evidence_bundle_from_json_file
from services.workflow_rst_core_backbone_staging_export_replay_validation import NO_RUNTIME_DIVERGENCE
from services.workflow_rst_core_backbone_staging_export_replay_validation import (
    EXPORT_REPLAY_VALIDATION_SCHEMA_VERSION as EXPORT_REPLAY_SCHEMA,
)
from services.workflow_rst_core_backbone_staging_load_replay_validation import (
    CRITICAL_OPERATIONAL_ENTROPY,
    HIGH_OPERATIONAL_ENTROPY,
    HIGH_RUNTIME_DIVERGENCE,
    LOAD_REPLAY_VALIDATION_SCHEMA_VERSION,
    LOW_OPERATIONAL_ENTROPY,
    OPERATIONAL_DURABILITY_CONFIRMED,
    READY_FOR_PHASE2B_GOVERNANCE_REVIEW,
    build_rst_core_backbone_staging_load_replay_validation_report,
    classify_operational_entropy_from_pressure_signals,
    escalate_runtime_divergence_under_pressure,
    pressure_burst_duplicate_sequence,
    pressure_reverse_lexicographic_tid,
)

FIXTURE_HIGH = Path(__file__).resolve().parent / "fixtures" / "staging_evidence" / "rst_core_backbone_staging_bundle_high_realism.json"
FIXTURE_SYNTH = Path(__file__).resolve().parent / "fixtures" / "staging_evidence" / "rst_core_backbone_staging_bundle_synthetic_dominant.json"


def test_pressure_burst_sequence_deterministic_and_duplicate_ratio():
    traces = [{"transition_id": "a", "correlation_id": "c"}, {"transition_id": "b", "correlation_id": "d"}]
    b2 = pressure_burst_duplicate_sequence(traces, burst_factor=2)
    assert len(b2) == 4
    rev = pressure_reverse_lexicographic_tid(traces)
    assert len(rev) == 2


def test_burst_pressure_increases_entropy_score_vs_minimal_campaign():
    bundle = load_staging_evidence_bundle_from_json_file(FIXTURE_HIGH)
    r_min = build_rst_core_backbone_staging_load_replay_validation_report(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-09T10:00:00Z",
        burst_factors=(1,),
        include_ordering_variants=False,
    )
    r_hot = build_rst_core_backbone_staging_load_replay_validation_report(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-09T10:00:00Z",
        burst_factors=(1, 4),
        include_ordering_variants=False,
    )
    assert r_min["operational_entropy"]["classification"] == LOW_OPERATIONAL_ENTROPY
    assert r_hot["operational_entropy"]["entropy_score"] >= r_min["operational_entropy"]["entropy_score"]


def test_minimal_pressure_governance_review_ready_on_fixture():
    bundle = load_staging_evidence_bundle_from_json_file(FIXTURE_HIGH)
    r = build_rst_core_backbone_staging_load_replay_validation_report(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-09T10:00:00Z",
        burst_factors=(1,),
        include_ordering_variants=False,
    )
    assert r["schema_version"] == LOAD_REPLAY_VALIDATION_SCHEMA_VERSION
    assert r["operational_durability_classification"] == OPERATIONAL_DURABILITY_CONFIRMED
    assert r["readiness_gate_phase2b_governance_review"]["readiness_classification"] == READY_FOR_PHASE2B_GOVERNANCE_REVIEW
    nested = r["baseline_export_replay_report"]
    assert nested["schema_version"] == EXPORT_REPLAY_SCHEMA


def test_load_replay_campaign_digest_deterministic():
    bundle = load_staging_evidence_bundle_from_json_file(FIXTURE_HIGH)
    kw = dict(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-09T10:00:00Z",
        burst_factors=(1, 2),
        include_ordering_variants=False,
    )
    r1 = build_rst_core_backbone_staging_load_replay_validation_report(**kw)
    r2 = build_rst_core_backbone_staging_load_replay_validation_report(**kw)
    assert r1["load_replay_campaign_digest_sha256"] == r2["load_replay_campaign_digest_sha256"]


def test_divergence_escalation_entropy_critical_bumps_tier():
    out = escalate_runtime_divergence_under_pressure(
        baseline_divergence_classification=NO_RUNTIME_DIVERGENCE,
        worst_pressure_divergence_classification=NO_RUNTIME_DIVERGENCE,
        entropy_classification=CRITICAL_OPERATIONAL_ENTROPY,
    )
    assert out["runtime_divergence_escalated_classification"] == HIGH_RUNTIME_DIVERGENCE


def test_entropy_classification_direct_signals():
    traces = [{"transition_id": "x", "correlation_id": "y", "replay_chain_detected": True}] * 6
    ent = classify_operational_entropy_from_pressure_signals(
        traces_after_pressure=traces,
        burst_factor_max=4,
        scenario_rollup_labels=["VALIDATION_CONFIRMED", "VALIDATION_PARTIAL"],
        join_weak_ratio_max=0.5,
        convergence_matrix_row_count=5,
        baseline_trace_count=3,
    )
    assert ent["classification"] in (HIGH_OPERATIONAL_ENTROPY, CRITICAL_OPERATIONAL_ENTROPY)
    assert ent["entropy_score"] >= 48


def test_mixed_lineage_two_exports_scenario_runs():
    high = load_staging_evidence_bundle_from_json_file(FIXTURE_HIGH)
    synth = load_staging_evidence_bundle_from_json_file(FIXTURE_SYNTH)
    r = build_rst_core_backbone_staging_load_replay_validation_report(
        staging_capture_bundle=high,
        secondary_capture_bundle=synth,
        generated_at_iso="2026-05-09T10:00:00Z",
        burst_factors=(1,),
        include_ordering_variants=False,
    )
    assert "mixed_lineage_two_exports" in r["pressure_scenario_labels"]
    assert len(r["pressure_scenario_reports"]) == len(r["pressure_scenario_labels"])


def test_backward_compat_json_roundtrip_stable_keys():
    bundle = load_staging_evidence_bundle_from_json_file(FIXTURE_HIGH)
    r = build_rst_core_backbone_staging_load_replay_validation_report(
        staging_capture_bundle=bundle,
        generated_at_iso="2026-05-09T10:00:00Z",
        burst_factors=(1,),
        include_ordering_variants=False,
    )
    pruned = {k: r[k] for k in sorted(r.keys()) if k not in ("baseline_export_replay_report", "pressure_scenario_reports")}
    j1 = json.dumps(pruned, sort_keys=True, default=str)
    j2 = json.dumps(pruned, sort_keys=True, default=str)
    assert j1 == j2
