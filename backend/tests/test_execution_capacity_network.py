"""
EXECUTION-CAPACITY-AND-NETWORK-RELIABILITY-01 unit tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.execution_capacity_network_service import (
    build_assignment_conversion_v1,
    build_quote_throughput_v1,
    build_execution_recovery_v1,
    _primary_failure_reason,
    _coverage_class,
)


def test_coverage_class_no_eligible():
    assert _coverage_class(0, 5) == "fragile_coverage"
    assert _coverage_class(0, 0) == "no_coverage"
    assert _coverage_class(2, 5) == "healthy_coverage"


def test_primary_failure_postcode():
    reason = _primary_failure_reason(
        {
            "eligible": 0,
            "excluded_location_postcode": 4,
            "excluded_maintenance_trade": 0,
            "visible_in_directory": 4,
        },
        {"no_eligible_contractors": True},
    )
    assert reason == "no_coverage:postcode_mismatch"


@pytest.mark.asyncio
async def test_assignment_conversion_open_unassigned():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {"work_order_id": "w1", "status": "OPEN", "client_id": "c1"},
            {"work_order_id": "w2", "status": "VERIFIED", "contractor_id": "ctr", "client_id": "c1"},
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_assignment_conversion_v1("c1")

    assert out["open_unassigned_count"] == 1
    assert out["verified_count"] == 1


@pytest.mark.asyncio
async def test_quote_throughput_awaiting():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {
                "work_order_id": "w1",
                "price_status": "AWAITING_QUOTE",
                "assigned_at": "2020-01-01T00:00:00+00:00",
                "pricing_mode": "MAINTENANCE_PREQUOTE",
            },
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_quote_throughput_v1("c1")

    assert out["awaiting_quote_count"] == 1
    assert len(out["quote_deadlocks"]) == 1


@pytest.mark.asyncio
async def test_execution_recovery_execution_capacity_blockage():
    audit = {
        "coverage_distribution": {"no_coverage": 6},
        "unassigned_jobs_total": 10,
        "unsupported_operational_zones": [{"postcode_prefix": "CF10", "unassigned_jobs": 4}],
    }
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(return_value=[])

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_execution_recovery_v1("c1", network_audit=audit)

    assert out["workflow_blockage_vs_execution_capacity"]["execution_capacity_dominant"] is True
    assert any(a.get("blockage_class") == "execution_capacity_blockage" for a in out.get("recovery_actions") or [])
