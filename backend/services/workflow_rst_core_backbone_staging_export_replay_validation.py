"""
Staging export capture & replay validation — operational truth before Phase 2B (advisory only).

Replays captured JSON exports through the existing staging runtime verification stack without
mutation, queue execution, or activation widening.

Scope: REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE, COMPLIANCE_SCORE_RECALC,
REGENERATION_RECALC and the LIMITED propagation chain evidence only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Tuple

from services.requirement_transition_observability import (
    ENQUEUE_DEGRADED,
    ENQUEUE_DUPLICATE_SUPPRESSED,
)
from services.workflow_rst_core_backbone_staging_evidence_validation import (
    HOLD_PENDING_CONVERGENCE_ALIGNMENT,
    HOLD_PENDING_GOVERNANCE_ALIGNMENT,
    HOLD_PENDING_RUNTIME_REALISM,
    READY_FOR_PHASE2B_REVIEW,
    RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT,
    STAGING_CONFIDENCE_CONFIRMED,
    STAGING_CONFIDENCE_DEGRADED,
    STAGING_CONFIDENCE_DRIFT_VISIBLE,
    STAGING_CONFIDENCE_OBSERVE_ONLY,
    STAGING_CONFIDENCE_PARTIAL,
    STAGING_CONFIDENCE_REQUIRES_REVIEW,
    assemble_harness_for_staging_verification,
    build_rst_core_backbone_staging_runtime_evidence_verification_report,
    extract_convergence_snapshot,
    extract_transition_traces,
    normalize_staging_evidence_bundle,
    validate_staging_export_rollback_realism,
)
from services.workflow_runtime_activation_validation import (
    VALIDATION_CONFIRMED,
    VALIDATION_FAILED,
    VALIDATION_INSUFFICIENT_EVIDENCE,
    VALIDATION_PARTIAL,
)
from services.workflow_runtime_convergence_observability import RECONCILIATION_NOT_VISIBLE
from services.workflow_runtime_operational_burn_in import _downstream_rows as burn_in_downstream_rows

EXPORT_REPLAY_VALIDATION_SCHEMA_VERSION = "rst_core_backbone_staging_export_replay_validation_v1"

NO_RUNTIME_DIVERGENCE = "NO_RUNTIME_DIVERGENCE"
LOW_RUNTIME_DIVERGENCE = "LOW_RUNTIME_DIVERGENCE"
MODERATE_RUNTIME_DIVERGENCE = "MODERATE_RUNTIME_DIVERGENCE"
HIGH_RUNTIME_DIVERGENCE = "HIGH_RUNTIME_DIVERGENCE"
CRITICAL_RUNTIME_DIVERGENCE = "CRITICAL_RUNTIME_DIVERGENCE"

OPERATIONAL_TRUTH_CONFIRMED = "OPERATIONAL_TRUTH_CONFIRMED"
OPERATIONAL_TRUTH_PARTIAL = "OPERATIONAL_TRUTH_PARTIAL"
OPERATIONAL_TRUTH_DEGRADED = "OPERATIONAL_TRUTH_DEGRADED"
OPERATIONAL_TRUTH_DRIFT_VISIBLE = "OPERATIONAL_TRUTH_DRIFT_VISIBLE"
OPERATIONAL_TRUTH_SYNTHETIC_DOMINANT = "OPERATIONAL_TRUTH_SYNTHETIC_DOMINANT"
OPERATIONAL_TRUTH_REQUIRES_REVIEW = "OPERATIONAL_TRUTH_REQUIRES_REVIEW"

HOLD_PENDING_RUNTIME_TRUTH_ALIGNMENT = "HOLD_PENDING_RUNTIME_TRUTH_ALIGNMENT"
HOLD_PENDING_REPLAY_ALIGNMENT = "HOLD_PENDING_REPLAY_ALIGNMENT"
HOLD_PENDING_DEGRADED_PATH_ALIGNMENT = "HOLD_PENDING_DEGRADED_PATH_ALIGNMENT"

_RECALC_SUB = "compliance_recalc_queue.enqueue_compliance_recalc"
_REGEN_SUB = "risk_signal_regen_queue.enqueue_risk_signal_regen"


def coalesce_staging_export_roots(bundle: Mapping[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Normalize capture envelopes: aliases and ``raw_staging_export`` wrapper (top-level keys win).

    Frozen governance overlays remain under ``frozen_governance_bundle`` for the verification stack
    to merge (unchanged behavior).

    Returns ``(normalized_bundle, coalescing_applied)``.
    """
    applied = False
    b: MutableMapping[str, Any] = dict(bundle)
    aliases = (
        ("convergence_export", "convergence_snapshot"),
        ("runtime_evidence_pack_export", "evidence_pack"),
        ("governance_export", "governance_report_full"),
        ("operational_burn_in_export", "operational_burn_in_report"),
        ("frozen_governance_bundle_export", "frozen_governance_bundle"),
    )
    for src, dst in aliases:
        if src in b and dst not in b:
            b[dst] = b[src]
            applied = True
    raw = b.get("raw_staging_export")
    if isinstance(raw, Mapping):
        merged: Dict[str, Any] = dict(raw)
        for k, v in b.items():
            if k == "raw_staging_export":
                continue
            merged[k] = v
        b = merged
        applied = True
    return normalize_staging_evidence_bundle(dict(b)), applied


