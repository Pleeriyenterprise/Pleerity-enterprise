"""
Workflow runtime convergence — audit-only evidence (Phase 1 + Phase 2).

Phase 1: propagation / reconciliation / matrix / hotspots.
Phase 2: read-only joins between transition traces and ``compliance_recalc_queue``-shaped
job dicts (caller-supplied); no DB writes, no worker changes, bounded deterministic reads.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from services.requirement_transition_observability import (
    ENQUEUE_ACCEPTED,
    ENQUEUE_DEGRADED,
    ENQUEUE_DUPLICATE_SUPPRESSED,
    ENQUEUE_FAILED,
    ENQUEUE_PARTIAL_FAILURE,
    ENQUEUE_SKIPPED,
    TRANSITION_APPLIED,
    TRANSITION_DEGRADED_DOWNSTREAM,
    TRANSITION_FAILED,
    TRANSITION_NOOP,
    TRANSITION_PARTIAL_PROPAGATION,
    TRANSITION_PENDING_RECONCILIATION,
    TRANSITION_REPLAY_DETECTED,
    TRANSITION_ORIGIN_FAMILY_BACKFILL,
    TRANSITION_ORIGIN_FAMILY_DOCUMENT_TOUCH,
    TRANSITION_ORIGIN_FAMILY_OUTCOME_ENGINE,
)

# --- Propagation completion (audit-only) ---

PROPAGATION_SETTLED = "PROPAGATION_SETTLED"
PROPAGATION_PENDING = "PROPAGATION_PENDING"
PROPAGATION_DEGRADED = "PROPAGATION_DEGRADED"
PROPAGATION_PARTIAL = "PROPAGATION_PARTIAL"
PROPAGATION_RETRYING = "PROPAGATION_RETRYING"
PROPAGATION_RECONCILIATION_REQUIRED = "PROPAGATION_RECONCILIATION_REQUIRED"
PROPAGATION_STALE_VISIBLE = "PROPAGATION_STALE_VISIBLE"
PROPAGATION_UNKNOWN = "PROPAGATION_UNKNOWN"

# --- Convergence confidence ---

HIGH_CONVERGENCE_CONFIDENCE = "HIGH_CONVERGENCE_CONFIDENCE"
MODERATE_CONVERGENCE_CONFIDENCE = "MODERATE_CONVERGENCE_CONFIDENCE"
LOW_CONVERGENCE_CONFIDENCE = "LOW_CONVERGENCE_CONFIDENCE"
UNKNOWN_CONVERGENCE_CONFIDENCE = "UNKNOWN_CONVERGENCE_CONFIDENCE"

# --- Reconciliation evidence ---

RECONCILIATION_OBSERVED = "RECONCILIATION_OBSERVED"
RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
RECONCILIATION_NOT_VISIBLE = "RECONCILIATION_NOT_VISIBLE"
RECONCILIATION_RECOVERED = "RECONCILIATION_RECOVERED"
RECONCILIATION_DEGRADED = "RECONCILIATION_DEGRADED"
RECONCILIATION_UNKNOWN = "RECONCILIATION_UNKNOWN"


def _downstream_rows(trace: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    rows = trace.get("downstream_trigger_targets")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, Mapping)]
    return []


def _worst_enqueue_outcome(rows: Sequence[Mapping[str, Any]]) -> Optional[str]:
    priority = (
        ENQUEUE_FAILED,
        ENQUEUE_PARTIAL_FAILURE,
        ENQUEUE_DEGRADED,
        ENQUEUE_DUPLICATE_SUPPRESSED,
        ENQUEUE_SKIPPED,
        ENQUEUE_ACCEPTED,
    )
    worst: Optional[str] = None
    for r in rows:
        oc = str(r.get("enqueue_outcome") or "")
        if not oc:
            continue
        if worst is None:
            worst = oc
            continue
        try:
            if priority.index(oc) < priority.index(worst):
                worst = oc
        except ValueError:
            worst = oc
    return worst


def classify_propagation_completion_from_transition_trace(trace: Mapping[str, Any]) -> str:
    """
    Map a requirement transition trace (see ``build_requirement_transition_trace``)
    to a propagation-completion label. Audit-only.
    """
    tout = str(trace.get("transition_outcome") or "").strip()
    if not tout:
        return PROPAGATION_UNKNOWN
    if tout == TRANSITION_FAILED:
        return PROPAGATION_DEGRADED
    if tout == TRANSITION_DEGRADED_DOWNSTREAM:
        return PROPAGATION_DEGRADED
    if tout == TRANSITION_PENDING_RECONCILIATION:
        return PROPAGATION_RECONCILIATION_REQUIRED
    if tout == TRANSITION_PARTIAL_PROPAGATION:
        return PROPAGATION_PARTIAL

    rows = _downstream_rows(trace)
    worst = _worst_enqueue_outcome(rows)
    if worst in (ENQUEUE_FAILED, ENQUEUE_PARTIAL_FAILURE, ENQUEUE_DEGRADED):
        return PROPAGATION_PARTIAL if tout == TRANSITION_APPLIED else PROPAGATION_DEGRADED

    if tout == TRANSITION_REPLAY_DETECTED:
        if trace.get("stale_transition_replayed"):
            return PROPAGATION_STALE_VISIBLE
        return PROPAGATION_RETRYING

    if tout == TRANSITION_NOOP:
        if trace.get("stale_transition_replayed") or trace.get("stale_document_transition_possible"):
            return PROPAGATION_STALE_VISIBLE
        if trace.get("replay_possible") and rows:
            return PROPAGATION_RETRYING
        return PROPAGATION_SETTLED

    if tout == TRANSITION_APPLIED:
        if worst == ENQUEUE_SKIPPED and any(bool(r.get("enqueue_attempted")) for r in rows):
            return PROPAGATION_PARTIAL
        return PROPAGATION_SETTLED

    return PROPAGATION_UNKNOWN


def classify_propagation_completion_from_recalc_queue_job(job: Mapping[str, Any]) -> str:
    """Audit-only label from a persisted ``compliance_recalc_queue`` job shape."""
    status = str(job.get("status") or "").strip().upper()
    if status == "DONE":
        return PROPAGATION_SETTLED
    if status == "DEAD":
        return PROPAGATION_DEGRADED
    if status == "FAILED":
        return PROPAGATION_RETRYING
    if status in ("PENDING", "RUNNING"):
        return PROPAGATION_PENDING
    return PROPAGATION_UNKNOWN


def classify_reconciliation_evidence_from_transition_trace(trace: Mapping[str, Any]) -> str:
    """Reconciliation posture inferred from gap sync + transition outcome (audit-only)."""
    tout = str(trace.get("transition_outcome") or "").strip()
    partial = bool(trace.get("partial_downstream_failure"))
    targets = trace.get("downstream_propagation") or []
    gap_sync_row = next(
        (t for t in targets if str((t or {}).get("downstream_target") or "").find("compliance_gap_sync") >= 0),
        None,
    )
    gap_degraded = bool((gap_sync_row or {}).get("propagation_degraded_possible"))

    if tout == TRANSITION_PENDING_RECONCILIATION or (partial and gap_degraded):
        return RECONCILIATION_PENDING
    if tout == TRANSITION_DEGRADED_DOWNSTREAM:
        return RECONCILIATION_DEGRADED
    if tout in (TRANSITION_APPLIED, TRANSITION_NOOP) and not partial:
        if gap_sync_row and not gap_degraded:
            return RECONCILIATION_OBSERVED
        if not targets:
            return RECONCILIATION_NOT_VISIBLE
        return RECONCILIATION_OBSERVED
    if tout == TRANSITION_PARTIAL_PROPAGATION:
        return RECONCILIATION_PENDING
    if trace.get("replay_possible") and tout == TRANSITION_APPLIED:
        return RECONCILIATION_RECOVERED
    return RECONCILIATION_UNKNOWN


def classify_convergence_confidence(
    propagation_completion: str,
    reconciliation_evidence: str,
) -> str:
    """Roll up confidence from propagation + reconciliation labels (audit-only)."""
    if propagation_completion == PROPAGATION_UNKNOWN or reconciliation_evidence == RECONCILIATION_UNKNOWN:
        return UNKNOWN_CONVERGENCE_CONFIDENCE
    if propagation_completion in (PROPAGATION_DEGRADED, PROPAGATION_PARTIAL) or reconciliation_evidence in (
        RECONCILIATION_DEGRADED,
        RECONCILIATION_PENDING,
    ):
        return LOW_CONVERGENCE_CONFIDENCE
    if propagation_completion in (
        PROPAGATION_PENDING,
        PROPAGATION_RETRYING,
        PROPAGATION_RECONCILIATION_REQUIRED,
        PROPAGATION_STALE_VISIBLE,
    ):
        return MODERATE_CONVERGENCE_CONFIDENCE
    if propagation_completion == PROPAGATION_SETTLED and reconciliation_evidence in (
        RECONCILIATION_OBSERVED,
        RECONCILIATION_NOT_VISIBLE,
        RECONCILIATION_RECOVERED,
    ):
        return HIGH_CONVERGENCE_CONFIDENCE
    return MODERATE_CONVERGENCE_CONFIDENCE


def workflow_family_from_transition_origin(origin: Optional[str]) -> str:
    o = str(origin or "").strip()
    if o.startswith(f"{TRANSITION_ORIGIN_FAMILY_OUTCOME_ENGINE}:"):
        return "automated_outcome_authority"
    if o.startswith(f"{TRANSITION_ORIGIN_FAMILY_DOCUMENT_TOUCH}:"):
        return "generic_document_touch_authority"
    if o.startswith(f"{TRANSITION_ORIGIN_FAMILY_BACKFILL}:"):
        return "backfill_authority_script"
    if "routes.evidence_review" in o:
        return "evidence_review"
    if "routes.admin" in o:
        return "admin_mutation"
    if "routes.documents" in o or o.startswith("routes.documents"):
        return "document_workflow"
    if "routes.properties" in o or "patch_requirement" in o:
        return "property_requirement_client"
    if "api_compliance_workflow" in o or "client_compliance_evidence" in o:
        return "client_compliance_workflow"
    if o.startswith("unspecified") or not o:
        return "unspecified_or_legacy"
    return "other"


def propagation_chain_label(trace: Mapping[str, Any]) -> str:
    """Stable chain descriptor from trace (audit-only)."""
    parts = ["requirement_evidence_authority.sync"]
    for t in trace.get("downstream_propagation") or []:
        if isinstance(t, Mapping):
            tgt = str(t.get("downstream_target") or "").strip()
            if tgt:
                parts.append(tgt.split(".")[-1][:48])
    rows = _downstream_rows(trace)
    for r in rows:
        dt = str(r.get("downstream_target") or "").strip()
        if dt and dt not in parts:
            parts.append(dt.split(".")[-1][:48])
    return "->".join(parts[:12])


def stale_read_dependency_hint(trace: Mapping[str, Any]) -> bool:
    """Heuristic: trust surfaces that may read before async recalc settles."""
    if bool(trace.get("stale_document_transition_possible")):
        return True
    if bool(trace.get("stale_transition_replayed")):
        return True
    o = str(trace.get("transition_origin") or "")
    if "DOCUMENT_TOUCH" in o and bool(trace.get("replay_possible")):
        return True
    return False


def degraded_path_visibility_hint(trace: Mapping[str, Any]) -> bool:
    rows = _downstream_rows(trace)
    if any(bool(r.get("degraded_possible")) for r in rows):
        return True
    return str(trace.get("transition_outcome") or "") in (
        TRANSITION_DEGRADED_DOWNSTREAM,
        TRANSITION_PARTIAL_PROPAGATION,
    )


def retry_evidence_hint(trace: Mapping[str, Any]) -> str:
    if trace.get("replay_chain_detected") or trace.get("transition_outcome") == TRANSITION_REPLAY_DETECTED:
        return "replay_or_reentry"
    rows = _downstream_rows(trace)
    if any(str(r.get("enqueue_outcome") or "") == ENQUEUE_DUPLICATE_SUPPRESSED for r in rows):
        return "enqueue_duplicate_suppressed"
    if any(str(r.get("enqueue_outcome") or "") == ENQUEUE_FAILED for r in rows):
        return "enqueue_failed"
    return "none_observed"


def trace_to_convergence_matrix_row(trace: Mapping[str, Any]) -> Dict[str, Any]:
    prop = classify_propagation_completion_from_transition_trace(trace)
    recon = classify_reconciliation_evidence_from_transition_trace(trace)
    conf = classify_convergence_confidence(prop, recon)
    origin = str(trace.get("transition_origin") or "")
    wf = workflow_family_from_transition_origin(origin)
    chain = propagation_chain_label(trace)
    targets = sorted(
        {str(r.get("downstream_target") or "") for r in _downstream_rows(trace) if r.get("downstream_target")}
    )
    maturity = (
        "HIGH_MATURITY_VISIBILITY"
        if conf == HIGH_CONVERGENCE_CONFIDENCE
        else (
            "MODERATE_MATURITY_VISIBILITY"
            if conf == MODERATE_CONVERGENCE_CONFIDENCE
            else "LOW_MATURITY_VISIBILITY" if conf == LOW_CONVERGENCE_CONFIDENCE else "UNKNOWN_MATURITY_VISIBILITY"
        )
    )
    return {
        "workflow_family": wf,
        "propagation_chain": chain,
        "downstream_targets": targets,
        "stale_read_dependency": stale_read_dependency_hint(trace),
        "retry_evidence": retry_evidence_hint(trace),
        "degraded_visibility": degraded_path_visibility_hint(trace),
        "reconciliation_visibility": recon,
        "settlement_evidence": prop,
        "convergence_confidence": conf,
        "operational_maturity": maturity,
        "requirement_id": str(trace.get("requirement_id") or ""),
        "correlation_id": str(trace.get("correlation_id") or ""),
    }


def _matrix_sort_key(row: Mapping[str, Any]) -> Tuple[Any, ...]:
    return (
        str(row.get("workflow_family") or ""),
        str(row.get("propagation_chain") or ""),
        ",".join(row.get("downstream_targets") or []),
        str(row.get("requirement_id") or ""),
        str(row.get("correlation_id") or ""),
    )


def build_convergence_evidence_matrix(*, matrix_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic matrix across supplied rows (already normalized dicts).
    Callers may build rows from ``trace_to_convergence_matrix_row`` or jobs.
    """
    rows = [dict(r) for r in matrix_rows]
    rows.sort(key=_matrix_sort_key)

    by_family: Dict[str, List[str]] = {}
    for r in rows:
        fam = str(r.get("workflow_family") or "unknown")
        by_family.setdefault(fam, []).append(str(r.get("settlement_evidence") or ""))

    def _families_all_settled() -> List[str]:
        out: List[str] = []
        for fam, labels in sorted(by_family.items()):
            if labels and all(l == PROPAGATION_SETTLED for l in labels):
                out.append(fam)
        return out

    def _families_weakest() -> List[str]:
        weak: List[str] = []
        bad = {
            PROPAGATION_UNKNOWN,
            PROPAGATION_DEGRADED,
            PROPAGATION_PARTIAL,
            PROPAGATION_RECONCILIATION_REQUIRED,
        }
        for fam, labels in sorted(by_family.items()):
            if any(l in bad for l in labels):
                weak.append(fam)
        return weak

    boundaries: List[str] = []
    for r in rows:
        if r.get("stale_read_dependency") and r.get("settlement_evidence") not in (
            PROPAGATION_SETTLED,
            PROPAGATION_UNKNOWN,
        ):
            boundaries.append(
                f"stale_read_dependency_with_{r.get('settlement_evidence')}:{r.get('workflow_family')}"
            )
        if r.get("retry_evidence") == "enqueue_failed":
            boundaries.append(f"enqueue_failure_without_local_retry:{r.get('workflow_family')}")
        if r.get("reconciliation_visibility") == RECONCILIATION_NOT_VISIBLE and r.get("degraded_visibility"):
            boundaries.append(f"degraded_without_reconciliation_signal:{r.get('workflow_family')}")

    return {
        "schema_version": "workflow_runtime_convergence_evidence_matrix_v1",
        "matrix_rows": rows,
        "strongest_settlement_families": _families_all_settled(),
        "weakest_convergence_families": _families_weakest(),
        "opaque_eventual_consistency_boundaries": sorted(set(boundaries)),
        "non_blocking": True,
        "audit_only": True,
    }


