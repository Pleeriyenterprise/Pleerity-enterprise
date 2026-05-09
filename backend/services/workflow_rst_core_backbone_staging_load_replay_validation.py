"""
Controlled staging load replay validation — operational entropy & durability (Phase 2B prep).

Replays exported bundles under deterministic trace-pressure patterns (burst, reorder, interleave)
through the existing export-replay validation stack. Read-only, advisory, no queues/workers.

Scope: REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE, COMPLIANCE_SCORE_RECALC,
REGENERATION_RECALC propagation-chain evidence only.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Tuple

from services.workflow_rst_core_backbone_staging_evidence_validation import (
    extract_convergence_snapshot,
    extract_transition_traces,
)
from services.workflow_rst_core_backbone_staging_export_replay_validation import (
    CRITICAL_RUNTIME_DIVERGENCE,
    HIGH_RUNTIME_DIVERGENCE,
    LOW_RUNTIME_DIVERGENCE,
    MODERATE_RUNTIME_DIVERGENCE,
    NO_RUNTIME_DIVERGENCE,
    OPERATIONAL_TRUTH_DRIFT_VISIBLE,
    build_rst_core_backbone_staging_export_replay_validation_report,
    coalesce_staging_export_roots,
)
from services.workflow_runtime_activation_validation import VALIDATION_CONFIRMED, VALIDATION_PARTIAL
from services.workflow_runtime_operational_burn_in import _downstream_rows as burn_in_downstream_rows

LOAD_REPLAY_VALIDATION_SCHEMA_VERSION = "rst_core_backbone_staging_load_replay_validation_v1"

LOW_OPERATIONAL_ENTROPY = "LOW_OPERATIONAL_ENTROPY"
MODERATE_OPERATIONAL_ENTROPY = "MODERATE_OPERATIONAL_ENTROPY"
HIGH_OPERATIONAL_ENTROPY = "HIGH_OPERATIONAL_ENTROPY"
CRITICAL_OPERATIONAL_ENTROPY = "CRITICAL_OPERATIONAL_ENTROPY"

OPERATIONAL_DURABILITY_CONFIRMED = "OPERATIONAL_DURABILITY_CONFIRMED"
OPERATIONAL_DURABILITY_PARTIAL = "OPERATIONAL_DURABILITY_PARTIAL"
OPERATIONAL_DURABILITY_DEGRADED = "OPERATIONAL_DURABILITY_DEGRADED"
OPERATIONAL_DURABILITY_DRIFT_VISIBLE = "OPERATIONAL_DURABILITY_DRIFT_VISIBLE"
OPERATIONAL_DURABILITY_FRAGILE = "OPERATIONAL_DURABILITY_FRAGILE"
OPERATIONAL_DURABILITY_REQUIRES_REVIEW = "OPERATIONAL_DURABILITY_REQUIRES_REVIEW"

READY_FOR_PHASE2B_GOVERNANCE_REVIEW = "READY_FOR_PHASE2B_GOVERNANCE_REVIEW"
HOLD_PENDING_ENTROPY_ALIGNMENT = "HOLD_PENDING_ENTROPY_ALIGNMENT"
HOLD_PENDING_REPLAY_DURABILITY = "HOLD_PENDING_REPLAY_DURABILITY"
HOLD_PENDING_CONVERGENCE_DURABILITY = "HOLD_PENDING_CONVERGENCE_DURABILITY"
HOLD_PENDING_GOVERNANCE_DURABILITY = "HOLD_PENDING_GOVERNANCE_DURABILITY"
HOLD_PENDING_ROLLBACK_DURABILITY = "HOLD_PENDING_ROLLBACK_DURABILITY"

_DIVERGENCE_ORDER = {
    NO_RUNTIME_DIVERGENCE: 0,
    LOW_RUNTIME_DIVERGENCE: 1,
    MODERATE_RUNTIME_DIVERGENCE: 2,
    HIGH_RUNTIME_DIVERGENCE: 3,
    CRITICAL_RUNTIME_DIVERGENCE: 4,
}
_INV_DIVERGENCE = {v: k for k, v in _DIVERGENCE_ORDER.items()}


def _runtime_divergence_classification_from_export_replay_report(report: Mapping[str, Any]) -> str:
    blk = report.get("runtime_divergence") if isinstance(report.get("runtime_divergence"), Mapping) else {}
    return str(blk.get("runtime_divergence_classification") or "") or NO_RUNTIME_DIVERGENCE


def _trace_identity(tr: Mapping[str, Any]) -> Tuple[str, str]:
    return (str(tr.get("transition_id") or ""), str(tr.get("correlation_id") or ""))


def pressure_burst_duplicate_sequence(
    transition_traces: Sequence[Mapping[str, Any]],
    *,
    burst_factor: int,
) -> List[Dict[str, Any]]:
    """Deterministic verbatim duplication (copies only; no field synthesis)."""
    if burst_factor < 1:
        burst_factor = 1
    base = [dict(t) for t in transition_traces if isinstance(t, Mapping)]
    out: List[Dict[str, Any]] = []
    for _ in range(burst_factor):
        out.extend(dict(x) for x in base)
    return out


def pressure_sort_replay_first(transition_traces: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows = [dict(t) for t in transition_traces if isinstance(t, Mapping)]
    rows.sort(
        key=lambda tr: (
            0 if bool(tr.get("replay_chain_detected")) else 1,
            str(tr.get("staging_runtime_flow_kind") or ""),
            _trace_identity(tr)[0],
            _trace_identity(tr)[1],
        )
    )
    return rows


def pressure_sort_replay_last(transition_traces: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows = [dict(t) for t in transition_traces if isinstance(t, Mapping)]
    rows.sort(
        key=lambda tr: (
            1 if bool(tr.get("replay_chain_detected")) else 0,
            str(tr.get("staging_runtime_flow_kind") or ""),
            _trace_identity(tr)[0],
            _trace_identity(tr)[1],
        )
    )
    return rows


def pressure_reverse_lexicographic_tid(transition_traces: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows = [dict(t) for t in transition_traces if isinstance(t, Mapping)]
    rows.sort(key=lambda tr: (_trace_identity(tr)[0], _trace_identity(tr)[1]), reverse=True)
    return rows


def pressure_interleave_halves(transition_traces: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Messy ordering: interleave first/second half (deterministic)."""
    rows = [dict(t) for t in transition_traces if isinstance(t, Mapping)]
    if len(rows) <= 2:
        return list(reversed(rows))
    mid = len(rows) // 2
    a, b = rows[:mid], rows[mid:]
    out: List[Dict[str, Any]] = []
    i = j = 0
    toggle = True
    while i < len(a) or j < len(b):
        if toggle and i < len(a):
            out.append(a[i])
            i += 1
        elif not toggle and j < len(b):
            out.append(b[j])
            j += 1
        elif i < len(a):
            out.append(a[i])
            i += 1
        elif j < len(b):
            out.append(b[j])
            j += 1
        toggle = not toggle
    return out


