"""
Unified workflow activation governance report (Phase 4).

Single read-only deterministic artifact for operators. No enforcement, no runtime
mutations, no DB access.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from services.workflow_activation_calibration import (
    CALIBRATION_CONFIRMED,
    CALIBRATION_DEGRADED,
    CALIBRATION_INSUFFICIENT_EVIDENCE,
    CALIBRATION_PARTIAL,
    CALIBRATION_UNCERTAIN,
    LOW_RUNTIME_CONFIDENCE,
    build_calibration_summary,
    build_confirmed_activation_candidates,
    build_evidence_gap_summary,
    build_runtime_confidence_summary,
    build_workflow_activation_calibration_snapshot,
)
from services.workflow_activation_governance import (
    GOVERNANCE_APPROVAL_CONDITIONAL,
    GOVERNANCE_APPROVAL_READY,
    GOVERNANCE_BLOCKED,
    GOVERNANCE_OBSERVE_ONLY,
    GOVERNANCE_REVIEW_RECOMMENDED,
    GOVERNANCE_REVIEW_REQUIRED,
    ROLLBACK_NOT_DEFINED,
    ROLLBACK_UNCERTAIN,
    build_escalation_risk_summary,
    build_governance_blocked_candidates,
    build_governance_drift_summary,
    build_governance_review_summary,
    build_operational_approval_summary,
    build_rollback_posture_summary,
    build_workflow_activation_governance_snapshot,
)
from services.workflow_runtime_activation_registry import (
    build_activation_rollout_visibility,
    build_activation_state_summary,
    build_regeneration_limited_activation_visibility,
    build_rst_core_backbone_activation_operational_visibility,
    build_runtime_activation_snapshot,
)
from services.workflow_activation_readiness import (
    DEFERRED_PENDING_ARCHITECTURE,
    GOVERNANCE_DEFERRED_FAMILIES,
    NOT_READY,
    OBSERVE_ONLY,
    RISK_CRITICAL,
    RISK_HIGH,
    RISK_LOW,
    RISK_MODERATE,
    SAFE_FOR_INCREMENTAL_EXPANSION,
    SAFE_FOR_LIMITED_ACTIVATION,
    STABILIZATION_REQUIRED,
    build_activation_readiness_summary,
    build_workflow_activation_operational_snapshot,
)

REPORT_VERSION = "workflow_activation_governance_report_v1"

# --- Advisory governance decision posture (per family) ---

APPROVE_FOR_LIMITED_ACTIVATION = "APPROVE_FOR_LIMITED_ACTIVATION"
APPROVE_WITH_GOVERNANCE_GUARDS = "APPROVE_WITH_GOVERNANCE_GUARDS"
HOLD_PENDING_EVIDENCE = "HOLD_PENDING_EVIDENCE"
HOLD_PENDING_ARCHITECTURE = "HOLD_PENDING_ARCHITECTURE"
OBSERVE_ONLY_RUNTIME = "OBSERVE_ONLY_RUNTIME"
BLOCKED_PENDING_GOVERNANCE = "BLOCKED_PENDING_GOVERNANCE"

# --- Operational review priority bands ---

PRIORITY_P0_CRITICAL = "PRIORITY_P0_CRITICAL"
PRIORITY_P1_HIGH = "PRIORITY_P1_HIGH"
PRIORITY_P2_MODERATE = "PRIORITY_P2_MODERATE"
PRIORITY_P3_LOW = "PRIORITY_P3_LOW"

_RISK_ORDER = {RISK_CRITICAL: 0, RISK_HIGH: 1, RISK_MODERATE: 2, RISK_LOW: 3, "": 99}


def _max_escalation_severity_from_gov_row(gov_row: Mapping[str, Any]) -> str:
    best = "INFO"
    order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "WARNING": 3, "INFO": 4}
    for r in gov_row.get("escalation_risks") or []:
        if not isinstance(r, Mapping):
            continue
        sev = str(r.get("escalation_severity") or "INFO")
        if order.get(sev, 99) < order.get(best, 99):
            best = sev
    return best


def classify_governance_decision_posture(
    *,
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    governance_row: Mapping[str, Any],
) -> str:
    """Advisory activation decision label; no enforcement."""
    fam = str(readiness_row.get("workflow_family") or "")
    act = str(readiness_row.get("activation_state") or "")
    cal = str(calibration_row.get("calibration_outcome") or "")
    g_state = str(governance_row.get("activation_governance_state") or "")

    if fam in GOVERNANCE_DEFERRED_FAMILIES or act == DEFERRED_PENDING_ARCHITECTURE:
        return HOLD_PENDING_ARCHITECTURE
    if g_state == GOVERNANCE_BLOCKED:
        return BLOCKED_PENDING_GOVERNANCE
    if act == OBSERVE_ONLY:
        return OBSERVE_ONLY_RUNTIME
    if cal == CALIBRATION_INSUFFICIENT_EVIDENCE or act == NOT_READY:
        return HOLD_PENDING_EVIDENCE
    if act == STABILIZATION_REQUIRED or cal == CALIBRATION_DEGRADED:
        return HOLD_PENDING_EVIDENCE
    if g_state == GOVERNANCE_APPROVAL_READY and cal == CALIBRATION_CONFIRMED:
        return APPROVE_FOR_LIMITED_ACTIVATION
    if g_state in (GOVERNANCE_APPROVAL_CONDITIONAL, GOVERNANCE_REVIEW_RECOMMENDED):
        return APPROVE_WITH_GOVERNANCE_GUARDS
    if g_state == GOVERNANCE_REVIEW_REQUIRED:
        return HOLD_PENDING_EVIDENCE
    return APPROVE_WITH_GOVERNANCE_GUARDS


def derive_operational_priority_band(
    *,
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    governance_row: Mapping[str, Any],
) -> str:
    """Deterministic P0–P3 from existing readiness, calibration, governance rows."""
    risk = str(readiness_row.get("activation_risk_classification") or "")
    cal = str(calibration_row.get("calibration_outcome") or "")
    scores = calibration_row.get("evidence_scores") or {}
    conv = int(scores.get("convergence_visibility_score") or 0) if isinstance(scores, Mapping) else 0
    sig = readiness_row.get("signal_summary") or {}
    fragmented = bool(sig.get("fragmented_orchestration")) if isinstance(sig, Mapping) else False
    rc = str(calibration_row.get("runtime_confidence") or "")
    rb = str(governance_row.get("rollback_readiness") or "")
    drift_cal = bool(calibration_row.get("calibration_drift_detected"))
    drift_gov = bool(governance_row.get("governance_drift_detected"))
    max_es = _max_escalation_severity_from_gov_row(governance_row)
    pri = str(governance_row.get("operational_review_priority") or "P4")

    if risk == RISK_CRITICAL:
        return PRIORITY_P0_CRITICAL
    if cal == CALIBRATION_DEGRADED and max_es in ("CRITICAL", "HIGH"):
        return PRIORITY_P0_CRITICAL
    if drift_gov and max_es in ("CRITICAL", "HIGH"):
        return PRIORITY_P0_CRITICAL
    if fragmented and conv < 40:
        return PRIORITY_P1_HIGH
    if drift_cal and rc == __import__(
        "services.workflow_activation_calibration", fromlist=["LOW_RUNTIME_CONFIDENCE"]
    ).LOW_RUNTIME_CONFIDENCE:
        return PRIORITY_P1_HIGH
    if pri == "P1" or rb in (__import__("services.workflow_activation_governance", fromlist=["ROLLBACK_UNCERTAIN"]).ROLLBACK_UNCERTAIN,):
        if risk in (RISK_HIGH, RISK_CRITICAL) or conv < 50:
            return PRIORITY_P1_HIGH
    if pri == "P1":
        return PRIORITY_P1_HIGH
    if pri == "P2" or cal in (CALIBRATION_UNCERTAIN, CALIBRATION_INSUFFICIENT_EVIDENCE):
        return PRIORITY_P2_MODERATE
    return PRIORITY_P3_LOW


def _reason_readiness(readiness_row: Mapping[str, Any]) -> str:
    act = str(readiness_row.get("activation_state") or "")
    risk = str(readiness_row.get("activation_risk_classification") or "")
    scoped = bool(readiness_row.get("scoped_activation_program"))
    gov_only = bool(readiness_row.get("governance_only"))
    return f"activation_state={act}; activation_risk_classification={risk}; scoped_activation_program={scoped}; governance_only={gov_only}."


def _reason_governance(governance_row: Mapping[str, Any]) -> str:
    g = str(governance_row.get("activation_governance_state") or "")
    conf = str(governance_row.get("governance_confidence") or "")
    posture = str(governance_row.get("operational_approval_posture") or "")
    return f"activation_governance_state={g}; governance_confidence={conf}; operational_approval_posture={posture}."


def _reason_escalation(governance_row: Mapping[str, Any]) -> str:
    codes = sorted(
        str(r.get("code") or "")
        for r in (governance_row.get("escalation_risks") or [])
        if isinstance(r, Mapping)
    )
    mx = _max_escalation_severity_from_gov_row(governance_row)
    return f"max_escalation_severity={mx}; escalation_risk_codes={','.join(codes)}."


def _reason_rollback(governance_row: Mapping[str, Any]) -> str:
    rb = str(governance_row.get("rollback_readiness") or "")
    esc = str(governance_row.get("escalation_readiness") or "")
    return f"rollback_readiness={rb}; escalation_readiness={esc}."


def _reason_runtime_confidence(calibration_row: Mapping[str, Any]) -> str:
    rc = str(calibration_row.get("runtime_confidence") or "")
    drift = bool(calibration_row.get("calibration_drift_detected"))
    return f"runtime_confidence={rc}; calibration_drift_detected={drift}."


def _reason_convergence_visibility(calibration_row: Mapping[str, Any]) -> str:
    scores = calibration_row.get("evidence_scores") or {}
    conv = int(scores.get("convergence_visibility_score") or 0) if isinstance(scores, Mapping) else 0
    cal = str(calibration_row.get("calibration_outcome") or "")
    return f"convergence_visibility_score={conv}; calibration_outcome={cal}."


def _activation_recommendation(decision_posture: str, priority_band: str) -> str:
    return f"decision_posture={decision_posture}; operational_priority_band={priority_band}; advisory_operator_review_required."


def build_convergence_visibility_summary(calibration_snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(calibration_snapshot.get("families") or [])
    by_family: List[Dict[str, Any]] = []
    for r in sorted(rows, key=lambda x: str(x.get("workflow_family") or "")):
        fam = str(r.get("workflow_family") or "")
        sc = r.get("evidence_scores") or {}
        conv = int(sc.get("convergence_visibility_score") or 0) if isinstance(sc, Mapping) else 0
        by_family.append({"workflow_family": fam, "convergence_visibility_score": conv})
    return {
        "schema_version": "convergence_visibility_summary_v1",
        "by_workflow_family": by_family,
        "non_blocking": True,
    }


def _zip_snapshots(
    activation_snapshot: Mapping[str, Any],
    calibration_snapshot: Mapping[str, Any],
    governance_snapshot: Mapping[str, Any],
) -> List[Tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]]:
    def _by_fam(snap: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
        out: Dict[str, Mapping[str, Any]] = {}
        for r in snap.get("families") or []:
            if isinstance(r, Mapping) and r.get("workflow_family"):
                out[str(r["workflow_family"])] = r
        return out

    a = _by_fam(activation_snapshot)
    c = _by_fam(calibration_snapshot)
    g = _by_fam(governance_snapshot)
    keys = sorted(set(a.keys()) & set(c.keys()) & set(g.keys()))
    return [(a[k], c[k], g[k]) for k in keys]


def build_family_activation_report_row(
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    governance_row: Mapping[str, Any],
) -> Dict[str, Any]:
    decision = classify_governance_decision_posture(
        readiness_row=readiness_row,
        calibration_row=calibration_row,
        governance_row=governance_row,
    )
    band = derive_operational_priority_band(
        readiness_row=readiness_row,
        calibration_row=calibration_row,
        governance_row=governance_row,
    )
    row: Dict[str, Any] = {
        "activation_readiness_reason": _reason_readiness(readiness_row),
        "activation_recommendation": _activation_recommendation(decision, band),
        "convergence_visibility_reason": _reason_convergence_visibility(calibration_row),
        "escalation_review_reason": _reason_escalation(governance_row),
        "governance_decision_posture": decision,
        "operational_governance_reason": _reason_governance(governance_row),
        "operational_priority_band": band,
        "rollback_reason": _reason_rollback(governance_row),
        "runtime_confidence_reason": _reason_runtime_confidence(calibration_row),
        "workflow_family": readiness_row.get("workflow_family"),
    }
    # Merge governance + calibration identifiers for operator context (read-only copies)
    for k in (
        "activation_governance_state",
        "approval_blockers",
        "governance_confidence",
        "governance_drift_detected",
        "governance_drift_reason",
        "governance_owner",
        "governance_review_escalation_recommended",
        "operational_review_priority",
        "production_exposure_risk",
        "rollback_readiness",
    ):
        if k in governance_row:
            row[k] = governance_row.get(k)
    for k in (
        "calibration_drift_detected",
        "calibration_drift_reason",
        "calibration_outcome",
        "evidence_gaps",
        "evidence_scores",
        "governance_review_recommended",
        "readiness_activation_state",
        "runtime_confidence",
    ):
        if k in calibration_row:
            row[k] = calibration_row.get(k)
    row["audit_only"] = True
    row["non_blocking"] = True
    return dict(sorted(row.items(), key=lambda kv: str(kv[0])))


def build_report_governance_findings(family_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Report-level counts; deterministic."""
    ready = sum(1 for r in family_rows if r.get("governance_decision_posture") == APPROVE_FOR_LIMITED_ACTIVATION)
    blocked = sum(1 for r in family_rows if r.get("governance_decision_posture") == BLOCKED_PENDING_GOVERNANCE)
    observe = sum(1 for r in family_rows if r.get("governance_decision_posture") == OBSERVE_ONLY_RUNTIME)
    deferred = sum(1 for r in family_rows if r.get("governance_decision_posture") == HOLD_PENDING_ARCHITECTURE)
    high_risk = sum(
        1
        for r in family_rows
        if str(r.get("production_exposure_risk") or "") in (RISK_HIGH, RISK_CRITICAL)
    )
    low_rt = sum(1 for r in family_rows if str(r.get("runtime_confidence") or "") == LOW_RUNTIME_CONFIDENCE)
    drift_n = sum(
        1
        for r in family_rows
        if r.get("governance_drift_detected") or r.get("calibration_drift_detected")
    )
    rb_unc = sum(
        1
        for r in family_rows
        if str(r.get("rollback_readiness") or "") in (ROLLBACK_UNCERTAIN, ROLLBACK_NOT_DEFINED)
    )
    return dict(
        sorted(
            {
                "deferred_architecture_family_count": deferred,
                "drift_detected_family_count": drift_n,
                "governance_blocked_family_count": blocked,
                "governance_ready_family_count": ready,
                "high_risk_family_count": high_risk,
                "low_runtime_confidence_family_count": low_rt,
                "observe_only_family_count": observe,
                "rollback_uncertain_family_count": rb_unc,
            }.items()
        )
    )


