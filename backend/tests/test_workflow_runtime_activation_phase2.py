"""Phase 2: REGENERATION_RECALC limited activation (mocked DB; no workers)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import services.risk_signal_regen_queue as rsr_mod
import services.workflow_runtime_activation_registry as reg
from services.workflow_activation_readiness import FAMILY_REGENERATION_RECALC
from services.risk_signal_regen_queue import enqueue_risk_signal_regen
from services.workflow_runtime_activation_registry import (
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
    build_regeneration_limited_activation_visibility,
    build_runtime_activation_snapshot,
    build_workflow_activation_context,
    resolve_regeneration_recalc_activation_gate,
)
from services.workflow_runtime_activation_validation import (
    ROLLBACK_VALIDATED,
    VALIDATION_CONFIRMED,
    build_activation_rollback_summary,
    build_runtime_activation_validation_snapshot,
    validate_live_regeneration_recalc_gate,
    validate_risk_signal_regen_enqueue_mapping_continuity,
    validate_registry_rollback_posture,
)
from services.workflow_activation_governance_report import build_workflow_activation_governance_report
from services.workflow_runtime_activation_evidence_pack import build_runtime_activation_evidence_pack
from services.requirement_transition_observability import ENQUEUE_SKIPPED, attach_downstream_trigger_observation, classify_enqueue_outcome


def test_regeneration_context_and_gate():
    ctx = build_workflow_activation_context(FAMILY_REGENERATION_RECALC)
    assert ctx["permitted"] is True
    assert ctx["activation_scope"] == "risk_signal_regen_enqueue_only"
    assert ctx["activation_guard_result"] == "GUARD_RESULT_PERMITTED"
    assert ctx["activation_governance_version"] == ACTIVATION_GOVERNANCE_VERSION
    g = resolve_regeneration_recalc_activation_gate()
    assert g["activation_family"] == FAMILY_REGENERATION_RECALC
    v = validate_live_regeneration_recalc_gate()
    assert v["activation_validation"] == VALIDATION_CONFIRMED


def test_regeneration_operational_visibility():
    vis = build_regeneration_limited_activation_visibility(generated_at_iso="2026-05-11T12:00:00Z")
    assert vis["regeneration_permitted"] is True
    assert FAMILY_REGENERATION_RECALC in vis["limited_activation_families"]


def test_rollout_snapshot_lists_both_limited():
    snap = build_runtime_activation_snapshot(generated_at_iso="2026-05-11T12:00:00Z")
    lim = {str(r.get("activation_family")) for r in snap.get("families") or [] if r.get("permitted")}
    assert FAMILY_REGENERATION_RECALC in lim


def test_regeneration_rollback_posture():
    a = validate_registry_rollback_posture(from_ceiling=ACTIVATION_LIMITED, to_ceiling=ACTIVATION_OBSERVE_ONLY)
    assert a["rollback_posture"] == ROLLBACK_VALIDATED
    summary = build_activation_rollback_summary()
    assert FAMILY_REGENERATION_RECALC in summary["limited_activation_family_scope"]


def test_regen_enqueue_skips_when_registry_observe_only():
    mock_db = MagicMock()
    mock_db.risk_signal_regen_queue.find_one = AsyncMock(return_value=None)
    mock_db.risk_signal_regen_queue.insert_one = AsyncMock()
    mock_db.risk_signal_regen_queue.update_one = AsyncMock()

    async def _go():
        with patch.object(rsr_mod.database, "get_db", return_value=mock_db):
            with patch.dict(reg._REGISTRY_CEILING, {FAMILY_REGENERATION_RECALC: ACTIVATION_OBSERVE_ONLY}, clear=False):
                return await enqueue_risk_signal_regen("p1", "c1", "COMPLIANCE_ENQUEUE:X")

    res = asyncio.run(_go())
    assert res.get("queued") is False
    assert res.get("activation_skipped") is True
    assert res.get("activation_guard_result") == "GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY"
    mock_db.risk_signal_regen_queue.insert_one.assert_not_called()


def test_regen_enqueue_inserts_when_registry_limited():
    mock_db = MagicMock()
    mock_db.risk_signal_regen_queue.find_one = AsyncMock(return_value=None)
    mock_db.risk_signal_regen_queue.insert_one = AsyncMock()

    async def _go():
        with patch.object(rsr_mod.database, "get_db", return_value=mock_db):
            with patch.dict(reg._REGISTRY_CEILING, {FAMILY_REGENERATION_RECALC: ACTIVATION_LIMITED}, clear=False):
                return await enqueue_risk_signal_regen("p1", "c1", "COMPLIANCE_ENQUEUE:X")

    res = asyncio.run(_go())
    assert res.get("queued") is True
    assert res.get("activation_skipped") is False
    assert res.get("activation_family") == FAMILY_REGENERATION_RECALC
    mock_db.risk_signal_regen_queue.insert_one.assert_called_once()


def test_regen_enqueue_continuity_validation():
    gate = resolve_regeneration_recalc_activation_gate()
    ok = {
        "activation_family": gate["activation_family"],
        "activation_governance_version": gate["activation_governance_version"],
        "activation_guard_result": gate["activation_guard_result"],
        "activation_reason": gate["activation_reason"],
        "activation_scope": gate["activation_scope"],
        "activation_state": gate["activation_state"],
        "activation_skipped": False,
        "merged": False,
        "property_id": "p1",
        "queued": True,
    }
    v = validate_risk_signal_regen_enqueue_mapping_continuity(gate_ctx=gate, result_mapping=ok)
    assert v["activation_validation"] == VALIDATION_CONFIRMED


def test_classify_enqueue_skipped_for_regen_mapping():
    gate = resolve_regeneration_recalc_activation_gate()
    oc, ok, dup = classify_enqueue_outcome(
        attempted=True,
        enqueue_result={
            "activation_skipped": True,
            "activation_reason": "registry_ceiling_activation_observe_only",
            "queued": False,
        },
    )
    assert oc == ENQUEUE_SKIPPED and ok is False


def test_attach_downstream_carries_regen_activation_metadata():
    tr: dict = {"correlation_id": "c1", "downstream_trigger_targets": []}
    gate = resolve_regeneration_recalc_activation_gate()
    er = {
        "activation_family": gate["activation_family"],
        "activation_governance_version": gate["activation_governance_version"],
        "activation_guard_result": gate["activation_guard_result"],
        "activation_reason": "registry_ceiling_activation_observe_only",
        "activation_scope": gate["activation_scope"],
        "activation_skipped": True,
        "activation_state": ACTIVATION_OBSERVE_ONLY,
        "merged": False,
        "queued": False,
    }
    attach_downstream_trigger_observation(
        tr,
        downstream_target="risk_signal_regen_queue.enqueue_risk_signal_regen",
        trigger_mode="async_queue",
        propagation_stage="test",
        enqueue_result=er,
    )
    row = tr["downstream_trigger_targets"][-1]
    assert row.get("activation_family") == FAMILY_REGENERATION_RECALC
    assert row.get("enqueue_outcome") == ENQUEUE_SKIPPED


def test_governance_report_includes_regeneration_visibility():
    r = build_workflow_activation_governance_report(
        generated_at_iso="2026-05-11T14:00:00Z",
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=[{"downstream_trigger_targets": [{"enqueue_outcome": "ENQUEUE_ACCEPTED"}]}],
        queue_visibility={"diagnostics": {"returned_count": 1, "skipped_unbounded_scan": False}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 1}}},
    )
    vis = r.get("regeneration_activation_operational_visibility")
    assert isinstance(vis, dict)
    assert vis.get("schema_version") == "regeneration_limited_activation_visibility_v1"


def test_validation_snapshot_includes_regeneration_gate():
    gov = build_workflow_activation_governance_report(
        generated_at_iso="2026-05-11T15:00:00Z",
        convergence_snapshot={"convergence_evidence_matrix": {"matrix_rows": [{"convergence_confidence": "HIGH_CONVERGENCE_CONFIDENCE"}]}},
        transition_traces=[],
        queue_visibility={"diagnostics": {"returned_count": 0, "skipped_unbounded_scan": True}},
        observability_summary={"reconciliation_visibility": {"by_reconciliation_evidence": {"RECONCILIATION_OBSERVED": 0}}},
    )
    gate = resolve_regeneration_recalc_activation_gate()
    regen_body = {
        "activation_family": gate["activation_family"],
        "activation_governance_version": gate["activation_governance_version"],
        "activation_guard_result": gate["activation_guard_result"],
        "activation_reason": gate["activation_reason"],
        "activation_scope": gate["activation_scope"],
        "activation_state": gate["activation_state"],
        "activation_skipped": False,
        "merged": False,
        "property_id": "p1",
        "queued": True,
    }
    snap = build_runtime_activation_validation_snapshot(
        generated_at_iso="2026-05-11T15:00:00Z",
        governance_report=gov,
        regeneration_enqueue_samples=[(gate, regen_body)],
    )
    assert snap.get("regeneration_recalc_gate_validation", {}).get("activation_validation") == VALIDATION_CONFIRMED
    assert snap.get("regeneration_enqueue_sample_validations")


def test_evidence_pack_includes_regeneration_validation():
    pack = build_runtime_activation_evidence_pack(
        generated_at="2026-05-11T16:00:00Z",
        governance_families=(FAMILY_REGENERATION_RECALC,),
        transition_traces=(),
        representative_enqueue_samples=(),
    )
    inner = pack.get("activation_validation_snapshot") or {}
    assert "regeneration_recalc_gate_validation" in inner
