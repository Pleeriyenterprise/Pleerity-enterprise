"""
Workflow activation operational calibration — evidence vs readiness (Phase 2).

Read-only, deterministic comparison of activation-readiness classifications against
runtime-shaped evidence. No enforcement, no mutations, no orchestration changes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from services.workflow_activation_readiness import (
    BLOCKER_SEVERITY_CRITICAL,
    DEFERRED_PENDING_ARCHITECTURE,
    GOVERNANCE_DEFERRED_FAMILIES,
    NOT_READY,
    OBSERVE_ONLY,
    SAFE_FOR_INCREMENTAL_EXPANSION,
    SAFE_FOR_LIMITED_ACTIVATION,
    STABILIZATION_REQUIRED,
)

# --- Calibration outcomes (advisory) ---

CALIBRATION_CONFIRMED = "CALIBRATION_CONFIRMED"
CALIBRATION_PARTIAL = "CALIBRATION_PARTIAL"
CALIBRATION_UNCERTAIN = "CALIBRATION_UNCERTAIN"
CALIBRATION_DEGRADED = "CALIBRATION_DEGRADED"
CALIBRATION_BLOCKED = "CALIBRATION_BLOCKED"
CALIBRATION_INSUFFICIENT_EVIDENCE = "CALIBRATION_INSUFFICIENT_EVIDENCE"

# --- Runtime confidence (evidence-backed rollup) ---

HIGH_RUNTIME_CONFIDENCE = "HIGH_RUNTIME_CONFIDENCE"
MODERATE_RUNTIME_CONFIDENCE = "MODERATE_RUNTIME_CONFIDENCE"
LOW_RUNTIME_CONFIDENCE = "LOW_RUNTIME_CONFIDENCE"
UNKNOWN_RUNTIME_CONFIDENCE = "UNKNOWN_RUNTIME_CONFIDENCE"

# --- Evidence gap codes ---

GAP_NO_RUNTIME_SAMPLE = "NO_RUNTIME_SAMPLE"
GAP_NO_SETTLEMENT_VISIBILITY = "NO_SETTLEMENT_VISIBILITY"
GAP_NO_RECONCILIATION_VISIBILITY = "NO_RECONCILIATION_VISIBILITY"
GAP_STALE_STATE_OPAQUE = "STALE_STATE_OPAQUE"
GAP_DEGRADED_PATH_OPAQUE = "DEGRADED_PATH_OPAQUE"
GAP_OBSERVABILITY_FRAGMENTATION = "OBSERVABILITY_FRAGMENTATION"
GAP_WEAK_IDEMPOTENCY_EVIDENCE = "WEAK_IDEMPOTENCY_EVIDENCE"
GAP_PARTIAL_CONVERGENCE_EVIDENCE = "PARTIAL_CONVERGENCE_EVIDENCE"
GAP_TRUST_SURFACE_DIVERGENCE = "TRUST_SURFACE_DIVERGENCE"

# --- Thresholds (deterministic advisory bands) ---

_SCORE_HIGH = 70
_SCORE_MID = 50
_SCORE_LOW = 35
_RUNTIME_HIGH_AVG = 75
_RUNTIME_MODERATE_AVG = 50


def _clamp_int(x: float) -> int:
    return max(0, min(100, int(round(x))))


def _downstream_rows_from_traces(traces: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    rows: List[Mapping[str, Any]] = []
    for t in traces:
        d = t.get("downstream_trigger_targets") or []
        if isinstance(d, list):
            rows.extend([r for r in d if isinstance(r, Mapping)])
    return rows


def build_operational_evidence_bundle(
    *,
    readiness_row: Mapping[str, Any],
    convergence_snapshot: Optional[Mapping[str, Any]] = None,
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    queue_visibility: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    reliability_snapshot: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalize inputs into a single evidence dict (read-only merge)."""
    traces = list(transition_traces or [])
    rows = _downstream_rows_from_traces(traces)
    sig = dict(readiness_row.get("signal_summary") or {})

    conv = convergence_snapshot or {}
    mrows = (conv.get("convergence_evidence_matrix") or {}).get("matrix_rows") if isinstance(conv.get("convergence_evidence_matrix"), Mapping) else None
    matrix_count = len(mrows) if isinstance(mrows, list) else 0
    low_matrix = False
    if isinstance(mrows, list):
        for mr in mrows:
            if not isinstance(mr, Mapping):
                continue
            if "LOW" in str(mr.get("convergence_confidence") or ""):
                low_matrix = True
                break

    qvis = queue_visibility or {}
    qdiag = qvis.get("diagnostics") if isinstance(qvis, Mapping) and "diagnostics" in qvis else qvis
    if not isinstance(qdiag, Mapping):
        qdiag = {}
    queue_skipped = bool(qdiag.get("skipped_unbounded_scan"))
    queue_returned = int(qdiag.get("returned_count") or len(qvis.get("jobs") or []) or 0)

    obs = observability_summary or {}
    rhist: Dict[str, Any] = {}
    if isinstance(obs.get("reconciliation_visibility"), Mapping):
        rhist = dict((obs["reconciliation_visibility"] or {}).get("by_reconciliation_evidence") or {})

    joined = conv.get("joined_rows") if isinstance(conv, Mapping) else None
    stale_joined = 0
    if isinstance(joined, list):
        stale_joined = sum(1 for r in joined if isinstance(r, Mapping) and r.get("stale_read_risk_visible"))

    rel = reliability_snapshot or {}
    fragmented = str(rel.get("orchestration_fragmentation") or "").upper() in ("HIGH", "CRITICAL")

    return {
        "trace_count": len(traces),
        "downstream_row_count": len(rows),
        "has_accepted_enqueue": bool(sig.get("has_accepted_enqueue")),
        "silent_failure_dominance": bool(sig.get("silent_failure_dominance")),
        "low_convergence_signal": bool(sig.get("low_convergence_signal")),
        "queue_skipped_unbounded": queue_skipped,
        "queue_returned_count": queue_returned,
        "convergence_matrix_row_count": matrix_count,
        "convergence_matrix_low_signal": low_matrix,
        "reconciliation_hist": dict(sorted(rhist.items())),
        "stale_joined_row_count": stale_joined,
        "degraded_marked": bool(sig.get("degraded_marked")) or any(bool(r.get("degraded_possible")) for r in rows),
        "duplicate_enqueue_signal": bool(sig.get("duplicate_enqueue_signal")),
        "fragmented_orchestration_signal": fragmented or bool(sig.get("fragmented_orchestration")),
        "has_snapshot_inputs": bool(sig.get("has_snapshot_inputs")),
    }


