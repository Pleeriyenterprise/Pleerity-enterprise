"""Phase 1C: staging evidence pack (mocked staging-shaped inputs; no DB)."""

from __future__ import annotations

import json
from pathlib import Path

import services.workflow_runtime_activation_registry as reg
from services.workflow_activation_readiness import FAMILY_COMPLIANCE_SCORE_RECALC
from services.workflow_activation_governance_report import build_workflow_activation_governance_report
from services.workflow_runtime_activation_evidence_pack import (
    EVIDENCE_PACK_VERSION,
    HIGH_STAGING_DRIFT,
    HOLD_PENDING_MORE_RUNTIME_EVIDENCE,
    LOW_STAGING_DRIFT,
    MODERATE_STAGING_DRIFT,
    READY_FOR_CONTINUED_LIMITED_ACTIVATION,
    READY_FOR_INCREMENTAL_EXPANSION_REVIEW,
    REPRESENTATIVE_EVIDENCE_CONFIRMED,
    REPRESENTATIVE_EVIDENCE_INSUFFICIENT,
    build_activation_evidence_summary,
    build_runtime_activation_evidence_pack,
    classify_representative_evidence,
    classify_staging_drift,
    derive_readiness_conclusion,
    normalize_runtime_activation_evidence_pack,
    write_runtime_activation_evidence_pack,
)
from services.workflow_runtime_activation_registry import (
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    GUARD_RESULT_PERMITTED,
    resolve_compliance_recalc_activation_gate,
)
from services.workflow_runtime_activation_validation import LOW_VALIDATION_DRIFT


def _gate_limited():
    return resolve_compliance_recalc_activation_gate()


def _trace_with_recalc_row(*, tid: str, cid: str, outcome: str, activation: bool) -> dict:
    row = {
        "degraded_possible": False,
        "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
        "enqueue_outcome": outcome,
        "enqueue_succeeded": outcome == "ENQUEUE_ACCEPTED",
        "propagation_stage": "test",
        "trigger_mode": "async_queue",
    }
    if activation:
        row["activation_family"] = FAMILY_COMPLIANCE_SCORE_RECALC
        row["activation_governance_version"] = ACTIVATION_GOVERNANCE_VERSION
        row["activation_guard_result"] = GUARD_RESULT_PERMITTED
        row["activation_reason"] = "registry_allows_limited_compliance_score_recalc_enqueue"
        row["activation_scope"] = "compliance_recalc_enqueue_only"
        row["activation_state"] = ACTIVATION_LIMITED
    return {
        "correlation_id": cid,
        "downstream_trigger_targets": [row],
        "transition_id": tid,
    }


def _enqueue_sample(*, enqueued: bool, cid: str, skipped: bool):
    g = _gate_limited()
    body = {
        "activation_family": g["activation_family"],
        "activation_governance_version": g["activation_governance_version"],
        "activation_guard_result": g["activation_guard_result"],
        "activation_reason": g["activation_reason"],
        "activation_scope": g["activation_scope"],
        "activation_skipped": skipped,
        "activation_state": g["activation_state"],
        "correlation_id": cid,
        "enqueued": enqueued,
        "regeneration_requeued": True,
        "regeneration_error": None,
    }
    return {"enqueue": body, "gate": g}


