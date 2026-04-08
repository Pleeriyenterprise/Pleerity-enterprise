"""Client invoice review email when contractor submits or resubmits an invoice."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database as db_singleton
from services import maintenance_service as ms
from services.invoice_service import SOURCE_CONTRACTOR, create_invoice
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE
from services.work_order_pricing_constants import (
    PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
    PRICE_STATUS_APPROVED,
)


@pytest.mark.asyncio
async def test_contractor_create_invoice_sends_client_review_email():
    wo = {
        "work_order_id": "wo-cir-1",
        "client_id": "cli-cir",
        "property_id": "prop-cir",
        "description": "Boiler service",
        "status": ms.STATUS_VERIFIED,
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_APPROVED,
        "quoted_price": 200.0,
        "price_currency": "GBP",
    }
    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(return_value=dict(wo))
    mock_db.contractors.find_one = AsyncMock(return_value={"contractor_id": "ctr-cir"})
    mock_db.properties.find_one = AsyncMock(return_value={"_id": "x"})
    mock_db.invoices.insert_one = AsyncMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={"contact_email": "client@cir.example", "full_name": "Client Org"}
    )
    mock_db.counters.find_one_and_update = AsyncMock(return_value={"seq": 1})

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))
    fixed_now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    class _DT:
        @staticmethod
        def now(tz=None):
            return fixed_now

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.invoice_service.datetime", _DT()),
        patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        patch("services.invoice_service.create_audit_log", new_callable=AsyncMock),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        doc = await create_invoice(
            client_id="cli-cir",
            property_id="prop-cir",
            contractor_id="ctr-cir",
            work_order_id="wo-cir-1",
            submitted_amount=200.0,
            currency="GBP",
            source=SOURCE_CONTRACTOR,
            created_by_id="ctr-cir",
            invoice_number="PLE-INV-2026-000001",
        )

    assert doc.get("invoice_id")
    assert send_mock.await_count == 1
    kw = send_mock.await_args.kwargs
    assert kw.get("template_key") == "CLIENT_INVOICE_REVIEW_REQUIRED"
    assert kw.get("event_type") == "CLIENT_INVOICE_REVIEW_REQUIRED"
    iid = doc["invoice_id"]
    assert kw.get("idempotency_key") == f"client_invoice_review:{iid}:2026-05-01T12:00:00+00:00"
    ctx = kw.get("context") or {}
    assert ctx.get("recipient") == "client@cir.example"
    assert ctx.get("has_agreed_price") is True
    assert "invoice_id=" in (ctx.get("invoice_review_link") or "")


@pytest.mark.asyncio
async def test_admin_create_invoice_skips_client_review_email():
    wo = {
        "work_order_id": "wo-cir-2",
        "client_id": "cli-cir",
        "property_id": "prop-cir",
        "description": "Repair",
        "status": ms.STATUS_VERIFIED,
        "work_order_kind": "MAINTENANCE",
    }
    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(return_value=dict(wo))
    mock_db.contractors.find_one = AsyncMock(return_value={"contractor_id": "ctr"})
    mock_db.properties.find_one = AsyncMock(return_value={"_id": "x"})
    mock_db.invoices.insert_one = AsyncMock()
    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.invoice_service.create_audit_log", new_callable=AsyncMock),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        await create_invoice(
            client_id="cli-cir",
            property_id="prop-cir",
            contractor_id="ctr",
            work_order_id="wo-cir-2",
            submitted_amount=50.0,
            source="admin",
            created_by_id="admin-1",
            invoice_number="ADM-1",
        )

    send_mock.assert_not_called()
