"""
Operational burn-in & staging runtime validation for the shared limited recalc backbone.

Read-only assembly of staging-style traces into convergence, governance, evidence-pack,
and dual-family validation artifacts. Advisory classifications must not drive activation.

Phase 2A: validates COMPLIANCE_SCORE_RECALC + REGENERATION_RECALC + RST core backbone
(REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE) without widening activation scope.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from services.workflow_activation_readiness import (
    FAMILY_COMPLIANCE_SCORE_RECALC,
    FAMILY_REGENERATION_RECALC,
    FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
)
from services.workflow_runtime_activation_dual_family_validation import (
    DUAL_FAMILY_STAGING_CONFIRMED,
    DUAL_FAMILY_STAGING_DEGRADED,
    DUAL_FAMILY_STAGING_DRIFT_VISIBLE,
    DUAL_FAMILY_STAGING_OBSERVE_ONLY,
    DUAL_FAMILY_STAGING_PARTIAL,
    build_dual_family_staging_validation_snapshot,
    validate_dual_family_downstream_coexistence,
)
from services.workflow_runtime_activation_evidence_pack import (
    build_runtime_activation_evidence_pack,
    compliance_enqueue_samples_as_result_tuples,
    regeneration_enqueue_samples_as_mapping_tuples,
)
from services.workflow_runtime_activation_registry import (
    ACTIVATION_DISABLED,
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
    build_rst_core_backbone_activation_operational_visibility,
)
from services.workflow_runtime_activation_validation import (
    CRITICAL_VALIDATION_DRIFT,
    HIGH_VALIDATION_DRIFT,
    LOW_VALIDATION_DRIFT,
    MODERATE_VALIDATION_DRIFT,
    VALIDATION_CONFIRMED,
    VALIDATION_FAILED,
    VALIDATION_INSUFFICIENT_EVIDENCE,
    VALIDATION_PARTIAL,
    validate_registry_rollback_posture,
    validate_rst_core_backbone_convergence_continuity,
)
from services.workflow_runtime_convergence_observability import (
    RECONCILIATION_NOT_VISIBLE,
    build_runtime_convergence_snapshot,
)
from services.requirement_transition_observability import (
    ENQUEUE_ACCEPTED,
    ENQUEUE_DEGRADED,
    ENQUEUE_DUPLICATE_SUPPRESSED,
    ENQUEUE_SKIPPED,
)

OPERATIONAL_BURN_IN_SCHEMA_VERSION = "operational_burn_in_report_v1"
PHASE2A_RST_CORE_BACKBONE_BURN_IN_VALIDATION_SCHEMA_VERSION = "phase2a_rst_core_backbone_burn_in_validation_v1"

_RECALC_TARGET_SUBSTR = "compliance_recalc_queue.enqueue_compliance_recalc"
_REGEN_TARGET_SUBSTR = "risk_signal_regen_queue.enqueue_risk_signal_regen"
_GAP_SYNC_TARGET_SUBSTR = "compliance_gap_sync"
_AUTHORITY_BACKBONE_SKIP_TARGET_SUBSTR = "requirement_state_transition.core_backbone.authority_sync"

# --- Representative staging flow kinds (ordering deterministic; advisory labels only) ---
STAGING_FLOW_DOCUMENT_UPLOAD = "STAGING_FLOW_DOCUMENT_UPLOAD"
STAGING_FLOW_DOCUMENT_VERIFY = "STAGING_FLOW_DOCUMENT_VERIFY"
STAGING_FLOW_EVIDENCE_REVIEW_APPROVAL = "STAGING_FLOW_EVIDENCE_REVIEW_APPROVAL"
STAGING_FLOW_EVIDENCE_REVIEW_REJECTION = "STAGING_FLOW_EVIDENCE_REVIEW_REJECTION"
STAGING_FLOW_ADMIN_RELINK = "STAGING_FLOW_ADMIN_RELINK"
STAGING_FLOW_ADMIN_AUTHORITY_SYNC = "STAGING_FLOW_ADMIN_AUTHORITY_SYNC"
STAGING_FLOW_DECLARATION = "STAGING_FLOW_DECLARATION"
STAGING_FLOW_AI_EXTRACTION_CONFIRMATION = "STAGING_FLOW_AI_EXTRACTION_CONFIRMATION"
STAGING_FLOW_OUTCOME_ENGINE_AUTHORITY_REFRESH = "STAGING_FLOW_OUTCOME_ENGINE_AUTHORITY_REFRESH"
STAGING_FLOW_DOCUMENT_DELETE_REVERT = "STAGING_FLOW_DOCUMENT_DELETE_REVERT"

STAGING_RUNTIME_FLOW_KINDS: Tuple[str, ...] = (
    STAGING_FLOW_DOCUMENT_UPLOAD,
    STAGING_FLOW_DOCUMENT_VERIFY,
    STAGING_FLOW_EVIDENCE_REVIEW_APPROVAL,
    STAGING_FLOW_EVIDENCE_REVIEW_REJECTION,
    STAGING_FLOW_ADMIN_RELINK,
    STAGING_FLOW_ADMIN_AUTHORITY_SYNC,
    STAGING_FLOW_DECLARATION,
    STAGING_FLOW_AI_EXTRACTION_CONFIRMATION,
    STAGING_FLOW_OUTCOME_ENGINE_AUTHORITY_REFRESH,
    STAGING_FLOW_DOCUMENT_DELETE_REVERT,
)

# --- Burn-in bands (advisory; must not be consumed by runtime activation logic) ---
BURN_IN_CONFIRMED = "BURN_IN_CONFIRMED"
BURN_IN_PARTIAL = "BURN_IN_PARTIAL"
BURN_IN_DEGRADED = "BURN_IN_DEGRADED"
BURN_IN_DRIFT_VISIBLE = "BURN_IN_DRIFT_VISIBLE"
BURN_IN_OBSERVE_ONLY = "BURN_IN_OBSERVE_ONLY"
BURN_IN_REQUIRES_REVIEW = "BURN_IN_REQUIRES_REVIEW"

# --- Visibility bands for stale/degraded/replay surfaces ---
VISIBILITY_VISIBLE = "visible"
VISIBILITY_PARTIALLY_VISIBLE = "partially_visible"
VISIBILITY_OPAQUE = "opaque"

# --- Operational readiness (advisory; non-enforcing) ---
READY_FOR_CONTINUED_LIMITED_ACTIVATION = "READY_FOR_CONTINUED_LIMITED_ACTIVATION"
READY_FOR_PHASE2_REVIEW = "READY_FOR_PHASE2_REVIEW"
HOLD_PENDING_MORE_RUNTIME_EVIDENCE = "HOLD_PENDING_MORE_RUNTIME_EVIDENCE"
HOLD_PENDING_CONVERGENCE_ALIGNMENT = "HOLD_PENDING_CONVERGENCE_ALIGNMENT"
HOLD_PENDING_OBSERVABILITY_ALIGNMENT = "HOLD_PENDING_OBSERVABILITY_ALIGNMENT"
HOLD_PENDING_GOVERNANCE_REVIEW = "HOLD_PENDING_GOVERNANCE_REVIEW"


def _sort_key_trace(t: Mapping[str, Any]) -> Tuple[str, str]:
    return (str(t.get("transition_id") or ""), str(t.get("correlation_id") or ""))


def _downstream_rows(trace: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    rows = trace.get("downstream_trigger_targets") or trace.get("downstream_propagation") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, Mapping)]


def merge_staging_flow_traces_for_harness(
    flow_traces_by_kind: Mapping[str, Sequence[Mapping[str, Any]]],
) -> List[Dict[str, Any]]:
    """Deterministic merge with ``staging_runtime_flow_kind`` annotation (read-only copies)."""
    out: List[Dict[str, Any]] = []
    unknown_kinds: List[str] = []
    for kind in sorted(flow_traces_by_kind.keys()):
        seq = flow_traces_by_kind[kind]
        if kind not in STAGING_RUNTIME_FLOW_KINDS:
            unknown_kinds.append(kind)
        if not isinstance(seq, (list, tuple)):
            continue
        for t in sorted(seq, key=_sort_key_trace):
            d = dict(t) if isinstance(t, Mapping) else {}
            d["staging_runtime_flow_kind"] = kind
            out.append(d)
    out.sort(
        key=lambda tr: (
            str(tr.get("staging_runtime_flow_kind") or ""),
            str(tr.get("transition_id") or ""),
            str(tr.get("correlation_id") or ""),
        )
    )
    return out


def build_staging_runtime_evidence_harness(
    *,
    generated_at_iso: str,
    flow_traces_by_kind: Mapping[str, Sequence[Mapping[str, Any]]],
    queue_visibility: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    representative_enqueue_samples: Sequence[Mapping[str, Any]] = (),
    representative_regeneration_enqueue_samples: Sequence[Mapping[str, Any]] = (),
    governance_families: Optional[Sequence[str]] = None,
    embed_full_merged_traces: bool = True,
    representative_trace_sample_limit: int = 16,
) -> Dict[str, Any]:
    """
    Assemble convergence, governance report, evidence pack, and dual-family validation
    from per-flow-kind trace buckets (read-only).
    """
    merged = merge_staging_flow_traces_for_harness(flow_traces_by_kind)
    conv = build_runtime_convergence_snapshot(transition_traces=merged, generated_at_iso=generated_at_iso)

    gov_fams = governance_families if governance_families is not None else (
        FAMILY_COMPLIANCE_SCORE_RECALC,
        FAMILY_REGENERATION_RECALC,
    )

    evidence_pack = build_runtime_activation_evidence_pack(
        generated_at=generated_at_iso,
        transition_traces=merged,
        queue_visibility=queue_visibility,
        observability_summary=observability_summary,
        convergence_snapshot=conv,
        governance_families=gov_fams,
        representative_enqueue_samples=representative_enqueue_samples,
        representative_regeneration_enqueue_samples=representative_regeneration_enqueue_samples,
    )

    compliance_tuples = compliance_enqueue_samples_as_result_tuples(representative_enqueue_samples)
    regen_tuples = regeneration_enqueue_samples_as_mapping_tuples(representative_regeneration_enqueue_samples)

    from services.workflow_activation_governance_report import build_workflow_activation_governance_report

    governance_report_full = build_workflow_activation_governance_report(
        generated_at_iso=generated_at_iso,
        convergence_snapshot=conv,
        transition_traces=merged,
        queue_visibility=queue_visibility,
        observability_summary=observability_summary,
        families=gov_fams,
    )

    dual_family = build_dual_family_staging_validation_snapshot(
        generated_at_iso=generated_at_iso,
        governance_report=governance_report_full,
        convergence_snapshot=conv,
        transition_traces=merged,
        compliance_enqueue_samples=compliance_tuples or None,
        regeneration_enqueue_samples=regen_tuples or None,
        evidence_pack=dict(evidence_pack),
    )

    counts_by_kind = {k: 0 for k in STAGING_RUNTIME_FLOW_KINDS}
    for k, seq in flow_traces_by_kind.items():
        if k in counts_by_kind and isinstance(seq, (list, tuple)):
            counts_by_kind[k] = len(seq)

    unknown_flow_keys = sorted(k for k in flow_traces_by_kind.keys() if k not in STAGING_RUNTIME_FLOW_KINDS)

    harness: Dict[str, Any] = {
        "convergence_snapshot": conv,
        "dual_family_staging_validation": dual_family,
        "evidence_pack": dict(evidence_pack),
        "flow_trace_counts_by_kind": dict(sorted(counts_by_kind.items())),
        "generated_at_iso": generated_at_iso,
        "governance_report_full": governance_report_full,
        "merged_transition_trace_sample": merged[: max(0, representative_trace_sample_limit)],
        "merged_transition_traces": merged if embed_full_merged_traces else [],
        "merged_transition_traces_count": len(merged),
        "observability_summary_pass_through": dict(observability_summary) if observability_summary else {},
        "queue_visibility_pass_through": dict(queue_visibility) if queue_visibility else {},
        "representative_unknown_flow_keys": unknown_flow_keys,
        "rst_core_backbone_activation_operational_visibility": build_rst_core_backbone_activation_operational_visibility(
            generated_at_iso=generated_at_iso
        ),
        "schema_version": "staging_runtime_evidence_harness_v1",
    }
    return dict(sorted(harness.items(), key=lambda kv: str(kv[0])))


def validate_propagation_continuity_burn_in(*, transition_traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Counts enqueue/replay/regen/coexistence signals across traces (advisory)."""
    findings: List[str] = []
    n_accept = n_skip = n_dup = n_deg = n_recon_rec = 0
    replay_trace = regen_delegate = recalc_hit = 0
    backbone_trace_hits = 0
    for tr in transition_traces:
        if tr.get("rst_core_backbone_activation"):
            backbone_trace_hits += 1
        if bool(tr.get("replay_chain_detected")) or str(tr.get("transition_outcome") or "").endswith("REPLAY"):
            replay_trace += 1
        for row in _downstream_rows(tr):
            oc = str(row.get("enqueue_outcome") or "")
            if oc == ENQUEUE_ACCEPTED:
                n_accept += 1
            elif oc == ENQUEUE_SKIPPED:
                n_skip += 1
            elif oc == ENQUEUE_DUPLICATE_SUPPRESSED:
                n_dup += 1
            elif oc == ENQUEUE_DEGRADED:
                n_deg += 1
            if row.get("reconciliation_recommended"):
                n_recon_rec += 1
            tgt = str(row.get("downstream_target") or "")
            if "risk_signal_regen" in tgt:
                regen_delegate += 1
            if "compliance_recalc_queue.enqueue_compliance_recalc" in tgt:
                recalc_hit += 1

    coex = validate_dual_family_downstream_coexistence(transition_traces=transition_traces)
    if not coex.get("has_recalc_downstream") and not coex.get("has_regen_downstream"):
        findings.append("propagation_no_gated_downstream_observed")
    if recalc_hit and regen_delegate:
        pass
    elif recalc_hit or regen_delegate:
        findings.append("propagation_single_surface_only_in_sample")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "coexistence": coex,
        "downstream_enqueue_accepted_count": n_accept,
        "downstream_enqueue_degraded_count": n_deg,
        "downstream_enqueue_duplicate_suppressed_count": n_dup,
        "downstream_enqueue_skipped_count": n_skip,
        "downstream_reconciliation_recommended_count": n_recon_rec,
        "finding_codes": sorted(findings),
        "has_compliance_recalc_downstream_hits": recalc_hit > 0,
        "has_regen_delegate_rows": regen_delegate > 0,
        "replay_or_reentry_trace_signals": replay_trace,
        "rst_core_backbone_trace_hit_count": backbone_trace_hits,
        "schema_version": "burn_in_propagation_continuity_v1",
    }


