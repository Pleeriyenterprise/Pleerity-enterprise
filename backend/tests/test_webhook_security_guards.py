"""Security regression tests for webhook verification guards."""
import asyncio
import os
from unittest.mock import patch

from services.stripe_webhook_service import StripeWebhookService


def test_legacy_postmark_delivery_requires_token_when_configured(client):
    with patch.dict(os.environ, {"POSTMARK_WEBHOOK_TOKEN": "pm-secret"}, clear=False):
        r = client.post("/api/webhook/postmark/delivery", json={})
    assert r.status_code == 401


def test_legacy_postmark_bounce_requires_token_when_configured(client):
    with patch.dict(os.environ, {"POSTMARK_WEBHOOK_TOKEN": "pm-secret"}, clear=False):
        r = client.post("/api/webhook/postmark/bounce", json={})
    assert r.status_code == 401


def test_legacy_postmark_delivery_accepts_valid_token(client):
    with patch.dict(os.environ, {"POSTMARK_WEBHOOK_TOKEN": "pm-secret"}, clear=False):
        r = client.post(
            "/api/webhook/postmark/delivery",
            json={},
            headers={"X-Postmark-Token": "pm-secret"},
        )
    # Empty payload is allowed and ignored when authorized.
    assert r.status_code == 200
    assert r.json().get("status") in ("ignored", "received")


def test_stripe_webhook_fails_closed_without_secret_in_production():
    svc = StripeWebhookService()
    payload = b'{"id":"evt_test","type":"checkout.session.completed","data":{"object":{}}}'
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "STRIPE_WEBHOOK_SECRET": ""}, clear=False):
        ok, message, details = asyncio.run(
            svc.process_webhook(payload=payload, signature="t=1,v1=fake")
        )
    assert ok is False
    assert message == "Invalid signature"
    assert "missing" in str((details or {}).get("error", "")).lower()
