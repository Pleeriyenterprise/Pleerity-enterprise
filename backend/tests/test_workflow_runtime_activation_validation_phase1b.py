"""Phase 1B: read-only activation validation (mocked enqueue; no DB)."""

from __future__ import annotations

import json
from unittest.mock import patch

import services.workflow_runtime_activation_registry as reg
from services.compliance_recalc_queue import EnqueueComplianceRecalcResult
from services.workflow_activation_governance_report import build_workflow_activation_governance_report
from services.workflow_activation_readiness import FAMILY_COMPLIANCE_SCORE_RECALC
from services.workflow_runtime_activation_registry import (
    ACTIVATION_DISABLED,
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
    GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY,
    GUARD_RESULT_PERMITTED,
    resolve_compliance_recalc_activation_gate,
)
from services.workflow_runtime_activation_validation import (
    CRITICAL_VALIDATION_DRIFT,
    HIGH_VALIDATION_DRIFT,
    LOW_VALIDATION_DRIFT,
    MODERATE_VALIDATION_DRIFT,
    QUEUE_CONTINUITY_CONFIRMED,
    QUEUE_CONTINUITY_UNVERIFIED,
    ROLLBACK_VALIDATED,
    VALIDATION_CONFIRMED,
    VALIDATION_FAILED,
    VALIDATION_INSUFFICIENT_EVIDENCE,
    VALIDATION_PARTIAL,
    build_activation_continuity_summary,
    build_activation_rollback_summary,
    build_activation_validation_summary,
    build_runtime_activation_validation_snapshot,
    build_validation_drift_findings,
    classify_validation_drift,
    validate_activation_gate_internal_consistency,
    validate_deferred_and_non_scoped_guards,
    validate_downstream_activation_metadata,
    validate_enqueue_result_continuity,
    validate_governance_runtime_activation_visibility,
    validate_live_compliance_recalc_gate,
    validate_observability_on_enqueue_result,
    validate_registry_rollback_posture,
    validate_worker_payload_field_set,
)


