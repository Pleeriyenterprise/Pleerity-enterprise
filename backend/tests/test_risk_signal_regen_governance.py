"""
F4 remediation: risk signal regen governance retains operational propagation lineage.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.risk_signal_regen_governance import (
    collect_operational_debt_signal_ids,
    should_retain_signal_on_regen,
    stable_signal_key,
)
from services.risk_signal_service import (
    STATUS_ACKNOWLEDGED,
    STATUS_ACTIVE,
    generate_risk_signals_for_property,
    create_issue_from_risk_signal,
)


def test_stable_signal_key_normalizes_asset_id():
    assert stable_signal_key("Electrical Risk", None) == ("Electrical Risk", None)
    assert stable_signal_key("Electrical Risk", "  ") == ("Electrical Risk", None)
    assert stable_signal_key("Electrical Risk", "a1") == ("Electrical Risk", "a1")


@pytest.mark.asyncio
async def test_collect_operational_debt_signal_ids_from_issue_and_wo():
    mock_db = MagicMock()

    async def issue_iter():
        yield {"risk_signal_id": "rs_issue_debt"}

    async def wo_iter():
        yield {"risk_signal_id": "rs_wo_debt"}

    mock_db.maintenance_issues.find.return_value = issue_iter()
    mock_db.work_orders.find.return_value = wo_iter()
    mock_db.clients.find_one = AsyncMock(return_value={"default_jurisdiction": "england"})
    mock_db.properties.find_one = AsyncMock(
        return_value={"property_id": "p1", "jurisdiction": "england"}
    )

    debt = await collect_operational_debt_signal_ids(mock_db, "c1", "p1")
    assert debt == {"rs_issue_debt", "rs_wo_debt"}


def test_should_retain_signal_on_regen_protects_debt_and_lifecycle_states():
    doc_active = {"signal_id": "rs_a", "status": STATUS_ACTIVE}
    doc_ack = {"signal_id": "rs_b", "status": STATUS_ACKNOWLEDGED}
    assert should_retain_signal_on_regen(doc_active, operational_debt_ids={"rs_a"}, merged_retained_ids=set())
    assert should_retain_signal_on_regen(doc_ack, operational_debt_ids=set(), merged_retained_ids=set())
    assert not should_retain_signal_on_regen(doc_active, operational_debt_ids=set(), merged_retained_ids=set())


@pytest.mark.asyncio
async def test_generate_risk_signals_merges_in_place_for_existing_key():
    existing_signal = {
        "signal_id": "rs_keep_me",
        "client_id": "c1",
        "property_id": "p1",
        "risk_type": "Electrical Risk",
        "asset_id": None,
        "status": STATUS_ACKNOWLEDGED,
        "source": "heuristic",
        "generated_at": "2026-01-01T00:00:00+00:00",
    }

    mock_db = MagicMock()
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[existing_signal])
    mock_db.risk_signals.update_one = AsyncMock()
    mock_db.risk_signals.insert_one = AsyncMock()
    mock_db.risk_signals.delete_many = AsyncMock(return_value=MagicMock(deleted_count=0))

    rule_patches = {
        "_fetch_property": {"property_id": "p1"},
        "_fetch_assets": [],
        "_fetch_work_orders": [],
        "_fetch_work_orders_with_breach_in_window": [],
        "_fetch_issues": [],
        "_fetch_requirements_overdue": [],
        "_fetch_requirements_expiring_soon": [],
        "_rule_boiler_failure": [],
        "_rule_damp_moisture": [],
        "_rule_recurring_repairs": [],
        "_rule_maintenance_frequency": [],
        "_rule_sla_breach": [],
        "_rule_compliance_churn": [],
        "_rule_certificate_expiry_soon": [],
        "_rule_electrical": [
            {
                "signal_category": "asset",
                "risk_type": "Electrical Risk",
                "risk_level": "medium",
                "reasons": ["EICR overdue"],
                "recommended_action": "Review certificate",
                "asset_id": None,
            }
        ],
    }

    with patch("services.risk_signal_service.database.get_db", return_value=mock_db):
        stack = [
            patch(f"services.risk_signal_service.{name}", new_callable=AsyncMock, return_value=val)
            for name, val in rule_patches.items()
        ]
        for p in stack:
            p.start()
        try:
            with patch(
                "services.risk_signal_regen_governance.collect_operational_debt_signal_ids",
                new_callable=AsyncMock,
                return_value={"rs_keep_me"},
            ):
                with patch("services.automation_status_service.record_risk_refresh", new_callable=AsyncMock):
                    out = await generate_risk_signals_for_property("p1", "c1")
        finally:
            for p in stack:
                p.stop()

    assert out["merged_in_place"] == 1
    mock_db.risk_signals.delete_many.assert_not_called()
    update_call = mock_db.risk_signals.update_one.await_args
    assert update_call[0][0]["signal_id"] == "rs_keep_me"


@pytest.mark.asyncio
async def test_create_issue_from_risk_signal_replays_open_issue():
    replay_doc = {"issue_id": "iss-replay", "risk_signal_id": "rs1", "idempotent_replay": True}
    with patch(
        "services.risk_signal_service.get_risk_signal_by_id",
        new_callable=AsyncMock,
        return_value={"signal_id": "rs1", "property_id": "p1", "risk_type": "Electrical Risk"},
    ):
        with patch(
            "services.risk_signal_issue_idempotency.replay_open_issue_for_signal",
            new_callable=AsyncMock,
            return_value=replay_doc,
        ):
            out = await create_issue_from_risk_signal("rs1", "c1")
    assert out["issue_id"] == "iss-replay"
    assert out.get("idempotent_replay") is True
