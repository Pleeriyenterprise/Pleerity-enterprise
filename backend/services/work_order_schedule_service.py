"""
Work order scheduling lifecycle: propose, confirm, reschedule request, cancel, reminders, ICS.
All mutations persist on work_orders and write audit_logs. No availability / slot engine.
"""
from __future__ import annotations

import base64
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database import database
from models import AuditAction
from services.work_order_execution_constants import COMPLIANCE_BOOKING_SCHEDULED, WORK_ORDER_KIND_COMPLIANCE
from services.work_order_schedule_constants import (
    AUDIT_EVENT_SCHEDULE_CANCELLED,
    AUDIT_EVENT_SCHEDULE_CONFIRMED,
    AUDIT_EVENT_SCHEDULE_PROPOSED,
    AUDIT_EVENT_SCHEDULE_REMINDER,
    AUDIT_EVENT_SCHEDULE_RESCHEDULE_REQUESTED,
    SCHEDULE_ACTOR_ADMIN,
    SCHEDULE_ACTOR_CLIENT,
    SCHEDULE_ACTOR_CONTRACTOR,
    SCHEDULE_STATUS_CANCELLED,
    SCHEDULE_STATUS_COMPLETED,
    SCHEDULE_STATUS_CONFIRMED,
    SCHEDULE_STATUS_PROPOSED,
    SCHEDULE_STATUS_RESCHEDULE_REQUESTED,
)
from utils.audit import create_audit_log
from utils.public_app_url import get_frontend_base_url

logger = logging.getLogger(__name__)

TERMINAL_WO_STATUSES = frozenset({"CANCELLED", "COMPLETED", "CLOSED", "VERIFIED"})


def _disallow_past_schedules() -> bool:
    return os.getenv("WORK_ORDER_SCHEDULE_DISALLOW_PAST", "true").strip().lower() in ("1", "true", "yes")


def _completion_requires_confirmed_schedule() -> bool:
    return os.getenv("WORK_ORDER_COMPLETION_REQUIRES_CONFIRMED_SCHEDULE", "").strip().lower() in ("1", "true", "yes")


def normalize_scheduled_instant(scheduled_at_raw: str, timezone_name: str) -> Tuple[str, str]:
    """
    Parse wall/ISO input and timezone name; return (utc_iso_string, canonical_timezone_name).
    Naive datetimes are interpreted in timezone_name.
    """
    tz_name = (timezone_name or "").strip()
    if not tz_name:
        raise ValueError("timezone is required (e.g. Europe/London)")
    try:
        zi = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as e:
        raise ValueError(f"Unknown timezone: {timezone_name}") from e
    s = (scheduled_at_raw or "").strip()
    if not s:
        raise ValueError("scheduled_at is required")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("scheduled_at must be a valid ISO-8601 datetime") from e
    if dt.tzinfo is None:
        dt_utc = dt.replace(tzinfo=zi).astimezone(timezone.utc)
    else:
        dt_utc = dt.astimezone(timezone.utc)
    if _disallow_past_schedules() and dt_utc < datetime.now(timezone.utc):
        raise ValueError("scheduled_at must be in the future")
    return dt_utc.replace(microsecond=0).isoformat(), tz_name


