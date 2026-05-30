"""Authoritative workflow timer updates — never driven from frontend."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services.workflow_timer_constants import (
    CTR_ACTIVATION_PENDING_SINCE,
    DOC_AWAITING_EVIDENCE_REVIEW_SINCE,
    DOC_AWAITING_LANDLORD_EVIDENCE_ACTION_SINCE,
    DOC_EVIDENCE_UPLOADED_SINCE,
    REQ_OVERDUE_SINCE,
    REQ_UNRESOLVED_SINCE,
    TENANT_ACTIVATION_PENDING_SINCE,
    TENANT_PORTAL_INVITE_SENT_AT,
    WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE,
    WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE,
    WO_AWAITING_QUOTE_SINCE,
    WO_AWAITING_VISIT_CONFIRMATION_SINCE,
    WO_AWAITING_VISIT_RESCHEDULE_SINCE,
    WO_COMPLETION_PROOF_PENDING_SINCE,
    WO_INVOICE_PENDING_SINCE,
    WO_QUOTE_REQUESTED_AT,
    WO_VISIT_PROPOSED_SINCE,
    WO_WORK_AUTHORISED_SINCE,
    WORK_ORDER_TIMER_FIELDS,
)

logger = logging.getLogger(__name__)

_TERMINAL_WO = frozenset({"CANCELLED", "COMPLETED", "VERIFIED", "CLOSED"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _patch_work_order_timers(
    work_order_id: str,
    *,
    set_fields: Dict[str, Any],
    unset_fields: Sequence[str],
    reason: str,
    actor_id: Optional[str] = None,
) -> None:
    wid = (work_order_id or "").strip()
    if not wid:
        return
    update: Dict[str, Any] = {"$set": {**set_fields, "updated_at": _iso(_now())}}
    if unset_fields:
        update["$unset"] = {f: "" for f in unset_fields}
    db = database.get_db()
    await db.work_orders.update_one({"work_order_id": wid}, update)
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="work_order",
        resource_id=wid,
        metadata={"reason": reason, "set": list(set_fields.keys()), "unset": list(unset_fields)},
    )


async def on_work_order_quote_requested(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _now()
    await _patch_work_order_timers(
        work_order_id,
        set_fields={
            WO_QUOTE_REQUESTED_AT: _iso(now),
            WO_AWAITING_QUOTE_SINCE: _iso(now),
        },
        unset_fields=[
            WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE,
            WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE,
        ],
        reason="quote_requested",
        actor_id=actor_id,
    )


async def on_work_order_quote_submitted(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _now()
    await _patch_work_order_timers(
        work_order_id,
        set_fields={WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE: _iso(now)},
        unset_fields=[WO_AWAITING_QUOTE_SINCE, WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE],
        reason="quote_submitted",
        actor_id=actor_id,
    )


async def on_work_order_quote_revision_requested(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _now()
    await _patch_work_order_timers(
        work_order_id,
        set_fields={WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE: _iso(now)},
        unset_fields=[WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE],
        reason="quote_revision_requested",
        actor_id=actor_id,
    )


async def on_work_order_quote_approved(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _now()
    await _patch_work_order_timers(
        work_order_id,
        set_fields={WO_WORK_AUTHORISED_SINCE: _iso(now)},
        unset_fields=[
            WO_AWAITING_QUOTE_SINCE,
            WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE,
            WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE,
        ],
        reason="quote_approved",
        actor_id=actor_id,
    )


async def on_work_order_visit_proposed(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _now()
    await _patch_work_order_timers(
        work_order_id,
        set_fields={
            WO_VISIT_PROPOSED_SINCE: _iso(now),
            WO_AWAITING_VISIT_CONFIRMATION_SINCE: _iso(now),
        },
        unset_fields=[WO_AWAITING_VISIT_RESCHEDULE_SINCE],
        reason="visit_proposed",
        actor_id=actor_id,
    )


async def on_work_order_visit_confirmed(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    await _patch_work_order_timers(
        work_order_id,
        set_fields={},
        unset_fields=[
            WO_VISIT_PROPOSED_SINCE,
            WO_AWAITING_VISIT_CONFIRMATION_SINCE,
            WO_AWAITING_VISIT_RESCHEDULE_SINCE,
        ],
        reason="visit_confirmed",
        actor_id=actor_id,
    )


async def on_work_order_visit_reschedule_requested(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _now()
    await _patch_work_order_timers(
        work_order_id,
        set_fields={WO_AWAITING_VISIT_RESCHEDULE_SINCE: _iso(now)},
        unset_fields=[WO_AWAITING_VISIT_CONFIRMATION_SINCE],
        reason="visit_reschedule_requested",
        actor_id=actor_id,
    )


async def on_work_order_visit_cancelled(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    await _patch_work_order_timers(
        work_order_id,
        set_fields={},
        unset_fields=[
            WO_VISIT_PROPOSED_SINCE,
            WO_AWAITING_VISIT_CONFIRMATION_SINCE,
            WO_AWAITING_VISIT_RESCHEDULE_SINCE,
        ],
        reason="visit_cancelled",
        actor_id=actor_id,
    )


async def on_work_order_completion_proof_pending(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    await _patch_work_order_timers(
        work_order_id,
        set_fields={WO_COMPLETION_PROOF_PENDING_SINCE: _iso(_now())},
        unset_fields=[],
        reason="completion_proof_pending",
        actor_id=actor_id,
    )


async def on_work_order_invoice_pending(work_order_id: str, *, actor_id: Optional[str] = None) -> None:
    await _patch_work_order_timers(
        work_order_id,
        set_fields={WO_INVOICE_PENDING_SINCE: _iso(_now())},
        unset_fields=[],
        reason="invoice_pending",
        actor_id=actor_id,
    )


async def clear_work_order_timers(work_order_id: str, *, reason: str, actor_id: Optional[str] = None) -> None:
    await _patch_work_order_timers(
        work_order_id,
        set_fields={},
        unset_fields=list(WORK_ORDER_TIMER_FIELDS),
        reason=reason,
        actor_id=actor_id,
    )


async def on_contractor_portal_invite_sent(contractor_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _iso(_now())
    db = database.get_db()
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"portal_invite_sent_at": now, CTR_ACTIVATION_PENDING_SINCE: now}},
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="contractor",
        resource_id=contractor_id,
        metadata={"reason": "contractor_portal_invite_sent"},
    )


async def on_contractor_activated(contractor_id: str, *, actor_id: Optional[str] = None) -> None:
    db = database.get_db()
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$unset": {CTR_ACTIVATION_PENDING_SINCE: ""}},
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="contractor",
        resource_id=contractor_id,
        metadata={"reason": "contractor_activated"},
    )


async def on_tenant_portal_invite_sent(portal_user_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _iso(_now())
    db = database.get_db()
    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {
            "$set": {
                TENANT_PORTAL_INVITE_SENT_AT: now,
                TENANT_ACTIVATION_PENDING_SINCE: now,
                "portal_invite_sent_at": now,
            }
        },
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="tenant",
        resource_id=portal_user_id,
        metadata={"reason": "tenant_portal_invite_sent"},
    )


async def on_tenant_activated(portal_user_id: str, *, actor_id: Optional[str] = None) -> None:
    db = database.get_db()
    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {"$unset": {TENANT_ACTIVATION_PENDING_SINCE: ""}},
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="tenant",
        resource_id=tenant_id,
        metadata={"reason": "tenant_activated"},
    )


async def on_evidence_uploaded(document_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _iso(_now())
    db = database.get_db()
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {DOC_EVIDENCE_UPLOADED_SINCE: now, DOC_AWAITING_EVIDENCE_REVIEW_SINCE: now}},
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="document",
        resource_id=document_id,
        metadata={"reason": "evidence_uploaded"},
    )


async def on_evidence_review_started(document_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _iso(_now())
    db = database.get_db()
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {DOC_AWAITING_EVIDENCE_REVIEW_SINCE: now}, "$unset": {DOC_AWAITING_LANDLORD_EVIDENCE_ACTION_SINCE: ""}},
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="document",
        resource_id=document_id,
        metadata={"reason": "evidence_review_started"},
    )


async def on_evidence_needs_landlord_action(document_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _iso(_now())
    db = database.get_db()
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {DOC_AWAITING_LANDLORD_EVIDENCE_ACTION_SINCE: now}},
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="document",
        resource_id=document_id,
        metadata={"reason": "evidence_needs_landlord_action"},
    )


async def on_evidence_review_terminal(document_id: str, *, actor_id: Optional[str] = None) -> None:
    db = database.get_db()
    await db.documents.update_one(
        {"document_id": document_id},
        {
            "$unset": {
                DOC_EVIDENCE_UPLOADED_SINCE: "",
                DOC_AWAITING_EVIDENCE_REVIEW_SINCE: "",
                DOC_AWAITING_LANDLORD_EVIDENCE_ACTION_SINCE: "",
            }
        },
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="document",
        resource_id=document_id,
        metadata={"reason": "evidence_review_terminal"},
    )


async def on_requirement_overdue(requirement_id: str, *, actor_id: Optional[str] = None) -> None:
    now = _iso(_now())
    db = database.get_db()
    await db.requirements.update_one(
        {"requirement_id": requirement_id},
        {"$set": {REQ_OVERDUE_SINCE: now, REQ_UNRESOLVED_SINCE: now}},
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="requirement",
        resource_id=requirement_id,
        metadata={"reason": "requirement_overdue"},
    )


async def on_requirement_resolved(requirement_id: str, *, actor_id: Optional[str] = None) -> None:
    db = database.get_db()
    await db.requirements.update_one(
        {"requirement_id": requirement_id},
        {"$unset": {REQ_OVERDUE_SINCE: "", REQ_UNRESOLVED_SINCE: ""}},
    )
    await create_audit_log(
        action=AuditAction.WORKFLOW_TIMER_UPDATED,
        actor_id=actor_id,
        resource_type="requirement",
        resource_id=requirement_id,
        metadata={"reason": "requirement_resolved"},
    )


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


def work_order_stall_context(wo: Dict[str, Any], *, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Derive active stall for nudge reconciliation (server-side read only)."""
    st = (wo.get("status") or "").upper()
    if st in _TERMINAL_WO:
        return None
    ps = (wo.get("price_status") or "").upper()
    ss = (wo.get("schedule_status") or "").lower()

    if wo.get(WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE) or ps in ("REVISION_REQUESTED", "REJECTED"):
        return {
            "stall_type": "awaiting_contractor_quote_revision",
            "since": wo.get(WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE) or wo.get("quote_revision_requested_at"),
            "waiting_on": "contractor",
            "age_hours": _age_hours(wo.get(WO_AWAITING_CONTRACTOR_QUOTE_REVISION_SINCE) or wo.get("quote_revision_requested_at"), now),
        }
    if wo.get(WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE) or ps == "QUOTED":
        return {
            "stall_type": "awaiting_landlord_quote_response",
            "since": wo.get(WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE) or wo.get("quote_submitted_at"),
            "waiting_on": "landlord",
            "age_hours": _age_hours(wo.get(WO_AWAITING_LANDLORD_QUOTE_RESPONSE_SINCE) or wo.get("quote_submitted_at"), now),
        }
    if wo.get(WO_AWAITING_QUOTE_SINCE) or ps == "AWAITING_QUOTE":
        return {
            "stall_type": "awaiting_contractor_quote",
            "since": wo.get(WO_AWAITING_QUOTE_SINCE) or wo.get("assigned_at"),
            "waiting_on": "contractor",
            "age_hours": _age_hours(wo.get(WO_AWAITING_QUOTE_SINCE) or wo.get("assigned_at"), now),
        }
    if wo.get(WO_AWAITING_VISIT_RESCHEDULE_SINCE) or ss == "reschedule_requested":
        return {
            "stall_type": "awaiting_visit_reschedule",
            "since": wo.get(WO_AWAITING_VISIT_RESCHEDULE_SINCE),
            "waiting_on": "contractor",
            "age_hours": _age_hours(wo.get(WO_AWAITING_VISIT_RESCHEDULE_SINCE), now),
        }
    if wo.get(WO_AWAITING_VISIT_CONFIRMATION_SINCE) or (ss == "proposed" and wo.get("scheduled_at")):
        waiting = "landlord" if (wo.get("scheduled_by") or "").lower() == "contractor" else "contractor"
        return {
            "stall_type": "awaiting_visit_confirmation",
            "since": wo.get(WO_AWAITING_VISIT_CONFIRMATION_SINCE) or wo.get(WO_VISIT_PROPOSED_SINCE) or wo.get("last_schedule_update_at"),
            "waiting_on": waiting,
            "age_hours": _age_hours(
                wo.get(WO_AWAITING_VISIT_CONFIRMATION_SINCE) or wo.get(WO_VISIT_PROPOSED_SINCE) or wo.get("last_schedule_update_at"),
                now,
            ),
        }
    if wo.get(WO_COMPLETION_PROOF_PENDING_SINCE):
        return {
            "stall_type": "completion_proof_pending",
            "since": wo.get(WO_COMPLETION_PROOF_PENDING_SINCE),
            "waiting_on": "contractor",
            "age_hours": _age_hours(wo.get(WO_COMPLETION_PROOF_PENDING_SINCE), now),
        }
    if wo.get(WO_INVOICE_PENDING_SINCE):
        return {
            "stall_type": "invoice_pending",
            "since": wo.get(WO_INVOICE_PENDING_SINCE),
            "waiting_on": "contractor",
            "age_hours": _age_hours(wo.get(WO_INVOICE_PENDING_SINCE), now),
        }
    return None
