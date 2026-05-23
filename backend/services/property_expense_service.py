"""Property-linked operational expense tracking."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from models.rent_operations import DEFAULT_CURRENCY, ExpenseCategory
from services.rent_ledger_service import ensure_property_scope
from services.rent_document_validation import validate_document_for_property
from utils.audit import create_audit_log
from models import AuditAction, UserRole

logger = logging.getLogger(__name__)

COLLECTION = "property_expenses"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _validate_property(db, client_id: str, property_id: str) -> None:
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 1},
    )
    if not prop:
        raise ValueError("PROPERTY_NOT_FOUND")


async def create_expense(
    client_id: str,
    body: Dict[str, Any],
    actor_id: Optional[str] = None,
    actor_role: Optional[UserRole] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    property_id = body["property_id"]
    await _validate_property(db, client_id, property_id)
    if body.get("document_id"):
        await validate_document_for_property(client_id, property_id, body.get("document_id"))

    expense_date = body["expense_date"]
    if hasattr(expense_date, "isoformat"):
        expense_date = expense_date.isoformat()

    expense_id = f"pe_{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    doc = {
        "expense_id": expense_id,
        "client_id": client_id,
        "property_id": property_id,
        "category": body["category"],
        "amount_minor": int(body["amount_minor"]),
        "currency": body.get("currency") or DEFAULT_CURRENCY,
        "expense_date": expense_date,
        "vendor_name": body.get("vendor_name"),
        "description": body.get("description"),
        "notes": body.get("notes"),
        "compliance_related": bool(body.get("compliance_related", False)),
        "job_id": body.get("job_id"),
        "work_order_id": body.get("work_order_id"),
        "contractor_id": body.get("contractor_id"),
        "requirement_id": body.get("requirement_id"),
        "document_id": body.get("document_id"),
        "created_at": now,
        "updated_at": now,
        "created_by": actor_id,
        "updated_by": actor_id,
        "is_deleted": False,
        "deleted_at": None,
        "deleted_by": None,
    }
    await db[COLLECTION].insert_one(doc)
    await create_audit_log(
        action=AuditAction.PROPERTY_EXPENSE_CREATED,
        actor_role=actor_role,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="property_expense",
        resource_id=expense_id,
        metadata={"property_id": property_id, "category": body["category"], "amount_minor": doc["amount_minor"]},
    )
    return {k: v for k, v in doc.items() if k != "_id"}


async def update_expense(
    expense_id: str,
    client_id: str,
    body: Dict[str, Any],
    actor_id: Optional[str] = None,
    actor_role: Optional[UserRole] = None,
) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db[COLLECTION].find_one(
        {"expense_id": expense_id, "client_id": client_id, "is_deleted": {"$ne": True}},
        {"_id": 0},
    )
    if not doc:
        return None

    updates: Dict[str, Any] = {"updated_at": _now_iso(), "updated_by": actor_id}
    for field in (
        "category",
        "amount_minor",
        "expense_date",
        "vendor_name",
        "description",
        "notes",
        "compliance_related",
        "job_id",
        "work_order_id",
        "contractor_id",
        "requirement_id",
        "document_id",
    ):
        if field in body and body[field] is not None:
            updates[field] = body[field]
    if "amount_minor" in updates:
        updates["amount_minor"] = int(updates["amount_minor"])

    await db[COLLECTION].update_one({"expense_id": expense_id}, {"$set": updates})
    await create_audit_log(
        action=AuditAction.PROPERTY_EXPENSE_UPDATED,
        actor_role=actor_role,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="property_expense",
        resource_id=expense_id,
        metadata={k: v for k, v in body.items() if v is not None},
    )
    updated = await db[COLLECTION].find_one({"expense_id": expense_id}, {"_id": 0})
    return updated


async def delete_expense(
    expense_id: str,
    client_id: str,
    actor_id: Optional[str] = None,
    actor_role: Optional[UserRole] = None,
) -> bool:
    db = database.get_db()
    result = await db[COLLECTION].update_one(
        {"expense_id": expense_id, "client_id": client_id, "is_deleted": {"$ne": True}},
        {"$set": {"is_deleted": True, "deleted_at": _now_iso(), "deleted_by": actor_id, "updated_at": _now_iso()}},
    )
    if result.modified_count == 0:
        return False
    await create_audit_log(
        action=AuditAction.PROPERTY_EXPENSE_DELETED,
        actor_role=actor_role,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="property_expense",
        resource_id=expense_id,
    )
    return True


async def list_expenses(
    client_id: str,
    property_id: Optional[str] = None,
    category: Optional[str] = None,
    compliance_related: Optional[bool] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    if property_id:
        await ensure_property_scope(client_id, property_id)
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id, "is_deleted": {"$ne": True}}
    if property_id:
        q["property_id"] = property_id
    if category:
        q["category"] = category
    if compliance_related is not None:
        q["compliance_related"] = compliance_related
    if from_date or to_date:
        q["expense_date"] = {}
        if from_date:
            q["expense_date"]["$gte"] = from_date
        if to_date:
            q["expense_date"]["$lte"] = to_date

    total = await db[COLLECTION].count_documents(q)
    rows = (
        await db[COLLECTION].find(q, {"_id": 0}).sort("expense_date", -1).skip(skip).limit(limit).to_list(limit)
    )
    return {"expenses": rows, "total": total}


async def get_expense_summary(
    client_id: str,
    property_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    if property_id:
        await ensure_property_scope(client_id, property_id)
    db = database.get_db()
    match: Dict[str, Any] = {"client_id": client_id, "is_deleted": {"$ne": True}}
    if property_id:
        match["property_id"] = property_id
    if from_date or to_date:
        match["expense_date"] = {}
        if from_date:
            match["expense_date"]["$gte"] = from_date
        if to_date:
            match["expense_date"]["$lte"] = to_date

    by_category = await db[COLLECTION].aggregate(
        [
            {"$match": match},
            {"$group": {"_id": "$category", "total_minor": {"$sum": "$amount_minor"}, "count": {"$sum": 1}}},
            {"$sort": {"total_minor": -1}},
        ]
    ).to_list(50)

    compliance_pipeline = [
        {"$match": {**match, "compliance_related": True}},
        {"$group": {"_id": None, "total_minor": {"$sum": "$amount_minor"}, "count": {"$sum": 1}}},
    ]
    compliance = await db[COLLECTION].aggregate(compliance_pipeline).to_list(1)
    compliance_minor = int((compliance[0]["total_minor"] if compliance else 0) or 0)

    total_pipeline = [{"$match": match}, {"$group": {"_id": None, "total_minor": {"$sum": "$amount_minor"}}}]
    total = await db[COLLECTION].aggregate(total_pipeline).to_list(1)
    total_minor = int((total[0]["total_minor"] if total else 0) or 0)

    return {
        "currency": DEFAULT_CURRENCY,
        "total_expenses_minor": total_minor,
        "compliance_related_total_minor": compliance_minor,
        "by_category": [
            {"category": r["_id"], "total_minor": int(r["total_minor"]), "count": int(r["count"])}
            for r in by_category
        ],
    }


async def get_property_financial_snapshot(client_id: str, property_id: str) -> Dict[str, Any]:
    from services import rent_ledger_service

    await _validate_property(database.get_db(), client_id, property_id)
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1).isoformat()
    month_end = today.isoformat()

    rent_summary = await rent_ledger_service.get_rent_summary(client_id, property_id=property_id)
    expense_summary = await get_expense_summary(client_id, property_id=property_id, from_date=month_start, to_date=month_end)

    db = database.get_db()
    schedule = await db.rent_schedules.find_one(
        {"client_id": client_id, "property_id": property_id, "is_active": True},
        {"_id": 0, "expected_amount_minor": 1, "currency": 1},
    )
    expected_monthly_minor = int((schedule or {}).get("expected_amount_minor") or 0)

    collected_minor = rent_summary.get("rent_collected_this_month_minor") or 0
    expenses_minor = expense_summary.get("total_expenses_minor") or 0
    overdue_minor = rent_summary.get("total_outstanding_minor") or 0
    net_operational_minor = collected_minor - expenses_minor

    return {
        "property_id": property_id,
        "currency": DEFAULT_CURRENCY,
        "expected_monthly_rent_minor": expected_monthly_minor,
        "rent_collected_this_month_minor": collected_minor,
        "overdue_balance_minor": overdue_minor,
        "upcoming_due_count": rent_summary.get("upcoming_due_count") or 0,
        "total_expenses_this_month_minor": expenses_minor,
        "compliance_related_expenses_minor": expense_summary.get("compliance_related_total_minor") or 0,
        "estimated_net_operational_minor": net_operational_minor,
        "disclaimer": "Operational estimate only. Not accounting or tax advice.",
    }
