"""
OPERATIONAL-CLOSURE-CONVERSION-01 unit tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.operational_closure_conversion_service import (
    score_issue_closure,
    score_work_order_closure,
    score_risk_closure,
    build_deadlock_reduction_v1,
    build_verification_throughput_v1,
    merge_momentum_with_compliance_actions,
    ACTION_CLOSURE_CONTRACTOR_DEADLOCK,
)


def test_score_wo_contractor_deadlock_low_momentum():
    sc = score_work_order_closure({"work_order_id": "w1", "status": "OPEN", "contractor_id": None})
    assert "contractor_deadlock" in sc["closure_blockers"]
    assert sc["likely_to_stall"] is True
    assert sc["operational_momentum_score"] < 0.35


def test_score_wo_completed_unverified_fake_progress():
    sc = score_work_order_closure(
        {"work_order_id": "w2", "status": "COMPLETED", "completed_at": "2026-01-01T00:00:00+00:00"}
    )
    assert sc["fake_progress_risk"] is True
    assert sc["verification_blockage"] is True


def test_score_risk_resolved_without_timestamp():
    sc = score_risk_closure({"signal_id": "r1", "status": "resolved"})
    assert sc["fake_progress_risk"] is True
    assert "fake_resolved_timestamp" in sc["closure_blockers"]


def test_merge_momentum_prioritises_closure_actions():
    momentum = [
        {"action_type": ACTION_CLOSURE_CONTRACTOR_DEADLOCK, "priority": 92, "related_work_order_id": "w1", "title": "A"},
    ]
    compliance = [
        {"action_type": "open_work_order", "priority": 50, "related_work_order_id": "w1", "title": "B"},
        {"action_type": "open_issue", "priority": 40, "related_issue_id": "i1", "title": "C"},
    ]
    merged = merge_momentum_with_compliance_actions(momentum, compliance, cap=10)
    assert merged[0]["action_type"] == ACTION_CLOSURE_CONTRACTOR_DEADLOCK
    assert len(merged) == 2


@pytest.mark.asyncio
async def test_deadlock_reduction_groups_contractor_and_verification():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(
        return_value=[{"signal_id": "r1", "status": "resolved"}]
    )
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {"work_order_id": "w1", "status": "OPEN", "client_id": "c1"},
            {"work_order_id": "w2", "status": "COMPLETED", "completed_at": "2026-01-01T00:00:00+00:00"},
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_deadlock_reduction_v1("c1")

    dtypes = [g["deadlock_type"] for g in out.get("groups") or []]
    assert "contractor_deadlock" in dtypes
    assert "verification_deadlock" in dtypes


@pytest.mark.asyncio
async def test_verification_throughput_queue():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {"work_order_id": "w1", "status": "COMPLETED", "completed_at": "2026-01-01T00:00:00+00:00"},
            {"work_order_id": "w2", "status": "VERIFIED", "verified_at": "2026-02-01T00:00:00+00:00"},
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_verification_throughput_v1("c1")

    assert out["verification_queue_count"] == 1
    assert out["completed_without_verification_count"] == 1


def test_score_issue_ready_for_work_order():
    sc = score_issue_closure({"issue_id": "i1", "status": "ready_for_work_order", "updated_at": "2026-05-01T00:00:00+00:00"})
    assert sc["closure_likelihood"] >= 0.5
    assert sc["entity_type"] == "issue"