def _rollup_phase2a_activation_validation(blocks: Sequence[Mapping[str, Any]]) -> str:
    order = {
        VALIDATION_CONFIRMED: 0,
        VALIDATION_PARTIAL: 1,
        VALIDATION_INSUFFICIENT_EVIDENCE: 2,
        VALIDATION_FAILED: 3,
    }
    worst = VALIDATION_CONFIRMED
    for b in blocks:
        if not isinstance(b, Mapping):
            continue
        v = str(b.get("activation_validation") or "")
        if order.get(v, -1) > order.get(worst, -1):
            worst = v
    return worst


def validate_rst_core_backbone_propagation_chain_phase2a_burn_in(
    *, transition_traces: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    """Advisory: staging traces expose gap → recalc → regen chain coherently when backbone permits."""
    findings: List[str] = []
    for tr in transition_traces:
        rows = _downstream_rows(tr)
        if not rows:
            continue
        has_recalc = any(_RECALC_TARGET_SUBSTR in str(r.get("downstream_target") or "") for r in rows)
        has_regen = any(_REGEN_TARGET_SUBSTR in str(r.get("downstream_target") or "") for r in rows)
        has_gap = any(_GAP_SYNC_TARGET_SUBSTR in str(r.get("downstream_target") or "") for r in rows)
        blob = tr.get("rst_core_backbone_activation")
        if has_recalc and not isinstance(blob, Mapping):
            findings.append("phase2a_propagation_recalc_without_rst_core_backbone_blob")
        if isinstance(blob, Mapping) and blob.get("permitted") and has_recalc:
            recalc_rows = [r for r in rows if _RECALC_TARGET_SUBSTR in str(r.get("downstream_target") or "")]
            if recalc_rows:
                oc0 = str(recalc_rows[0].get("enqueue_outcome") or "")
                if oc0 == ENQUEUE_ACCEPTED and not has_regen:
                    findings.append("phase2a_regen_delegate_not_observed_after_accepted_recalc")
            if not has_gap:
                findings.append("phase2a_gap_sync_row_not_observed_in_downstream_sample")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "schema_version": "phase2a_rst_core_backbone_propagation_chain_burn_in_v1",
    }


