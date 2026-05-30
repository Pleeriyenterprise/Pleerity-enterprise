"""Reconciliation before recovery notifications — suppress stale or duplicate guidance."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services.operational_recovery_service import classify_recovery_state, suppress_invalid_recovery_guidance
from services.workflow_timer_service import work_order_stall_context

logger = logging.getLogger(__name__)

_TERMINAL_WO = frozenset({"CANCELLED", "COMPLETED", "VERIFIED", "CLOSED"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def recovery_idempotency_key(
    entity_type: str,
    entity_id: str,
    recovery_type: str,
    *,
    day: Optional[str] = None,
) -> str:
    d = day or _now().strftime("%Y-%m-%d")
    return f"workflow_recovery:{entity_type}:{entity_id}:{recovery_type}:{d}"


@dataclass
class RecoveryReconciliationDecision:
    fire: bool
    suppress_reason: Optional[str] = None
    recovery: Optional[Dict[str, Any]] = None


async def _duplicate_blocked(idempotency_key: str) -> bool:
    db = database.get_db()
    if db is None:
        return False
    existing = await db.message_logs.find_one({"idempotency_key": idempotency_key}, {"_id": 1})
    return existing is not None


async def _recovery_sent_recently(entity_type: str, entity_id: str, recovery_type: str) -> bool:
    db = database.get_db()
    if db is None:
        return False
    doc = await db.workflow_recovery_audit.find_one(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "recovery_type": recovery_type,
            "outcome": "sent",
        },
        {"_id": 1},
    )
    return doc is not None


async def reconcile_recovery_notification(
    recovery: Dict[str, Any],
) -> RecoveryReconciliationDecision:
    entity_type = recovery.get("entity_type") or ""
    entity_id = recovery.get("entity_id") or ""
    recovery_type = recovery.get("recovery_type") or ""
    if recovery.get("suppressed"):
        return RecoveryReconciliationDecision(False, recovery.get("suppression_state") or "suppressed")

    db = database.get_db()
    if entity_type == "work_order":
        wo = await db.work_orders.find_one({"work_order_id": entity_id}, {"_id": 0})
        if not wo:
            return RecoveryReconciliationDecision(False, "entity_missing")
        st = (wo.get("status") or "").upper()
        if st in _TERMINAL_WO:
            return RecoveryReconciliationDecision(
                False,
                "entity_terminal",
                suppress_invalid_recovery_guidance(recovery, entity_terminal=True),
            )
        stall = work_order_stall_context(wo)
        current_type = classify_recovery_state("work_order", wo, stall=stall)
        if not current_type:
            return RecoveryReconciliationDecision(
                False,
                "stall_resolved",
                suppress_invalid_recovery_guidance(recovery, stall_resolved=True),
            )
        if current_type != recovery_type:
            return RecoveryReconciliationDecision(
                False,
                "recovery_type_mismatch",
                suppress_invalid_recovery_guidance(recovery, recovery_type_mismatch=True),
            )

    idem = recovery_idempotency_key(entity_type, entity_id, recovery_type)
    if await _duplicate_blocked(idem):
        return RecoveryReconciliationDecision(False, "duplicate_same_day")
    if await _recovery_sent_recently(entity_type, entity_id, recovery_type):
        return RecoveryReconciliationDecision(False, "recovery_already_sent")

    return RecoveryReconciliationDecision(True, recovery=recovery)


async def record_recovery_suppressed(
    *,
    entity_type: str,
    entity_id: str,
    client_id: Optional[str],
    recovery_type: str,
    suppress_reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    db = database.get_db()
    now = _now().isoformat()
    await db.workflow_recovery_audit.insert_one(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "client_id": client_id,
            "recovery_type": recovery_type,
            "outcome": "suppressed",
            "suppress_reason": suppress_reason,
            "created_at": now,
            "metadata": metadata or {},
        }
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_RECOVERY_SUPPRESSED,
        client_id=client_id,
        resource_type=entity_type,
        resource_id=entity_id,
        metadata={"recovery_type": recovery_type, "reason": suppress_reason, **(metadata or {})},
    )


async def record_recovery_sent(
    *,
    entity_type: str,
    entity_id: str,
    client_id: Optional[str],
    recovery_type: str,
    idempotency_key: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    db = database.get_db()
    now = _now().isoformat()
    await db.workflow_recovery_audit.insert_one(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "client_id": client_id,
            "recovery_type": recovery_type,
            "outcome": "sent",
            "idempotency_key": idempotency_key,
            "created_at": now,
            "metadata": metadata or {},
        }
    )
    await db.workflow_recovery_metrics.update_one(
        {"recovery_type": recovery_type, "client_id": client_id or "global"},
        {
            "$inc": {"recovery_triggered": 1},
            "$set": {"last_triggered_at": now},
        },
        upsert=True,
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_RECOVERY_SENT,
        client_id=client_id,
        resource_type=entity_type,
        resource_id=entity_id,
        metadata={"recovery_type": recovery_type, "idempotency_key": idempotency_key, **(metadata or {})},
    )


async def record_recovery_resolved(
    *,
    entity_type: str,
    entity_id: str,
    client_id: Optional[str],
    recovery_type: str,
) -> None:
    db = database.get_db()
    now = _now().isoformat()
    await db.workflow_recovery_metrics.update_one(
        {"recovery_type": recovery_type, "client_id": client_id or "global"},
        {
            "$inc": {"recovery_resolved": 1},
            "$set": {"last_resolved_at": now},
        },
        upsert=True,
    )
    await db.workflow_recovery_audit.insert_one(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "client_id": client_id,
            "recovery_type": recovery_type,
            "outcome": "resolved",
            "created_at": now,
        }
    )
