"""
Phase 2B: read-only dual-family (COMPLIANCE_SCORE_RECALC + REGENERATION_RECALC) staging validation.

Advisory only. No activation changes, no new registry families, no persistence.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from services.workflow_activation_readiness import (
    FAMILY_COMPLIANCE_SCORE_RECALC,
    FAMILY_REGENERATION_RECALC,
    FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
)
from services.workflow_runtime_activation_registry import (
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
)
from services.workflow_runtime_activation_validation import (
    CRITICAL_VALIDATION_DRIFT,
    HIGH_VALIDATION_DRIFT,
    OBSERVABILITY_CONFIRMED,
    VALIDATION_CONFIRMED,
    VALIDATION_FAILED,
    VALIDATION_INSUFFICIENT_EVIDENCE,
    VALIDATION_PARTIAL,
    build_activation_rollback_summary,
    build_runtime_activation_validation_snapshot,
    validate_downstream_activation_metadata,
    validate_governance_runtime_activation_visibility,
)

DUAL_FAMILY_VALIDATION_SCHEMA_VERSION = "workflow_runtime_activation_dual_family_validation_v1"

# --- Staging-readiness (advisory; must not drive activation logic) ---
DUAL_FAMILY_STAGING_CONFIRMED = "DUAL_FAMILY_STAGING_CONFIRMED"
DUAL_FAMILY_STAGING_PARTIAL = "DUAL_FAMILY_STAGING_PARTIAL"
DUAL_FAMILY_STAGING_DEGRADED = "DUAL_FAMILY_STAGING_DEGRADED"
DUAL_FAMILY_STAGING_DRIFT_VISIBLE = "DUAL_FAMILY_STAGING_DRIFT_VISIBLE"
DUAL_FAMILY_STAGING_OBSERVE_ONLY = "DUAL_FAMILY_STAGING_OBSERVE_ONLY"

_EXPECTED_SCOPES = {
    FAMILY_COMPLIANCE_SCORE_RECALC: "compliance_recalc_enqueue_only",
    FAMILY_REGENERATION_RECALC: "risk_signal_regen_enqueue_only",
}

_RECALC_T = "compliance_recalc_queue.enqueue_compliance_recalc"
_REGEN_T = "risk_signal_regen_queue.enqueue_risk_signal_regen"


def _rows_from_runtime_snapshot(rt: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    rows = rt.get("families") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, Mapping)]


def validate_dual_family_gate_alignment(*, validation_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Both resolver gates consistent with registry snapshot rows (read-only)."""
    findings: List[str] = []
    cg = validation_snapshot.get("gate_validation") if isinstance(validation_snapshot.get("gate_validation"), Mapping) else {}
    rg = (
        validation_snapshot.get("regeneration_recalc_gate_validation")
        if isinstance(validation_snapshot.get("regeneration_recalc_gate_validation"), Mapping)
        else {}
    )
    cg_gate = cg.get("gate") if isinstance(cg.get("gate"), Mapping) else {}
    rg_gate = rg.get("gate") if isinstance(rg.get("gate"), Mapping) else {}

    rt = validation_snapshot.get("runtime_activation_snapshot")
    if not isinstance(rt, Mapping):
        findings.append("missing_runtime_activation_snapshot")
        cls = VALIDATION_FAILED
        return {
            "activation_validation": cls,
            "finding_codes": sorted(findings),
            "schema_version": "dual_family_gate_alignment_v1",
        }

    ver_rt = str(rt.get("activation_governance_version") or "")
    if ver_rt != ACTIVATION_GOVERNANCE_VERSION:
        findings.append("runtime_snapshot_governance_version_misaligned")

    by_fam: Dict[str, Mapping[str, Any]] = {}
    for row in _rows_from_runtime_snapshot(rt):
        fam = str(row.get("activation_family") or "")
        if fam in _EXPECTED_SCOPES or fam == FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE:
            by_fam[fam] = row

    for fam in (FAMILY_COMPLIANCE_SCORE_RECALC, FAMILY_REGENERATION_RECALC, FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE):
        if fam not in by_fam:
            findings.append(f"missing_runtime_row_for_{fam}")
            continue
        exp_scope = _EXPECTED_SCOPES.get(fam)
        if fam == FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE:
            if str(by_fam[fam].get("activation_scope") or "") != "requirement_state_transition_core_backbone_only":
                findings.append("runtime_scope_mismatch_for_rst_core_backbone")
        elif exp_scope and str(by_fam[fam].get("activation_scope") or "") != exp_scope:
            findings.append(f"runtime_scope_mismatch_for_{fam}")
        if str(by_fam[fam].get("activation_governance_version") or "") != ver_rt and ver_rt:
            findings.append(f"runtime_row_version_mismatch_for_{fam}")

    bb = validation_snapshot.get("rst_core_backbone_gate_validation") if isinstance(validation_snapshot.get("rst_core_backbone_gate_validation"), Mapping) else {}
    bb_gate = bb.get("gate") if isinstance(bb.get("gate"), Mapping) else {}

    if str(cg_gate.get("activation_governance_version") or "") != ver_rt:
        findings.append("compliance_gate_version_mismatch_vs_snapshot")
    if str(rg_gate.get("activation_governance_version") or "") != ver_rt:
        findings.append("regeneration_gate_version_mismatch_vs_snapshot")
    if str(bb_gate.get("activation_governance_version") or "") != ver_rt:
        findings.append("rst_core_backbone_gate_version_mismatch_vs_snapshot")
    if str(cg_gate.get("activation_scope") or "") != _EXPECTED_SCOPES[FAMILY_COMPLIANCE_SCORE_RECALC]:
        findings.append("compliance_gate_scope_misaligned")
    if str(rg_gate.get("activation_scope") or "") != _EXPECTED_SCOPES[FAMILY_REGENERATION_RECALC]:
        findings.append("regeneration_gate_scope_misaligned")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_FAILED if any("missing" in f for f in findings) else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "schema_version": "dual_family_gate_alignment_v1",
    }


