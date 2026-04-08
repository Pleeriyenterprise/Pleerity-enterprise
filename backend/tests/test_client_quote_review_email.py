"""Client quote review email on contractor submit (orchestrator + idempotency)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database as db_singleton
from services.work_order_pricing_constants import (
    PRICE_STATUS_AWAITING_QUOTE,
    PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
)
from services.work_order_pricing_service import submit_quote_for_work_order


@pytest.mark.asyncio
async def test_submit_quote_sends_client_quote_review_email_once_per_submission():
    work_order_id = "wo-qr-1"
    client_id = "cli-qr"
    contractor_id = "ctr-qr"
    now = datetime(2026, 4, 2, 12, 0, 0, 123456, tzinfo=timezone.utc)

    wo_before = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-qr",
        "contractor_id": contractor_id,
        "description": "Fix leak",
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_AWAITING_QUOTE,
        "work_order_kind": "COMPLIANCE",
    }

    wo_after = {
        **wo_before,
        "quoted_price": 199.5,
        "price_currency": "GBP",
        "quote_notes": "Parts included",
        "price_status": "QUOTED",
        "quote_submitted_at": now,
        "quote_approved_at": None,
        "quote_rejected_at": None,
        "quote_rejection_reason": None,
    }

    fetch_n = 0

    async def find_one_wo(query, projection=None):
        nonlocal fetch_n
        if query.get("work_order_id") != work_order_id:
            return None
        fetch_n += 1
        if fetch_n == 1:
            return dict(wo_before)
        return dict(wo_after)

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(side_effect=find_one_wo)
    mock_db.work_orders.update_one = AsyncMock(return_value={"modified_count": 1})
    mock_db.properties.find_one = AsyncMock(
        return_value={"address_line_1": "1 Test Rd", "city": "London", "postcode": "E1 1AA"}
    )
    mock_db.contractors.find_one = AsyncMock(
        return_value={"name": "Ace Repairs", "company_name": "Ace Repairs Ltd"}
    )
    mock_db.clients.find_one = AsyncMock(
        return_value={
            "contact_email": "owner@client.example",
            "full_name": "Jamie Client",
            "customer_reference": "REF-99",
        }
    )
    mock_db.portal_users.find_one = AsyncMock(return_value=None)

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    class _FixedDateTime:
        @staticmethod
        def now(tz=None):
            return now

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.work_order_pricing_service.create_audit_log", new_callable=AsyncMock),
        patch("services.work_order_pricing_service.datetime", _FixedDateTime()),
        patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        out = await submit_quote_for_work_order(
            work_order_id,
            contractor_id,
            amount=199.5,
            currency="GBP",
            notes="Parts included",
        )

    assert out.get("price_status") == "QUOTED"
    assert send_mock.await_count == 1
    kwargs = send_mock.await_args.kwargs
    assert kwargs.get("template_key") == "CLIENT_QUOTE_REVIEW_REQUIRED"
    assert kwargs.get("idempotency_key") == f"client_quote_review:{work_order_id}:{now.isoformat()}"
    assert kwargs.get("event_type") == "CLIENT_QUOTE_REVIEW_REQUIRED"
    assert kwargs.get("client_id") == client_id
    ctx = kwargs.get("context") or {}
    assert ctx.get("recipient") == "owner@client.example"
    assert ctx.get("client_job_link") == f"https://app.example.com/operations/jobs/{work_order_id}"
    assert ctx.get("contractor_name") == "Ace Repairs"
    assert ctx.get("quoted_price") == 199.5
    assert ctx.get("price_currency") == "GBP"
    assert ctx.get("quote_notes") == "Parts included"
