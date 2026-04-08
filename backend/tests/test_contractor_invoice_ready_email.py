"""Contractor invoice-ready email when work order becomes eligible for first invoice."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database as db_singleton
from services import maintenance_service as ms
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE
from services.work_order_pricing_constants import (
    PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
    PRICE_STATUS_APPROVED,
)


@pytest.mark.asyncio
async def test_completed_compliance_sends_invoice_ready_when_quoted_and_proof():
    work_order_id = "wo-inv-1"
    client_id = "cli-inv"
    contractor_id = "ctr-inv"
    prev = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-inv",
        "contractor_id": contractor_id,
        "status": "IN_PROGRESS",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "description": "Gas cert",
        "evidence_keys": ["k1"],
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_APPROVED,
        "quoted_price": 120.0,
        "price_currency": "GBP",
        "scheduled_at": "2030-01-01T10:00:00+00:00",
        "schedule_status": "confirmed",
    }
    after = {
        **prev,
        "status": "COMPLETED",
        "completed_at": "2026-04-02T14:00:00+00:00",
        "updated_at": "2026-04-02T14:00:00+00:00",
    }

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(side_effect=[dict(prev), dict(prev), dict(after)])
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(after))
    mock_db.invoices.find_one = AsyncMock(return_value=None)
    mock_db.properties.find_one = AsyncMock(
        return_value={"address_line_1": "9 Invoice Rd", "city": "York", "postcode": "YO1 1AA"}
    )
    mock_db.contractors.find_one = AsyncMock(
        return_value={"email": "ctr@example.com", "name": "Gas Co", "company_name": "Gas Co"}
    )
    mock_db.contractor_job_tokens.insert_one = AsyncMock(return_value=None)

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.work_order_schedule_service.assert_completion_schedule_policy"),
        patch("services.work_order_pricing_service.assert_may_transition_to_completed"),
        patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        patch("services.invoice_service.generate_secure_token", return_value="inv-tok-32chars-minimum___________"),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        out = await ms.update_work_order(work_order_id, status=ms.STATUS_COMPLETED)

    assert out and out.get("status") == "COMPLETED"
    inv_calls = [c for c in send_mock.await_args_list if c.kwargs.get("template_key") == "CONTRACTOR_INVOICE_READY"]
    assert len(inv_calls) == 1
    kw = inv_calls[0].kwargs
    assert kw.get("event_type") == "CONTRACTOR_INVOICE_READY"
    assert kw.get("idempotency_key") == "contractor_invoice_ready:wo-inv-1:2026-04-02T14:00:00+00:00"
    ctx = kw.get("context") or {}
    assert ctx.get("recipient") == "ctr@example.com"
    assert ctx.get("approved_price") == 120.0
    assert ctx.get("price_currency") == "GBP"
    assert ctx.get("secure_job_link") == "https://app.example.com/job?token=inv-tok-32chars-minimum___________"


@pytest.mark.asyncio
async def test_completed_skips_invoice_ready_when_invoice_exists():
    work_order_id = "wo-inv-2"
    client_id = "cli-inv"
    contractor_id = "ctr-inv"
    prev = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-inv",
        "contractor_id": contractor_id,
        "status": "IN_PROGRESS",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "description": "Gas cert",
        "evidence_keys": ["k1"],
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_APPROVED,
        "quoted_price": 50.0,
        "price_currency": "GBP",
        "scheduled_at": "2030-01-01T10:00:00+00:00",
        "schedule_status": "confirmed",
    }
    after = {**prev, "status": "COMPLETED", "completed_at": "2026-04-02T15:00:00+00:00"}

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(side_effect=[dict(prev), dict(prev), dict(after)])
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(after))
    mock_db.invoices.find_one = AsyncMock(return_value={"_id": "x"})

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.work_order_schedule_service.assert_completion_schedule_policy"),
        patch("services.work_order_pricing_service.assert_may_transition_to_completed"),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        await ms.update_work_order(work_order_id, status=ms.STATUS_COMPLETED)

    inv_calls = [c for c in send_mock.await_args_list if c.kwargs.get("template_key") == "CONTRACTOR_INVOICE_READY"]
    assert len(inv_calls) == 0


@pytest.mark.asyncio
async def test_verified_after_completed_skips_second_invoice_ready():
    """Completion already opened invoicing; move to VERIFIED should not send again."""
    work_order_id = "wo-inv-3"
    client_id = "cli-inv"
    contractor_id = "ctr-inv"
    prev = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-inv",
        "contractor_id": contractor_id,
        "status": "COMPLETED",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "description": "Gas cert",
        "evidence_keys": ["k1"],
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_APPROVED,
        "quoted_price": 50.0,
        "price_currency": "GBP",
        "completed_at": "2026-04-01T10:00:00+00:00",
    }
    after = {**prev, "status": "VERIFIED", "updated_at": "2026-04-03T10:00:00+00:00"}

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(return_value=dict(prev))
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(after))
    mock_db.invoices.find_one = AsyncMock(return_value=None)

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        await ms.update_work_order(work_order_id, status=ms.STATUS_VERIFIED)

    inv_calls = [c for c in send_mock.await_args_list if c.kwargs.get("template_key") == "CONTRACTOR_INVOICE_READY"]
    assert len(inv_calls) == 0
