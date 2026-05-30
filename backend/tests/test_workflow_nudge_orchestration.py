"""Tests for workflow nudge guardrails and reconciliation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.workflow_nudge_guardrails import (
    assert_nudge_action_safe,
    assert_orchestration_allowed,
)
from services.workflow_nudge_reconciliation_service import reconcile_work_order_nudge
from services.workflow_timer_service import work_order_stall_context


def test_orchestration_allowed_types():
    assert_orchestration_allowed("auto_notify")
    assert_orchestration_allowed("auto_prioritise")
    assert_orchestration_allowed("recommend_only")
    with pytest.raises(ValueError):
        assert_orchestration_allowed("auto_approve")


def test_guardrails_forbid_authority_mutation():
    with pytest.raises(ValueError):
        assert_nudge_action_safe(automation_type="auto_notify", payload={"price_status": "APPROVED"})


@pytest.mark.asyncio
async def test_reconcile_suppresses_terminal_work_order():
    wo = {"work_order_id": "wo1", "status": "COMPLETED", "awaiting_quote_since": datetime.now(timezone.utc).isoformat()}
    decision = await reconcile_work_order_nudge(
        wo,
        nudge_key="quote_contractor_reminder",
        tier="T24",
        expected_stall_type="awaiting_contractor_quote",
        min_age_hours=24,
    )
    assert not decision.fire
    assert decision.suppress_reason == "entity_terminal"


@pytest.mark.asyncio
async def test_reconcile_suppresses_stall_mismatch():
    now = datetime.now(timezone.utc)
    wo = {
        "work_order_id": "wo2",
        "status": "ASSIGNED",
        "price_status": "QUOTED",
        "awaiting_landlord_quote_response_since": (now - timedelta(hours=30)).isoformat(),
    }
    stall = work_order_stall_context(wo)
    assert stall and stall["stall_type"] == "awaiting_landlord_quote_response"
    decision = await reconcile_work_order_nudge(
        wo,
        nudge_key="quote_contractor_reminder",
        tier="T24",
        expected_stall_type="awaiting_contractor_quote",
        min_age_hours=24,
    )
    assert not decision.fire
    assert decision.suppress_reason == "stall_mismatch"


@pytest.mark.asyncio
async def test_reconcile_fires_when_stall_matches_and_age_met():
    now = datetime.now(timezone.utc)
    wo = {
        "work_order_id": "wo3",
        "status": "ASSIGNED",
        "price_status": "AWAITING_QUOTE",
        "awaiting_quote_since": (now - timedelta(hours=30)).isoformat(),
        "contractor_id": "ctr1",
    }
    decision = await reconcile_work_order_nudge(
        wo,
        nudge_key="quote_contractor_reminder",
        tier="T24",
        expected_stall_type="awaiting_contractor_quote",
        min_age_hours=24,
        waiting_on="contractor",
    )
    assert decision.fire
    assert decision.waiting_on == "contractor"
