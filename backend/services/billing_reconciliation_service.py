from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from models import AuditAction, UserRole
from utils.audit import create_audit_log


async def mark_billing_reconciliation_needed(
    *,
    client_id: str,
    reason: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    db = database.get_db()
    now = datetime.now(timezone.utc)
    ctx = context or {}
    await db.client_billing.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "billing_sync_state": "needs_reconciliation",
                "billing_reconciliation_needed": True,
                "billing_reconciliation_reason": (reason or "unknown")[:160],
                "billing_reconciliation_marked_at": now,
                "billing_reconciliation_context": ctx,
                "updated_at": now,
            }
        },
    )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.SYSTEM,
        client_id=client_id,
        metadata={
            "action_type": "BILLING_RECONCILIATION_NEEDED",
            "reason": (reason or "unknown")[:160],
            "context": ctx,
        },
    )


async def clear_billing_reconciliation_needed(
    *,
    client_id: str,
    reason: str = "state_converged",
) -> None:
    db = database.get_db()
    now = datetime.now(timezone.utc)
    await db.client_billing.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "billing_reconciliation_needed": False,
                "billing_reconciliation_cleared_at": now,
                "billing_reconciliation_cleared_reason": reason[:160],
                "updated_at": now,
            }
        },
        upsert=False,
    )
