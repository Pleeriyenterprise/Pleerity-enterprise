"""Rent payment recording with oldest-outstanding-first allocation."""
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set

from database import database
from models.rent_operations import DEFAULT_CURRENCY, RentLedgerStatus
from services import rent_ledger_service
from services.rent_document_validation import validate_document_for_property
from utils.audit import create_audit_log
from models import AuditAction, UserRole

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payment_date_str(body: Dict[str, Any]) -> str:
    pd = body.get("payment_date")
    if isinstance(pd, date):
        return pd.isoformat()
    return str(pd)[:10]


async def _outstanding_ledgers(
    client_id: str,
    property_id: str,
    explicit_ledger_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    if explicit_ledger_id:
        doc = await db.rent_ledger_periods.find_one(
            {
                "ledger_id": explicit_ledger_id,
                "client_id": client_id,
                "is_deleted": {"$ne": True},
            },
            {"_id": 0},
        )
        return [doc] if doc else []

    rows = (
        await db.rent_ledger_periods.find(
            {
                "client_id": client_id,
                "property_id": property_id,
                "is_deleted": {"$ne": True},
                "status": {
                    "$nin": [
                        RentLedgerStatus.PAID.value,
                        RentLedgerStatus.WAIVED.value,
                    ]
                },
            },
            {"_id": 0},
        )
        .sort("due_date", 1)
        .to_list(200)
    )
    return [r for r in rows if int(r.get("outstanding_balance_minor") or 0) > 0]


async def _recalc_ledgers(
    ledger_ids: Set[str],
    client_id: str,
    actor_id: Optional[str],
    actor_role: Optional[UserRole],
) -> None:
    for lid in ledger_ids:
        try:
            await rent_ledger_service.recalculate_and_persist_ledger(
                lid, client_id, actor_id=actor_id, actor_role=actor_role, write_audit=True
            )
        except Exception as exc:
            logger.warning("rent payment recalc failed ledger_id=%s: %s", lid, exc)


async def record_payment(
    client_id: str,
    body: Dict[str, Any],
    actor_id: Optional[str] = None,
    actor_role: Optional[UserRole] = None,
) -> Dict[str, Any]:
    """
    Record payment with oldest-outstanding-first allocation unless ledger_id specified.
    Returns { payments, allocations, unallocated_minor }.
    """
    db = database.get_db()
    amount_remaining = int(body["amount_minor"])
    property_id = body.get("property_id")
    explicit_ledger_id = body.get("ledger_id")
    payment_date = _payment_date_str(body)
    touched_ledgers: Set[str] = set()

    if explicit_ledger_id:
        ledger = await db.rent_ledger_periods.find_one(
            {"ledger_id": explicit_ledger_id, "client_id": client_id, "is_deleted": {"$ne": True}},
            {"_id": 0},
        )
        if not ledger:
            raise ValueError("LEDGER_NOT_FOUND")
        property_id = ledger["property_id"]
        targets = [ledger]
    else:
        if not property_id:
            raise ValueError("PROPERTY_ID_REQUIRED")
        await rent_ledger_service._validate_property(db, client_id, property_id)
        targets = await _outstanding_ledgers(client_id, property_id)

    if not targets:
        raise ValueError("NO_OUTSTANDING_LEDGER")

    if body.get("document_id"):
        await validate_document_for_property(client_id, property_id, body.get("document_id"))

    created_payments: List[Dict[str, Any]] = []
    allocations: List[Dict[str, Any]] = []
    now = _now_iso()

    try:
        for ledger in targets:
            if amount_remaining <= 0:
                break
            ledger_id = ledger["ledger_id"]
            touched_ledgers.add(ledger_id)
            await rent_ledger_service.recalculate_and_persist_ledger(
                ledger_id, client_id, actor_id, actor_role, write_audit=True
            )
            fresh = await db.rent_ledger_periods.find_one(
                {"ledger_id": ledger_id, "client_id": client_id}, {"_id": 0}
            )
            outstanding = int(fresh.get("outstanding_balance_minor") or 0)
            if outstanding <= 0:
                continue
            alloc = min(amount_remaining, outstanding)
            payment_id = f"rp_{uuid.uuid4().hex[:12]}"
            payment_doc = {
                "payment_id": payment_id,
                "ledger_id": ledger_id,
                "client_id": client_id,
                "property_id": property_id,
                "amount_minor": alloc,
                "currency": body.get("currency") or fresh.get("currency") or DEFAULT_CURRENCY,
                "payment_date": payment_date,
                "payment_method": body.get("payment_method"),
                "reference": body.get("reference"),
                "note": body.get("note"),
                "document_id": body.get("document_id"),
                "recorded_by": actor_id,
                "created_at": now,
                "updated_at": now,
            }
            await db.rent_payments.insert_one(payment_doc)
            await create_audit_log(
                action=AuditAction.RENT_PAYMENT_RECORDED,
                actor_role=actor_role,
                actor_id=actor_id,
                client_id=client_id,
                resource_type="rent_payment",
                resource_id=payment_id,
                metadata={
                    "ledger_id": ledger_id,
                    "property_id": property_id,
                    "amount_minor": alloc,
                    "payment_date": payment_date,
                },
            )
            allocations.append(
                {"ledger_id": ledger_id, "amount_minor": alloc, "period_key": fresh.get("period_key")}
            )
            created_payments.append({k: v for k, v in payment_doc.items() if k != "_id"})
            amount_remaining -= alloc
    finally:
        if touched_ledgers:
            await _recalc_ledgers(touched_ledgers, client_id, actor_id, actor_role)

    if not created_payments:
        raise ValueError("NO_ALLOCATION_MADE")

    return {
        "payments": created_payments,
        "allocations": allocations,
        "unallocated_minor": amount_remaining,
    }


async def record_payment_for_ledger(
    ledger_id: str,
    client_id: str,
    body: Dict[str, Any],
    actor_id: Optional[str] = None,
    actor_role: Optional[UserRole] = None,
) -> Dict[str, Any]:
    body = dict(body)
    body["ledger_id"] = ledger_id
    return await record_payment(client_id, body, actor_id, actor_role)
