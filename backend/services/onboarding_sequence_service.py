"""
Landlord 7-day onboarding email sequence: queue-based scheduling and processing.
Triggered when client is provisioned (WELCOME_EMAIL_SENT). Behaviour-aware: stops when monitoring enabled.
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from database import database

from services.email_event_registry import LANDLORD_ONBOARDING_EVENT_IDS, get_template_key_for_event
from services.onboarding_state_checker import check_onboarding_state

logger = logging.getLogger(__name__)

COLLECTION = "onboarding_email_queue"
STATUS_PENDING = "PENDING"
STATUS_SENT = "SENT"
STATUS_CANCELLED = "CANCELLED"

# Day 0 = immediate, Day 1 = +24h, ... Day 7 = +168h
OFFSET_HOURS = (0, 24, 48, 72, 96, 120, 144, 168)


async def schedule_onboarding_sequence(client_id: str) -> int:
    """
    Enqueue 8 onboarding email items for the client (Day 0 .. Day 7).
    Call when user_onboarding_started (e.g. after WELCOME_EMAIL_SENT in provisioning).
    Returns number of items enqueued (0 if already scheduled or client_id missing).
    """
    if not client_id or not LANDLORD_ONBOARDING_EVENT_IDS:
        return 0
    db = database.get_db()
    now = datetime.now(timezone.utc)
    existing = await db[COLLECTION].find_one({"client_id": client_id}, {"_id": 1})
    if existing:
        logger.info("Onboarding sequence already scheduled for client_id=%s", client_id)
        return 0
    to_insert = []
    for i, event_id in enumerate(LANDLORD_ONBOARDING_EVENT_IDS):
        send_at = now + timedelta(hours=OFFSET_HOURS[i])
        to_insert.append({
            "client_id": client_id,
            "event_id": event_id,
            "send_at": send_at,  # datetime (BSON); processor compares with datetime.now(utc)
            "status": STATUS_PENDING,
            "created_at": now.isoformat(),
        })
    try:
        await db[COLLECTION].insert_many(to_insert, ordered=False)
        logger.info("Onboarding sequence scheduled for client_id=%s (%s items)", client_id, len(to_insert))
        return len(to_insert)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            return 0
        raise


async def cancel_remaining_onboarding_emails(client_id: str) -> int:
    """
    Cancel all PENDING onboarding queue items for this client.
    Call when monitoring is enabled or user opts out of onboarding emails.
    Returns count of cancelled items.
    """
    if not client_id:
        return 0
    db = database.get_db()
    result = await db[COLLECTION].update_many(
        {"client_id": client_id, "status": STATUS_PENDING},
        {"$set": {"status": STATUS_CANCELLED, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.modified_count:
        logger.info("Cancelled %s onboarding email(s) for client_id=%s", result.modified_count, client_id)
    return result.modified_count or 0


async def process_onboarding_email_queue() -> dict:
    """
    Process due onboarding queue items: for each PENDING with send_at <= now,
    check onboarding state (cancel rest if monitoring_enabled), respect preferences, send via orchestrator.
    Returns {"sent": n, "cancelled": m, "skipped": k}.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    cursor = db[COLLECTION].find(
        {"status": STATUS_PENDING, "send_at": {"$lte": now}},
        {"_id": 1, "client_id": 1, "event_id": 1},
    ).sort("send_at", 1).limit(50)
    items = await cursor.to_list(50)
    sent = 0
    cancelled = 0
    skipped = 0
    for item in items:
        client_id = item.get("client_id")
        event_id = item.get("event_id")
        if not client_id or not event_id:
            skipped += 1
            continue
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "client_id": 1, "email": 1, "contact_email": 1, "full_name": 1, "customer_reference": 1},
        )
        if not client:
            await db[COLLECTION].update_one(
                {"_id": item["_id"]},
                {"$set": {"status": STATUS_CANCELLED, "updated_at": now_iso}},
            )
            cancelled += 1
            continue
        state = await check_onboarding_state(client_id)
        if state.get("monitoring_enabled"):
            await cancel_remaining_onboarding_emails(client_id)
            cancelled += 1
            continue
        template_key = get_template_key_for_event(event_id)
        if not template_key:
            skipped += 1
            continue
        recipient = (client.get("contact_email") or client.get("email") or "").strip()
        if not recipient:
            skipped += 1
            continue
        portal_base = (os.getenv("FRONTEND_URL") or os.getenv("PORTAL_BASE_URL") or "").strip().rstrip("/")
        context = {
            "client_name": client.get("full_name") or "there",
            "portal_base_url": portal_base,
            "portal_link": (portal_base + "/dashboard") if portal_base else "#",
            "customer_reference": client.get("customer_reference"),
        }
        idempotency_key = f"ONBOARDING_{event_id}_{client_id}"
        try:
            from services.notification_orchestrator import notification_orchestrator
            result = await notification_orchestrator.send(
                template_key=template_key,
                client_id=client_id,
                context={**context, "recipient": recipient, "subject": _subject_for_event(event_id)},
                idempotency_key=idempotency_key,
                event_type=f"onboarding_{event_id.lower()}",
            )
            if result.outcome in ("sent", "duplicate_ignored"):
                await db[COLLECTION].update_one(
                    {"_id": item["_id"]},
                    {"$set": {"status": STATUS_SENT, "updated_at": now_iso}},
                )
                sent += 1
            else:
                skipped += 1
        except Exception as e:
            logger.warning("Onboarding email send failed client_id=%s event_id=%s: %s", client_id, event_id, e)
            skipped += 1
    return {"sent": sent, "cancelled": cancelled, "skipped": skipped}


def _subject_for_event(event_id: str) -> str:
    """Default subject line per onboarding event."""
    subjects = {
        "ONBOARDING_DAY0_WELCOME": "Welcome to Compliance Vault Pro",
        "ONBOARDING_DAY1_SETUP_REMINDER": "Complete your setup",
        "ONBOARDING_DAY2_COMPLIANCE_EDUCATION": "Track your compliance requirements",
        "ONBOARDING_DAY3_PRODUCT_VALUE": "Your compliance dashboard",
        "ONBOARDING_DAY4_DOCUMENT_PACK_INTRO": "Landlord document packs",
        "ONBOARDING_DAY5_RISK_AWARENESS": "Why compliance alerts matter",
        "ONBOARDING_DAY6_CASE_EXAMPLE": "How we helped one landlord",
        "ONBOARDING_DAY7_ACTIVATION_PUSH": "Activate monitoring",
    }
    return subjects.get(event_id, "Compliance Vault Pro")