def build_workflow_activation_governance_report(
    *,
    generated_at_iso: str,
    convergence_snapshot: Optional[Mapping[str, Any]] = None,
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    queue_visibility: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    reliability_snapshot: Optional[Mapping[str, Any]] = None,
    stabilization_planning: Optional[Mapping[str, Any]] = None,
    families: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    activation_snapshot = build_workflow_activation_operational_snapshot(
        convergence_snapshot=convergence_snapshot,
        transition_traces=transition_traces,
        queue_visibility=queue_visibility,
        reliability_snapshot=reliability_snapshot,
        stabilization_planning=stabilization_planning,
        observability_summary=observability_summary,
        generated_at_iso=generated_at_iso,
        families=families,
    )
    calibration_snapshot = build_workflow_activation_calibration_snapshot(
        activation_operational_snapshot=activation_snapshot,
        generated_at_iso=generated_at_iso,
        convergence_snapshot=convergence_snapshot,
        transition_traces=transition_traces,
        queue_visibility=queue_visibility,
        observability_summary=observability_summary,
        reliability_snapshot=reliability_snapshot,
    )
    governance_snapshot = build_workflow_activation_governance_snapshot(
        activation_operational_snapshot=activation_snapshot,
        generated_at_iso=generated_at_iso,
        convergence_snapshot=convergence_snapshot,
        transition_traces=transition_traces,
        queue_visibility=queue_visibility,
        observability_summary=observability_summary,
        reliability_snapshot=reliability_snapshot,
    )

    triples = _zip_snapshots(activation_snapshot, calibration_snapshot, governance_snapshot)
    family_reports = [
        build_family_activation_report_row(rd, cd, gd) for rd, cd, gd in triples
    ]

    approved_activation_candidates = sorted(
        str(r.get("workflow_family") or "")
        for r in family_reports
        if r.get("governance_decision_posture") == APPROVE_FOR_LIMITED_ACTIVATION
    )
    blocked_activation_candidates = sorted(
        str(r.get("workflow_family") or "")
        for r in family_reports
        if r.get("governance_decision_posture") == BLOCKED_PENDING_GOVERNANCE
    )
    conditional_activation_candidates = sorted(
        str(r.get("workflow_family") or "")
        for r in family_reports
        if r.get("governance_decision_posture") == APPROVE_WITH_GOVERNANCE_GUARDS
    )
    observe_only_candidates = sorted(
        str(r.get("workflow_family") or "")
        for r in family_reports
        if r.get("governance_decision_posture") == OBSERVE_ONLY_RUNTIME
    )
    deferred_architecture_candidates = sorted(
        str(r.get("workflow_family") or "")
        for r in family_reports
        if r.get("governance_decision_posture") == HOLD_PENDING_ARCHITECTURE
    )

    findings = build_report_governance_findings(family_reports)
    risk_detail_high = build_highest_risk_activation_summary(family_reports)
    risk_detail_safe = build_safest_activation_summary(family_reports)
    highest_names = [str(x.get("workflow_family") or "") for x in risk_detail_high]
    safest_names = [str(x.get("workflow_family") or "") for x in risk_detail_safe]

    rt_snap = build_runtime_activation_snapshot(generated_at_iso=generated_at_iso)
    regen_vis = build_regeneration_limited_activation_visibility(generated_at_iso=generated_at_iso)
    rst_bb_vis = build_rst_core_backbone_activation_operational_visibility(generated_at_iso=generated_at_iso)

    report: Dict[str, Any] = {
        "activation_decision_summary": build_activation_decision_summary(family_reports),
        "activation_readiness_summary": build_activation_readiness_summary(activation_snapshot),
        "approved_activation_candidates": approved_activation_candidates,
        "audit_only": True,
        "blocked_activation_candidates": blocked_activation_candidates,
        "calibration_stage_confirmed_candidates": build_confirmed_activation_candidates(calibration_snapshot),
        "conditional_activation_candidates": conditional_activation_candidates,
        "convergence_visibility_summary": build_convergence_visibility_summary(calibration_snapshot),
        "deferred_architecture_candidates": deferred_architecture_candidates,
        "escalation_risk_summary": build_escalation_risk_summary(governance_snapshot),
        "evidence_gap_summary": build_evidence_gap_summary(calibration_snapshot),
        "family_activation_reports": family_reports,
        "generated_at": generated_at_iso,
        "governance_blocked_registry_candidates": build_governance_blocked_candidates(governance_snapshot),
        "governance_drift_summary": build_governance_drift_summary(governance_snapshot),
        "governance_readiness_findings": findings,
        "governance_readiness_overview": build_governance_readiness_overview(findings, family_reports),
        "governance_review_summary": build_governance_review_summary(governance_snapshot),
        "highest_risk_activation_detail": risk_detail_high,
        "highest_risk_activation_families": highest_names,
        "non_blocking": True,
        "observe_only_candidates": observe_only_candidates,
        "operational_approval_summary": build_operational_approval_summary(governance_snapshot),
        "operational_review_priorities": build_operational_review_queue(family_reports),
        "report_version": REPORT_VERSION,
        "regeneration_activation_operational_visibility": regen_vis,
        "requirement_transition_core_backbone_activation_operational_visibility": rst_bb_vis,
        "rollback_posture_summary": build_rollback_posture_summary(governance_snapshot),
        "runtime_activation_rollout_visibility": build_activation_rollout_visibility(rt_snap),
        "runtime_activation_snapshot": rt_snap,
        "runtime_activation_state_summary": build_activation_state_summary(rt_snap),
        "runtime_behavior_changed": False,
        "runtime_calibration_summary": build_calibration_summary(calibration_snapshot),
        "runtime_confidence_summary": build_runtime_confidence_summary(calibration_snapshot),
        "safest_activation_detail": risk_detail_safe,
        "safest_activation_families": safest_names,
    }
    return dict(sorted(report.items(), key=lambda kv: str(kv[0])))


def build_activation_decision_summary(family_reports: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    hist: Dict[str, int] = {}
    for r in family_reports:
        k = str(r.get("governance_decision_posture") or "")
        hist[k] = hist.get(k, 0) + 1
    return {
        "schema_version": "activation_decision_summary_v1",
        "by_governance_decision_posture": dict(sorted(hist.items())),
        "non_blocking": True,
    }


def build_governance_readiness_overview(
    findings: Mapping[str, Any],
    family_reports: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Structured operator signal for controlled activation readiness."""
    p0 = sum(1 for r in family_reports if r.get("operational_priority_band") == PRIORITY_P0_CRITICAL)
    blocked = int(findings.get("governance_blocked_family_count") or 0)
    drift = int(findings.get("drift_detected_family_count") or 0)
    ready = int(findings.get("governance_ready_family_count") or 0)

    if p0 == 0 and blocked == 0 and ready > 0:
        indicator = "INDICATOR_READY_FOR_DISCIPLINED_HUMAN_ACTIVATION_REVIEW"
    elif p0 > 0:
        indicator = "INDICATOR_NOT_READY_CRITICAL_PRIORITY_PRESENT"
    elif blocked > 0 and ready == 0:
        indicator = "INDICATOR_NOT_READY_BLOCKED_OR_DEFERRED_DOMINANT"
    else:
        indicator = "INDICATOR_CONDITIONAL_FURTHER_EVIDENCE_OR_REVIEW_REQUIRED"

    return dict(
        sorted(
            {
                "controlled_activation_readiness_indicator": indicator,
                "governance_ready_family_count": ready,
                "notes": "Advisory_only_no_automatic_activation.",
                "priority_p0_family_count": p0,
                "schema_version": "governance_readiness_overview_v1",
            }.items()
        )
    )


def build_operational_review_queue(family_reports: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    order_band = {
        PRIORITY_P0_CRITICAL: 0,
        PRIORITY_P1_HIGH: 1,
        PRIORITY_P2_MODERATE: 2,
        PRIORITY_P3_LOW: 3,
    }
    rows: List[Dict[str, Any]] = []
    for r in family_reports:
        fam = str(r.get("workflow_family") or "")
        band = str(r.get("operational_priority_band") or PRIORITY_P3_LOW)
        rows.append(
            {
                "governance_decision_posture": r.get("governance_decision_posture"),
                "operational_priority_band": band,
                "production_exposure_risk": r.get("production_exposure_risk"),
                "workflow_family": fam,
            }
        )
    rows.sort(
        key=lambda x: (
            order_band.get(str(x.get("operational_priority_band")), 99),
            _RISK_ORDER.get(str(x.get("production_exposure_risk")), 99),
            str(x.get("workflow_family") or ""),
        )
    )
    return rows


def build_highest_risk_activation_summary(family_reports: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows = [
        {
            "governance_decision_posture": r.get("governance_decision_posture"),
            "operational_priority_band": r.get("operational_priority_band"),
            "production_exposure_risk": r.get("production_exposure_risk"),
            "workflow_family": str(r.get("workflow_family") or ""),
        }
        for r in family_reports
    ]
    rows.sort(
        key=lambda x: (
            _RISK_ORDER.get(str(x.get("production_exposure_risk")), 99),
            str(x.get("workflow_family") or ""),
        )
    )
    return rows


def build_safest_activation_summary(family_reports: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows = [
        {
            "governance_decision_posture": r.get("governance_decision_posture"),
            "operational_priority_band": r.get("operational_priority_band"),
            "production_exposure_risk": r.get("production_exposure_risk"),
            "workflow_family": str(r.get("workflow_family") or ""),
        }
        for r in family_reports
    ]
    rows.sort(
        key=lambda x: (
            -_RISK_ORDER.get(str(x.get("production_exposure_risk")), 99),
            str(x.get("workflow_family") or ""),
        )
    )
    return rows

