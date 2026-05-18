"""
Optional pilot operational notification hooks — reuses notification_orchestrator only.

Does not introduce parallel notification systems. Events without seeded templates
are recorded in pilot_operational_notification_log only.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database

logger = logging.getLogger(__name__)

COL_PILOT_NOTIFICATION_LOG = "pilot_operational_notification_log"

# Map event_type -> orchestrator template_key (must exist in notification seed)
_EVENT_TEMPLATE_MAP: Dict[str, str] = {
    "pilot_converted": "SUBSCRIPTION_CONFIRMED",
    "missing_payment_method": "SUBSCRIPTION_GRACE_REMINDER",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def emit_pilot_operational_event(
    *,
    event_type: str,
    client_id: str,
    context: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    now = _utc_now()
    idem = idempotency_key or f"pilot_ops:{event_type}:{client_id}:{now.date().isoformat()}"
    log_doc = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "client_id": client_id,
        "context": context or {},
        "idempotency_key": idem,
        "created_at": now,
        "orchestrator_outcome": None,
    }
    await db[COL_PILOT_NOTIFICATION_LOG].insert_one(log_doc)

    template_key = _EVENT_TEMPLATE_MAP.get(event_type)
    if not template_key:
        return {"logged": True, "sent": False, "reason": "no_template_mapped"}

    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "contact_email": 1})
        recipient = (client or {}).get("contact_email") or (client or {}).get("email")
        if not recipient:
            return {"logged": True, "sent": False, "reason": "no_recipient"}

        from services.notification_orchestrator import notification_orchestrator

        result = await notification_orchestrator.send(
            template_key=template_key,
            client_id=client_id,
            context={**(context or {}), "recipient": recipient, "pilot_event_type": event_type},
            idempotency_key=idem,
            event_type=f"pilot_ops_{event_type}",
        )
        outcome = getattr(result, "outcome", None) or str(result)
        await db[COL_PILOT_NOTIFICATION_LOG].update_one(
            {"event_id": log_doc["event_id"]},
            {"$set": {"orchestrator_outcome": outcome}},
        )
        return {"logged": True, "sent": outcome == "sent", "outcome": outcome}
    except Exception as ex:
        logger.warning("Pilot operational notification failed event=%s client=%s: %s", event_type, client_id, ex)
        return {"logged": True, "sent": False, "error": str(ex)}