def derive_evidence_scores(bundle: Mapping[str, Any]) -> Dict[str, int]:
    """Bounded 0–100 advisory scores; deterministic, no ML."""
    # Settlement: queue not skipped + (returned jobs or enqueue accepted)
    settlement = 0
    if not bundle.get("queue_skipped_unbounded"):
        settlement += 40
    if int(bundle.get("queue_returned_count") or 0) > 0:
        settlement += 35
    if bundle.get("has_accepted_enqueue"):
        settlement += 25
    settlement = _clamp_int(settlement)

    # Degraded: explicit markers or downstream degraded_possible
    degraded = 55 if bundle.get("degraded_marked") else 25
    if bundle.get("downstream_row_count", 0) > 0 and bundle.get("degraded_marked"):
        degraded = 85
    degraded = _clamp_int(degraded)

    # Reconciliation: histogram has OBSERVED or RECOVERED
    rh = bundle.get("reconciliation_hist") or {}
    recon = 30
    if isinstance(rh, Mapping):
        if rh.get("RECONCILIATION_OBSERVED", 0) or rh.get("RECONCILIATION_RECOVERED", 0):
            recon = 90
        elif rh.get("RECONCILIATION_PENDING", 0) and not rh.get("RECONCILIATION_NOT_VISIBLE", 0):
            recon = 60
        elif rh.get("RECONCILIATION_NOT_VISIBLE", 0) and not rh.get("RECONCILIATION_OBSERVED", 0):
            recon = 25
    recon = _clamp_int(recon)

    # Stale: fewer stale joined rows is better
    sj = int(bundle.get("stale_joined_row_count") or 0)
    stale = _clamp_int(100 - min(100, sj * 20))

    # Idempotency
    idem = 90 if bundle.get("duplicate_enqueue_signal") else 40
    idem = _clamp_int(idem)

    # Convergence
    conv = 25
    if int(bundle.get("convergence_matrix_row_count") or 0) > 0:
        conv += 40
    if not bundle.get("convergence_matrix_low_signal") and int(bundle.get("convergence_matrix_row_count") or 0) > 0:
        conv += 35
    elif bundle.get("convergence_matrix_low_signal"):
        conv = 30
    conv = _clamp_int(conv)

    # Observability coverage: inputs present
    cov = 20
    if bundle.get("trace_count", 0) > 0:
        cov += 25
    if int(bundle.get("queue_returned_count") or 0) > 0 or bundle.get("has_accepted_enqueue"):
        cov += 25
    if int(bundle.get("convergence_matrix_row_count") or 0) > 0:
        cov += 20
    if isinstance(rh, Mapping) and rh:
        cov += 10
    cov = _clamp_int(cov)

    return {
        "settlement_visibility_score": settlement,
        "degraded_visibility_score": degraded,
        "reconciliation_visibility_score": recon,
        "stale_state_visibility_score": stale,
        "idempotency_visibility_score": idem,
        "convergence_visibility_score": conv,
        "observability_coverage_score": cov,
    }


