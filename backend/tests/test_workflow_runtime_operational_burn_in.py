"""Operational burn-in harness (mocked staging traces; no DB)."""

from __future__ import annotations

import json
from unittest.mock import patch

import services.workflow_runtime_activation_registry as reg
from services.workflow_activation_readiness import FAMILY_COMPLIANCE_SCORE_RECALC, FAMILY_REGENERATION_RECALC
from services.requirement_transition_observability import ENQUEUE_ACCEPTED
from services.workflow_runtime_activation_validation import VALIDATION_CONFIRMED
from services.workflow_runtime_operational_burn_in import (
    BURN_IN_CONFIRMED,
    BURN_IN_OBSERVE_ONLY,
    BURN_IN_PARTIAL,
    OPERATIONAL_BURN_IN_SCHEMA_VERSION,
    PHASE2A_RST_CORE_BACKBONE_BURN_IN_VALIDATION_SCHEMA_VERSION,
    READY_FOR_PHASE2_REVIEW,
    STAGING_FLOW_AI_EXTRACTION_CONFIRMATION,
    STAGING_FLOW_DOCUMENT_UPLOAD,
    STAGING_FLOW_DOCUMENT_VERIFY,
    STAGING_FLOW_OUTCOME_ENGINE_AUTHORITY_REFRESH,
    STAGING_RUNTIME_FLOW_KINDS,
    VISIBILITY_PARTIALLY_VISIBLE,
    VISIBILITY_VISIBLE,
    build_operational_burn_in_report,
    build_staging_runtime_evidence_harness,
    classify_stale_degraded_runtime_visibility,
    merge_staging_flow_traces_for_harness,
    validate_propagation_continuity_burn_in,
)
from services.workflow_runtime_activation_registry import (
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
)
from services.workflow_runtime_activation_registry import resolve_compliance_recalc_activation_gate, resolve_regeneration_recalc_activation_gate


def _recalc_row(outcome: str, **extra):
    return {
        "activation_family": FAMILY_COMPLIANCE_SCORE_RECALC,
        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
        "activation_guard_result": "GUARD_RESULT_PERMITTED",
        "activation_reason": "r",
        "activation_scope": "compliance_recalc_enqueue_only",
        "activation_state": ACTIVATION_LIMITED,
        "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
        "enqueue_outcome": outcome,
        "propagation_stage": "recalc_enqueue_sample",
        **extra,
    }


def _regen_row(outcome: str):
    return {
        "activation_family": FAMILY_REGENERATION_RECALC,
        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
        "activation_guard_result": "GUARD_RESULT_PERMITTED",
        "activation_reason": "r",
        "activation_scope": "risk_signal_regen_enqueue_only",
        "activation_state": ACTIVATION_LIMITED,
        "downstream_target": "risk_signal_regen_queue.enqueue_risk_signal_regen",
        "enqueue_outcome": outcome,
        "propagation_stage": "risk_regen_delegate_sample",
    }


def _gap_row():
    return {
        "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
        "enqueue_outcome": ENQUEUE_ACCEPTED,
        "propagation_stage": "gap_sync_sample",
    }


def _backbone_blob(permitted=True):
    return {
        "child_compliance_recalc_permitted": True,
        "child_regeneration_recalc_permitted": True,
        "permitted": permitted,
        "propagation_skipped_visibility": not permitted,
    }


def _trace(flow_key: str, tid: str, rows: list, *, replay: bool = False, origin: str = "OUTCOME_ENGINE_SYNC:test", backbone_blob=None):
    tr = {
        "correlation_id": f"c-{tid}",
        "downstream_trigger_targets": rows,
        "replay_chain_detected": replay,
        "transition_id": tid,
        "transition_origin": origin,
    }
    if backbone_blob is not None:
        tr["rst_core_backbone_activation"] = backbone_blob
    return tr