def validate_authority_sync_stability_phase2a_burn_in(
    *, transition_traces: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    """Advisory: transition identity continuity and backbone vs authority-skip coherence."""
    findings: List[str] = []
    for tr in transition_traces:
        rows = _downstream_rows(tr)
        if not rows:
            continue
        if not str(tr.get("transition_id") or "").strip():
            findings.append("phase2a_missing_transition_id_with_downstream_rows")
        if not str(tr.get("correlation_id") or "").strip():
            findings.append("phase2a_missing_correlation_id_with_downstream_rows")
        for r in rows:
            if not str(r.get("propagation_stage") or "").strip():
                findings.append("phase2a_downstream_row_missing_propagation_stage")
                break
        blob = tr.get("rst_core_backbone_activation")
        blocked_auth = any(_AUTHORITY_BACKBONE_SKIP_TARGET_SUBSTR in str(r.get("downstream_target") or "") for r in rows)
        if isinstance(blob, Mapping) and blob.get("permitted") and blocked_auth:
            findings.append("phase2a_inconsistent_backbone_permitted_with_authority_skip_row")
        if isinstance(blob, Mapping) and not blob.get("permitted") and not blocked_auth:
            has_recalc = any(_RECALC_TARGET_SUBSTR in str(r.get("downstream_target") or "") for r in rows)
            if has_recalc:
                findings.append("phase2a_backbone_blocked_but_recalc_downstream_present_review_path")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "schema_version": "phase2a_authority_sync_stability_burn_in_v1",
    }


