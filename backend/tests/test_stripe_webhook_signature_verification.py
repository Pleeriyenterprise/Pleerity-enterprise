"""Stripe webhook signature verification — proves construct_event succeeds with known payload/signature."""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
import stripe

from services.stripe_mode_authority import (
    resolve_webhook_secret,
    resolve_webhook_secret_with_source,
    webhook_secret_fingerprint,
)

def _stripe_test_signature(payload: bytes, secret: str, *, timestamp: int | None = None) -> str:
    """Build a valid Stripe-Signature header for unit tests (compatible with construct_event)."""
    ts = int(time.time()) if timestamp is None else timestamp
    signed_payload = f"{ts}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


@pytest.fixture(autouse=True)
def _clear_stripe_env(monkeypatch):
    for key in list(__import__("os").environ.keys()):
        if key.startswith("STRIPE_"):
            monkeypatch.delenv(key, raising=False)
    yield


def test_webhook_secret_selected_by_mode_live(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_LIVE", "whsec_live_only")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_TEST", "whsec_test_only")
    secret, env_var = resolve_webhook_secret_with_source()
    assert env_var == "STRIPE_WEBHOOK_SECRET_LIVE"
    assert secret == "whsec_live_only"
    assert resolve_webhook_secret() == "whsec_live_only"


def test_webhook_secret_strips_surrounding_quotes(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_LIVE", '"whsec_quoted_secret"')
    secret, env_var = resolve_webhook_secret_with_source()
    assert env_var == "STRIPE_WEBHOOK_SECRET_LIVE"
    assert secret == "whsec_quoted_secret"


def test_webhook_secret_fingerprint_never_returns_full_secret():
    secret = "whsec_abcdefghijklmnopqrstuvwxyz"
    fp = webhook_secret_fingerprint(secret)
    assert fp is not None
    assert secret not in fp
    assert fp.startswith("whsec_ab")
    assert fp.endswith("wxyz")


@pytest.mark.parametrize("mode,env_key,secret", [
    ("test", "STRIPE_WEBHOOK_SECRET_TEST", "whsec_test_signing_secret_unit"),
    ("live", "STRIPE_WEBHOOK_SECRET_LIVE", "whsec_live_signing_secret_unit"),
])
def test_construct_event_with_stripe_test_header(monkeypatch, mode, env_key, secret):
    monkeypatch.setenv("STRIPE_MODE", mode)
    monkeypatch.setenv(env_key, secret)
    payload_dict = {
        "id": "evt_sig_unit_test",
        "object": "event",
        "type": "checkout.session.completed",
        "livemode": mode == "live",
    }
    payload = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    header = _stripe_test_signature(payload, secret)

    resolved = resolve_webhook_secret()
    event = stripe.Webhook.construct_event(payload, header, resolved)
    assert event["id"] == "evt_sig_unit_test"
    assert event["type"] == "checkout.session.completed"
