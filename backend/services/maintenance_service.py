"""
Maintenance workflows: work orders (tenant report / client / admin).
Create, list, update, assign contractor. SLA fields optional.
Gated by MAINTENANCE_WORKFLOWS feature flag for client/tenant.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid
from database import database
import logging

logger = logging.getLogger(__name__)

# Work order status lifecycle
STATUS_OPEN = "OPEN"
STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_CANCELLED = "CANCELLED"

SOURCE_TENANT_REQUEST = "tenant_request"
SOURCE_CLIENT = "client"
SOURCE_ADMIN = "admin"

# Categories for rule-based categorisation (optional)
CATEGORY_PLUMBING = "plumbing"
CATEGORY_ELECTRICAL = "electrical"
CATEGORY_HEATING = "heating"
CATEGORY_GENERAL = "general"
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_URGENT = "urgent"


async def create_work_order(
    client_id: str,
    property_id: str,
    description: str,
    source: str = SOURCE_CLIENT,
    reporter_id: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a work order. source: tenant_request | client | admin."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    work_order_id = str(uuid.uuid4())
    # Optional SLA: respond within 24h, complete within 5 days (can be made configurable)
    sla_respond_hours = 24
    sla_complete_days = 5
    doc = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": property_id,
        "description": (description or "").strip(),
        "source": source,
        "reporter_id": reporter_id,
        "category": category or CATEGORY_GENERAL,
        "severity": severity or SEVERITY_MEDIUM,
        "status": STATUS_OPEN,
        "contractor_id": None,
        "created_at": now,
        "updated_at": now,
        "sla_respond_by": (datetime.now(timezone.utc) + timedelta(hours=sla_respond_hours)).isoformat(),
        "sla_complete_by": (datetime.now(timezone.utc) + timedelta(days=sla_complete_days)).isoformat(),
        "completed_at": None,
    }
    await db.work_orders.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_work_orders(
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    contractor_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """List work orders with optional filters."""
    db = database.get_db()
    q = {}
    if client_id is not None:
        q["client_id"] = client_id
    if property_id is not None:
        q["property_id"] = property_id
    if status is not None:
        q["status"] = status
    if contractor_id is not None:
        q["contractor_id"] = contractor_id
    cursor = db.work_orders.find(q).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    for d in items:
        d.pop("_id", None)
    total = await db.work_orders.count_documents(q)
    return {"work_orders": items, "total": total, "skip": skip, "limit": limit}


async def get_work_order(work_order_id: str) -> Optional[Dict[str, Any]]:
    """Get a single work order by id."""
    db = database.get_db()
    doc = await db.work_orders.find_one({"work_order_id": work_order_id})
    if doc:
        doc.pop("_id", None)
    return doc


async def update_work_order(
    work_order_id: str,
    status: Optional[str] = None,
    contractor_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update work order status and/or assign contractor."""
    db = database.get_db()
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if status is not None:
        update["status"] = status
        if status == STATUS_COMPLETED:
            update["completed_at"] = datetime.now(timezone.utc).isoformat()
    if contractor_id is not None:
        update["contractor_id"] = contractor_id
        if status is None:
            # If only assigning, move to ASSIGNED
            existing = await db.work_orders.find_one({"work_order_id": work_order_id}, {"status": 1})
            if existing and existing.get("status") == STATUS_OPEN:
                update["status"] = STATUS_ASSIGNED
    result = await db.work_orders.find_one_and_update(
        {"work_order_id": work_order_id},
        {"$set": update},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
        # Feed predictive: when work order is completed, record a maintenance event
        if status == STATUS_COMPLETED and result.get("client_id") and result.get("property_id"):
            try:
                from services.predictive_maintenance_service import record_maintenance_event
                await record_maintenance_event(
                    client_id=result["client_id"],
                    property_id=result["property_id"],
                    event_type="repair",
                    asset_id=None,
                    notes=f"Work order {work_order_id} completed: {result.get('description', '')[:200]}",
                )
            except Exception as e:
                logger.warning("Failed to record maintenance event for completed work order: %s", e)
    return result


def _categorise_severity(description: str) -> str:
    """Simple heuristic: keyword-based severity. Can be replaced by AI later."""
    d = (description or "").lower()
    if any(w in d for w in ["leak", "no heat", "no water", "gas smell", "emergency"]):
        return SEVERITY_URGENT
    if any(w in d for w in ["broken", "not working", "fault"]):
        return SEVERITY_HIGH
    return SEVERITY_MEDIUM
