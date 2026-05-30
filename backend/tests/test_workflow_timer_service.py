"""Tests for canonical workflow timer stall detection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.workflow_timer_service import work_order_stall_context


def test_stall_context_awaiting_contractor_quote():
    now = datetime.now(timezone.utc)
    wo = {
        "work_order_id": "w1",
        "status": "ASSIGNED",
        "price_status": "AWAITING_QUOTE",
        "awaiting_quote_since": (now - timedelta(hours=10)).isoformat(),
    }
    ctx = work_order_stall_context(wo, now=now)
    assert ctx
    assert ctx["stall_type"] == "awaiting_contractor_quote"
    assert ctx["waiting_on"] == "contractor"
    assert ctx["age_hours"] >= 9.9


def test_stall_context_none_when_terminal():
    wo = {
        "work_order_id": "w2",
        "status": "COMPLETED",
        "awaiting_quote_since": datetime.now(timezone.utc).isoformat(),
    }
    assert work_order_stall_context(wo) is None


def test_stall_context_landlord_quote_review():
    now = datetime.now(timezone.utc)
    wo = {
        "work_order_id": "w3",
        "status": "ASSIGNED",
        "price_status": "QUOTED",
        "awaiting_landlord_quote_response_since": (now - timedelta(hours=80)).isoformat(),
    }
    ctx = work_order_stall_context(wo, now=now)
    assert ctx
    assert ctx["stall_type"] == "awaiting_landlord_quote_response"
    assert ctx["waiting_on"] == "landlord"