def _parse_wo_scheduled_dt(wo: Dict[str, Any]) -> Optional[datetime]:
    raw = wo.get("scheduled_at")
    if not raw or not str(raw).strip():
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _ics_escape(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _fold_ics_line(line: str, max_len: int = 75) -> str:
    if len(line) <= max_len:
        return line
    parts: List[str] = []
    cur = line
    while len(cur) > max_len:
        parts.append(cur[:max_len])
        cur = " " + cur[max_len:]
    if cur:
        parts.append(cur)
    return "\r\n ".join(parts)


def build_work_order_ics_bytes(
    work_order: Dict[str, Any],
    *,
    property_label: str,
    dt_start_utc: datetime,
    duration_minutes: int = 60,
) -> bytes:
    """Minimal VEVENT (UTC) for professional calendar import."""
    uid = f"wo-{work_order.get('work_order_id', 'unknown')}-{uuid.uuid4().hex[:8]}@pleerity-work-order"
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    start = dt_start_utc.strftime("%Y%m%dT%H%M%SZ")
    end = (dt_start_utc + timedelta(minutes=duration_minutes)).strftime("%Y%m%dT%H%M%SZ")
    title = (work_order.get("description") or "Work order visit").strip()[:200]
    kind = (work_order.get("work_order_kind") or "MAINTENANCE").strip().upper()
    summary = f"{kind} — {_ics_escape(title)}"
    loc = _ics_escape((property_label or "").strip()[:500])
    desc_parts = [
        f"Work order: {work_order.get('work_order_id', '')}",
        f"Status: {work_order.get('status', '')}",
    ]
    if work_order.get("requirement_code"):
        desc_parts.append(f"Requirement: {work_order.get('requirement_code')}")
    description = _ics_escape("\n".join(desc_parts))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Pleerity//Work Order Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start}",
        f"DTEND:{end}",
        _fold_ics_line(f"SUMMARY:{summary}"),
        _fold_ics_line(f"LOCATION:{loc}"),
        _fold_ics_line(f"DESCRIPTION:{description}"),
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


async def _load_property_label(db, client_id: str, property_id: Optional[str]) -> str:
    if not property_id or not client_id:
        return ""
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1, "nickname": 1},
    )
    if not prop:
        return property_id
    nick = (prop.get("nickname") or "").strip()
    if nick:
        return nick
    return ", ".join(p for p in [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")] if p) or property_id


async def _audit_schedule(
    *,
    action: AuditAction,
    event_type: str,
    work_order_id: str,
    client_id: Optional[str],
    actor_id: Optional[str],
    actor_role: Optional[str],
    metadata: Dict[str, Any],
) -> None:
    meta = {
        "event_type": event_type,
        "work_order_id": work_order_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }
    try:
        await create_audit_log(
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            client_id=client_id,
            resource_type="work_order",
            resource_id=work_order_id,
            metadata=meta,
        )
    except Exception as e:
        logger.warning("Schedule audit log failed: %s", e)


async def _client_primary_email(db, client_id: str) -> Optional[str]:
    c = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "contact_email": 1})
    if not c:
        return None
    return (c.get("contact_email") or c.get("email") or "").strip() or None


async def _contractor_email(db, contractor_id: str) -> Optional[str]:
    c = await db.contractors.find_one({"contractor_id": contractor_id}, {"_id": 0, "email": 1})
    if not c:
        return None
    return (c.get("email") or "").strip() or None