def validate_recalc_regen_metadata_phase2a_burn_in(
    *, transition_traces: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    """Advisory: gated downstream skips remain observable (activation metadata)."""
    findings: List[str] = []
    skipped_missing = 0
    for tr in transition_traces:
        for row in _downstream_rows(tr):
            tgt = str(row.get("downstream_target") or "")
            if _RECALC_TARGET_SUBSTR not in tgt and _REGEN_TARGET_SUBSTR not in tgt:
                continue
            if str(row.get("enqueue_outcome") or "") != ENQUEUE_SKIPPED:
                continue
            if not row.get("activation_guard_result") and not row.get("activation_state"):
                skipped_missing += 1
                findings.append("phase2a_skipped_gated_row_missing_activation_metadata")
    cls = VALIDATION_CONFIRMED if skipped_missing == 0 else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "skipped_rows_missing_activation_metadata_count": skipped_missing,
        "schema_version": "phase2a_recalc_regen_metadata_burn_in_v1",
    }


def validate_convergence_trace_alignment_phase2a_burn_in(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    convergence_snapshot: Mapping[str, Any],
) -> Dict[str, Any]:
    """Advisory: convergence matrix remains populated vs traces; RST backbone continuity reused."""
    findings: List[str] = []
    cem = convergence_snapshot.get("convergence_evidence_matrix") if isinstance(convergence_snapshot, Mapping) else {}
    mrows = cem.get("matrix_rows") if isinstance(cem, Mapping) else []
    n_mx = len(mrows) if isinstance(mrows, list) else 0
    n_tr = len(transition_traces)
    if n_tr >= 1 and n_mx == 0:
        findings.append("phase2a_convergence_matrix_empty_while_traces_present")
    conv_cont = validate_rst_core_backbone_convergence_continuity(transition_traces=list(transition_traces))
    if str(conv_cont.get("activation_validation") or "") == VALIDATION_FAILED:
        findings.extend([str(x) for x in (conv_cont.get("finding_codes") or [])])
    elif str(conv_cont.get("activation_validation") or "") == VALIDATION_PARTIAL:
        findings.extend([f"rst_bb_conv:{x}" for x in (conv_cont.get("finding_codes") or [])])
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL if n_mx > 0 else VALIDATION_INSUFFICIENT_EVIDENCE
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "rst_core_backbone_convergence_continuity": conv_cont,
        "schema_version": "phase2a_convergence_trace_alignment_burn_in_v1",
    }


def validate_governance_runtime_alignment_phase2a_burn_in(*, harness: Mapping[str, Any]) -> Dict[str, Any]:
    """Advisory: governance v3 snapshot rows + backbone visibility + evidence pack alignment."""
    findings: List[str] = []
    gov = harness.get("governance_report_full") if isinstance(harness.get("governance_report_full"), Mapping) else {}
    rt = gov.get("runtime_activation_snapshot") if isinstance(gov.get("runtime_activation_snapshot"), Mapping) else {}
    req_fams = (
        FAMILY_COMPLIANCE_SCORE_RECALC,
        FAMILY_REGENERATION_RECALC,
        FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
    )
    seen = {str(r.get("activation_family")) for r in (rt.get("families") or []) if isinstance(r, Mapping)}
    for fam in req_fams:
        if fam not in seen:
            findings.append(f"phase2a_governance_missing_runtime_family:{fam}")
    if str(rt.get("activation_governance_version") or "") != ACTIVATION_GOVERNANCE_VERSION:
        findings.append("phase2a_governance_runtime_version_mismatch")
    if "requirement_transition_core_backbone_activation_operational_visibility" not in gov:
        findings.append("phase2a_governance_missing_backbone_operational_visibility")
    ep = harness.get("evidence_pack") if isinstance(harness.get("evidence_pack"), Mapping) else {}
    if "requirement_transition_core_backbone_activation_evidence" not in ep:
        findings.append("phase2a_evidence_pack_missing_backbone_block")
    bb_vis_h = (
        harness.get("rst_core_backbone_activation_operational_visibility")
        if isinstance(harness.get("rst_core_backbone_activation_operational_visibility"), Mapping)
        else {}
    )
    if not bb_vis_h.get("schema_version"):
        findings.append("phase2a_harness_missing_backbone_visibility_schema")
    drift = ((harness.get("dual_family_staging_validation") or {}).get("validation_snapshot") or {}).get("drift") or {}
    fc = drift.get("finding_codes") if isinstance(drift.get("finding_codes"), list) else []
    backbone_drifts = [str(x) for x in fc if "rst_core" in str(x).lower() or "backbone" in str(x).lower()]
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "backbone_related_drift_finding_codes": sorted(set(backbone_drifts)),
        "finding_codes": sorted(set(findings)),
        "schema_version": "phase2a_governance_runtime_alignment_burn_in_v1",
    }


def validate_code_only_rollback_posture_phase2a_burn_in() -> Dict[str, Any]:
    """Advisory: limited→observe/disabled rollback transitions remain code-validated (no runtime reset)."""
    transitions = [
        validate_registry_rollback_posture(from_ceiling=ACTIVATION_LIMITED, to_ceiling=ACTIVATION_OBSERVE_ONLY),
        validate_registry_rollback_posture(from_ceiling=ACTIVATION_LIMITED, to_ceiling=ACTIVATION_DISABLED),
        validate_registry_rollback_posture(from_ceiling=ACTIVATION_OBSERVE_ONLY, to_ceiling=ACTIVATION_DISABLED),
    ]
    findings: List[str] = []
    for i, t in enumerate(transitions):
        if str(t.get("rollback_posture") or "") != "ROLLBACK_VALIDATED":
            findings.append(f"phase2a_rollback_transition_{i}_not_validated")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "rollback_transition_validations": transitions,
        "schema_version": "phase2a_code_only_rollback_posture_burn_in_v1",
    }


