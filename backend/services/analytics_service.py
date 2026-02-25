"""
Analytics events service — passive logging for conversion funnel and operational metrics.

- Logs events to analytics_events collection; no business logic changes.
- Idempotency for key events (e.g. payment_succeeded) via idempotency_key to avoid double-count on webhook retries.
- first_doc_uploaded: logged at most once per client_id.
"""
from datetime import datetime, timezone
from typing import Any, Optional
import logging

from database import database

logger = logging.getLogger(__name__)

COLLECTION = "analytics_events"

# Events that must be deduped by idempotency_key (e.g. Stripe event id)
IDEMPOTENT_EVENTS = frozenset({"payment_succeeded"})


async def log_event(event_name: str, payload: dict[str, Any], idempotency_key: Optional[str] = None) -> bool:
    """
    Insert one analytics event. Payload is normalized to schema fields; extra keys go into metadata.

    Schema fields (optional): lead_id, client_id, customer_reference, email, source, plan_code,
    properties_count, stripe_session_id, stripe_subscription_id. Any other payload keys go to metadata.

    If idempotency_key is provided and event_name is in IDEMPOTENT_EVENTS, skips insert if a document
    with that idempotency_key already exists (returns False without inserting).
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)

    allowed = {
        "lead_id", "client_id", "customer_reference", "email", "source", "plan_code",
        "properties_count", "stripe_session_id", "stripe_subscription_id",
    }
    doc = {
        "ts": now,
        "event": event_name,
    }
    metadata = {}
    for k, v in payload.items():
        if k in allowed and v is not None:
            doc[k] = v
        else:
            metadata[k] = v

    if metadata:
        doc["metadata"] = metadata

    if idempotency_key and event_name in IDEMPOTENT_EVENTS:
        existing = await db[COLLECTION].find_one(
            {"idempotency_key": idempotency_key},
            {"_id": 1},
        )
        if existing:
            logger.debug("Analytics event skipped (idempotency): event=%s key=%s", event_name, idempotency_key[:32])
            return False
        doc["idempotency_key"] = idempotency_key

    try:
        await db[COLLECTION].insert_one(doc)
        return True
    except Exception as e:
        # Duplicate key on idempotency_key is acceptable
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            logger.debug("Analytics event skipped (duplicate key): event=%s", event_name)
            return False
        logger.warning("Analytics log_event failed: event=%s err=%s", event_name, e)
        return False


async def log_public_track(event_name: str, page: Optional[str] = None, session_id: Optional[str] = None, props: Optional[dict[str, Any]] = None) -> bool:
    """
    Insert one analytics event from public track (client-side). Rate-limit at caller.
    Stores event, ts, page, session_id, and props as metadata (sanitized).
    """
    db = database.get_db()
    if not db:
        return False
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {"ts": now, "event": event_name}
    if page is not None and isinstance(page, str) and len(page) <= 500:
        doc["page"] = page
    if session_id is not None and isinstance(session_id, str) and len(session_id) <= 128:
        doc["session_id"] = session_id
    if props and isinstance(props, dict):
        # Keep only simple types; cap size
        safe: dict[str, Any] = {}
        for k, v in list(props.items())[:20]:
            if isinstance(k, str) and len(k) <= 64:
                if v is None or isinstance(v, (str, int, float, bool)):
                    safe[k] = str(v)[:200] if isinstance(v, str) else v
        if safe:
            doc["metadata"] = safe
    try:
        await db[COLLECTION].insert_one(doc)
        return True
    except Exception as e:
        logger.warning("log_public_track failed: event=%s err=%s", event_name, e)
        return False


async def log_first_doc_uploaded_once(client_id: str, payload: Optional[dict[str, Any]] = None) -> bool:
    """
    Log first_doc_uploaded only once per client_id. Returns True if logged, False if already present.
    Call after each doc_uploaded when you want to record "first value" for funnel.
    """
    db = database.get_db()
    existing = await db[COLLECTION].find_one(
        {"event": "first_doc_uploaded", "client_id": client_id},
        {"_id": 1},
    )
    if existing:
        return False
    doc = {
        "ts": datetime.now(timezone.utc),
        "event": "first_doc_uploaded",
        "client_id": client_id,
        **(payload or {}),
    }
    try:
        await db[COLLECTION].insert_one(doc)
        return True
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            return False
        logger.warning("Analytics log_first_doc_uploaded_once failed: client_id=%s err=%s", client_id, e)
        return False