def detect_runtime_convergence_hotspots(matrix_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Classify weak spots from matrix rows (audit-only; no remediation)."""
    rows = list(matrix_rows)
    settlement_blind = [r for r in rows if r.get("settlement_evidence") == PROPAGATION_UNKNOWN]
    recon_gap = [r for r in rows if r.get("reconciliation_visibility") == RECONCILIATION_NOT_VISIBLE]
    stale_risk = [r for r in rows if r.get("stale_read_dependency")]
    degraded_risk = [r for r in rows if r.get("degraded_visibility")]
    replay_instability = [r for r in rows if r.get("retry_evidence") == "replay_or_reentry"]
    partial_persist = [r for r in rows if r.get("settlement_evidence") == PROPAGATION_PARTIAL]
    regen_ambiguous = [
        r
        for r in rows
        if any("risk_signal_regen" in str(t) for t in (r.get("downstream_targets") or []))
        and r.get("convergence_confidence") != HIGH_CONVERGENCE_CONFIDENCE
    ]
    trust_div = [r for r in rows if r.get("stale_read_dependency") and r.get("settlement_evidence") != PROPAGATION_SETTLED]

    def _keys(rs: List[Mapping[str, Any]]) -> List[str]:
        return sorted({f"{r.get('workflow_family')}:{r.get('requirement_id') or r.get('correlation_id')}" for r in rs})

    return {
        "schema_version": "workflow_runtime_convergence_hotspots_v1",
        "settlement_blind_spots": _keys(settlement_blind),
        "reconciliation_gaps": _keys(recon_gap),
        "stale_state_persistence_risk": _keys(stale_risk),
        "degraded_path_persistence_risk": _keys(degraded_risk),
        "replay_reentry_instability": _keys(replay_instability),
        "partial_propagation_persistence": _keys(partial_persist),
        "regeneration_convergence_ambiguity": _keys(regen_ambiguous),
        "trust_surface_divergence_risk": _keys(trust_div),
        "non_blocking": True,
        "audit_only": True,
    }


def build_propagation_completion_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    hist: Dict[str, int] = {}
    for t in traces:
        lab = classify_propagation_completion_from_transition_trace(t)
        hist[lab] = hist.get(lab, 0) + 1
    return {
        "schema_version": "propagation_completion_summary_v1",
        "by_propagation_completion": dict(sorted(hist.items())),
        "settled_count": hist.get(PROPAGATION_SETTLED, 0),
        "degraded_or_partial_count": hist.get(PROPAGATION_DEGRADED, 0) + hist.get(PROPAGATION_PARTIAL, 0),
        "pending_or_retrying_count": hist.get(PROPAGATION_PENDING, 0) + hist.get(PROPAGATION_RETRYING, 0),
        "non_blocking": True,
    }


def build_reconciliation_visibility_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    hist: Dict[str, int] = {}
    for t in traces:
        lab = classify_reconciliation_evidence_from_transition_trace(t)
        hist[lab] = hist.get(lab, 0) + 1
    return {
        "schema_version": "reconciliation_visibility_summary_v1",
        "by_reconciliation_evidence": dict(sorted(hist.items())),
        "pending_or_degraded_count": hist.get(RECONCILIATION_PENDING, 0) + hist.get(RECONCILIATION_DEGRADED, 0),
        "not_visible_count": hist.get(RECONCILIATION_NOT_VISIBLE, 0),
        "non_blocking": True,
    }


def build_stale_state_recovery_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    stale_marked = sum(
        1
        for t in traces
        if t.get("stale_document_transition_possible") or t.get("stale_transition_replayed")
    )
    recovery_hint = sum(
        1 for t in traces if t.get("replay_possible") and classify_propagation_completion_from_transition_trace(t)
        == PROPAGATION_SETTLED
    )
    return {
        "schema_version": "stale_state_recovery_summary_v1",
        "stale_surface_trace_count": stale_marked,
        "replay_settled_trace_count": recovery_hint,
        "stale_visible_propagation_count": sum(
            1
            for t in traces
            if classify_propagation_completion_from_transition_trace(t) == PROPAGATION_STALE_VISIBLE
        ),
        "non_blocking": True,
    }


def build_runtime_convergence_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
    recalc_queue_jobs: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Aggregate propagation, reconciliation, stale recovery, matrix, and hotspots.
    ``recalc_queue_jobs`` optional: persisted job docs for enqueue/settlement audit join.
    """
    matrix_rows: List[Dict[str, Any]] = [trace_to_convergence_matrix_row(t) for t in transition_traces]
    if recalc_queue_jobs:
        for job in recalc_queue_jobs:
            prop = classify_propagation_completion_from_recalc_queue_job(job)
            recon_q = RECONCILIATION_NOT_VISIBLE
            conf_q = classify_convergence_confidence(prop, recon_q)
            mat_q = (
                "HIGH_MATURITY_VISIBILITY"
                if conf_q == HIGH_CONVERGENCE_CONFIDENCE
                else (
                    "MODERATE_MATURITY_VISIBILITY"
                    if conf_q == MODERATE_CONVERGENCE_CONFIDENCE
                    else "LOW_MATURITY_VISIBILITY" if conf_q == LOW_CONVERGENCE_CONFIDENCE else "UNKNOWN_MATURITY_VISIBILITY"
                )
            )
            matrix_rows.append(
                {
                    "workflow_family": "compliance_recalc_queue_job",
                    "propagation_chain": "enqueue->worker->recalculate_and_persist",
                    "downstream_targets": ["compliance_recalc_queue"],
                    "stale_read_dependency": True,
                    "retry_evidence": "worker_retry_backoff" if prop == PROPAGATION_RETRYING else "none_observed",
                    "degraded_visibility": prop == PROPAGATION_DEGRADED,
                    "reconciliation_visibility": recon_q,
                    "settlement_evidence": prop,
                    "convergence_confidence": conf_q,
                    "operational_maturity": mat_q,
                    "requirement_id": "",
                    "correlation_id": str(job.get("correlation_id") or ""),
                }
            )

    matrix = build_convergence_evidence_matrix(matrix_rows=matrix_rows)
    return {
        "schema_version": "workflow_runtime_convergence_snapshot_v1",
        "generated_at_iso": generated_at_iso,
        "propagation_completion": build_propagation_completion_summary(transition_traces),
        "reconciliation_visibility": build_reconciliation_visibility_summary(transition_traces),
        "stale_state_recovery": build_stale_state_recovery_summary(transition_traces),
        "convergence_evidence_matrix": matrix,
        "runtime_convergence_hotspots": detect_runtime_convergence_hotspots(matrix["matrix_rows"]),
        "non_blocking": True,
        "audit_only": True,
    }
# --- Phase 2: trace ↔ queue join (audit-only) ---

JOIN_CONFIRMED = "JOIN_CONFIRMED"
JOIN_PROBABLE = "JOIN_PROBABLE"
JOIN_WEAK = "JOIN_WEAK"
JOIN_NOT_VISIBLE = "JOIN_NOT_VISIBLE"
JOIN_AMBIGUOUS = "JOIN_AMBIGUOUS"

SETTLEMENT_CONFIRMED = "SETTLEMENT_CONFIRMED"
SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
SETTLEMENT_DEGRADED = "SETTLEMENT_DEGRADED"
SETTLEMENT_UNKNOWN = "SETTLEMENT_UNKNOWN"
SETTLEMENT_RECONCILIATION_REQUIRED = "SETTLEMENT_RECONCILIATION_REQUIRED"

RECONCILIATION_CHAIN_VISIBLE = "RECONCILIATION_CHAIN_VISIBLE"
RECONCILIATION_CHAIN_PARTIAL = "RECONCILIATION_CHAIN_PARTIAL"
RECONCILIATION_CHAIN_NOT_VISIBLE = "RECONCILIATION_CHAIN_NOT_VISIBLE"


def _job_sort_key(job: Mapping[str, Any]) -> Tuple[Any, ...]:
    return (
        str(job.get("property_id") or ""),
        str(job.get("client_id") or ""),
        str(job.get("correlation_id") or ""),
        str(job.get("status") or ""),
        str(job.get("_id") or ""),
    )


def deterministic_recalc_job_sort_key(job: Mapping[str, Any]) -> Tuple[Any, ...]:
    """Stable sort key for ``compliance_recalc_queue``-shaped dicts (Phase 2/3)."""
    return _job_sort_key(job)


def _correlation_hints_for_trace(trace: Mapping[str, Any]) -> List[str]:
    hints: List[str] = []
    tc = str(trace.get("correlation_id") or "").strip()
    if tc:
        hints.append(tc)
    for r in _downstream_rows(trace):
        dc = str(r.get("downstream_correlation_id") or "").strip()
        if dc and dc not in hints:
            hints.append(dc)
    return hints


def _correlation_pair_strength(trace_c: str, job_c: str) -> Optional[int]:
    """Lower int is stronger; None = no correlation link."""
    if not trace_c or not job_c:
        return None
    if trace_c == job_c:
        return 0
    if trace_c.startswith(job_c + ":") or trace_c.startswith(job_c + "|"):
        return 1
    if job_c.startswith(trace_c + ":") or job_c.startswith(trace_c + "|"):
        return 1
    if job_c in trace_c or trace_c in job_c:
        return 2
    return None


def _match_jobs_for_trace(
    trace: Mapping[str, Any],
    jobs_sorted: Sequence[Mapping[str, Any]],
) -> Tuple[List[Mapping[str, Any]], str]:
    """
    Best-effort match of pre-sorted job dicts to a trace.
    Uses property_id + client_id scoping when present, then correlation hints.
    """
    tp = str(trace.get("property_id") or "").strip()
    tcl = str(trace.get("client_id") or "").strip()
    hints = _correlation_hints_for_trace(trace)

    scoped: List[Mapping[str, Any]] = []
    for j in jobs_sorted:
        jp = str(j.get("property_id") or "").strip()
        jcl = str(j.get("client_id") or "").strip()
        if tp and jp and jp != tp:
            continue
        if tcl and jcl and jcl != tcl:
            continue
        scoped.append(j)

    if not scoped:
        return [], JOIN_NOT_VISIBLE

    candidates: List[Tuple[int, Mapping[str, Any]]] = []
    for j in scoped:
        jc = str(j.get("correlation_id") or "").strip()
        best_strength: Optional[int] = None
        for h in hints:
            st = _correlation_pair_strength(h, jc)
            if st is None:
                continue
            if best_strength is None or st < best_strength:
                best_strength = st
        if best_strength is not None:
            candidates.append((best_strength, j))

    if not candidates:
        if tp or tcl:
            return [], JOIN_NOT_VISIBLE
        return [], JOIN_NOT_VISIBLE

    min_strength = min(c[0] for c in candidates)
    matched = [j for s, j in candidates if s == min_strength]
    # De-duplicate by _id / id string
    seen: set[str] = set()
    deduped: List[Mapping[str, Any]] = []
    for j in matched:
        jid = str(j.get("_id") or j.get("job_id") or id(j))
        if jid in seen:
            continue
        seen.add(jid)
        deduped.append(j)

    if len(deduped) > 1 and min_strength == 0:
        return deduped, JOIN_AMBIGUOUS
    if len(deduped) > 1:
        return deduped, JOIN_AMBIGUOUS
    if not deduped:
        return [], JOIN_NOT_VISIBLE
    if min_strength == 0:
        return deduped, JOIN_CONFIRMED
    if min_strength == 1:
        return deduped, JOIN_PROBABLE
    return deduped, JOIN_WEAK


def classify_settlement_linkage(
    *,
    trace: Mapping[str, Any],
    matched_jobs: Sequence[Mapping[str, Any]],
    join_classification: str,
) -> str:
    """Link authority/trace settlement to queue lifecycle (audit-only)."""
    if join_classification in (JOIN_NOT_VISIBLE,):
        if any(
            str(r.get("enqueue_outcome") or "") == ENQUEUE_ACCEPTED for r in _downstream_rows(trace)
        ):
            return SETTLEMENT_PENDING
        return SETTLEMENT_UNKNOWN

    prop_t = classify_propagation_completion_from_transition_trace(trace)
    tout = str(trace.get("transition_outcome") or "").strip()
    if tout == TRANSITION_PENDING_RECONCILIATION or prop_t == PROPAGATION_RECONCILIATION_REQUIRED:
        return SETTLEMENT_RECONCILIATION_REQUIRED

    statuses = [str(j.get("status") or "").upper() for j in matched_jobs]
    if any(s == "DEAD" for s in statuses):
        return SETTLEMENT_DEGRADED
    if any(s in ("PENDING", "RUNNING", "FAILED") for s in statuses):
        return SETTLEMENT_PENDING
    if all(s == "DONE" for s in statuses) and prop_t == PROPAGATION_SETTLED:
        return SETTLEMENT_CONFIRMED
    if all(s == "DONE" for s in statuses):
        if prop_t in (PROPAGATION_SETTLED, PROPAGATION_STALE_VISIBLE):
            return SETTLEMENT_CONFIRMED
        return SETTLEMENT_UNKNOWN
    return SETTLEMENT_UNKNOWN


def classify_reconciliation_chain(
    trace: Mapping[str, Any],
    matched_jobs: Sequence[Mapping[str, Any]],
) -> str:
    markers: List[str] = []
    for j in matched_jobs:
        sig = j.get("recalc_execution_signals") or {}
        if isinstance(sig, Mapping):
            if sig.get("reconciliation_recommended"):
                markers.append("job_reconciliation_recommended")
            if sig.get("retry_pending"):
                markers.append("job_retry_pending")
            if sig.get("degraded_execution"):
                markers.append("job_degraded_execution")
        if str(j.get("status") or "").upper() == "DEAD":
            markers.append("job_dead")
    for r in _downstream_rows(trace):
        oc = str(r.get("enqueue_outcome") or "")
        if oc == ENQUEUE_DUPLICATE_SUPPRESSED:
            markers.append("enqueue_duplicate_suppressed")
        if oc in (ENQUEUE_FAILED, ENQUEUE_PARTIAL_FAILURE, ENQUEUE_DEGRADED):
            markers.append("enqueue_degraded_or_failed")
        tgt = str(r.get("downstream_target") or "")
        if "risk_signal_regen" in tgt:
            markers.append("regeneration_delegate")
        if r.get("replay_chain_detected"):
            markers.append("replay_chain")

    if len(set(markers)) >= 2:
        return RECONCILIATION_CHAIN_VISIBLE
    if markers:
        return RECONCILIATION_CHAIN_PARTIAL
    return RECONCILIATION_CHAIN_NOT_VISIBLE


def _stale_convergence_flags(
    trace: Mapping[str, Any],
    matched_jobs: Sequence[Mapping[str, Any]],
    join_classification: str,
) -> Dict[str, bool]:
    statuses = [str(j.get("status") or "").upper() for j in matched_jobs]
    pending_worker = any(s in ("PENDING", "RUNNING") for s in statuses)
    dead = any(s == "DEAD" for s in statuses)
    failed_retry = any(s == "FAILED" for s in statuses)
    recon_trace = classify_reconciliation_evidence_from_transition_trace(trace)
    degraded_unresolved = degraded_path_visibility_hint(trace) and recon_trace in (
        RECONCILIATION_PENDING,
        RECONCILIATION_DEGRADED,
    )
    no_join = join_classification == JOIN_NOT_VISIBLE

    return {
        "stale_read_risk_visible": bool(
            pending_worker or stale_read_dependency_hint(trace) or (no_join and pending_worker)
        ),
        "settlement_not_yet_observed": bool(matched_jobs and (pending_worker or failed_retry)),
        "queue_lifecycle_visible": bool(matched_jobs),
        "downstream_reconciliation_visible": recon_trace
        not in (RECONCILIATION_NOT_VISIBLE, RECONCILIATION_UNKNOWN),
        "convergence_window_open": bool(pending_worker or failed_retry or dead),
        "dead_job_present": dead,
        "degraded_propagation_unresolved": degraded_unresolved,
        "no_joined_recalc_lifecycle_found": no_join,
    }


def join_transition_traces_with_recalc_jobs(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    recalc_queue_jobs: Sequence[Mapping[str, Any]],
    max_jobs_scanned: int = 10_000,
) -> List[Dict[str, Any]]:
    """
    Join each trace to matching job dicts (read-only, in-memory).

    ``max_jobs_scanned`` bounds work per call; jobs are sorted then truncated deterministically.
    """
    jobs_list = list(recalc_queue_jobs)
    jobs_list.sort(key=_job_sort_key)
    if max_jobs_scanned >= 0:
        jobs_list = jobs_list[: max_jobs_scanned]

    out: List[Dict[str, Any]] = []
    for idx, trace in enumerate(transition_traces):
        matched, join_kind = _match_jobs_for_trace(trace, jobs_list)
        settlement = classify_settlement_linkage(
            trace=trace, matched_jobs=matched, join_classification=join_kind
        )
        recon_chain = classify_reconciliation_chain(trace, matched)
        stale_flags = _stale_convergence_flags(trace, matched, join_kind)
        row: Dict[str, Any] = {
            "trace_index": idx,
            "workflow_family": workflow_family_from_transition_origin(str(trace.get("transition_origin") or "")),
            "trace_correlation_id": str(trace.get("correlation_id") or ""),
            "property_id": str(trace.get("property_id") or ""),
            "client_id": str(trace.get("client_id") or ""),
            "requirement_id": str(trace.get("requirement_id") or ""),
            "join_classification": join_kind,
            "settlement_linkage": settlement,
            "matched_job_correlation_ids": sorted({str(j.get("correlation_id") or "") for j in matched if j.get("correlation_id")}),
            "matched_job_statuses": sorted({str(j.get("status") or "") for j in matched}),
            "reconciliation_chain": recon_chain,
            "propagation_completion_trace": classify_propagation_completion_from_transition_trace(trace),
            **stale_flags,
        }
        out.append(row)
    out.sort(key=lambda r: (r["trace_index"],))
    return out


def build_recalc_convergence_summary(
    joined_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    by_join: Dict[str, int] = {}
    by_settlement: Dict[str, int] = {}
    by_chain: Dict[str, int] = {}
    for r in joined_rows:
        by_join[str(r.get("join_classification") or "")] = by_join.get(str(r.get("join_classification") or ""), 0) + 1
        by_settlement[str(r.get("settlement_linkage") or "")] = (
            by_settlement.get(str(r.get("settlement_linkage") or ""), 0) + 1
        )
        by_chain[str(r.get("reconciliation_chain") or "")] = by_chain.get(str(r.get("reconciliation_chain") or ""), 0) + 1
    return {
        "schema_version": "recalc_convergence_summary_v1",
        "by_join_classification": dict(sorted(by_join.items())),
        "by_settlement_linkage": dict(sorted(by_settlement.items())),
        "by_reconciliation_chain": dict(sorted(by_chain.items())),
        "non_blocking": True,
    }


def build_queue_settlement_visibility_summary(
    *,
    recalc_queue_jobs: Sequence[Mapping[str, Any]],
    joined_rows: Sequence[Mapping[str, Any]],
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    max_jobs_scanned: int = 10_000,
) -> Dict[str, Any]:
    jobs_list = list(recalc_queue_jobs)
    jobs_list.sort(key=_job_sort_key)
    if max_jobs_scanned >= 0:
        jobs_list = jobs_list[: max_jobs_scanned]

    hint_set = set()
    for t in joined_rows:
        for cid in t.get("matched_job_correlation_ids") or []:
            if cid:
                hint_set.add(cid)
    all_job_corr = {str(j.get("correlation_id") or "") for j in jobs_list if j.get("correlation_id")}
    jobs_without_joined_trace = sorted(c for c in all_job_corr if c and c not in hint_set)

    trace_enqueue_accepted_no_queue = 0
    if transition_traces is not None:
        for r in joined_rows:
            if r.get("join_classification") != JOIN_NOT_VISIBLE:
                continue
            _ti = r.get("trace_index")
            idx = int(_ti) if _ti is not None else -1
            if 0 <= idx < len(transition_traces):
                tr = transition_traces[idx]
                if any(
                    str(x.get("enqueue_outcome") or "") == ENQUEUE_ACCEPTED for x in _downstream_rows(tr)
                ):
                    trace_enqueue_accepted_no_queue += 1

    status_hist: Dict[str, int] = {}
    for j in jobs_list:
        st = str(j.get("status") or "")
        status_hist[st] = status_hist.get(st, 0) + 1

    return {
        "schema_version": "queue_settlement_visibility_summary_v1",
        "queue_job_count_bounded": len(jobs_list),
        "queue_status_histogram": dict(sorted(status_hist.items())),
        "queue_correlation_ids_without_trace_join": jobs_without_joined_trace,
        "joined_trace_rows": len(joined_rows),
        "trace_enqueue_accepted_without_queue_join_count": trace_enqueue_accepted_no_queue,
        "non_blocking": True,
    }


def build_convergence_join_operational_summary(
    *,
    joined_rows: Sequence[Mapping[str, Any]],
    transition_traces: Sequence[Mapping[str, Any]],
    recalc_queue_jobs: Sequence[Mapping[str, Any]],
    max_jobs_scanned: int = 10_000,
) -> Dict[str, Any]:
    """Deterministic rollups for ops dashboards (audit-only)."""
    jobs_list = list(recalc_queue_jobs)
    jobs_list.sort(key=_job_sort_key)
    if max_jobs_scanned >= 0:
        jobs_list = jobs_list[: max_jobs_scanned]

    by_wf: Dict[str, List[str]] = {}
    for r in joined_rows:
        wf = str(r.get("workflow_family") or "unknown")
        by_wf.setdefault(wf, []).append(str(r.get("join_classification") or ""))

    strongest = sorted(
        wf
        for wf in by_wf
        if by_wf[wf]
        and all(
            str(r.get("join_classification") or "") in (JOIN_CONFIRMED, JOIN_PROBABLE)
            for r in joined_rows
            if str(r.get("workflow_family") or "unknown") == wf
        )
        and any(
            str(r.get("join_classification") or "") == JOIN_CONFIRMED
            for r in joined_rows
            if str(r.get("workflow_family") or "unknown") == wf
        )
    )
    weakest = sorted(
        wf
        for wf in by_wf
        if by_wf[wf]
        and any(
            str(r.get("join_classification") or "") in (JOIN_NOT_VISIBLE, JOIN_AMBIGUOUS, JOIN_WEAK)
            or str(r.get("settlement_linkage") or "") == SETTLEMENT_DEGRADED
            for r in joined_rows
            if str(r.get("workflow_family") or "unknown") == wf
        )
    )

    stale_surface_candidates = sorted(
        {
            f"{r.get('workflow_family')}:{r.get('requirement_id') or r.get('trace_correlation_id')}"
            for r in joined_rows
            if r.get("stale_read_risk_visible")
        }
    )
    degraded_candidates = sorted(
        {
            f"{r.get('workflow_family')}:{r.get('requirement_id') or r.get('trace_correlation_id')}"
            for r in joined_rows
            if r.get("settlement_linkage") == SETTLEMENT_DEGRADED or r.get("dead_job_present")
        }
    )
    recon_gaps = sorted(
        {
            f"{r.get('workflow_family')}:{r.get('requirement_id') or r.get('trace_correlation_id')}"
            for r in joined_rows
            if r.get("reconciliation_chain") == RECONCILIATION_CHAIN_NOT_VISIBLE
            and degraded_path_visibility_hint(transition_traces[int(r["trace_index"])])
        }
    )

    trace_corr = set()
    for t in transition_traces:
        for h in _correlation_hints_for_trace(t):
            if h:
                trace_corr.add(h)
    job_corr = {str(j.get("correlation_id") or "") for j in jobs_list if j.get("correlation_id")}
    queue_without_trace = sorted(c for c in job_corr if c and c not in trace_corr)

    trace_without_queue: List[str] = []
    for r in joined_rows:
        if r.get("join_classification") == JOIN_NOT_VISIBLE:
            trace_without_queue.append(
                f"{r.get('workflow_family')}:{r.get('trace_correlation_id') or r.get('requirement_id')}"
            )
    trace_without_queue = sorted(set(trace_without_queue))

    return {
        "schema_version": "convergence_join_operational_summary_v1",
        "strongest_joined_workflows": strongest,
        "weakest_joined_workflows": weakest,
        "stale_surface_candidates": stale_surface_candidates,
        "queue_without_trace_visibility": queue_without_trace,
        "trace_without_queue_visibility": trace_without_queue,
        "degraded_settlement_candidates": degraded_candidates,
        "reconciliation_visibility_gaps": recon_gaps,
        "non_blocking": True,
    }


def build_recalc_joined_convergence_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    recalc_queue_jobs: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
    max_jobs_scanned: int = 10_000,
) -> Dict[str, Any]:
    """
    Full read-only snapshot: Phase-1 runtime snapshot plus trace↔queue joins and summaries.

    Caller supplies already-read job documents; this function performs no I/O.
    """
    joined = join_transition_traces_with_recalc_jobs(
        transition_traces=transition_traces,
        recalc_queue_jobs=recalc_queue_jobs,
        max_jobs_scanned=max_jobs_scanned,
    )
    base = build_runtime_convergence_snapshot(
        transition_traces=transition_traces,
        generated_at_iso=generated_at_iso,
        recalc_queue_jobs=None,
    )
    base["schema_version"] = "workflow_runtime_convergence_snapshot_joined_v2"
    base["joined_rows"] = joined
    base["recalc_convergence_summary"] = build_recalc_convergence_summary(joined)
    base["queue_settlement_visibility"] = build_queue_settlement_visibility_summary(
        recalc_queue_jobs=recalc_queue_jobs,
        joined_rows=joined,
        transition_traces=transition_traces,
        max_jobs_scanned=max_jobs_scanned,
    )
    base["convergence_join_operational_summary"] = build_convergence_join_operational_summary(
        joined_rows=joined,
        transition_traces=transition_traces,
        recalc_queue_jobs=recalc_queue_jobs,
        max_jobs_scanned=max_jobs_scanned,
    )
    return base


