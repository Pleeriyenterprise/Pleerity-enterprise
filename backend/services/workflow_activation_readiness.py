"""
Controlled workflow activation readiness — governance metadata only (Phase 1).

Additive classification and read-only snapshots. No enforcement, no orchestration
changes, no queue/scoring/reminder/cache behavior changes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# --- Scoped families (safest baseline program) ---

FAMILY_COMPLIANCE_SCORE_RECALC = "COMPLIANCE_SCORE_RECALC"
FAMILY_REGENERATION_RECALC = "REGENERATION_RECALC"
FAMILY_NOTIFICATION_DISPATCH = "NOTIFICATION_DISPATCH"
FAMILY_REQUIREMENT_STATE_TRANSITION = "REQUIREMENT_STATE_TRANSITION"

SCOPED_ACTIVATION_FAMILIES = frozenset(
    {
        FAMILY_COMPLIANCE_SCORE_RECALC,
        FAMILY_REGENERATION_RECALC,
        FAMILY_NOTIFICATION_DISPATCH,
        FAMILY_REQUIREMENT_STATE_TRANSITION,
    }
)

# --- Governance-only (not in Phase 1 activation scope) ---

FAMILY_CACHE_INVALIDATION = "CACHE_INVALIDATION"
FAMILY_COMMAND_CENTER_REFRESH = "COMMAND_CENTER_REFRESH"
FAMILY_TODAY_TASK_REBUILD = "TODAY_TASK_REBUILD"
FAMILY_PORTFOLIO_SUMMARY_REFRESH = "PORTFOLIO_SUMMARY_REFRESH"

GOVERNANCE_DEFERRED_FAMILIES = frozenset(
    {
        FAMILY_CACHE_INVALIDATION,
        FAMILY_COMMAND_CENTER_REFRESH,
        FAMILY_TODAY_TASK_REBUILD,
        FAMILY_PORTFOLIO_SUMMARY_REFRESH,
    }
)

# --- Lifecycle / state labels (advisory) ---

NOT_READY = "NOT_READY"
OBSERVE_ONLY = "OBSERVE_ONLY"
SAFE_FOR_LIMITED_ACTIVATION = "SAFE_FOR_LIMITED_ACTIVATION"
SAFE_FOR_INCREMENTAL_EXPANSION = "SAFE_FOR_INCREMENTAL_EXPANSION"
STABILIZATION_REQUIRED = "STABILIZATION_REQUIRED"
DEFERRED_PENDING_ARCHITECTURE = "DEFERRED_PENDING_ARCHITECTURE"

STABILIZATION_STABLE = "STABLE"
STABILIZATION_MONITORING = "MONITORING"
STABILIZATION_AT_RISK = "AT_RISK"

OBSERVABILITY_FULL = "FULL"
OBSERVABILITY_PARTIAL = "PARTIAL"
OBSERVABILITY_GAP = "GAP"

ROLL_OBSERVE_ONLY = "OBSERVE_ONLY"
ROLL_INTERNAL_STAFF_ONLY = "INTERNAL_STAFF_ONLY"
ROLL_LIMITED_PRODUCTION = "LIMITED_PRODUCTION"
ROLL_CONTROLLED_EXPANSION = "CONTROLLED_EXPANSION"
ROLL_BROAD_ACTIVATION_BLOCKED = "BROAD_ACTIVATION_BLOCKED"

RISK_LOW = "LOW"
RISK_MODERATE = "MODERATE"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"

# --- Blocker codes (classification only) ---

BLOCKER_CACHE_BOUNDARY_UNDEFINED = "CACHE_BOUNDARY_UNDEFINED"
BLOCKER_NO_RECONCILIATION_VISIBILITY = "NO_RECONCILIATION_VISIBILITY"
BLOCKER_LOW_CONVERGENCE_CONFIDENCE = "LOW_CONVERGENCE_CONFIDENCE"
BLOCKER_FRAGMENTED_ORCHESTRATION = "FRAGMENTED_ORCHESTRATION"
BLOCKER_NO_DEGRADED_STATE_VISIBILITY = "NO_DEGRADED_STATE_VISIBILITY"
BLOCKER_WEAK_IDEMPOTENCY_VISIBILITY = "WEAK_IDEMPOTENCY_VISIBILITY"
BLOCKER_UNKNOWN_RUNTIME_SETTLEMENT = "UNKNOWN_RUNTIME_SETTLEMENT"
BLOCKER_READ_REBUILD_DEPENDENCY = "READ_REBUILD_DEPENDENCY"
BLOCKER_OBSERVABILITY_GAP = "OBSERVABILITY_GAP"
BLOCKER_SILENT_FAILURE_DOMINANCE = "SILENT_FAILURE_DOMINANCE"

BLOCKER_SEVERITY_INFO = "INFO"
BLOCKER_SEVERITY_WARNING = "WARNING"
BLOCKER_SEVERITY_CRITICAL = "CRITICAL"

LOW_CONVERGENCE_LABELS = frozenset({"LOW_CONVERGENCE_CONFIDENCE", "LOW_MATURITY_VISIBILITY"})


def _base_row(
    *,
    workflow_family: str,
    activation_state: str,
    stabilization_state: str,
    observability_state: str,
    convergence_confidence: str,
    idempotency_confidence: str,
    retry_visibility: str,
    degraded_path_visibility: str,
    operational_owner: str,
    rollout_stage: str,
    activation_blockers: List[Dict[str, Any]],
    activation_risk_classification: str,
    scope_note: str = "",
) -> Dict[str, Any]:
    return {
        "workflow_family": workflow_family,
        "activation_state": activation_state,
        "stabilization_state": stabilization_state,
        "observability_state": observability_state,
        "convergence_confidence": convergence_confidence,
        "idempotency_confidence": idempotency_confidence,
        "retry_visibility": retry_visibility,
        "degraded_path_visibility": degraded_path_visibility,
        "operational_owner": operational_owner,
        "rollout_stage": rollout_stage,
        "activation_blockers": list(activation_blockers),
        "activation_risk_classification": activation_risk_classification,
        "scope_note": scope_note,
        "governance_only": workflow_family in GOVERNANCE_DEFERRED_FAMILIES,
        "scoped_activation_program": workflow_family in SCOPED_ACTIVATION_FAMILIES,
        "non_blocking": True,
        "audit_only": True,
    }


def _governance_deferred_row(family: str) -> Dict[str, Any]:
    blockers = [
        _blocker(
            BLOCKER_READ_REBUILD_DEPENDENCY,
            BLOCKER_SEVERITY_INFO,
            "Trust-surface / cache-adjacent; Phase 1 program excludes this family.",
            "Defer; observability-only until architecture slice.",
        )
    ]
    if family == FAMILY_CACHE_INVALIDATION:
        blockers.insert(
            0,
            _blocker(
                BLOCKER_CACHE_BOUNDARY_UNDEFINED,
                BLOCKER_SEVERITY_CRITICAL,
                "Cache boundaries not part of safe baseline activation.",
                "BROAD_ACTIVATION_BLOCKED; no runtime activation in Phase 1.",
            ),
        )
    return _base_row(
        workflow_family=family,
        activation_state=DEFERRED_PENDING_ARCHITECTURE,
        stabilization_state=STABILIZATION_MONITORING,
        observability_state=OBSERVABILITY_PARTIAL,
        convergence_confidence="UNKNOWN_CONVERGENCE_CONFIDENCE",
        idempotency_confidence="UNKNOWN",
        retry_visibility="UNKNOWN",
        degraded_path_visibility="UNKNOWN",
        operational_owner="platform_governance",
        rollout_stage=ROLL_BROAD_ACTIVATION_BLOCKED,
        activation_blockers=blockers,
        activation_risk_classification=RISK_HIGH,
        scope_note="Governance registry only; not in scoped safest families.",
    )


def _blocker(
    code: str,
    severity: str,
    operational_impact: str,
    rollout_recommendation: str,
) -> Dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "operational_impact": operational_impact,
        "rollout_recommendation": rollout_recommendation,
    }


ACTIVATION_READINESS_REGISTRY_BASE: Dict[str, Dict[str, Any]] = {
    FAMILY_COMPLIANCE_SCORE_RECALC: _base_row(
        workflow_family=FAMILY_COMPLIANCE_SCORE_RECALC,
        activation_state=OBSERVE_ONLY,
        stabilization_state=STABILIZATION_MONITORING,
        observability_state=OBSERVABILITY_FULL,
        convergence_confidence="MODERATE_CONVERGENCE_CONFIDENCE",
        idempotency_confidence="HIGH",
        retry_visibility="BOUNDED",
        degraded_path_visibility="BOUNDED",
        operational_owner="compliance_platform",
        rollout_stage=ROLL_LIMITED_PRODUCTION,
        activation_blockers=[],
        activation_risk_classification=RISK_LOW,
        scope_note="Queue + worker path; eligibility re-evaluated from live signals.",
    ),
    FAMILY_REGENERATION_RECALC: _base_row(
        workflow_family=FAMILY_REGENERATION_RECALC,
        activation_state=OBSERVE_ONLY,
        stabilization_state=STABILIZATION_MONITORING,
        observability_state=OBSERVABILITY_FULL,
        convergence_confidence="MODERATE_CONVERGENCE_CONFIDENCE",
        idempotency_confidence="MODERATE",
        retry_visibility="BOUNDED",
        degraded_path_visibility="BOUNDED",
        operational_owner="compliance_platform",
        rollout_stage=ROLL_LIMITED_PRODUCTION,
        activation_blockers=[],
        activation_risk_classification=RISK_MODERATE,
        scope_note="Delegate enqueue from recalc; eligibility re-evaluated from traces.",
    ),
    FAMILY_NOTIFICATION_DISPATCH: _base_row(
        workflow_family=FAMILY_NOTIFICATION_DISPATCH,
        activation_state=OBSERVE_ONLY,
        stabilization_state=STABILIZATION_MONITORING,
        observability_state=OBSERVABILITY_PARTIAL,
        convergence_confidence="UNKNOWN_CONVERGENCE_CONFIDENCE",
        idempotency_confidence="MODERATE",
        retry_visibility="PARTIAL",
        degraded_path_visibility="PARTIAL",
        operational_owner="notifications",
        rollout_stage=ROLL_INTERNAL_STAFF_ONLY,
        activation_blockers=[
            _blocker(
                BLOCKER_OBSERVABILITY_GAP,
                BLOCKER_SEVERITY_WARNING,
                "Dispatch path may lack full convergence join coverage.",
                "Observe and stabilize metrics before LIMITED_PRODUCTION.",
            )
        ],
        activation_risk_classification=RISK_MODERATE,
        scope_note="Phase 1: observability + stabilization classification only.",
    ),
    FAMILY_REQUIREMENT_STATE_TRANSITION: _base_row(
        workflow_family=FAMILY_REQUIREMENT_STATE_TRANSITION,
        activation_state=OBSERVE_ONLY,
        stabilization_state=STABILIZATION_STABLE,
        observability_state=OBSERVABILITY_FULL,
        convergence_confidence="HIGH_CONVERGENCE_CONFIDENCE",
        idempotency_confidence="HIGH",
        retry_visibility="BOUNDED",
        degraded_path_visibility="BOUNDED",
        operational_owner="compliance_platform",
        rollout_stage=ROLL_LIMITED_PRODUCTION,
        activation_blockers=[],
        activation_risk_classification=RISK_LOW,
        scope_note="Visibility and idempotency signals from transition traces; no new orchestration.",
    ),
    FAMILY_CACHE_INVALIDATION: _governance_deferred_row(FAMILY_CACHE_INVALIDATION),
    FAMILY_COMMAND_CENTER_REFRESH: _governance_deferred_row(FAMILY_COMMAND_CENTER_REFRESH),
    FAMILY_TODAY_TASK_REBUILD: _governance_deferred_row(FAMILY_TODAY_TASK_REBUILD),
    FAMILY_PORTFOLIO_SUMMARY_REFRESH: _governance_deferred_row(FAMILY_PORTFOLIO_SUMMARY_REFRESH),
}


def _collect_signals(
    *,
    convergence_snapshot: Optional[Mapping[str, Any]],
    transition_traces: Optional[Sequence[Mapping[str, Any]]],
    queue_visibility: Optional[Mapping[str, Any]],
    reliability_snapshot: Optional[Mapping[str, Any]],
    stabilization_planning: Optional[Mapping[str, Any]],
    observability_summary: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Derive normalized booleans/ratios from optional snapshot dicts (read-only)."""
    traces = list(transition_traces or [])
    rows: List[Mapping[str, Any]] = []
    for t in traces:
        d = t.get("downstream_trigger_targets") or []
        if isinstance(d, list):
            rows.extend([r for r in d if isinstance(r, Mapping)])

    enqueue_outcomes = [str(r.get("enqueue_outcome") or "") for r in rows]
    has_enqueue_observed = bool(enqueue_outcomes)
    has_accepted = any(o == "ENQUEUE_ACCEPTED" for o in enqueue_outcomes)
    has_failed = any(o in ("ENQUEUE_FAILED", "ENQUEUE_PARTIAL_FAILURE") for o in enqueue_outcomes)
    degraded_marked = any(bool(r.get("degraded_possible")) for r in rows)
    dup_seen = any("DUPLICATE" in str(r.get("enqueue_outcome") or "") for r in rows)

    conv = convergence_snapshot or {}
    low_conf = False
    for path in (
        conv.get("convergence_evidence_matrix", {}),
        conv.get("runtime_convergence_hotspots", {}),
    ):
        if isinstance(path, Mapping):
            text_blob = str(path).upper()
            if any(x in text_blob for x in LOW_CONVERGENCE_LABELS):
                low_conf = True
    # Explicit matrix rows
    mrows = (conv.get("convergence_evidence_matrix") or {}).get("matrix_rows") if isinstance(conv.get("convergence_evidence_matrix"), Mapping) else None
    if isinstance(mrows, list):
        for mr in mrows:
            if not isinstance(mr, Mapping):
                continue
            if str(mr.get("convergence_confidence") or "") in LOW_CONVERGENCE_LABELS:
                low_conf = True
                break
            if str(mr.get("operational_maturity") or "").upper() in LOW_CONVERGENCE_LABELS:
                low_conf = True
                break

    qvis = queue_visibility or {}
    qdiag = qvis.get("diagnostics") if isinstance(qvis, Mapping) else None
    fetch_diag = qvis if "skipped_unbounded_scan" in qvis else qdiag
    if not isinstance(fetch_diag, Mapping):
        fetch_diag = {}
    queue_skipped_unbounded = bool(fetch_diag.get("skipped_unbounded_scan"))
    silent_failure_dominance = has_failed and not has_accepted and has_enqueue_observed

    rel = reliability_snapshot or {}
    fragmented = str(rel.get("orchestration_fragmentation") or "").upper() in ("CRITICAL", "HIGH")

    stab = stabilization_planning or {}
    stab_risk = str(stab.get("critical_path_risk") or "").upper() == "CRITICAL"

    obs = observability_summary or {}
    recon_visible = True
    if isinstance(obs.get("reconciliation_visibility"), Mapping):
        hist = (obs["reconciliation_visibility"] or {}).get("by_reconciliation_evidence") or {}
        if isinstance(hist, Mapping) and hist.get("RECONCILIATION_NOT_VISIBLE", 0) and not hist.get("RECONCILIATION_OBSERVED"):
            recon_visible = False

    return {
        "trace_count": len(traces),
        "downstream_row_count": len(rows),
        "has_enqueue_observed": has_enqueue_observed,
        "has_accepted_enqueue": has_accepted,
        "degraded_marked": degraded_marked,
        "duplicate_enqueue_signal": dup_seen,
        "low_convergence_signal": low_conf,
        "queue_skipped_unbounded": queue_skipped_unbounded,
        "silent_failure_dominance": silent_failure_dominance,
        "fragmented_orchestration": fragmented or stab_risk,
        "reconciliation_visibility_ok": recon_visible,
        "has_snapshot_inputs": bool(conv or traces or qvis or rel or stab or obs),
    }


