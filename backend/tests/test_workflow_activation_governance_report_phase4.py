"""Phase 4: unified activation governance report (mocked snapshots only)."""

from __future__ import annotations

import copy
import json

from services.workflow_activation_readiness import FAMILY_CACHE_INVALIDATION, FAMILY_COMPLIANCE_SCORE_RECALC
from services.workflow_activation_governance_report import (
    PRIORITY_P0_CRITICAL,
    REPORT_VERSION,
    build_activation_decision_summary,
    build_governance_readiness_overview,
    build_highest_risk_activation_summary,
    build_operational_review_queue,
    build_safest_activation_summary,
    build_workflow_activation_governance_report,
)


def _strong_snap_kw():
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


def _strong_kw():
    return dict(generated_at_iso="2026-05-08T14:00:00Z", **_strong_snap_kw())


def test_report_determinism_and_top_level_flags():
    r1 = build_workflow_activation_governance_report(**_strong_kw())
    r2 = build_workflow_activation_governance_report(**_strong_kw())
    assert r1["report_version"] == REPORT_VERSION
    assert r1["runtime_behavior_changed"] is False
    assert r1["audit_only"] is True
    assert r1["non_blocking"] is True
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_section_completeness():
    r = build_workflow_activation_governance_report(**_strong_kw())
    required = (
        "generated_at",
        "report_version",
        "runtime_behavior_changed",
        "audit_only",
        "non_blocking",
        "activation_readiness_summary",
        "runtime_calibration_summary",
        "governance_review_summary",
        "escalation_risk_summary",
        "rollback_posture_summary",
        "governance_drift_summary",
        "convergence_visibility_summary",
        "evidence_gap_summary",
        "approved_activation_candidates",
        "blocked_activation_candidates",
        "conditional_activation_candidates",
        "observe_only_candidates",
        "deferred_architecture_candidates",
        "operational_review_priorities",
        "highest_risk_activation_families",
        "safest_activation_families",
        "highest_risk_activation_detail",
        "safest_activation_detail",
        "operational_approval_summary",
        "activation_decision_summary",
        "governance_readiness_overview",
        "governance_readiness_findings",
        "family_activation_reports",
        "calibration_stage_confirmed_candidates",
        "governance_blocked_registry_candidates",
        "runtime_confidence_summary",
        "runtime_activation_snapshot",
        "runtime_activation_state_summary",
        "runtime_activation_rollout_visibility",
        "regeneration_activation_operational_visibility",
        "requirement_transition_core_backbone_activation_operational_visibility",
    )
    for k in required:
        assert k in r, f"missing {k}"


def test_deferred_family_blocked_and_detail_ordering():
    r = build_workflow_activation_governance_report(
        generated_at_iso="2026-05-08T14:00:00Z",
        families=[FAMILY_CACHE_INVALIDATION],
    )
    assert FAMILY_CACHE_INVALIDATION in r["deferred_architecture_candidates"]
    assert FAMILY_CACHE_INVALIDATION in r["governance_blocked_registry_candidates"]
    fams = [x["workflow_family"] for x in r["highest_risk_activation_detail"]]
    assert fams == sorted(fams)


def test_family_row_decision_and_reasons():
    r = build_workflow_activation_governance_report(**_strong_kw())
    rows = r["family_activation_reports"]
    by_f = {str(x["workflow_family"]): x for x in rows}
    row = by_f[FAMILY_COMPLIANCE_SCORE_RECALC]
    for k in (
        "activation_recommendation",
        "activation_readiness_reason",
        "operational_governance_reason",
        "escalation_review_reason",
        "rollback_reason",
        "runtime_confidence_reason",
        "convergence_visibility_reason",
        "governance_decision_posture",
        "operational_priority_band",
    ):
        assert k in row and isinstance(row[k], str)
    assert row["activation_readiness_reason"].startswith("activation_state=")


def test_governance_findings_counts():
    r = build_workflow_activation_governance_report(**_strong_kw())
    f = r["governance_readiness_findings"]
    for k in (
        "governance_ready_family_count",
        "governance_blocked_family_count",
        "observe_only_family_count",
        "deferred_architecture_family_count",
        "high_risk_family_count",
        "low_runtime_confidence_family_count",
        "drift_detected_family_count",
        "rollback_uncertain_family_count",
    ):
        assert k in f
        assert isinstance(f[k], int)


def test_helpers_on_family_rows():
    r = build_workflow_activation_governance_report(**_strong_kw())
    fr = r["family_activation_reports"]
    q = build_operational_review_queue(fr)
    assert isinstance(q, list) and all("workflow_family" in x for x in q)
    d = build_activation_decision_summary(fr)
    assert "by_governance_decision_posture" in d
    ov = build_governance_readiness_overview(r["governance_readiness_findings"], fr)
    assert "controlled_activation_readiness_indicator" in ov
    hi = build_highest_risk_activation_summary(fr)
    sf = build_safest_activation_summary(fr)
    assert len(hi) == len(sf) == len(fr)


def test_input_snapshots_not_mutated():
    kw = _strong_kw()
    snap = copy.deepcopy(kw["convergence_snapshot"])
    build_workflow_activation_governance_report(**kw)
    assert kw["convergence_snapshot"] == snap


def test_priority_p0_critical_on_critical_risk():
    from services.workflow_activation_governance_report import build_family_activation_report_row, derive_operational_priority_band
    from services.workflow_activation_calibration import build_family_calibration_row
    from services.workflow_activation_governance import build_family_governance_row
    from services.workflow_activation_readiness import build_workflow_activation_operational_snapshot

    act = build_workflow_activation_operational_snapshot(
        generated_at_iso="2026-05-08T14:00:00Z",
        **_strong_snap_kw(),
    )
    rows = {str(r["workflow_family"]): r for r in act["families"]}
    rd = dict(rows[FAMILY_COMPLIANCE_SCORE_RECALC])
    rd["activation_risk_classification"] = "CRITICAL"
    cal = build_family_calibration_row(rd, **_strong_snap_kw())
    gov = build_family_governance_row(rd, cal)
    fr = build_family_activation_report_row(rd, cal, gov)
    band = derive_operational_priority_band(readiness_row=rd, calibration_row=cal, governance_row=gov)
    assert band == PRIORITY_P0_CRITICAL
    assert fr["operational_priority_band"] == PRIORITY_P0_CRITICAL