def derive_evidence_gaps(
    bundle: Mapping[str, Any],
    scores: Mapping[str, int],
) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []

    def _g(code: str, severity: str, implication: str, posture: str) -> Dict[str, Any]:
        return {
            "code": code,
            "severity": severity,
            "operational_implication": implication,
            "recommended_operational_posture": posture,
        }

    if not bundle.get("has_snapshot_inputs") and bundle.get("trace_count", 0) == 0 and int(bundle.get("queue_returned_count") or 0) == 0:
        gaps.append(
            _g(
                GAP_NO_RUNTIME_SAMPLE,
                "WARNING",
                "No traces or queue rows in sample; calibration is weakly grounded.",
                "Collect bounded convergence diagnostic sample before relying on calibration.",
            )
        )
    if scores.get("settlement_visibility_score", 0) < _SCORE_MID:
        gaps.append(
            _g(
                GAP_NO_SETTLEMENT_VISIBILITY,
                "WARNING",
                "Settlement / queue join visibility is thin in the evidence bundle.",
                "Run read-only queue fetch with property/client scope.",
            )
        )
    if scores.get("reconciliation_visibility_score", 0) < _SCORE_MID:
        gaps.append(
            _g(
                GAP_NO_RECONCILIATION_VISIBILITY,
                "WARNING",
                "Reconciliation evidence not clearly observable in sample.",
                "Pair transition traces with gap-sync visibility or observability summary.",
            )
        )
    if scores.get("stale_state_visibility_score", 0) < _SCORE_LOW:
        gaps.append(
            _g(
                GAP_STALE_STATE_OPAQUE,
                "INFO",
                "Stale-read / joined stale risk signals are elevated or opaque.",
                "Treat trust-surface reads as possibly stale; use convergence join output.",
            )
        )
    if scores.get("degraded_visibility_score", 0) < _SCORE_MID:
        gaps.append(
            _g(
                GAP_DEGRADED_PATH_OPAQUE,
                "INFO",
                "Limited degraded_path markers in downstream rows.",
                "Ensure fanout rows attach degraded_possible where applicable.",
            )
        )
    if bundle.get("fragmented_orchestration_signal"):
        gaps.append(
            _g(
                GAP_OBSERVABILITY_FRAGMENTATION,
                "WARNING",
                "Orchestration fragmentation signal present in reliability/stabilization inputs.",
                "Hold calibration as advisory; reduce cross-surface coupling in review.",
            )
        )
    if scores.get("idempotency_visibility_score", 0) < _SCORE_MID:
        gaps.append(
            _g(
                GAP_WEAK_IDEMPOTENCY_EVIDENCE,
                "INFO",
                "Duplicate-suppression / idempotency not evident in sample.",
                "Not blocking if dedupe proven outside sample window.",
            )
        )
    if scores.get("convergence_visibility_score", 0) < _SCORE_MID:
        gaps.append(
            _g(
                GAP_PARTIAL_CONVERGENCE_EVIDENCE,
                "WARNING",
                "Convergence matrix thin or LOW-confidence signalled.",
                "Expand convergence snapshot before promoting activation narrative.",
            )
        )
    if int(bundle.get("stale_joined_row_count") or 0) > 2 and scores.get("settlement_visibility_score", 0) < _SCORE_HIGH:
        gaps.append(
            _g(
                GAP_TRUST_SURFACE_DIVERGENCE,
                "WARNING",
                "Stale risk without strong settlement visibility suggests trust-surface divergence risk.",
                "Prefer property-scoped recalc join + freshness metadata in review.",
            )
        )

    return sorted(gaps, key=lambda g: (g.get("code") or "", g.get("severity") or ""))