def replay_staging_export_through_verification_stack(
    *,
    staging_export_bundle: Mapping[str, Any],
    generated_at_iso: str,
) -> Dict[str, Any]:
    """Replay captured export through ``build_rst_core_backbone_staging_runtime_evidence_verification_report`` unchanged."""
    return build_rst_core_backbone_staging_runtime_evidence_verification_report(
        staging_evidence_bundle=dict(staging_export_bundle),
        generated_at_iso=generated_at_iso,
    )


def validate_staging_export_replay_realism(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    convergence_snapshot: Mapping[str, Any],
    propagation_continuity: Mapping[str, Any],
) -> Dict[str, Any]:
    """Replay-specific continuity: replay flags, duplicates, reconciliation visibility, degraded paths."""
    findings: List[str] = []
    replay_trace_n = sum(1 for t in transition_traces if bool(t.get("replay_chain_detected")))
    for tr in transition_traces:
        rows = burn_in_downstream_rows(tr)
        if bool(tr.get("replay_chain_detected")):
            if not rows:
                findings.append("replay_realism_replay_chain_collapse_empty_downstream")
            elif not any(str(r.get("propagation_stage") or "").strip() for r in rows):
                findings.append("replay_realism_replay_downstream_missing_propagation_stage_visibility")
            else:
                has_recalc = any(_RECALC_SUB in str(r.get("downstream_target") or "") for r in rows)
                has_regen = any(_REGEN_SUB in str(r.get("downstream_target") or "") for r in rows)
                if has_recalc and not has_regen:
                    findings.append("replay_realism_replay_path_regen_delegate_lineage_gap")
        for r in rows:
            oc = str(r.get("enqueue_outcome") or "")
            if oc == ENQUEUE_DUPLICATE_SUPPRESSED and not str(r.get("propagation_stage") or "").strip():
                findings.append("replay_realism_duplicate_suppression_missing_propagation_stage")
            if oc == ENQUEUE_DEGRADED and not str(r.get("propagation_stage") or "").strip():
                findings.append("replay_realism_degraded_enqueue_missing_propagation_stage")
            if oc == ENQUEUE_DEGRADED and not (r.get("activation_guard_result") or r.get("activation_state")):
                findings.append("replay_realism_degraded_enqueue_missing_activation_overlay")

    recon_hidden = 0
    cem = convergence_snapshot.get("convergence_evidence_matrix") if isinstance(convergence_snapshot, Mapping) else {}
    mrows = cem.get("matrix_rows") if isinstance(cem, Mapping) else []
    row_list = [r for r in mrows if isinstance(r, Mapping)] if isinstance(mrows, list) else []
    for r in row_list:
        if str(r.get("reconciliation_visibility") or "") == RECONCILIATION_NOT_VISIBLE:
            recon_hidden += 1
    if replay_trace_n >= 1 and recon_hidden > max(len(row_list) // 2, 2) and len(row_list) >= 3:
        findings.append("replay_realism_reconciliation_visibility_gap_under_replay_sample")

    coex = propagation_continuity.get("coexistence") if isinstance(propagation_continuity.get("coexistence"), Mapping) else {}
    if replay_trace_n >= 1 and not (coex.get("has_recalc_downstream") or coex.get("has_regen_downstream")):
        findings.append("replay_realism_replay_sample_without_downstream_coexistence_visibility")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "replay_trace_signal_count": replay_trace_n,
        "schema_version": "staging_export_replay_realism_v1",
    }