def validate_dual_family_downstream_coexistence(*, transition_traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Recalc and regen downstream targets may coexist in the same trace set without ambiguity (advisory)."""
    findings: List[str] = []
    has_recalc = False
    has_regen = False
    for tr in transition_traces:
        rows = tr.get("downstream_trigger_targets") or tr.get("downstream_propagation") or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            tgt = str(row.get("downstream_target") or "")
            if _RECALC_T in tgt:
                has_recalc = True
            if _REGEN_T in tgt:
                has_regen = True
    if has_recalc and has_regen:
        pass  # coexistence confirmed
    elif has_recalc or has_regen:
        findings.append("dual_family_downstream_partial_only_one_gated_surface_observed")
    else:
        findings.append("dual_family_downstream_insufficient_no_gated_targets")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL if has_recalc or has_regen else VALIDATION_INSUFFICIENT_EVIDENCE
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "has_recalc_downstream": has_recalc,
        "has_regen_downstream": has_regen,
        "schema_version": "dual_family_downstream_coexistence_v1",
    }


def validate_dual_family_convergence_visibility(*, convergence_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Matrix / hotspots present for convergence visibility (no redesign)."""
    findings: List[str] = []
    cem = convergence_snapshot.get("convergence_evidence_matrix") if isinstance(convergence_snapshot, Mapping) else None
    rows = cem.get("matrix_rows") if isinstance(cem, Mapping) else None
    n_mx = len(rows) if isinstance(rows, list) else 0
    if n_mx == 0:
        findings.append("convergence_matrix_empty_visibility_reduced")

    hs = convergence_snapshot.get("runtime_convergence_hotspots") if isinstance(convergence_snapshot, Mapping) else {}
    if not isinstance(hs, Mapping):
        findings.append("convergence_hotspots_missing")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "convergence_matrix_row_count": n_mx,
        "finding_codes": sorted(findings),
        "schema_version": "dual_family_convergence_visibility_v1",
    }