def _full_flow_map():
    """One trace per canonical flow kind with gap→recalc→regen and RST backbone metadata."""
    m = {}
    bb = _backbone_blob()
    for i, kind in enumerate(STAGING_RUNTIME_FLOW_KINDS):
        rows = [_gap_row(), _recalc_row("ENQUEUE_ACCEPTED"), _regen_row("ENQUEUE_DEGRADED")]
        if kind == STAGING_FLOW_DOCUMENT_VERIFY:
            rows = [
                _gap_row(),
                _recalc_row("ENQUEUE_DUPLICATE_SUPPRESSED", duplicate_suppression_reason="dedupe"),
                _regen_row("ENQUEUE_ACCEPTED"),
            ]
        if kind == STAGING_FLOW_AI_EXTRACTION_CONFIRMATION:
            rows = [
                _gap_row(),
                _recalc_row(
                    "ENQUEUE_SKIPPED",
                    activation_guard_result="GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY",
                    activation_reason="activation_gate",
                    activation_skipped=True,
                    propagation_stage="recalc_skipped_sample",
                ),
                _regen_row("ENQUEUE_ACCEPTED"),
            ]
        replay = kind == STAGING_FLOW_OUTCOME_ENGINE_AUTHORITY_REFRESH
        m[kind] = [_trace(kind, f"t{i}", rows, replay=replay, backbone_blob=bb)]
    return m


def _enqueue_samples():
    cg = resolve_compliance_recalc_activation_gate()
    rg = resolve_regeneration_recalc_activation_gate()
    return (
        [
            {
                "enqueue": {
                    "activation_family": cg["activation_family"],
                    "activation_governance_version": cg["activation_governance_version"],
                    "activation_guard_result": cg["activation_guard_result"],
                    "activation_reason": cg["activation_reason"],
                    "activation_scope": cg["activation_scope"],
                    "activation_skipped": False,
                    "activation_state": cg["activation_state"],
                    "correlation_id": "burn-in-cid",
                    "enqueued": True,
                    "regeneration_error": None,
                    "regeneration_requeued": True,
                },
                "gate": cg,
            }
        ],
        [
            {
                "enqueue": {
                    "activation_family": rg["activation_family"],
                    "activation_governance_version": rg["activation_governance_version"],
                    "activation_guard_result": rg["activation_guard_result"],
                    "activation_reason": rg["activation_reason"],
                    "activation_scope": rg["activation_scope"],
                    "activation_skipped": False,
                    "activation_state": rg["activation_state"],
                    "merged": False,
                    "property_id": "p-burn",
                    "queued": True,
                },
                "gate": rg,
            }
        ],
    )


def test_merge_ordering_deterministic():
    m = {
        STAGING_FLOW_DOCUMENT_UPLOAD: [_trace(STAGING_FLOW_DOCUMENT_UPLOAD, "b", [_recalc_row("ENQUEUE_ACCEPTED")])],
        STAGING_FLOW_DOCUMENT_VERIFY: [_trace(STAGING_FLOW_DOCUMENT_VERIFY, "a", [_recalc_row("ENQUEUE_ACCEPTED")])],
    }
    merged = merge_staging_flow_traces_for_harness(m)
    kinds = [str(t.get("staging_runtime_flow_kind")) for t in merged]
    assert kinds == sorted(kinds)


def test_burn_in_report_determinism():
    flows = _full_flow_map()
    ce, re = _enqueue_samples()
    kw = dict(
        generated_at_iso="2026-05-13T12:00:00Z",
        flow_traces_by_kind=flows,
        queue_visibility={"diagnostics": {"returned_count": 4, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 2}}},
        representative_enqueue_samples=ce,
        representative_regeneration_enqueue_samples=re,
        embed_full_merged_traces=False,
    )
    r1 = build_operational_burn_in_report(**kw)
    r2 = build_operational_burn_in_report(**kw)
    assert json.dumps(r1, sort_keys=True, default=str) == json.dumps(r2, sort_keys=True, default=str)
    assert r1["schema_version"] == OPERATIONAL_BURN_IN_SCHEMA_VERSION


def test_burn_in_confirmed_and_phase2_readiness():
    flows = _full_flow_map()
    ce, re = _enqueue_samples()
    rep = build_operational_burn_in_report(
        generated_at_iso="2026-05-13T12:00:00Z",
        flow_traces_by_kind=flows,
        representative_enqueue_samples=ce,
        representative_regeneration_enqueue_samples=re,
        embed_full_merged_traces=False,
    )
    assert rep["burn_in_classification"] == BURN_IN_CONFIRMED
    assert rep["operational_readiness_recommendation"]["operational_readiness_conclusion"] == READY_FOR_PHASE2_REVIEW


def test_burn_in_partial_low_coverage():
    flows = {
        STAGING_FLOW_DOCUMENT_UPLOAD: [
            _trace(
                STAGING_FLOW_DOCUMENT_UPLOAD,
                "x",
                [_gap_row(), _recalc_row("ENQUEUE_ACCEPTED"), _regen_row("ENQUEUE_ACCEPTED")],
                backbone_blob=_backbone_blob(),
            ),
        ]
    }
    ce, re = _enqueue_samples()
    rep = build_operational_burn_in_report(
        generated_at_iso="2026-05-13T13:00:00Z",
        flow_traces_by_kind=flows,
        representative_enqueue_samples=ce,
        representative_regeneration_enqueue_samples=re,
        embed_full_merged_traces=False,
    )
    assert rep["burn_in_classification"] == BURN_IN_PARTIAL