def _strong_governance_kw():
    return dict(
        generated_at_iso="2026-05-08T15:00:00Z",
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


def test_validation_determinism_snapshot():
    s1 = build_runtime_activation_validation_snapshot(
        generated_at_iso="2026-05-09T12:00:00Z",
        governance_report=build_workflow_activation_governance_report(**_strong_governance_kw()),
    )
    s2 = build_runtime_activation_validation_snapshot(
        generated_at_iso="2026-05-09T12:00:00Z",
        governance_report=build_workflow_activation_governance_report(**_strong_governance_kw()),
    )
    assert json.dumps(s1, sort_keys=True) == json.dumps(s2, sort_keys=True)


def test_live_gate_and_deferred_guards():
    g = validate_live_compliance_recalc_gate()
    assert g["activation_validation"] == VALIDATION_CONFIRMED
    d = validate_deferred_and_non_scoped_guards()
    assert d["activation_validation"] == VALIDATION_CONFIRMED


def test_gate_internal_consistency_detects_permitted_guard_mismatch():
    bad = {
        "permitted": True,
        "activation_guard_result": GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY,
        "activation_state": ACTIVATION_LIMITED,
        "registry_ceiling": ACTIVATION_LIMITED,
        "activation_family": FAMILY_COMPLIANCE_SCORE_RECALC,
        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
        "activation_scope": "compliance_recalc_enqueue_only",
    }
    cls, findings = validate_activation_gate_internal_consistency(bad)
    assert cls == VALIDATION_FAILED
    assert "permitted_but_guard_not_permitted" in findings


def test_rollback_posture_limited_to_observe_and_disabled():
    a = validate_registry_rollback_posture(from_ceiling=ACTIVATION_LIMITED, to_ceiling=ACTIVATION_OBSERVE_ONLY)
    b = validate_registry_rollback_posture(from_ceiling=ACTIVATION_LIMITED, to_ceiling=ACTIVATION_DISABLED)
    c = validate_registry_rollback_posture(from_ceiling=ACTIVATION_OBSERVE_ONLY, to_ceiling=ACTIVATION_DISABLED)
    assert a["rollback_posture"] == ROLLBACK_VALIDATED and not a["finding_codes"]
    assert b["rollback_posture"] == ROLLBACK_VALIDATED and not b["finding_codes"]
    assert c["rollback_posture"] == ROLLBACK_VALIDATED and not c["finding_codes"]
    inc = validate_registry_rollback_posture(from_ceiling=ACTIVATION_OBSERVE_ONLY, to_ceiling=ACTIVATION_LIMITED)
    assert "rollback_must_not_increase_activation" in inc["finding_codes"]


def test_rollback_summary():
    s = build_activation_rollback_summary()
    assert s["rollback_posture"] == ROLLBACK_VALIDATED
    assert len(s["transitions"]) == 3


def test_enqueue_continuity_permitted_enqueued():
    gate = resolve_compliance_recalc_activation_gate()
    er = EnqueueComplianceRecalcResult(
        enqueued=True,
        correlation_id="cid",
        activation_skipped=False,
        activation_state=gate["activation_state"],
        activation_reason=gate["activation_reason"],
        activation_scope=gate["activation_scope"],
        activation_family=gate["activation_family"],
        activation_guard_result=gate["activation_guard_result"],
        activation_governance_version=gate["activation_governance_version"],
        regeneration_requeued=True,
        regeneration_error=None,
    )
    v = validate_enqueue_result_continuity(gate_ctx=gate, enqueue_result=er)
    assert v["activation_validation"] == VALIDATION_CONFIRMED
    assert v["queue_continuity"] == QUEUE_CONTINUITY_CONFIRMED


def test_enqueue_continuity_activation_skip():
    gate = dict(resolve_compliance_recalc_activation_gate())
    gate["permitted"] = False
    gate["activation_guard_result"] = GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY
    gate["activation_state"] = ACTIVATION_OBSERVE_ONLY
    er = EnqueueComplianceRecalcResult(
        enqueued=False,
        correlation_id="cid",
        activation_skipped=True,
        activation_state=ACTIVATION_OBSERVE_ONLY,
        activation_reason="registry_ceiling_activation_observe_only",
        activation_scope="compliance_recalc_enqueue_only",
        activation_family=FAMILY_COMPLIANCE_SCORE_RECALC,
        activation_guard_result=GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY,
        activation_governance_version=ACTIVATION_GOVERNANCE_VERSION,
    )
    v = validate_enqueue_result_continuity(gate_ctx=gate, enqueue_result=er)
    assert v["queue_continuity"] == QUEUE_CONTINUITY_UNVERIFIED
    assert v["activation_validation"] == VALIDATION_CONFIRMED


def test_enqueue_continuity_critical_mismatch():
    gate = dict(resolve_compliance_recalc_activation_gate())
    gate["permitted"] = False
    er = EnqueueComplianceRecalcResult(
        enqueued=True,
        correlation_id="cid",
        activation_skipped=False,
        activation_state=ACTIVATION_LIMITED,
        activation_reason="x",
        activation_scope="compliance_recalc_enqueue_only",
        activation_family=FAMILY_COMPLIANCE_SCORE_RECALC,
        activation_guard_result=GUARD_RESULT_PERMITTED,
        activation_governance_version=ACTIVATION_GOVERNANCE_VERSION,
    )
    v = validate_enqueue_result_continuity(gate_ctx=gate, enqueue_result=er)
    assert v["activation_validation"] == VALIDATION_FAILED
    assert "not_permitted_but_enqueued_true" in v["finding_codes"]


def test_observability_on_enqueue_skipped_missing_reason():
    er = EnqueueComplianceRecalcResult(
        enqueued=False,
        correlation_id="cid",
        activation_skipped=True,
        activation_reason=None,
        activation_guard_result="GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY",
        activation_governance_version=ACTIVATION_GOVERNANCE_VERSION,
    )
    o = validate_observability_on_enqueue_result(er)
    assert "skipped_missing_activation_reason" in o["finding_codes"]


def test_downstream_metadata_with_trace():
    from services.requirement_transition_observability import attach_downstream_trigger_observation

    tr: dict = {
        "transition_id": "t1",
        "correlation_id": "c1",
        "downstream_trigger_targets": [],
    }
    er = EnqueueComplianceRecalcResult(
        enqueued=False,
        correlation_id="cid",
        activation_skipped=True,
        activation_state=ACTIVATION_OBSERVE_ONLY,
        activation_reason="registry_ceiling_activation_observe_only",
        activation_scope="compliance_recalc_enqueue_only",
        activation_family=FAMILY_COMPLIANCE_SCORE_RECALC,
        activation_guard_result=GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY,
        activation_governance_version=ACTIVATION_GOVERNANCE_VERSION,
    )
    attach_downstream_trigger_observation(
        tr,
        downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
        trigger_mode="async_queue",
        propagation_stage="test",
        enqueue_result=er,
    )
    d = validate_downstream_activation_metadata(transition_traces=[tr])
    assert d["activation_validation"] == VALIDATION_CONFIRMED
    assert d["recalc_downstream_rows_checked"] == 1


def test_downstream_insufficient_evidence():
    d = validate_downstream_activation_metadata(transition_traces=[{"downstream_trigger_targets": []}])
    assert d["activation_validation"] == VALIDATION_INSUFFICIENT_EVIDENCE
    assert "no_gated_downstream_rows_in_traces" in d["finding_codes"]


def test_governance_visibility():
    r = build_workflow_activation_governance_report(**_strong_governance_kw())
    v = validate_governance_runtime_activation_visibility(r)
    assert v["activation_validation"] == VALIDATION_CONFIRMED


def test_drift_classification():
    assert classify_validation_drift(finding_codes=[]) == LOW_VALIDATION_DRIFT
    assert classify_validation_drift(finding_codes=["downstream_skipped_missing_activation_state"]) == MODERATE_VALIDATION_DRIFT
    assert classify_validation_drift(finding_codes=["compliance_row_version_mismatch_in_snapshot"]) == HIGH_VALIDATION_DRIFT
    assert classify_validation_drift(finding_codes=["not_permitted_but_enqueued_true"]) == CRITICAL_VALIDATION_DRIFT


def test_worker_payload_keys():
    keys = list(
        {
            "property_id",
            "client_id",
            "trigger_reason",
            "actor_type",
            "actor_id",
            "correlation_id",
            "status",
            "attempts",
            "retry_count",
            "retry_exhausted",
            "next_run_at",
            "last_error",
            "created_at",
            "updated_at",
        }
    )
    assert validate_worker_payload_field_set(job_doc_keys=keys)["activation_validation"] == VALIDATION_CONFIRMED


def test_summaries_from_snapshot():
    snap = build_runtime_activation_validation_snapshot(
        generated_at_iso="2026-05-09T12:00:00Z",
        governance_report=build_workflow_activation_governance_report(**_strong_governance_kw()),
    )
    vs = build_activation_validation_summary(snap)
    assert vs["overall_activation_validation"] == snap["overall_activation_validation"]
    cs = build_activation_continuity_summary(snap)
    assert cs["schema_version"] == "activation_continuity_summary_v1"


def test_snapshot_with_enqueue_samples_under_registry_patch():
    gate_limited = resolve_compliance_recalc_activation_gate()
    er_ok = EnqueueComplianceRecalcResult(
        enqueued=True,
        correlation_id="cid-lim",
        activation_skipped=False,
        activation_state=gate_limited["activation_state"],
        activation_reason=gate_limited["activation_reason"],
        activation_scope=gate_limited["activation_scope"],
        activation_family=gate_limited["activation_family"],
        activation_guard_result=gate_limited["activation_guard_result"],
        activation_governance_version=gate_limited["activation_governance_version"],
        regeneration_requeued=False,
        regeneration_error=None,
    )
    with patch.dict(reg._REGISTRY_CEILING, {FAMILY_COMPLIANCE_SCORE_RECALC: ACTIVATION_OBSERVE_ONLY}, clear=False):
        gate_obs = resolve_compliance_recalc_activation_gate()
    er_skip = EnqueueComplianceRecalcResult(
        enqueued=False,
        correlation_id="cid-obs",
        activation_skipped=True,
        activation_state=gate_obs["activation_state"],
        activation_reason=gate_obs["activation_reason"],
        activation_scope=gate_obs["activation_scope"],
        activation_family=gate_obs["activation_family"],
        activation_guard_result=gate_obs["activation_guard_result"],
        activation_governance_version=gate_obs["activation_governance_version"],
    )
    snap = build_runtime_activation_validation_snapshot(
        generated_at_iso="2026-05-09T12:00:00Z",
        governance_report=build_workflow_activation_governance_report(**_strong_governance_kw()),
        enqueue_samples=[(gate_limited, er_ok), (gate_obs, er_skip)],
    )
    assert len(snap["enqueue_sample_validations"]) == 2
    assert snap["gate_validation"]["activation_validation"] == VALIDATION_CONFIRMED


def test_build_validation_drift_merges_enqueue_blocks():
    gate = {"finding_codes": ["a"], "activation_validation": VALIDATION_CONFIRMED}
    deferred = {"finding_codes": [], "activation_validation": VALIDATION_CONFIRMED}
    blocks = [
        {
            "continuity": {"finding_codes": ["c1"], "activation_validation": VALIDATION_CONFIRMED},
            "observability": {"finding_codes": ["o1"], "activation_validation": VALIDATION_CONFIRMED},
        }
    ]
    d = build_validation_drift_findings(
        gate_validation=gate,
        deferred_validation=deferred,
        enqueue_continuity_blocks=blocks,
    )
    assert set(d["finding_codes"]) == {"a", "c1", "o1"}
