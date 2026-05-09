"""Phase 1: runtime activation registry + compliance recalc enqueue gate (mocked DB)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import services.compliance_recalc_queue as crq_mod
import services.workflow_runtime_activation_registry as reg
from services.compliance_recalc_queue import EnqueueComplianceRecalcResult, enqueue_compliance_recalc
from services.workflow_activation_readiness import (
    FAMILY_COMPLIANCE_SCORE_RECALC,
    FAMILY_NOTIFICATION_DISPATCH,
    FAMILY_REGENERATION_RECALC,
    FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
)
from services.workflow_runtime_activation_registry import (
    ACTIVATION_DISABLED,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
    ACTIVATION_GOVERNANCE_VERSION,
    resolve_regeneration_recalc_activation_gate,
    build_activation_rollout_visibility,
    build_activation_state_summary,
    build_runtime_activation_snapshot,
    build_workflow_activation_context,
    get_workflow_activation_state,
    is_workflow_activation_enabled,
    list_registry_family_keys,
    resolve_compliance_recalc_activation_gate,
)


def test_registry_determinism_compliance_limited():
    assert get_workflow_activation_state(FAMILY_COMPLIANCE_SCORE_RECALC) == ACTIVATION_LIMITED
    assert is_workflow_activation_enabled(FAMILY_COMPLIANCE_SCORE_RECALC) is True
    assert get_workflow_activation_state(FAMILY_REGENERATION_RECALC) == ACTIVATION_LIMITED
    assert is_workflow_activation_enabled(FAMILY_REGENERATION_RECALC) is True
    assert get_workflow_activation_state("CACHE_INVALIDATION") == ACTIVATION_DISABLED
    assert is_workflow_activation_enabled("CACHE_INVALIDATION") is False


def test_activation_context_guard_fields():
    ctx = build_workflow_activation_context(FAMILY_COMPLIANCE_SCORE_RECALC)
    assert ctx["permitted"] is True
    assert ctx["activation_guard_result"] == "GUARD_RESULT_PERMITTED"
    assert ctx["activation_governance_version"] == ACTIVATION_GOVERNANCE_VERSION
    assert ctx["activation_scope"] == "compliance_recalc_enqueue_only"


def test_blocked_non_scoped_family():
    ctx = build_workflow_activation_context(FAMILY_NOTIFICATION_DISPATCH)
    assert ctx["permitted"] is False
    assert ctx["activation_guard_result"] == "GUARD_RESULT_BLOCKED_NON_SCOPED_FAMILY"


def test_blocked_deferred_family_guard_precedence():
    ctx = build_workflow_activation_context("CACHE_INVALIDATION")
    assert ctx["permitted"] is False
    assert ctx["activation_guard_result"] == "GUARD_RESULT_BLOCKED_DEFERRED_FAMILY"


def test_snapshot_and_summaries_stable():
    s1 = build_runtime_activation_snapshot(generated_at_iso="2026-05-09T12:00:00Z")
    s2 = build_runtime_activation_snapshot(generated_at_iso="2026-05-09T12:00:00Z")
    assert s1 == s2
    assert build_activation_state_summary(s1) == build_activation_state_summary(s2)
    assert build_activation_rollout_visibility(s1) == build_activation_rollout_visibility(s2)


def test_registry_list_keys_sorted():
    k = list_registry_family_keys()
    assert k == sorted(k)
    assert (
        FAMILY_COMPLIANCE_SCORE_RECALC in k
        and FAMILY_REGENERATION_RECALC in k
        and FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE in k
    )


def test_rollback_downgrade_via_registry_patch():
    with patch.dict(reg._REGISTRY_CEILING, {FAMILY_COMPLIANCE_SCORE_RECALC: ACTIVATION_OBSERVE_ONLY}, clear=False):
        assert get_workflow_activation_state(FAMILY_COMPLIANCE_SCORE_RECALC) == ACTIVATION_OBSERVE_ONLY
        assert is_workflow_activation_enabled(FAMILY_COMPLIANCE_SCORE_RECALC, required_minimum=ACTIVATION_LIMITED) is False
        gate = resolve_compliance_recalc_activation_gate()
        assert gate["permitted"] is False


def test_classify_activation_skipped_outcome():
    from services.requirement_transition_observability import ENQUEUE_SKIPPED, classify_enqueue_outcome

    oc, ok, dup = classify_enqueue_outcome(
        attempted=True,
        enqueue_result=EnqueueComplianceRecalcResult(
            enqueued=False,
            correlation_id="cid",
            activation_skipped=True,
            activation_reason="registry_ceiling_activation_observe_only",
            activation_state=ACTIVATION_OBSERVE_ONLY,
            activation_guard_result="GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY",
        ),
    )
    assert oc == ENQUEUE_SKIPPED and ok is False and dup == "registry_ceiling_activation_observe_only"


def test_attach_downstream_carries_activation_metadata():
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
        activation_state=ACTIVATION_DISABLED,
        activation_reason="test_reason",
        activation_scope="compliance_recalc_enqueue_only",
        activation_family=FAMILY_COMPLIANCE_SCORE_RECALC,
        activation_guard_result="GUARD_RESULT_BLOCKED_REGISTRY_DISABLED",
        activation_governance_version=ACTIVATION_GOVERNANCE_VERSION,
    )
    attach_downstream_trigger_observation(
        tr,
        downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
        trigger_mode="async_queue",
        propagation_stage="test",
        enqueue_result=er,
    )
    row = tr["downstream_trigger_targets"][-1]
    assert row.get("activation_state") == ACTIVATION_DISABLED
    assert row.get("activation_family") == FAMILY_COMPLIANCE_SCORE_RECALC
    assert row.get("activation_guard_result") == "GUARD_RESULT_BLOCKED_REGISTRY_DISABLED"


def test_enqueue_skips_when_registry_observe_only():
    mock_db = MagicMock()
    mock_db.compliance_recalc_queue.insert_one = AsyncMock()
    mock_db.properties.update_one = AsyncMock()

    async def _go() -> EnqueueComplianceRecalcResult:
        with patch.object(crq_mod.database, "get_db", return_value=mock_db):
            with patch("services.risk_signal_regen_queue.enqueue_risk_signal_regen", new_callable=AsyncMock):
                with patch.dict(reg._REGISTRY_CEILING, {FAMILY_COMPLIANCE_SCORE_RECALC: ACTIVATION_OBSERVE_ONLY}, clear=False):
                    return await enqueue_compliance_recalc(
                        property_id="p1",
                        client_id="c1",
                        trigger_reason="PROPERTY_UPDATED",
                        actor_type="CLIENT",
                    )

    res = asyncio.run(_go())
    assert res.enqueued is False
    assert res.activation_skipped is True
    mock_db.compliance_recalc_queue.insert_one.assert_not_called()


def test_enqueue_inserts_when_registry_limited():
    mock_db = MagicMock()
    mock_db.compliance_recalc_queue.insert_one = AsyncMock()
    mock_db.properties.update_one = AsyncMock()

    async def _go() -> EnqueueComplianceRecalcResult:
        with patch.object(crq_mod.database, "get_db", return_value=mock_db):
            with patch("services.risk_signal_regen_queue.enqueue_risk_signal_regen", new_callable=AsyncMock):
                with patch.dict(reg._REGISTRY_CEILING, {FAMILY_COMPLIANCE_SCORE_RECALC: ACTIVATION_LIMITED}, clear=False):
                    return await enqueue_compliance_recalc(
                        property_id="p1",
                        client_id="c1",
                        trigger_reason="PROPERTY_UPDATED",
                        actor_type="CLIENT",
                    )

    res = asyncio.run(_go())
    assert res.enqueued is True
    assert res.activation_skipped is False
    mock_db.compliance_recalc_queue.insert_one.assert_called_once()
