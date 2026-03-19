"""
Compliance Vault Pro subscription onboarding email lifecycle.

Order: payment confirmation → activation (set password) → dashboard-ready + 7-day sequence.
Dashboard-ready sends only after password is set (auth.set_password). Activation reminders
if password still unset after configurable delays.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from database import database
from models import UserRole, PasswordStatus, AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def send_dashboard_ready_and_start_sequence(client_id: Optional[str]) -> None:
    """
    Idempotent: send DASHBOARD_READY email once, then enqueue landlord onboarding sequence.
    Called from auth after successful password set (client admin only).
    """
    if not client_id or client_id == "ADMIN_INVITE":
        return
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "onboarding_dashboard_ready_email_sent_at": 1, "email": 1, "contact_email": 1, "full_name": 1, "contact_name": 1, "customer_reference": 1},
    )
    if not client:
        return
    if client.get("onboarding_dashboard_ready_email_sent_at"):
        return

    from utils.app_urls import get_app_base_url
    from services.notification_orchestrator import notification_orchestrator

    display_name = (client.get("contact_name") or client.get("full_name") or "").strip() or "there"
    recipient = (client.get("contact_email") or client.get("email") or "").strip()
    if not recipient:
        logger.warning("dashboard_ready_email skipped: no recipient client_id=%s", client_id)
        return

    portal_base = get_app_base_url(for_email_links=True).strip().rstrip("/")
    portal_link = f"{portal_base}/app/dashboard" if portal_base else "#"
    crn = (client.get("customer_reference") or "").strip()

    result = await notification_orchestrator.send(
        template_key="DASHBOARD_READY",
        client_id=client_id,
        context={
            "recipient": recipient,
            "client_name": display_name,
            "customer_reference": crn,
            "portal_link": portal_link,
            "portal_base_url": portal_base,
            "dashboard_milestone_email": True,
            "subject": "Your Compliance Vault Pro dashboard is ready",
        },
        idempotency_key=f"DASHBOARD_READY_{client_id}",
        event_type="onboarding_dashboard_ready",
    )
    if result.outcome not in ("sent", "duplicate_ignored"):
        logger.warning(
            "dashboard_ready_email failed client_id=%s outcome=%s",
            client_id,
            getattr(result, "outcome", None),
        )
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.clients.update_one(
        {"client_id": client_id},
        {"$set": {"onboarding_dashboard_ready_email_sent_at": now_iso}},
    )
    await create_audit_log(
        action=AuditAction.ONBOARDING_DASHBOARD_READY_EMAIL_SENT,
        client_id=client_id,
        metadata={"template_key": "DASHBOARD_READY", "message_id": getattr(result, "message_id", None)},
    )

    try:
        from services.onboarding_sequence_service import schedule_onboarding_sequence

        enqueued = await schedule_onboarding_sequence(client_id)
        if enqueued:
            logger.info("Onboarding sequence enqueued after password set client_id=%s count=%s", client_id, enqueued)
    except Exception as e:
        logger.warning("schedule_onboarding_sequence failed client_id=%s: %s", client_id, e)


async def process_activation_reminders() -> Dict[str, int]:
    """
    Send activation reminders for client admins who received activation email but never set password.
    First reminder after ACTIVATION_REMINDER_HOURS_FIRST (default 24h), final after ACTIVATION_REMINDER_HOURS_FINAL (default 72h from activation send).
    """
    db = database.get_db()
    hours_first = int(os.getenv("ACTIVATION_REMINDER_HOURS_FIRST", "24") or "24")
    hours_final = int(os.getenv("ACTIVATION_REMINDER_HOURS_FINAL", "72") or "72")
    now = datetime.now(timezone.utc)
    sent_first = 0
    sent_final = 0

    cursor = db.clients.find(
        {
            "activation_email_sent_at": {"$exists": True, "$ne": None},
            "onboarding_dashboard_ready_email_sent_at": {"$exists": False},
            "onboarding_status": {"$ne": "FAILED"},
        },
        {
            "_id": 0,
            "client_id": 1,
            "activation_email_sent_at": 1,
            "onboarding_activation_reminder_sent_at": 1,
            "onboarding_activation_reminder_final_sent_at": 1,
            "email": 1,
            "full_name": 1,
            "contact_name": 1,
        },
    )
    clients = await cursor.to_list(200)
    for c in clients:
        cid = c.get("client_id")
        if not cid:
            continue
        act_at = _parse_dt(c.get("activation_email_sent_at"))
        if not act_at:
            continue
        pu = await db.portal_users.find_one(
            {"client_id": cid, "role": UserRole.ROLE_CLIENT_ADMIN.value},
            {"_id": 0, "portal_user_id": 1, "password_status": 1, "auth_email": 1},
        )
        if not pu or pu.get("password_status") == PasswordStatus.SET.value:
            continue

        email = (pu.get("auth_email") or c.get("email") or "").strip()
        if not email:
            continue
        name = (c.get("contact_name") or c.get("full_name") or "Valued Customer").strip()

        age = now - act_at
        rem1 = c.get("onboarding_activation_reminder_sent_at")
        rem2 = c.get("onboarding_activation_reminder_final_sent_at")

        from services.provisioning import provisioning_service

        if not rem1 and age >= timedelta(hours=hours_first):
            ok, st, err = await provisioning_service.send_activation_reminder_email(
                cid,
                pu["portal_user_id"],
                email,
                name,
                idempotency_key=f"ACTIVATION_REMINDER_FIRST_{cid}",
            )
            if ok:
                await db.clients.update_one(
                    {"client_id": cid},
                    {"$set": {"onboarding_activation_reminder_sent_at": now.isoformat()}},
                )
                await create_audit_log(
                    action=AuditAction.ONBOARDING_ACTIVATION_REMINDER_SENT,
                    client_id=cid,
                    metadata={"round": "first", "status": st},
                )
                sent_first += 1
            else:
                logger.warning("activation_reminder_first failed client_id=%s %s %s", cid, st, err)

        elif rem1 and not rem2 and age >= timedelta(hours=hours_final):
            ok, st, err = await provisioning_service.send_activation_reminder_email(
                cid,
                pu["portal_user_id"],
                email,
                name,
                idempotency_key=f"ACTIVATION_REMINDER_FINAL_{cid}",
            )
            if ok:
                await db.clients.update_one(
                    {"client_id": cid},
                    {"$set": {"onboarding_activation_reminder_final_sent_at": now.isoformat()}},
                )
                await create_audit_log(
                    action=AuditAction.ONBOARDING_ACTIVATION_REMINDER_SENT,
                    client_id=cid,
                    metadata={"round": "final", "status": st},
                )
                sent_final += 1
            else:
                logger.warning("activation_reminder_final failed client_id=%s %s %s", cid, st, err)

    return {"first": sent_first, "final": sent_final}
