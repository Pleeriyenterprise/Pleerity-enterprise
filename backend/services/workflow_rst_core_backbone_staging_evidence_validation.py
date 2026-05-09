"""
Read-only staging / runtime evidence verification for RST core backbone (Phase 2B prep).

Validates exported JSON bundles (traces, convergence, governance, evidence pack, burn-in)
without DB writes, queue access, or activation widening.

Scope (advisory only): REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
COMPLIANCE_SCORE_RECALC, REGENERATION_RECALC and the LIMITED propagation chain samples.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from services.requirement_transition_observability import ENQUEUE_SKIPPED
from services.workflow_runtime_activation_dual_family_validation import (
    DUAL_FAMILY_STAGING_DRIFT_VISIBLE,
    DUAL_FAMILY_STAGING_OBSERVE_ONLY,
)
from services.workflow_runtime_activation_registry import ACTIVATION_GOVERNANCE_VERSION
from services.workflow_runtime_activation_validation import (
    VALIDATION_CONFIRMED,
    VALIDATION_FAILED,
    VALIDATION_INSUFFICIENT_EVIDENCE,
    VALIDATION_PARTIAL,
)
from services.workflow_runtime_convergence_observability import JOIN_WEAK
from services.workflow_runtime_operational_burn_in import (
    _downstream_rows as burn_in_downstream_rows,
    build_phase2a_rst_core_backbone_runtime_validation_bundle,
    classify_stale_degraded_runtime_visibility,
    validate_governance_runtime_alignment_phase2a_burn_in,
    validate_propagation_continuity_burn_in,
    validate_code_only_rollback_posture_phase2a_burn_in,
)

STAGING_EVIDENCE_BUNDLE_SCHEMA_VERSION = "rst_core_backbone_staging_evidence_bundle_v1"
STAGING_RUNTIME_EVIDENCE_VERIFICATION_SCHEMA_VERSION = "rst_core_backbone_staging_runtime_evidence_verification_v1"

RUNTIME_EVIDENCE_HIGH_REALISM = "RUNTIME_EVIDENCE_HIGH_REALISM"
RUNTIME_EVIDENCE_MODERATE_REALISM = "RUNTIME_EVIDENCE_MODERATE_REALISM"
RUNTIME_EVIDENCE_LOW_REALISM = "RUNTIME_EVIDENCE_LOW_REALISM"
RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT = "RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT"

STAGING_CONFIDENCE_CONFIRMED = "STAGING_CONFIDENCE_CONFIRMED"
STAGING_CONFIDENCE_PARTIAL = "STAGING_CONFIDENCE_PARTIAL"
STAGING_CONFIDENCE_DEGRADED = "STAGING_CONFIDENCE_DEGRADED"
STAGING_CONFIDENCE_DRIFT_VISIBLE = "STAGING_CONFIDENCE_DRIFT_VISIBLE"
STAGING_CONFIDENCE_OBSERVE_ONLY = "STAGING_CONFIDENCE_OBSERVE_ONLY"
STAGING_CONFIDENCE_REQUIRES_REVIEW = "STAGING_CONFIDENCE_REQUIRES_REVIEW"

READY_FOR_PHASE2B_REVIEW = "READY_FOR_PHASE2B_REVIEW"
HOLD_PENDING_MORE_REAL_RUNTIME_EVIDENCE = "HOLD_PENDING_MORE_REAL_RUNTIME_EVIDENCE"
HOLD_PENDING_CONVERGENCE_ALIGNMENT = "HOLD_PENDING_CONVERGENCE_ALIGNMENT"
HOLD_PENDING_GOVERNANCE_ALIGNMENT = "HOLD_PENDING_GOVERNANCE_ALIGNMENT"
HOLD_PENDING_RUNTIME_REALISM = "HOLD_PENDING_RUNTIME_REALISM"
HOLD_PENDING_PROPAGATION_ALIGNMENT = "HOLD_PENDING_PROPAGATION_ALIGNMENT"

_RECALC_TARGET_SUBSTR = "compliance_recalc_queue.enqueue_compliance_recalc"
_REGEN_TARGET_SUBSTR = "risk_signal_regen_queue.enqueue_risk_signal_regen"


def normalize_staging_evidence_bundle(obj: Any) -> Dict[str, Any]:
    """Deterministic JSON-normalization (stable key ordering; read-only)."""
    return json.loads(json.dumps(obj, sort_keys=True, default=str))


def load_staging_evidence_bundle_from_json_file(path: str | Path) -> Dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, Mapping):
        raise TypeError("staging_evidence_bundle_root_must_be_object")
    return normalize_staging_evidence_bundle(dict(data))


def merge_frozen_governance_bundle(
    *,
    base_bundle: Mapping[str, Any],
    frozen_bundle: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Overlay frozen governance export keys onto base (read-only shallow-merge of top-level keys).

    Later keys in sorted(frozen) win when both sides define the same top-level field.
    """
    out = dict(base_bundle)
    for k in sorted(frozen_bundle.keys()):
        v = frozen_bundle.get(k)
        if v is None:
            continue
        out[str(k)] = v
    return normalize_staging_evidence_bundle(out)


