"""Rent reminder tracking — idempotent keys; Phase 1 default is manual send."""
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pymongo.errors import DuplicateKeyError

from database import database
from models.rent_operations import RentLedgerStatus, RentReminderType, ReminderDeliveryStatus
from utils.audit import create_audit_log
from models import AuditAction, UserRole

logger = logging.getLogger(__name__)

COLLECTION = "rent_reminder_events"

DUE_SOON_DAYS = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def build_reminder_key(reminder_type: str, ledger_id: str, period_key: str) -> str:
    type_upper = reminder_type.upper().replace("-", "_")
    if type_upper == "DUE_SOON":
        prefix = "RENT_DUE_SOON"
    elif type_upper == "DUE_TODAY":
        prefix = "RENT_DUE_TODAY"
    elif type_upper == "OVERDUE_3D":
        prefix = "RENT_OVERDUE_3D"
    elif type_upper == "OVERDUE_7D":
        prefix = "RENT_OVERDUE_7D"
    elif type_upper == "OVERDUE_14D":
        prefix = "RENT_OVERDUE_14D"
    else:
        prefix = f"RENT_{type_upper}"
    return f"{prefix}_{ledger_id}_{period_key}"


def _live_send_enabled() -> bool:
    return os.environ.get("RENT_REMINDERS_LIVE_SEND", "").strip().lower() in ("1", "true", "yes", "on")


async def mark_reminder_sent(
    ledger_id: str,
    client_id: str,
    body: Dict[str, Any],
    actor_id: Optional[str] = None,
    actor_role: Optional[UserRole] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    ledger = await db.rent_ledger_periods.find_one(
        {"ledger_id": ledger_id, "client_id": client_id, "is_deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not ledger:
        raise ValueError("LEDGER_NOT_FOUND")

    reminder_type = body["reminder_type"]
    period_key = ledger.get("period_key") or ledger_id
    reminder_key = build_reminder_key(reminder_type, ledger_id, period_key)
    now = _now_iso()

    existing = await db[COLLECTION].find_one({"reminder_key": reminder_key}, {"_id": 0})
    if existing:
        return existing

    doc = {
        "reminder_key": reminder_key,
        "ledger_id": ledger_id,
        "client_id": client_id,
        "property_id": ledger["property_id"],
        "reminder_type": reminder_type,
        "channel": body.get("channel") or "manual",
        "sent_at": now,
        "marked_sent_by": actor_id,
        "message_preview": body.get("message_preview"),
        "delivery_status": ReminderDeliveryStatus.MANUAL.value,
        "created_at": now,
    }
    await db[COLLECTION].insert_one(doc)
    await create_audit_log(
        action=AuditAction.RENT_REMINDER_MARKED_SENT,
        actor_role=actor_role,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="rent_reminder_event",
        resource_id=reminder_key,
        metadata={"ledger_id": ledger_id, "reminder_type": reminder_type},
    )
    return {k: v for k, v in doc.items() if k != "_id"}


def _reminder_types_for_ledger(ledger: Dict[str, Any], today: date) -> List[str]:
    due = _parse_date(ledger["due_date"])
    status = ledger.get("status")
    days_overdue = int(ledger.get("days_overdue") or 0)
    outstanding = int(ledger.get("outstanding_balance_minor") or 0)
    if outstanding <= 0 or status in (RentLedgerStatus.PAID.value, RentLedgerStatus.WAIVED.value):
        return []

    types: List[str] = []
    if due - today == timedelta(days=DUE_SOON_DAYS):
        types.append(RentReminderType.DUE_SOON.value)
    if due == today:
        types.append(RentReminderType.DUE_TODAY.value)
    if days_overdue >= 3:
        types.append(RentReminderType.OVERDUE_3D.value)
    if days_overdue >= 7:
        types.append(RentReminderType.OVERDUE_7D.value)
    if days_overdue >= 14:
        types.append(RentReminderType.OVERDUE_14D.value)
    return types


async def process_reminders_for_client(client_id: str) -> Dict[str, Any]:
    """Create missing reminder events for client ledgers. Live send only if flag enabled."""
    db = database.get_db()
    today = datetime.now(timezone.utc).date()
    ledgers = await db.rent_ledger_periods.find(
        {
            "client_id": client_id,
            "is_deleted": {"$ne": True},
            "outstanding_balance_minor": {"$gt": 0},
        },
        {"_id": 0},
    ).to_list(2000)

    created = 0
    skipped = 0
    for ledger in ledgers:
        period_key = ledger.get("period_key") or ledger["ledger_id"]
        for rtype in _reminder_types_for_ledger(ledger, today):
            key = build_reminder_key(rtype, ledger["ledger_id"], period_key)
            existing = await db[COLLECTION].find_one({"reminder_key": key}, {"_id": 1})
            if existing:
                skipped += 1
                continue
            delivery = ReminderDeliveryStatus.PENDING.value if _live_send_enabled() else ReminderDeliveryStatus.MANUAL.value
            doc = {
                "reminder_key": key,
                "ledger_id": ledger["ledger_id"],
                "client_id": client_id,
                "property_id": ledger["property_id"],
                "reminder_type": rtype,
                "channel": "system",
                "sent_at": None,
                "marked_sent_by": None,
                "message_preview": None,
                "delivery_status": delivery,
                "created_at": _now_iso(),
            }
            try:
                await db[COLLECTION].insert_one(doc)
            except DuplicateKeyError:
                skipped += 1
                continue
            await create_audit_log(
                action=AuditAction.RENT_REMINDER_AUTO_CREATED,
                client_id=client_id,
                resource_type="rent_reminder_event",
                resource_id=key,
                metadata={"ledger_id": ledger["ledger_id"], "reminder_type": rtype, "live_send": _live_send_enabled()},
            )
            created += 1

            if _live_send_enabled():
                try:
                    from services.notification_orchestrator import notification_orchestrator
                    await notification_orchestrator.send(
                        template_key="RENT_REMINDER",
                        client_id=client_id,
                        context={
                            "reminder_type": rtype,
                            "ledger_id": ledger["ledger_id"],
                            "property_id": ledger["property_id"],
                            "tenant_name": ledger.get("tenant_name"),
                            "outstanding_balance_minor": ledger.get("outstanding_balance_minor"),
                        },
                        idempotency_key=key,
                        event_type="RENT_REMINDER",
                    )
                    await db[COLLECTION].update_one(
                        {"reminder_key": key},
                        {"$set": {"delivery_status": ReminderDeliveryStatus.SENT.value, "sent_at": _now_iso()}},
                    )
                except Exception as exc:
                    logger.warning("Rent reminder live send failed key=%s: %s", key, exc)
                    await db[COLLECTION].update_one(
                        {"reminder_key": key},
                        {"$set": {"delivery_status": ReminderDeliveryStatus.FAILED.value}},
                    )

    return {"created": created, "skipped_existing": skipped}