def _staging_inputs():
    t1 = _trace_with_recalc_row(tid="t1", cid="c1", outcome="ENQUEUE_ACCEPTED", activation=True)
    t2 = _trace_with_recalc_row(tid="t2", cid="c2", outcome="ENQUEUE_DUPLICATE_SUPPRESSED", activation=True)
    t2["downstream_trigger_targets"][0]["duplicate_suppression_reason"] = "dedupe"
    samples = [
        _enqueue_sample(enqueued=True, cid="e1", skipped=False),
    ]
    return {
        "generated_at": "2026-05-10T10:00:00Z",
        "governance_families": (FAMILY_COMPLIANCE_SCORE_RECALC,),
        "observability_summary": {"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
        "queue_visibility": {"diagnostics": {"returned_count": 3, "skipped_unbounded_scan": False}},
        "representative_enqueue_samples": samples,
        "transition_traces": (t1, t2),
    }


def test_evidence_pack_determinism_and_keys():
    kw = _staging_inputs()
    p1 = build_runtime_activation_evidence_pack(**kw)
    p2 = build_runtime_activation_evidence_pack(**kw)
    assert json.dumps(normalize_runtime_activation_evidence_pack(p1), sort_keys=True) == json.dumps(
        normalize_runtime_activation_evidence_pack(p2), sort_keys=True
    )
    for key in (
        "generated_at",
        "evidence_pack_version",
        "activation_family",
        "activation_state",
        "activation_governance_version",
        "runtime_behavior_changed",
        "audit_only",
        "non_blocking",
        "runtime_activation_snapshot",
        "activation_validation_snapshot",
        "governance_report_summary",
        "convergence_visibility_summary",
        "queue_visibility_summary",
        "runtime_confidence_summary",
        "rollback_validation_summary",
        "observability_validation_summary",
        "drift_validation_summary",
        "representative_transition_samples",
        "representative_enqueue_samples",
        "representative_downstream_samples",
        "representative_regeneration_enqueue_samples",
        "activation_operational_findings",
        "convergence_evidence_snapshot",
        "runtime_activation_rollout_visibility",
        "staging_drift_classification",
        "staging_drift_findings",
        "readiness_conclusion_block",
    ):
        assert key in p1, f"missing {key}"
    assert p1["evidence_pack_version"] == EVIDENCE_PACK_VERSION
    assert p1["audit_only"] is True and p1["non_blocking"] is True and p1["runtime_behavior_changed"] is False


def test_representative_classification():
    kw = _staging_inputs()
    pack = build_runtime_activation_evidence_pack(**kw)
    conv = pack["convergence_evidence_snapshot"]
    traces = list(kw["transition_traces"])
    samples = list(kw["representative_enqueue_samples"])
    gov_full = build_workflow_activation_governance_report(
        generated_at_iso=kw["generated_at"],
        convergence_snapshot=conv,
        transition_traces=traces,
        queue_visibility=kw["queue_visibility"],
        observability_summary=kw["observability_summary"],
    )
    assert (
        classify_representative_evidence(
            transition_traces=traces,
            representative_enqueue_samples=samples,
            governance_report=gov_full,
            convergence_snapshot=conv,
        )
        == REPRESENTATIVE_EVIDENCE_CONFIRMED
    )
    assert (
        classify_representative_evidence(
            transition_traces=[],
            representative_enqueue_samples=[],
            governance_report={"report_version": "x"},
            convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": []}},
        )
        == REPRESENTATIVE_EVIDENCE_INSUFFICIENT
    )


def test_readiness_and_staging_drift_strong_pack():
    pack = build_runtime_activation_evidence_pack(**_staging_inputs())
    assert pack["representative_evidence_classification"] == REPRESENTATIVE_EVIDENCE_CONFIRMED
    assert pack["readiness_conclusion_block"]["readiness_conclusion"] in (
        READY_FOR_CONTINUED_LIMITED_ACTIVATION,
        READY_FOR_INCREMENTAL_EXPANSION_REVIEW,
    )
    assert pack["staging_drift_classification"] in (LOW_STAGING_DRIFT, MODERATE_STAGING_DRIFT)


def test_runtime_consistency_derivation():
    pack = build_runtime_activation_evidence_pack(**_staging_inputs())
    c = pack["runtime_consistency_findings"]
    assert c["activation_runtime_consistency"] == "CONSISTENT"
    assert c["schema_version"] == "activation_runtime_consistency_v1"


def test_normalize_export_roundtrip(tmp_path: Path):
    pack = build_runtime_activation_evidence_pack(**_staging_inputs())
    path = tmp_path / "evidence_pack.json"
    written = write_runtime_activation_evidence_pack(path, pack)
    assert Path(written).is_file()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == normalize_runtime_activation_evidence_pack(pack)


def test_activation_evidence_summary():
    pack = build_runtime_activation_evidence_pack(**_staging_inputs())
    s = build_activation_evidence_summary(pack)
    assert s["schema_version"] == "activation_evidence_summary_v1"
    assert s["evidence_pack_version"] == EVIDENCE_PACK_VERSION


def test_classify_staging_drift_escalation_from_governance():
    drift_summary = {"drift_classification": LOW_VALIDATION_DRIFT, "finding_codes": []}
    gov_summary = {
        "governance_drift_summary": {
            "governance_drift_detected_count": 5,
            "governance_review_escalation_recommended_count": 0,
            "schema_version": "governance_drift_summary_v1",
        }
    }
    conv = {"convergence_evidence_matrix": {"matrix_rows": [{"workflow_family": "x"}]}}
    sd = classify_staging_drift(
        drift_validation_summary=drift_summary,
        governance_report_summary=gov_summary,
        convergence_snapshot=conv,
    )
    assert sd == HIGH_STAGING_DRIFT


def test_readiness_hold_when_insufficient():
    rc = derive_readiness_conclusion(
        representative_evidence_class=REPRESENTATIVE_EVIDENCE_INSUFFICIENT,
        staging_drift_classification=LOW_STAGING_DRIFT,
        validation_overall="VALIDATION_CONFIRMED",
        governance_report_summary={"governance_drift_summary": {"governance_drift_detected_count": 0}},
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": []}},
    )
    assert rc["readiness_conclusion"] == HOLD_PENDING_MORE_RUNTIME_EVIDENCE


def test_pack_with_explicit_governance_report():
    gov = build_workflow_activation_governance_report(
        generated_at_iso="2026-05-10T11:00:00Z",
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=[{"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED"}]}],
        queue_visibility={"diagnostics": {"returned_count": 1, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    pack = build_runtime_activation_evidence_pack(
        generated_at="2026-05-10T11:00:00Z",
        governance_report=gov,
        transition_traces=(),
        representative_enqueue_samples=(),
    )
    assert pack["governance_report_summary"]["report_version"] == gov["report_version"]


def test_no_registry_mutation_after_pack():
    before = reg._REGISTRY_CEILING.get(FAMILY_COMPLIANCE_SCORE_RECALC)
    build_runtime_activation_evidence_pack(**_staging_inputs())
    after = reg._REGISTRY_CEILING.get(FAMILY_COMPLIANCE_SCORE_RECALC)
    assert before == after
