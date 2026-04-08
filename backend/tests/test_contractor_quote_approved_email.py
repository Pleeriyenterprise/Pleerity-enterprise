"""Contractor quote-approved email when client approves (orchestrator + idempotency)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database as db_singleton
from services.work_order_pricing_constants import (
    PRICE_STATUS_QUOTED,
    PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
    PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED,
)
from services.work_order_pricing_service import approve_quote_for_work_order


@pytest.mark.asyncio
async def test_approve_quote_sends_contractor_quote_approved_email():
    work_order_id = "wo-qa-1"
    client_id = "cli-qa"
    contractor_id = "ctr-qa"
    now = datetime(2026, 4, 2, 15, 30, 0, 0, tzinfo=timezone.utc)

    wo_before = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-qa",
        "contractor_id": contractor_id,
        "description": "Replace boiler",
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_QUOTED,
        "work_order_kind": "COMPLIANCE",
        "quoted_price": 2500.0,
        "price_currency": "GBP",
        "quote_notes": None,
    }

    wo_after = {
        **wo_before,
        "price_status": "APPROVED",
        "quote_approved_at": now,
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
        return_value={"address_line_1": "2 Approve Rd", "city": "Bristol", "postcode": "BS1 1AA"}
    )
    mock_db.contractors.find_one = AsyncMock(
        return_value={"email": "contractor@qa.example", "name": "Boiler Co", "company_name": "Boiler Co Ltd"}
    )
    mock_db.contractor_job_tokens.insert_one = AsyncMock(return_value=None)

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
        patch("services.work_order_pricing_service.generate_secure_token", return_value="approve-tok-32chars-minimum_______"),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        out = await approve_quote_for_work_order(work_order_id, client_id, actor_id="pu-qa")

    assert out.get("price_status") == "APPROVED"
    assert send_mock.await_count == 1
    kwargs = send_mock.await_args.kwargs
    assert kwargs.get("template_key") == "CONTRACTOR_QUOTE_APPROVED"
    assert kwargs.get("idempotency_key") == f"contractor_quote_approved:{work_order_id}:{now.isoformat()}"
    assert kwargs.get("event_type") == "CONTRACTOR_QUOTE_APPROVED"
    assert kwargs.get("client_id") == client_id
    ctx = kwargs.get("context") or {}
    assert ctx.get("recipient") == "contractor@qa.example"
    assert ctx.get("approved_price") == 2500.0
    assert ctx.get("price_currency") == "GBP"
    assert ctx.get("is_compliance") is True
    assert "certificate" in (ctx.get("next_action") or "").lower()
    assert ctx.get("secure_job_link") == "https://app.example.com/job?token=approve-tok-32chars-minimum_______"


@pytest.mark.asyncio
async def test_approve_quote_skips_email_when_no_contractor():
    work_order_id = "wo-qa-nc"
    client_id = "cli-qa"
    now = datetime(2026, 4, 2, 16, 0, 0, 0, tzinfo=timezone.utc)

    wo_before = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-qa",
        "contractor_id": "",
        "description": "No contractor",
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_QUOTED,
        "work_order_kind": "COMPLIANCE",
        "quoted_price": 100.0,
        "price_currency": "GBP",
    }
    wo_after = {**wo_before, "price_status": "APPROVED", "quote_approved_at": now}

    fetch_n = 0

    async def find_one_wo(query, projection=None):
        nonlocal fetch_n
        if query.get("work_order_id") != work_order_id:
            return None
        fetch_n += 1
        return dict(wo_before) if fetch_n == 1 else dict(wo_after)

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(side_effect=find_one_wo)
    mock_db.work_orders.update_one = AsyncMock(return_value={"modified_count": 1})

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    class _FixedDateTime:
        @staticmethod
        def now(tz=None):
            return now

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.work_order_pricing_service.create_audit_log", new_callable=AsyncMock),
        patch("services.work_order_pricing_service.datetime", _FixedDateTime()),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        await approve_quote_for_work_order(work_order_id, client_id, actor_id="pu-qa")

    send_mock.assert_not_called()


@pytest.mark.asyncio
async def test_maintenance_inspection_next_action_before_inspection_complete():
    from services.work_order_pricing_service import _next_action_line_for_quote_approved

    wo = {
        "work_order_kind": "MAINTENANCE",
        "pricing_mode": PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED,
        "inspection_completed_at": None,
    }
    line = _next_action_line_for_quote_approved(wo)
    assert "inspection" in line.lower()