def _sort_key_trace(t: Mapping[str, Any]) -> Tuple[str, str]:
    return (str(t.get("transition_id") or ""), str(t.get("correlation_id") or ""))


def extract_transition_traces(bundle: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Resolve traces from exported bundle (aliases + burn-in nesting); deterministic sort."""
    if bundle.get("transition_traces"):
        seq = bundle["transition_traces"]
    elif bundle.get("merged_transition_traces"):
        seq = bundle["merged_transition_traces"]
    else:
        br = bundle.get("operational_burn_in_report")
        if isinstance(br, Mapping):
            harness = br.get("staging_runtime_evidence_harness") if isinstance(br.get("staging_runtime_evidence_harness"), Mapping) else {}
            seq = harness.get("merged_transition_traces") or harness.get("merged_transition_trace_sample") or []
        else:
            seq = []
    if not isinstance(seq, list):
        return []
    traces = [dict(x) for x in seq if isinstance(x, Mapping)]
    traces.sort(key=_sort_key_trace)
    return traces


def extract_convergence_snapshot(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    conv = bundle.get("convergence_snapshot")
    if isinstance(conv, Mapping):
        return dict(conv)
    br = bundle.get("operational_burn_in_report")
    if isinstance(br, Mapping):
        harness = br.get("staging_runtime_evidence_harness") if isinstance(br.get("staging_runtime_evidence_harness"), Mapping) else {}
        c2 = harness.get("convergence_snapshot")
        if isinstance(c2, Mapping):
            return dict(c2)
    return {}


def assemble_harness_for_staging_verification(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    """Build harness-shaped dict expected by Phase 2A validators."""
    gov = (
        bundle.get("governance_report_full")
        or bundle.get("governance_report")
        or bundle.get("activation_snapshot")
        or {}
    )
    ep = bundle.get("evidence_pack") if isinstance(bundle.get("evidence_pack"), Mapping) else {}
    bb_vis = bundle.get("rst_core_backbone_activation_operational_visibility")
    if not isinstance(bb_vis, Mapping):
        bb_vis = {}
    dual = bundle.get("dual_family_staging_validation")
    if not isinstance(dual, Mapping):
        dual = {}
    harness: Dict[str, Any] = {
        "dual_family_staging_validation": dict(dual),
        "evidence_pack": dict(ep),
        "governance_report_full": dict(gov) if isinstance(gov, Mapping) else {},
        "rst_core_backbone_activation_operational_visibility": dict(bb_vis),
    }
    br = bundle.get("operational_burn_in_report")
    if isinstance(br, Mapping):
        inner = br.get("staging_runtime_evidence_harness") if isinstance(br.get("staging_runtime_evidence_harness"), Mapping) else {}
        if isinstance(inner.get("governance_report_full"), Mapping) and not harness["governance_report_full"]:
            harness["governance_report_full"] = dict(inner["governance_report_full"])
        if isinstance(inner.get("evidence_pack"), Mapping) and not harness["evidence_pack"]:
            harness["evidence_pack"] = dict(inner["evidence_pack"])
        if isinstance(inner.get("rst_core_backbone_activation_operational_visibility"), Mapping) and not harness[
            "rst_core_backbone_activation_operational_visibility"
        ].get("schema_version"):
            harness["rst_core_backbone_activation_operational_visibility"] = dict(
                inner["rst_core_backbone_activation_operational_visibility"]
            )
        if isinstance(inner.get("dual_family_staging_validation"), Mapping) and not harness["dual_family_staging_validation"]:
            harness["dual_family_staging_validation"] = dict(inner["dual_family_staging_validation"])
    return dict(sorted(((str(k), v) for k, v in harness.items()), key=lambda kv: kv[0]))


def validate_staging_export_propagation_surface_integrity(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Additional propagation findings beyond Phase 2A chain validators (exported traces only)."""
    findings: List[str] = []
    for tr in transition_traces:
        rows = burn_in_downstream_rows(tr)
        if bool(tr.get("replay_chain_detected")) and not rows:
            findings.append("staging_propagation_replay_chain_collapse_empty_downstream")
        if rows and not str(tr.get("correlation_id") or "").strip():
            gated = False
            for r in rows:
                tgt = str(r.get("downstream_target") or "")
                if _RECALC_TARGET_SUBSTR in tgt or _REGEN_TARGET_SUBSTR in tgt:
                    gated = True
                    break
            if gated:
                findings.append("staging_propagation_orphan_enqueue_missing_correlation_with_gated_rows")
        idx_recalc: List[int] = []
        idx_regen: List[int] = []
        for i, r in enumerate(rows):
            tgt = str(r.get("downstream_target") or "")
            if _RECALC_TARGET_SUBSTR in tgt:
                idx_recalc.append(i)
            if _REGEN_TARGET_SUBSTR in tgt:
                idx_regen.append(i)
        if idx_regen and not idx_recalc:
            findings.append("staging_propagation_regen_without_recalc_lineage_in_downstream_order")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "schema_version": "staging_export_propagation_surface_integrity_v1",
    }


