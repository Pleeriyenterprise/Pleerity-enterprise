"""Rent reminder tracking — idempotent keys; Phase 1 default is manual send."""
import logging
import os
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

_REMINDER_LABELS = {
    RentReminderType.DUE_SOON.value: "Rent due soon",
    RentReminderType.DUE_TODAY.value: "Rent due today",
    RentReminderType.OVERDUE_3D.value: "Rent overdue",
    RentReminderType.OVERDUE_7D.value: "Rent seriously overdue",
    RentReminderType.OVERDUE_14D.value: "Rent severely overdue",
}


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


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _live_send_enabled() -> bool:
    return _env_flag("RENT_REMINDERS_LIVE_SEND")


def _production_mode_enabled() -> bool:
    """Production intent: all RENT_OPERATIONS clients, any linked tenant email domain."""
    return _env_flag("RENT_REMINDERS_PRODUCTION_MODE")


def _live_send_enabled_for_client(client_id: str) -> bool:
    if not _live_send_enabled():
        return False
    if _production_mode_enabled():
        return True
    allowlist = os.environ.get("RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST", "").strip()
    if not allowlist:
        return True
    allowed = {item.strip() for item in allowlist.split(",") if item.strip()}
    return client_id in allowed


def _safe_recipient_domains() -> List[str]:
    raw = os.environ.get("RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS")
    if raw is None:
        # Staging-safe default unless production mode explicitly opts into all domains.
        raw = "" if _production_mode_enabled() else "yopmail.com"
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def recipient_allowed_for_live_send(email: str) -> bool:
    if not email or not str(email).strip():
        return False
    domains = _safe_recipient_domains()
    if not domains:
        return True
    normalized = str(email).strip().lower()
    return any(normalized.endswith(f"@{domain}") for domain in domains)


def get_live_send_config() -> Dict[str, Any]:
    allowlist = os.environ.get("RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST", "")
    production_mode = _production_mode_enabled()
    return {
        "global_live_send": _live_send_enabled(),
        "production_mode": production_mode,
        "client_allowlist": allowlist,
        "client_allowlist_enforced": bool(allowlist.strip()) and not production_mode,
        "safe_recipient_domains": _safe_recipient_domains(),
        "safe_recipient_domains_enforced": bool(_safe_recipient_domains()),
        "sms_live_send": _env_flag("SMS_ENABLED"),
    }


def _format_gbp_minor(minor: int) -> str:
    return f"£{int(minor or 0) / 100:.2f}"


def build_reminder_message(ledger: Dict[str, Any], reminder_type: str) -> str:
    tenant = (ledger.get("tenant_name") or "Tenant").strip()
    due = ledger.get("due_date") or ""
    outstanding = int(ledger.get("outstanding_balance_minor") or 0)
    expected = int(ledger.get("expected_amount_minor") or outstanding)
    label = _REMINDER_LABELS.get(reminder_type, "Rent reminder")
    partial_note = ""
    if ledger.get("status") == RentLedgerStatus.PARTIALLY_PAID.value:
        partial_note = (
            " A partial payment has already been recorded; this notice relates to the remaining balance."
        )
    return (
        f"<p>Dear {tenant},</p>"
        f"<p><strong>{label}</strong></p>"
        f"<p>Rent of {_format_gbp_minor(expected)} was due on {due}. "
        f"The outstanding balance is {_format_gbp_minor(outstanding)}.{partial_note}</p>"
        f"<p>Please arrange payment at your earliest convenience. "
        f"If you have already paid, please disregard this message.</p>"
        f"<p>Kind regards,<br/>Rent Operations</p>"
    )


async def _resolve_reminder_recipient(db, ledger: Dict[str, Any], client_id: str) -> Optional[str]:
    tenant_ids: List[str] = []
    tenancy_id = ledger.get("tenancy_id")
    if tenancy_id and not str(tenancy_id).startswith("ext_"):
        tenancy = await db.property_tenancies.find_one(
            {"tenancy_id": tenancy_id, "client_id": client_id},
            {"_id": 0, "tenant_ids": 1, "tenant_assignments": 1},
        )
        if tenancy:
            tenant_ids = list(tenancy.get("tenant_ids") or [])
            for assignment in tenancy.get("tenant_assignments") or []:
                tid = assignment.get("tenant_id")
                if tid and tid not in tenant_ids:
                    tenant_ids.append(tid)
    if not tenant_ids:
        assignments = await db.tenant_assignments.find(
            {"property_id": ledger.get("property_id"), "client_id": client_id},
            {"_id": 0, "tenant_id": 1},
        ).to_list(10)
        tenant_ids = [row["tenant_id"] for row in assignments if row.get("tenant_id")]
    for tid in tenant_ids:
        tenant = await db.portal_users.find_one(
            {"portal_user_id": tid, "client_id": client_id},
            {"_id": 0, "auth_email": 1, "email": 1},
        )
        if not tenant:
            continue
        email = (tenant.get("auth_email") or tenant.get("email") or "").strip()
        if email:
            return email
    return None


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


