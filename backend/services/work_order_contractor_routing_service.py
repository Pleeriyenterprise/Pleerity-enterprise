"""
Client-confirmed contractor assignment routing for work orders.
Recommendations do not set contractor_id or send contractor emails until the client confirms (or admin overrides).
"""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from database import database
import logging

from models import AuditAction
from services import contractor_service
from services import maintenance_service
from services.work_order_assignment_constants import (
    ASSIGNMENT_ROUTING_ASSIGNED,
    ASSIGNMENT_ROUTING_CONTRACTOR_DECLINED,
    ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN,
    ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
    ASSIGNMENT_ROUTING_UNASSIGNED,
    PENDING_STATES,
)
from services.work_order_execution_constants import (
    COMPLIANCE_BOOKING_PENDING_CLIENT_CONFIRMATION,
    EXECUTION_CAPABILITY_COMPLIANCE,
    WORK_ORDER_KIND_COMPLIANCE,
)
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


def _rid_hash(email: str) -> str:
    """Short stable fragment for notification idempotency keys (per recipient)."""
    return hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()[:16]


def _confirmation_deadline_hours_for_work_order(wo: Dict[str, Any]) -> int:
    sev = (wo.get("severity") or "").strip().lower()
    if sev in ("urgent", "high") or wo.get("sla_breached_at") or wo.get("sla_breach_risk_at"):
        raw = (os.environ.get("CLIENT_CONTRACTOR_CONFIRM_HOURS_CRITICAL") or "4").strip()
    else:
        raw = (os.environ.get("CLIENT_CONTRACTOR_CONFIRM_HOURS_STANDARD") or "24").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 24 if sev not in ("urgent", "high") else 4


def _extension_hours_after_reminder() -> int:
    raw = (os.environ.get("CLIENT_CONTRACTOR_CONFIRM_REMINDER_EXTENSION_HOURS") or "12").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 12


async def invalidate_pending_routing_for_work_order(work_order_id: str, reason: str) -> None:
    """Clear pending recommendation when work order is cancelled/completed or superseded."""
    db = database.get_db()
    wo = await db.work_orders.find_one({"work_order_id": work_order_id}, {"_id": 0, "assignment_routing_state": 1})
    if not wo:
        return
    st = (wo.get("assignment_routing_state") or ASSIGNMENT_ROUTING_UNASSIGNED).strip().upper()
    if st in (ASSIGNMENT_ROUTING_ASSIGNED, ASSIGNMENT_ROUTING_UNASSIGNED):
        return
    now = datetime.now(timezone.utc).isoformat()
    await db.work_orders.update_one(
        {"work_order_id": work_order_id},
        {
            "$set": {
                "assignment_routing_state": ASSIGNMENT_ROUTING_UNASSIGNED,
                "recommended_contractor_id": None,
                "recommendation_reason_summary": None,
                "recommended_at": None,
                "recommendation_id": None,
                "client_confirmation_deadline_at": None,
                "confirmation_reminder_sent_at": None,
                "routing_decline_note": None,
                "routing_pending_admin": False,
                "routing_invalidation_reason": reason,
                "updated_at": now,
            },
        },
    )
    try:
        await create_audit_log(
            action=AuditAction.WORK_ORDER_CONTRACTOR_ROUTING_INVALIDATED,
            actor_id="system",
            resource_type="work_order",
            resource_id=work_order_id,
            metadata={"reason": reason[:500]},
        )
    except Exception as e:
        logger.warning("Audit routing invalidated failed: %s", e)


