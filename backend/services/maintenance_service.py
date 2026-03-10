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

# Work order status lifecycle (existing + additive)
STATUS_OPEN = "OPEN"
STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_CANCELLED = "CANCELLED"
# Additive statuses (Maintenance Intelligence Flow)
STATUS_DRAFT = "DRAFT"
STATUS_SCHEDULED = "SCHEDULED"
STATUS_AWAITING_PARTS = "AWAITING_PARTS"
STATUS_VERIFIED = "VERIFIED"
STATUS_CLOSED = "CLOSED"

ALL_STATUSES = (
    STATUS_OPEN,
    STATUS_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
    STATUS_DRAFT,
    STATUS_SCHEDULED,
    STATUS_AWAITING_PARTS,
    STATUS_VERIFIED,
    STATUS_CLOSED,
)

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
    asset_id: Optional[str] = None,
    issue_id: Optional[str] = None,
    cost_estimate_min: Optional[float] = None,
    cost_estimate_max: Optional[float] = None,
    initial_status: Optional[str] = None,
    sla_respond_by: Optional[str] = None,
    sla_complete_by: Optional[str] = None,
    use_triage: bool = True,
) -> Dict[str, Any]:
    """Create a work order. source: tenant_request | client | admin.
    Optional: asset_id, issue_id, cost estimates, initial_status (default OPEN), SLA overrides.
    If use_triage is True and severity/sla are not provided, runs triage and applies result (stores reasoning).
    """
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    work_order_id = str(uuid.uuid4())
    sla_respond_hours = 24
    sla_complete_days = 5
    default_respond = (datetime.now(timezone.utc) + timedelta(hours=sla_respond_hours)).isoformat()
    default_complete = (datetime.now(timezone.utc) + timedelta(days=sla_complete_days)).isoformat()
    status = (initial_status or STATUS_OPEN).strip().upper() if initial_status else STATUS_OPEN
    if status not in ALL_STATUSES:
        status = STATUS_OPEN

    triage_reasoning: Optional[List[str]] = None
    recommended_contractor_type: Optional[str] = None
    effective_severity = severity
    effective_respond = sla_respond_by
    effective_complete = sla_complete_by

    if use_triage and (effective_severity is None or effective_respond is None or effective_complete is None):
        try:
            from services.maintenance_triage import triage_maintenance_issue_async
            triage = await triage_maintenance_issue_async(
                description=description,
                category=category or CATEGORY_GENERAL,
                source=source,
                property_id=property_id,
                client_id=client_id,
            )
            if effective_severity is None:
                effective_severity = triage.get("severity") or SEVERITY_MEDIUM
            if effective_respond is None or effective_complete is None:
                sla_hours = triage.get("sla_hours") or 72
                respond_dt = datetime.now(timezone.utc) + timedelta(hours=min(24, sla_hours))
                complete_dt = datetime.now(timezone.utc) + timedelta(hours=sla_hours)
                if effective_respond is None:
                    effective_respond = respond_dt.isoformat()
                if effective_complete is None:
                    effective_complete = complete_dt.isoformat()
            triage_reasoning = triage.get("reasoning") or []
            recommended_contractor_type = triage.get("recommended_contractor_type")
        except Exception as e:
            logger.warning("Triage failed for work order, using defaults: %s", e)

    doc = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": property_id,
        "description": (description or "").strip(),
        "source": source,
        "reporter_id": reporter_id,
        "category": category or CATEGORY_GENERAL,
        "severity": effective_severity or SEVERITY_MEDIUM,
        "status": status,
        "contractor_id": None,
        "created_at": now,
        "updated_at": now,
        "sla_respond_by": effective_respond or default_respond,
        "sla_complete_by": effective_complete or default_complete,
        "completed_at": None,
        "asset_id": asset_id,
        "issue_id": issue_id,
        "cost_estimate_min": cost_estimate_min,
        "cost_estimate_max": cost_estimate_max,
        "resolution_outcome": None,
        "sla_breach_risk_at": None,
        "sla_breached_at": None,
        "triage_reasoning": triage_reasoning,
        "recommended_contractor_type": recommended_contractor_type,
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
    resolution_outcome: Optional[str] = None,
    cost_estimate_min: Optional[float] = None,
    cost_estimate_max: Optional[float] = None,
    assigned_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update work order status, contractor, resolution outcome, and/or cost estimates. When contractor_id is set, records assignment and sets assigned_at."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    update = {"updated_at": now}
    if status is not None:
        status = status.strip().upper()
        if status in ALL_STATUSES:
            update["status"] = status
            if status == STATUS_COMPLETED:
                update["completed_at"] = now
    if contractor_id is not None:
        update["contractor_id"] = contractor_id
        update["assigned_at"] = now
        if status is None:
            existing = await db.work_orders.find_one({"work_order_id": work_order_id}, {"status": 1})
            if existing and existing.get("status") == STATUS_OPEN:
                update["status"] = STATUS_ASSIGNED
    if resolution_outcome is not None:
        update["resolution_outcome"] = resolution_outcome
    if cost_estimate_min is not None:
        update["cost_estimate_min"] = cost_estimate_min
    if cost_estimate_max is not None:
        update["cost_estimate_max"] = cost_estimate_max
    result = await db.work_orders.find_one_and_update(
        {"work_order_id": work_order_id},
        {"$set": update},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
        if contractor_id is not None:
            try:
                await db.contractor_assignments.insert_one({
                    "work_order_id": work_order_id,
                    "contractor_id": contractor_id,
                    "assigned_at": now,
                    "assigned_by": assigned_by,
                })
            except Exception as e:
                logger.warning("Failed to record contractor assignment: %s", e)
            try:
                contractor = await db.contractors.find_one(
                    {"contractor_id": contractor_id},
                    {"_id": 0, "email": 1},
                )
                to_email = (contractor or {}).get("email") if contractor else None
                if to_email and str(to_email).strip():
                    property_address = ""
                    if result.get("property_id") and result.get("client_id"):
                        prop = await db.properties.find_one(
                            {"property_id": result["property_id"], "client_id": result["client_id"]},
                            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1},
                        )
                        if prop:
                            parts = [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")]
                            property_address = ", ".join(p for p in parts if p) or "Property"
                    desc = (result.get("description") or "Work order")[:200]
                    from services.notification_orchestrator import notification_orchestrator
                    await notification_orchestrator.send(
                        template_key="CONTRACTOR_ASSIGNED",
                        client_id=result.get("client_id"),
                        context={
                            "recipient": str(to_email).strip(),
                            "subject": "Work order assignment",
                            "body": f"You have been assigned to work order: {work_order_id}. Description: {desc}. Property: {property_address or 'See portal'}.",
                        },
                        idempotency_key=f"contractor_assign_{work_order_id}_{contractor_id}",
                        event_type="CONTRACTOR_ASSIGNED",
                    )
            except Exception as e:
                logger.warning("Failed to send contractor assignment notification: %s", e)
        if status == STATUS_COMPLETED and result.get("client_id") and result.get("property_id"):
            try:
                from services.predictive_maintenance_service import record_maintenance_event
                await record_maintenance_event(
                    client_id=result["client_id"],
                    property_id=result["property_id"],
                    event_type="repair",
                    asset_id=result.get("asset_id"),
                    notes=f"Work order {work_order_id} completed: {result.get('description', '')[:200]}",
                )
            except Exception as e:
                logger.warning("Failed to record maintenance event for completed work order: %s", e)
            if result.get("asset_id"):
                try:
                    from services.property_assets_service import add_asset_event, ASSET_EVENT_REPAIR_COMPLETED
                    await add_asset_event(
                        asset_id=result["asset_id"],
                        property_id=result["property_id"],
                        client_id=result["client_id"],
                        event_type=ASSET_EVENT_REPAIR_COMPLETED,
                        description=(result.get("description") or "Work completed")[:200],
                        source="work_order",
                        related_work_order_id=work_order_id,
                    )
                except Exception as e:
                    logger.warning("Failed to record asset event for completed work order: %s", e)
            if result.get("contractor_id"):
                try:
                    await _update_contractor_performance_on_completion(db, result)
                except Exception as e:
                    logger.warning("Failed to update contractor performance for completed work order: %s", e)
    return result


async def _update_contractor_performance_on_completion(db, work_order: Dict[str, Any]) -> None:
    """Increment contractor jobs_completed and jobs_on_time when work order is completed. Sync contractor doc (job_count, sla_compliance_rate)."""
    contractor_id = work_order.get("contractor_id")
    client_id = work_order.get("client_id")
    if not contractor_id:
        return
    now = datetime.now(timezone.utc).isoformat()
    completed_at = work_order.get("completed_at")
    sla_complete_by = work_order.get("sla_complete_by")
    on_time = False
    if completed_at and sla_complete_by:
        try:
            c_at = completed_at if isinstance(completed_at, datetime) else datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            s_at = sla_complete_by if isinstance(sla_complete_by, datetime) else datetime.fromisoformat(sla_complete_by.replace("Z", "+00:00"))
            if getattr(c_at, "tzinfo", None) is None:
                c_at = c_at.replace(tzinfo=timezone.utc)
            if getattr(s_at, "tzinfo", None) is None:
                s_at = s_at.replace(tzinfo=timezone.utc)
            on_time = c_at <= s_at
        except Exception:
            pass
    doc = await db.contractor_performance.find_one({"contractor_id": contractor_id, "client_id": client_id or ""})
    if doc:
        await db.contractor_performance.update_one(
            {"contractor_id": contractor_id, "client_id": client_id or ""},
            {
                "$set": {"updated_at": now, "last_used_at": now},
                "$inc": {"jobs_completed": 1, "jobs_on_time": 1 if on_time else 0},
            },
        )
    else:
        await db.contractor_performance.insert_one({
            "contractor_id": contractor_id,
            "client_id": client_id or "",
            "jobs_completed": 1,
            "jobs_on_time": 1 if on_time else 0,
            "created_at": now,
            "updated_at": now,
            "last_used_at": now,
        })
    cursor = db.contractor_performance.find({"contractor_id": contractor_id}, {"_id": 0, "jobs_completed": 1, "jobs_on_time": 1})
    total_jobs = 0
    total_on_time = 0
    async for row in cursor:
        total_jobs += row.get("jobs_completed") or 0
        total_on_time += row.get("jobs_on_time") or 0
    rate = round(total_on_time / total_jobs, 4) if total_jobs else None
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"job_count": total_jobs, "sla_compliance_rate": rate, "updated_at": now}},
    )
    try:
        from services.contractor_service import compute_rework_rate
        await compute_rework_rate(contractor_id, client_id or "")
    except Exception as e:
        logger.warning("Failed to compute rework rate for contractor %s: %s", contractor_id, e)


def _categorise_severity(description: str) -> str:
    """Simple heuristic: keyword-based severity. Can be replaced by AI later."""
    d = (description or "").lower()
    if any(w in d for w in ["leak", "no heat", "no water", "gas smell", "emergency"]):
        return SEVERITY_URGENT
    if any(w in d for w in ["broken", "not working", "fault"]):
        return SEVERITY_HIGH
    return SEVERITY_MEDIUM