async def _attempt_live_send(
    db,
    *,
    client_id: str,
    ledger: Dict[str, Any],
    reminder_type: str,
    reminder_key: str,
) -> str:
    recipient = await _resolve_reminder_recipient(db, ledger, client_id)
    if not recipient:
        await db[COLLECTION].update_one(
            {"reminder_key": reminder_key},
            {
                "$set": {
                    "delivery_status": ReminderDeliveryStatus.FAILED.value,
                    "message_preview": "no_tenant_recipient",
                }
            },
        )
        return "no_recipient"
    if not recipient_allowed_for_live_send(recipient):
        await db[COLLECTION].update_one(
            {"reminder_key": reminder_key},
            {
                "$set": {
                    "delivery_status": ReminderDeliveryStatus.FAILED.value,
                    "message_preview": "recipient_not_safe_for_live_send",
                    "recipient_email": recipient,
                }
            },
        )
        return "recipient_blocked"
    message = build_reminder_message(ledger, reminder_type)
    try:
        from services.notification_orchestrator import notification_orchestrator

        result = await notification_orchestrator.send(
            template_key="RENT_REMINDER",
            client_id=client_id,
            context={
                "reminder_type": reminder_type,
                "ledger_id": ledger["ledger_id"],
                "property_id": ledger["property_id"],
                "tenant_name": ledger.get("tenant_name"),
                "outstanding_balance_minor": ledger.get("outstanding_balance_minor"),
                "expected_amount_minor": ledger.get("expected_amount_minor"),
                "due_date": ledger.get("due_date"),
                "period_key": ledger.get("period_key") or ledger["ledger_id"],
                "recipient": recipient,
                "message": message,
            },
            idempotency_key=reminder_key,
            event_type="RENT_REMINDER",
        )
        if result.outcome in ("sent", "duplicate_ignored"):
            await db[COLLECTION].update_one(
                {"reminder_key": reminder_key},
                {
                    "$set": {
                        "delivery_status": ReminderDeliveryStatus.SENT.value,
                        "sent_at": _now_iso(),
                        "recipient_email": recipient,
                        "message_preview": message[:500],
                        "channel": "email",
                    }
                },
            )
            return result.outcome
        await db[COLLECTION].update_one(
            {"reminder_key": reminder_key},
            {
                "$set": {
                    "delivery_status": ReminderDeliveryStatus.FAILED.value,
                    "message_preview": result.block_reason or result.error_message or result.outcome,
                    "recipient_email": recipient,
                }
            },
        )
        return result.outcome
    except Exception as exc:
        logger.warning("Rent reminder live send failed key=%s: %s", reminder_key, exc)
        await db[COLLECTION].update_one(
            {"reminder_key": reminder_key},
            {"$set": {"delivery_status": ReminderDeliveryStatus.FAILED.value, "message_preview": str(exc)[:200]}},
        )
        return "failed"


async def process_reminders_for_client(client_id: str) -> Dict[str, Any]:
    """Create missing reminder events for client ledgers. Live send only if flag enabled."""
    db = database.get_db()
    today = datetime.now(timezone.utc).date()
    live_for_client = _live_send_enabled_for_client(client_id)
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
    sent = 0
    failed = 0
    for ledger in ledgers:
        period_key = ledger.get("period_key") or ledger["ledger_id"]
        for rtype in _reminder_types_for_ledger(ledger, today):
            key = build_reminder_key(rtype, ledger["ledger_id"], period_key)
            existing = await db[COLLECTION].find_one({"reminder_key": key}, {"_id": 1})
            if existing:
                skipped += 1
                continue
            delivery = (
                ReminderDeliveryStatus.PENDING.value
                if live_for_client
                else ReminderDeliveryStatus.MANUAL.value
            )
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
                metadata={"ledger_id": ledger["ledger_id"], "reminder_type": rtype, "live_send": live_for_client},
            )
            created += 1

            if live_for_client:
                outcome = await _attempt_live_send(
                    db,
                    client_id=client_id,
                    ledger=ledger,
                    reminder_type=rtype,
                    reminder_key=key,
                )
                if outcome in ("sent", "duplicate_ignored"):
                    sent += 1
                else:
                    failed += 1

    return {
        "created": created,
        "skipped_existing": skipped,
        "live_send_enabled": live_for_client,
        "live_sent": sent,
        "live_failed": failed,
    }