async def _load_wo_client(work_order_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    wo = await db.work_orders.find_one({"work_order_id": work_order_id})
    if not wo or (wo.get("client_id") or "").strip() != (client_id or "").strip():
        return None
    wo.pop("_id", None)
    return wo


def _actions_for_state(st: str, wo: Dict[str, Any]) -> List[str]:
    if wo.get("contractor_id"):
        return ["view_assignment"]
    if st == ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION:
        return ["confirm_recommended", "decline_recommendation", "choose_alternate", "add_personal_contractor", "request_admin"]
    if st == ASSIGNMENT_ROUTING_CONTRACTOR_DECLINED:
        return ["choose_alternate", "add_personal_contractor", "request_admin", "generate_recommendation"]
    if st == ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN:
        return ["wait_for_admin"]
    return ["generate_recommendation", "choose_alternate", "add_personal_contractor"]


async def get_contractor_routing_state(work_order_id: str, client_id: str) -> Dict[str, Any]:
    wo = await _load_wo_client(work_order_id, client_id)
    if not wo:
        return {"ok": False, "error": "not_found"}
    st = (wo.get("assignment_routing_state") or ASSIGNMENT_ROUTING_UNASSIGNED).strip() or ASSIGNMENT_ROUTING_UNASSIGNED
    rec_id = wo.get("recommended_contractor_id")
    rec_summary = wo.get("recommendation_reason_summary")
    rec_contractor = await contractor_service.get_contractor(rec_id) if rec_id else None
    routing = await contractor_service.recommend_contractors_for_work_order(work_order_id, client_id=client_id, limit=5)
    return {
        "ok": True,
        "work_order_id": work_order_id,
        "assignment_routing_state": st,
        "requires_client_assignment_confirmation": wo.get("requires_client_assignment_confirmation", True),
        "recommended_contractor_id": rec_id,
        "recommendation_reason_summary": rec_summary,
        "recommended_at": wo.get("recommended_at"),
        "recommendation_id": wo.get("recommendation_id"),
        "client_confirmation_deadline_at": wo.get("client_confirmation_deadline_at"),
        "confirmation_reminder_sent_at": wo.get("confirmation_reminder_sent_at"),
        "confirmation_escalated_at": wo.get("confirmation_escalated_at"),
        "routing_pending_admin": bool(wo.get("routing_pending_admin")),
        "routing_decline_note": wo.get("routing_decline_note"),
        "recommended_contractor_preview": rec_contractor,
        "available_actions": _actions_for_state(st, wo),
        "routing_payload": routing.get("routing"),
        "ranked_preview": routing.get("contractors", [])[:5],
    }


async def generate_and_notify_recommendation(
    work_order_id: str,
    client_id: str,
    *,
    actor_portal_user_id: Optional[str],
) -> Dict[str, Any]:
    wo = await _load_wo_client(work_order_id, client_id)
    if not wo:
        raise ValueError("Work order not found")
    if wo.get("contractor_id"):
        raise ValueError("Work order already has a contractor assigned")
    if str(wo.get("status") or "").upper() in (
        maintenance_service.STATUS_CANCELLED,
        maintenance_service.STATUS_COMPLETED,
    ):
        raise ValueError("Work order is closed")
    ranked = await contractor_service.recommend_contractors_for_work_order(
        work_order_id, client_id=client_id, limit=1
    )
    contractors = ranked.get("contractors") or []
    if not contractors:
        now = datetime.now(timezone.utc).isoformat()
        db = database.get_db()
        await db.work_orders.update_one(
            {"work_order_id": work_order_id},
            {
                "$set": {
                    "assignment_routing_state": ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN,
                    "routing_pending_admin": True,
                    "routing_decline_note": "No eligible contractor recommendation available",
                    "updated_at": now,
                },
            },
        )
        await create_audit_log(
            action=AuditAction.WORK_ORDER_CONTRACTOR_ROUTING_ESCALATED_ADMIN,
            actor_id=actor_portal_user_id or "system",
            client_id=client_id,
            resource_type="work_order",
            resource_id=work_order_id,
            metadata={"reason": "no_eligible_recommendation"},
        )
        return {"ok": False, "escalated": True, "reason": "no_eligible_contractor"}
    top = contractors[0]
    cid = top.get("contractor_id")
    reasons = top.get("reasons") or []
    summary = "; ".join(reasons[:4]) if reasons else "Top-ranked eligible contractor for this job."
    rid = str(uuid.uuid4())
    hours = _confirmation_deadline_hours_for_work_order(wo)
    deadline = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    db = database.get_db()
    booking_extra = {}
    if (wo.get("work_order_kind") or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE:
        booking_extra["compliance_booking_status"] = COMPLIANCE_BOOKING_PENDING_CLIENT_CONFIRMATION
    await db.work_orders.update_one(
        {"work_order_id": work_order_id},
        {
            "$set": {
                "assignment_routing_state": ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
                "recommended_contractor_id": cid,
                "recommendation_reason_summary": summary[:2000],
                "recommended_at": now,
                "recommendation_id": rid,
                "client_confirmation_deadline_at": deadline,
                "confirmation_reminder_sent_at": None,
                "confirmation_escalated_at": None,
                "routing_decline_note": None,
                "routing_pending_admin": False,
                "routing_invalidation_reason": None,
                "updated_at": now,
                **booking_extra,
            },
        },
    )
    await create_audit_log(
        action=AuditAction.WORK_ORDER_CONTRACTOR_RECOMMENDED,
        actor_id=actor_portal_user_id or "system",
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={
            "recommended_contractor_id": cid,
            "recommendation_id": rid,
            "work_order_kind": wo.get("work_order_kind"),
            "requirement_code": wo.get("requirement_code"),
            "routing_context": (
                "compliance_execution"
                if (wo.get("work_order_kind") or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE
                else "maintenance_repair"
            ),
        },
    )
    await _notify_client_recommendation_pending(work_order_id, client_id, wo, top, deadline, routing=ranked.get("routing"))
    await create_audit_log(
        action=AuditAction.WORK_ORDER_CONTRACTOR_RECOMMENDATION_CLIENT_NOTIFIED,
        actor_id=actor_portal_user_id or "system",
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"recommended_contractor_id": cid},
    )
    return {
        "ok": True,
        "recommended_contractor_id": cid,
        "recommendation_id": rid,
        "client_confirmation_deadline_at": deadline,
        "recommendation_reason_summary": summary,
    }


async def _notify_client_recommendation_pending(
    work_order_id: str,
    client_id: str,
    wo: Dict[str, Any],
    top_rank: Dict[str, Any],
    deadline_iso: str,
    routing: Optional[Dict[str, Any]] = None,
) -> None:
    db = database.get_db()
    prop_line = ""
    if wo.get("property_id"):
        prop = await db.properties.find_one(
            {"property_id": wo["property_id"], "client_id": client_id},
            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1},
        )
        if prop:
            prop_line = ", ".join(p for p in [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")] if p)
    cname = top_rank.get("name") or top_rank.get("company_name") or "Contractor"
    urgency = (routing or {}).get("assignment_urgency") or "normal"
    sla_msg = "; ".join((routing or {}).get("routing_messages") or [])
    desc = (wo.get("description") or "")[:300]
    is_comp = (wo.get("work_order_kind") or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE
    req_line = ""
    if is_comp and wo.get("requirement_code"):
        req_line = f"<p><strong>Compliance requirement:</strong> {wo.get('requirement_code')}</p>"
    if is_comp:
        headline = "Compliance contractor recommendation (inspection / renewal / certification)"
        subj = f"Action required: confirm compliance contractor for work order {work_order_id}"
        in_title = "Confirm compliance contractor"
        in_msg = (
            f"Compliance work order {work_order_id}: confirm the recommended contractor before we notify them "
            f"(this is not a generic maintenance repair dispatch)."
        )
    else:
        headline = "Maintenance contractor recommendation (repair work order)"
        subj = f"Action required: confirm maintenance contractor for work order {work_order_id}"
        in_title = "Confirm maintenance contractor"
        in_msg = f"Maintenance work order {work_order_id}: review recommended contractor {cname} before we notify them."
    body = (
        f"<p><strong>{headline}</strong> — work order <strong>{work_order_id}</strong>.</p>"
        f"{req_line}"
        f"<p>{desc}</p>"
        f"<p><strong>Property:</strong> {prop_line or 'See portal'}</p>"
        f"<p><strong>Urgency / SLA:</strong> {urgency}. {sla_msg}</p>"
        f"<p><strong>Recommended:</strong> {cname}</p>"
        f"<p><strong>Why:</strong> {top_rank.get('reasons') and '; '.join(top_rank['reasons'][:5]) or 'Rule-based routing match.'}</p>"
        f"<p><strong>Please respond by:</strong> {deadline_iso}</p>"
        f"<p>Open your client portal to <strong>confirm</strong> this contractor, <strong>choose another</strong>, or <strong>add your own contractor</strong>.</p>"
    )
    cursor = db.portal_users.find(
        {"client_id": client_id},
        {"_id": 0, "portal_user_id": 1, "auth_email": 1, "email": 1},
    )
    users = await cursor.to_list(50)
    from services.notification_orchestrator import notification_orchestrator

    for u in users:
        email = (u.get("auth_email") or u.get("email") or "").strip()
        if not email:
            continue
        try:
            await notification_orchestrator.send(
                template_key="ADMIN_MANUAL",
                client_id=client_id,
                context={
                    "recipient": email,
                    "subject": subj,
                    "message": body,
                    "company_name": "Pleerity Enterprise Ltd",
                },
                idempotency_key=f"wo_rec_client_{work_order_id}_{_rid_hash(email)}",
                event_type="work_order_contractor_recommendation",
            )
        except Exception as e:
            logger.warning("Recommendation email to %s failed: %s", email, e)
        try:
            from services.order_service import create_in_app_notification

            await create_in_app_notification(
                recipient_id=u.get("portal_user_id") or email,
                title=in_title,
                message=in_msg,
                notification_type="work_order_contractor_routing",
                link="/operations/work-orders",
                metadata={"work_order_id": work_order_id, "recommended_contractor_id": top_rank.get("contractor_id")},
                severity="medium",
                notification_category="operations",
                related_entity_type="work_order",
                related_entity_id=work_order_id,
                primary_cta_label="Work orders",
                primary_cta_path="/operations/work-orders",
            )
        except Exception as e:
            logger.warning("In-app recommendation notify failed: %s", e)


async def confirm_recommended_contractor(
    work_order_id: str,
    client_id: str,
    *,
    actor_portal_user_id: Optional[str],
) -> Dict[str, Any]:
    wo = await _load_wo_client(work_order_id, client_id)
    if not wo:
        raise ValueError("Work order not found")
    st = wo.get("assignment_routing_state")
    if st != ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION:
        raise ValueError("No pending recommendation to confirm")
    rc = wo.get("recommended_contractor_id")
    if not rc:
        raise ValueError("Missing recommended contractor")
    doc = await maintenance_service.update_work_order(
        work_order_id,
        contractor_id=rc,
        assigned_by=actor_portal_user_id,
        allow_direct_contractor_assignment=True,
        assignment_profile="standard",
    )
    await create_audit_log(
        action=AuditAction.WORK_ORDER_CLIENT_CONFIRMED_CONTRACTOR,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"contractor_id": rc, "source": "recommended"},
    )
    return {"ok": True, "work_order": doc}


async def confirm_alternate_contractor(
    work_order_id: str,
    client_id: str,
    alternate_contractor_id: str,
    *,
    actor_portal_user_id: Optional[str],
) -> Dict[str, Any]:
    wo = await _load_wo_client(work_order_id, client_id)
    if not wo:
        raise ValueError("Work order not found")
    if wo.get("contractor_id"):
        raise ValueError("Work order already assigned")
    st = wo.get("assignment_routing_state")
    allowed = set(PENDING_STATES) | {ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN, ASSIGNMENT_ROUTING_UNASSIGNED}
    if st not in allowed:
        raise ValueError("Work order is not in a state that allows alternate selection")
    doc = await maintenance_service.update_work_order(
        work_order_id,
        contractor_id=alternate_contractor_id,
        assigned_by=actor_portal_user_id,
        allow_direct_contractor_assignment=True,
        assignment_profile="standard",
    )
    await create_audit_log(
        action=AuditAction.WORK_ORDER_ALTERNATE_CONTRACTOR_SELECTED,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"contractor_id": alternate_contractor_id},
    )
    return {"ok": True, "work_order": doc}


async def decline_recommendation(
    work_order_id: str,
    client_id: str,
    *,
    note: Optional[str],
    actor_portal_user_id: Optional[str],
) -> Dict[str, Any]:
    wo = await _load_wo_client(work_order_id, client_id)
    if not wo:
        raise ValueError("Work order not found")
    if wo.get("assignment_routing_state") != ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION:
        raise ValueError("No active recommendation to decline")
    now = datetime.now(timezone.utc).isoformat()
    db = database.get_db()
    await db.work_orders.update_one(
        {"work_order_id": work_order_id},
        {
            "$set": {
                "assignment_routing_state": ASSIGNMENT_ROUTING_CONTRACTOR_DECLINED,
                "routing_decline_note": (note or "")[:2000],
                "recommended_contractor_id": None,
                "recommendation_reason_summary": None,
                "recommended_at": None,
                "recommendation_id": None,
                "client_confirmation_deadline_at": None,
                "confirmation_reminder_sent_at": None,
                "updated_at": now,
            },
        },
    )
    await create_audit_log(
        action=AuditAction.WORK_ORDER_CLIENT_DECLINED_CONTRACTOR_RECOMMENDATION,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"note": (note or "")[:500]},
    )
    return {"ok": True, "assignment_routing_state": ASSIGNMENT_ROUTING_CONTRACTOR_DECLINED}


async def request_admin_for_routing(
    work_order_id: str,
    client_id: str,
    *,
    note: Optional[str],
    actor_portal_user_id: Optional[str],
) -> Dict[str, Any]:
    wo = await _load_wo_client(work_order_id, client_id)
    if not wo:
        raise ValueError("Work order not found")
    now = datetime.now(timezone.utc).isoformat()
    db = database.get_db()
    await db.work_orders.update_one(
        {"work_order_id": work_order_id},
        {
            "$set": {
                "assignment_routing_state": ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN,
                "routing_pending_admin": True,
                "routing_decline_note": (note or "Client requested admin handling")[:2000],
                "recommended_contractor_id": None,
                "recommendation_reason_summary": None,
                "recommended_at": None,
                "recommendation_id": None,
                "client_confirmation_deadline_at": None,
                "updated_at": now,
            },
        },
    )
    await create_audit_log(
        action=AuditAction.WORK_ORDER_CONTRACTOR_ROUTING_ESCALATED_ADMIN,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"note": (note or "")[:500], "source": "client_request"},
    )
    try:
        from utils.submission_utils import notify_admin_new_submission

        await notify_admin_new_submission(
            "work_order_contractor_routing",
            work_order_id,
            f"Client escalated contractor routing for WO {work_order_id}",
            detail_url_path=f"/admin/ops/maintenance/work-orders/{work_order_id}",
        )
    except Exception as e:
        logger.warning("Admin notify escalation failed: %s", e)
    return {"ok": True, "assignment_routing_state": ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN}


