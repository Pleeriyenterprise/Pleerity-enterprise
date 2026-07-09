"""P0 subscription lifecycle transition convergence — targeted tests."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from routes import billing as billing_routes
from services.account_lifecycle_runtime_contract import build_runtime_contract
from services.billing_scheduled_cancellation_authority import (
    is_stale_scheduled_cancellation_mirror,
    stale_scheduled_cancellation_mongo_filter,
)
from services.stripe_service import StripeService

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
CLIENT_ID = "client-transition-01"


def _client(**overrides):
    base = {
        "client_id": CLIENT_ID,
        "billing_plan": "PLAN_2_PORTFOLIO",
        "client_lifecycle_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": CLIENT_ID,
        "subscription_status": "ACTIVE",
        "cancel_at_period_end": True,
        "current_period_end": datetime(2026, 6, 16, 11, 18, 55, tzinfo=timezone.utc),
        "billing_lifecycle_state": "cancel_at_period_end",
        "stripe_subscription_id": "sub_test_stale",
        "stripe_customer_id": "cus_test_stale",
    }
    base.update(overrides)
    return base


def test_is_stale_scheduled_cancellation_mirror_past_period_end():
    assert is_stale_scheduled_cancellation_mirror(_billing(), now=NOW) is True


def test_is_stale_scheduled_cancellation_mirror_future_period_end():
    future = NOW + timedelta(days=10)
    assert (
        is_stale_scheduled_cancellation_mirror(
            _billing(current_period_end=future),
            now=NOW,
        )
        is False
    )


def test_stale_scheduled_cancellation_mongo_filter_uses_now():
    filt = stale_scheduled_cancellation_mongo_filter(now=NOW)
    assert filt["cancel_at_period_end"] is True
    assert filt["subscription_status"] == {"$in": ["ACTIVE", "TRIALING"]}
    assert filt["current_period_end"]["$lt"] == NOW


def test_customer_experience_stale_scheduled_no_past_access_date():
    contract = build_runtime_contract(
        client=_client(),
        billing=_billing(),
        now=NOW,
    )
    cx = contract["customer_experience"]
    assert cx["heading"] == "Updating your subscription status"
    assert "being updated" in cx["explanation"]
    assert "2026-06-16" not in cx["explanation"]
    assert cx["primary_cta"]["action"] == "resume_subscription"
    assert contract["lifecycle_context"]["transition_pending"] is True


def test_customer_experience_future_cancellation_shows_access_until():
    future = NOW + timedelta(days=14)
    contract = build_runtime_contract(
        client=_client(),
        billing=_billing(current_period_end=future),
        now=NOW,
    )
    cx = contract["customer_experience"]
    assert cx["heading"] == "Cancellation scheduled"
    assert "full access until" in cx["explanation"]
    assert cx["primary_cta"]["action"] == "resume_subscription"


@pytest.mark.asyncio
async def test_resume_subscription_idempotent_when_not_scheduled():
    svc = StripeService()
    billing = _billing(cancel_at_period_end=False)
    with patch.object(svc, "_get_db", create=True):
        with patch("services.stripe_service.database.get_db") as mock_db:
            mock_db.return_value.client_billing.find_one = AsyncMock(return_value=billing)
            result = await svc.resume_subscription(CLIENT_ID)
    assert result["success"] is True
    assert result["already_active"] is True


@pytest.mark.asyncio
async def test_resume_subscription_calls_stripe_and_sync():
    svc = StripeService()
    billing = _billing()
    sub = MagicMock()
    sub.to_dict.return_value = {
        "id": "sub_test_stale",
        "status": "active",
        "cancel_at_period_end": False,
        "current_period_end": int((NOW + timedelta(days=30)).timestamp()),
    }
    with patch("services.stripe_service.database.get_db") as mock_db:
        mock_db.return_value.client_billing.find_one = AsyncMock(return_value=billing)
        with patch("services.stripe_service.stripe.Subscription.modify", return_value=sub) as modify:
            with patch(
                "services.stripe_service.sync_client_billing_from_stripe_subscription_id",
                new=AsyncMock(),
            ) as sync_bill:
                with patch(
                    "services.stripe_service.sync_subscription_lifecycle",
                    new=AsyncMock(),
                ) as sync_lc:
                    with patch(
                        "services.stripe_service.create_audit_log",
                        new=AsyncMock(),
                    ):
                        result = await svc.resume_subscription(CLIENT_ID, actor_id="pu-1")
    modify.assert_called_once_with("sub_test_stale", cancel_at_period_end=False)
    sync_bill.assert_awaited_once()
    sync_lc.assert_awaited_once()
    assert result["success"] is True
    assert result["already_active"] is False


@pytest.mark.asyncio
async def test_billing_resume_route_requires_capability():
    user = {
        "client_id": CLIENT_ID,
        "portal_user_id": "pu-1",
        "role": "ROLE_CLIENT",
    }
    request = MagicMock(spec=Request)
    with patch.object(billing_routes, "client_route_guard", new=AsyncMock(return_value=user)):
        with patch.object(billing_routes, "assert_client_capability", new=AsyncMock()) as cap:
            with patch.object(billing_routes, "require_recent_step_up", new=AsyncMock()):
                with patch.object(
                    billing_routes.stripe_service,
                    "resume_subscription",
                    new=AsyncMock(return_value={"success": True, "already_active": False}),
                ):
                    with patch.object(billing_routes, "create_audit_log", new=AsyncMock()):
                        result = await billing_routes.resume_subscription(request)
    cap.assert_awaited()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_reconcile_batch_includes_stale_scheduled_cancellation_rows():
    from services.stripe_subscription_reconcile_job import reconcile_all_stripe_subscriptions

    stale_row = {"client_id": "stale-1", "stripe_subscription_id": "sub_stale_1"}
    flagged_row = {"client_id": "flag-1", "stripe_subscription_id": "sub_flag_1"}

    class _Cursor:
        def __init__(self, rows):
            self._rows = rows

        def sort(self, *_args, **_kwargs):
            return self

        def limit(self, _lim):
            return self

        async def to_list(self, _lim):
            return self._rows

    mock_find = MagicMock(side_effect=[_Cursor([flagged_row]), _Cursor([stale_row])])
    mock_db = MagicMock()
    mock_db.client_billing.find = mock_find

    with patch("services.stripe_subscription_reconcile_job.configure_stripe_sdk", return_value="sk_test_x"):
        with patch("services.stripe_subscription_reconcile_job.database.get_db", return_value=mock_db):
            with patch(
                "services.stripe_subscription_reconcile_job.sync_client_billing_from_stripe_subscription_id",
                new=AsyncMock(),
            ):
                with patch(
                    "services.stripe_subscription_reconcile_job.sync_subscription_lifecycle",
                    new=AsyncMock(),
                ):
                    with patch(
                        "services.stripe_subscription_reconcile_job.clear_billing_reconciliation_needed",
                        new=AsyncMock(),
                    ):
                        result = await reconcile_all_stripe_subscriptions()
    assert result["attempted"] == 2
    assert mock_find.call_count == 2


@pytest.mark.asyncio
async def test_reconciliation_sync_trusts_deployment_mode_when_stripe_mode_missing():
    from services.billing_stripe_sync_service import sync_client_billing_from_stripe_subscription_id

    mock_db = MagicMock()
    mock_db.client_billing.find_one = AsyncMock(return_value={"stripe_mode": None})
    with patch("services.billing_stripe_sync_service.database.get_db", return_value=mock_db):
        with patch("services.billing_stripe_sync_service.get_stripe_mode", return_value="test"):
            with patch(
                "services.billing_stripe_sync_service.retrieve_stripe_subscription_dict",
                new=AsyncMock(return_value={"id": "sub_x", "status": "canceled", "customer": "cus_x"}),
            ) as retrieve:
                with patch(
                    "services.billing_stripe_sync_service.persist_subscription_billing_from_stripe",
                    new=AsyncMock(return_value={"client_id": CLIENT_ID}),
                ):
                    await sync_client_billing_from_stripe_subscription_id(
                        CLIENT_ID,
                        "sub_x",
                        event_source="runtime_contract_stale_scheduled_cancellation",
                    )
    retrieve.assert_awaited_once()
    assert retrieve.await_args.kwargs.get("trusted_mode") == "test"
