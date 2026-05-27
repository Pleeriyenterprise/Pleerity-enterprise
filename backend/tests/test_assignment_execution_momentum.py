"""
ASSIGNMENT-CONVERSION-AND-EXECUTION-MOMENTUM-01 unit tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.assignment_execution_momentum_service import (
    _classify_coordination_failure,
    _execution_momentum_state,
    _quote_momentum_state,
    build_coordination_nudges_v1,
    build_quote_conversion_v1,
)


def test_classify_landlord_inaction_pending_confirm():
    wo = {
        "assignment_routing_state": "PENDING_CLIENT_CONFIRMATION",
        "client_confirmation_deadline_at": "2020-01-01T00:00:00+00:00",
    }
    assert _classify_coordination_failure(wo, 2) == "landlord_inaction"


def test_classify_orchestration_no_recommendation():
    wo = {
        "assignment_routing_state": "UNASSIGNED",
        "created_at": "2020-01-01T00:00:00+00:00",
    }
    assert _classify_coordination_failure(wo, 3) == "orchestration_failure"


def test_momentum_state_deadlocked_eligible_unassigned():
    wo = {"status": "OPEN", "created_at": "2020-01-01T00:00:00+00:00", "updated_at": "2020-01-01T00:00:00+00:00"}
    assert _execution_momentum_state(wo, eligible_count=2) == "deadlocked"


def test_quote_momentum_awaiting():
    wo = {"price_status": "AWAITING_QUOTE", "assigned_at": "2020-01-01T00:00:00+00:00", "pricing_mode": "MAINTENANCE_PREQUOTE"}
    assert _quote_momentum_state(wo) in ("stalled", "abandoned", "requested")


@pytest.mark.asyncio
async def test_coordination_nudges_eligible_unassigned():
    trace = {
        "traces_sample": [
            {
                "work_order_id": "w1",
                "eligible_contractor_count": 2,
                "coordination_failure": "landlord_inaction",
                "assignment_age_days": 20,
                "execution_momentum_state": "deadlocked",
            }
        ]
    }
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(return_value=[])

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_coordination_nudges_v1("c1", trace=trace)

    types = [n["nudge_type"] for n in out.get("nudges") or []]
    assert "eligible_but_unassigned" in types


@pytest.mark.asyncio
async def test_quote_conversion_states():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {"work_order_id": "w1", "price_status": "AWAITING_QUOTE", "assigned_at": "2026-05-01T00:00:00+00:00"},
            {"work_order_id": "w2", "price_status": "APPROVED", "status": "IN_PROGRESS"},
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_quote_conversion_v1("c1")

    assert out["quote_momentum_states"].get("executing") == 1 or out["quote_momentum_states"].get("approved") == 1
