"""Stripe webhook route behavior: retryable failures must return 5xx."""
from unittest.mock import AsyncMock, patch


def test_stripe_webhook_returns_500_for_retryable_processing_failure(client):
    with patch(
        "routes.webhooks.stripe_webhook_service.process_webhook",
        new_callable=AsyncMock,
        return_value=(False, "Processing failed", {"retryable": True, "error": "db timeout"}),
    ):
        r = client.post(
            "/api/webhooks/stripe",
            json={"id": "evt_test", "type": "checkout.session.completed"},
            headers={"Stripe-Signature": "sig"},
        )
    assert r.status_code == 500


def test_stripe_webhook_returns_400_for_invalid_signature(client):
    with patch(
        "routes.webhooks.stripe_webhook_service.process_webhook",
        new_callable=AsyncMock,
        return_value=(False, "Invalid signature", {"error": "bad sig"}),
    ):
        r = client.post("/api/webhooks/stripe", json={"id": "evt_test"}, headers={"Stripe-Signature": "sig"})
    assert r.status_code == 400