def pressure_mixed_lineage_two_bundles(
    bundle_a: Mapping[str, Any],
    bundle_b: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Alternate traces from two exports (read-only merge of existing artifacts)."""
    ta = extract_transition_traces(bundle_a)
    tb = extract_transition_traces(bundle_b)
    out: List[Dict[str, Any]] = []
    i = j = 0
    toggle = True
    while i < len(ta) or j < len(tb):
        if toggle and i < len(ta):
            out.append(dict(ta[i]))
            i += 1
        elif not toggle and j < len(tb):
            out.append(dict(tb[j]))
            j += 1
        elif i < len(ta):
            out.append(dict(ta[i]))
            i += 1
        elif j < len(tb):
            out.append(dict(tb[j]))
            j += 1
        toggle = not toggle
    return out


def apply_pressure_transition_traces_to_bundle(
    base_bundle: Mapping[str, Any],
    transition_traces: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Inject a trace sequence into a bundle copy (read-only relative to caller's inputs)."""
    out: MutableMapping[str, Any] = dict(base_bundle)
    out["transition_traces"] = [dict(t) for t in transition_traces if isinstance(t, Mapping)]
    coalesced, _ = coalesce_staging_export_roots(out)
    return dict(coalesced)


def _duplicate_replay_ratio(traces: Sequence[Mapping[str, Any]]) -> float:
    ids = [_trace_identity(t) for t in traces]
    if not ids:
        return 0.0
    return round(1.0 - len(set(ids)) / max(len(ids), 1), 6)


def _replay_lineage_overlap_score(traces: Sequence[Mapping[str, Any]]) -> int:
    """Count replay-flagged traces whose identity appears more than once (overlap pressure)."""
    replay_ids = [_trace_identity(t) for t in traces if bool(t.get("replay_chain_detected"))]
    if not replay_ids:
        return 0
    c = Counter(replay_ids)
    return sum(n for n in c.values() if n > 1)


def _degraded_row_accumulation(traces: Sequence[Mapping[str, Any]]) -> Tuple[int, int]:
    deg = gated = 0
    for tr in traces:
        for r in burn_in_downstream_rows(tr):
            tgt = str(r.get("downstream_target") or "")
            if "compliance_recalc_queue" in tgt or "risk_signal_regen_queue" in tgt:
                gated += 1
                if str(r.get("enqueue_outcome") or "") == "ENQUEUE_DEGRADED":
                    deg += 1
    return deg, max(gated, 1)


def _ordering_instability_rollups(scenario_rollups: Sequence[str]) -> int:
    return len(set(scenario_rollups)) - 1


def classify_operational_entropy_from_pressure_signals(
    *,
    traces_after_pressure: Sequence[Mapping[str, Any]],
    burst_factor_max: int,
    scenario_rollup_labels: Sequence[str],
    join_weak_ratio_max: float,
    convergence_matrix_row_count: int,
    baseline_trace_count: int,
) -> Dict[str, Any]:
    """Deterministic operational entropy tier from pressure-shaped traces and replay outcomes."""
    dup_ratio = _duplicate_replay_ratio(traces_after_pressure)
    overlap = _replay_lineage_overlap_score(traces_after_pressure)
    deg_n, gated_den = _degraded_row_accumulation(traces_after_pressure)
    deg_ratio = round(deg_n / gated_den, 6)
    instab = max(0, _ordering_instability_rollups(scenario_rollup_labels))

    matrix_strain = 0.0
    if baseline_trace_count >= 1 and convergence_matrix_row_count >= 0:
        strain = len(traces_after_pressure) / max(convergence_matrix_row_count, 1)
        matrix_strain = round(strain, 6)

    score = 0
    signals: List[str] = []
    if dup_ratio >= 0.65:
        score += 35
        signals.append("entropy_high_duplicate_replay_ratio")
    elif dup_ratio >= 0.35:
        score += 18
        signals.append("entropy_elevated_duplicate_replay_ratio")

    if burst_factor_max >= 4:
        score += 22
        signals.append("entropy_replay_burst_high")
    elif burst_factor_max >= 2:
        score += 10
        signals.append("entropy_replay_burst_moderate")

    if overlap >= 3:
        score += 28
        signals.append("entropy_replay_lineage_overlap_high")
    elif overlap >= 1:
        score += 14
        signals.append("entropy_replay_lineage_overlap_present")

    if deg_ratio >= 0.35:
        score += 20
        signals.append("entropy_degraded_replay_accumulation_high")
    elif deg_ratio >= 0.15:
        score += 10
        signals.append("entropy_degraded_replay_accumulation_moderate")

    if join_weak_ratio_max >= 0.45:
        score += 24
        signals.append("entropy_join_weak_accumulation_high")
    elif join_weak_ratio_max >= 0.25:
        score += 12
        signals.append("entropy_join_weak_accumulation_moderate")

    if matrix_strain >= 25.0:
        score += 22
        signals.append("entropy_trace_burst_vs_convergence_matrix_strain_high")
    elif matrix_strain >= 10.0:
        score += 11
        signals.append("entropy_trace_burst_vs_convergence_matrix_strain_moderate")

    if instab >= 2:
        score += 18
        signals.append("entropy_replay_ordering_instability_rollups_diverged")
    elif instab == 1:
        score += 8
        signals.append("entropy_replay_ordering_instability_rollups_variant")

    if score >= 72:
        cls = CRITICAL_OPERATIONAL_ENTROPY
    elif score >= 48:
        cls = HIGH_OPERATIONAL_ENTROPY
    elif score >= 22:
        cls = MODERATE_OPERATIONAL_ENTROPY
    else:
        cls = LOW_OPERATIONAL_ENTROPY

    return {
        "burst_factor_max": burst_factor_max,
        "classification": cls,
        "degraded_gated_ratio": deg_ratio,
        "duplicate_replay_ratio": dup_ratio,
        "entropy_score": score,
        "join_weak_ratio_max": round(join_weak_ratio_max, 6),
        "matrix_row_count": convergence_matrix_row_count,
        "replay_lineage_overlap_replays": overlap,
        "rollup_ordering_instability_count": instab,
        "schema_version": "operational_entropy_classification_v1",
        "signals": sorted(set(signals)),
        "trace_burst_vs_matrix_strain_ratio": matrix_strain,
        "trace_count_after_pressure": len(traces_after_pressure),
    }


def validate_observability_durability_under_pressure(
    *,
    pressure_reports: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate observability collapse/orphan signals across pressure scenarios."""
    findings: List[str] = []
    worst_vis = ""
    for pr in pressure_reports:
        vr = pr.get("replay_validation") if isinstance(pr.get("replay_validation"), Mapping) else {}
        base = vr.get("replay_ordered_verification_report") if isinstance(vr.get("replay_ordered_verification_report"), Mapping) else {}
        vis = base.get("stale_degraded_visibility") if isinstance(base.get("stale_degraded_visibility"), Mapping) else {}
        band = str(vis.get("visibility_band") or "")
        if band == "opaque":
            findings.append("durability_visibility_opaque_observed_under_pressure")
        worst_vis = band if band else worst_vis
        prop = base.get("propagation_integrity_surface") if isinstance(base.get("propagation_integrity_surface"), Mapping) else {}
        for fc in prop.get("finding_codes") or []:
            fcs = str(fc)
            if "replay_chain_collapse" in fcs or "orphan" in fcs:
                findings.append(f"durability_propagation_pressure_signal:{fcs}")
        p2 = (
            base.get("phase2a_rst_core_backbone_runtime_validation")
            if isinstance(base.get("phase2a_rst_core_backbone_runtime_validation"), Mapping)
            else {}
        )
        degraded = p2.get("degraded_path_signals") if isinstance(p2.get("degraded_path_signals"), Mapping) else {}
        for fc in degraded.get("finding_codes") or []:
            findings.append(f"durability_degraded_path_pressure:{fc}")
        rr = pr.get("replay_realism") if isinstance(pr.get("replay_realism"), Mapping) else {}
        for fc in rr.get("finding_codes") or []:
            findings.append(f"durability_replay_realism_pressure:{fc}")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "schema_version": "observability_durability_under_pressure_v1",
        "worst_visibility_band_observed": worst_vis or None,
    }


def validate_convergence_durability_under_pressure(
    *,
    pressure_reports: Sequence[Mapping[str, Any]],
    trace_count_max: int,
    convergence_matrix_row_count: int,
) -> Dict[str, Any]:
    findings: List[str] = []
    join_weak_max = 0.0
    for pr in pressure_reports:
        vr = pr.get("replay_validation") if isinstance(pr.get("replay_validation"), Mapping) else {}
        base = vr.get("replay_ordered_verification_report") if isinstance(vr.get("replay_ordered_verification_report"), Mapping) else {}
        conv = base.get("convergence_integrity") if isinstance(base.get("convergence_integrity"), Mapping) else {}
        for fc in conv.get("finding_codes") or []:
            findings.append(f"durability_convergence_pressure:{fc}")
        jw = float((conv.get("convergence_join_weak_ratio") or 0))
        join_weak_max = max(join_weak_max, jw)

    strain = trace_count_max / max(convergence_matrix_row_count, 1)
    if strain >= 25.0 and convergence_matrix_row_count >= 1:
        findings.append("durability_convergence_matrix_strain_under_trace_burst")
    if join_weak_max > 0.5:
        findings.append("durability_join_weak_escalation_under_pressure")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "convergence_join_weak_ratio_max": round(join_weak_max, 6),
        "finding_codes": sorted(set(findings)),
        "matrix_row_count": convergence_matrix_row_count,
        "schema_version": "convergence_durability_under_pressure_v1",
        "trace_to_matrix_strain_ratio_max": round(strain, 6),
    }


def validate_rollback_durability_under_pressure(
    *,
    pressure_reports: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Rollback truth coherence across pressure scenarios (read-only exports)."""
    findings: List[str] = []
    for pr in pressure_reports:
        rb = pr.get("rollback_truth") if isinstance(pr.get("rollback_truth"), Mapping) else {}
        if str(rb.get("activation_validation") or "") != VALIDATION_CONFIRMED:
            for fc in rb.get("artifact_specific_finding_codes") or []:
                findings.append(f"durability_rollback_pressure:{fc}")
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "schema_version": "rollback_durability_under_pressure_v1",
        "simulated_posture_transition_notes": (
            "code_only_rollback_posture_validators_run_inside_each_replay_report;"
            "LIMITED→OBSERVE_ONLY,LIMITED→DISABLED,OBSERVE_ONLY→DISABLED"
        ),
    }


def escalate_runtime_divergence_under_pressure(
    *,
    baseline_divergence_classification: str,
    worst_pressure_divergence_classification: str,
    entropy_classification: str,
) -> Dict[str, Any]:
    """Escalate divergence tier when entropy + pressure surfaces worsen vs baseline."""
    raw = max(
        _DIVERGENCE_ORDER.get(baseline_divergence_classification, 0),
        _DIVERGENCE_ORDER.get(worst_pressure_divergence_classification, 0),
    )
    if entropy_classification == CRITICAL_OPERATIONAL_ENTROPY:
        raw = max(raw, _DIVERGENCE_ORDER[HIGH_RUNTIME_DIVERGENCE])
    elif entropy_classification == HIGH_OPERATIONAL_ENTROPY:
        raw = max(raw, _DIVERGENCE_ORDER[MODERATE_RUNTIME_DIVERGENCE])
    elif entropy_classification == MODERATE_OPERATIONAL_ENTROPY:
        raw = max(raw, _DIVERGENCE_ORDER[LOW_RUNTIME_DIVERGENCE])

    escalated = _INV_DIVERGENCE.get(raw, worst_pressure_divergence_classification)
    bumped = escalated != worst_pressure_divergence_classification or escalated != baseline_divergence_classification
    return {
        "baseline_runtime_divergence_classification": baseline_divergence_classification,
        "entropy_adjustment_applied": entropy_classification
        in (MODERATE_OPERATIONAL_ENTROPY, HIGH_OPERATIONAL_ENTROPY, CRITICAL_OPERATIONAL_ENTROPY),
        "pressure_runtime_divergence_classification": worst_pressure_divergence_classification,
        "runtime_divergence_escalated_classification": escalated,
        "schema_version": "runtime_divergence_pressure_escalation_v1",
        "severity_bumped_vs_pressure_max": bumped,
    }


def classify_operational_durability(
    *,
    observability_durability: Mapping[str, Any],
    convergence_durability: Mapping[str, Any],
    rollback_durability: Mapping[str, Any],
    entropy_classification: str,
    escalated_divergence_classification: str,
    operational_truth_classification: str,
) -> str:
    """Single operational durability advisory classification."""
    if escalated_divergence_classification == CRITICAL_RUNTIME_DIVERGENCE:
        return OPERATIONAL_DURABILITY_REQUIRES_REVIEW
    if entropy_classification == CRITICAL_OPERATIONAL_ENTROPY:
        return OPERATIONAL_DURABILITY_FRAGILE
    if operational_truth_classification == OPERATIONAL_TRUTH_DRIFT_VISIBLE:
        return OPERATIONAL_DURABILITY_DRIFT_VISIBLE
    if escalated_divergence_classification == HIGH_RUNTIME_DIVERGENCE:
        return OPERATIONAL_DURABILITY_DEGRADED
    if entropy_classification == HIGH_OPERATIONAL_ENTROPY:
        return OPERATIONAL_DURABILITY_FRAGILE
    obs = str(observability_durability.get("activation_validation") or "")
    conv = str(convergence_durability.get("activation_validation") or "")
    rb = str(rollback_durability.get("activation_validation") or "")
    if obs != VALIDATION_CONFIRMED or conv != VALIDATION_CONFIRMED or rb != VALIDATION_CONFIRMED:
        return OPERATIONAL_DURABILITY_PARTIAL
    if entropy_classification == MODERATE_OPERATIONAL_ENTROPY:
        return OPERATIONAL_DURABILITY_PARTIAL
    if escalated_divergence_classification in (MODERATE_RUNTIME_DIVERGENCE, LOW_RUNTIME_DIVERGENCE):
        return OPERATIONAL_DURABILITY_PARTIAL
    return OPERATIONAL_DURABILITY_CONFIRMED


def derive_phase2b_governance_review_readiness(
    *,
    operational_durability_classification: str,
    entropy_classification: str,
    escalated_divergence_classification: str,
    observability_durability: Mapping[str, Any],
    convergence_durability: Mapping[str, Any],
    rollback_durability: Mapping[str, Any],
) -> Dict[str, Any]:
    """Advisory governance-review gate after load replay (non-enforcing)."""
    readiness = READY_FOR_PHASE2B_GOVERNANCE_REVIEW
    rationale = "load_replay_durability_ready_for_phase2b_governance_review"

    if entropy_classification in (HIGH_OPERATIONAL_ENTROPY, CRITICAL_OPERATIONAL_ENTROPY):
        readiness = HOLD_PENDING_ENTROPY_ALIGNMENT
        rationale = "high_or_critical_operational_entropy_hold_alignment"
    elif escalated_divergence_classification in (HIGH_RUNTIME_DIVERGENCE, CRITICAL_RUNTIME_DIVERGENCE):
        readiness = HOLD_PENDING_REPLAY_DURABILITY
        rationale = "escalated_runtime_divergence_under_pressure_hold_replay_durability"
    elif str(observability_durability.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_REPLAY_DURABILITY
        rationale = "observability_durability_partial_under_pressure"
    elif str(convergence_durability.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_CONVERGENCE_DURABILITY
        rationale = "convergence_durability_partial_under_pressure"
    elif str(rollback_durability.get("activation_validation") or "") != VALIDATION_CONFIRMED:
        readiness = HOLD_PENDING_ROLLBACK_DURABILITY
        rationale = "rollback_durability_partial_under_pressure"
    elif operational_durability_classification in (
        OPERATIONAL_DURABILITY_DEGRADED,
        OPERATIONAL_DURABILITY_FRAGILE,
        OPERATIONAL_DURABILITY_REQUIRES_REVIEW,
    ):
        readiness = HOLD_PENDING_GOVERNANCE_DURABILITY
        rationale = "operational_durability_degraded_fragile_or_requires_review"
    elif operational_durability_classification in (
        OPERATIONAL_DURABILITY_PARTIAL,
        OPERATIONAL_DURABILITY_DRIFT_VISIBLE,
    ):
        readiness = HOLD_PENDING_GOVERNANCE_DURABILITY
        rationale = "operational_durability_partial_or_drift_visible_hold_governance_review"

    return {
        "advisory_only": True,
        "non_blocking": True,
        "operational_durability_classification": operational_durability_classification,
        "rationale_code": rationale,
        "readiness_classification": readiness,
        "schema_version": "phase2b_governance_review_readiness_load_replay_v1",
    }


def build_load_replay_pressure_summaries(
    *,
    entropy: Mapping[str, Any],
    observability_durability: Mapping[str, Any],
    convergence_durability: Mapping[str, Any],
    rollback_durability: Mapping[str, Any],
    divergence_escalation: Mapping[str, Any],
    operational_durability: str,
    lineage_summary: Mapping[str, Any],
    readiness: Mapping[str, Any],
    scenario_labels: Sequence[str],
) -> Dict[str, Any]:
    """Replay-pressure operational summaries (deterministic)."""
    return {
        "convergence_durability_summary": {
            "activation_validation": convergence_durability.get("activation_validation"),
            "finding_codes": convergence_durability.get("finding_codes"),
            "join_weak_ratio_max": convergence_durability.get("convergence_join_weak_ratio_max"),
            "trace_to_matrix_strain_ratio_max": convergence_durability.get("trace_to_matrix_strain_ratio_max"),
        },
        "degraded_replay_summary": {"degraded_gated_ratio": entropy.get("degraded_gated_ratio")},
        "governance_durability_summary": {"operational_durability_classification": operational_durability},
        "operational_durability_summary": {"classification": operational_durability},
        "operational_entropy_summary": {
            "classification": entropy.get("classification"),
            "entropy_score": entropy.get("entropy_score"),
            "signals": entropy.get("signals"),
        },
        "replay_durability_summary": {
            "activation_validation": observability_durability.get("activation_validation"),
            "finding_codes": observability_durability.get("finding_codes"),
        },
        "replay_lineage_summary": dict(lineage_summary),
        "replay_validation_summary": {"scenario_count": len(scenario_labels), "scenario_labels": list(scenario_labels)},
        "rollback_durability_summary": {
            "activation_validation": rollback_durability.get("activation_validation"),
            "finding_codes": rollback_durability.get("finding_codes"),
        },
        "runtime_divergence_escalation_summary": {
            "escalated_classification": divergence_escalation.get("runtime_divergence_escalated_classification"),
            "pressure_max_classification": divergence_escalation.get("pressure_runtime_divergence_classification"),
        },
        "schema_version": "load_replay_pressure_summaries_v1",
        "stale_replay_summary": {"ordering_instability_count": entropy.get("rollup_ordering_instability_count")},
        "phase2b_governance_review_confidence_summary": {
            "readiness_classification": readiness.get("readiness_classification"),
            "rationale_code": readiness.get("rationale_code"),
        },
    }


def build_rst_core_backbone_staging_load_replay_validation_report(
    *,
    staging_capture_bundle: Mapping[str, Any],
    generated_at_iso: str,
    burst_factors: Sequence[int] = (1, 2, 4),
    include_ordering_variants: bool = True,
    secondary_capture_bundle: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Run deterministic replay-pressure scenarios through the export-replay validation stack.

    ``burst_factors`` include 1 as baseline-equivalent (single copy). Larger values duplicate the
    entire exported trace list verbatim that many times.
    """
    coalesced, _ = coalesce_staging_export_roots(staging_capture_bundle)
    base_traces = extract_transition_traces(coalesced)
    baseline_tc = max(len(base_traces), 1)
    conv = extract_convergence_snapshot(coalesced)
    cem = conv.get("convergence_evidence_matrix") if isinstance(conv.get("convergence_evidence_matrix"), Mapping) else {}
    mrows = cem.get("matrix_rows") if isinstance(cem.get("matrix_rows"), list) else []
    matrix_n = len([x for x in mrows if isinstance(x, Mapping)])

    scenarios: List[Tuple[str, List[Dict[str, Any]]]] = []

    for bf in sorted(set(int(x) for x in burst_factors if int(x) >= 1)):
        label = f"burst_{bf}x"
        scenarios.append((label, pressure_burst_duplicate_sequence(base_traces, burst_factor=bf)))

    if include_ordering_variants and base_traces:
        scenarios.append(("ordering_replay_first", pressure_sort_replay_first(base_traces)))
        scenarios.append(("ordering_replay_last", pressure_sort_replay_last(base_traces)))
        scenarios.append(("ordering_reverse_lexicographic_tid", pressure_reverse_lexicographic_tid(base_traces)))
        scenarios.append(("ordering_interleave_halves", pressure_interleave_halves(base_traces)))

    if secondary_capture_bundle is not None:
        coalesced_b, _ = coalesce_staging_export_roots(secondary_capture_bundle)
        scenarios.append(
            ("mixed_lineage_two_exports", pressure_mixed_lineage_two_bundles(coalesced, coalesced_b)),
        )

    pressure_reports: List[Dict[str, Any]] = []
    scenario_rollups: List[str] = []
    divergences: List[str] = []
    join_weak_max = 0.0
    trace_max = 0
    scenario_labels: List[str] = []

    baseline_report = build_rst_core_backbone_staging_export_replay_validation_report(
        staging_capture_bundle=coalesced,
        generated_at_iso=generated_at_iso,
    )
    baseline_div = _runtime_divergence_classification_from_export_replay_report(baseline_report)

    for label, seq in scenarios:
        scenario_labels.append(label)
        pressured_bundle = apply_pressure_transition_traces_to_bundle(coalesced, seq)
        pr = build_rst_core_backbone_staging_export_replay_validation_report(
            staging_capture_bundle=pressured_bundle,
            generated_at_iso=generated_at_iso,
        )
        pressure_reports.append(pr)
        vr = pr["replay_validation"]["replay_ordered_verification_report"]
        p2v = (
            vr.get("phase2a_rst_core_backbone_runtime_validation")
            if isinstance(vr.get("phase2a_rst_core_backbone_runtime_validation"), Mapping)
            else {}
        )
        rollup = str(p2v.get("rollup_activation_validation") or "")
        scenario_rollups.append(rollup or "UNKNOWN")
        div = _runtime_divergence_classification_from_export_replay_report(pr)
        divergences.append(div)
        conv_i = vr.get("convergence_integrity") if isinstance(vr.get("convergence_integrity"), Mapping) else {}
        join_weak_max = max(join_weak_max, float(conv_i.get("convergence_join_weak_ratio") or 0))
        trace_max = max(trace_max, len(seq))

    burst_max = max((int(x) for x in burst_factors if int(x) >= 1), default=1)

    longest_pressure_traces = max((seq for _, seq in scenarios), key=len, default=[]) if scenarios else []
    entropy_traces = longest_pressure_traces if longest_pressure_traces else base_traces

    entropy = classify_operational_entropy_from_pressure_signals(
        traces_after_pressure=entropy_traces,
        burst_factor_max=burst_max,
        scenario_rollup_labels=scenario_rollups,
        join_weak_ratio_max=join_weak_max,
        convergence_matrix_row_count=matrix_n,
        baseline_trace_count=baseline_tc,
    )

    obs_dur = validate_observability_durability_under_pressure(pressure_reports=pressure_reports)
    conv_dur = validate_convergence_durability_under_pressure(
        pressure_reports=pressure_reports,
        trace_count_max=trace_max,
        convergence_matrix_row_count=matrix_n,
    )
    rb_dur = validate_rollback_durability_under_pressure(pressure_reports=pressure_reports)

    worst_pressure_div = max(divergences, key=lambda d: _DIVERGENCE_ORDER.get(d, 0))

    divergence_escalation = escalate_runtime_divergence_under_pressure(
        baseline_divergence_classification=baseline_div,
        worst_pressure_divergence_classification=worst_pressure_div,
        entropy_classification=str(entropy.get("classification") or ""),
    )

    operational_truth = str(baseline_report.get("operational_truth_classification") or "")

    lineage_summary = {
        "duplicate_replay_ratio_max": entropy.get("duplicate_replay_ratio"),
        "replay_lineage_overlap_replays": entropy.get("replay_lineage_overlap_replays"),
        "trace_count_max_under_pressure": trace_max,
    }

    operational_durability = classify_operational_durability(
        observability_durability=obs_dur,
        convergence_durability=conv_dur,
        rollback_durability=rb_dur,
        entropy_classification=str(entropy.get("classification") or ""),
        escalated_divergence_classification=str(divergence_escalation.get("runtime_divergence_escalated_classification") or ""),
        operational_truth_classification=operational_truth,
    )

    readiness = derive_phase2b_governance_review_readiness(
        operational_durability_classification=operational_durability,
        entropy_classification=str(entropy.get("classification") or ""),
        escalated_divergence_classification=str(divergence_escalation.get("runtime_divergence_escalated_classification") or ""),
        observability_durability=obs_dur,
        convergence_durability=conv_dur,
        rollback_durability=rb_dur,
    )

    summaries = build_load_replay_pressure_summaries(
        entropy=entropy,
        observability_durability=obs_dur,
        convergence_durability=conv_dur,
        rollback_durability=rb_dur,
        divergence_escalation=divergence_escalation,
        operational_durability=operational_durability,
        lineage_summary=lineage_summary,
        readiness=readiness,
        scenario_labels=scenario_labels,
    )

    report: Dict[str, Any] = {
        "audit_only": True,
        "baseline_export_replay_report": baseline_report,
        "generated_at_iso": generated_at_iso,
        "non_blocking": True,
        "operational_durability_classification": operational_durability,
        "operational_entropy": entropy,
        "pressure_scenario_labels": scenario_labels,
        "pressure_scenario_reports": pressure_reports,
        "readiness_gate_phase2b_governance_review": readiness,
        "replay_pressure_summaries": summaries,
        "rollback_durability_under_pressure": rb_dur,
        "runtime_divergence_pressure_escalation": divergence_escalation,
        "schema_version": LOAD_REPLAY_VALIDATION_SCHEMA_VERSION,
        "validate_convergence_durability_under_pressure": conv_dur,
        "validate_observability_durability_under_pressure": obs_dur,
    }
    report["load_replay_campaign_digest_sha256"] = hashlib.sha256(
        json.dumps(scenario_labels + divergences + scenario_rollups, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return dict(sorted(report.items(), key=lambda kv: str(kv[0])))


def load_replay_pressure_supported_controls() -> Tuple[str, ...]:
    """Documented control knobs (read-only harness)."""
    return ("burst_factors", "include_ordering_variants", "secondary_capture_bundle")
