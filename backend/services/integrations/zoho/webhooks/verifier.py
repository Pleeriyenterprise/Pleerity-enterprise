"""Zoho webhook signature verification."""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional


class ZohoWebhookVerificationError(Exception):
    pass


def verify_zoho_webhook_signature(
    raw_body: bytes,
    signature: Optional[str],
    secret: str,
) -> None:
    if not secret:
        raise ZohoWebhookVerificationError("webhook_secret_not_configured")
    if not signature:
        raise ZohoWebhookVerificationError("missing_signature")

    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature.replace("sha256=", "").strip()
    if not hmac.compare_digest(expected, provided):
        raise ZohoWebhookVerificationError("invalid_signature")
