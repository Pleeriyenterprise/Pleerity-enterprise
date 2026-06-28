"""Stream E2.1: outcome engine refreshes evidence authority (incl. gap sync) after compliant-set."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_apply_action_outcome_certificate_verified_syncs_authority_before_recalc():
    from services import compliance_outcome_engine as coe

    db = MagicMock()
    db.compliance_activity_log.find_one = AsyncMock(return_value=None)
    db.compliance_activity_log.insert_one = AsyncMock()
    db.properties.find_one = AsyncMock(
        side_effect=[
            {"compliance_score": 50, "compliance_status": "RED"},
            {"compliance_score": 55, "compliance_status": "RED"},
        ]
    )
    db.properties.update_one = AsyncMock()
    db.requirements.update_many = AsyncMock()
    req_find = MagicMock()
    req_find.to_list = AsyncMock(
        return_value=[
            {"requirement_id": "r_gas_1"},
            {"requirement_id": "r_gas_2"},
        ]
    )
    db.requirements.find = MagicMock(return_value=req_find)
    db.risk_signals.update_many = AsyncMock()

    call_order: list[str] = []

    async def sync_side(*args, **kwargs):
        call_order.append("sync")

    async def recalc_side(*args, **kwargs):
        call_order.append("recalc")

    sync_mock = AsyncMock(side_effect=sync_side)
    recalc_mock = AsyncMock(side_effect=recalc_side)

    event = {
        "event_type": coe.EVENT_CERTIFICATE_VERIFIED,
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "GAS_SAFETY",
        "source_id": "doc1",
        "dedupe_key": "test:cert:1",
        "actor_id": "u1",
        "actor_role": "ADMIN",
    }

    with (
        patch("services.compliance_outcome_engine.database.get_db", return_value=db),
        patch("services.authority_mutation_fanout.authority_sync_with_transition_observability", sync_mock),
        patch("services.compliance_outcome_engine.recalculate_and_persist", recalc_mock),
        patch.object(coe, "_count_active_risk_signals", new_callable=AsyncMock, return_value=0),
        patch.object(coe, "_sync_regenerate_risks_and_operational", new_callable=AsyncMock),
        patch("services.compliance_evidence_graph.producers.hooks.dispatch_p0_producer", new_callable=AsyncMock),
    ):
        out = await coe.apply_action_outcome(event)

    assert out.get("idempotent") is False
    assert sync_mock.await_count == 2
    synced_ids = [c.args[1] for c in sync_mock.await_args_list]
    assert "r_gas_1" in synced_ids
    assert "r_gas_2" in synced_ids
    assert recalc_mock.await_count == 1
    assert call_order == ["sync", "sync", "recalc"]
    assert recalc_mock.await_args_list[0].kwargs.get("property_id") == "p1"
    ctx = recalc_mock.await_args_list[0].kwargs.get("context") or {}
    assert ctx.get("correlation_id") == "certificate_verified:doc1"


@pytest.mark.asyncio
async def test_apply_action_outcome_skips_authority_sync_when_no_requirement_type():
    from services import compliance_outcome_engine as coe

    db = MagicMock()
    db.compliance_activity_log.find_one = AsyncMock(return_value=None)
    db.compliance_activity_log.insert_one = AsyncMock()
    db.properties.find_one = AsyncMock(
        side_effect=[
            {"compliance_score": 50, "compliance_status": "RED"},
            {"compliance_score": 50, "compliance_status": "RED"},
        ]
    )
    db.properties.update_one = AsyncMock()
    db.requirements.update_many = AsyncMock()
    db.risk_signals.update_many = AsyncMock()

    sync_mock = AsyncMock()
    recalc_mock = AsyncMock()

    event = {
        "event_type": coe.EVENT_CERTIFICATE_VERIFIED,
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "",
        "source_id": "doc1",
        "dedupe_key": "test:cert:2",
        "actor_id": "u1",
        "actor_role": "ADMIN",
    }

    with (
        patch("services.compliance_outcome_engine.database.get_db", return_value=db),
        patch("services.requirement_evidence_authority.sync_requirement_evidence_authority", sync_mock),
        patch("services.compliance_outcome_engine.recalculate_and_persist", recalc_mock),
        patch.object(coe, "_count_active_risk_signals", new_callable=AsyncMock, return_value=0),
        patch.object(coe, "_sync_regenerate_risks_and_operational", new_callable=AsyncMock),
    ):
        await coe.apply_action_outcome(event)

    sync_mock.assert_not_called()
    db.requirements.find.assert_not_called()
    ctx = recalc_mock.await_args.kwargs.get("context") or {}
    assert ctx.get("correlation_id") == "certificate_verified:doc1"


@pytest.mark.asyncio
async def test_apply_action_outcome_respects_top_level_correlation_id():
    from services import compliance_outcome_engine as coe

    db = MagicMock()
    db.compliance_activity_log.find_one = AsyncMock(return_value=None)
    db.compliance_activity_log.insert_one = AsyncMock()
    db.properties.find_one = AsyncMock(
        side_effect=[
            {"compliance_score": 50, "compliance_status": "RED"},
            {"compliance_score": 50, "compliance_status": "RED"},
        ]
    )
    db.properties.update_one = AsyncMock()
    db.risk_signals.count_documents = AsyncMock(return_value=0)
    db.risk_signals.update_many = AsyncMock()
    recalc_mock = AsyncMock()

    event = {
        "event_type": coe.EVENT_CERTIFICATE_UPLOADED,
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "GAS_SAFETY",
        "source_id": "wo-99",
        "dedupe_key": "upload:wo-99:1",
        "correlation_id": "PARENT_WO_SESSION:abc",
        "metadata": {"work_order_id": "wo-99"},
        "actor_id": "u1",
        "actor_role": "CONTRACTOR",
    }

    with (
        patch("services.compliance_outcome_engine.database.get_db", return_value=db),
        patch("services.compliance_outcome_engine.recalculate_and_persist", recalc_mock),
        patch.object(coe, "_count_active_risk_signals", new_callable=AsyncMock, return_value=0),
        patch.object(coe, "_sync_regenerate_risks_and_operational", new_callable=AsyncMock),
    ):
        await coe.apply_action_outcome(event)

    ctx = recalc_mock.await_args.kwargs.get("context") or {}
    assert ctx.get("correlation_id") == "PARENT_WO_SESSION:abc"


@pytest.mark.asyncio
async def test_apply_action_outcome_metadata_correlation_id_precedence_over_heuristic():
    from services import compliance_outcome_engine as coe

    db = MagicMock()
    db.compliance_activity_log.find_one = AsyncMock(return_value=None)
    db.compliance_activity_log.insert_one = AsyncMock()
    db.properties.find_one = AsyncMock(
        side_effect=[
            {"compliance_score": 50, "compliance_status": "RED"},
            {"compliance_score": 50, "compliance_status": "RED"},
        ]
    )
    db.properties.update_one = AsyncMock()
    db.risk_signals.count_documents = AsyncMock(return_value=0)
    db.risk_signals.update_many = AsyncMock()
    recalc_mock = AsyncMock()

    event = {
        "event_type": coe.EVENT_CERTIFICATE_UPLOADED,
        "client_id": "c1",
        "property_id": "p1",
        "source_id": "wo-99",
        "dedupe_key": "upload:wo-99:1",
        "metadata": {"work_order_id": "wo-99", "correlation_id": "META_ROOT:1"},
        "actor_id": "u1",
        "actor_role": "CONTRACTOR",
    }

    with (
        patch("services.compliance_outcome_engine.database.get_db", return_value=db),
        patch("services.compliance_outcome_engine.recalculate_and_persist", recalc_mock),
        patch.object(coe, "_count_active_risk_signals", new_callable=AsyncMock, return_value=0),
        patch.object(coe, "_sync_regenerate_risks_and_operational", new_callable=AsyncMock),
    ):
        await coe.apply_action_outcome(event)

    ctx = recalc_mock.await_args.kwargs.get("context") or {}
    assert ctx.get("correlation_id") == "META_ROOT:1"


@pytest.mark.asyncio
async def test_apply_action_outcome_issue_created_correlation_uses_source_id():
    from services import compliance_outcome_engine as coe

    db = MagicMock()
    db.compliance_activity_log.find_one = AsyncMock(return_value=None)
    db.compliance_activity_log.insert_one = AsyncMock()
    db.properties.find_one = AsyncMock(
        side_effect=[
            {"compliance_score": 50, "compliance_status": "RED"},
            {"compliance_score": 50, "compliance_status": "RED"},
        ]
    )
    db.properties.update_one = AsyncMock()
    db.risk_signals.count_documents = AsyncMock(return_value=0)
    db.risk_signals.update_many = AsyncMock()
    recalc_mock = AsyncMock()

    event = {
        "event_type": coe.EVENT_ISSUE_CREATED,
        "client_id": "c1",
        "property_id": "p1",
        "source_id": "iss-1",
        "dedupe_key": "cov:issue_created:iss-1",
        "actor_id": "u1",
        "actor_role": "CLIENT",
        "metadata": {},
    }

    with (
        patch("services.compliance_outcome_engine.database.get_db", return_value=db),
        patch("services.compliance_outcome_engine.recalculate_and_persist", recalc_mock),
        patch.object(coe, "_count_active_risk_signals", new_callable=AsyncMock, return_value=0),
        patch.object(coe, "_sync_regenerate_risks_and_operational", new_callable=AsyncMock),
    ):
        await coe.apply_action_outcome(event)

    ctx = recalc_mock.await_args.kwargs.get("context") or {}
    assert ctx.get("correlation_id") == "issue_created:iss-1"


@pytest.mark.asyncio
async def test_apply_action_outcome_correlation_action_outcome_prefix_when_no_entity_ids():
    """certificate_uploaded with no work_order_id / source_id → ACTION_OUTCOME:{dedupe_key}."""
    from services import compliance_outcome_engine as coe

    db = MagicMock()
    db.compliance_activity_log.find_one = AsyncMock(return_value=None)
    db.compliance_activity_log.insert_one = AsyncMock()
    db.properties.find_one = AsyncMock(
        side_effect=[
            {"compliance_score": 50, "compliance_status": "RED"},
            {"compliance_score": 50, "compliance_status": "RED"},
        ]
    )
    db.properties.update_one = AsyncMock()
    db.risk_signals.count_documents = AsyncMock(return_value=0)
    db.risk_signals.update_many = AsyncMock()
    recalc_mock = AsyncMock()

    event = {
        "event_type": coe.EVENT_CERTIFICATE_UPLOADED,
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "X",
        "source_id": "",
        "dedupe_key": "orphan_upload:row1",
        "metadata": {},
        "actor_id": "u1",
        "actor_role": "SYSTEM",
    }

    with (
        patch("services.compliance_outcome_engine.database.get_db", return_value=db),
        patch("services.compliance_outcome_engine.recalculate_and_persist", recalc_mock),
        patch.object(coe, "_count_active_risk_signals", new_callable=AsyncMock, return_value=0),
        patch.object(coe, "_sync_regenerate_risks_and_operational", new_callable=AsyncMock),
    ):
        await coe.apply_action_outcome(event)

    ctx = recalc_mock.await_args.kwargs.get("context") or {}
    assert ctx.get("correlation_id") == "ACTION_OUTCOME:orphan_upload:row1"