def validate_dual_family_governance_evidence_posture(
    *,
    governance_report: Mapping[str, Any],
    evidence_pack: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Governance + optional evidence pack share stable dual-family posture (read-only)."""
    findings: List[str] = []
    gov_vis = validate_governance_runtime_activation_visibility(governance_report)
    findings.extend(list(gov_vis.get("finding_codes") or []))

    for key in (
        "runtime_activation_snapshot",
        "runtime_activation_rollout_visibility",
        "regeneration_activation_operational_visibility",
        "requirement_transition_core_backbone_activation_operational_visibility",
    ):
        if key not in governance_report:
            findings.append(f"governance_missing_dual_family_section_{key}")

    if evidence_pack is not None and "activation_validation_snapshot" not in evidence_pack:
        findings.append("evidence_pack_missing_activation_validation_snapshot")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_FAILED if gov_vis.get("activation_validation") == VALIDATION_FAILED else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "schema_version": "dual_family_governance_evidence_posture_v1",
    }


def validate_registry_v2_governance_load_signal(*, governance_report: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Advisory: detect whether governance drift counters are elevated (not causal proof of registry v2).

    Does not assert v1 vs v2 causality — only surfaces co-occurrence for human review.
    """
    findings: List[str] = []
    gdr = governance_report.get("governance_drift_summary")
    n = int(gdr.get("governance_drift_detected_count") or 0) if isinstance(gdr, Mapping) else 0
    esc = int(gdr.get("governance_review_escalation_recommended_count") or 0) if isinstance(gdr, Mapping) else 0
    if n > 3:
        findings.append("governance_drift_count_elevated_review_dual_family_context")
    if esc > 0:
        findings.append("governance_escalation_recommended_review_dual_family_context")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "schema_version": "registry_v2_governance_load_signal_v1",
    }


