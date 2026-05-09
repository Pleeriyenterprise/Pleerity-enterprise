"""
Human operational governance layer for workflow activation (Phase 3).

Read-only, deterministic advisory classifications on top of Phase 1 readiness
and Phase 2 calibration. No enforcement, no automation, no runtime mutations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from services.workflow_activation_calibration import (
    CALIBRATION_BLOCKED,
    CALIBRATION_CONFIRMED,
    CALIBRATION_DEGRADED,
    CALIBRATION_INSUFFICIENT_EVIDENCE,
    CALIBRATION_PARTIAL,
    CALIBRATION_UNCERTAIN,
    GAP_PARTIAL_CONVERGENCE_EVIDENCE,
    GAP_TRUST_SURFACE_DIVERGENCE,
    HIGH_RUNTIME_CONFIDENCE,
    LOW_RUNTIME_CONFIDENCE,
    MODERATE_RUNTIME_CONFIDENCE,
    UNKNOWN_RUNTIME_CONFIDENCE,
    build_family_calibration_row,
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
)

# --- Governance review states (advisory) ---

GOVERNANCE_REVIEW_REQUIRED = "GOVERNANCE_REVIEW_REQUIRED"
GOVERNANCE_REVIEW_RECOMMENDED = "GOVERNANCE_REVIEW_RECOMMENDED"
GOVERNANCE_APPROVAL_READY = "GOVERNANCE_APPROVAL_READY"
GOVERNANCE_APPROVAL_CONDITIONAL = "GOVERNANCE_APPROVAL_CONDITIONAL"
GOVERNANCE_BLOCKED = "GOVERNANCE_BLOCKED"
GOVERNANCE_OBSERVE_ONLY = "GOVERNANCE_OBSERVE_ONLY"

# --- Governance confidence (human + evidence fusion, deterministic) ---

GOVERNANCE_CONFIDENCE_HIGH = "GOVERNANCE_CONFIDENCE_HIGH"
GOVERNANCE_CONFIDENCE_MODERATE = "GOVERNANCE_CONFIDENCE_MODERATE"
GOVERNANCE_CONFIDENCE_LOW = "GOVERNANCE_CONFIDENCE_LOW"
GOVERNANCE_CONFIDENCE_UNKNOWN = "GOVERNANCE_CONFIDENCE_UNKNOWN"

# --- Escalation risk codes ---

ESCALATION_DRIFT_WITHOUT_REVIEW = "DRIFT_WITHOUT_REVIEW"
ESCALATION_DEGRADATION_WITHOUT_ESCALATION = "DEGRADATION_WITHOUT_ESCALATION"
ESCALATION_LOW_RUNTIME_CONFIDENCE_WITH_SAFE_LABEL = "LOW_RUNTIME_CONFIDENCE_WITH_SAFE_LABEL"
ESCALATION_OBSERVABILITY_WITHOUT_OPERATIONS_OWNER = "OBSERVABILITY_WITHOUT_OPERATIONS_OWNER"
ESCALATION_PARTIAL_CONVERGENCE_WITHOUT_REVIEW = "PARTIAL_CONVERGENCE_WITHOUT_REVIEW"
ESCALATION_TRUST_SURFACE_RISK = "TRUST_SURFACE_RISK"
ESCALATION_UNKNOWN_ROLLBACK_POSTURE = "UNKNOWN_ROLLBACK_POSTURE"
ESCALATION_NO_EXPLICIT_ESCALATION_GUIDANCE = "NO_EXPLICIT_ESCALATION_GUIDANCE"
ESCALATION_RECONCILIATION_OPACITY = "RECONCILIATION_OPACITY"

# --- Rollback governance posture (metadata only) ---

ROLLBACK_READY = "ROLLBACK_READY"
ROLLBACK_REQUIRES_REVIEW = "ROLLBACK_REQUIRES_REVIEW"
ROLLBACK_UNCERTAIN = "ROLLBACK_UNCERTAIN"
ROLLBACK_NOT_DEFINED = "ROLLBACK_NOT_DEFINED"

# --- Operational approval posture (human-facing advisory) ---

APPROVAL_POSTURE_HOLD = "HOLD_PENDING_GOVERNANCE_REVIEW"
APPROVAL_POSTURE_CONDITIONAL = "CONDITIONAL_APPROVAL_WITH_DOCUMENTED_GUARDS"
APPROVAL_POSTURE_READY = "READY_FOR_HUMAN_SIGN_OFF"
APPROVAL_POSTURE_OBSERVE = "OBSERVE_ONLY_NO_APPROVAL"
APPROVAL_POSTURE_BLOCKED = "BLOCKED_PENDING_ARCHITECTURE_OR_POLICY"

# --- Escalation readiness rollup ---

ESCALATION_READINESS_CLEAR = "ESCALATION_READINESS_CLEAR"
ESCALATION_READINESS_PARTIAL = "ESCALATION_READINESS_PARTIAL"
ESCALATION_READINESS_UNDEFINED = "ESCALATION_READINESS_UNDEFINED"

def _sorted_family_keys(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    return sorted({str(r.get("workflow_family") or "") for r in rows if r.get("workflow_family")})


def _gap_codes(gaps: Sequence[Mapping[str, Any]]) -> List[str]:
    return sorted(str(g.get("code") or "") for g in gaps if isinstance(g, Mapping) and g.get("code"))


def classify_governance_confidence(
    *,
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    evidence_scores: Mapping[str, int],
) -> str:
    """Deterministic fusion of readiness + calibration + scores; advisory only."""
    fam = str(readiness_row.get("workflow_family") or "")
    act = str(readiness_row.get("activation_state") or "")
    cal = str(calibration_row.get("calibration_outcome") or "")
    rc = str(calibration_row.get("runtime_confidence") or "")

    if fam in GOVERNANCE_DEFERRED_FAMILIES or act == DEFERRED_PENDING_ARCHITECTURE or cal == CALIBRATION_BLOCKED:
        if rc == HIGH_RUNTIME_CONFIDENCE and cal in (CALIBRATION_PARTIAL, CALIBRATION_CONFIRMED):
            return GOVERNANCE_CONFIDENCE_MODERATE
        return GOVERNANCE_CONFIDENCE_UNKNOWN

    vals = list(evidence_scores.values()) if evidence_scores else []
    avg = sum(vals) / len(vals) if vals else 0.0

    if cal == CALIBRATION_CONFIRMED and rc == HIGH_RUNTIME_CONFIDENCE and avg >= 70:
        return GOVERNANCE_CONFIDENCE_HIGH
    if cal in (CALIBRATION_CONFIRMED, CALIBRATION_PARTIAL) and rc in (HIGH_RUNTIME_CONFIDENCE, MODERATE_RUNTIME_CONFIDENCE):
        return GOVERNANCE_CONFIDENCE_MODERATE
    if rc == UNKNOWN_RUNTIME_CONFIDENCE or cal == CALIBRATION_INSUFFICIENT_EVIDENCE:
        return GOVERNANCE_CONFIDENCE_UNKNOWN
    if act == OBSERVE_ONLY and rc == HIGH_RUNTIME_CONFIDENCE:
        return GOVERNANCE_CONFIDENCE_MODERATE
    return GOVERNANCE_CONFIDENCE_LOW


def derive_escalation_risks(
    *,
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    evidence_scores: Mapping[str, int],
) -> List[Dict[str, Any]]:
    risks: List[Dict[str, Any]] = []

    def _r(
        code: str,
        escalation_severity: str,
        operational_impact: str,
        recommended_governance_posture: str,
    ) -> Dict[str, Any]:
        return {
            "code": code,
            "escalation_severity": escalation_severity,
            "operational_impact": operational_impact,
            "recommended_governance_posture": recommended_governance_posture,
        }

    act = str(readiness_row.get("activation_state") or "")
    cal = str(calibration_row.get("calibration_outcome") or "")
    rc = str(calibration_row.get("runtime_confidence") or "")
    drift = bool(calibration_row.get("calibration_drift_detected"))
    review_rec = bool(calibration_row.get("governance_review_recommended"))

    if drift:
        risks.append(
            _r(
                ESCALATION_DRIFT_WITHOUT_REVIEW,
                "MODERATE" if review_rec else "HIGH",
                "Calibration drift vs readiness; governance review alignment varies.",
                "Schedule human activation review; align registry with evidence.",
            )
        )

    if cal == CALIBRATION_DEGRADED or int(evidence_scores.get("degraded_visibility_score") or 0) < 50:
        risks.append(
            _r(
                ESCALATION_DEGRADATION_WITHOUT_ESCALATION,
                "HIGH",
                "Degraded-path or failure dominance visible; escalation path must be explicit.",
                "Define on-call + comms before any activation narrative.",
            )
        )

    if act in (SAFE_FOR_LIMITED_ACTIVATION, SAFE_FOR_INCREMENTAL_EXPANSION) and rc == LOW_RUNTIME_CONFIDENCE:
        risks.append(
            _r(
                ESCALATION_LOW_RUNTIME_CONFIDENCE_WITH_SAFE_LABEL,
                "HIGH",
                "Registry-safe label disagrees with low runtime evidence confidence.",
                "Human review mandatory; do not treat registry alone as approval.",
            )
        )

    owner = str(readiness_row.get("operational_owner") or "").strip().lower()
    if owner in ("", "unknown"):
        risks.append(
            _r(
                ESCALATION_OBSERVABILITY_WITHOUT_OPERATIONS_OWNER,
                "MODERATE",
                "No clear operational owner for escalation routing.",
                "Assign named owner in governance roster before approval.",
            )
        )

    if int(evidence_scores.get("convergence_visibility_score") or 0) < 50 or cal in (
        CALIBRATION_PARTIAL,
        CALIBRATION_UNCERTAIN,
    ):
        if cal != CALIBRATION_CONFIRMED:
            risks.append(
                _r(
                    ESCALATION_PARTIAL_CONVERGENCE_WITHOUT_REVIEW,
                    "MODERATE",
                    "Convergence evidence partial or calibration not confirmed.",
                    "Bounded convergence diagnostic review before sign-off.",
                )
            )

    for g in calibration_row.get("evidence_gaps") or []:
        if isinstance(g, Mapping) and str(g.get("code")) == GAP_TRUST_SURFACE_DIVERGENCE:
            risks.append(
                _r(
                    ESCALATION_TRUST_SURFACE_RISK,
                    "HIGH",
                    "Trust-surface divergence signal in evidence gaps.",
                    "Treat reads and joins as suspect in rollback planning.",
                )
            )
            break

    if int(evidence_scores.get("reconciliation_visibility_score") or 0) < 50:
        risks.append(
            _r(
                ESCALATION_RECONCILIATION_OPACITY,
                "MODERATE",
                "Reconciliation visibility weak in sample.",
                "Pair with gap-sync / reconciliation runbook before production exposure.",
            )
        )

    blockers = [b for b in (readiness_row.get("activation_blockers") or []) if isinstance(b, Mapping)]
    has_rollout_text = any(str(b.get("rollout_recommendation") or "").strip() for b in blockers)
    if blockers and not has_rollout_text:
        risks.append(
            _r(
                ESCALATION_NO_EXPLICIT_ESCALATION_GUIDANCE,
                "INFO",
                "Blockers present without explicit rollout recommendation text.",
                "Add explicit escalation guidance in human runbook.",
            )
        )

    rb = classify_rollback_posture(
        readiness_row=readiness_row,
        calibration_row=calibration_row,
        evidence_scores=evidence_scores,
    )
    if rb == ROLLBACK_UNCERTAIN or rb == ROLLBACK_NOT_DEFINED:
        risks.append(
            _r(
                ESCALATION_UNKNOWN_ROLLBACK_POSTURE,
                "MODERATE",
                "Rollback posture not clearly READY; operational unwind ambiguous.",
                "Document rollback steps and blast radius before approval.",
            )
        )

    return sorted(risks, key=lambda x: (x.get("code") or "", x.get("escalation_severity") or ""))


def classify_rollback_posture(
    *,
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    evidence_scores: Mapping[str, int],
) -> str:
    fam = str(readiness_row.get("workflow_family") or "")
    act = str(readiness_row.get("activation_state") or "")
    cal = str(calibration_row.get("calibration_outcome") or "")

    if fam in GOVERNANCE_DEFERRED_FAMILIES or act == DEFERRED_PENDING_ARCHITECTURE:
        return ROLLBACK_NOT_DEFINED
    if act == NOT_READY or cal == CALIBRATION_INSUFFICIENT_EVIDENCE:
        return ROLLBACK_UNCERTAIN

    conv_ok = int(evidence_scores.get("convergence_visibility_score") or 0) >= 70
    recon_ok = int(evidence_scores.get("reconciliation_visibility_score") or 0) >= 50
    deg_ok = int(evidence_scores.get("degraded_visibility_score") or 0) >= 50
    settle_ok = int(evidence_scores.get("settlement_visibility_score") or 0) >= 50
    risk = str(readiness_row.get("activation_risk_classification") or "")
    complex = risk in (RISK_HIGH, RISK_CRITICAL) or str(readiness_row.get("observability_state") or "") == "GAP"

    if cal in (CALIBRATION_BLOCKED, CALIBRATION_DEGRADED):
        return ROLLBACK_REQUIRES_REVIEW

    if conv_ok and recon_ok and deg_ok and settle_ok and not complex and cal == CALIBRATION_CONFIRMED:
        return ROLLBACK_READY
    if conv_ok and settle_ok and cal in (CALIBRATION_CONFIRMED, CALIBRATION_PARTIAL):
        return ROLLBACK_REQUIRES_REVIEW
    if cal in (CALIBRATION_UNCERTAIN, CALIBRATION_PARTIAL):
        return ROLLBACK_UNCERTAIN
    return ROLLBACK_NOT_DEFINED


def _max_escalation_severity(risks: Sequence[Mapping[str, Any]]) -> str:
    best = "INFO"
    order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "WARNING": 3, "INFO": 4}
    for r in risks:
        sev = str(r.get("escalation_severity") or "INFO")
        if order.get(sev, 99) < order.get(best, 99):
            best = sev
    return best


def classify_escalation_readiness(risks: Sequence[Mapping[str, Any]]) -> str:
    mx = _max_escalation_severity(risks)
    if mx in ("CRITICAL", "HIGH"):
        return ESCALATION_READINESS_UNDEFINED
    if mx in ("MODERATE", "WARNING"):
        return ESCALATION_READINESS_PARTIAL
    return ESCALATION_READINESS_CLEAR


def _operational_review_priority(
    *,
    governance_confidence: str,
    calibration_outcome: str,
    max_escalation: str,
) -> str:
    if max_escalation in ("CRITICAL", "HIGH"):
        return "P1"
    if calibration_outcome in (CALIBRATION_DEGRADED, CALIBRATION_BLOCKED):
        return "P1"
    if governance_confidence == GOVERNANCE_CONFIDENCE_LOW:
        return "P2"
    if calibration_outcome in (CALIBRATION_UNCERTAIN, CALIBRATION_INSUFFICIENT_EVIDENCE):
        return "P2"
    if max_escalation == "MODERATE":
        return "P3"
    return "P4"


def _production_exposure_risk(readiness_row: Mapping[str, Any], calibration_row: Mapping[str, Any]) -> str:
    base = str(readiness_row.get("activation_risk_classification") or RISK_MODERATE)
    cal = str(calibration_row.get("calibration_outcome") or "")
    if cal in (CALIBRATION_DEGRADED, CALIBRATION_BLOCKED):
        if base == RISK_LOW:
            return RISK_MODERATE
        if base == RISK_MODERATE:
            return RISK_HIGH
        return RISK_CRITICAL
    if cal == CALIBRATION_INSUFFICIENT_EVIDENCE and base == RISK_LOW:
        return RISK_MODERATE
    return base


def _approval_blockers(
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    governance_state: str,
    risks: Sequence[Mapping[str, Any]],
) -> List[str]:
    out: List[str] = []
    for b in readiness_row.get("activation_blockers") or []:
        if isinstance(b, Mapping) and b.get("code"):
            out.append(str(b["code"]))
    if calibration_row.get("calibration_outcome") not in (CALIBRATION_CONFIRMED,):
        out.append(f"calibration:{calibration_row.get('calibration_outcome')}")
    if governance_state in (GOVERNANCE_BLOCKED, GOVERNANCE_REVIEW_REQUIRED):
        out.append(f"governance_state:{governance_state}")
    for r in risks:
        if str(r.get("escalation_severity")) in ("CRITICAL", "HIGH"):
            out.append(f"escalation:{r.get('code')}")
    return sorted(set(out))


def classify_activation_governance_review_state(
    *,
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    governance_confidence: str,
    risks: Sequence[Mapping[str, Any]],
) -> str:
    fam = str(readiness_row.get("workflow_family") or "")
    act = str(readiness_row.get("activation_state") or "")
    cal = str(calibration_row.get("calibration_outcome") or "")

    if fam in GOVERNANCE_DEFERRED_FAMILIES or act == DEFERRED_PENDING_ARCHITECTURE or cal == CALIBRATION_BLOCKED:
        return GOVERNANCE_BLOCKED

    if act == OBSERVE_ONLY and cal not in (CALIBRATION_CONFIRMED, CALIBRATION_PARTIAL):
        return GOVERNANCE_OBSERVE_ONLY

    if act == OBSERVE_ONLY:
        return GOVERNANCE_REVIEW_RECOMMENDED

    if act in (STABILIZATION_REQUIRED, NOT_READY):
        return GOVERNANCE_REVIEW_REQUIRED

    max_es = _max_escalation_severity(risks)
    if act in (SAFE_FOR_LIMITED_ACTIVATION, SAFE_FOR_INCREMENTAL_EXPANSION):
        if cal != CALIBRATION_CONFIRMED or governance_confidence in (
            GOVERNANCE_CONFIDENCE_LOW,
            GOVERNANCE_CONFIDENCE_UNKNOWN,
        ):
            return GOVERNANCE_REVIEW_REQUIRED
        if max_es in ("CRITICAL", "HIGH"):
            return GOVERNANCE_REVIEW_REQUIRED
        if max_es == "MODERATE" or calibration_row.get("calibration_drift_detected"):
            return GOVERNANCE_REVIEW_RECOMMENDED
        if cal == CALIBRATION_CONFIRMED and governance_confidence == GOVERNANCE_CONFIDENCE_HIGH:
            return GOVERNANCE_APPROVAL_READY
        return GOVERNANCE_APPROVAL_CONDITIONAL

    if cal == CALIBRATION_CONFIRMED and governance_confidence == GOVERNANCE_CONFIDENCE_HIGH:
        return GOVERNANCE_APPROVAL_CONDITIONAL
    return GOVERNANCE_REVIEW_RECOMMENDED


def classify_operational_approval_posture(governance_state: str) -> str:
    if governance_state == GOVERNANCE_APPROVAL_READY:
        return APPROVAL_POSTURE_READY
    if governance_state == GOVERNANCE_APPROVAL_CONDITIONAL:
        return APPROVAL_POSTURE_CONDITIONAL
    if governance_state == GOVERNANCE_BLOCKED:
        return APPROVAL_POSTURE_BLOCKED
    if governance_state == GOVERNANCE_OBSERVE_ONLY:
        return APPROVAL_POSTURE_OBSERVE
    if governance_state == GOVERNANCE_REVIEW_REQUIRED:
        return APPROVAL_POSTURE_HOLD
    return APPROVAL_POSTURE_CONDITIONAL


def _operational_review_recommendation(
    governance_state: str,
    rollback: str,
    calibration_outcome: str,
) -> str:
    return (
        f"governance_state={governance_state}; rollback_posture={rollback}; "
        f"calibration_outcome={calibration_outcome}; advisory_human_review_only."
    )


def analyze_governance_drift(
    *,
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
    governance_confidence: str,
    activation_governance_state: str,
) -> Tuple[bool, str, bool]:
    """(governance_drift_detected, governance_drift_reason, governance_review_escalation_recommended)."""
    act = str(readiness_row.get("activation_state") or "")
    cal = str(calibration_row.get("calibration_outcome") or "")
    rc = str(calibration_row.get("runtime_confidence") or "")

    if act in (SAFE_FOR_LIMITED_ACTIVATION, SAFE_FOR_INCREMENTAL_EXPANSION):
        if governance_confidence in (GOVERNANCE_CONFIDENCE_LOW, GOVERNANCE_CONFIDENCE_UNKNOWN):
            return (
                True,
                "safe_activation_assumption_with_low_governance_confidence",
                True,
            )

    if rc == HIGH_RUNTIME_CONFIDENCE and activation_governance_state == GOVERNANCE_BLOCKED:
        return (
            True,
            "high_runtime_evidence_with_blocked_governance_posture",
            True,
        )

    if cal == CALIBRATION_CONFIRMED and activation_governance_state in (
        GOVERNANCE_REVIEW_REQUIRED,
        GOVERNANCE_BLOCKED,
    ):
        return (
            True,
            "calibration_confirmed_but_human_governance_gate_not_cleared",
            True,
        )

    if act == OBSERVE_ONLY and rc == HIGH_RUNTIME_CONFIDENCE and cal in (CALIBRATION_CONFIRMED, CALIBRATION_PARTIAL):
        return (
            True,
            "observe_only_registry_with_strong_runtime_evidence_governance_review_candidate",
            True,
        )

    return False, "", False


def build_family_governance_row(
    readiness_row: Mapping[str, Any],
    calibration_row: Mapping[str, Any],
) -> Dict[str, Any]:
    """Single-family governance projection from readiness + calibration rows (read-only)."""
    scores = dict(calibration_row.get("evidence_scores") or {})
    scores = dict(sorted(scores.items()))

    risks = derive_escalation_risks(
        readiness_row=readiness_row,
        calibration_row=calibration_row,
        evidence_scores=scores,
    )
    max_es = _max_escalation_severity(risks)

    gov_conf = classify_governance_confidence(
        readiness_row=readiness_row,
        calibration_row=calibration_row,
        evidence_scores=scores,
    )
    g_state = classify_activation_governance_review_state(
        readiness_row=readiness_row,
        calibration_row=calibration_row,
        governance_confidence=gov_conf,
        risks=risks,
    )

    rollback = classify_rollback_posture(
        readiness_row=readiness_row,
        calibration_row=calibration_row,
        evidence_scores=scores,
    )
    esc_read = classify_escalation_readiness(risks)
    pri = _operational_review_priority(
        governance_confidence=gov_conf,
        calibration_outcome=str(calibration_row.get("calibration_outcome") or ""),
        max_escalation=max_es,
    )
    prod_risk = _production_exposure_risk(readiness_row, calibration_row)
    owner = str(readiness_row.get("operational_owner") or "").strip() or "platform_governance"
    blockers = _approval_blockers(readiness_row, calibration_row, g_state, risks)
    posture = classify_operational_approval_posture(g_state)
    rec = _operational_review_recommendation(
        g_state,
        rollback,
        str(calibration_row.get("calibration_outcome") or ""),
    )

    g_drift, g_reason, g_esc = analyze_governance_drift(
        readiness_row=readiness_row,
        calibration_row=calibration_row,
        governance_confidence=gov_conf,
        activation_governance_state=g_state,
    )

    row: Dict[str, Any] = {
        "workflow_family": readiness_row.get("workflow_family"),
        "operational_approval_posture": posture,
        "activation_governance_state": g_state,
        "governance_confidence": gov_conf,
        "rollback_readiness": rollback,
        "escalation_readiness": esc_read,
        "operational_review_priority": pri,
        "production_exposure_risk": prod_risk,
        "governance_owner": owner,
        "approval_blockers": blockers,
        "operational_review_recommendation": rec,
        "escalation_risks": risks,
        "governance_drift_detected": g_drift,
        "governance_drift_reason": g_reason or None,
        "governance_review_escalation_recommended": g_esc,
        "calibration_outcome": calibration_row.get("calibration_outcome"),
        "readiness_activation_state": readiness_row.get("activation_state"),
        "runtime_confidence": calibration_row.get("runtime_confidence"),
        "non_blocking": True,
        "audit_only": True,
    }
    return dict(sorted(row.items(), key=lambda kv: str(kv[0])))


def build_workflow_activation_governance_snapshot(
    *,
    activation_operational_snapshot: Mapping[str, Any],
    generated_at_iso: str,
    convergence_snapshot: Optional[Mapping[str, Any]] = None,
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    queue_visibility: Optional[Mapping[str, Any]] = None,
    observability_summary: Optional[Mapping[str, Any]] = None,
    reliability_snapshot: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build governance rows by reusing Phase 2 calibration on each readiness row.
    Deterministic family ordering.
    """
    rows_in = list(activation_operational_snapshot.get("families") or [])
    fams = _sorted_family_keys(rows_in)
    out_rows: List[Dict[str, Any]] = []
    for fam in fams:
        readiness_row = next((r for r in rows_in if str(r.get("workflow_family")) == fam), None)
        if not isinstance(readiness_row, Mapping):
            continue
        cal = build_family_calibration_row(
            readiness_row,
            convergence_snapshot=convergence_snapshot,
            transition_traces=transition_traces,
            queue_visibility=queue_visibility,
            observability_summary=observability_summary,
            reliability_snapshot=reliability_snapshot,
        )
        out_rows.append(build_family_governance_row(readiness_row, cal))
    return {
        "schema_version": "workflow_activation_governance_snapshot_v1",
        "generated_at_iso": generated_at_iso,
        "families": out_rows,
        "non_blocking": True,
        "audit_only": True,
    }


