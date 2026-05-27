"""
BACKLOG-REDUCTION-RUNTIME-01 unit tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.backlog_reduction_runtime_service import (
    build_contractor_throughput_v1,
    build_verification_throughput_execution_v1,
    build_staging_simulation_coverage_v1,
    build_operational_momentum_validation_v1,
)


@pytest.mark.asyncio
async def test_contractor_throughput_unassigned_escalation():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {
                "work_order_id": "w1",
                "status": "OPEN",
                "created_at": "2020-01-01T00:00:00+00:00",
                "client_id": "c1",
            },
            {
                "work_order_id": "w2",
                "status": "IN_PROGRESS",
                "contractor_id": "ctr1",
                "client_id": "c1",
            },
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_contractor_throughput_v1("c1")

    assert out["unassigned_count"] == 1
    assert out["critical_unassigned_count"] == 1
    assert out["escalation_headline"]


@pytest.mark.asyncio
async def test_verification_throughput_execution_critical():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {
                "work_order_id": "w1",
                "status": "COMPLETED",
                "completed_at": "2020-01-01T00:00:00+00:00",
                "client_id": "c1",
            },
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_verification_throughput_execution_v1("c1")

    assert out["critical_verification_count"] == 1
    assert out["verification_queue_count"] == 1


@pytest.mark.asyncio
async def test_momentum_validation_deltas():
    baseline = {"unassigned_jobs": 24, "fake_progress_chains": 40}
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(
        return_value=[{"signal_id": "r1", "status": "resolved"}]
    )
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[{"work_order_id": "w1", "status": "OPEN", "client_id": "c1"}]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_operational_momentum_validation_v1("c1", baseline=baseline)

    assert out["deltas_vs_baseline"]["unassigned_jobs"] == -23


@pytest.mark.asyncio
async def test_simulation_coverage_detects_patterns():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(
        return_value=[
            {
                "issue_id": "i1",
                "status": "triaged",
                "updated_at": "2020-01-01T00:00:00+00:00",
            }
        ]
    )
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {"work_order_id": "w1", "status": "AWAITING_PARTS"},
            {"work_order_id": "w2", "status": "COMPLETED", "reschedule_count": 3},
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_staging_simulation_coverage_v1("c1")

    assert out["scenarios"]["awaiting_parts_loops"]["present"] is True
    assert out["scenarios"]["stale_review_escalation"]["present"] is True
