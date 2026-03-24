"""Regression tests for value/trust fixes: open work orders in tasks, issues count, paid spend."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_open_work_order_action_wired_in_unified_tasks():
    from services import priority_actions as pa
    from services.unified_tasks_service import ACTION_TO_SOURCE, ACTION_OPEN_WORK_ORDER

    assert pa.ACTION_OPEN_WORK_ORDER == "open_work_order"
    assert ACTION_TO_SOURCE[pa.ACTION_OPEN_WORK_ORDER] == "work_order"


def test_count_open_issues_queries_issues_collection_not_work_orders():
    from services import maintenance_issues_service as mis

    async def _run():
        mock_db = MagicMock()
        mock_db.maintenance_issues.count_documents = AsyncMock(return_value=7)
        with patch.object(mis.database, "get_db", return_value=mock_db):
            n = await mis.count_open_issues("client-abc")
        assert n == 7
        mock_db.maintenance_issues.count_documents.assert_awaited_once()
        q = mock_db.maintenance_issues.count_documents.await_args[0][0]
        assert q["client_id"] == "client-abc"
        assert "$in" in q["status"]

    asyncio.run(_run())


def test_spend_this_month_uses_paid_status_and_aggregate():
    from services import approval_service as aprv

    async def _run():
        mock_db = MagicMock()
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[{"_id": "GBP", "total": 125.5, "count": 2}])
        mock_db.invoices.aggregate = MagicMock(return_value=cursor)
        with patch.object(aprv.database, "get_db", return_value=mock_db):
            out = await aprv.get_maintenance_invoice_spend_this_month("cid-1")
        assert out["total_amount"] == 125.5
        assert out["invoice_count"] == 2
        assert out["currency"] == "GBP"
        pipeline = mock_db.invoices.aggregate.call_args[0][0]
        match = pipeline[0]["$match"]
        assert match["client_id"] == "cid-1"
        assert match["status"] == aprv.STATUS_PAID
        assert "$gte" in match["paid_at"]
        assert "$lt" in match["paid_at"]

    asyncio.run(_run())