def build_governance_review_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    hist: Dict[str, int] = {}
    for r in rows:
        k = str(r.get("activation_governance_state") or "")
        hist[k] = hist.get(k, 0) + 1
    return {
        "schema_version": "governance_review_summary_v1",
        "by_activation_governance_state": dict(sorted(hist.items())),
        "non_blocking": True,
    }


def build_operational_approval_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    hist: Dict[str, int] = {}
    for r in rows:
        k = str(r.get("operational_approval_posture") or "")
        hist[k] = hist.get(k, 0) + 1
    return {
        "schema_version": "operational_approval_summary_v1",
        "by_operational_approval_posture": dict(sorted(hist.items())),
        "non_blocking": True,
    }


def build_governance_drift_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    n = sum(1 for r in rows if r.get("governance_drift_detected"))
    reasons: Dict[str, int] = {}
    for r in rows:
        if r.get("governance_drift_detected") and r.get("governance_drift_reason"):
            rr = str(r.get("governance_drift_reason"))
            reasons[rr] = reasons.get(rr, 0) + 1
    esc = sum(1 for r in rows if r.get("governance_review_escalation_recommended"))
    return {
        "schema_version": "governance_drift_summary_v1",
        "governance_drift_detected_count": n,
        "by_governance_drift_reason": dict(sorted(reasons.items())),
        "governance_review_escalation_recommended_count": esc,
        "non_blocking": True,
    }