async def _send_schedule_emails(
    *,
    template_key: str,
    client_id: Optional[str],
    recipients: List[str],
    subject: str,
    html: str,
    idempotency_prefix: str,
    event_type: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> None:
    from services.notification_orchestrator import notification_orchestrator

    for i, to in enumerate(recipients):
        if not to:
            continue
        ctx: Dict[str, Any] = {
            "recipient": to,
            "subject": subject,
            "message": html,
            "company_name": "Pleerity Enterprise Ltd",
        }
        if attachments:
            ctx["attachments"] = attachments
        try:
            await notification_orchestrator.send(
                template_key=template_key,
                client_id=client_id,
                context=ctx,
                idempotency_key=f"{idempotency_prefix}_{to}_{i}",
                event_type=event_type,
            )
        except Exception as e:
            logger.warning("Schedule notification send failed (%s): %s", to, e)


def _schedule_summary_html(wo: Dict[str, Any], prop_label: str) -> str:
    wid = wo.get("work_order_id", "")
    when = wo.get("scheduled_at", "")
    tz = wo.get("scheduled_timezone", "")
    st = wo.get("schedule_status", "")
    base = get_frontend_base_url().rstrip("/")
    return (
        f"<p><strong>Work order</strong> {wid}</p>"
        f"<p><strong>Property</strong> {prop_label or '—'}</p>"
        f"<p><strong>Visit</strong> {when} ({tz})</p>"
        f"<p><strong>Schedule state</strong> {st}</p>"
        f'<p><a href="{base}/operations/work-orders">Open work orders</a></p>'
    )


def _can_confirm(actor_type: str, scheduled_by: Optional[str]) -> bool:
    if actor_type == SCHEDULE_ACTOR_ADMIN:
        return True
    sb = (scheduled_by or "").strip().lower()
    if sb == SCHEDULE_ACTOR_CLIENT and actor_type == SCHEDULE_ACTOR_CONTRACTOR:
        return True
    if sb == SCHEDULE_ACTOR_CONTRACTOR and actor_type == SCHEDULE_ACTOR_CLIENT:
        return True
    if sb == SCHEDULE_ACTOR_ADMIN and actor_type in (SCHEDULE_ACTOR_CLIENT, SCHEDULE_ACTOR_CONTRACTOR):
        return True
    return False


def _assert_wo_schedulable(wo: Dict[str, Any]) -> None:
    st = (wo.get("status") or "").strip().upper()
    if st in TERMINAL_WO_STATUSES:
        raise ValueError("Cannot change schedule for a closed or completed work order")


async def _require_work_order_for_actor(
    work_order_id: str,
    *,
    client_id: Optional[str] = None,
    contractor_id: Optional[str] = None,
    admin: bool = False,
) -> Dict[str, Any]:
    db = database.get_db()
    wo = await db.work_orders.find_one({"work_order_id": work_order_id})
    if not wo:
        raise LookupError("Work order not found")
    if admin:
        wo.pop("_id", None)
        return wo
    if client_id and (wo.get("client_id") or "").strip() != str(client_id).strip():
        raise PermissionError("Work order not found for this organisation")
    if contractor_id and (wo.get("contractor_id") or "").strip() != str(contractor_id).strip():
        raise PermissionError("Work order not found or not assigned to you")
    if contractor_id and not client_id:
        pass
    elif client_id and not contractor_id:
        pass
    wo.pop("_id", None)
    return wo


async def propose_schedule(
    work_order_id: str,
    *,
    actor_type: str,
    actor_id: Optional[str],
    actor_role: Optional[str],
    scheduled_at_raw: str,
    timezone_name: str,
    notes: Optional[str],
    client_id: Optional[str] = None,
    contractor_id: Optional[str] = None,
    admin: bool = False,
) -> Dict[str, Any]:
    if actor_type not in (SCHEDULE_ACTOR_CLIENT, SCHEDULE_ACTOR_CONTRACTOR, SCHEDULE_ACTOR_ADMIN):
        raise ValueError("Invalid actor for schedule proposal")
    wo = await _require_work_order_for_actor(
        work_order_id, client_id=client_id, contractor_id=contractor_id, admin=admin
    )
    _assert_wo_schedulable(wo)
    if not admin and actor_type != SCHEDULE_ACTOR_ADMIN and not (wo.get("contractor_id") or "").strip():
        raise ValueError("Assign a contractor before proposing a visit time")
    utc_iso, tz_canon = normalize_scheduled_instant(scheduled_at_raw, timezone_name)
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    cid = (wo.get("client_id") or "").strip()
    kind = ((wo.get("work_order_kind") or "").strip().upper()) or "MAINTENANCE"
    set_doc: Dict[str, Any] = {
        "scheduled_at": utc_iso,
        "scheduled_timezone": tz_canon,
        "schedule_status": SCHEDULE_STATUS_PROPOSED,
        "scheduled_by": actor_type,
        "schedule_notes": (notes or "").strip() or None,
        "last_schedule_update_at": now,
        "reminder_sent": False,
        "updated_at": now,
    }
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        set_doc["compliance_booking_status"] = COMPLIANCE_BOOKING_SCHEDULED
    res = await db.work_orders.find_one_and_update(
        {"work_order_id": work_order_id},
        {"$set": set_doc},
        return_document=True,
    )
    if not res:
        raise LookupError("Work order not found")
    res.pop("_id", None)
    prop_label = await _load_property_label(db, cid, wo.get("property_id"))
    await _audit_schedule(
        action=AuditAction.WORK_ORDER_SCHEDULE_PROPOSED,
        event_type=AUDIT_EVENT_SCHEDULE_PROPOSED,
        work_order_id=work_order_id,
        client_id=cid or None,
        actor_id=actor_id,
        actor_role=actor_role,
        metadata={
            "scheduled_at": utc_iso,
            "timezone": tz_canon,
            "notes": (notes or "").strip() or None,
            "scheduled_by": actor_type,
        },
    )
    # Notifications: other party (admin proposes → both)
    client_em = await _client_primary_email(db, cid) if cid else None
    contr_em = await _contractor_email(db, str(wo.get("contractor_id") or "")) if wo.get("contractor_id") else None
    subj = f"Visit time proposed — work order {work_order_id}"
    body = _schedule_summary_html({**wo, **set_doc}, prop_label)
    if actor_type == SCHEDULE_ACTOR_CLIENT:
        if contr_em:
            await _send_schedule_emails(
                template_key="ADMIN_MANUAL",
                client_id=None,
                recipients=[contr_em],
                subject=subj,
                html=body,
                idempotency_prefix=f"sch_prop_c_{work_order_id}",
                event_type=AUDIT_EVENT_SCHEDULE_PROPOSED,
            )
    elif actor_type == SCHEDULE_ACTOR_CONTRACTOR:
        if client_em:
            await _send_schedule_emails(
                template_key="ADMIN_MANUAL",
                client_id=cid,
                recipients=[client_em],
                subject=subj,
                html=body,
                idempotency_prefix=f"sch_prop_co_{work_order_id}",
                event_type=AUDIT_EVENT_SCHEDULE_PROPOSED,
            )
    else:
        rec = [e for e in [client_em, contr_em] if e]
        if rec:
            await _send_schedule_emails(
                template_key="ADMIN_MANUAL",
                client_id=cid,
                recipients=rec,
                subject=subj,
                html=body,
                idempotency_prefix=f"sch_prop_a_{work_order_id}",
                event_type=AUDIT_EVENT_SCHEDULE_PROPOSED,
            )
    return res


async def confirm_schedule(
    work_order_id: str,
    *,
    actor_type: str,
    actor_id: Optional[str],
    actor_role: Optional[str],
    client_id: Optional[str] = None,
    contractor_id: Optional[str] = None,
    admin: bool = False,
) -> Dict[str, Any]:
    wo = await _require_work_order_for_actor(
        work_order_id, client_id=client_id, contractor_id=contractor_id, admin=admin
    )
    _assert_wo_schedulable(wo)
    cur = (wo.get("schedule_status") or "").strip().lower()
    if cur != SCHEDULE_STATUS_PROPOSED:
        raise ValueError("Visit can only be confirmed when a time has been proposed")
    if not (wo.get("scheduled_at") or "").strip():
        raise ValueError("No proposed visit time to confirm")
    if not _can_confirm(actor_type, wo.get("scheduled_by")):
        raise ValueError("You are not allowed to confirm this proposal (wrong party)")
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    set_doc = {
        "schedule_status": SCHEDULE_STATUS_CONFIRMED,
        "last_schedule_update_at": now,
        "reminder_sent": False,
        "updated_at": now,
    }
    res = await db.work_orders.find_one_and_update(
        {"work_order_id": work_order_id},
        {"$set": set_doc},
        return_document=True,
    )
    if not res:
        raise LookupError("Work order not found")
    res.pop("_id", None)
    cid = (wo.get("client_id") or "").strip()
    prop_label = await _load_property_label(db, cid, wo.get("property_id"))
    merged = {**wo, **res}
    dt = _parse_wo_scheduled_dt(merged)
    ics_bytes = b""
    if dt:
        ics_bytes = build_work_order_ics_bytes(merged, property_label=prop_label, dt_start_utc=dt)
    attachments = None
    if ics_bytes:
        attachments = [
            {
                "Name": f"work-order-{work_order_id}-visit.ics",
                "Content": base64.b64encode(ics_bytes).decode("ascii"),
                "ContentType": "text/calendar; charset=utf-8",
            }
        ]
    await _audit_schedule(
        action=AuditAction.WORK_ORDER_SCHEDULE_CONFIRMED,
        event_type=AUDIT_EVENT_SCHEDULE_CONFIRMED,
        work_order_id=work_order_id,
        client_id=cid or None,
        actor_id=actor_id,
        actor_role=actor_role,
        metadata={
            "scheduled_at": merged.get("scheduled_at"),
            "timezone": merged.get("scheduled_timezone"),
            "notes": merged.get("schedule_notes"),
        },
    )
    client_em = await _client_primary_email(db, cid) if cid else None
    contr_em = await _contractor_email(db, str(wo.get("contractor_id") or "")) if wo.get("contractor_id") else None
    subj = f"Visit confirmed — work order {work_order_id}"
    body = (
        _schedule_summary_html(merged, prop_label)
        + "<p>A calendar file (.ics) is attached. You can also download it again from your client or contractor portal "
        "(Work orders → visit details).</p>"
    )
    rec = [e for e in [client_em, contr_em] if e]
    if rec:
        await _send_schedule_emails(
            template_key="ADMIN_MANUAL",
            client_id=cid,
            recipients=rec,
            subject=subj,
            html=body,
            idempotency_prefix=f"sch_conf_{work_order_id}",
            event_type=AUDIT_EVENT_SCHEDULE_CONFIRMED,
            attachments=attachments,
        )
    return res


async def request_reschedule(
    work_order_id: str,
    *,
    actor_type: str,
    actor_id: Optional[str],
    actor_role: Optional[str],
    reason: Optional[str],
    client_id: Optional[str] = None,
    contractor_id: Optional[str] = None,
    admin: bool = False,
) -> Dict[str, Any]:
    wo = await _require_work_order_for_actor(
        work_order_id, client_id=client_id, contractor_id=contractor_id, admin=admin
    )
    _assert_wo_schedulable(wo)
    if not (wo.get("scheduled_at") or "").strip():
        raise ValueError("There is no visit scheduled to reschedule")
    cur = (wo.get("schedule_status") or "").strip().lower()
    if cur in (SCHEDULE_STATUS_CANCELLED, SCHEDULE_STATUS_COMPLETED):
        raise ValueError("Cannot request reschedule for this schedule state")
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    set_doc = {
        "schedule_status": SCHEDULE_STATUS_RESCHEDULE_REQUESTED,
        "last_schedule_update_at": now,
        "reminder_sent": False,
        "updated_at": now,
        "schedule_reschedule_reason": (reason or "").strip()[:2000] or None,
    }
    res = await db.work_orders.find_one_and_update(
        {"work_order_id": work_order_id},
        {"$set": set_doc},
        return_document=True,
    )
    if not res:
        raise LookupError("Work order not found")
    res.pop("_id", None)
    cid = (wo.get("client_id") or "").strip()
    await _audit_schedule(
        action=AuditAction.WORK_ORDER_SCHEDULE_RESCHEDULE_REQUESTED,
        event_type=AUDIT_EVENT_SCHEDULE_RESCHEDULE_REQUESTED,
        work_order_id=work_order_id,
        client_id=cid or None,
        actor_id=actor_id,
        actor_role=actor_role,
        metadata={
            "scheduled_at": wo.get("scheduled_at"),
            "timezone": wo.get("scheduled_timezone"),
            "notes": reason,
        },
    )
    prop_label = await _load_property_label(db, cid, wo.get("property_id"))
    merged = {**wo, **res}
    subj = f"Reschedule requested — work order {work_order_id}"
    body = _schedule_summary_html(merged, prop_label) + f"<p><strong>Reason:</strong> {(reason or '').strip() or '—'}</p>"
    client_em = await _client_primary_email(db, cid) if cid else None
    contr_em = await _contractor_email(db, str(wo.get("contractor_id") or "")) if wo.get("contractor_id") else None
    if actor_type == SCHEDULE_ACTOR_CLIENT and contr_em:
        await _send_schedule_emails(
            template_key="ADMIN_MANUAL",
            client_id=None,
            recipients=[contr_em],
            subject=subj,
            html=body,
            idempotency_prefix=f"sch_rs_c_{work_order_id}",
            event_type=AUDIT_EVENT_SCHEDULE_RESCHEDULE_REQUESTED,
        )
    elif actor_type == SCHEDULE_ACTOR_CONTRACTOR and client_em:
        await _send_schedule_emails(
            template_key="ADMIN_MANUAL",
            client_id=cid,
            recipients=[client_em],
            subject=subj,
            html=body,
            idempotency_prefix=f"sch_rs_co_{work_order_id}",
            event_type=AUDIT_EVENT_SCHEDULE_RESCHEDULE_REQUESTED,
        )
    elif actor_type in (SCHEDULE_ACTOR_ADMIN,):
        rec = [e for e in [client_em, contr_em] if e]
        if rec:
            await _send_schedule_emails(
                template_key="ADMIN_MANUAL",
                client_id=cid,
                recipients=rec,
                subject=subj,
                html=body,
                idempotency_prefix=f"sch_rs_a_{work_order_id}",
                event_type=AUDIT_EVENT_SCHEDULE_RESCHEDULE_REQUESTED,
            )
    return res


async def cancel_schedule(
    work_order_id: str,
    *,
    actor_type: str,
    actor_id: Optional[str],
    actor_role: Optional[str],
    client_id: Optional[str] = None,
    contractor_id: Optional[str] = None,
    admin: bool = False,
) -> Dict[str, Any]:
    wo = await _require_work_order_for_actor(
        work_order_id, client_id=client_id, contractor_id=contractor_id, admin=admin
    )
    _assert_wo_schedulable(wo)
    if not (wo.get("scheduled_at") or "").strip() and not (wo.get("schedule_status") or "").strip():
        raise ValueError("There is no schedule to cancel")
    cur = (wo.get("schedule_status") or "").strip().lower()
    if cur == SCHEDULE_STATUS_CANCELLED:
        raise ValueError("Visit is already cancelled")
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    # Clear visit fields so the job summary does not imply an active visit; work order status is unchanged (not job cancel).
    set_doc = {
        "schedule_status": SCHEDULE_STATUS_CANCELLED,
        "scheduled_at": None,
        "scheduled_timezone": None,
        "schedule_notes": None,
        "last_schedule_update_at": now,
        "reminder_sent": False,
        "updated_at": now,
    }
    res = await db.work_orders.find_one_and_update(
        {"work_order_id": work_order_id},
        {"$set": set_doc},
        return_document=True,
    )
    if not res:
        raise LookupError("Work order not found")
    res.pop("_id", None)
    cid = (wo.get("client_id") or "").strip()
    await _audit_schedule(
        action=AuditAction.WORK_ORDER_SCHEDULE_CANCELLED,
        event_type=AUDIT_EVENT_SCHEDULE_CANCELLED,
        work_order_id=work_order_id,
        client_id=cid or None,
        actor_id=actor_id,
        actor_role=actor_role,
        metadata={
            "scheduled_at": wo.get("scheduled_at"),
            "timezone": wo.get("scheduled_timezone"),
            "notes": wo.get("schedule_notes"),
        },
    )
    prop_label = await _load_property_label(db, cid, wo.get("property_id"))
    merged = {**wo, **res}
    subj = f"Visit cancelled — work order {work_order_id}"
    body = _schedule_summary_html(merged, prop_label)
    client_em = await _client_primary_email(db, cid) if cid else None
    contr_em = await _contractor_email(db, str(wo.get("contractor_id") or "")) if wo.get("contractor_id") else None
    rec = [e for e in [client_em, contr_em] if e]
    if rec:
        await _send_schedule_emails(
            template_key="ADMIN_MANUAL",
            client_id=cid,
            recipients=rec,
            subject=subj,
            html=body,
            idempotency_prefix=f"sch_can_{work_order_id}",
            event_type=AUDIT_EVENT_SCHEDULE_CANCELLED,
        )
    return res


async def get_schedule_ics_payload(work_order_id: str, *, client_id: Optional[str] = None, contractor_id: Optional[str] = None, admin: bool = False) -> Tuple[bytes, str]:
    wo = await _require_work_order_for_actor(
        work_order_id, client_id=client_id, contractor_id=contractor_id, admin=admin
    )
    dt = _parse_wo_scheduled_dt(wo)
    if not dt:
        raise ValueError("No visit datetime on file for this work order")
    db = database.get_db()
    cid = (wo.get("client_id") or "").strip()
    prop_label = await _load_property_label(db, cid, wo.get("property_id"))
    ics = build_work_order_ics_bytes(wo, property_label=prop_label, dt_start_utc=dt)
    filename = f"work-order-{work_order_id}-visit.ics"
    return ics, filename


async def run_schedule_reminders_job() -> Dict[str, Any]:
    """Send one reminder email to client + contractor for confirmed visits in the next 24h."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=24)
    q = {
        "schedule_status": SCHEDULE_STATUS_CONFIRMED,
        "$or": [{"reminder_sent": False}, {"reminder_sent": {"$exists": False}}],
        "scheduled_at": {"$exists": True, "$nin": [None, ""]},
        "contractor_id": {"$exists": True, "$nin": [None, ""]},
    }
    sent = 0
    cursor = db.work_orders.find(q)
    async for raw in cursor:
        wo = dict(raw)
        st = (wo.get("status") or "").strip().upper()
        if st in TERMINAL_WO_STATUSES:
            continue
        dt = _parse_wo_scheduled_dt(wo)
        if not dt or not (now <= dt <= window_end):
            continue
        wid = wo.get("work_order_id")
        cid = (wo.get("client_id") or "").strip()
        prop_label = await _load_property_label(db, cid, wo.get("property_id"))
        subj = f"Reminder: visit tomorrow or soon — work order {wid}"
        body = _schedule_summary_html(wo, prop_label)
        client_em = await _client_primary_email(db, cid) if cid else None
        contr_em = await _contractor_email(db, str(wo.get("contractor_id") or "")) if wo.get("contractor_id") else None
        rec = [e for e in [client_em, contr_em] if e]
        if rec:
            await _send_schedule_emails(
                template_key="ADMIN_MANUAL",
                client_id=cid,
                recipients=rec,
                subject=subj,
                html=body,
                idempotency_prefix=f"sch_rem_{wid}",
                event_type=AUDIT_EVENT_SCHEDULE_REMINDER,
            )
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.work_orders.update_one(
            {"work_order_id": wid},
            {"$set": {"reminder_sent": True, "last_schedule_update_at": now_iso, "updated_at": now_iso}},
        )
        await _audit_schedule(
            action=AuditAction.WORK_ORDER_SCHEDULE_REMINDER_SENT,
            event_type=AUDIT_EVENT_SCHEDULE_REMINDER,
            work_order_id=str(wid),
            client_id=cid or None,
            actor_id="system",
            actor_role="job",
            metadata={"scheduled_at": wo.get("scheduled_at"), "timezone": wo.get("scheduled_timezone")},
        )
        sent += 1
    return {"message": f"Schedule reminders processed: {sent}", "count": sent}


def assert_completion_schedule_policy(wo: Dict[str, Any]) -> None:
    if not _completion_requires_confirmed_schedule():
        return
    if (wo.get("schedule_status") or "").strip().lower() != SCHEDULE_STATUS_CONFIRMED:
        raise ValueError("Work order cannot be completed without a confirmed visit schedule")
    if not (wo.get("scheduled_at") or "").strip():
        raise ValueError("Work order cannot be completed without a scheduled visit time")