async def add_personal_contractor_and_assign(
    work_order_id: str,
    client_id: str,
    *,
    name: str,
    email: str,
    phone: Optional[str],
    trade_types: List[str],
    actor_portal_user_id: Optional[str],
) -> Dict[str, Any]:
    wo = await _load_wo_client(work_order_id, client_id)
    if not wo:
        raise ValueError("Work order not found")
    if wo.get("contractor_id"):
        raise ValueError("Work order already assigned")
    if str(wo.get("status") or "").upper() in (
        maintenance_service.STATUS_CANCELLED,
        maintenance_service.STATUS_COMPLETED,
    ):
        raise ValueError("Work order is closed")
    extra_personal: Dict[str, Any] = {}
    if (wo.get("work_order_kind") or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE:
        extra_personal["execution_capabilities"] = EXECUTION_CAPABILITY_COMPLIANCE
        rc = (wo.get("requirement_code") or "").strip().lower()
        if rc:
            extra_personal["supported_requirement_codes"] = [rc]
    cdoc = await contractor_service.create_contractor_client_supplied_personal(
        client_id=client_id,
        name=name.strip(),
        email=email.strip(),
        trade_types=trade_types,
        phone=phone.strip() if phone else None,
        **extra_personal,
    )
    cid = cdoc["contractor_id"]
    await create_audit_log(
        action=AuditAction.WORK_ORDER_PERSONAL_CONTRACTOR_ADDED,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"contractor_id": cid},
    )
    doc = await maintenance_service.update_work_order(
        work_order_id,
        contractor_id=cid,
        assigned_by=actor_portal_user_id,
        allow_direct_contractor_assignment=True,
        assignment_profile="client_supplied_personal",
    )
    return {"ok": True, "contractor": cdoc, "work_order": doc}