def validate_staging_export_convergence_surface_integrity(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    convergence_snapshot: Mapping[str, Any],
) -> Dict[str, Any]:
    """JOIN_WEAK dominance, matrix explosion guard, orphan enqueue rows (matrix vs traces)."""
    findings: List[str] = []
    cem = convergence_snapshot.get("convergence_evidence_matrix") if isinstance(convergence_snapshot, Mapping) else {}
    mrows = cem.get("matrix_rows") if isinstance(cem, Mapping) else []
    row_list = [r for r in mrows if isinstance(r, Mapping)] if isinstance(mrows, list) else []
    n_mx = len(row_list)
    n_tr = len(transition_traces)
    weak_n = sum(1 for r in row_list if str(r.get("join_classification") or "") == JOIN_WEAK)
    if row_list and weak_n / max(len(row_list), 1) > 0.5:
        findings.append("staging_convergence_join_weak_dominant_in_matrix_sample")
    bound = max(500, n_tr * 50)
    if n_mx > bound:
        findings.append("staging_convergence_matrix_explosion_risk_vs_trace_sample")
    gated_targets = {_RECALC_TARGET_SUBSTR, _REGEN_TARGET_SUBSTR}
    trace_gate_rows = 0
    for tr in transition_traces:
        for r in burn_in_downstream_rows(tr):
            tgt = str(r.get("downstream_target") or "")
            if any(g in tgt for g in gated_targets):
                trace_gate_rows += 1
    if trace_gate_rows >= 1 and n_mx == 0 and n_tr >= 1:
        findings.append("staging_convergence_downstream_visibility_collapse_matrix_empty_with_gated_traces")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "convergence_join_weak_ratio": round(weak_n / max(len(row_list), 1), 6) if row_list else 0.0,
        "convergence_matrix_row_count": n_mx,
        "schema_version": "staging_export_convergence_surface_integrity_v1",
    }