def validate_staging_export_rollback_truth(
    *,
    bundle: Mapping[str, Any],
    harness: Mapping[str, Any],
    stale_degraded_visibility: Mapping[str, Any],
) -> Dict[str, Any]:
    """Rollback posture + export artifacts + convergence visibility survival (read-only)."""
    rb = validate_staging_export_rollback_realism(bundle=bundle, harness=harness)
    findings = list(rb.get("artifact_specific_finding_codes") or [])
    vis = str(stale_degraded_visibility.get("visibility_band") or "")
    ep = harness.get("evidence_pack") if isinstance(harness.get("evidence_pack"), Mapping) else {}
    has_rb_ep = isinstance(ep.get("rollback_validation_summary"), Mapping)
    dual = harness.get("dual_family_staging_validation") if isinstance(harness.get("dual_family_staging_validation"), Mapping) else {}
    has_dual_rb = isinstance((dual.get("combined_activation_rollback_summary") or {}).get("rollback_summary"), Mapping)
    if vis == "opaque" and (has_rb_ep or has_dual_rb):
        findings.append("rollback_truth_convergence_visibility_opaque_with_rollback_summary_review_matrix")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    out = dict(rb)
    out["artifact_specific_finding_codes"] = sorted(set(findings))
    out["activation_validation"] = cls
    out["schema_version"] = "staging_export_rollback_truth_v1"
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def _collect_all_replay_finding_codes(base_report: Mapping[str, Any], replay_realism: Mapping[str, Any]) -> List[str]:
    codes: List[str] = []
    for block_name in (
        "phase2a_rst_core_backbone_runtime_validation",
        "propagation_integrity_surface",
        "convergence_integrity",
        "cross_artifact_alignment",
        "rollback_realism",
    ):
        blk = base_report.get(block_name)
        if isinstance(blk, Mapping):
            for fc in blk.get("finding_codes") or []:
                codes.append(str(fc))
            if block_name == "phase2a_rst_core_backbone_runtime_validation":
                for subkey in blk:
                    sub = blk.get(subkey)
                    if isinstance(sub, Mapping) and sub.get("finding_codes"):
                        for fc in sub["finding_codes"]:
                            codes.append(str(fc))
    for fc in replay_realism.get("finding_codes") or []:
        codes.append(str(fc))
    return sorted(set(codes))


