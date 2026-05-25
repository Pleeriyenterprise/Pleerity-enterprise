"""
Rent ledger periods — property-linked operational rent tracking.
Status is derived from facts; never manually trusted except waive/dispute flags.
"""
import logging
import os
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from database import database
from models.rent_operations import (
    DEFAULT_CURRENCY,
    FUTURE_PERIODS_MONTHS_AHEAD,
    RENT_SEVERELY_OVERDUE_DAYS,
    RentFrequency,
    RentLedgerStatus,
)
from utils.audit import create_audit_log
from models import AuditAction, UserRole
from services import rent_tenancy_authority_service as tenancy_authority

logger = logging.getLogger(__name__)

COLLECTION_PERIODS = "rent_ledger_periods"
COLLECTION_SCHEDULES = "rent_schedules"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def _severely_overdue_days() -> int:
    raw = os.environ.get("RENT_SEVERELY_OVERDUE_DAYS", str(RENT_SEVERELY_OVERDUE_DAYS))
    try:
        return max(1, int(raw))
    except ValueError:
        return RENT_SEVERELY_OVERDUE_DAYS


def recalculate_rent_ledger_status(
    expected_amount_minor: int,
    received_amount_minor: int,
    due_date_str: str,
    waived_at: Optional[str] = None,
    disputed_at: Optional[str] = None,
    as_of: Optional[date] = None,
) -> Tuple[str, int, int]:
    """
    Derive status, days_overdue, outstanding_balance_minor from facts.
    Returns (status, days_overdue, outstanding_balance_minor).
    """
    as_of = as_of or datetime.now(timezone.utc).date()
    due_date = _parse_date(due_date_str)
    outstanding = max(0, expected_amount_minor - received_amount_minor)
    days_overdue = max(0, (as_of - due_date).days) if due_date < as_of else 0

    if waived_at:
        return RentLedgerStatus.WAIVED.value, days_overdue, outstanding
    if disputed_at:
        return RentLedgerStatus.DISPUTED.value, days_overdue, outstanding
    if outstanding == 0 and received_amount_minor > 0:
        return RentLedgerStatus.PAID.value, 0, 0
    if 0 < received_amount_minor < expected_amount_minor:
        if due_date == as_of and outstanding > 0:
            return RentLedgerStatus.DUE_TODAY.value, 0, outstanding
        return RentLedgerStatus.PARTIALLY_PAID.value, days_overdue, outstanding
    if due_date == as_of and outstanding > 0:
        return RentLedgerStatus.DUE_TODAY.value, 0, outstanding
    if due_date > as_of:
        return RentLedgerStatus.UPCOMING.value, 0, outstanding
    threshold = _severely_overdue_days()
    if days_overdue >= threshold:
        return RentLedgerStatus.SEVERELY_OVERDUE.value, days_overdue, outstanding
    return RentLedgerStatus.OVERDUE.value, days_overdue, outstanding


def derive_is_overdue(
    outstanding_balance_minor: int,
    due_date_str: str,
    waived_at: Optional[str] = None,
    disputed_at: Optional[str] = None,
    as_of: Optional[date] = None,
) -> bool:
    """True when balance remains and due date is before today (operational overdue)."""
    if waived_at or disputed_at:
        return False
    if outstanding_balance_minor <= 0:
        return False
    as_of = as_of or datetime.now(timezone.utc).date()
    due_date = _parse_date(due_date_str)
    return due_date < as_of


async def _validate_property(db, client_id: str, property_id: str) -> Dict[str, Any]:
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    if not prop:
        raise ValueError("PROPERTY_NOT_FOUND")
    return prop


async def ensure_property_scope(client_id: str, property_id: Optional[str]) -> None:
    """Raise PROPERTY_NOT_FOUND when property_id is supplied but not owned."""
    if not property_id:
        return
    db = database.get_db()
    await _validate_property(db, client_id, property_id)


async def sum_rent_collected_by_payment_date(
    client_id: str,
    month_start: str,
    month_end: str,
    property_id: Optional[str] = None,
) -> int:
    """Sum rent_payments.amount_minor by payment_date (includes partial payments)."""
    db = database.get_db()
    match: Dict[str, Any] = {
        "client_id": client_id,
        "payment_date": {"$gte": month_start, "$lte": month_end},
    }
    if property_id:
        match["property_id"] = property_id
    pipeline = [
        {"$match": match},
        {"$group": {"_id": None, "total": {"$sum": "$amount_minor"}}},
    ]
    rows = await db.rent_payments.aggregate(pipeline).to_list(1)
    return int((rows[0]["total"] if rows else 0) or 0)


