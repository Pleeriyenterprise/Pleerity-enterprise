"""Predictive operational risk lifecycle governance."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.risk_signal_operational_history_governance import (
    MIN_COMPLETED_OPERATIONAL_CYCLES,
    client_predictive_operational_history_eligible,
    customer_safe_reasons,
    filter_qualifying_operational_records,
    qualifies_for_predictive_operational_count,
)


def test_qualifies_excludes_compliance_bridge_records():
    assert not qualifies_for_predictive_operational_count(
        {"source": "system", "created_from": "compliance", "operational_root_key": "gap:1"}
    )
    assert qualifies_for_predictive_operational_count(
        {"source": "client", "created_from": "manual", "description": "Leaking tap"}
    )


def test_filter_qualifying_operational_records():
    rows = [
        {"issue_id": "a", "source": "client"},
        {"issue_id": "b", "source": "system", "created_from": "compliance"},
    ]
    out = filter_qualifying_operational_records(rows)
    assert len(out) == 1
    assert out[0]["issue_id"] == "a"


def test_customer_safe_reasons_recurring():
    raw = ["Same asset/category has 6 issues or work orders in the last 12 months"]
    out = customer_safe_reasons(raw, "Recurring Repairs Risk")
    assert "6 similar maintenance reports" in out[0]
    assert "underlying cause" in out[0].lower()


@pytest.mark.asyncio
async def test_client_not_eligible_without_completed_cycles():
    mock_db = MagicMock()

    async def empty_iter(*args, **kwargs):
        if False:
            yield {}

    mock_db.work_orders.find.return_value = empty_iter()
    mock_db.maintenance_issues.find.return_value = empty_iter()

    eligible, metrics = await client_predictive_operational_history_eligible(mock_db, "c1")
    assert eligible is False
    assert metrics["completed_operational_cycles"] == 0
    assert metrics["min_required_cycles"] == MIN_COMPLETED_OPERATIONAL_CYCLES


@pytest.mark.asyncio
async def test_client_eligible_with_completed_work_orders():
    mock_db = MagicMock()

    async def wo_iter():
        for _ in range(MIN_COMPLETED_OPERATIONAL_CYCLES):
            yield {"work_order_id": "wo", "source": "client", "created_from": "manual"}

    async def issue_iter():
        if False:
            yield {}

    mock_db.work_orders.find.return_value = wo_iter()
    mock_db.maintenance_issues.find.return_value = issue_iter()

    eligible, metrics = await client_predictive_operational_history_eligible(mock_db, "c1")
    assert eligible is True
    assert metrics["completed_operational_cycles"] >= MIN_COMPLETED_OPERATIONAL_CYCLES
