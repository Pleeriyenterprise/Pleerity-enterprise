"""Append-only pilot lifecycle audit trail."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from database import database

COLLECTION_NAME = "pilot_lifecycle_audit"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_pilot_lifecycle_audit_document(
    *,
    client_id: str,
    action_type: str,
    actor: Mapping[str, Any],
    previous_values: Optional[Mapping[str, Any]] = None,
    new_values: Optional[Mapping[str, Any]] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    stripe_event_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    if not str(client_id or "").strip():
        raise ValueError("client_id is required")
    if not str(action_type or "").strip():
        raise ValueError("action_type is required")
    actor_type = str(actor.get("type") or "system").lower()
    doc: Dict[str, Any] = {
        "audit_id": str(uuid.uuid4()),
        "client_id": client_id,
        "action_type": str(action_type),
        "actor": {
            "type": actor_type,
            "id": actor.get("id"),
            "email": actor.get("email"),
        },
        "previous_values": dict(previous_values or {}),
        "new_values": dict(new_values or {}),
        "reason": (reason or "").strip() or None,
        "notes": (notes or "").strip() or None,
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_event_id": stripe_event_id,
        "idempotency_key": (idempotency_key or "").strip() or None,
        "created_at": created_at or _utcnow(),
    }
    return doc


async def insert_pilot_lifecycle_audit(doc: Dict[str, Any]) -> str:
    db = database.get_db()
    key = doc.get("idempotency_key")
    if key:
        existing = await db[COLLECTION_NAME].find_one({"idempotency_key": key}, {"_id": 0, "audit_id": 1})
        if existing:
            return str(existing.get("audit_id") or "")
    try:
        await db[COLLECTION_NAME].insert_one(doc)
    except Exception as e:
        if key and ("duplicate key" in str(e).lower() or "E11000" in str(e)):
            existing = await db[COLLECTION_NAME].find_one({"idempotency_key": key}, {"_id": 0, "audit_id": 1})
            return str((existing or {}).get("audit_id") or doc.get("audit_id") or "")
        raise
    return str(doc.get("audit_id") or "")