def _avg_score(scores: Mapping[str, int]) -> float:
    vals = list(scores.values())
    return sum(vals) / len(vals) if vals else 0.0


def classify_runtime_confidence(scores: Mapping[str, int], bundle: Mapping[str, Any]) -> str:
    if not bundle.get("has_snapshot_inputs") and bundle.get("trace_count", 0) == 0:
        return UNKNOWN_RUNTIME_CONFIDENCE
    avg = _avg_score(scores)
    if avg >= _RUNTIME_HIGH_AVG:
        return HIGH_RUNTIME_CONFIDENCE
    if avg >= _RUNTIME_MODERATE_AVG:
        return MODERATE_RUNTIME_CONFIDENCE
    if avg > 0:
        return LOW_RUNTIME_CONFIDENCE
    return UNKNOWN_RUNTIME_CONFIDENCE


def _has_critical_blocker(readiness_row: Mapping[str, Any]) -> bool:
    for b in readiness_row.get("activation_blockers") or []:
        if isinstance(b, Mapping) and str(b.get("severity")) == BLOCKER_SEVERITY_CRITICAL:
            return True
    return False


def classify_calibration_outcome(
    *,
    readiness_row: Mapping[str, Any],
    bundle: Mapping[str, Any],
    scores: Mapping[str, int],
    gaps: Sequence[Mapping[str, Any]],
) -> str:
    fam = str(readiness_row.get("workflow_family") or "")
    act = str(readiness_row.get("activation_state") or "")

    if fam in GOVERNANCE_DEFERRED_FAMILIES or act == DEFERRED_PENDING_ARCHITECTURE:
        return CALIBRATION_BLOCKED

    if act == NOT_READY or not bundle.get("has_snapshot_inputs"):
        if bundle.get("trace_count", 0) == 0 and int(bundle.get("queue_returned_count") or 0) == 0:
            return CALIBRATION_INSUFFICIENT_EVIDENCE

    if bundle.get("silent_failure_dominance") or _has_critical_blocker(readiness_row):
        return CALIBRATION_DEGRADED

    if act not in (SAFE_FOR_LIMITED_ACTIVATION, SAFE_FOR_INCREMENTAL_EXPANSION):
        if scores.get("convergence_visibility_score", 0) >= _SCORE_HIGH and not bundle.get("low_convergence_signal"):
            return CALIBRATION_PARTIAL
        return CALIBRATION_UNCERTAIN

    # Safe readiness: require evidence bars for CONFIRMED
    confirmed = (
        int(bundle.get("convergence_matrix_row_count") or 0) > 0
        and scores.get("settlement_visibility_score", 0) >= _SCORE_MID
        and scores.get("degraded_visibility_score", 0) >= _SCORE_MID
        and scores.get("reconciliation_visibility_score", 0) >= _SCORE_MID
        and not bundle.get("silent_failure_dominance")
        and not _has_critical_blocker(readiness_row)
        and scores.get("stale_state_visibility_score", 0) >= _SCORE_LOW
        and not bundle.get("low_convergence_signal")
    )
    if confirmed:
        return CALIBRATION_CONFIRMED

    if scores.get("settlement_visibility_score", 0) < _SCORE_LOW or scores.get("convergence_visibility_score", 0) < _SCORE_LOW:
        return CALIBRATION_DEGRADED

    warn_gaps = sum(1 for g in gaps if str(g.get("severity")) == "WARNING")
    if warn_gaps >= 2:
        return CALIBRATION_UNCERTAIN
    return CALIBRATION_PARTIAL


