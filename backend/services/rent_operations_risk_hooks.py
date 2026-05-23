"""
Advisory operational risk signals from rent/expense data.
Does NOT mutate compliance authority, requirement status, or compliance score.
Uses source=rent_operations so heuristic regen does not delete these.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from database import database
from models.rent_operations import RentLedgerStatus
from utils.audit import create_audit_log
from models import AuditAction

logger = logging.getLogger(__name__)

SOURCE_RENT_OPS = "rent_operations"
STATUS_ACTIVE = "active"
SIGNAL_CATEGORY = "financial_operational"

RISK_RENT_OVERDUE = "RENT_OVERDUE"
RISK_RENT_SEVERELY_OVERDUE = "RENT_SEVERELY_OVERDUE"
RISK_REPEATED_LATE = "REPEATED_LATE_PAYMENT"
RISK_HIGH_EXPENSES = "HIGH_PROPERTY_EXPENSES"
RISK_COMPLIANCE_COST_SPIKE = "COMPLIANCE_COST_SPIKE"
RISK_ARREARS_COMPLIANCE = "ARREARS_PLUS_COMPLIANCE_RISK"

HIGH_EXPENSE_THRESHOLD_MINOR = 500000  # £5,000/month default operational warning
COMPLIANCE_SPIKE_THRESHOLD_MINOR = 200000  # £2,000 compliance expenses/month


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _upsert_signal(
    client_id: str,
    property_id: str,
    risk_type: str,
    description: str,
    risk_level: str = "medium",
) -> bool:
    db = database.get_db()
    stable_key = f"{risk_type}_{property_id}"
    existing = await db.risk_signals.find_one(
        {
            "client_id": client_id,
            "property_id": property_id,
            "risk_type": risk_type,
            "source": SOURCE_RENT_OPS,
            "status": STATUS_ACTIVE,
        },
        {"_id": 1},
    )
    if existing:
        await db.risk_signals.update_one(
            {"_id": existing["_id"]},
            {"$set": {"description": description, "generated_at": _now_iso(), "updated_at": _now_iso()}},
        )
        return False

    signal_id = f"rs_{uuid.uuid4().hex[:12]}"
    doc = {
        "signal_id": signal_id,
        "client_id": client_id,
        "property_id": property_id,
        "asset_id": None,
        "signal_category": SIGNAL_CATEGORY,
        "risk_type": risk_type,
        "risk_level": risk_level,
        "description": description,
        "suggested_actions": ["Review rent ledger and follow up with tenant", "Record payments when received"],
        "trend": "stable",
        "score": None,
        "reasons": [description],
        "recommended_action": "Review operational rent position for this property",
        "status": STATUS_ACTIVE,
        "source": SOURCE_RENT_OPS,
        "stable_key": stable_key,
        "generated_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await db.risk_signals.insert_one(doc)
    await create_audit_log(
        action=AuditAction.RISK_SIGNAL_CREATED,
        client_id=client_id,
        resource_type="risk_signal",
        resource_id=signal_id,
        metadata={"risk_type": risk_type, "source": SOURCE_RENT_OPS, "property_id": property_id},
    )
    return True


async def _clear_resolved_signals(client_id: str, property_id: str, active_types: List[str]) -> int:
    db = database.get_db()
    q = {
        "client_id": client_id,
        "property_id": property_id,
        "source": SOURCE_RENT_OPS,
        "status": STATUS_ACTIVE,
    }
    if active_types:
        q["risk_type"] = {"$nin": active_types}
    else:
        q["risk_type"] = {"$exists": True}
    result = await db.risk_signals.update_many(
        q,
        {"$set": {"status": "resolved", "resolved_at": _now_iso(), "updated_at": _now_iso()}},
    )
    return int(result.modified_count)


async def generate_operational_risk_signals_for_property(client_id: str, property_id: str) -> Dict[str, Any]:
    db = database.get_db()
    active_types: List[str] = []
    created = 0

    overdue = await db.rent_ledger_periods.count_documents(
        {
            "client_id": client_id,
            "property_id": property_id,
            "is_deleted": {"$ne": True},
            "status": RentLedgerStatus.OVERDUE.value,
        }
    )
    if overdue:
        active_types.append(RISK_RENT_OVERDUE)
        if await _upsert_signal(
            client_id,
            property_id,
            RISK_RENT_OVERDUE,
            f"{overdue} rent period(s) overdue",
            "medium",
        ):
            created += 1

    severe = await db.rent_ledger_periods.count_documents(
        {
            "client_id": client_id,
            "property_id": property_id,
            "is_deleted": {"$ne": True},
            "status": RentLedgerStatus.SEVERELY_OVERDUE.value,
        }
    )
    if severe:
        active_types.append(RISK_RENT_SEVERELY_OVERDUE)
        if await _upsert_signal(
            client_id,
            property_id,
            RISK_RENT_SEVERELY_OVERDUE,
            f"{severe} rent period(s) severely overdue (14+ days)",
            "high",
        ):
            created += 1

    late_count = await db.rent_ledger_periods.count_documents(
        {
            "client_id": client_id,
            "property_id": property_id,
            "is_deleted": {"$ne": True},
            "status": RentLedgerStatus.PAID.value,
            "days_overdue": {"$gte": 7},
        }
    )
    if late_count >= 2:
        active_types.append(RISK_REPEATED_LATE)
        if await _upsert_signal(
            client_id,
            property_id,
            RISK_REPEATED_LATE,
            f"{late_count} periods paid more than 7 days late",
            "medium",
        ):
            created += 1

    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1).isoformat()
    expense_pipeline = [
        {
            "$match": {
                "client_id": client_id,
                "property_id": property_id,
                "is_deleted": {"$ne": True},
                "expense_date": {"$gte": month_start},
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount_minor"}}},
    ]
    exp = await db.property_expenses.aggregate(expense_pipeline).to_list(1)
    expense_total = int((exp[0]["total"] if exp else 0) or 0)
    if expense_total >= HIGH_EXPENSE_THRESHOLD_MINOR:
        active_types.append(RISK_HIGH_EXPENSES)
        if await _upsert_signal(
            client_id,
            property_id,
            RISK_HIGH_EXPENSES,
            f"Property expenses this month exceed operational threshold (£{expense_total / 100:.2f})",
            "medium",
        ):
            created += 1

    compliance_pipeline = [
        {
            "$match": {
                "client_id": client_id,
                "property_id": property_id,
                "is_deleted": {"$ne": True},
                "compliance_related": True,
                "expense_date": {"$gte": month_start},
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$amount_minor"}}},
    ]
    comp = await db.property_expenses.aggregate(compliance_pipeline).to_list(1)
    comp_total = int((comp[0]["total"] if comp else 0) or 0)
    if comp_total >= COMPLIANCE_SPIKE_THRESHOLD_MINOR:
        active_types.append(RISK_COMPLIANCE_COST_SPIKE)
        if await _upsert_signal(
            client_id,
            property_id,
            RISK_COMPLIANCE_COST_SPIKE,
            f"Compliance-related expenses elevated this month (£{comp_total / 100:.2f})",
            "medium",
        ):
            created += 1

    if (overdue or severe) and comp_total > 0:
        open_req = await db.requirements.count_documents(
            {
                "client_id": client_id,
                "property_id": property_id,
                "status": {"$in": ["overdue", "expired", "missing", "failed"]},
            }
        )
        if open_req:
            active_types.append(RISK_ARREARS_COMPLIANCE)
            if await _upsert_signal(
                client_id,
                property_id,
                RISK_ARREARS_COMPLIANCE,
                "Rent arrears combined with open compliance requirements — advisory operational warning only",
                "high",
            ):
                created += 1

    cleared = await _clear_resolved_signals(client_id, property_id, active_types)
    return {"created": created, "cleared": cleared, "active_types": active_types}


async def generate_operational_risk_signals(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    properties = await db.properties.find({"client_id": client_id}, {"_id": 0, "property_id": 1}).to_list(5000)
    total_created = 0
    for p in properties:
        r = await generate_operational_risk_signals_for_property(client_id, p["property_id"])
        total_created += r.get("created", 0)
    return {"properties_processed": len(properties), "signals_created": total_created}