def classify_runtime_divergence_from_replay_signals(
    *,
    verification_report: Mapping[str, Any],
    replay_realism: Mapping[str, Any],
) -> Dict[str, Any]:
    """Deterministic divergence tier from replayed validation outputs (advisory)."""
    score = 0
    signals: List[str] = []
    phase2a = verification_report.get("phase2a_rst_core_backbone_runtime_validation") if isinstance(
        verification_report.get("phase2a_rst_core_backbone_runtime_validation"), Mapping
    ) else {}
    rollup = str(phase2a.get("rollup_activation_validation") or "")
    if rollup == VALIDATION_FAILED:
        score += 100
        signals.append("divergence_phase2a_rollup_failed")
    elif rollup == VALIDATION_INSUFFICIENT_EVIDENCE:
        score += 55
        signals.append("divergence_phase2a_insufficient_evidence")
    elif rollup == VALIDATION_PARTIAL:
        score += 38
        signals.append("divergence_phase2a_rollup_partial")

    conv = verification_report.get("convergence_integrity") if isinstance(verification_report.get("convergence_integrity"), Mapping) else {}
    if str(conv.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        score += 28
        signals.append("divergence_convergence_surface_partial_or_worse")
        for fc in conv.get("finding_codes") or []:
            fcs = str(fc)
            if "collapse" in fcs or "join_weak_dominant" in fcs:
                score += 15
                signals.append(f"divergence_convergence_signal:{fcs}")

    cross = verification_report.get("cross_artifact_alignment") if isinstance(verification_report.get("cross_artifact_alignment"), Mapping) else {}
    if str(cross.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        score += 22
        signals.append("divergence_cross_artifact_mismatch")

    prop_surf = verification_report.get("propagation_integrity_surface") if isinstance(
        verification_report.get("propagation_integrity_surface"), Mapping
    ) else {}
    if str(prop_surf.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        score += 18
        signals.append("divergence_propagation_surface_partial")
        for fc in prop_surf.get("finding_codes") or []:
            if "replay_chain_collapse" in str(fc) or "orphan" in str(fc):
                score += 12
                signals.append(f"divergence_propagation_signal:{fc}")

    gov = verification_report.get("governance_runtime_alignment_phase2a") if isinstance(
        verification_report.get("governance_runtime_alignment_phase2a"), Mapping
    ) else {}
    if str(gov.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        score += 25
        signals.append("divergence_governance_runtime_alignment_partial")

    rb = verification_report.get("rollback_realism") if isinstance(verification_report.get("rollback_realism"), Mapping) else {}
    if str(rb.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        score += 20
        signals.append("divergence_rollback_realism_partial")

    degraded = phase2a.get("degraded_path_signals") if isinstance(phase2a.get("degraded_path_signals"), Mapping) else {}
    if str(degraded.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        score += 15
        signals.append("divergence_degraded_path_signals_partial")

    if str(replay_realism.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        score += 24
        signals.append("divergence_replay_realism_partial")

    realism = verification_report.get("runtime_evidence_realism") if isinstance(verification_report.get("runtime_evidence_realism"), Mapping) else {}
    if str(realism.get("classification") or "") == RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT:
        score += 30
        signals.append("divergence_runtime_evidence_synthetic_dominant_sample")

    if score >= 85:
        cls = CRITICAL_RUNTIME_DIVERGENCE
    elif score >= 58:
        cls = HIGH_RUNTIME_DIVERGENCE
    elif score >= 35:
        cls = MODERATE_RUNTIME_DIVERGENCE
    elif score >= 12:
        cls = LOW_RUNTIME_DIVERGENCE
    else:
        cls = NO_RUNTIME_DIVERGENCE

    return {
        "contributing_signals": sorted(set(signals)),
        "divergence_score": score,
        "finding_codes_all_surfaces": _collect_all_replay_finding_codes(verification_report, replay_realism),
        "runtime_divergence_classification": cls,
        "schema_version": "runtime_divergence_classification_v1",
    }


def classify_operational_truth_export_replay(
    *,
    divergence_classification: str,
    realism_classification: str,
    staging_confidence_classification: str,
    replay_realism: Mapping[str, Any],
) -> str:
    """Operational truth tier from replay + divergence (deterministic)."""
    if str(realism_classification or "") == RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT:
        return OPERATIONAL_TRUTH_SYNTHETIC_DOMINANT
    if divergence_classification == CRITICAL_RUNTIME_DIVERGENCE:
        return OPERATIONAL_TRUTH_REQUIRES_REVIEW
    if staging_confidence_classification == STAGING_CONFIDENCE_DRIFT_VISIBLE:
        return OPERATIONAL_TRUTH_DRIFT_VISIBLE
    if staging_confidence_classification == STAGING_CONFIDENCE_OBSERVE_ONLY:
        return OPERATIONAL_TRUTH_PARTIAL
    if divergence_classification == HIGH_RUNTIME_DIVERGENCE:
        return OPERATIONAL_TRUTH_DEGRADED
    if staging_confidence_classification in (STAGING_CONFIDENCE_DEGRADED, STAGING_CONFIDENCE_REQUIRES_REVIEW):
        return OPERATIONAL_TRUTH_REQUIRES_REVIEW if divergence_classification != NO_RUNTIME_DIVERGENCE else OPERATIONAL_TRUTH_PARTIAL
    if divergence_classification in (MODERATE_RUNTIME_DIVERGENCE, LOW_RUNTIME_DIVERGENCE):
        return OPERATIONAL_TRUTH_PARTIAL
    if str(replay_realism.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        return OPERATIONAL_TRUTH_PARTIAL
    if staging_confidence_classification == STAGING_CONFIDENCE_PARTIAL:
        return OPERATIONAL_TRUTH_PARTIAL
    if divergence_classification == NO_RUNTIME_DIVERGENCE and staging_confidence_classification == STAGING_CONFIDENCE_CONFIRMED:
        return OPERATIONAL_TRUTH_CONFIRMED
    return OPERATIONAL_TRUTH_PARTIAL


def derive_phase2b_export_replay_readiness_gate(
    *,
    operational_truth_classification: str,
    divergence_classification: str,
    replay_realism: Mapping[str, Any],
    verification_report: Mapping[str, Any],
    realism_classification: str,
) -> Dict[str, Any]:
    """Advisory Phase 2B gate from replay + divergence + truth (non-enforcing)."""
    p2 = (
        verification_report.get("phase2a_rst_core_backbone_runtime_validation")
        if isinstance(verification_report.get("phase2a_rst_core_backbone_runtime_validation"), Mapping)
        else {}
    )
    degraded_path = p2.get("degraded_path_signals") if isinstance(p2.get("degraded_path_signals"), Mapping) else {}
    rollup = str(p2.get("rollup_activation_validation") or "")
    readiness = READY_FOR_PHASE2B_REVIEW
    rationale = "export_replay_operational_truth_ready_for_phase2b_review_gate"

    if divergence_classification == CRITICAL_RUNTIME_DIVERGENCE:
        readiness = HOLD_PENDING_RUNTIME_TRUTH_ALIGNMENT
        rationale = "critical_runtime_divergence_hold_truth_alignment"
    elif operational_truth_classification == OPERATIONAL_TRUTH_SYNTHETIC_DOMINANT:
        readiness = HOLD_PENDING_RUNTIME_REALISM
        rationale = "operational_truth_synthetic_dominant_hold_runtime_realism"
    elif operational_truth_classification == OPERATIONAL_TRUTH_REQUIRES_REVIEW:
        readiness = HOLD_PENDING_RUNTIME_TRUTH_ALIGNMENT
        rationale = "operational_truth_requires_review_hold_truth_alignment"
    elif str(realism_classification or "") == RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT:
        readiness = HOLD_PENDING_RUNTIME_REALISM
        rationale = "synthetic_dominant_export_hold_runtime_realism"
    elif divergence_classification == HIGH_RUNTIME_DIVERGENCE:
        readiness = HOLD_PENDING_RUNTIME_TRUTH_ALIGNMENT
        rationale = "high_runtime_divergence_hold_truth_alignment"
    elif int(replay_realism.get("replay_trace_signal_count") or 0) >= 1 and str(replay_realism.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_REPLAY_ALIGNMENT
        rationale = "replay_signals_present_but_replay_realism_partial"
    elif str(degraded_path.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_DEGRADED_PATH_ALIGNMENT
        rationale = "degraded_path_signals_partial_hold_alignment"
    elif str((verification_report.get("convergence_integrity") or {}).get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_CONVERGENCE_ALIGNMENT
        rationale = "convergence_surface_partial_hold_alignment"
    elif str((verification_report.get("cross_artifact_alignment") or {}).get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_GOVERNANCE_ALIGNMENT
        rationale = "governance_runtime_cross_artifact_partial_hold_alignment"
    elif operational_truth_classification == OPERATIONAL_TRUTH_PARTIAL:
        readiness = HOLD_PENDING_RUNTIME_TRUTH_ALIGNMENT
        rationale = "operational_truth_partial_hold_truth_alignment"
    elif rollup != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_RUNTIME_TRUTH_ALIGNMENT
        rationale = "phase2a_rollup_not_confirmed_hold_truth_alignment"

    return {
        "advisory_only": True,
        "non_blocking": True,
        "phase2a_rollup_activation_validation": rollup,
        "rationale_code": rationale,
        "readiness_classification": readiness,
        "schema_version": "phase2b_export_replay_readiness_gate_v1",
    }


def build_export_replay_operational_summaries(
    *,
    divergence: Mapping[str, Any],
    operational_truth: str,
    replay_realism: Mapping[str, Any],
    rollback_truth: Mapping[str, Any],
    verification_report: Mapping[str, Any],
    readiness_gate: Mapping[str, Any],
) -> Dict[str, Any]:
    """Extended operational summaries for export replay review."""
    phase2a = verification_report.get("phase2a_rst_core_backbone_runtime_validation") if isinstance(
        verification_report.get("phase2a_rst_core_backbone_runtime_validation"), Mapping
    ) else {}
    degraded = phase2a.get("degraded_path_signals") if isinstance(phase2a.get("degraded_path_signals"), Mapping) else {}
    conv_realism = verification_report.get("runtime_evidence_realism") if isinstance(
        verification_report.get("runtime_evidence_realism"), Mapping
    ) else {}
    vis = verification_report.get("stale_degraded_visibility") if isinstance(verification_report.get("stale_degraded_visibility"), Mapping) else {}
    gov = verification_report.get("governance_runtime_alignment_phase2a") if isinstance(
        verification_report.get("governance_runtime_alignment_phase2a"), Mapping
    ) else {}
    return {
        "convergence_realism_summary": {
            "join_weak_ratio": conv_realism.get("join_weak_ratio"),
            "matrix_reconciliation_not_visible_rows": conv_realism.get("convergence_matrix_reconciliation_not_visible_rows"),
            "matrix_stale_rows": conv_realism.get("convergence_matrix_stale_rows"),
        },
        "degraded_path_realism_summary": {
            "activation_validation": degraded.get("activation_validation"),
            "finding_codes": degraded.get("finding_codes"),
            "informational_observation_codes": degraded.get("informational_observation_codes"),
        },
        "governance_runtime_truth_summary": {
            "activation_validation": gov.get("activation_validation"),
            "finding_codes": gov.get("finding_codes"),
        },
        "operational_truth_summary": {"classification": operational_truth},
        "phase2b_review_confidence_summary": {
            "readiness_classification": readiness_gate.get("readiness_classification"),
            "rationale_code": readiness_gate.get("rationale_code"),
        },
        "replay_realism_summary": {
            "activation_validation": replay_realism.get("activation_validation"),
            "finding_codes": replay_realism.get("finding_codes"),
            "replay_trace_signal_count": replay_realism.get("replay_trace_signal_count"),
        },
        "replay_validation_summary": {
            "verification_schema_version": verification_report.get("schema_version"),
            "trace_digest_sha256": verification_report.get("transition_traces_digest_sha256"),
            "trace_sample_count": verification_report.get("trace_sample_count"),
        },
        "rollback_truth_summary": {
            "activation_validation": rollback_truth.get("activation_validation"),
            "artifact_specific_finding_codes": rollback_truth.get("artifact_specific_finding_codes"),
        },
        "runtime_divergence_summary": {
            "classification": divergence.get("runtime_divergence_classification"),
            "divergence_score": divergence.get("divergence_score"),
            "signals": divergence.get("contributing_signals"),
        },
        "schema_version": "export_replay_operational_summaries_v1",
        "stale_visibility_summary": {
            "visibility_band": vis.get("visibility_band"),
            "replay_trace_level_signal_count": vis.get("replay_trace_level_signal_count"),
        },
    }


def build_rst_core_backbone_staging_export_replay_validation_report(
    *,
    staging_capture_bundle: Mapping[str, Any],
    generated_at_iso: str,
) -> Dict[str, Any]:
    """
    Full export capture → coalesce → replay through verification stack → divergence + truth + gate.

    No execution of queues/workers; uses exports as-is after optional envelope unwrapping only.
    """
    coalesced, coalescing_applied = coalesce_staging_export_roots(staging_capture_bundle)
    bundle_for_verify = dict(coalesced)

    verification_report = replay_staging_export_through_verification_stack(
        staging_export_bundle=bundle_for_verify,
        generated_at_iso=generated_at_iso,
    )

    traces = extract_transition_traces(bundle_for_verify)
    conv = extract_convergence_snapshot(bundle_for_verify)
    harness = assemble_harness_for_staging_verification(bundle_for_verify)
    propagation = verification_report.get("propagation_continuity") if isinstance(verification_report.get("propagation_continuity"), Mapping) else {}

    replay_realism = validate_staging_export_replay_realism(
        transition_traces=traces,
        convergence_snapshot=conv,
        propagation_continuity=propagation,
    )
    visibility = verification_report.get("stale_degraded_visibility") if isinstance(
        verification_report.get("stale_degraded_visibility"), Mapping
    ) else {}
    rollback_truth = validate_staging_export_rollback_truth(
        bundle=bundle_for_verify,
        harness=harness,
        stale_degraded_visibility=visibility,
    )

    divergence = classify_runtime_divergence_from_replay_signals(
        verification_report=verification_report,
        replay_realism=replay_realism,
    )

    operational_truth = classify_operational_truth_export_replay(
        divergence_classification=str(divergence.get("runtime_divergence_classification") or ""),
        realism_classification=str((verification_report.get("runtime_evidence_realism") or {}).get("classification") or ""),
        staging_confidence_classification=str(verification_report.get("staging_confidence_classification") or ""),
        replay_realism=replay_realism,
    )

    readiness_gate = derive_phase2b_export_replay_readiness_gate(
        operational_truth_classification=operational_truth,
        divergence_classification=str(divergence.get("runtime_divergence_classification") or ""),
        replay_realism=replay_realism,
        verification_report=verification_report,
        realism_classification=str((verification_report.get("runtime_evidence_realism") or {}).get("classification") or ""),
    )

    summaries = build_export_replay_operational_summaries(
        divergence=divergence,
        operational_truth=operational_truth,
        replay_realism=replay_realism,
        rollback_truth=rollback_truth,
        verification_report=verification_report,
        readiness_gate=readiness_gate,
    )

    report: Dict[str, Any] = {
        "audit_only": True,
        "export_coalescing_applied": coalescing_applied,
        "generated_at_iso": generated_at_iso,
        "non_blocking": True,
        "operational_truth_classification": operational_truth,
        "operational_summaries": summaries,
        "readiness_gate_phase2b_export_replay": readiness_gate,
        "replay_realism": replay_realism,
        "replay_validation": {
            "replay_ordered_verification_report": verification_report,
            "schema_version": "staging_export_replay_validation_wrapper_v1",
        },
        "rollback_truth": rollback_truth,
        "runtime_divergence": divergence,
        "schema_version": EXPORT_REPLAY_VALIDATION_SCHEMA_VERSION,
    }
    return dict(sorted(report.items(), key=lambda kv: str(kv[0])))


def export_replay_capture_supported_envelope_keys() -> Tuple[str, ...]:
    """Backward compatibility: documented capture wrapper keys."""
    return (
        "raw_staging_export",
        "convergence_export",
        "runtime_evidence_pack_export",
        "governance_export",
        "operational_burn_in_export",
        "frozen_governance_bundle_export",
    )
