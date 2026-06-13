"""
EXECUTION-CAPACITY-AND-NETWORK-RELIABILITY-01 unit tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.execution_capacity_network_service import (
    build_assignment_conversion_v1,
    build_execution_capacity_bundle_v1,
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


@pytest.mark.asyncio
async def test_build_execution_capacity_bundle_v1_passes_assignment_before_kpis():
    """Regression: assignment/quote must exist before momentum KPIs (UnboundLocalError)."""
    audit = {"unassigned_jobs_total": 0, "coverage_distribution": {"no_coverage": 0}}
    assignment = {"open_unassigned_count": 0, "assignment_conversion_rate": 0.5, "contractor_reliability_score": 0.8}
    quote = {"quote_turnaround_score": 0.7}
    recovery = {"recovery_actions": [{"headline": "Test bottleneck"}]}
    kpis = {"execution_capacity_confidence": 0.75}
    entropy = {"coverage_count": 1}

    with (
        patch(
            "services.execution_capacity_network_service.build_contractor_network_audit_v1",
            new_callable=AsyncMock,
            return_value=audit,
        ),
        patch(
            "services.execution_capacity_network_service.build_assignment_conversion_v1",
            new_callable=AsyncMock,
            return_value=assignment,
        ) as mock_assignment,
        patch(
            "services.execution_capacity_network_service.build_quote_throughput_v1",
            new_callable=AsyncMock,
            return_value=quote,
        ) as mock_quote,
        patch(
            "services.execution_capacity_network_service.build_execution_recovery_v1",
            new_callable=AsyncMock,
            return_value=recovery,
        ),
        patch(
            "services.execution_capacity_network_service.build_execution_momentum_kpis_v1",
            new_callable=AsyncMock,
            return_value=kpis,
        ) as mock_kpis,
        patch(
            "services.execution_capacity_network_service.build_execution_entropy_coverage_v1",
            new_callable=AsyncMock,
            return_value=entropy,
        ),
        patch(
            "services.execution_capacity_network_service.fetch_execution_capacity_priority_actions",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        out = await build_execution_capacity_bundle_v1("c1")

    assert out["assignment_conversion_v1"] == assignment
    assert out["execution_momentum_kpis_v1"] == kpis
    mock_assignment.assert_awaited_once()
    mock_quote.assert_awaited_once()
    mock_kpis.assert_awaited_once()
    _args, kwargs = mock_kpis.call_args
    assert kwargs["assignment"] == assignment
    assert kwargs["quote"] == quote
