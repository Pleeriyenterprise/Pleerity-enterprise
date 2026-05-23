"""G10: client PATCH cannot reopen terminal maintenance work orders."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from services.maintenance_service import STATUS_COMPLETED, update_work_order


def test_client_cannot_reopen_completed_work_order():
    async def _run():
        prev = {"work_order_id": "wo-t1", "status": STATUS_COMPLETED, "client_id": "c1", "work_order_kind": "MAINTENANCE"}
        mock_db = MagicMock()
        mock_db.work_orders.find_one = AsyncMock(return_value=prev)
        with patch("services.maintenance_service.database.get_db", return_value=mock_db):
            try:
                await update_work_order("wo-t1", status="OPEN")
                assert False, "expected ValueError"
            except ValueError as exc:
                assert "terminal state" in str(exc).lower()

    asyncio.run(_run())


def test_admin_may_reopen_when_allowed():
    async def _run():
        prev = {"work_order_id": "wo-t2", "status": STATUS_COMPLETED, "client_id": "c1", "work_order_kind": "MAINTENANCE"}
        updated = {"work_order_id": "wo-t2", "status": "OPEN", "client_id": "c1"}
        mock_db = MagicMock()
        mock_db.work_orders.find_one = AsyncMock(side_effect=[prev, prev, updated])
        mock_db.work_orders.update_one = AsyncMock()
        mock_db.work_orders.find_one_and_update = AsyncMock(return_value=updated)
        with (
            patch("services.maintenance_service.database.get_db", return_value=mock_db),
            patch("services.maintenance_service.get_work_order", AsyncMock(return_value=updated)),
        ):
            out = await update_work_order("wo-t2", status="OPEN", allow_terminal_reopen=True)
        assert out is not None

    asyncio.run(_run())