def derive_activation_blockers(
    *,
    workflow_family: str,
    signals: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    if workflow_family in GOVERNANCE_DEFERRED_FAMILIES:
        return list((ACTIVATION_READINESS_REGISTRY_BASE.get(workflow_family) or {}).get("activation_blockers") or [])

    if signals.get("low_convergence_signal"):
        blockers.append(
            _blocker(
                BLOCKER_LOW_CONVERGENCE_CONFIDENCE,
                BLOCKER_SEVERITY_WARNING,
                "Convergence confidence inferred LOW from snapshot text or matrix rows.",
                "Hold at OBSERVE_ONLY or STABILIZATION_REQUIRED until convergence improves.",
            )
        )
    if not signals.get("reconciliation_visibility_ok", True):
        blockers.append(
            _blocker(
                BLOCKER_NO_RECONCILIATION_VISIBILITY,
                BLOCKER_SEVERITY_WARNING,
                "Reconciliation evidence thin in observability summary.",
                "Expand reconciliation traces before incremental expansion.",
            )
        )
    if signals.get("queue_skipped_unbounded"):
        blockers.append(
            _blocker(
                BLOCKER_UNKNOWN_RUNTIME_SETTLEMENT,
                BLOCKER_SEVERITY_WARNING,
                "Queue fetch skipped unbounded scan; settlement visibility incomplete.",
                "Provide bounded property/client filters for join diagnostics.",
            )
        )
    if signals.get("silent_failure_dominance"):
        blockers.append(
            _blocker(
                BLOCKER_SILENT_FAILURE_DOMINANCE,
                BLOCKER_SEVERITY_CRITICAL,
                "Enqueue failures dominate without accepted completions in sample.",
                "STABILIZATION_REQUIRED; do not expand activation.",
            )
        )
    if not signals.get("degraded_marked") and signals.get("has_enqueue_observed"):
        blockers.append(
            _blocker(
                BLOCKER_NO_DEGRADED_STATE_VISIBILITY,
                BLOCKER_SEVERITY_INFO,
                "No degraded_possible markers on downstream rows in sample.",
                "Acceptable if other degraded signals exist; verify fanout coverage.",
            )
        )
    if not signals.get("duplicate_enqueue_signal") and signals.get("has_accepted_enqueue"):
        blockers.append(
            _blocker(
                BLOCKER_WEAK_IDEMPOTENCY_VISIBILITY,
                BLOCKER_SEVERITY_INFO,
                "No duplicate-suppression visibility in sample traces.",
                "Not blocking if dedupe proven elsewhere.",
            )
        )
    if signals.get("fragmented_orchestration"):
        blockers.append(
            _blocker(
                BLOCKER_FRAGMENTED_ORCHESTRATION,
                BLOCKER_SEVERITY_WARNING,
                "Stabilization/reliability snapshot indicates fragmented critical path.",
                "Defer incremental expansion until orchestration clarity improves.",
            )
        )
    return blockers


def classify_activation_state(
    *,
    workflow_family: str,
    signals: Mapping[str, Any],
    blockers: Sequence[Mapping[str, Any]],
) -> Tuple[str, str]:
    """
    Return (activation_state, activation_risk_classification). Advisory only.
    """
    if workflow_family in GOVERNANCE_DEFERRED_FAMILIES:
        return DEFERRED_PENDING_ARCHITECTURE, RISK_HIGH

    critical = any(str(b.get("severity")) == BLOCKER_SEVERITY_CRITICAL for b in blockers)
    if critical:
        return STABILIZATION_REQUIRED, RISK_CRITICAL

    if not signals.get("has_snapshot_inputs"):
        return NOT_READY, RISK_MODERATE

    if signals.get("low_convergence_signal") or signals.get("silent_failure_dominance"):
        return STABILIZATION_REQUIRED, RISK_HIGH

    warn = sum(1 for b in blockers if str(b.get("severity")) == BLOCKER_SEVERITY_WARNING)
    if warn >= 2:
        return OBSERVE_ONLY, RISK_MODERATE

    # Safe path: bounded visibility + no dominant silent failures + convergence ok
    if (
        signals.get("has_accepted_enqueue") or signals.get("has_enqueue_observed")
    ) and not signals.get("low_convergence_signal"):
        if workflow_family in (FAMILY_NOTIFICATION_DISPATCH,):
            return SAFE_FOR_LIMITED_ACTIVATION, RISK_MODERATE
        if workflow_family in (FAMILY_REQUIREMENT_STATE_TRANSITION,):
            return SAFE_FOR_INCREMENTAL_EXPANSION, RISK_LOW
        return SAFE_FOR_LIMITED_ACTIVATION, RISK_LOW

    return OBSERVE_ONLY, RISK_MODERATE


def merge_readiness_row_with_signals(
    workflow_family: str,
    *,
    convergence_snapshot: Optional[Mapping[str, Any]] = None,
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    queue_visibility: Optional[Mapping[str, Any]] = None,
    reliability_snapshot: Optional[Mapping[str, Any]] = None,
    stabilization_planning: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    base = ACTIVATION_READINESS_REGISTRY_BASE.get(workflow_family)
    if not base:
        return _base_row(
            workflow_family=workflow_family,
            activation_state=NOT_READY,
            stabilization_state=STABILIZATION_AT_RISK,
            observability_state=OBSERVABILITY_GAP,
            convergence_confidence="UNKNOWN_CONVERGENCE_CONFIDENCE",
            idempotency_confidence="UNKNOWN",
            retry_visibility="UNKNOWN",
            degraded_path_visibility="UNKNOWN",
            operational_owner="unknown",
            rollout_stage=ROLL_OBSERVE_ONLY,
            activation_blockers=[
                _blocker(
                    BLOCKER_OBSERVABILITY_GAP,
                    BLOCKER_SEVERITY_WARNING,
                    "Family not in activation registry.",
                    "Add to registry before activation planning.",
                )
            ],
            activation_risk_classification=RISK_HIGH,
        )
    row = dict(base)
    signals = _collect_signals(
        convergence_snapshot=convergence_snapshot,
        transition_traces=transition_traces,
        queue_visibility=queue_visibility,
        reliability_snapshot=reliability_snapshot,
        stabilization_planning=stabilization_planning,
        observability_summary=observability_summary,
    )
    derived = derive_activation_blockers(workflow_family=workflow_family, signals=signals)
    by_code = {str(b.get("code")): dict(b) for b in (row.get("activation_blockers") or []) if isinstance(b, Mapping)}
    for b in derived:
        if isinstance(b, Mapping) and b.get("code"):
            by_code[str(b["code"])] = dict(b)
    blockers_list = sorted(by_code.values(), key=lambda b: (str(b.get("code") or ""), str(b.get("severity") or "")))
    act_state, risk = classify_activation_state(workflow_family=workflow_family, signals=signals, blockers=blockers_list)
    row["activation_state"] = act_state
    row["activation_risk_classification"] = risk
    row["activation_blockers"] = blockers_list
    row["signal_summary"] = dict(sorted(signals.items()))
    if workflow_family in GOVERNANCE_DEFERRED_FAMILIES:
        row["rollout_stage"] = base.get("rollout_stage", ROLL_BROAD_ACTIVATION_BLOCKED)
    elif act_state in (SAFE_FOR_LIMITED_ACTIVATION, SAFE_FOR_INCREMENTAL_EXPANSION):
        row["rollout_stage"] = ROLL_CONTROLLED_EXPANSION
    elif act_state == STABILIZATION_REQUIRED:
        row["rollout_stage"] = ROLL_INTERNAL_STAFF_ONLY
    elif act_state == NOT_READY:
        row["rollout_stage"] = ROLL_OBSERVE_ONLY
    return row


def build_workflow_activation_operational_snapshot(
    *,
    convergence_snapshot: Optional[Mapping[str, Any]] = None,
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    queue_visibility: Optional[Mapping[str, Any]] = None,
    reliability_snapshot: Optional[Mapping[str, Any]] = None,
    stabilization_planning: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    generated_at_iso: str,
    families: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    fams = sorted(set(families) if families else set(ACTIVATION_READINESS_REGISTRY_BASE.keys()))
    rows = [
        merge_readiness_row_with_signals(
            f,
            convergence_snapshot=convergence_snapshot,
            transition_traces=transition_traces,
            queue_visibility=queue_visibility,
            reliability_snapshot=reliability_snapshot,
            stabilization_planning=stabilization_planning,
            observability_summary=observability_summary,
        )
        for f in fams
    ]
    return {
        "schema_version": "workflow_activation_operational_snapshot_v1",
        "generated_at_iso": generated_at_iso,
        "families": rows,
        "non_blocking": True,
        "audit_only": True,
    }


def build_activation_readiness_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    by_state: Dict[str, int] = {}
    for r in rows:
        st = str(r.get("activation_state") or "")
        by_state[st] = by_state.get(st, 0) + 1
    return {
        "schema_version": "activation_readiness_summary_v1",
        "by_activation_state": dict(sorted(by_state.items())),
        "scoped_family_count": sum(1 for r in rows if r.get("scoped_activation_program")),
        "governance_deferred_count": sum(1 for r in rows if r.get("governance_only")),
        "non_blocking": True,
    }


def build_activation_risk_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    by_risk: Dict[str, int] = {}
    for r in rows:
        rk = str(r.get("activation_risk_classification") or "")
        by_risk[rk] = by_risk.get(rk, 0) + 1
    critical_blockers = 0
    for r in rows:
        for b in r.get("activation_blockers") or []:
            if isinstance(b, Mapping) and str(b.get("severity")) == BLOCKER_SEVERITY_CRITICAL:
                critical_blockers += 1
    return {
        "schema_version": "activation_risk_summary_v1",
        "by_risk_classification": dict(sorted(by_risk.items())),
        "critical_blocker_row_count": critical_blockers,
        "non_blocking": True,
    }


def build_safe_activation_candidates(snapshot: Mapping[str, Any]) -> List[str]:
    rows = list(snapshot.get("families") or [])
    out = sorted(
        str(r.get("workflow_family") or "")
        for r in rows
        if r.get("activation_state") in (SAFE_FOR_LIMITED_ACTIVATION, SAFE_FOR_INCREMENTAL_EXPANSION)
        and r.get("scoped_activation_program")
    )
    return [x for x in out if x]


def build_deferred_activation_candidates(snapshot: Mapping[str, Any]) -> List[str]:
    rows = list(snapshot.get("families") or [])
    out = sorted(
        str(r.get("workflow_family") or "")
        for r in rows
        if r.get("activation_state")
        in (DEFERRED_PENDING_ARCHITECTURE, STABILIZATION_REQUIRED, NOT_READY, OBSERVE_ONLY)
        or r.get("governance_only")
    )
    return [x for x in out if x]
