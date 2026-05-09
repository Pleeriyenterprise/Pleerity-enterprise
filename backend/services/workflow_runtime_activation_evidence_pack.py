"""
Phase 1C: staging/runtime-shaped evidence pack for COMPLIANCE_SCORE_RECALC (read-only).

Assembles registry snapshot, validation snapshot, governance summaries, convergence,
queue visibility, and representative samples into one deterministic JSON-shaped pack.
Optional filesystem export only — no DB writes, no activation changes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from services.compliance_recalc_queue import EnqueueComplianceRecalcResult
from services.workflow_activation_governance_report import build_workflow_activation_governance_report
from services.workflow_activation_readiness import FAMILY_COMPLIANCE_SCORE_RECALC
from services.workflow_runtime_activation_registry import (
    ACTIVATION_GOVERNANCE_VERSION,
    build_rst_core_backbone_activation_operational_visibility,
    resolve_compliance_recalc_activation_gate,
    resolve_requirement_state_transition_core_backbone_gate,
)
from services.workflow_runtime_activation_validation import (
    CRITICAL_VALIDATION_DRIFT,
    HIGH_VALIDATION_DRIFT,
    LOW_VALIDATION_DRIFT,
    MODERATE_VALIDATION_DRIFT,
    VALIDATION_CONFIRMED,
    VALIDATION_DEGRADED,
    VALIDATION_FAILED,
    VALIDATION_INSUFFICIENT_EVIDENCE,
    VALIDATION_PARTIAL,
    build_activation_continuity_summary,
    build_activation_rollback_summary,
    build_activation_validation_summary,
    build_runtime_activation_validation_snapshot,
)
from services.workflow_runtime_convergence_observability import build_runtime_convergence_snapshot

EVIDENCE_PACK_VERSION = "workflow_runtime_activation_evidence_pack_v1"

# --- Representative evidence quality (advisory) ---
REPRESENTATIVE_EVIDENCE_CONFIRMED = "REPRESENTATIVE_EVIDENCE_CONFIRMED"
REPRESENTATIVE_EVIDENCE_PARTIAL = "REPRESENTATIVE_EVIDENCE_PARTIAL"
REPRESENTATIVE_EVIDENCE_LIMITED = "REPRESENTATIVE_EVIDENCE_LIMITED"
REPRESENTATIVE_EVIDENCE_INSUFFICIENT = "REPRESENTATIVE_EVIDENCE_INSUFFICIENT"

# --- Runtime consistency (per dimension) ---
CONSISTENT = "CONSISTENT"
PARTIAL = "PARTIAL"
DEGRADED = "DEGRADED"
UNKNOWN = "UNKNOWN"

# --- Staging drift (advisory; distinct labels from validation drift) ---
LOW_STAGING_DRIFT = "LOW_STAGING_DRIFT"
MODERATE_STAGING_DRIFT = "MODERATE_STAGING_DRIFT"
HIGH_STAGING_DRIFT = "HIGH_STAGING_DRIFT"
CRITICAL_STAGING_DRIFT = "CRITICAL_STAGING_DRIFT"

# --- Readiness conclusions (advisory) ---
READY_FOR_CONTINUED_LIMITED_ACTIVATION = "READY_FOR_CONTINUED_LIMITED_ACTIVATION"
READY_FOR_INCREMENTAL_EXPANSION_REVIEW = "READY_FOR_INCREMENTAL_EXPANSION_REVIEW"
HOLD_PENDING_MORE_RUNTIME_EVIDENCE = "HOLD_PENDING_MORE_RUNTIME_EVIDENCE"
HOLD_PENDING_GOVERNANCE_REVIEW = "HOLD_PENDING_GOVERNANCE_REVIEW"
HOLD_PENDING_CONVERGENCE_ALIGNMENT = "HOLD_PENDING_CONVERGENCE_ALIGNMENT"

_VALIDATION_TO_STAGING_DRIFT = {
    LOW_VALIDATION_DRIFT: LOW_STAGING_DRIFT,
    MODERATE_VALIDATION_DRIFT: MODERATE_STAGING_DRIFT,
    HIGH_VALIDATION_DRIFT: HIGH_STAGING_DRIFT,
    CRITICAL_VALIDATION_DRIFT: CRITICAL_STAGING_DRIFT,
}


def _sort_key_trace(t: Mapping[str, Any]) -> Tuple[str, str]:
    return (str(t.get("transition_id") or ""), str(t.get("correlation_id") or ""))


def _downstream_rows(trace: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    rows = trace.get("downstream_trigger_targets") or trace.get("downstream_propagation") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, Mapping)]


def _extract_downstream_samples(
    transition_traces: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> List[Dict[str, Any]]:
    collected: List[Dict[str, Any]] = []
    for tr in sorted(transition_traces, key=_sort_key_trace):
        for row in _downstream_rows(tr):
            collected.append(dict(sorted(dict(row).items(), key=lambda kv: str(kv[0]))))
            if len(collected) >= limit:
                return collected
    return collected


def _matrix_row_count(convergence: Mapping[str, Any]) -> int:
    cem = convergence.get("convergence_evidence_matrix") or {}
    rows = cem.get("matrix_rows") if isinstance(cem, Mapping) else None
    if isinstance(rows, list):
        return len(rows)
    return 0


def classify_representative_evidence(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    representative_enqueue_samples: Sequence[Any],
    governance_report: Mapping[str, Any],
    convergence_snapshot: Mapping[str, Any],
) -> str:
    """Advisory classification from counts and visibility (deterministic)."""
    n_tr = len(transition_traces)
    n_ds = sum(len(_downstream_rows(t)) for t in transition_traces)
    n_enq = len(representative_enqueue_samples)
    n_mx = _matrix_row_count(convergence_snapshot)

    rt = governance_report.get("runtime_activation_snapshot")
    gov_ok = isinstance(rt, Mapping) and bool(rt.get("families")) and bool(rt.get("activation_governance_version"))
    conv_ok = n_mx >= 1

    if n_tr >= 2 and n_ds >= 1 and n_enq >= 1 and gov_ok and conv_ok:
        return REPRESENTATIVE_EVIDENCE_CONFIRMED
    if n_tr >= 1 and (n_ds >= 1 or n_enq >= 1) and gov_ok:
        return REPRESENTATIVE_EVIDENCE_PARTIAL
    if n_tr >= 1 or n_enq >= 1 or gov_ok:
        return REPRESENTATIVE_EVIDENCE_LIMITED
    return REPRESENTATIVE_EVIDENCE_INSUFFICIENT


def _map_validation_band_to_consistency(activation_validation: str) -> str:
    v = str(activation_validation or "")
    if v == VALIDATION_CONFIRMED:
        return CONSISTENT
    if v in (VALIDATION_PARTIAL,):
        return PARTIAL
    if v in (VALIDATION_FAILED, VALIDATION_DEGRADED):
        return DEGRADED
    return UNKNOWN


def derive_runtime_consistency_findings(
    *,
    validation_snapshot: Mapping[str, Any],
    governance_report_summary: Mapping[str, Any],
    convergence_snapshot: Mapping[str, Any],
    representative_evidence_class: str,
) -> Dict[str, Any]:
    """Per-dimension consistency (advisory; no enforcement)."""
    gate = validation_snapshot.get("gate_validation") if isinstance(validation_snapshot.get("gate_validation"), Mapping) else {}
    regen_gate = (
        validation_snapshot.get("regeneration_recalc_gate_validation")
        if isinstance(validation_snapshot.get("regeneration_recalc_gate_validation"), Mapping)
        else {}
    )
    rst_bb_gate = (
        validation_snapshot.get("rst_core_backbone_gate_validation")
        if isinstance(validation_snapshot.get("rst_core_backbone_gate_validation"), Mapping)
        else {}
    )
    a1 = _map_validation_band_to_consistency(str(gate.get("activation_validation") or ""))
    a2 = _map_validation_band_to_consistency(str(regen_gate.get("activation_validation") or ""))
    a3 = _map_validation_band_to_consistency(str(rst_bb_gate.get("activation_validation") or ""))
    axes = [a1, a2, a3]
    if any(a == DEGRADED for a in axes):
        activation_runtime_consistency = DEGRADED
    elif any(a == PARTIAL for a in axes):
        activation_runtime_consistency = PARTIAL
    elif all(a == CONSISTENT for a in axes):
        activation_runtime_consistency = CONSISTENT
    elif all(a == UNKNOWN for a in axes):
        activation_runtime_consistency = UNKNOWN
    else:
        activation_runtime_consistency = PARTIAL

    enq_blocks = list(validation_snapshot.get("enqueue_sample_validations") or [])
    enq_blocks.extend(list(validation_snapshot.get("regeneration_enqueue_sample_validations") or []))
    if isinstance(enq_blocks, list) and enq_blocks:
        states = [str(b.get("continuity", {}).get("activation_validation") or "") for b in enq_blocks if isinstance(b, Mapping)]
        if all(s == VALIDATION_CONFIRMED for s in states):
            enqueue_runtime_consistency = CONSISTENT
        elif any(s == VALIDATION_FAILED for s in states):
            enqueue_runtime_consistency = DEGRADED
        elif any(s == VALIDATION_PARTIAL for s in states):
            enqueue_runtime_consistency = PARTIAL
        else:
            enqueue_runtime_consistency = UNKNOWN
    else:
        enqueue_runtime_consistency = UNKNOWN

    down = validation_snapshot.get("transition_downstream_observability")
    if isinstance(down, Mapping):
        downstream_runtime_consistency = _map_validation_band_to_consistency(str(down.get("activation_validation") or ""))
    else:
        downstream_runtime_consistency = UNKNOWN

    gov_vis = validation_snapshot.get("governance_runtime_visibility")
    if isinstance(gov_vis, Mapping):
        governance_runtime_alignment = _map_validation_band_to_consistency(str(gov_vis.get("activation_validation") or ""))
    else:
        governance_runtime_alignment = UNKNOWN

    # Convergence: weak matrix / no rows => UNKNOWN or PARTIAL
    n_mx = _matrix_row_count(convergence_snapshot)
    if n_mx == 0:
        convergence_runtime_alignment = UNKNOWN
    elif representative_evidence_class == REPRESENTATIVE_EVIDENCE_INSUFFICIENT:
        convergence_runtime_alignment = PARTIAL
    else:
        convergence_runtime_alignment = CONSISTENT

    rb_summary = governance_report_summary.get("rollback_posture_summary")
    if isinstance(rb_summary, Mapping) and rb_summary.get("schema_version"):
        rollback_runtime_alignment = CONSISTENT
    else:
        rollback_runtime_alignment = PARTIAL

    rc_summary = governance_report_summary.get("runtime_confidence_summary")
    if isinstance(rc_summary, Mapping) and rc_summary.get("schema_version"):
        obs_hist = list(validation_snapshot.get("enqueue_sample_validations") or [])
        obs_hist.extend(list(validation_snapshot.get("regeneration_enqueue_sample_validations") or []))
        obs_partial = any(
            isinstance(b, Mapping) and str(b.get("observability", {}).get("observability") or "") != "OBSERVABILITY_CONFIRMED"
            for b in obs_hist
        )
        observability_runtime_alignment = PARTIAL if obs_partial else CONSISTENT
    else:
        observability_runtime_alignment = UNKNOWN

    return {
        "activation_runtime_consistency": activation_runtime_consistency,
        "convergence_runtime_alignment": convergence_runtime_alignment,
        "downstream_runtime_consistency": downstream_runtime_consistency,
        "enqueue_runtime_consistency": enqueue_runtime_consistency,
        "governance_runtime_alignment": governance_runtime_alignment,
        "observability_runtime_alignment": observability_runtime_alignment,
        "rollback_runtime_alignment": rollback_runtime_alignment,
        "schema_version": "activation_runtime_consistency_v1",
    }


def _validation_drift_to_staging(drift_classification: str) -> str:
    return _VALIDATION_TO_STAGING_DRIFT.get(str(drift_classification or ""), MODERATE_STAGING_DRIFT)


def classify_staging_drift(
    *,
    drift_validation_summary: Mapping[str, Any],
    governance_report_summary: Mapping[str, Any],
    convergence_snapshot: Mapping[str, Any],
) -> str:
    """Staging drift band: validation drift plus light governance/convergence signals."""
    base = str((drift_validation_summary or {}).get("drift_classification") or LOW_VALIDATION_DRIFT)
    staging = _validation_drift_to_staging(base)

    gdr = governance_report_summary.get("governance_drift_summary")
    if isinstance(gdr, Mapping):
        n = int(gdr.get("governance_drift_detected_count") or 0)
        esc = int(gdr.get("governance_review_escalation_recommended_count") or 0)
        if esc > 0 and staging == LOW_STAGING_DRIFT:
            staging = MODERATE_STAGING_DRIFT
        if n > 2 and staging in (LOW_STAGING_DRIFT, MODERATE_STAGING_DRIFT):
            staging = HIGH_STAGING_DRIFT

    if base == CRITICAL_VALIDATION_DRIFT:
        staging = CRITICAL_STAGING_DRIFT
    return staging


def derive_readiness_conclusion(
    *,
    representative_evidence_class: str,
    staging_drift_classification: str,
    validation_overall: str,
    governance_report_summary: Mapping[str, Any],
    convergence_snapshot: Mapping[str, Any],
) -> Dict[str, Any]:
    """Advisory readiness posture — no automatic activation expansion."""
    gdr = governance_report_summary.get("governance_drift_summary")
    drift_n = int(gdr.get("governance_drift_detected_count") or 0) if isinstance(gdr, Mapping) else 0
    esc_n = int(gdr.get("governance_review_escalation_recommended_count") or 0) if isinstance(gdr, Mapping) else 0

    conv_summary = governance_report_summary.get("convergence_visibility_summary")
    low_conf = False
    if isinstance(conv_summary, Mapping):
        bym = conv_summary.get("by_convergence_confidence") or {}
        if isinstance(bym, Mapping):
            low_conf = int(bym.get("LOW_CONVERGENCE_CONFIDENCE") or 0) > int(bym.get("HIGH_CONVERGENCE_CONFIDENCE") or 0)

    readiness = HOLD_PENDING_MORE_RUNTIME_EVIDENCE
    expansion = "NO_EXPANSION_RECOMMENDED"
    posture = "LIMITED_ACTIVATION_EVIDENCE_UNDER_REVIEW"

    if staging_drift_classification == CRITICAL_STAGING_DRIFT or validation_overall == VALIDATION_FAILED:
        readiness = HOLD_PENDING_GOVERNANCE_REVIEW
        expansion = "NO_EXPANSION_RECOMMENDED"
        posture = "LIMITED_ACTIVATION_BLOCKED_BY_VALIDATION_OR_DRIFT"
    elif esc_n > 0 or drift_n > 2:
        readiness = HOLD_PENDING_GOVERNANCE_REVIEW
        expansion = "REVIEW_GOVERNANCE_DRIFT_BEFORE_EXPANSION"
        posture = "LIMITED_ACTIVATION_WITH_GOVERNANCE_DRIFT_SIGNALS"
    elif representative_evidence_class == REPRESENTATIVE_EVIDENCE_INSUFFICIENT:
        readiness = HOLD_PENDING_MORE_RUNTIME_EVIDENCE
        expansion = "NO_EXPANSION_RECOMMENDED"
        posture = "LIMITED_ACTIVATION_INSUFFICIENT_REPRESENTATIVE_EVIDENCE"
    elif low_conf or _matrix_row_count(convergence_snapshot) == 0:
        readiness = HOLD_PENDING_CONVERGENCE_ALIGNMENT
        expansion = "NO_EXPANSION_RECOMMENDED"
        posture = "LIMITED_ACTIVATION_CONVERGENCE_EVIDENCE_WEAK"
    elif (
        representative_evidence_class == REPRESENTATIVE_EVIDENCE_CONFIRMED
        and staging_drift_classification == LOW_STAGING_DRIFT
        and validation_overall == VALIDATION_CONFIRMED
    ):
        readiness = READY_FOR_CONTINUED_LIMITED_ACTIVATION
        expansion = "CONTINUE_LIMITED_SCOPE_ONLY"
        posture = "LIMITED_ACTIVATION_REPRESENTATIVE_EVIDENCE_STRONG"
    elif representative_evidence_class in (REPRESENTATIVE_EVIDENCE_PARTIAL, REPRESENTATIVE_EVIDENCE_CONFIRMED) and staging_drift_classification in (
        LOW_STAGING_DRIFT,
        MODERATE_STAGING_DRIFT,
    ):
        readiness = READY_FOR_INCREMENTAL_EXPANSION_REVIEW
        expansion = "HUMAN_REVIEW_BEFORE_ANY_FAMILY_EXPANSION"
        posture = "LIMITED_ACTIVATION_INCREMENTAL_REVIEW_RECOMMENDED"

    return {
        "activation_expansion_recommendation": expansion,
        "operational_activation_posture": posture,
        "readiness_conclusion": readiness,
        "schema_version": "activation_readiness_conclusion_v1",
    }


def _governance_report_summary(full_report: Mapping[str, Any]) -> Dict[str, Any]:
    fams = full_report.get("family_activation_reports") or []
    n_fam = len(fams) if isinstance(fams, list) else 0
    keys_in = (
        "report_version",
        "generated_at",
        "activation_readiness_summary",
        "convergence_visibility_summary",
        "runtime_confidence_summary",
        "rollback_posture_summary",
        "governance_drift_summary",
        "governance_readiness_overview",
    )
    out: Dict[str, Any] = {k: full_report[k] for k in keys_in if k in full_report}
    out["family_activation_reports_count"] = n_fam
    out["schema_version"] = "governance_report_summary_v1"
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def _queue_visibility_summary(qv: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not qv:
        return {"schema_version": "queue_visibility_summary_v1", "present": False}
    diag = qv.get("diagnostics") if isinstance(qv.get("diagnostics"), Mapping) else {}
    slim = {
        "present": True,
        "returned_count": diag.get("returned_count"),
        "skipped_unbounded_scan": diag.get("skipped_unbounded_scan"),
    }
    return {"diagnostics": dict(sorted(slim.items(), key=lambda kv: str(kv[0]))), "schema_version": "queue_visibility_summary_v1"}


def _observability_validation_summary(validation_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    by_obs: Dict[str, int] = {}
    for sample in validation_snapshot.get("enqueue_sample_validations") or []:
        if not isinstance(sample, Mapping):
            continue
        obs = sample.get("observability")
        if isinstance(obs, Mapping):
            k = str(obs.get("observability") or "UNKNOWN")
            by_obs[k] = by_obs.get(k, 0) + 1
    down = validation_snapshot.get("transition_downstream_observability")
    if isinstance(down, Mapping):
        k = str(down.get("observability") or "UNKNOWN")
        by_obs[k] = by_obs.get(k, 0) + 1
    return {
        "by_observability_band": dict(sorted(by_obs.items())),
        "schema_version": "observability_validation_summary_v1",
    }


def _drift_validation_summary(validation_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    drift = validation_snapshot.get("drift")
    if not isinstance(drift, Mapping):
        return {"drift_classification": LOW_VALIDATION_DRIFT, "finding_codes": [], "schema_version": "drift_validation_summary_v1"}
    return {
        "drift_classification": drift.get("drift_classification"),
        "finding_codes": list(drift.get("finding_codes") or []),
        "schema_version": "drift_validation_summary_v1",
    }


def _staging_drift_findings(
    *,
    staging_drift_classification: str,
    drift_validation_summary: Mapping[str, Any],
    governance_report_summary: Mapping[str, Any],
    convergence_snapshot: Mapping[str, Any],
) -> Dict[str, Any]:
    """Structured staging drift axes (advisory)."""
    codes = set(drift_validation_summary.get("finding_codes") or [])
    conv_drift = MODERATE_STAGING_DRIFT if _matrix_row_count(convergence_snapshot) == 0 else LOW_STAGING_DRIFT
    axes = {
        "activation_drift": staging_drift_classification,
        "convergence_drift": conv_drift,
        "governance_drift": MODERATE_STAGING_DRIFT
        if int((governance_report_summary.get("governance_drift_summary") or {}).get("governance_drift_detected_count") or 0) > 0
        else LOW_STAGING_DRIFT,
        "observability_drift": MODERATE_STAGING_DRIFT
        if any(str(x).startswith("downstream_") for x in codes)
        else LOW_STAGING_DRIFT,
        "rollback_drift": LOW_STAGING_DRIFT,
        "runtime_confidence_drift": LOW_STAGING_DRIFT,
    }
    if any("convergence" in c for c in codes):
        axes["convergence_drift"] = MODERATE_STAGING_DRIFT
    if staging_drift_classification in (HIGH_STAGING_DRIFT, CRITICAL_STAGING_DRIFT):
        axes["activation_drift"] = staging_drift_classification
    return {
        "axes": dict(sorted(axes.items(), key=lambda kv: str(kv[0]))),
        "overall_staging_drift": staging_drift_classification,
        "schema_version": "staging_drift_findings_v1",
    }


def _activation_operational_findings(
    *,
    representative_evidence_class: str,
    consistency: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> Dict[str, Any]:
    notes = sorted(
        {
            f"representative_evidence={representative_evidence_class}",
            f"readiness={readiness.get('readiness_conclusion')}",
            f"posture={readiness.get('operational_activation_posture')}",
        }
    )
    return {
        "consistency_axes": {k: v for k, v in consistency.items() if k != "schema_version"},
        "finding_codes": notes,
        "schema_version": "activation_operational_findings_v1",
    }


def compliance_enqueue_samples_as_result_tuples(
    samples: Sequence[Mapping[str, Any]],
) -> List[Tuple[Dict[str, Any], EnqueueComplianceRecalcResult]]:
    """Public helper for burn-in / dual-family validators (read-only tuple conversion)."""
    return _enqueue_samples_to_tuples(samples)


def regeneration_enqueue_samples_as_mapping_tuples(
    samples: Sequence[Mapping[str, Any]],
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Public helper for burn-in / dual-family validators (read-only tuple conversion)."""
    return _regeneration_enqueue_samples_to_tuples(samples)