def build_dual_family_combined_activation_continuity_summary(validation_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    from services.workflow_runtime_activation_validation import build_activation_continuity_summary

    base = build_activation_continuity_summary(validation_snapshot)
    return {
        "combined_by_queue_continuity": dict(base.get("by_queue_continuity") or {}),
        "schema_version": "dual_family_combined_continuity_summary_v1",
        "source_schema": base.get("schema_version"),
    }


def build_dual_family_combined_activation_drift_summary(validation_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    drift = validation_snapshot.get("drift") if isinstance(validation_snapshot.get("drift"), Mapping) else {}
    return {
        "drift_classification": drift.get("drift_classification"),
        "finding_codes": list(drift.get("finding_codes") or []),
        "schema_version": "dual_family_combined_drift_summary_v1",
    }


def build_dual_family_combined_activation_rollback_summary() -> Dict[str, Any]:
    rb = build_activation_rollback_summary()
    return {
        "rollback_summary": rb,
        "schema_version": "dual_family_combined_rollback_summary_v1",
    }


def build_dual_family_combined_activation_observability_summary(validation_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    obs_counts: Dict[str, int] = {}
    for bucket in ("enqueue_sample_validations", "regeneration_enqueue_sample_validations"):
        for sample in validation_snapshot.get(bucket) or []:
            if not isinstance(sample, Mapping):
                continue
            for sub in ("continuity", "observability"):
                b = sample.get(sub)
                if isinstance(b, Mapping):
                    if sub == "observability":
                        k = str(b.get("observability") or "UNKNOWN")
                        obs_counts[k] = obs_counts.get(k, 0) + 1
    down = validation_snapshot.get("transition_downstream_observability")
    if isinstance(down, Mapping):
        k = str(down.get("observability") or "UNKNOWN")
        obs_counts[k] = obs_counts.get(k, 0) + 1
    return {
        "by_observability_band": dict(sorted(obs_counts.items())),
        "dual_family_observability_integrity": (
            OBSERVABILITY_CONFIRMED if obs_counts and all(str(k) == OBSERVABILITY_CONFIRMED for k in obs_counts) else "MIXED"
        ),
        "schema_version": "dual_family_combined_observability_summary_v1",
    }


def build_dual_family_combined_activation_convergence_summary(
    *,
    convergence_snapshot: Mapping[str, Any],
    transition_traces: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    co = validate_dual_family_convergence_visibility(convergence_snapshot=convergence_snapshot)
    ds = validate_dual_family_downstream_coexistence(transition_traces=transition_traces)
    cem = convergence_snapshot.get("convergence_evidence_matrix") if isinstance(convergence_snapshot, Mapping) else {}
    rows = cem.get("matrix_rows") if isinstance(cem, Mapping) else []
    return {
        "convergence_matrix_row_count": co.get("convergence_matrix_row_count"),
        "downstream_coexistence": ds,
        "matrix_workflow_families": sorted({str(r.get("workflow_family") or "") for r in rows if isinstance(r, Mapping)}),
        "schema_version": "dual_family_combined_convergence_summary_v1",
    }


def classify_dual_family_staging_readiness(
    *,
    validation_snapshot: Mapping[str, Any],
    convergence_snapshot: Mapping[str, Any],
    governance_report: Mapping[str, Any],
    transition_traces: Sequence[Mapping[str, Any]],
    evidence_pack: Optional[Mapping[str, Any]] = None,
) -> str:
    """Advisory staging-readiness band (deterministic). Must not be consumed by activation enforcement."""
    rt = validation_snapshot.get("runtime_activation_snapshot")
    if isinstance(rt, Mapping):
        for row in _rows_from_runtime_snapshot(rt):
            if str(row.get("activation_family") or "") in _EXPECTED_SCOPES and str(row.get("activation_state") or "") == ACTIVATION_OBSERVE_ONLY:
                return DUAL_FAMILY_STAGING_OBSERVE_ONLY

    drift = (validation_snapshot.get("drift") or {}).get("drift_classification")
    overall = str(validation_snapshot.get("overall_activation_validation") or "")

    gate_al = validate_dual_family_gate_alignment(validation_snapshot=validation_snapshot)
    gov_ev = validate_dual_family_governance_evidence_posture(governance_report=governance_report, evidence_pack=evidence_pack)
    conv = validate_dual_family_convergence_visibility(convergence_snapshot=convergence_snapshot)
    coex = validate_dual_family_downstream_coexistence(transition_traces=transition_traces)

    parts = (
        gate_al.get("activation_validation"),
        gov_ev.get("activation_validation"),
        conv.get("activation_validation"),
        coex.get("activation_validation"),
    )
    if any(x == VALIDATION_FAILED for x in parts) or overall == VALIDATION_FAILED:
        return DUAL_FAMILY_STAGING_DEGRADED
    if drift in (CRITICAL_VALIDATION_DRIFT, HIGH_VALIDATION_DRIFT):
        return DUAL_FAMILY_STAGING_DRIFT_VISIBLE
    if any(x in (VALIDATION_PARTIAL, VALIDATION_INSUFFICIENT_EVIDENCE) for x in parts) or overall == VALIDATION_PARTIAL:
        return DUAL_FAMILY_STAGING_PARTIAL
    return DUAL_FAMILY_STAGING_CONFIRMED


def build_dual_family_staging_validation_snapshot(
    *,
    generated_at_iso: str,
    governance_report: Mapping[str, Any],
    convergence_snapshot: Mapping[str, Any],
    transition_traces: Sequence[Mapping[str, Any]],
    compliance_enqueue_samples: Optional[Sequence[Tuple[Mapping[str, Any], Any]]] = None,
    regeneration_enqueue_samples: Optional[Sequence[Tuple[Mapping[str, Any], Mapping[str, Any]]]] = None,
    evidence_pack: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Single read-only dual-family staging validation artifact.

    Reuses ``build_runtime_activation_validation_snapshot`` (no registry mutation).
    """
    traces_list = [dict(t) if isinstance(t, Mapping) else {} for t in transition_traces]
    traces_list.sort(key=lambda t: (str(t.get("transition_id") or ""), str(t.get("correlation_id") or "")))

    validation_snapshot = build_runtime_activation_validation_snapshot(
        generated_at_iso=generated_at_iso,
        governance_report=dict(governance_report),
        transition_traces=traces_list,
        enqueue_samples=compliance_enqueue_samples,
        regeneration_enqueue_samples=regeneration_enqueue_samples,
    )

    gate_alignment = validate_dual_family_gate_alignment(validation_snapshot=validation_snapshot)
    downstream_meta = validate_downstream_activation_metadata(transition_traces=traces_list)
    coexistence = validate_dual_family_downstream_coexistence(transition_traces=traces_list)
    convergence_vis = validate_dual_family_convergence_visibility(convergence_snapshot=convergence_snapshot)
    gov_posture = validate_dual_family_governance_evidence_posture(governance_report=governance_report, evidence_pack=evidence_pack)
    v2_signal = validate_registry_v2_governance_load_signal(governance_report=governance_report)

    staging_readiness = classify_dual_family_staging_readiness(
        validation_snapshot=validation_snapshot,
        convergence_snapshot=convergence_snapshot,
        governance_report=governance_report,
        transition_traces=traces_list,
        evidence_pack=evidence_pack,
    )

    out: Dict[str, Any] = {
        "combined_activation_continuity_summary": build_dual_family_combined_activation_continuity_summary(validation_snapshot),
        "combined_activation_convergence_summary": build_dual_family_combined_activation_convergence_summary(
            convergence_snapshot=convergence_snapshot,
            transition_traces=traces_list,
        ),
        "combined_activation_drift_summary": build_dual_family_combined_activation_drift_summary(validation_snapshot),
        "combined_activation_observability_summary": build_dual_family_combined_activation_observability_summary(validation_snapshot),
        "combined_activation_rollback_summary": build_dual_family_combined_activation_rollback_summary(),
        "downstream_metadata_validation": downstream_meta,
        "dual_family_downstream_coexistence": coexistence,
        "dual_family_gate_alignment": gate_alignment,
        "dual_family_governance_evidence_posture": gov_posture,
        "dual_family_staging_readiness_classification": staging_readiness,
        "generated_at_iso": generated_at_iso,
        "registry_v2_governance_load_signal": v2_signal,
        "schema_version": DUAL_FAMILY_VALIDATION_SCHEMA_VERSION,
        "validation_snapshot": validation_snapshot,
    }
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def build_dual_family_staging_validation_from_evidence_pack(
    pack: Mapping[str, Any],
    *,
    governance_report_full: Mapping[str, Any],
    convergence_snapshot: Mapping[str, Any],
    transition_traces: Sequence[Mapping[str, Any]],
    compliance_enqueue_samples: Optional[Sequence[Tuple[Mapping[str, Any], Any]]] = None,
    regeneration_enqueue_samples: Optional[Sequence[Tuple[Mapping[str, Any], Mapping[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Convenience: dual snapshot using evidence pack + full governance report (read-only)."""
    generated_at = str(pack.get("generated_at") or "")
    return build_dual_family_staging_validation_snapshot(
        generated_at_iso=generated_at,
        governance_report=governance_report_full,
        convergence_snapshot=dict(convergence_snapshot),
        transition_traces=transition_traces,
        compliance_enqueue_samples=compliance_enqueue_samples,
        regeneration_enqueue_samples=regeneration_enqueue_samples,
        evidence_pack=dict(pack),
    )