def validate_degraded_path_signals_phase2a_burn_in(
    *,
    propagation: Mapping[str, Any],
    visibility: Mapping[str, Any],
    recalc_meta: Mapping[str, Any],
) -> Dict[str, Any]:
    """Advisory: silent skips degrade rollup; other signals are informational observations only."""
    findings: List[str] = []
    informational: List[str] = []
    if int(recalc_meta.get("skipped_rows_missing_activation_metadata_count") or 0) > 0:
        findings.append("phase2a_degraded_path_skipped_without_metadata")
    if int(propagation.get("downstream_enqueue_degraded_count") or 0) > 0:
        informational.append("phase2a_degraded_enqueue_observed_expect_visibility_review")
    if (
        str(visibility.get("visibility_band") or "") == VISIBILITY_OPAQUE
        and int(propagation.get("downstream_enqueue_accepted_count") or 0) > 0
    ):
        informational.append("phase2a_visibility_opaque_with_accepted_enqueue_review_matrix")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "informational_observation_codes": sorted(informational),
        "schema_version": "phase2a_degraded_path_signals_burn_in_v1",
    }


def build_phase2a_rst_core_backbone_runtime_validation_bundle(
    *,
    harness: Mapping[str, Any],
    merged_traces: Sequence[Mapping[str, Any]],
    convergence_snapshot: Mapping[str, Any],
    propagation: Mapping[str, Any],
    visibility: Mapping[str, Any],
) -> Dict[str, Any]:
    """Single deterministic Phase 2A RST backbone runtime validation artifact (read-only)."""
    chain = validate_rst_core_backbone_propagation_chain_phase2a_burn_in(transition_traces=merged_traces)
    authority = validate_authority_sync_stability_phase2a_burn_in(transition_traces=merged_traces)
    recalc_meta = validate_recalc_regen_metadata_phase2a_burn_in(transition_traces=merged_traces)
    conv_align = validate_convergence_trace_alignment_phase2a_burn_in(
        transition_traces=merged_traces,
        convergence_snapshot=convergence_snapshot,
    )
    gov_align = validate_governance_runtime_alignment_phase2a_burn_in(harness=harness)
    rollback = validate_code_only_rollback_posture_phase2a_burn_in()
    degraded = validate_degraded_path_signals_phase2a_burn_in(
        propagation=propagation,
        visibility=visibility,
        recalc_meta=recalc_meta,
    )
    blocks = (chain, authority, recalc_meta, conv_align, gov_align, rollback, degraded)
    rollup = _rollup_phase2a_activation_validation(blocks)
    bundle: Dict[str, Any] = {
        "authority_sync_stability": authority,
        "code_only_rollback_posture": rollback,
        "convergence_trace_alignment": conv_align,
        "degraded_path_signals": degraded,
        "governance_runtime_alignment": gov_align,
        "propagation_chain": chain,
        "recalc_regen_metadata": recalc_meta,
        "rollup_activation_validation": rollup,
        "schema_version": PHASE2A_RST_CORE_BACKBONE_BURN_IN_VALIDATION_SCHEMA_VERSION,
    }
    return dict(sorted(bundle.items(), key=lambda kv: str(kv[0])))