async def run_contractor_confirmation_timeout_sweep() -> Dict[str, Any]:
    """
    Reminder then admin escalation. No auto-assign unless CONTRACTOR_ROUTING_AUTO_ASSIGN_ON_TIMEOUT=true (off by default).
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    auto = (os.environ.get("CONTRACTOR_ROUTING_AUTO_ASSIGN_ON_TIMEOUT") or "").strip().lower() in ("1", "true", "yes")
    cursor = db.work_orders.find(
        {
            "assignment_routing_state": ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
            "contractor_id": None,
            "client_confirmation_deadline_at": {"$exists": True, "$ne": None},
        },
        {"_id": 0},
    )
    rows = await cursor.to_list(200)
    reminders = 0
    escalations = 0
    for wo in rows:
        wid = wo["work_order_id"]
        deadline_raw = wo.get("client_confirmation_deadline_at")
        try:
            deadline = deadline_raw if isinstance(deadline_raw, datetime) else datetime.fromisoformat(str(deadline_raw).replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if now <= deadline:
            continue
        if not wo.get("confirmation_reminder_sent_at"):
            ext = now + timedelta(hours=_extension_hours_after_reminder())
            await db.work_orders.update_one(
                {"work_order_id": wid},
                {
                    "$set": {
                        "confirmation_reminder_sent_at": now_iso,
                        "client_confirmation_deadline_at": ext.isoformat(),
                        "updated_at": now_iso,
                    },
                },
            )
            try:
                await create_audit_log(
                    action=AuditAction.WORK_ORDER_CONTRACTOR_CONFIRMATION_REMINDER_SENT,
                    actor_id="system",
                    client_id=wo.get("client_id"),
                    resource_type="work_order",
                    resource_id=wid,
                    metadata={},
                )
            except Exception:
                pass
            client_id = wo.get("client_id")
            if client_id:
                wo_fresh = await db.work_orders.find_one({"work_order_id": wid})
                if wo_fresh:
                    wo_fresh.pop("_id", None)
                rc = (wo_fresh or wo).get("recommended_contractor_id")
                top_preview: Dict[str, Any] = {"contractor_id": rc, "name": "", "reasons": ["Reminder: please confirm or change contractor"]}
                if rc:
                    cd = await contractor_service.get_contractor(rc)
                    if cd:
                        top_preview["name"] = cd.get("name") or cd.get("company_name") or ""
                await _notify_client_recommendation_pending(
                    wid,
                    str(client_id),
                    wo_fresh or wo,
                    top_preview,
                    ext.isoformat(),
                    routing=None,
                )
            reminders += 1
            continue
        if auto and wo.get("recommended_contractor_id"):
            # Explicit opt-in only; still log as policy-driven
            try:
                await maintenance_service.update_work_order(
                    wid,
                    contractor_id=wo["recommended_contractor_id"],
                    assigned_by="system_timeout_auto",
                    allow_direct_contractor_assignment=True,
                    assignment_profile="standard",
                )
            except Exception as e:
                logger.warning("Auto-assign on timeout failed %s: %s", wid, e)
            continue
        if not wo.get("confirmation_escalated_at"):
            await db.work_orders.update_one(
                {"work_order_id": wid},
                {
                    "$set": {
                        "confirmation_escalated_at": now_iso,
                        "assignment_routing_state": ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN,
                        "routing_pending_admin": True,
                        "updated_at": now_iso,
                    },
                },
            )
            try:
                await create_audit_log(
                    action=AuditAction.WORK_ORDER_CONTRACTOR_CONFIRMATION_TIMEOUT,
                    actor_id="system",
                    client_id=wo.get("client_id"),
                    resource_type="work_order",
                    resource_id=wid,
                    metadata={},
                )
                await create_audit_log(
                    action=AuditAction.WORK_ORDER_CONTRACTOR_ROUTING_ESCALATED_ADMIN,
                    actor_id="system",
                    client_id=wo.get("client_id"),
                    resource_type="work_order",
                    resource_id=wid,
                    metadata={"reason": "confirmation_timeout"},
                )
            except Exception:
                pass
            try:
                from utils.submission_utils import notify_admin_new_submission

                await notify_admin_new_submission(
                    "work_order_contractor_routing_timeout",
                    wid,
                    f"Work order {wid}: client did not confirm contractor in time",
                    detail_url_path=f"/admin/ops/maintenance/work-orders/{wid}",
                )
            except Exception as e:
                logger.warning("Admin notify timeout failed: %s", e)
            escalations += 1
    return {"reminders": reminders, "escalations": escalations, "scanned": len(rows)}
