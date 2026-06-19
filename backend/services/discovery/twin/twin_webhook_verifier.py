"""HMAC verification for Twin webhook deliveries — Stage Y."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class TwinWebhookVerificationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class TwinWebhookHeaders:
    signature: str
    event: str


def parse_signature_header(signature_header: Optional[str]) -> str:
    if not signature_header or not str(signature_header).strip():
        raise TwinWebhookVerificationError("MISSING_SIGNATURE", "X-Cobb-Signature header is required")
    value = str(signature_header).strip()
    if not value.startswith("sha256="):
        raise TwinWebhookVerificationError(
            "INVALID_SIGNATURE_FORMAT",
            "X-Cobb-Signature must start with sha256=",
        )
    return value


def verify_webhook_signature(
    *,
    signing_secret: str,
    raw_body: bytes,
    signature_header: Optional[str],
) -> None:
    if not signing_secret or not signing_secret.strip():
        raise TwinWebhookVerificationError("MISSING_SIGNING_SECRET", "Twin webhook signing secret not configured")

    provided = parse_signature_header(signature_header)
    expected = "sha256=" + hmac.new(
        signing_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, provided):
        raise TwinWebhookVerificationError("SIGNATURE_MISMATCH", "Webhook signature verification failed")


def verify_timestamp_skew(
    timestamp_iso: str,
    *,
    max_skew_seconds: int,
    now: Optional[datetime] = None,
) -> None:
    if not timestamp_iso or not str(timestamp_iso).strip():
        raise TwinWebhookVerificationError("MISSING_TIMESTAMP", "Webhook timestamp is required")

    text = str(timestamp_iso).strip().replace("Z", "+00:00")
    try:
        when = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TwinWebhookVerificationError("INVALID_TIMESTAMP", "Webhook timestamp is not valid ISO-8601") from exc

    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    reference = now or datetime.now(timezone.utc)
    delta = abs((when - reference).total_seconds())
    if delta > max_skew_seconds:
        raise TwinWebhookVerificationError(
            "TIMESTAMP_SKEW",
            f"Webhook timestamp outside allowed skew ({max_skew_seconds}s)",
        )


def validate_webhook_envelope(
    payload: Dict[str, Any],
    *,
    allowed_agent_id: str,
    header_event: Optional[str],
) -> Dict[str, Any]:
    event = payload.get("event")
    if not event or not str(event).strip():
        raise TwinWebhookVerificationError("MISSING_EVENT", "Webhook event field is required")

    if header_event and str(header_event).strip() and str(header_event).strip() != str(event).strip():
        raise TwinWebhookVerificationError("EVENT_HEADER_MISMATCH", "X-Cobb-Event does not match body event")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise TwinWebhookVerificationError("INVALID_DATA", "Webhook data must be an object")

    agent_id = data.get("agent_id")
    run_id = data.get("run_id")
    if not agent_id or not str(agent_id).strip():
        raise TwinWebhookVerificationError("MISSING_AGENT_ID", "Webhook data.agent_id is required")
    if not run_id or not str(run_id).strip():
        raise TwinWebhookVerificationError("MISSING_RUN_ID", "Webhook data.run_id is required")

    if allowed_agent_id and str(agent_id).strip() != allowed_agent_id:
        raise TwinWebhookVerificationError(
            "AGENT_NOT_ALLOWED",
            f"Webhook agent_id '{agent_id}' is not allowlisted",
        )

    return {
        "event": str(event).strip(),
        "timestamp": str(payload.get("timestamp") or "").strip(),
        "agent_id": str(agent_id).strip(),
        "run_id": str(run_id).strip(),
        "status": data.get("status"),
        "outcome": data.get("outcome"),
        "finished_at": data.get("finished_at"),
        "raw_data": data,
    }