def validate_staging_export_cross_artifact_alignment(
    *,
    bundle: Mapping[str, Any],
    harness: Mapping[str, Any],
) -> Dict[str, Any]:
    """Governance version drift across evidence_pack / governance_report / optional burn-in."""
    findings: List[str] = []
    gov = harness.get("governance_report_full") if isinstance(harness.get("governance_report_full"), Mapping) else {}
    rt = gov.get("runtime_activation_snapshot") if isinstance(gov.get("runtime_activation_snapshot"), Mapping) else {}
    gov_ver = str(rt.get("activation_governance_version") or "")
    ep = harness.get("evidence_pack") if isinstance(harness.get("evidence_pack"), Mapping) else {}
    ep_ver = str(ep.get("activation_governance_version") or "")
    if ep_ver and gov_ver and ep_ver != gov_ver:
        findings.append("staging_cross_artifact_evidence_pack_governance_version_mismatch_vs_governance_report")
    if gov_ver and gov_ver != ACTIVATION_GOVERNANCE_VERSION:
        findings.append("staging_cross_artifact_governance_report_version_not_registry_current_export")
    br = bundle.get("operational_burn_in_report")
    if isinstance(br, Mapping):
        p2 = br.get("phase2a_rst_core_backbone_runtime_validation") if isinstance(br.get("phase2a_rst_core_backbone_runtime_validation"), Mapping) else {}
        rollup = str(p2.get("rollup_activation_validation") or "")
        if rollup == VALIDATION_FAILED:
            findings.append("staging_cross_artifact_embedded_burn_in_phase2a_rollup_failed_vs_current_bundle_review")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "evidence_pack_activation_governance_version": ep_ver or None,
        "finding_codes": sorted(set(findings)),
        "governance_report_activation_governance_version": gov_ver or None,
        "schema_version": "staging_export_cross_artifact_alignment_v1",
    }


