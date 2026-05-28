"""Tests for operational continuation and risk-signal WO idempotency."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.operational_continuation_service import (
    build_continuation_envelope,
    resolve_continuation_for_risk_signal,
)
from services.risk_signal_wo_idempotency import replay_active_work_order_for_risk_signal


@pytest.mark.asyncio
async def test_build_continuation_envelope_includes_cta():
    wo = {"work_order_id": "wo-1", "status": "ASSIGNED", "work_order_kind": "MAINTENANCE"}
    env = build_continuation_envelope(
        existing_work_order_id="wo-1",
        existing_issue_id="iss-1",
        work_order=wo,
    )
    assert env["mode"] == "continuation"
    assert env["has_active_lineage"] is True
    assert env["continuation_cta"]["key"] == "view_workflow"
    assert "wo-1" in env["continuation_cta"]["url"]


@pytest.mark.asyncio
async def test_resolve_continuation_for_risk_signal_uses_propagation():
    signal = {
        "signal_id": "rs-1",
        "propagation": {"work_order_id": "wo-99", "issue_id": "iss-1"},
    }
    wo = {"work_order_id": "wo-99", "status": "ASSIGNED", "work_order_kind": "MAINTENANCE"}
    with patch("services.maintenance_service.get_work_order", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = wo
        out = await resolve_continuation_for_risk_signal(signal, "client-1")
    assert out["has_active_lineage"] is True
    assert out["existing_work_order_id"] == "wo-99"


@pytest.mark.asyncio
async def test_replay_active_work_order_for_risk_signal():
    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(return_value={"work_order_id": "wo-2"})
    with patch("database.database.get_db", return_value=mock_db):
        with patch("services.maintenance_service.get_work_order", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"work_order_id": "wo-2", "status": "ASSIGNED"}
            out = await replay_active_work_order_for_risk_signal("rs-2", "client-1")
    assert out is not None
    assert out["work_order_id"] == "wo-2"
    assert out.get("idempotent_replay") is True
