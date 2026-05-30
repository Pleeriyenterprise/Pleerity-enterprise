"""Reconciliation before workflow nudges — suppress stale, duplicate, or irrelevant automation."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services.workflow_timer_constants import (
    CTR_ACTIVATION_PENDING_SINCE,
    DOC_AWAITING_EVIDENCE_REVIEW_SINCE,
    REQ_OVERDUE_SINCE,
    TENANT_ACTIVATION_PENDING_SINCE,
)
from services.workflow_timer_service import work_order_stall_context

logger = logging.getLogger(__name__)

_TERMINAL_WO = frozenset({"CANCELLED", "COMPLETED", "VERIFIED", "CLOSED"})
_OVERDUE_REQ_STATUSES = frozenset({"OVERDUE", "EXPIRED"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        s = raw if isinstance(raw, str) else str(raw)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except (ValueError, TypeError):
        return None


def _age_hours(raw: Any, now: Optional[datetime] = None) -> Optional[float]:
    d = _parse_iso(raw)
    if not d:
        return None
    ref = now or _now()
    return (ref - d).total_seconds() / 3600.0


def nudge_idempotency_key(
    entity_type: str,
    entity_id: str,
    nudge_key: str,
    tier: str,
    *,
    day: Optional[str] = None,
) -> str:
    d = day or _now().strftime("%Y-%m-%d")
    return f"workflow_nudge:{entity_type}:{entity_id}:{nudge_key}:{tier}:{d}"


@dataclass
class ReconciliationDecision:
    fire: bool
    suppress_reason: Optional[str] = None
    stall_context: Optional[Dict[str, Any]] = None
    age_hours: Optional[float] = None
    waiting_on: Optional[str] = None


async def _duplicate_idempotency_blocked(idempotency_key: str) -> bool:
    db = database.get_db()
    if db is None:
        return False
    existing = await db.message_logs.find_one({"idempotency_key": idempotency_key}, {"_id": 1})
    return existing is not None


async def _tier_sent_recently(entity_type: str, entity_id: str, nudge_key: str, tier: str) -> bool:
    db = database.get_db()
    if db is None:
        return False
    doc = await db.workflow_nudge_audit.find_one(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "nudge_key": nudge_key,
            "tier": tier,
            "outcome": "sent",
        },
        {"_id": 1},
    )
    return doc is not None


async def reconcile_work_order_nudge(
    wo: Dict[str, Any],
    *,
    nudge_key: str,
    tier: str,
    expected_stall_type: str,
    min_age_hours: float,
    waiting_on: Optional[str] = None,
) -> ReconciliationDecision:
    wid = (wo.get("work_order_id") or "").strip()
    st = (wo.get("status") or "").upper()
    if st in _TERMINAL_WO:
        return ReconciliationDecision(False, "entity_terminal")
    stall = work_order_stall_context(wo)
    if not stall:
        return ReconciliationDecision(False, "no_active_stall")
    if stall.get("stall_type") != expected_stall_type:
        return ReconciliationDecision(False, "stall_mismatch")
    if waiting_on and stall.get("waiting_on") != waiting_on:
        return ReconciliationDecision(False, "waiting_on_mismatch")
    age = stall.get("age_hours")
    if age is None or age < min_age_hours:
        return ReconciliationDecision(False, "below_age_threshold", age_hours=age)
    idem = nudge_idempotency_key("wo", wid, nudge_key, tier)
    if await _duplicate_idempotency_blocked(idem):
        return ReconciliationDecision(False, "duplicate_same_day", stall_context=stall, age_hours=age)
    if await _tier_sent_recently("work_order", wid, nudge_key, tier):
        return ReconciliationDecision(False, "tier_already_sent", stall_context=stall, age_hours=age)
    return ReconciliationDecision(
        True,
        stall_context=stall,
        age_hours=age,
        waiting_on=stall.get("waiting_on"),
    )


async def reconcile_activation_nudge(
    entity: Dict[str, Any],
    *,
    entity_type: str,
    entity_id: str,
    nudge_key: str,
    tier: str,
    min_age_hours: float,
    pending_field: str,
) -> ReconciliationDecision:
    if not entity.get(pending_field):
        return ReconciliationDecision(False, "activation_complete")
    if (entity.get("status") or "").lower() in ("active", "archived", "suspended"):
        if entity_type == "contractor" and entity.get("activated_at"):
            return ReconciliationDecision(False, "activation_complete")
        if entity_type == "tenant" and (entity.get("password_status") or "").upper() == "SET":
            return ReconciliationDecision(False, "activation_complete")
    age = _age_hours(entity.get(pending_field))
    if age is None or age < min_age_hours:
        return ReconciliationDecision(False, "below_age_threshold", age_hours=age)
    idem = nudge_idempotency_key(entity_type, entity_id, nudge_key, tier)
    if await _duplicate_idempotency_blocked(idem):
        return ReconciliationDecision(False, "duplicate_same_day", age_hours=age)
    if await _tier_sent_recently(entity_type, entity_id, nudge_key, tier):
        return ReconciliationDecision(False, "tier_already_sent", age_hours=age)
    return ReconciliationDecision(True, age_hours=age)


async def reconcile_evidence_review_nudge(
    doc: Dict[str, Any],
    *,
    nudge_key: str,
    tier: str,
    min_age_hours: float,
) -> ReconciliationDecision:
    did = (doc.get("document_id") or "").strip()
    review = (doc.get("evidence_review_state") or "").upper()
    if review not in ("PENDING_REVIEW", "NEEDS_REVIEW", ""):
        if review in ("ACCEPTED_UNVERIFIED", "REJECTED", "VERIFIED"):
            return ReconciliationDecision(False, "review_terminal")
    since = doc.get(DOC_AWAITING_EVIDENCE_REVIEW_SINCE) or doc.get("uploaded_at")
    age = _age_hours(since)
    if age is None or age < min_age_hours:
        return ReconciliationDecision(False, "below_age_threshold", age_hours=age)
    idem = nudge_idempotency_key("document", did, nudge_key, tier)
    if await _duplicate_idempotency_blocked(idem):
        return ReconciliationDecision(False, "duplicate_same_day", age_hours=age)
    if await _tier_sent_recently("document", did, nudge_key, tier):
        return ReconciliationDecision(False, "tier_already_sent", age_hours=age)
    return ReconciliationDecision(True, age_hours=age)


async def reconcile_requirement_overdue_nudge(
    req: Dict[str, Any],
    *,
    nudge_key: str,
    tier: str,
    min_age_hours: float,
) -> ReconciliationDecision:
    rid = (req.get("requirement_id") or req.get("_id") or "").strip() or str(req.get("requirement_id") or "")
    status = (req.get("status") or "").upper()
    if status not in _OVERDUE_REQ_STATUSES:
        return ReconciliationDecision(False, "not_overdue")
    since = req.get(REQ_OVERDUE_SINCE) or req.get("due_date")
    age = _age_hours(since)
    if age is None or age < min_age_hours:
        return ReconciliationDecision(False, "below_age_threshold", age_hours=age)
    idem = nudge_idempotency_key("requirement", rid, nudge_key, tier)
    if await _duplicate_idempotency_blocked(idem):
        return ReconciliationDecision(False, "duplicate_same_day", age_hours=age)
    if await _tier_sent_recently("requirement", rid, nudge_key, tier):
        return ReconciliationDecision(False, "tier_already_sent", age_hours=age)
    return ReconciliationDecision(True, age_hours=age)


async def record_nudge_suppressed(
    *,
    entity_type: str,
    entity_id: str,
    client_id: Optional[str],
    nudge_key: str,
    tier: str,
    automation_type: str,
    suppress_reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    db = database.get_db()
    now = _now().isoformat()
    await db.workflow_nudge_audit.insert_one(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "client_id": client_id,
            "nudge_key": nudge_key,
            "tier": tier,
            "automation_type": automation_type,
            "outcome": "suppressed",
            "suppress_reason": suppress_reason,
            "created_at": now,
            "metadata": metadata or {},
        }
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_NUDGE_SUPPRESSED,
        client_id=client_id,
        resource_type=entity_type,
        resource_id=entity_id,
        metadata={
            "nudge_key": nudge_key,
            "tier": tier,
            "reason": suppress_reason,
            "automation_type": automation_type,
            **(metadata or {}),
        },
    )


async def record_nudge_sent(
    *,
    entity_type: str,
    entity_id: str,
    client_id: Optional[str],
    nudge_key: str,
    tier: str,
    automation_type: str,
    idempotency_key: str,
    message_id: Optional[str] = None,
    waiting_on: Optional[str] = None,
    escalation_level: int = 1,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    db = database.get_db()
    now = _now().isoformat()
    await db.workflow_nudge_audit.insert_one(
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "client_id": client_id,
            "nudge_key": nudge_key,
            "tier": tier,
            "automation_type": automation_type,
            "outcome": "sent",
            "idempotency_key": idempotency_key,
            "message_id": message_id,
            "waiting_on": waiting_on,
            "escalation_level": escalation_level,
            "created_at": now,
            "metadata": metadata or {},
        }
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_NUDGE_SENT,
        client_id=client_id,
        resource_type=entity_type,
        resource_id=entity_id,
        metadata={
            "nudge_key": nudge_key,
            "tier": tier,
            "automation_type": automation_type,
            "idempotency_key": idempotency_key,
            "waiting_on": waiting_on,
            "escalation_level": escalation_level,
            **(metadata or {}),
        },
    )