def test_burn_in_observe_only_registry():
    flows = {
        STAGING_FLOW_DOCUMENT_UPLOAD: [
            _trace(
                STAGING_FLOW_DOCUMENT_UPLOAD,
                "x",
                [_gap_row(), _recalc_row("ENQUEUE_ACCEPTED"), _regen_row("ENQUEUE_ACCEPTED")],
                backbone_blob=_backbone_blob(),
            ),
        ]
    }
    ce, re = _enqueue_samples()
    with patch.dict(
        reg._REGISTRY_CEILING,
        {FAMILY_COMPLIANCE_SCORE_RECALC: ACTIVATION_OBSERVE_ONLY, FAMILY_REGENERATION_RECALC: ACTIVATION_OBSERVE_ONLY},
        clear=False,
    ):
        rep = build_operational_burn_in_report(
            generated_at_iso="2026-05-13T14:00:00Z",
            flow_traces_by_kind=flows,
            representative_enqueue_samples=ce,
            representative_regeneration_enqueue_samples=re,
            embed_full_merged_traces=False,
        )
    assert rep["burn_in_classification"] == BURN_IN_OBSERVE_ONLY


def test_propagation_coexistence_and_visibility():
    flows = {
        STAGING_FLOW_DOCUMENT_UPLOAD: [
            _trace(STAGING_FLOW_DOCUMENT_UPLOAD, "x", [_recalc_row("ENQUEUE_ACCEPTED"), _regen_row("ENQUEUE_DEGRADED")], replay=True),
        ]
    }
    merged = merge_staging_flow_traces_for_harness(flows)
    from services.workflow_runtime_convergence_observability import build_runtime_convergence_snapshot

    conv = build_runtime_convergence_snapshot(transition_traces=merged, generated_at_iso="2026-05-13T15:00:00Z")
    p = validate_propagation_continuity_burn_in(transition_traces=merged)
    assert p["has_compliance_recalc_downstream_hits"] and p["has_regen_delegate_rows"]
    assert p["replay_or_reentry_trace_signals"] >= 1
    v = classify_stale_degraded_runtime_visibility(transition_traces=merged, convergence_snapshot=conv)
    assert v["visibility_band"] in (VISIBILITY_VISIBLE, VISIBILITY_PARTIALLY_VISIBLE)


def test_summaries_present():
    flows = _full_flow_map()
    ce, re = _enqueue_samples()
    rep = build_operational_burn_in_report(
        generated_at_iso="2026-05-13T16:00:00Z",
        flow_traces_by_kind=flows,
        representative_enqueue_samples=ce,
        representative_regeneration_enqueue_samples=re,
        embed_full_merged_traces=False,
    )
    for key in (
        "burn_in_activation_summary",
        "burn_in_convergence_summary",
        "burn_in_observability_summary",
        "burn_in_reconciliation_summary",
        "burn_in_drift_summary",
        "burn_in_runtime_consistency_summary",
        "burn_in_rollback_summary",
        "phase2a_rst_core_backbone_runtime_validation",
        "representative_staging_evidence_findings",
    ):
        assert key in rep
    assert (
        rep["phase2a_rst_core_backbone_runtime_validation"]["schema_version"]
        == PHASE2A_RST_CORE_BACKBONE_BURN_IN_VALIDATION_SCHEMA_VERSION
    )
    assert (
        rep["phase2a_rst_core_backbone_runtime_validation"]["rollup_activation_validation"] == VALIDATION_CONFIRMED
    )


def test_harness_includes_evidence_pack_and_dual_family():
    flows = _full_flow_map()
    ce, re = _enqueue_samples()
    h = build_staging_runtime_evidence_harness(
        generated_at_iso="2026-05-13T17:00:00Z",
        flow_traces_by_kind=flows,
        representative_enqueue_samples=ce,
        representative_regeneration_enqueue_samples=re,
        embed_full_merged_traces=False,
    )
    assert "evidence_pack" in h and "dual_family_staging_validation" in h
    assert h["merged_transition_traces_count"] == len(STAGING_RUNTIME_FLOW_KINDS)
