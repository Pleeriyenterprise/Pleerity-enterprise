"""Stripe mode containment — Phase 1 guardrails tests."""
from __future__ import annotations

import pytest

from services.stripe_mode_containment_service import (
    CUSTOMER_BILLING_REFRESH_MESSAGE,
    STRIPE_CHECKOUT_MODE_DRIFT,
    STRIPE_CUSTOMER_MODE_DRIFT,
    STRIPE_EVENT_MODE_DRIFT,
    STRIPE_PORTAL_MODE_DRIFT,
    STRIPE_SUBSCRIPTION_MODE_DRIFT,
    StripeModeDriftError,
    assess_billing_stripe_mode_drift,
    classify_stripe_api_error_for_drift,
    validate_checkout_session_mode,
    validate_portal_billing_preflight,
    validate_stripe_customer_mode,
    validate_stripe_subscription_mode,
    validate_webhook_event_mode,
)


@pytest.fixture(autouse=True)
def _stripe_mode_test(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_SECRET_KEY_LIVE", "sk_live_containment_test")


def test_validate_subscription_mode_match():
    out = validate_stripe_subscription_mode("sub_x", "live", stored_mode="live", client_id="c1")
    assert out["ok"] is True


def test_validate_subscription_mode_mismatch():
    with pytest.raises(StripeModeDriftError) as exc:
        validate_stripe_subscription_mode("sub_x", "live", stored_mode="test", client_id="c1")
    assert exc.value.error_code == STRIPE_SUBSCRIPTION_MODE_DRIFT
    assert "sub_" not in exc.value.customer_message
    assert "livemode" not in exc.value.customer_message.lower()


def test_validate_subscription_missing_mode_blocks():
    with pytest.raises(StripeModeDriftError) as exc:
        validate_stripe_subscription_mode("sub_x", "live", stored_mode=None, client_id="c1")
    assert exc.value.error_code == STRIPE_SUBSCRIPTION_MODE_DRIFT
    assert exc.value.customer_message == CUSTOMER_BILLING_REFRESH_MESSAGE


def test_validate_subscription_trusted_mode_for_webhook():
    out = validate_stripe_subscription_mode(
        "sub_x", "live", stored_mode=None, trusted_mode="live", client_id="c1", operation="webhook"
    )
    assert out["ok"] is True
    assert out.get("trusted") is True


def test_validate_customer_mode_drift():
    with pytest.raises(StripeModeDriftError) as exc:
        validate_stripe_customer_mode("cus_x", "live", stored_mode="test", client_id="c1")
    assert exc.value.error_code == STRIPE_CUSTOMER_MODE_DRIFT


def test_validate_checkout_mode_drift():
    with pytest.raises(StripeModeDriftError) as exc:
        validate_checkout_session_mode("test", "live", client_id="c1")
    assert exc.value.error_code == STRIPE_CHECKOUT_MODE_DRIFT


def test_validate_portal_mixed_customer_subscription():
    with pytest.raises(StripeModeDriftError) as exc:
        validate_portal_billing_preflight(
            {
                "stripe_customer_id": "cus_x",
                "stripe_subscription_id": "sub_x",
                "stripe_customer_mode": "live",
                "stripe_mode": "test",
            },
            "live",
            client_id="c1",
        )
    assert exc.value.error_code == STRIPE_PORTAL_MODE_DRIFT


def test_validate_webhook_event_mode_drift():
    with pytest.raises(StripeModeDriftError) as exc:
        validate_webhook_event_mode(False, "live", client_id="c1")
    assert exc.value.error_code == STRIPE_EVENT_MODE_DRIFT


def test_classify_stripe_api_error_for_drift():
    msg = (
        "No such subscription: 'sub_1TX'; a similar object exists in test mode, "
        "but a live mode key was used to make this request."
    )
    assert classify_stripe_api_error_for_drift(Exception(msg)) == STRIPE_SUBSCRIPTION_MODE_DRIFT


def test_drift_error_customer_detail_safe():
    err = StripeModeDriftError(STRIPE_SUBSCRIPTION_MODE_DRIFT, client_id="c1")
    detail = err.to_customer_detail()
    assert detail["error_code"] == STRIPE_SUBSCRIPTION_MODE_DRIFT
    assert detail["message"] == CUSTOMER_BILLING_REFRESH_MESSAGE
    assert "sub_" not in str(detail)


@pytest.mark.asyncio
async def test_assess_billing_mode_drift_missing_mode(monkeypatch):
    class FakeCol:
        async def find_one(self, *_a, **_k):
            return {
                "client_id": "c1",
                "stripe_subscription_id": "sub_x",
                "stripe_customer_id": "cus_x",
            }

    class FakeDb:
        client_billing = FakeCol()

    monkeypatch.setattr(
        "services.stripe_mode_containment_service.database.get_db",
        lambda: FakeDb(),
    )
    out = await assess_billing_stripe_mode_drift("c1")
    assert out["drift_detected"] is True
    assert out["severity"] == "high"
    assert "entitlement_note" in out