def analyze_calibration_drift(
    *,
    readiness_row: Mapping[str, Any],
    calibration_outcome: str,
    runtime_confidence: str,
) -> Tuple[bool, str, bool]:
    """(drift_detected, reason, governance_review_recommended). Advisory only."""
    act = str(readiness_row.get("activation_state") or "")
    drift = False
    reason = ""
    review = False

    if act in (SAFE_FOR_LIMITED_ACTIVATION, SAFE_FOR_INCREMENTAL_EXPANSION):
        if runtime_confidence == LOW_RUNTIME_CONFIDENCE:
            drift = True
            reason = "readiness_marked_safe_but_runtime_confidence_low"
        elif calibration_outcome in (CALIBRATION_UNCERTAIN, CALIBRATION_DEGRADED, CALIBRATION_INSUFFICIENT_EVIDENCE):
            drift = True
            reason = "readiness_marked_safe_but_calibration_not_confirmed"

    if act == OBSERVE_ONLY and runtime_confidence == HIGH_RUNTIME_CONFIDENCE:
        if calibration_outcome in (CALIBRATION_PARTIAL, CALIBRATION_CONFIRMED):
            drift = True
            reason = "observe_only_but_high_runtime_evidence_may_warrant_governance_review"
            review = True

    if act == STABILIZATION_REQUIRED and runtime_confidence == HIGH_RUNTIME_CONFIDENCE:
        drift = True
        reason = "stabilization_required_despite_high_runtime_sample_review_context"
        review = True

    return drift, reason, review