def _enqueue_samples_to_tuples(
    samples: Sequence[Mapping[str, Any]],
) -> List[Tuple[Dict[str, Any], EnqueueComplianceRecalcResult]]:
    out: List[Tuple[Dict[str, Any], EnqueueComplianceRecalcResult]] = []
    for raw in samples:
        if not isinstance(raw, Mapping):
            continue
        gate = dict(raw.get("gate") or {})
        body = dict(raw.get("enqueue") or {})
        er = EnqueueComplianceRecalcResult(
            enqueued=bool(body.get("enqueued")),
            correlation_id=str(body.get("correlation_id") or ""),
            duplicate_suppression_reason=body.get("duplicate_suppression_reason"),
            regeneration_requeued=bool(body.get("regeneration_requeued", False)),
            regeneration_error=body.get("regeneration_error"),
            activation_skipped=bool(body.get("activation_skipped", False)),
            activation_state=body.get("activation_state"),
            activation_reason=body.get("activation_reason"),
            activation_scope=body.get("activation_scope"),
            activation_family=body.get("activation_family"),
            activation_guard_result=body.get("activation_guard_result"),
            activation_governance_version=body.get("activation_governance_version"),
        )
        out.append((gate, er))
    return out


def _regeneration_enqueue_samples_to_tuples(
    samples: Sequence[Mapping[str, Any]],
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    out: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for raw in samples:
        if not isinstance(raw, Mapping):
            continue
        gate = dict(raw.get("gate") or {})
        body = dict(raw.get("enqueue") or {})
        out.append((gate, body))
    return out


def build_runtime_activation_evidence_pack(
    *,
    generated_at: str,
    activation_family: str = FAMILY_COMPLIANCE_SCORE_RECALC,
    transition_traces: Sequence[Mapping[str, Any]] = (),
    queue_visibility: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    convergence_snapshot: Optional[Mapping[str, Any]] = None,
    governance_report: Optional[Mapping[str, Any]] = None,
    governance_families: Optional[Sequence[str]] = None,
    representative_enqueue_samples: Sequence[Mapping[str, Any]] = (),
    representative_regeneration_enqueue_samples: Sequence[Mapping[str, Any]] = (),
    recalc_queue_jobs: Optional[Sequence[Mapping[str, Any]]] = None,
    representative_trace_limit: int = 8,
    representative_downstream_limit: int = 24,
) -> Dict[str, Any]:
    """
    Build one reproducible evidence pack from staging/runtime-shaped inputs (read-only).

    When ``governance_report`` is omitted, builds governance via
    ``build_workflow_activation_governance_report`` using the same inputs.
    When ``convergence_snapshot`` is omitted and traces are provided, builds convergence
    via ``build_runtime_convergence_snapshot``.
    """
    traces_list = [dict(t) if isinstance(t, Mapping) else {} for t in transition_traces]
    traces_list.sort(key=_sort_key_trace)

    if convergence_snapshot is not None:
        conv = dict(convergence_snapshot)
    elif traces_list:
        conv = build_runtime_convergence_snapshot(
            transition_traces=traces_list,
            generated_at_iso=generated_at,
            recalc_queue_jobs=recalc_queue_jobs,
        )
    else:
        conv = {
            "convergence_evidence_matrix": {"matrix_rows": []},
            "generated_at_iso": generated_at,
            "schema_version": "workflow_runtime_convergence_snapshot_v1",
        }

    if governance_report is not None:
        gov_full = dict(governance_report)
    else:
        gov_full = build_workflow_activation_governance_report(
            generated_at_iso=generated_at,
            convergence_snapshot=conv,
            transition_traces=traces_list,
            queue_visibility=queue_visibility,
            observability_summary=observability_summary,
            families=governance_families,
        )

    gov_summary = _governance_report_summary(gov_full)
    gate = resolve_compliance_recalc_activation_gate()
    rst_bb_gate = resolve_requirement_state_transition_core_backbone_gate()
    rst_bb_vis = build_rst_core_backbone_activation_operational_visibility(generated_at_iso=generated_at)
    activation_state = str(gate.get("activation_state") or "")
    activation_governance_version = str(gate.get("activation_governance_version") or ACTIVATION_GOVERNANCE_VERSION)

    enqueue_tuples = _enqueue_samples_to_tuples(representative_enqueue_samples)
    regen_tuples = _regeneration_enqueue_samples_to_tuples(representative_regeneration_enqueue_samples)
    validation_snapshot = build_runtime_activation_validation_snapshot(
        generated_at_iso=generated_at,
        governance_report=gov_full,
        transition_traces=traces_list,
        enqueue_samples=enqueue_tuples or None,
        regeneration_enqueue_samples=regen_tuples or None,
    )

    rep_class = classify_representative_evidence(
        transition_traces=traces_list,
        representative_enqueue_samples=list(representative_enqueue_samples),
        governance_report=gov_full,
        convergence_snapshot=conv,
    )

    consistency = derive_runtime_consistency_findings(
        validation_snapshot=validation_snapshot,
        governance_report_summary=gov_summary,
        convergence_snapshot=conv,
        representative_evidence_class=rep_class,
    )

    drift_val_summary = _drift_validation_summary(validation_snapshot)
    staging_drift = classify_staging_drift(
        drift_validation_summary=drift_val_summary,
        governance_report_summary=gov_summary,
        convergence_snapshot=conv,
    )

    readiness = derive_readiness_conclusion(
        representative_evidence_class=rep_class,
        staging_drift_classification=staging_drift,
        validation_overall=str(validation_snapshot.get("overall_activation_validation") or ""),
        governance_report_summary=gov_summary,
        convergence_snapshot=conv,
    )

    staging_drift_detail = _staging_drift_findings(
        staging_drift_classification=staging_drift,
        drift_validation_summary=drift_val_summary,
        governance_report_summary=gov_summary,
        convergence_snapshot=conv,
    )

    rt_snap = validation_snapshot.get("runtime_activation_snapshot")
    if not isinstance(rt_snap, Mapping):
        rt_snap = {}

    samples_traces = traces_list[: max(0, representative_trace_limit)]
    downstream_samples = _extract_downstream_samples(traces_list, limit=representative_downstream_limit)

    pack: Dict[str, Any] = {
        "activation_family": activation_family,
        "activation_governance_version": activation_governance_version,
        "activation_operational_findings": _activation_operational_findings(
            representative_evidence_class=rep_class,
            consistency=consistency,
            readiness=readiness,
        ),
        "activation_state": activation_state,
        "activation_validation_snapshot": validation_snapshot,
        "audit_only": True,
        "convergence_evidence_snapshot": conv,
        "convergence_visibility_summary": gov_summary.get("convergence_visibility_summary"),
        "drift_validation_summary": drift_val_summary,
        "evidence_pack_version": EVIDENCE_PACK_VERSION,
        "generated_at": generated_at,
        "governance_report_summary": gov_summary,
        "non_blocking": True,
        "observability_validation_summary": _observability_validation_summary(validation_snapshot),
        "queue_visibility_summary": _queue_visibility_summary(queue_visibility),
        "readiness_conclusion_block": readiness,
        "representative_downstream_samples": downstream_samples,
        "representative_enqueue_samples": sorted(
            [dict(sorted(dict(s).items(), key=lambda kv: str(kv[0]))) for s in representative_enqueue_samples if isinstance(s, Mapping)],
            key=lambda s: str(s.get("enqueue", {}).get("correlation_id") or ""),
        ),
        "representative_regeneration_enqueue_samples": sorted(
            [
                dict(sorted(dict(s).items(), key=lambda kv: str(kv[0])))
                for s in representative_regeneration_enqueue_samples
                if isinstance(s, Mapping)
            ],
            key=lambda s: str(s.get("enqueue", {}).get("property_id") or ""),
        ),
        "representative_evidence_classification": rep_class,
        "representative_transition_samples": samples_traces,
        "requirement_transition_core_backbone_activation_evidence": dict(
            sorted(
                {
                    "activation_operational_visibility": rst_bb_vis,
                    "rst_core_backbone_activation_gate": dict(sorted(dict(rst_bb_gate).items(), key=lambda kv: str(kv[0]))),
                    "schema_version": "rst_core_backbone_activation_evidence_v1",
                }.items(),
                key=lambda kv: str(kv[0]),
            )
        ),
        "rollback_validation_summary": build_activation_rollback_summary(),
        "runtime_activation_rollout_visibility": gov_full.get("runtime_activation_rollout_visibility"),
        "runtime_activation_snapshot": rt_snap,
        "runtime_behavior_changed": False,
        "runtime_confidence_summary": gov_summary.get("runtime_confidence_summary"),
        "runtime_consistency_findings": consistency,
        "staging_drift_classification": staging_drift,
        "staging_drift_findings": staging_drift_detail,
        "validation_summary": build_activation_validation_summary(validation_snapshot),
        "continuity_summary": build_activation_continuity_summary(validation_snapshot),
    }
    return dict(sorted(pack.items(), key=lambda kv: str(kv[0])))


def normalize_runtime_activation_evidence_pack(pack: Mapping[str, Any]) -> Dict[str, Any]:
    """Deterministic JSON round-trip for diffing / hashing (read-only)."""
    return json.loads(json.dumps(pack, sort_keys=True, default=str))


def write_runtime_activation_evidence_pack(path: Union[str, Path], pack: Mapping[str, Any]) -> str:
    """
    Filesystem export only. Writes normalized JSON. Returns absolute path string.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_runtime_activation_evidence_pack(pack)
    text = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    p.write_text(text, encoding="utf-8")
    return str(p.resolve())


def build_activation_evidence_summary(pack: Mapping[str, Any]) -> Dict[str, Any]:
    """Compact operator-facing summary (read-only)."""
    return {
        "activation_expansion_recommendation": (pack.get("readiness_conclusion_block") or {}).get("activation_expansion_recommendation"),
        "continuity_summary": pack.get("continuity_summary"),
        "evidence_pack_version": pack.get("evidence_pack_version"),
        "generated_at": pack.get("generated_at"),
        "operational_activation_posture": (pack.get("readiness_conclusion_block") or {}).get("operational_activation_posture"),
        "readiness_conclusion": (pack.get("readiness_conclusion_block") or {}).get("readiness_conclusion"),
        "representative_evidence_classification": pack.get("representative_evidence_classification"),
        "schema_version": "activation_evidence_summary_v1",
        "staging_drift_classification": pack.get("staging_drift_classification"),
        "validation_summary": pack.get("validation_summary"),
    }
