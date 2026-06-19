"""Twin connector collection names and shared constants — Stage Y."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION = "discovery_twin_webhook_receipts"
DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION = "discovery_twin_run_event_captures"

TWIN_WEBHOOK_EVENTS_INGEST = frozenset({"run.completed", "run.failed"})
TWIN_WEBHOOK_EVENTS_ALL = frozenset(
    {"run.started", "run.completed", "run.failed", "run.stopped", "run.paused"}
)

DEFAULT_TWIN_API_BASE_URL = "https://build.twin.so"
DEFAULT_WEBHOOK_MAX_SKEW_SECONDS = 300


def twin_api_base_url() -> str:
    return (os.environ.get("TWIN_API_BASE_URL") or DEFAULT_TWIN_API_BASE_URL).rstrip("/")


def twin_webhook_max_skew_seconds() -> int:
    try:
        return int(os.environ.get("TWIN_WEBHOOK_MAX_SKEW_SECONDS", str(DEFAULT_WEBHOOK_MAX_SKEW_SECONDS)))
    except ValueError:
        return DEFAULT_WEBHOOK_MAX_SKEW_SECONDS


def twin_discovery_agent_id() -> str:
    return (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or "").strip()


def twin_discovery_campaign_id() -> str:
    return (os.environ.get("TWIN_DISCOVERY_CAMPAIGN_ID") or "").strip()


def twin_ingest_actor_id() -> str:
    return (os.environ.get("TWIN_INGEST_ACTOR_ID") or "twin-webhook-connector").strip()


def twin_ingest_actor_email() -> str:
    return (os.environ.get("TWIN_INGEST_ACTOR_EMAIL") or "twin-ingest@pleerity.staging").strip()


def _ts_id(prefix: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{ts}-{uuid.uuid4().hex[:6].upper()}"


def generate_twin_webhook_receipt_id() -> str:
    return _ts_id("DTWR")


def generate_twin_event_capture_id() -> str:
    return _ts_id("DTCE")
