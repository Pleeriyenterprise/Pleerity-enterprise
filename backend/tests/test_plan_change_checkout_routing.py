"""Plan-change deployment checkout — plan preservation and billing return URLs."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.stripe_service import (
    CHECKOUT_CONTEXT_ONBOARDING,
    CHECKOUT_CONTEXT_PLAN_CHANGE,
    CHECKOUT_CONTEXT_RECOVERY_PLAN_CHANGE,
    StripeService,
    checkout_redirect_urls,
)


@pytest.fixture(autouse=True)
def _stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_plan_change_routing")
    for plan in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"):
        monkeypatch.setenv(f"STRIPE_TEST_PRICE_{plan}_MONTHLY", f"price_{plan}_monthly")
        monkeypatch.setenv(f"STRIPE_TEST_PRICE_{plan}_ONBOARDING", f"price_{plan}_onboarding")


def test_checkout_redirect_urls_plan_change_uses_billing_settings():
    success, cancel = checkout_redirect_urls(
        "https://pleerityenterprise.co.uk",
        CHECKOUT_CONTEXT_PLAN_CHANGE,
    )
    assert success == (
        "https://pleerityenterprise.co.uk/settings/billing?checkout=success"
        "&session_id={CHECKOUT_SESSION_ID}"
    )
    assert cancel == "https://pleerityenterprise.co.uk/settings/billing?checkout=cancelled"


def test_checkout_redirect_urls_onboarding_uses_intake_cancel_route():
    success, cancel = checkout_redirect_urls(
        "https://pleerityenterprise.co.uk",
        CHECKOUT_CONTEXT_ONBOARDING,
    )
    assert success == "https://pleerityenterprise.co.uk/checkout/success?session_id={CHECKOUT_SESSION_ID}"
    assert cancel == "https://pleerityenterprise.co.uk/checkout/cancel"


def test_recovery_plan_change_uses_billing_return_urls():
    success, cancel = checkout_redirect_urls(
        "https://app.example",
        CHECKOUT_CONTEXT_RECOVERY_PLAN_CHANGE,
    )
    assert "/settings/billing" in success
    assert "/settings/billing" in cancel
    assert "/intake/start" not in cancel


def _mock_session(price_id: str):
    return SimpleNamespace(
        id="cs_test_1",
        url="https://checkout.stripe.test/cs_test_1",
        amount_total=3900,
        currency="gbp",
        line_items={"data": [{"price": {"id": price_id}}]},
    )


@pytest.mark.asyncio
async def test_create_checkout_session_preserves_requested_plan_price():
    """Solo checkout must use Solo price id — not Portfolio default."""
    mock_db = MagicMock()
    mock_db.client_billing.find_one = AsyncMock(
        return_value={
            "onboarding_fee_paid": True,
            "onboarding_fee_waived": False,
            "stripe_subscription_id": "sub_existing",
        }
    )
    mock_db.checkout_sessions.insert_one = AsyncMock()

    captured: dict = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return _mock_session("price_PLAN_1_SOLO_monthly")

    with patch("services.stripe_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_service.configure_stripe_sdk"):
            with patch("services.stripe_service.stripe.checkout.Session.create", side_effect=_create):
                svc = StripeService()
                result = await svc.create_checkout_session(
                    client_id="c1",
                    plan_code="PLAN_1_SOLO",
                    origin_url="https://app.example",
                    checkout_context=CHECKOUT_CONTEXT_PLAN_CHANGE,
                )

    assert result["plan_code"] == "PLAN_1_SOLO"
    assert result["requested_plan_code"] == "PLAN_1_SOLO"
    assert captured["line_items"][0]["price"] == "price_PLAN_1_SOLO_monthly"
    assert captured["metadata"]["requested_plan_code"] == "PLAN_1_SOLO"
    assert captured["metadata"]["checkout_context"] == CHECKOUT_CONTEXT_PLAN_CHANGE
    assert captured["success_url"].startswith("https://app.example/settings/billing")
    assert captured["cancel_url"] == "https://app.example/settings/billing?checkout=cancelled"
    insert_doc = mock_db.checkout_sessions.insert_one.call_args[0][0]
    assert insert_doc["requested_plan_code"] == "PLAN_1_SOLO"
    assert insert_doc["subscription_price_id"] == "price_PLAN_1_SOLO_monthly"


@pytest.mark.asyncio
async def test_create_checkout_session_professional_uses_pro_price_not_portfolio():
    mock_db = MagicMock()
    mock_db.client_billing.find_one = AsyncMock(
        return_value={"onboarding_fee_paid": True, "stripe_subscription_id": "sub_x"}
    )
    mock_db.checkout_sessions.insert_one = AsyncMock()
    captured: dict = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return _mock_session("price_PLAN_3_PRO_monthly")

    with patch("services.stripe_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_service.configure_stripe_sdk"):
            with patch("services.stripe_service.stripe.checkout.Session.create", side_effect=_create):
                svc = StripeService()
                await svc.create_checkout_session(
                    client_id="c1",
                    plan_code="PLAN_3_PRO",
                    origin_url="https://app.example",
                    checkout_context=CHECKOUT_CONTEXT_PLAN_CHANGE,
                )

    assert captured["line_items"][0]["price"] == "price_PLAN_3_PRO_monthly"
    assert captured["line_items"][0]["price"] != "price_PLAN_2_PORTFOLIO_monthly"


@pytest.mark.asyncio
async def test_onboarding_checkout_still_uses_intake_cancel_route():
    mock_db = MagicMock()
    mock_db.client_billing.find_one = AsyncMock(return_value=None)
    mock_db.checkout_sessions.insert_one = AsyncMock()
    captured: dict = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return _mock_session("price_PLAN_2_PORTFOLIO_monthly")

    with patch("services.stripe_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_service.configure_stripe_sdk"):
            with patch("services.stripe_service.stripe.checkout.Session.create", side_effect=_create):
                svc = StripeService()
                await svc.create_checkout_session(
                    client_id="c1",
                    plan_code="PLAN_2_PORTFOLIO",
                    origin_url="https://app.example",
                    checkout_context=CHECKOUT_CONTEXT_ONBOARDING,
                )

    assert captured["cancel_url"] == "https://app.example/checkout/cancel"
    assert "/intake/start" not in captured["cancel_url"]


@pytest.mark.asyncio
async def test_duplicate_price_env_raises_at_mapping_load():
    import services.plan_registry as pr

    pr._STRIPE_PRICE_CACHE.clear()
    with patch.dict(
        "os.environ",
        {
            "STRIPE_TEST_PRICE_PLAN_1_SOLO_MONTHLY": "price_same",
            "STRIPE_TEST_PRICE_PLAN_2_PORTFOLIO_MONTHLY": "price_same",
            "STRIPE_TEST_PRICE_PLAN_3_PRO_MONTHLY": "price_unique",
            "STRIPE_TEST_PRICE_PLAN_1_SOLO_ONBOARDING": "price_ob1",
            "STRIPE_TEST_PRICE_PLAN_2_PORTFOLIO_ONBOARDING": "price_ob2",
            "STRIPE_TEST_PRICE_PLAN_3_PRO_ONBOARDING": "price_ob3",
        },
        clear=False,
    ):
        from services.plan_registry import StripeModeMismatchError, get_stripe_price_mappings

        with pytest.raises(StripeModeMismatchError, match="Duplicate"):
            get_stripe_price_mappings("test")
    pr._STRIPE_PRICE_CACHE.clear()


@pytest.mark.asyncio
async def test_upgrade_deployment_checkout_passes_plan_change_context():
    from services.stripe_service import StripeService

    mock_db = MagicMock()
    mock_db.client_billing.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "stripe_mode_verification_status": "MODE_UNVERIFIED",
            "stripe_subscription_id": "sub_legacy",
            "stripe_customer_id": "cus_legacy",
        }
    )
    mock_db.clients.find_one = AsyncMock(
        return_value={"client_id": "c1", "email": "client@example.com"}
    )

    svc = StripeService()
    svc.create_checkout_session = AsyncMock(
        return_value={"session_id": "cs1", "checkout_url": "https://checkout.example", "plan_code": "PLAN_3_PRO"}
    )

    with patch("services.stripe_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_service.get_stripe_mode", return_value="live"):
            with patch("services.stripe_service.configure_stripe_sdk"):
                await svc.create_upgrade_session(
                    client_id="c1",
                    new_plan_code="PLAN_3_PRO",
                    origin_url="https://app.example/settings/billing",
                )

    kwargs = svc.create_checkout_session.call_args.kwargs
    assert kwargs["plan_code"] == "PLAN_3_PRO"
    assert kwargs["checkout_context"] == CHECKOUT_CONTEXT_PLAN_CHANGE

