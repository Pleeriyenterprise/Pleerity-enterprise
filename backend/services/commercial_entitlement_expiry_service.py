"""Commercial entitlement expiry and review enforcement (Phase 2C)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from services.commercial_entitlement_execution_service import ACTION_REVOKE
from services.commercial_entitlement_observability_service import (
    EVENT_COMMERCIAL_EXPIRED,
    EVENT_COMMERCIAL_REVIEW_DUE,
    record_commercial_entitlement_event,
)
from services.commercial_entitlement_service import (
    COL_GOVERNANCE,
    EXCEPTION_SPONSORED_ACCESS,
    GOVERNANCE_STATUS_ACTIVE,
    GOVERNANCE_STATUS_EXPIRED,
    load_client_billing_signals,
)
from services.entitlement_access import compute_canonical_entitlement_state

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def enforce_review_requirements(governance: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Returns (ok, error_message). Sponsored access must have review/expiry."""
    if governance.get("exception_type") != EXCEPTION_SPONSORED_ACCESS:
        return True, None
    exp = _parse_iso(governance.get("entitlement_expiry_at"))
    rev = _parse_iso(governance.get("entitlement_review_at"))
    if not exp and not rev:
        return False, "Sponsored access requires expiry or review date."
    if exp and exp <= _now():
        return False, "Sponsored access has expired."
    return True, None


async def expire_stale_governance_row(governance: Dict[str, Any], *, actor_id: str = "system_expiry") -> Dict[str, Any]:
    client_id = governance["client_id"]
    governance_id = governance["governance_id"]
    db = database.get_db()
    now = _now()
    await db[COL_GOVERNANCE].update_one(
        {"governance_id": governance_id},
        {
            "$set": {
                "status": GOVERNANCE_STATUS_EXPIRED,
                "expired_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        },
    )
    signals = await load_client_billing_signals(client_id)
    client = signals.get("client") or {}
    billing = signals.get("billing") or {}
    canon = compute_canonical_entitlement_state(
        billing_lifecycle_state=(billing.get("billing_lifecycle_state") or client.get("billing_lifecycle_state")),
        subscription_status_upper=(billing.get("subscription_status") or client.get("subscription_status")),
    )
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {"canonical_entitlement_state": canon},
            "$unset": {
                "commercial_governance_id": "",
                "commercial_governance_state": "",
                "effective_access_reason": "",
            },
        },
    )
    if billing:
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": {"canonical_entitlement_state": canon}},
        )
    await record_commercial_entitlement_event(
        event_type=EVENT_COMMERCIAL_EXPIRED,
        client_id=client_id,
        governance_id=governance_id,
        action=ACTION_REVOKE,
        actor_id=actor_id,
        metadata={"reason": "entitlement_expiry"},
    )
    return {"client_id": client_id, "governance_id": governance_id, "expired": True}


async def process_commercial_entitlement_expiry(*, limit: int = 200) -> Dict[str, Any]:
    """Expire active governance rows past entitlement_expiry_at; flag review due."""
    db = database.get_db()
    now = _now()
    expired: List[Dict[str, Any]] = []
    review_due: List[str] = []

    cursor = db[COL_GOVERNANCE].find({"status": GOVERNANCE_STATUS_ACTIVE}).limit(limit)
    async for row in cursor:
        exp = _parse_iso(row.get("entitlement_expiry_at"))
        if exp and exp <= now:
            result = await expire_stale_governance_row(row)
            expired.append(result)
            continue
        rev = _parse_iso(row.get("entitlement_review_at"))
        if row.get("entitlement_review_required") and rev and rev <= now:
            review_due.append(row.get("governance_id"))
            await record_commercial_entitlement_event(
                event_type=EVENT_COMMERCIAL_REVIEW_DUE,
                client_id=row["client_id"],
                governance_id=row.get("governance_id"),
                actor_id="system_expiry",
                metadata={"review_at": row.get("entitlement_review_at")},
            )

    return {
        "processed_limit": limit,
        "expired_count": len(expired),
        "expired": expired,
        "review_due_governance_ids": review_due,
    }
