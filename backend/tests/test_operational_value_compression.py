"""
OPERATIONAL-VALUE-COMPRESSION-01 unit tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.operational_value_compression_service import (
    CONSEQUENCE_OPERATIONALLY_DANGEROUS,
    CONSEQUENCE_RECURRING_DEGRADATION,
    CONSEQUENCE_STALE_OPERATIONAL_DEBT,
    classify_issue_consequence,
    classify_risk_consequence,
    classify_work_order_consequence,
    build_pressure_compression_v1,
    attach_consequence_to_priority_action,
)


def test_classify_risk_recurring_degradation():
    c = classify_risk_consequence({"risk_type": "Recurring Repairs Risk", "status": "active", "risk_level": "medium"})
    assert c["consequence_category"] == CONSEQUENCE_RECURRING_DEGRADATION
    assert c["if_ignored"]


def test_classify_issue_stale_debt():
    old = "2020-01-01T00:00:00+00:00"
    c = classify_issue_consequence({"status": "triaged", "updated_at": old, "severity": "low"})
    assert c["consequence_category"] == CONSEQUENCE_STALE_OPERATIONAL_DEBT


def test_classify_wo_contractor_deadlock():
    c = classify_work_order_consequence({"status": "OPEN", "contractor_id": None})
    assert c["consequence_category"] == CONSEQUENCE_OPERATIONALLY_DANGEROUS


def test_attach_consequence_to_priority_action():
    a = attach_consequence_to_priority_action({"action_type": "work_order_sla_breached", "title": "SLA"})
    assert a.get("consequence_category") == CONSEQUENCE_OPERATIONALLY_DANGEROUS


@pytest.mark.asyncio
async def test_pressure_compression_groups_contractor_deadlock():
    mock_db = MagicMock()
    mock_db.maintenance_issues.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.risk_signals.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.work_orders.find.return_value.to_list = AsyncMock(
        return_value=[
            {"work_order_id": "wo1", "status": "OPEN", "client_id": "c1", "property_id": "p1"},
            {"work_order_id": "wo2", "status": "SCHEDULED", "client_id": "c1", "property_id": "p1"},
        ]
    )

    with patch("services.operational_value_compression_service.database.get_db", return_value=mock_db):
        out = await build_pressure_compression_v1("c1")

    keys = [g["group_key"] for g in out.get("groups") or []]
    assert "contractor_deadlock" in keys
    assert out["cognitive_load"]["compression_ratio"] >= 1.0


@pytest.mark.asyncio
async def test_issue_reopen_raises_value_error():
    from services.maintenance_issues_service import update_issue, STATUS_CLOSED

    mock_db = MagicMock()
    issue = {"issue_id": "i1", "client_id": "c1", "status": STATUS_CLOSED, "description": "x", "property_id": "p1"}

    with patch("services.maintenance_issues_service.database.get_db", return_value=mock_db):
        with patch("services.maintenance_issues_service.get_issue", new_callable=AsyncMock, return_value=issue):
            with pytest.raises(ValueError, match="cannot be reopened"):
                await update_issue("i1", "c1", status="open")
