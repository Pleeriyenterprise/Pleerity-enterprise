"""
INV-JO-002, INV-JO-010: work order verification timestamps and issue closure routing.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services import maintenance_service


@pytest.mark.asyncio
async def test_update_work_order_verified_sets_verified_at_inv_jo_002():
    mock_db = MagicMock()
    prev = {"work_order_id": "wo1", "client_id": "c1", "status": "COMPLETED", "work_order_kind": "MAINTENANCE"}
    result = {**prev, "status": "VERIFIED", "verified_at": "2026-05-27T12:00:00+00:00"}

    mock_db.work_orders.find_one = AsyncMock(return_value=prev)
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=result)

    patches = [
        patch("services.maintenance_service.database.get_db", return_value=mock_db),
        patch(
            "services.work_order_contractor_routing_service.invalidate_pending_routing_for_work_order",
            new_callable=AsyncMock,
        ),
        patch("services.webhook_service.fire_work_order_status_changed", new_callable=AsyncMock),
        patch("services.invoice_service.maybe_send_contractor_invoice_ready_notification", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value={}),
    ]
    for p in patches:
        p.start()
    try:
        out = await maintenance_service.update_work_order("wo1", status="VERIFIED", assigned_by="admin")
    finally:
        for p in patches:
            p.stop()

    assert out is not None
    set_fields = mock_db.work_orders.find_one_and_update.await_args[0][1]["$set"]
    assert set_fields.get("verified_at")


@pytest.mark.asyncio
async def test_verified_closes_issue_via_update_issue_inv_jo_010():
    mock_db = MagicMock()
    prev = {
        "work_order_id": "wo2",
        "client_id": "c1",
        "status": "COMPLETED",
        "issue_id": "iss1",
        "work_order_kind": "MAINTENANCE",
    }
    result = {**prev, "status": "VERIFIED", "verified_at": "2026-05-27T12:00:00+00:00"}

    mock_db.work_orders.find_one = AsyncMock(return_value=prev)
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=result)

    with patch("services.maintenance_service.database.get_db", return_value=mock_db):
        with patch(
            "services.work_order_contractor_routing_service.invalidate_pending_routing_for_work_order",
            new_callable=AsyncMock,
        ):
            with patch("services.webhook_service.fire_work_order_status_changed", new_callable=AsyncMock):
                with patch(
                    "services.invoice_service.maybe_send_contractor_invoice_ready_notification",
                    new_callable=AsyncMock,
                ):
                    with patch(
                        "services.compliance_outcome_engine.apply_action_outcome",
                        new_callable=AsyncMock,
                        return_value={},
                    ):
                        with patch(
                            "services.maintenance_issues_service.update_issue",
                            new_callable=AsyncMock,
                        ) as mock_close:
                            await maintenance_service.update_work_order(
                                "wo2", status="VERIFIED", assigned_by="admin1"
                            )

    mock_close.assert_awaited_once()
    kw = mock_close.await_args.kwargs
    assert kw["issue_id"] == "iss1"
    assert kw["status"] == "closed"
    assert kw.get("closed_by")
