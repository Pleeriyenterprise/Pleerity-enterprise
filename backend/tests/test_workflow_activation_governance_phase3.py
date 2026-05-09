"""Phase 3: workflow activation governance (human layer, mocked only)."""

from __future__ import annotations

import json

from services.workflow_activation_readiness import (
    FAMILY_CACHE_INVALIDATION,
    FAMILY_COMPLIANCE_SCORE_RECALC,
    build_workflow_activation_operational_snapshot,
    merge_readiness_row_with_signals,
)
from services.workflow_activation_calibration import build_family_calibration_row
from services.workflow_activation_governance import (
    GOVERNANCE_APPROVAL_READY,
    GOVERNANCE_BLOCKED,
    GOVERNANCE_OBSERVE_ONLY,
    GOVERNANCE_REVIEW_RECOMMENDED,
    GOVERNANCE_REVIEW_REQUIRED,
    GOVERNANCE_CONFIDENCE_HIGH,
    GOVERNANCE_CONFIDENCE_LOW,
    ROLLBACK_READY,
    ROLLBACK_REQUIRES_REVIEW,
    ROLLBACK_NOT_DEFINED,
    ROLLBACK_UNCERTAIN,
    ESCALATION_LOW_RUNTIME_CONFIDENCE_WITH_SAFE_LABEL,
    ESCALATION_RECONCILIATION_OPACITY,
    analyze_governance_drift,
    build_escalation_risk_summary,
    build_family_governance_row,
    build_governance_blocked_candidates,
    build_governance_approved_candidates,
    build_governance_drift_summary,
    build_governance_review_summary,
    build_operational_approval_summary,
    build_rollback_posture_summary,
    build_workflow_activation_governance_snapshot,
    classify_rollback_posture,
    derive_escalation_risks,
)


def _strong_inputs():
    return dict(
        convergence_snapshot={
            "convergence_evidence_matrix": {
                "matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}],
            },
            "joined_rows": [],
        },
        transition_traces=[
            {"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED", "degraded_possible": True}]}
        ],
        queue_visibility={"diagnostics": {"skipped_unbounded_scan": False, "returned_count": 2}},
        observability_summary={
            "reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}
        },
    )


def _readiness_and_cal():
    kw = _strong_inputs()
    row = merge_readiness_row_with_signals(FAMILY_COMPLIANCE_SCORE_RECALC, **kw)
    cal = build_family_calibration_row(row, **kw)
    return row, cal


def test_governance_classifications_and_snapshot_ordering():
    act = build_workflow_activation_operational_snapshot(generated_at_iso="2026-05-08T12:00:00Z", **_strong_inputs())
    snap = build_workflow_activation_governance_snapshot(
        activation_operational_snapshot=act,
        generated_at_iso="2026-05-08T12:00:00Z",
        **_strong_inputs(),
    )
    fams = [r["workflow_family"] for r in snap["families"]]
    assert fams == sorted(fams)
    gr = build_governance_review_summary(snap)
    oa = build_operational_approval_summary(snap)
    assert "by_activation_governance_state" in gr
    assert "by_operational_approval_posture" in oa
    json.dumps(snap, sort_keys=True)


def test_approval_ready_candidate_strong_evidence():
    row, cal = _readiness_and_cal()
    gov = build_family_governance_row(row, cal)
    assert gov.get("activation_governance_state") in (
        GOVERNANCE_APPROVAL_READY,
        GOVERNANCE_REVIEW_RECOMMENDED,
    )
    if gov.get("activation_governance_state") == GOVERNANCE_APPROVAL_READY:
        assert gov.get("governance_confidence") == GOVERNANCE_CONFIDENCE_HIGH
        assert gov.get("rollback_readiness") == ROLLBACK_READY


def test_governance_blocked_deferred_family():
    act = build_workflow_activation_operational_snapshot(
        generated_at_iso="2026-05-08T12:00:00Z",
        families=[FAMILY_CACHE_INVALIDATION],
    )
    snap = build_workflow_activation_governance_snapshot(
        activation_operational_snapshot=act,
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    row = snap["families"][0]
    assert row["activation_governance_state"] == GOVERNANCE_BLOCKED
    blocked = build_governance_blocked_candidates(snap)
    assert FAMILY_CACHE_INVALIDATION in blocked
    approved = build_governance_approved_candidates(snap)
    assert FAMILY_CACHE_INVALIDATION not in approved


def test_escalation_low_runtime_safe_label():
    row = merge_readiness_row_with_signals(
        FAMILY_COMPLIANCE_SCORE_RECALC,
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": []}},
        transition_traces=[],
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {}}},
    )
    row = dict(row)
    row["activation_state"] = "SAFE_FOR_LIMITED_ACTIVATION"
    cal = build_family_calibration_row(row, transition_traces=[], queue_visibility={})
    scores = dict(cal["evidence_scores"])
    risks = derive_escalation_risks(readiness_row=row, calibration_row=cal, evidence_scores=scores)
    codes = [r["code"] for r in risks]
    if cal.get("runtime_confidence") == __import__(
        "services.workflow_activation_calibration", fromlist=["LOW_RUNTIME_CONFIDENCE"]
    ).LOW_RUNTIME_CONFIDENCE:
        assert ESCALATION_LOW_RUNTIME_CONFIDENCE_WITH_SAFE_LABEL in codes


