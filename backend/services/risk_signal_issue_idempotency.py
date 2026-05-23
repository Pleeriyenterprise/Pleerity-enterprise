"""
Bounded idempotency for risk signal → maintenance issue propagation (F4 / G9 remediation).

Replays the existing open linked issue for the same signal — no duplicate propagated debt.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.maintenance_issues_service import (
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_RESOLVED,
    get_issue,
)

OPEN_ISSUE_EXCLUDE = frozenset({STATUS_CLOSED, STATUS_CANCELLED, STATUS_RESOLVED})


async def find_open_issue_for_signal(db, *, signal_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    row = await db.maintenance_issues.find_one(
        {
            "client_id": client_id,
            "risk_signal_id": signal_id,
            "status": {"$nin": list(OPEN_ISSUE_EXCLUDE)},
        },
        sort=[("created_at", -1)],
    )
    if not row:
        return None
    row.pop("_id", None)
    return row


async def replay_open_issue_for_signal(signal_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    from database import database

    db = database.get_db()
    row = await find_open_issue_for_signal(db, signal_id=signal_id, client_id=client_id)
    if not row:
        return None
    issue_id = row.get("issue_id")
    if not issue_id:
        return None
    doc = await get_issue(str(issue_id), client_id=client_id)
    if not doc:
        return None
    out = dict(doc)
    out["idempotent_replay"] = True
    return out