async def recalculate_and_persist_ledger(
    ledger_id: str,
    client_id: str,
    actor_id: Optional[str] = None,
    actor_role: Optional[UserRole] = None,
    write_audit: bool = True,
) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db[COLLECTION_PERIODS].find_one(
        {"ledger_id": ledger_id, "client_id": client_id, "is_deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not doc:
        return None

    payments = await db.rent_payments.find(
        {"ledger_id": ledger_id, "client_id": client_id},
        {"_id": 0, "amount_minor": 1},
    ).to_list(500)
    received = sum(int(p.get("amount_minor") or 0) for p in payments)
    expected = int(doc.get("expected_amount_minor") or 0)
    overpaid_minor = max(0, received - expected)

    status, days_overdue, outstanding = recalculate_rent_ledger_status(
        expected_amount_minor=expected,
        received_amount_minor=received,
        due_date_str=doc.get("due_date", ""),
        waived_at=doc.get("waived_at"),
        disputed_at=doc.get("disputed_at"),
    )
    is_overdue = derive_is_overdue(
        outstanding,
        doc.get("due_date", ""),
        waived_at=doc.get("waived_at"),
        disputed_at=doc.get("disputed_at"),
    )
    now = _now_iso()
    await db[COLLECTION_PERIODS].update_one(
        {"ledger_id": ledger_id, "client_id": client_id},
        {
            "$set": {
                "received_amount_minor": received,
                "outstanding_balance_minor": outstanding,
                "status": status,
                "days_overdue": days_overdue,
                "is_overdue": is_overdue,
                "overpaid_minor": overpaid_minor,
                "updated_at": now,
            }
        },
    )
    if write_audit:
        await create_audit_log(
            action=AuditAction.RENT_STATUS_RECALCULATED,
            actor_role=actor_role,
            actor_id=actor_id,
            client_id=client_id,
            resource_type="rent_ledger_period",
            resource_id=ledger_id,
            metadata={
                "status": status,
                "outstanding_balance_minor": outstanding,
                "days_overdue": days_overdue,
                "is_overdue": is_overdue,
            },
        )
    doc.update(
        {
            "received_amount_minor": received,
            "outstanding_balance_minor": outstanding,
            "status": status,
            "days_overdue": days_overdue,
            "is_overdue": is_overdue,
            "overpaid_minor": overpaid_minor,
            "updated_at": now,
        }
    )
    return doc


def _monthly_period_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _monthly_due_date(year: int, month: int, due_day: int) -> date:
    last = monthrange(year, month)[1]
    day = min(due_day, last)
    return date(year, month, day)


def _weekly_period_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _weekly_due_date(start: date, due_weekday: int, period_start: date) -> date:
    """due_weekday: 0=Monday .. 6=Sunday"""
    delta = (due_weekday - period_start.weekday()) % 7
    return period_start + timedelta(days=delta)


def _generate_periods_for_schedule(
    schedule: Dict[str, Any],
    from_date: date,
    months_ahead: int = FUTURE_PERIODS_MONTHS_AHEAD,
) -> List[Dict[str, Any]]:
    frequency = (schedule.get("rent_frequency") or RentFrequency.MONTHLY.value).lower()
    due_day = int(schedule.get("due_day") or 1)
    amount = int(schedule.get("expected_amount_minor") or 0)
    currency = schedule.get("currency") or DEFAULT_CURRENCY
    start = _parse_date(schedule["start_date"])
    end = _parse_date(schedule["end_date"]) if schedule.get("end_date") else None
    until = from_date + timedelta(days=months_ahead * 31)
    if end and end < until:
        until = end

    periods: List[Dict[str, Any]] = []
    if frequency == RentFrequency.WEEKLY.value:
        cursor = start - timedelta(days=start.weekday())
        while cursor <= until:
            if cursor >= start:
                pk = _weekly_period_key(cursor)
                due = cursor + timedelta(days=(due_day % 7))
                periods.append(
                    {
                        "period_key": pk,
                        "due_date": due.isoformat(),
                        "expected_amount_minor": amount,
                        "currency": currency,
                        "rent_frequency": frequency,
                    }
                )
            cursor += timedelta(days=7)
    else:
        y, m = start.year, start.month
        while True:
            due = _monthly_due_date(y, m, due_day)
            if due >= start and due <= until:
                periods.append(
                    {
                        "period_key": _monthly_period_key(due),
                        "due_date": due.isoformat(),
                        "expected_amount_minor": amount,
                        "currency": currency,
                        "rent_frequency": frequency,
                    }
                )
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
            if _monthly_due_date(y, m, due_day) > until:
                break
    return periods


async def ensure_future_periods_for_schedule(
    schedule: Dict[str, Any],
    actor_id: Optional[str] = None,
) -> int:
    """Create missing rent_ledger_periods for an active schedule. Returns count created."""
    db = database.get_db()
    client_id = schedule["client_id"]
    property_id = schedule["property_id"]
    today = datetime.now(timezone.utc).date()
    periods = _generate_periods_for_schedule(schedule, today)
    created = 0
    now = _now_iso()

    schedule_id = schedule.get("schedule_id")
    tenancy_id = schedule.get("tenancy_id")

    for p in periods:
        period_query: Dict[str, Any] = {
            "client_id": client_id,
            "property_id": property_id,
            "period_key": p["period_key"],
            "is_deleted": {"$ne": True},
        }
        if schedule_id:
            period_query["schedule_id"] = schedule_id
        elif tenancy_id:
            period_query["tenancy_id"] = tenancy_id
        existing = await db[COLLECTION_PERIODS].find_one(period_query, {"_id": 1})
        if existing:
            continue
        ledger_id = f"rlp_{uuid.uuid4().hex[:12]}"
        period_start = p["due_date"]
        period_end = p["due_date"]
        status, days_overdue, outstanding = recalculate_rent_ledger_status(
            expected_amount_minor=p["expected_amount_minor"],
            received_amount_minor=0,
            due_date_str=p["due_date"],
        )
        is_overdue = derive_is_overdue(outstanding, p["due_date"])
        doc = {
            "ledger_id": ledger_id,
            "client_id": client_id,
            "property_id": property_id,
            "schedule_id": schedule.get("schedule_id"),
            "tenancy_id": schedule.get("tenancy_id"),
            "tenant_name": schedule.get("tenant_name"),
            "period_key": p["period_key"],
            "period_start": period_start,
            "period_end": period_end,
            "expected_amount_minor": p["expected_amount_minor"],
            "currency": p["currency"],
            "rent_frequency": p["rent_frequency"],
            "due_date": p["due_date"],
            "received_amount_minor": 0,
            "outstanding_balance_minor": outstanding,
            "status": status,
            "days_overdue": days_overdue,
            "is_overdue": is_overdue,
            "waived_at": None,
            "disputed_at": None,
            "dispute_note": None,
            "notes": schedule.get("notes"),
            "created_at": now,
            "updated_at": now,
            "created_by": actor_id,
            "updated_by": actor_id,
            "is_deleted": False,
        }
        try:
            await db[COLLECTION_PERIODS].insert_one(doc)
        except DuplicateKeyError:
            continue
        await create_audit_log(
            action=AuditAction.RENT_LEDGER_CREATED,
            actor_id=actor_id,
            client_id=client_id,
            resource_type="rent_ledger_period",
            resource_id=ledger_id,
            metadata={"property_id": property_id, "period_key": p["period_key"], "auto_generated": True},
        )
        created += 1
    return created


def preview_schedule_periods(body: Dict[str, Any]) -> Dict[str, Any]:
    """Non-persisting preview for schedule creation honesty (period count, range, cadence)."""
    rent_frequency = (body.get("rent_frequency") or RentFrequency.MONTHLY.value).lower()
    due_day = int(body.get("due_day") or 1)
    start_raw = body["start_date"]
    start_date = _parse_date(start_raw if isinstance(start_raw, str) else str(start_raw))
    end_raw = body.get("end_date")
    end_date = _parse_date(end_raw) if end_raw else None
    stub = {
        "rent_frequency": rent_frequency,
        "due_day": due_day,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat() if end_date else None,
        "expected_amount_minor": int(body.get("expected_amount_minor") or 0),
    }
    today = datetime.now(timezone.utc).date()
    periods = _generate_periods_for_schedule(stub, today)
    if not periods:
        return {
            "period_count": 0,
            "period_start": None,
            "period_end": None,
            "cadence_label": rent_frequency,
            "next_due_date": None,
            "disclosure": "No rent periods would be generated for the selected dates.",
        }
    due_dates = [_parse_date(p["due_date"]) for p in periods]
    next_due = min((d for d in due_dates if d >= today), default=due_dates[0])
    start_label = min(due_dates).strftime("%b %Y")
    end_label = max(due_dates).strftime("%b %Y")
    cadence = "monthly" if rent_frequency == RentFrequency.MONTHLY.value else "weekly"
    disclosure = (
        f"This will create {len(periods)} {cadence} rent periods from {start_label} to {end_label}. "
        f"Next due date: {next_due.isoformat()}."
    )
    return {
        "period_count": len(periods),
        "period_start": min(due_dates).isoformat(),
        "period_end": max(due_dates).isoformat(),
        "cadence_label": cadence,
        "next_due_date": next_due.isoformat(),
        "disclosure": disclosure,
    }


async def create_rent_schedule(
    client_id: str,
    body: Dict[str, Any],
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    property_id = body["property_id"]
    idempotency_key = (body.get("idempotency_key") or "").strip() or None

    if idempotency_key:
        prior = await db[COLLECTION_SCHEDULES].find_one(
            {"client_id": client_id, "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if prior:
            prior["idempotent_replay"] = True
            prior["periods_created"] = 0
            return prior

    _prop, tenancy, is_external = await tenancy_authority.validate_schedule_authority(client_id, body)
    tenancy_id = tenancy["tenancy_id"]
    rent_type = body.get("rent_type") or tenancy_authority.DEFAULT_RENT_TYPE
    tenant_name = (
        body.get("tenant_name")
        or tenancy.get("tenant_display_name")
        or body.get("external_payer_name")
        or "Tenant"
    )

    await db[COLLECTION_SCHEDULES].update_many(
        {
            "client_id": client_id,
            "property_id": property_id,
            "tenancy_id": tenancy_id,
            "rent_type": rent_type,
            "is_active": True,
        },
        {"$set": {"is_active": False, "superseded_at": _now_iso(), "updated_at": _now_iso()}},
    )

    schedule_id = f"rs_{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    ed = body.get("end_date")
    schedule = {
        "schedule_id": schedule_id,
        "client_id": client_id,
        "property_id": property_id,
        "tenancy_id": tenancy_id,
        "rent_type": rent_type,
        "tenant_name": tenant_name,
        "is_external_payer": is_external,
        "external_payer_name": body.get("external_payer_name") if is_external else None,
        "expected_amount_minor": int(body["expected_amount_minor"]),
        "currency": body.get("currency") or DEFAULT_CURRENCY,
        "rent_frequency": (body.get("rent_frequency") or RentFrequency.MONTHLY.value).lower(),
        "due_day": int(body.get("due_day") or 1),
        "start_date": body["start_date"] if isinstance(body["start_date"], str) else str(body["start_date"]),
        "end_date": ed if ed is None or isinstance(ed, str) else str(ed),
        "notes": body.get("notes"),
        "is_active": True,
        "idempotency_key": idempotency_key,
        "created_at": now,
        "updated_at": now,
        "created_by": actor_id,
    }
    preview = preview_schedule_periods(body)
    schedule["creation_preview"] = preview

    try:
        await db[COLLECTION_SCHEDULES].insert_one(schedule)
        periods_created = await ensure_future_periods_for_schedule(schedule, actor_id=actor_id)
        schedule["periods_created"] = periods_created
        schedule["success"] = True
        schedule["message"] = preview.get("disclosure") or f"Rent schedule created ({periods_created} periods)."
        if not is_external:
            await db[tenancy_authority.COLLECTION_TENANCIES].update_one(
                {"tenancy_id": tenancy_id, "client_id": client_id},
                {"$set": {"rent_tracking_enabled": True, "updated_at": now}},
            )
        return schedule
    except Exception as exc:
        logger.exception("rent schedule create failed schedule_id=%s", schedule_id)
        existing_periods = await db[COLLECTION_PERIODS].count_documents(
            {"client_id": client_id, "schedule_id": schedule_id, "is_deleted": {"$ne": True}},
        )
        if existing_periods:
            schedule["success"] = True
            schedule["partial_recovery"] = True
            schedule["periods_created"] = existing_periods
            schedule["message"] = (
                f"Schedule saved with {existing_periods} ledger period(s) already materialised. "
                "Refresh to view — do not resubmit."
            )
            return schedule
        await db[COLLECTION_SCHEDULES].delete_one({"schedule_id": schedule_id, "client_id": client_id})
        raise exc


async def list_schedules(client_id: str, property_id: Optional[str] = None) -> List[Dict[str, Any]]:
    db = database.get_db()
    if property_id:
        await ensure_property_scope(client_id, property_id)
    q: Dict[str, Any] = {"client_id": client_id, "is_active": True}
    if property_id:
        q["property_id"] = property_id
    rows = await db[COLLECTION_SCHEDULES].find(q, {"_id": 0}).to_list(100)
    return rows


async def list_ledgers(
    client_id: str,
    property_id: Optional[str] = None,
    tenancy_id: Optional[str] = None,
    status: Optional[str] = None,
    due_from: Optional[str] = None,
    due_to: Optional[str] = None,
    tenant_name: Optional[str] = None,
    attention_only: bool = False,
    overdue_only: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    db = database.get_db()
    if property_id:
        await ensure_property_scope(client_id, property_id)
    q: Dict[str, Any] = {"client_id": client_id, "is_deleted": {"$ne": True}}
    if property_id:
        q["property_id"] = property_id
    if tenancy_id:
        q["tenancy_id"] = tenancy_id
    if status:
        q["status"] = status
    if tenant_name:
        q["tenant_name"] = {"$regex": tenant_name, "$options": "i"}
    if due_from or due_to:
        q["due_date"] = {}
        if due_from:
            q["due_date"]["$gte"] = due_from
        if due_to:
            q["due_date"]["$lte"] = due_to
    if overdue_only:
        q["is_overdue"] = True
    elif attention_only:
        q["$or"] = [
            {"is_overdue": True},
            {"status": RentLedgerStatus.DUE_TODAY.value},
            {"status": RentLedgerStatus.DISPUTED.value},
            {"status": RentLedgerStatus.PARTIALLY_PAID.value, "is_overdue": True},
        ]

    total = await db[COLLECTION_PERIODS].count_documents(q)
    rows = await (
        db[COLLECTION_PERIODS]
        .find(q, {"_id": 0})
        .sort("due_date", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    return {"ledgers": rows, "total": total}


async def get_ledger(ledger_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db[COLLECTION_PERIODS].find_one(
        {"ledger_id": ledger_id, "client_id": client_id, "is_deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not doc:
        return None
    payments = (
        await db.rent_payments.find({"ledger_id": ledger_id, "client_id": client_id}, {"_id": 0})
        .sort("payment_date", -1)
        .to_list(200)
    )
    reminders = (
        await db.rent_reminder_events.find({"ledger_id": ledger_id, "client_id": client_id}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )
    doc["payments"] = payments
    doc["reminders"] = reminders
    return doc


async def update_ledger(
    ledger_id: str,
    client_id: str,
    body: Dict[str, Any],
    actor_id: Optional[str] = None,
    actor_role: Optional[UserRole] = None,
) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db[COLLECTION_PERIODS].find_one(
        {"ledger_id": ledger_id, "client_id": client_id, "is_deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not doc:
        return None

    updates: Dict[str, Any] = {"updated_at": _now_iso(), "updated_by": actor_id}
    if body.get("expected_amount_minor") is not None:
        updates["expected_amount_minor"] = int(body["expected_amount_minor"])
    if body.get("due_date") is not None:
        d = body["due_date"]
        updates["due_date"] = d if isinstance(d, str) else d.isoformat() if hasattr(d, "isoformat") else str(d)
    if body.get("tenant_name") is not None:
        updates["tenant_name"] = body["tenant_name"]
    if body.get("notes") is not None:
        updates["notes"] = body["notes"]
    if body.get("waived") is True:
        updates["waived_at"] = _now_iso()
        updates["disputed_at"] = None
    elif body.get("waived") is False:
        updates["waived_at"] = None
    if body.get("disputed") is True:
        updates["disputed_at"] = _now_iso()
        updates["waived_at"] = None
        if body.get("dispute_note"):
            updates["dispute_note"] = body["dispute_note"]
    elif body.get("disputed") is False:
        updates["disputed_at"] = None
        updates["dispute_note"] = None

    await db[COLLECTION_PERIODS].update_one({"ledger_id": ledger_id}, {"$set": updates})
    await create_audit_log(
        action=AuditAction.RENT_LEDGER_UPDATED,
        actor_role=actor_role,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="rent_ledger_period",
        resource_id=ledger_id,
        metadata={k: v for k, v in body.items() if v is not None},
    )
    return await recalculate_and_persist_ledger(ledger_id, client_id, actor_id, actor_role)


async def get_rent_summary(client_id: str, property_id: Optional[str] = None) -> Dict[str, Any]:
    db = database.get_db()
    if property_id:
        await ensure_property_scope(client_id, property_id)
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1).isoformat()
    month_end = today.isoformat()

    base: Dict[str, Any] = {"client_id": client_id, "is_deleted": {"$ne": True}}
    if property_id:
        base["property_id"] = property_id

    collected_minor = await sum_rent_collected_by_payment_date(
        client_id, month_start, month_end, property_id=property_id
    )

    upcoming_count = await db[COLLECTION_PERIODS].count_documents(
        {**base, "status": RentLedgerStatus.UPCOMING.value}
    )
    overdue_count = await db[COLLECTION_PERIODS].count_documents({**base, "is_overdue": True})
    severely_overdue_count = await db[COLLECTION_PERIODS].count_documents(
        {
            **base,
            "status": RentLedgerStatus.SEVERELY_OVERDUE.value,
            "is_overdue": True,
        }
    )
    partial_count = await db[COLLECTION_PERIODS].count_documents(
        {**base, "status": RentLedgerStatus.PARTIALLY_PAID.value}
    )
    partial_overdue_count = await db[COLLECTION_PERIODS].count_documents(
        {**base, "status": RentLedgerStatus.PARTIALLY_PAID.value, "is_overdue": True}
    )
    due_today_count = await db[COLLECTION_PERIODS].count_documents(
        {**base, "status": RentLedgerStatus.DUE_TODAY.value}
    )

    arrears_pipeline = [
        {"$match": {**base, "outstanding_balance_minor": {"$gt": 0}}},
        {
            "$group": {
                "_id": {
                    "$ifNull": [
                        "$tenancy_id",
                        {"$concat": ["property:", "$property_id"]},
                    ]
                }
            }
        },
        {"$count": "tenancies"},
    ]
    arrears = await db[COLLECTION_PERIODS].aggregate(arrears_pipeline).to_list(1)
    arrears_count = int((arrears[0]["tenancies"] if arrears else 0) or 0)

    delay_pipeline = [
        {
            "$match": {
                **base,
                "status": RentLedgerStatus.PAID.value,
                "days_overdue": {"$gt": 0},
            }
        },
        {"$group": {"_id": None, "avg_delay": {"$avg": "$days_overdue"}}},
    ]
    delay = await db[COLLECTION_PERIODS].aggregate(delay_pipeline).to_list(1)
    avg_delay = round(float((delay[0]["avg_delay"] if delay else 0) or 0), 1)

    overdue_balance_pipeline = [
        {"$match": {**base, "outstanding_balance_minor": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$outstanding_balance_minor"}}},
    ]
    ob = await db[COLLECTION_PERIODS].aggregate(overdue_balance_pipeline).to_list(1)
    overdue_balance_minor = int((ob[0]["total"] if ob else 0) or 0)

    return {
        "rent_collected_this_month_minor": collected_minor,
        "currency": DEFAULT_CURRENCY,
        "upcoming_due_count": upcoming_count,
        "overdue_count": overdue_count,
        "severely_overdue_count": severely_overdue_count,
        "partially_paid_count": partial_count,
        "partial_overdue_count": partial_overdue_count,
        "due_today_count": due_today_count,
        "tenancies_with_arrears_count": arrears_count,
        "average_payment_delay_days": avg_delay,
        "total_outstanding_minor": overdue_balance_minor,
    }


async def recalculate_all_active_ledgers(
    client_id: str,
    write_audit: bool = False,
) -> Dict[str, Any]:
    db = database.get_db()
    rows = await db[COLLECTION_PERIODS].find(
        {"client_id": client_id, "is_deleted": {"$ne": True}},
        {"_id": 0, "ledger_id": 1, "status": 1},
    ).to_list(5000)
    statuses_changed = 0
    for r in rows:
        prior_status = r.get("status")
        updated = await recalculate_and_persist_ledger(
            r["ledger_id"], client_id, write_audit=write_audit
        )
        if updated and updated.get("status") != prior_status:
            statuses_changed += 1
    if not write_audit and rows:
        await create_audit_log(
            action=AuditAction.RENT_STATUS_RECALCULATED_BATCH,
            client_id=client_id,
            resource_type="rent_ledger_batch",
            resource_id=client_id,
            metadata={
                "ledgers_processed": len(rows),
                "statuses_changed": statuses_changed,
            },
        )
    return {"ledgers_processed": len(rows), "statuses_changed": statuses_changed}