def build_escalation_risk_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    by_code: Dict[str, int] = {}
    for r in rows:
        for er in r.get("escalation_risks") or []:
            if isinstance(er, Mapping) and er.get("code"):
                c = str(er["code"])
                by_code[c] = by_code.get(c, 0) + 1
    return {
        "schema_version": "escalation_risk_summary_v1",
        "by_escalation_risk_code": dict(sorted(by_code.items())),
        "non_blocking": True,
    }


def build_rollback_posture_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    hist: Dict[str, int] = {}
    for r in rows:
        k = str(r.get("rollback_readiness") or "")
        hist[k] = hist.get(k, 0) + 1
    return {
        "schema_version": "rollback_posture_summary_v1",
        "by_rollback_readiness": dict(sorted(hist.items())),
        "non_blocking": True,
    }


def build_governance_approved_candidates(snapshot: Mapping[str, Any]) -> List[str]:
    rows = list(snapshot.get("families") or [])
    return sorted(
        str(r.get("workflow_family") or "")
        for r in rows
        if r.get("activation_governance_state") == GOVERNANCE_APPROVAL_READY
    )


def build_governance_blocked_candidates(snapshot: Mapping[str, Any]) -> List[str]:
    rows = list(snapshot.get("families") or [])
    return sorted(
        str(r.get("workflow_family") or "")
        for r in rows
        if r.get("activation_governance_state") == GOVERNANCE_BLOCKED
    )