def classify_stale_degraded_runtime_visibility(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    convergence_snapshot: Mapping[str, Any],
) -> Dict[str, Any]:
    """Aggregate stale/degraded/replay/retry visibility from convergence matrix rows + trace replay flags."""
    replay_trace_level = sum(1 for tr in transition_traces if bool(tr.get("replay_chain_detected")))
    recon_gap_n = stale_n = deg_n = retry_non_none = 0
    cem = convergence_snapshot.get("convergence_evidence_matrix") if isinstance(convergence_snapshot, Mapping) else {}
    rows = cem.get("matrix_rows") if isinstance(cem, Mapping) else []
    row_list = [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []
    for r in row_list:
        if r.get("stale_read_dependency"):
            stale_n += 1
        if r.get("degraded_visibility"):
            deg_n += 1
        if str(r.get("retry_evidence") or "") != "none_observed":
            retry_non_none += 1
        if r.get("reconciliation_visibility") == RECONCILIATION_NOT_VISIBLE:
            recon_gap_n += 1

    n_mx = max(len(row_list), 1)
    total_signals = stale_n + deg_n + retry_non_none + replay_trace_level

    if total_signals == 0 and recon_gap_n == 0:
        band = VISIBILITY_OPAQUE
    elif total_signals >= n_mx * 0.5 or replay_trace_level >= 1:
        band = VISIBILITY_VISIBLE if total_signals >= n_mx * 0.65 else VISIBILITY_PARTIALLY_VISIBLE
    elif total_signals >= 1 or recon_gap_n >= 1:
        band = VISIBILITY_PARTIALLY_VISIBLE
    else:
        band = VISIBILITY_OPAQUE

    return {
        "degraded_signal_count": deg_n,
        "matrix_row_count": len(row_list),
        "reconciliation_not_visible_count": recon_gap_n,
        "replay_trace_level_signal_count": replay_trace_level,
        "schema_version": "stale_degraded_runtime_visibility_v1",
        "stale_signal_count": stale_n,
        "visibility_band": band,
        "retry_non_none_observed_count": retry_non_none,
    }


def build_representative_staging_evidence_findings(
    *,
    flow_traces_by_kind: Mapping[str, Sequence[Mapping[str, Any]]],
    harness: Mapping[str, Any],
    propagation: Mapping[str, Any],
    visibility: Mapping[str, Any],
) -> Dict[str, Any]:
    """Coverage and gap codes (advisory)."""
    gaps: List[str] = []
    ambiguous: List[str] = []
    degraded_surfaces: List[str] = []
    rollback_uncertain: List[str] = []

    kinds_with_traces = sum(
        1 for k in STAGING_RUNTIME_FLOW_KINDS if flow_traces_by_kind.get(k) and len(flow_traces_by_kind[k]) > 0
    )
    ratio = kinds_with_traces / max(len(STAGING_RUNTIME_FLOW_KINDS), 1)

    for k in STAGING_RUNTIME_FLOW_KINDS:
        if not flow_traces_by_kind.get(k):
            gaps.append(f"evidence_gap_missing_flow_kind:{k}")

    if harness.get("representative_unknown_flow_keys"):
        ambiguous.append("unknown_staging_flow_keys_in_input")

    if propagation.get("finding_codes"):
        ambiguous.extend(str(x) for x in propagation["finding_codes"])

    if str(visibility.get("visibility_band") or "") == VISIBILITY_PARTIALLY_VISIBLE:
        degraded_surfaces.append("stale_or_degraded_partially_visible")
    if str(visibility.get("visibility_band") or "") == VISIBILITY_OPAQUE:
        degraded_surfaces.append("stale_degraded_retry_surfaces_opaque")

    rb = (
        (harness.get("dual_family_staging_validation") or {})
        .get("combined_activation_rollback_summary", {})
        .get("rollback_summary", {})
    )
    if isinstance(rb, Mapping) and rb.get("rollback_posture") != "ROLLBACK_VALIDATED":
        rollback_uncertain.append("rollback_summary_not_fully_validated_posture")

    drift = ((harness.get("dual_family_staging_validation") or {}).get("validation_snapshot") or {}).get("drift") or {}
    if str(drift.get("drift_classification") or "") in (HIGH_VALIDATION_DRIFT, CRITICAL_VALIDATION_DRIFT):
        ambiguous.append("activation_drift_visible_in_burn_in_window")

    env_pack = harness.get("evidence_pack") or {}
    aligned = str(env_pack.get("staging_drift_classification") or "") in (
        "LOW_STAGING_DRIFT",
        "MODERATE_STAGING_DRIFT",
    ) or str(drift.get("drift_classification") or "") in (LOW_VALIDATION_DRIFT, MODERATE_VALIDATION_DRIFT)

    coex = propagation.get("coexistence") or {}
    recalc_b = bool(coex.get("has_recalc_downstream"))
    regen_b = bool(coex.get("has_regen_downstream"))
    downstream_cov = 1.0 if recalc_b and regen_b else 0.5 if recalc_b or regen_b else 0.0

    return {
        "ambiguous_runtime_surfaces": sorted(set(ambiguous)),
        "degraded_visibility_surfaces": sorted(set(degraded_surfaces)),
        "evidence_gaps": sorted(set(gaps)),
        "representative_downstream_coverage_ratio": downstream_cov,
        "representative_enqueue_coverage_present": bool(env_pack.get("representative_enqueue_samples"))
        or bool(env_pack.get("representative_regeneration_enqueue_samples")),
        "representative_governance_alignment": aligned,
        "representative_runtime_alignment": ratio >= 0.5,
        "representative_trace_coverage_ratio": round(ratio, 4),
        "rollback_uncertain_surfaces": sorted(set(rollback_uncertain)),
        "schema_version": "representative_staging_evidence_findings_v1",
    }


def classify_operational_burn_in(
    *,
    dual_family_snapshot: Mapping[str, Any],
    propagation: Mapping[str, Any],
    visibility: Mapping[str, Any],
    findings: Mapping[str, Any],
    validation_snapshot: Mapping[str, Any],
    phase2a_rst_core_backbone_runtime_validation: Optional[Mapping[str, Any]] = None,
) -> str:
    """Advisory burn-in classification (deterministic)."""
    staging = str(dual_family_snapshot.get("dual_family_staging_readiness_classification") or "")
    if staging == DUAL_FAMILY_STAGING_OBSERVE_ONLY:
        return BURN_IN_OBSERVE_ONLY

    drift = str((validation_snapshot.get("drift") or {}).get("drift_classification") or "")
    if drift == CRITICAL_VALIDATION_DRIFT:
        return BURN_IN_DRIFT_VISIBLE
    if drift == HIGH_VALIDATION_DRIFT:
        return BURN_IN_DRIFT_VISIBLE

    overall = str(validation_snapshot.get("overall_activation_validation") or "")
    if overall == VALIDATION_FAILED or staging == DUAL_FAMILY_STAGING_DEGRADED:
        return BURN_IN_DEGRADED

    if phase2a_rst_core_backbone_runtime_validation:
        rollup = str(phase2a_rst_core_backbone_runtime_validation.get("rollup_activation_validation") or "")
        if rollup == VALIDATION_FAILED:
            return BURN_IN_DEGRADED

    gov_sig = dual_family_snapshot.get("registry_v2_governance_load_signal") or {}
    if gov_sig.get("finding_codes"):
        return BURN_IN_REQUIRES_REVIEW

    cov = float(findings.get("representative_trace_coverage_ratio") or 0)
    if cov < 0.35:
        return BURN_IN_PARTIAL

    if staging == DUAL_FAMILY_STAGING_DRIFT_VISIBLE:
        return BURN_IN_DRIFT_VISIBLE
    if staging == DUAL_FAMILY_STAGING_PARTIAL or overall == VALIDATION_PARTIAL:
        return BURN_IN_PARTIAL

    vis = str(visibility.get("visibility_band") or "")
    if vis == VISIBILITY_OPAQUE:
        return BURN_IN_PARTIAL

    prop_cls = str(propagation.get("activation_validation") or "")
    if prop_cls == VALIDATION_PARTIAL:
        return BURN_IN_PARTIAL

    if phase2a_rst_core_backbone_runtime_validation:
        rollup = str(phase2a_rst_core_backbone_runtime_validation.get("rollup_activation_validation") or "")
        if rollup in (VALIDATION_PARTIAL, VALIDATION_INSUFFICIENT_EVIDENCE):
            return BURN_IN_PARTIAL

    return BURN_IN_CONFIRMED


def derive_operational_readiness_recommendation_burn_in(
    *,
    burn_in_classification: str,
    findings: Mapping[str, Any],
    visibility: Mapping[str, Any],
    dual_family_snapshot: Mapping[str, Any],
    phase2a_rst_core_backbone_runtime_validation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Advisory readiness for continued limited backbone vs further review (non-enforcing)."""
    staging = str(dual_family_snapshot.get("dual_family_staging_readiness_classification") or "")
    cov = float(findings.get("representative_trace_coverage_ratio") or 0)
    gov_sig = dual_family_snapshot.get("registry_v2_governance_load_signal") or {}
    vis = str(visibility.get("visibility_band") or "")

    conclusion = HOLD_PENDING_MORE_RUNTIME_EVIDENCE
    rationale = "default_pending_evidence"

    if burn_in_classification == BURN_IN_OBSERVE_ONLY:
        conclusion = HOLD_PENDING_MORE_RUNTIME_EVIDENCE
        rationale = "registry_observe_only_posture_not_burn_in_complete"
    elif burn_in_classification in (BURN_IN_DRIFT_VISIBLE, BURN_IN_DEGRADED):
        conclusion = HOLD_PENDING_GOVERNANCE_REVIEW
        rationale = "burn_in_degraded_or_drift_visible"
    elif gov_sig.get("finding_codes"):
        conclusion = HOLD_PENDING_GOVERNANCE_REVIEW
        rationale = "governance_load_signal_present"
    elif vis == VISIBILITY_OPAQUE:
        conclusion = HOLD_PENDING_OBSERVABILITY_ALIGNMENT
        rationale = "stale_degraded_replay_surfaces_mostly_opaque"
    elif staging == DUAL_FAMILY_STAGING_PARTIAL or cov < 0.6:
        conclusion = HOLD_PENDING_MORE_RUNTIME_EVIDENCE
        rationale = "partial_staging_coverage_or_dual_family_partial"
    elif burn_in_classification == BURN_IN_REQUIRES_REVIEW:
        conclusion = HOLD_PENDING_GOVERNANCE_REVIEW
        rationale = "explicit_review_signal_from_governance_counters"
    elif burn_in_classification == BURN_IN_PARTIAL:
        conclusion = HOLD_PENDING_CONVERGENCE_ALIGNMENT
        rationale = "burn_in_partial_propagation_or_visibility"
    elif burn_in_classification == BURN_IN_CONFIRMED and cov >= 0.9:
        conclusion = READY_FOR_PHASE2_REVIEW
        rationale = "strong_representative_coverage_ready_for_rst_fanout_review_not_activation"
    elif burn_in_classification == BURN_IN_CONFIRMED:
        conclusion = READY_FOR_CONTINUED_LIMITED_ACTIVATION
        rationale = "confirmed_burn_in_continue_limited_backbone"

    if phase2a_rst_core_backbone_runtime_validation:
        rollup = str(phase2a_rst_core_backbone_runtime_validation.get("rollup_activation_validation") or "")
        if rollup == VALIDATION_FAILED:
            conclusion = HOLD_PENDING_GOVERNANCE_REVIEW
            rationale = "phase2a_rst_core_backbone_runtime_validation_failed"
        elif rollup in (VALIDATION_PARTIAL, VALIDATION_INSUFFICIENT_EVIDENCE) and conclusion in (
            READY_FOR_CONTINUED_LIMITED_ACTIVATION,
            READY_FOR_PHASE2_REVIEW,
        ):
            conclusion = HOLD_PENDING_CONVERGENCE_ALIGNMENT
            rationale = "phase2a_rst_core_backbone_runtime_validation_partial_or_insufficient"

    return {
        "advisory_only": True,
        "non_blocking": True,
        "operational_readiness_conclusion": conclusion,
        "phase2a_rst_core_backbone_rollup_activation_validation": (
            str((phase2a_rst_core_backbone_runtime_validation or {}).get("rollup_activation_validation") or "")
            if phase2a_rst_core_backbone_runtime_validation
            else None
        ),
        "rationale_code": rationale,
        "schema_version": "operational_readiness_recommendation_burn_in_v1",
    }


def _extract_validation_snapshot(harness: Mapping[str, Any]) -> Dict[str, Any]:
    df = harness.get("dual_family_staging_validation") if isinstance(harness.get("dual_family_staging_validation"), Mapping) else {}
    vs = df.get("validation_snapshot") if isinstance(df.get("validation_snapshot"), Mapping) else {}
    return dict(vs)


def build_burn_in_activation_summary(*, harness: Mapping[str, Any], dual_family: Mapping[str, Any]) -> Dict[str, Any]:
    vs = _extract_validation_snapshot(harness)
    return {
        "dual_family_staging_readiness": dual_family.get("dual_family_staging_readiness_classification"),
        "overall_activation_validation": vs.get("overall_activation_validation"),
        "schema_version": "burn_in_activation_summary_v1",
    }


def build_burn_in_convergence_summary(*, harness: Mapping[str, Any]) -> Dict[str, Any]:
    conv = harness.get("convergence_snapshot") if isinstance(harness.get("convergence_snapshot"), Mapping) else {}
    cem = conv.get("convergence_evidence_matrix") if isinstance(conv.get("convergence_evidence_matrix"), Mapping) else {}
    rows = cem.get("matrix_rows") if isinstance(cem.get("matrix_rows"), list) else []
    return {
        "convergence_matrix_row_count": len(rows),
        "hotspots_schema": (conv.get("runtime_convergence_hotspots") or {}).get("schema_version"),
        "schema_version": "burn_in_convergence_summary_v1",
    }


def build_burn_in_observability_summary(*, harness: Mapping[str, Any]) -> Dict[str, Any]:
    ep = harness.get("evidence_pack") if isinstance(harness.get("evidence_pack"), Mapping) else {}
    return {
        "observability_validation_summary": ep.get("observability_validation_summary"),
        "schema_version": "burn_in_observability_summary_v1",
    }


def build_burn_in_reconciliation_summary(*, harness: Mapping[str, Any], propagation: Mapping[str, Any]) -> Dict[str, Any]:
    conv = harness.get("convergence_snapshot") if isinstance(harness.get("convergence_snapshot"), Mapping) else {}
    recon = conv.get("reconciliation_visibility") if isinstance(conv.get("reconciliation_visibility"), Mapping) else {}
    return {
        "convergence_reconciliation_visibility_summary": recon,
        "downstream_reconciliation_recommended_total": propagation.get("downstream_reconciliation_recommended_count"),
        "schema_version": "burn_in_reconciliation_summary_v1",
    }


def build_burn_in_drift_summary(*, harness: Mapping[str, Any]) -> Dict[str, Any]:
    vs = _extract_validation_snapshot(harness)
    drift = vs.get("drift") if isinstance(vs.get("drift"), Mapping) else {}
    ep = harness.get("evidence_pack") if isinstance(harness.get("evidence_pack"), Mapping) else {}
    return {
        "drift_classification": drift.get("drift_classification"),
        "drift_finding_codes": list(drift.get("finding_codes") or []),
        "staging_drift_classification": ep.get("staging_drift_classification"),
        "schema_version": "burn_in_drift_summary_v1",
    }


def build_burn_in_runtime_consistency_summary(*, harness: Mapping[str, Any]) -> Dict[str, Any]:
    ep = harness.get("evidence_pack") if isinstance(harness.get("evidence_pack"), Mapping) else {}
    return {
        "runtime_consistency_findings": ep.get("runtime_consistency_findings"),
        "schema_version": "burn_in_runtime_consistency_summary_v1",
    }


def build_burn_in_rollback_summary(*, dual_family: Mapping[str, Any]) -> Dict[str, Any]:
    rb = dual_family.get("combined_activation_rollback_summary") if isinstance(dual_family.get("combined_activation_rollback_summary"), Mapping) else {}
    return {
        "combined_activation_rollback_summary": rb,
        "schema_version": "burn_in_rollback_summary_v1",
    }


def build_operational_burn_in_report(
    *,
    generated_at_iso: str,
    flow_traces_by_kind: Mapping[str, Sequence[Mapping[str, Any]]],
    queue_visibility: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    representative_enqueue_samples: Sequence[Mapping[str, Any]] = (),
    representative_regeneration_enqueue_samples: Sequence[Mapping[str, Any]] = (),
    governance_families: Optional[Sequence[str]] = None,
    embed_full_merged_traces: bool = False,
    representative_trace_sample_limit: int = 16,
) -> Dict[str, Any]:
    """
    Single read-only operational burn-in artifact for staging (no DB, no activation changes).

    Assembles harness + propagation continuity + visibility + findings + burn-in classification
    + readiness recommendation + summaries.
    """
    harness = build_staging_runtime_evidence_harness(
        generated_at_iso=generated_at_iso,
        flow_traces_by_kind=flow_traces_by_kind,
        queue_visibility=queue_visibility,
        observability_summary=observability_summary,
        representative_enqueue_samples=representative_enqueue_samples,
        representative_regeneration_enqueue_samples=representative_regeneration_enqueue_samples,
        governance_families=governance_families,
        embed_full_merged_traces=embed_full_merged_traces,
        representative_trace_sample_limit=representative_trace_sample_limit,
    )

    merged = merge_staging_flow_traces_for_harness(flow_traces_by_kind)
    conv = harness["convergence_snapshot"]
    dual = harness["dual_family_staging_validation"]
    vs = _extract_validation_snapshot(harness)

    propagation = validate_propagation_continuity_burn_in(transition_traces=merged)
    visibility = classify_stale_degraded_runtime_visibility(transition_traces=merged, convergence_snapshot=conv)
    findings = build_representative_staging_evidence_findings(
        flow_traces_by_kind=flow_traces_by_kind,
        harness=harness,
        propagation=propagation,
        visibility=visibility,
    )

    phase2a_bundle = build_phase2a_rst_core_backbone_runtime_validation_bundle(
        harness=harness,
        merged_traces=merged,
        convergence_snapshot=conv,
        propagation=propagation,
        visibility=visibility,
    )

    burn_in = classify_operational_burn_in(
        dual_family_snapshot=dual,
        propagation=propagation,
        visibility=visibility,
        findings=findings,
        validation_snapshot=vs,
        phase2a_rst_core_backbone_runtime_validation=phase2a_bundle,
    )

    readiness = derive_operational_readiness_recommendation_burn_in(
        burn_in_classification=burn_in,
        findings=findings,
        visibility=visibility,
        dual_family_snapshot=dual,
        phase2a_rst_core_backbone_runtime_validation=phase2a_bundle,
    )

    report: Dict[str, Any] = {
        "audit_only": True,
        "burn_in_classification": burn_in,
        "burn_in_activation_summary": build_burn_in_activation_summary(harness=harness, dual_family=dual),
        "burn_in_convergence_summary": build_burn_in_convergence_summary(harness=harness),
        "burn_in_drift_summary": build_burn_in_drift_summary(harness=harness),
        "burn_in_observability_summary": build_burn_in_observability_summary(harness=harness),
        "burn_in_reconciliation_summary": build_burn_in_reconciliation_summary(harness=harness, propagation=propagation),
        "burn_in_rollback_summary": build_burn_in_rollback_summary(dual_family=dual),
        "burn_in_runtime_consistency_summary": build_burn_in_runtime_consistency_summary(harness=harness),
        "generated_at_iso": generated_at_iso,
        "non_blocking": True,
        "operational_readiness_recommendation": readiness,
        "phase2a_rst_core_backbone_runtime_validation": phase2a_bundle,
        "propagation_continuity": propagation,
        "representative_staging_evidence_findings": findings,
        "runtime_behavior_changed": False,
        "staging_runtime_evidence_harness": harness,
        "stale_degraded_visibility": visibility,
        "schema_version": OPERATIONAL_BURN_IN_SCHEMA_VERSION,
    }
    return dict(sorted(report.items(), key=lambda kv: str(kv[0])))