def validate_staging_export_rollback_realism(
    *,
    bundle: Mapping[str, Any],
    harness: Mapping[str, Any],
) -> Dict[str, Any]:
    """Code-only rollback posture + artifact rollback summaries coherence (read-only)."""
    code_rb = validate_code_only_rollback_posture_phase2a_burn_in()
    findings: List[str] = []
    if str(code_rb.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        findings.extend(str(x) for x in (code_rb.get("finding_codes") or []))
    ep = harness.get("evidence_pack") if isinstance(harness.get("evidence_pack"), Mapping) else {}
    rb_ep = ep.get("rollback_validation_summary") if isinstance(ep.get("rollback_validation_summary"), Mapping) else {}
    if rb_ep:
        if str(rb_ep.get("rollback_posture") or "") != "ROLLBACK_VALIDATED":
            findings.append("staging_rollback_evidence_pack_summary_not_validated_posture")
    dual = harness.get("dual_family_staging_validation") if isinstance(harness.get("dual_family_staging_validation"), Mapping) else {}
    comb = dual.get("combined_activation_rollback_summary") if isinstance(dual.get("combined_activation_rollback_summary"), Mapping) else {}
    rs = comb.get("rollback_summary") if isinstance(comb.get("rollback_summary"), Mapping) else {}
    if rs and str(rs.get("rollback_posture") or "") not in ("", "ROLLBACK_VALIDATED"):
        findings.append("staging_rollback_dual_family_summary_posture_review")
    br = bundle.get("operational_burn_in_report")
    if isinstance(br, Mapping):
        summary = br.get("burn_in_rollback_summary") if isinstance(br.get("burn_in_rollback_summary"), Mapping) else {}
        if summary and not summary.get("combined_activation_rollback_summary"):
            findings.append("staging_rollback_burn_in_summary_missing_combined_block")
    traces = extract_transition_traces(bundle)
    skip_visible = 0
    skip_total = 0
    for tr in traces:
        for r in burn_in_downstream_rows(tr):
            if str(r.get("enqueue_outcome") or "") == ENQUEUE_SKIPPED:
                skip_total += 1
                if str(r.get("propagation_stage") or "").strip():
                    skip_visible += 1
    if skip_total and skip_visible < skip_total:
        findings.append("staging_rollback_skipped_propagation_partially_opaque_missing_propagation_stage")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    out = dict(code_rb)
    out["artifact_specific_finding_codes"] = sorted(set(findings))
    out["rollback_skipped_rows_total"] = skip_total
    out["rollback_skipped_rows_with_propagation_stage"] = skip_visible
    out["schema_version"] = "staging_export_rollback_realism_v1"
    out["activation_validation"] = cls
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def _rollup_worst(blocks: Sequence[Mapping[str, Any]]) -> str:
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


def score_runtime_evidence_realism(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    convergence_snapshot: Mapping[str, Any],
    propagation_continuity: Mapping[str, Any],
    governance_runtime_alignment: Mapping[str, Any],
    convergence_surface: Mapping[str, Any],
) -> Dict[str, Any]:
    """Deterministic advisory realism tier (no ML)."""
    n_tr = len(transition_traces)
    kinds = {str(t.get("staging_runtime_flow_kind") or "") for t in transition_traces}
    kinds.discard("")
    n_kinds = len(kinds)
    targets: set[str] = set()
    replay_tr = sum(1 for t in transition_traces if bool(t.get("replay_chain_detected")))
    deg_rows = 0
    total_gated = 0
    for t in transition_traces:
        for r in burn_in_downstream_rows(t):
            targets.add(str(r.get("downstream_target") or ""))
            oc = str(r.get("enqueue_outcome") or "")
            tgt = str(r.get("downstream_target") or "")
            if _RECALC_TARGET_SUBSTR in tgt or _REGEN_TARGET_SUBSTR in tgt:
                total_gated += 1
                if oc == "ENQUEUE_DEGRADED":
                    deg_rows += 1
    diversity = len(targets)
    coex = propagation_continuity.get("coexistence") if isinstance(propagation_continuity.get("coexistence"), Mapping) else {}
    has_both = bool(coex.get("has_recalc_downstream")) and bool(coex.get("has_regen_downstream"))
    gov_ok = str(governance_runtime_alignment.get("activation_validation") or "") == VALIDATION_CONFIRMED
    join_weak_ratio = float(convergence_surface.get("convergence_join_weak_ratio") or 0.0)
    backbone_hits = int(propagation_continuity.get("rst_core_backbone_trace_hit_count") or 0)

    cem = convergence_snapshot.get("convergence_evidence_matrix") if isinstance(convergence_snapshot, Mapping) else {}
    mrows = cem.get("matrix_rows") if isinstance(cem, Mapping) else []
    row_list = [r for r in mrows if isinstance(r, Mapping)] if isinstance(mrows, list) else []
    stale_n = deg_mx = recon_nv = 0
    for r in row_list:
        if r.get("stale_read_dependency"):
            stale_n += 1
        if r.get("degraded_visibility"):
            deg_mx += 1
        if str(r.get("reconciliation_visibility") or "") == "RECONCILIATION_NOT_VISIBLE":
            recon_nv += 1

    classification = RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT
    if n_tr <= 1 or (n_kinds <= 1 and diversity <= 2):
        classification = RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT
    elif n_tr >= 6 and n_kinds >= 5 and has_both and gov_ok and join_weak_ratio < 0.35 and backbone_hits >= max(1, n_tr // 2):
        classification = RUNTIME_EVIDENCE_HIGH_REALISM
    elif n_tr >= 3 and n_kinds >= 3 and has_both and join_weak_ratio <= 0.5:
        classification = RUNTIME_EVIDENCE_MODERATE_REALISM
    elif n_tr >= 2:
        classification = RUNTIME_EVIDENCE_LOW_REALISM

    return {
        "backbone_trace_hit_count": backbone_hits,
        "classification": classification,
        "convergence_matrix_degraded_visibility_rows": deg_mx,
        "convergence_matrix_reconciliation_not_visible_rows": recon_nv,
        "convergence_matrix_stale_rows": stale_n,
        "downstream_target_diversity": diversity,
        "dual_downstream_coexistence_observed": has_both,
        "governance_alignment_confirmed": gov_ok,
        "join_weak_ratio": join_weak_ratio,
        "replay_trace_signal_count": replay_tr,
        "schema_version": "runtime_evidence_realism_score_v1",
        "staging_flow_kind_distinct_count": n_kinds,
        "trace_sample_count": n_tr,
        "downstream_gated_row_sample_count": total_gated,
        "downstream_gated_degraded_row_count": deg_rows,
    }


def classify_staging_evidence_confidence(
    *,
    phase2a_bundle: Mapping[str, Any],
    propagation_surface: Mapping[str, Any],
    convergence_surface: Mapping[str, Any],
    cross_artifact: Mapping[str, Any],
    realism_classification: str,
    rollback_realism: Mapping[str, Any],
    dual_family_staging_readiness_classification: str = "",
) -> str:
    """Advisory staging confidence (deterministic)."""
    blocks = [
        phase2a_bundle,
        propagation_surface,
        convergence_surface,
        cross_artifact,
        rollback_realism,
    ]
    worst = _rollup_worst(blocks)
    staging = str(dual_family_staging_readiness_classification or "")
    if staging == DUAL_FAMILY_STAGING_OBSERVE_ONLY:
        return STAGING_CONFIDENCE_OBSERVE_ONLY
    if staging == DUAL_FAMILY_STAGING_DRIFT_VISIBLE:
        return STAGING_CONFIDENCE_DRIFT_VISIBLE
    if realism_classification == RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT:
        return STAGING_CONFIDENCE_REQUIRES_REVIEW
    if worst == VALIDATION_FAILED:
        return STAGING_CONFIDENCE_DEGRADED
    rollup = str(phase2a_bundle.get("rollup_activation_validation") or "")
    if rollup == VALIDATION_INSUFFICIENT_EVIDENCE:
        return STAGING_CONFIDENCE_PARTIAL
    if worst == VALIDATION_PARTIAL or rollup == VALIDATION_PARTIAL:
        return STAGING_CONFIDENCE_PARTIAL
    return STAGING_CONFIDENCE_CONFIRMED


def derive_staging_readiness_for_phase2b_review(
    *,
    staging_confidence: str,
    realism_classification: str,
    phase2a_bundle: Mapping[str, Any],
    convergence_surface: Mapping[str, Any],
    cross_artifact: Mapping[str, Any],
) -> Dict[str, Any]:
    """Advisory Phase 2B review readiness labels (non-enforcing)."""
    rollup = str(phase2a_bundle.get("rollup_activation_validation") or "")
    readiness = HOLD_PENDING_MORE_REAL_RUNTIME_EVIDENCE
    rationale = "default_hold_more_evidence"

    if staging_confidence == STAGING_CONFIDENCE_OBSERVE_ONLY:
        return {
            "advisory_only": True,
            "non_blocking": True,
            "phase2a_rollup_activation_validation": rollup,
            "rationale_code": "dual_family_observe_only_posture_hold_review_gate",
            "readiness_classification": HOLD_PENDING_MORE_REAL_RUNTIME_EVIDENCE,
            "schema_version": "staging_readiness_phase2b_review_v1",
            "staging_confidence_classification": staging_confidence,
        }
    if staging_confidence == STAGING_CONFIDENCE_DRIFT_VISIBLE:
        return {
            "advisory_only": True,
            "non_blocking": True,
            "phase2a_rollup_activation_validation": rollup,
            "rationale_code": "dual_family_drift_visible_hold_governance_alignment",
            "readiness_classification": HOLD_PENDING_GOVERNANCE_ALIGNMENT,
            "schema_version": "staging_readiness_phase2b_review_v1",
            "staging_confidence_classification": staging_confidence,
        }
    if staging_confidence == STAGING_CONFIDENCE_DEGRADED:
        return {
            "advisory_only": True,
            "non_blocking": True,
            "phase2a_rollup_activation_validation": rollup,
            "rationale_code": "staging_confidence_degraded_hold_propagation_alignment",
            "readiness_classification": HOLD_PENDING_PROPAGATION_ALIGNMENT,
            "schema_version": "staging_readiness_phase2b_review_v1",
            "staging_confidence_classification": staging_confidence,
        }

    if realism_classification == RUNTIME_EVIDENCE_SYNTHETIC_DOMINANT:
        readiness = HOLD_PENDING_RUNTIME_REALISM
        rationale = "synthetic_or_single_surface_dominant_sample"
    elif str(cross_artifact.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_GOVERNANCE_ALIGNMENT
        rationale = "cross_artifact_governance_runtime_mismatch"
    elif str(convergence_surface.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_CONVERGENCE_ALIGNMENT
        rationale = "convergence_surface_integrity_partial_or_failed"
    elif staging_confidence == STAGING_CONFIDENCE_PARTIAL:
        readiness = HOLD_PENDING_PROPAGATION_ALIGNMENT
        rationale = "staging_confidence_partial_export_surfaces"
    elif rollup in (VALIDATION_PARTIAL, VALIDATION_INSUFFICIENT_EVIDENCE):
        readiness = HOLD_PENDING_PROPAGATION_ALIGNMENT
        rationale = "phase2a_propagation_or_convergence_partial_in_export"
    elif staging_confidence == STAGING_CONFIDENCE_CONFIRMED and realism_classification == RUNTIME_EVIDENCE_HIGH_REALISM:
        readiness = READY_FOR_PHASE2B_REVIEW
        rationale = "confirmed_propagation_with_high_realism_export_sample"
    elif staging_confidence == STAGING_CONFIDENCE_CONFIRMED:
        readiness = READY_FOR_PHASE2B_REVIEW
        rationale = "confirmed_propagation_moderate_realism_acceptable_for_review_gate"
    elif staging_confidence == STAGING_CONFIDENCE_REQUIRES_REVIEW:
        readiness = HOLD_PENDING_RUNTIME_REALISM
        rationale = "confidence_requires_review_realism_or_surface_findings"

    return {
        "advisory_only": True,
        "non_blocking": True,
        "phase2a_rollup_activation_validation": rollup,
        "rationale_code": rationale,
        "readiness_classification": readiness,
        "schema_version": "staging_readiness_phase2b_review_v1",
        "staging_confidence_classification": staging_confidence,
    }


def build_operational_staging_evidence_summaries(
    *,
    realism: Mapping[str, Any],
    phase2a_bundle: Mapping[str, Any],
    propagation_surface: Mapping[str, Any],
    convergence_surface: Mapping[str, Any],
    cross_artifact: Mapping[str, Any],
    rollback_realism: Mapping[str, Any],
    propagation_continuity: Mapping[str, Any],
    visibility: Mapping[str, Any],
    staging_confidence: str,
    readiness: Mapping[str, Any],
) -> Dict[str, Any]:
    """Single deterministic summary block for operational review (read-only)."""
    return {
        "convergence_integrity_summary": {
            "activation_validation": convergence_surface.get("activation_validation"),
            "finding_codes": convergence_surface.get("finding_codes"),
            "join_weak_ratio": realism.get("join_weak_ratio"),
            "matrix_row_count": convergence_surface.get("convergence_matrix_row_count"),
        },
        "degraded_visibility_summary": {
            "degraded_signal_count": visibility.get("degraded_signal_count"),
            "visibility_band": visibility.get("visibility_band"),
        },
        "governance_runtime_alignment_summary": {
            "activation_validation": cross_artifact.get("activation_validation"),
            "finding_codes": cross_artifact.get("finding_codes"),
        },
        "operational_confidence_summary": {
            "readiness_classification": readiness.get("readiness_classification"),
            "staging_confidence_classification": staging_confidence,
        },
        "propagation_integrity_summary": {
            "continuity_validation": propagation_continuity.get("activation_validation"),
            "phase2a_rollup": phase2a_bundle.get("rollup_activation_validation"),
            "surface_finding_codes": propagation_surface.get("finding_codes"),
        },
        "realism_scoring_summary": {
            "classification": realism.get("classification"),
            "trace_sample_count": realism.get("trace_sample_count"),
        },
        "replay_reconciliation_summary": {
            "replay_trace_signal_count": realism.get("replay_trace_signal_count"),
            "reconciliation_not_visible_matrix_rows": realism.get("convergence_matrix_reconciliation_not_visible_rows"),
        },
        "rollback_realism_summary": {
            "activation_validation": rollback_realism.get("activation_validation"),
            "artifact_specific_finding_codes": rollback_realism.get("artifact_specific_finding_codes"),
        },
        "schema_version": "operational_staging_evidence_summaries_v1",
    }


def build_rst_core_backbone_staging_runtime_evidence_verification_report(
    *,
    staging_evidence_bundle: Mapping[str, Any],
    generated_at_iso: str,
) -> Dict[str, Any]:
    """
    Master read-only verification report from an exported staging bundle (dict or normalized JSON root).

    Does not mutate runtime, queues, or databases.
    """
    bundle: MutableMapping[str, Any] = dict(staging_evidence_bundle)
    frozen = bundle.get("frozen_governance_bundle")
    if isinstance(frozen, Mapping):
        bundle = merge_frozen_governance_bundle(base_bundle=bundle, frozen_bundle=dict(frozen))

    bundle_norm = normalize_staging_evidence_bundle(bundle)
    harness = assemble_harness_for_staging_verification(bundle_norm)
    traces = extract_transition_traces(bundle_norm)
    conv = extract_convergence_snapshot(bundle_norm)

    propagation = validate_propagation_continuity_burn_in(transition_traces=traces)
    visibility = classify_stale_degraded_runtime_visibility(transition_traces=traces, convergence_snapshot=conv)
    phase2a_bundle = build_phase2a_rst_core_backbone_runtime_validation_bundle(
        harness=harness,
        merged_traces=traces,
        convergence_snapshot=conv,
        propagation=propagation,
        visibility=visibility,
    )

    propagation_surface = validate_staging_export_propagation_surface_integrity(transition_traces=traces)
    convergence_surface = validate_staging_export_convergence_surface_integrity(
        transition_traces=traces,
        convergence_snapshot=conv,
    )
    cross_artifact = validate_staging_export_cross_artifact_alignment(bundle=bundle_norm, harness=harness)
    gov_align = validate_governance_runtime_alignment_phase2a_burn_in(harness=harness)
    rollback_realism = validate_staging_export_rollback_realism(bundle=bundle_norm, harness=harness)

    realism = score_runtime_evidence_realism(
        transition_traces=traces,
        convergence_snapshot=conv,
        propagation_continuity=propagation,
        governance_runtime_alignment=gov_align,
        convergence_surface=convergence_surface,
    )

    staging_confidence = classify_staging_evidence_confidence(
        phase2a_bundle=phase2a_bundle,
        propagation_surface=propagation_surface,
        convergence_surface=convergence_surface,
        cross_artifact=cross_artifact,
        realism_classification=str(realism.get("classification") or ""),
        rollback_realism=rollback_realism,
    )

    readiness = derive_staging_readiness_for_phase2b_review(
        staging_confidence=staging_confidence,
        realism_classification=str(realism.get("classification") or ""),
        phase2a_bundle=phase2a_bundle,
        convergence_surface=convergence_surface,
        cross_artifact=cross_artifact,
    )

    summaries = build_operational_staging_evidence_summaries(
        realism=realism,
        phase2a_bundle=phase2a_bundle,
        propagation_surface=propagation_surface,
        convergence_surface=convergence_surface,
        cross_artifact=cross_artifact,
        rollback_realism=rollback_realism,
        propagation_continuity=propagation,
        visibility=visibility,
        staging_confidence=staging_confidence,
        readiness=readiness,
    )

    explicit_chain = {
        "authority_sync_stability": phase2a_bundle.get("authority_sync_stability"),
        "compliance_gap_sync_recalc_regen_propagation_chain": phase2a_bundle.get("propagation_chain"),
        "recalc_enqueue_and_regen_delegate_metadata": phase2a_bundle.get("recalc_regen_metadata"),
    }

    report: Dict[str, Any] = {
        "audit_only": True,
        "convergence_integrity": convergence_surface,
        "cross_artifact_alignment": cross_artifact,
        "explicit_mutation_to_regen_chain_evidence": explicit_chain,
        "generated_at_iso": generated_at_iso,
        "governance_runtime_alignment_phase2a": gov_align,
        "non_blocking": True,
        "operational_summaries": summaries,
        "phase2a_rst_core_backbone_runtime_validation": phase2a_bundle,
        "propagation_continuity": propagation,
        "propagation_integrity_surface": propagation_surface,
        "readiness_for_phase2b_review": readiness,
        "rollback_realism": rollback_realism,
        "runtime_evidence_realism": realism,
        "staging_confidence_classification": staging_confidence,
        "stale_degraded_visibility": visibility,
        "trace_sample_count": len(traces),
        "transition_traces_digest_sha256": None,
        "schema_version": STAGING_RUNTIME_EVIDENCE_VERIFICATION_SCHEMA_VERSION,
    }

    digest_payload = json.dumps(traces, sort_keys=True, default=str).encode("utf-8")
    report["transition_traces_digest_sha256"] = hashlib.sha256(digest_payload).hexdigest()

    return dict(sorted(report.items(), key=lambda kv: str(kv[0])))


def staging_bundle_supported_schema_versions() -> Tuple[str, ...]:
    """Backward compatibility: declared bundle schema roots."""
    return (STAGING_EVIDENCE_BUNDLE_SCHEMA_VERSION, "staging_runtime_evidence_harness_v1", "operational_burn_in_report_v1")
