"""
INV-RS-001, INV-RS-002, INV-RS-005: risk signal lifecycle timestamp authority.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.risk_signal_service import (
    STATUS_ACKNOWLEDGED,
    STATUS_RESOLVED,
    update_signal_status,
)


@pytest.mark.asyncio
async def test_update_signal_status_acknowledged_sets_acknowledged_at_inv_rs_001():
    mock_db = MagicMock()
    mock_db.risk_signals.find_one = AsyncMock(
        return_value={"signal_id": "rs1", "client_id": "c1", "status": "active"}
    )
    updated = {
        "signal_id": "rs1",
        "client_id": "c1",
        "status": STATUS_ACKNOWLEDGED,
        "acknowledged_at": "2026-05-27T12:00:00+00:00",
        "resolved_at": None,
    }
    mock_db.risk_signals.find_one_and_update = AsyncMock(return_value=updated)

    with patch("services.risk_signal_service.database.get_db", return_value=mock_db):
        with patch("services.risk_signal_service.create_audit_log", new_callable=AsyncMock):
            with patch(
                "services.compliance_outcome_engine.apply_action_outcome",
                new_callable=AsyncMock,
                return_value={},
            ):
                out = await update_signal_status("rs1", "c1", STATUS_ACKNOWLEDGED)

    assert out is not None
    assert out.get("acknowledged_at")
    assert out.get("resolved_at") is None
    set_payload = mock_db.risk_signals.find_one_and_update.await_args[0][1]["$set"]
    assert "acknowledged_at" in set_payload
    assert "resolved_at" not in set_payload


@pytest.mark.asyncio
async def test_update_signal_status_resolved_sets_resolved_at_inv_rs_002():
    mock_db = MagicMock()
    mock_db.risk_signals.find_one = AsyncMock(
        return_value={"signal_id": "rs2", "client_id": "c1", "status": STATUS_ACKNOWLEDGED}
    )
    updated = {
        "signal_id": "rs2",
        "client_id": "c1",
        "status": STATUS_RESOLVED,
        "acknowledged_at": "2026-05-27T11:00:00+00:00",
        "resolved_at": "2026-05-27T12:00:00+00:00",
    }
    mock_db.risk_signals.find_one_and_update = AsyncMock(return_value=updated)

    with patch("services.risk_signal_service.database.get_db", return_value=mock_db):
        with patch(
            "services.risk_signal_service._risk_signal_has_execution_closure",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with patch("services.risk_signal_service.create_audit_log", new_callable=AsyncMock):
                with patch(
                    "services.compliance_outcome_engine.apply_action_outcome",
                    new_callable=AsyncMock,
                    return_value={},
                ):
                    out = await update_signal_status("rs2", "c1", STATUS_RESOLVED)

    assert out is not None
    assert out.get("resolved_at")
    set_payload = mock_db.risk_signals.find_one_and_update.await_args[0][1]["$set"]
    assert "resolved_at" in set_payload


@pytest.mark.asyncio
async def test_resolve_without_closure_or_dismiss_raises_inv_rs_005():
    mock_db = MagicMock()
    mock_db.risk_signals.find_one = AsyncMock(
        return_value={"signal_id": "rs3", "client_id": "c1", "status": "active"}
    )

    with patch("services.risk_signal_service.database.get_db", return_value=mock_db):
        with patch(
            "services.risk_signal_service._risk_signal_has_execution_closure",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with pytest.raises(ValueError, match="dismiss"):
                await update_signal_status("rs3", "c1", STATUS_RESOLVED)