def test_recon_opacity_escalation():
    row, cal_full = _readiness_and_cal()
    cal = dict(cal_full)
    cal["evidence_scores"] = dict(cal["evidence_scores"])
    cal["evidence_scores"]["reconciliation_visibility_score"] = 20
    risks = derive_escalation_risks(readiness_row=row, calibration_row=cal, evidence_scores=cal["evidence_scores"])
    assert any(r["code"] == ESCALATION_RECONCILIATION_OPACITY for r in risks)


def test_rollback_posture_requires_review_when_calibration_degraded():
    row, _ = _readiness_and_cal()
    cal = dict(_)
    cal["calibration_outcome"] = __import__(
        "services.workflow_activation_calibration", fromlist=["CALIBRATION_DEGRADED"]
    ).CALIBRATION_DEGRADED
    rb = classify_rollback_posture(
        readiness_row=row,
        calibration_row=cal,
        evidence_scores=cal.get("evidence_scores") or {},
    )
    assert rb == ROLLBACK_REQUIRES_REVIEW


def test_governance_drift_safe_low_confidence():
    row, cal = _readiness_and_cal()
    row = dict(row)
    row["activation_state"] = "SAFE_FOR_LIMITED_ACTIVATION"
    cal = dict(cal)
    cal["runtime_confidence"] = __import__(
        "services.workflow_activation_calibration", fromlist=["LOW_RUNTIME_CONFIDENCE"]
    ).LOW_RUNTIME_CONFIDENCE
    drift, reason, esc = analyze_governance_drift(
        readiness_row=row,
        calibration_row=cal,
        governance_confidence=GOVERNANCE_CONFIDENCE_LOW,
        activation_governance_state=GOVERNANCE_REVIEW_REQUIRED,
    )
    assert drift is True
    assert reason
    assert esc is True


def test_summaries_and_candidates_deterministic():
    act = build_workflow_activation_operational_snapshot(generated_at_iso="2026-05-08T12:00:00Z", **_strong_inputs())
    s1 = build_workflow_activation_governance_snapshot(
        activation_operational_snapshot=act,
        generated_at_iso="2026-05-08T12:00:00Z",
        **_strong_inputs(),
    )
    s2 = build_workflow_activation_governance_snapshot(
        activation_operational_snapshot=act,
        generated_at_iso="2026-05-08T12:00:00Z",
        **_strong_inputs(),
    )
    assert s1["families"] == s2["families"]
    d1 = build_governance_drift_summary(s1)
    d2 = build_governance_drift_summary(s2)
    assert d1 == d2
    e1 = build_escalation_risk_summary(s1)
    e2 = build_escalation_risk_summary(s2)
    assert e1 == e2
    r1 = build_rollback_posture_summary(s1)
    r2 = build_rollback_posture_summary(s2)
    assert r1 == r2


def test_observe_only_governance_state():
    row = merge_readiness_row_with_signals(
        FAMILY_COMPLIANCE_SCORE_RECALC,
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": []}},
        transition_traces=[],
    )
    row = dict(row)
    row["activation_state"] = "OBSERVE_ONLY"
    cal = build_family_calibration_row(row, transition_traces=[], queue_visibility={})
    gov = build_family_governance_row(row, cal)
    assert gov["activation_governance_state"] in (GOVERNANCE_OBSERVE_ONLY, GOVERNANCE_REVIEW_RECOMMENDED)


def test_rollback_uncertain_insufficient_evidence():
    row = merge_readiness_row_with_signals(FAMILY_COMPLIANCE_SCORE_RECALC)
    cal = build_family_calibration_row(row)
    rb = classify_rollback_posture(
        readiness_row=row,
        calibration_row=cal,
        evidence_scores=dict(cal.get("evidence_scores") or {}),
    )
    assert rb in (ROLLBACK_UNCERTAIN, ROLLBACK_REQUIRES_REVIEW, ROLLBACK_NOT_DEFINED)
