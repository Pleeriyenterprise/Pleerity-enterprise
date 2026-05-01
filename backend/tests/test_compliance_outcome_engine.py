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
        patch("services.requirement_evidence_authority.sync_requirement_evidence_authority", sync_mock),
        patch("services.compliance_outcome_engine.recalculate_and_persist", recalc_mock),
        patch.object(coe, "_count_active_risk_signals", new_callable=AsyncMock, return_value=0),
        patch.object(coe, "_sync_regenerate_risks_and_operational", new_callable=AsyncMock),
    ):
        out = await coe.apply_action_outcome(event)

    assert out.get("idempotent") is False
    assert sync_mock.await_count == 2
    sync_mock.assert_any_call(db, "r_gas_1", property_id_hint="p1")
    sync_mock.assert_any_call(db, "r_gas_2", property_id_hint="p1")
    assert recalc_mock.await_count == 1
    assert call_order == ["sync", "sync", "recalc"]
    assert recalc_mock.await_args_list[0].kwargs.get("property_id") == "p1"


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