def build_family_calibration_row(
    readiness_row: Mapping[str, Any],
    *,
    convergence_snapshot: Optional[Mapping[str, Any]] = None,
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    queue_visibility: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    reliability_snapshot: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    bundle = build_operational_evidence_bundle(
        readiness_row=readiness_row,
        convergence_snapshot=convergence_snapshot,
        transition_traces=transition_traces,
        queue_visibility=queue_visibility,
        observability_summary=observability_summary,
        reliability_snapshot=reliability_snapshot,
    )
    scores = derive_evidence_scores(bundle)
    gaps = derive_evidence_gaps(bundle, scores)
    cal = classify_calibration_outcome(readiness_row=readiness_row, bundle=bundle, scores=scores, gaps=gaps)
    runtime_conf = classify_runtime_confidence(scores, bundle)
    drift, drift_reason, review = analyze_calibration_drift(
        readiness_row=readiness_row,
        calibration_outcome=cal,
        runtime_confidence=runtime_conf,
    )
    return {
        "workflow_family": readiness_row.get("workflow_family"),
        "readiness_activation_state": readiness_row.get("activation_state"),
        "calibration_outcome": cal,
        "runtime_confidence": runtime_conf,
        "evidence_scores": dict(sorted(scores.items())),
        "evidence_gaps": gaps,
        "evidence_bundle": dict(sorted(bundle.items(), key=lambda kv: str(kv[0]))),
        "calibration_drift_detected": drift,
        "calibration_drift_reason": drift_reason or None,
        "governance_review_recommended": review,
        "non_blocking": True,
        "audit_only": True,
    }


def build_workflow_activation_calibration_snapshot(
    *,
    activation_operational_snapshot: Mapping[str, Any],
    generated_at_iso: str,
    convergence_snapshot: Optional[Mapping[str, Any]] = None,
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    queue_visibility: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    reliability_snapshot: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    rows_in = list(activation_operational_snapshot.get("families") or [])
    rows = [
        build_family_calibration_row(
            r,
            convergence_snapshot=convergence_snapshot,
            transition_traces=transition_traces,
            queue_visibility=queue_visibility,
            observability_summary=observability_summary,
            reliability_snapshot=reliability_snapshot,
        )
        for r in sorted(rows_in, key=lambda x: str(x.get("workflow_family") or ""))
    ]
    return {
        "schema_version": "workflow_activation_calibration_snapshot_v1",
        "generated_at_iso": generated_at_iso,
        "families": rows,
        "non_blocking": True,
        "audit_only": True,
    }


def build_calibration_summary(calibration_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(calibration_snapshot.get("families") or [])
    hist: Dict[str, int] = {}
    for r in rows:
        k = str(r.get("calibration_outcome") or "")
        hist[k] = hist.get(k, 0) + 1
    drift_n = sum(1 for r in rows if r.get("calibration_drift_detected"))
    return {
        "schema_version": "calibration_summary_v1",
        "by_calibration_outcome": dict(sorted(hist.items())),
        "drift_detected_count": drift_n,
        "non_blocking": True,
    }


def build_runtime_confidence_summary(calibration_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(calibration_snapshot.get("families") or [])
    hist: Dict[str, int] = {}
    for r in rows:
        k = str(r.get("runtime_confidence") or "")
        hist[k] = hist.get(k, 0) + 1
    return {
        "schema_version": "runtime_confidence_summary_v1",
        "by_runtime_confidence": dict(sorted(hist.items())),
        "non_blocking": True,
    }


def build_evidence_gap_summary(calibration_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(calibration_snapshot.get("families") or [])
    by_code: Dict[str, int] = {}
    for r in rows:
        for g in r.get("evidence_gaps") or []:
            if isinstance(g, Mapping):
                c = str(g.get("code") or "")
                by_code[c] = by_code.get(c, 0) + 1
    return {
        "schema_version": "evidence_gap_summary_v1",
        "by_gap_code": dict(sorted(by_code.items())),
        "non_blocking": True,
    }


def build_confirmed_activation_candidates(calibration_snapshot: Mapping[str, Any]) -> List[str]:
    rows = list(calibration_snapshot.get("families") or [])
    return sorted(
        str(r.get("workflow_family") or "")
        for r in rows
        if r.get("calibration_outcome") == CALIBRATION_CONFIRMED
        and str(r.get("readiness_activation_state") or "") in (SAFE_FOR_LIMITED_ACTIVATION, SAFE_FOR_INCREMENTAL_EXPANSION)
    )


def build_uncertain_activation_candidates(calibration_snapshot: Mapping[str, Any]) -> List[str]:
    rows = list(calibration_snapshot.get("families") or [])
    return sorted(
        str(r.get("workflow_family") or "")
        for r in rows
        if r.get("calibration_outcome")
        in (CALIBRATION_UNCERTAIN, CALIBRATION_PARTIAL, CALIBRATION_INSUFFICIENT_EVIDENCE)
    )
