"""
Maintenance issues: create, list, get, triage, and create work order from issue.
Gated by MAINTENANCE_WORKFLOWS. Additive to direct work order creation.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid

from database import database

from services.maintenance_triage import triage_maintenance_issue_async
from services import maintenance_service

logger = __import__("logging").getLogger(__name__)

# Issue status lifecycle
STATUS_NEW = "new"
STATUS_TRIAGED = "triaged"
STATUS_MONITORING = "monitoring"
STATUS_READY_FOR_WORK_ORDER = "ready_for_work_order"
STATUS_CLOSED = "closed"

SOURCE_TENANT = "tenant"
SOURCE_CLIENT = "client"
SOURCE_ADMIN = "admin"


async def create_issue(
    client_id: str,
    property_id: str,
    description: str,
    source: str = SOURCE_CLIENT,
    category: Optional[str] = None,
    asset_id: Optional[str] = None,
    reporter_name: Optional[str] = None,
    reporter_contact: Optional[str] = None,
    reported_urgency: Optional[str] = None,
    photos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a maintenance issue and run triage. Returns issue doc with triage result embedded."""
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 1, "property_id": 1},
    )
    if not prop:
        raise ValueError("Property not found for this client")

    if asset_id is None:
        try:
            from services.property_assets_service import infer_asset_id_from_category
            inferred = await infer_asset_id_from_category(property_id, client_id, category, description)
            if inferred:
                asset_id = inferred
        except Exception as e:
            logger.debug("Auto-link asset from category skip: %s", e)

    issue_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    triage = await triage_maintenance_issue_async(
        description=description,
        category=category or maintenance_service.CATEGORY_GENERAL,
        source=source,
        property_id=property_id,
        client_id=client_id,
        reported_urgency=reported_urgency,
        asset_id=asset_id,
    )

    doc = {
        "issue_id": issue_id,
        "client_id": client_id,
        "property_id": property_id,
        "asset_id": asset_id,
        "source": source,
        "category": category or maintenance_service.CATEGORY_GENERAL,
        "description": (description or "").strip(),
        "photos": photos or [],
        "reporter_name": (reporter_name or "").strip() or None,
        "reporter_contact": (reporter_contact or "").strip() or None,
        "reported_urgency": (reported_urgency or "").strip() or None,
        "severity": triage.get("severity"),
        "priority_score": triage.get("priority_score"),
        "status": STATUS_TRIAGED,
        "recurrence_flag": triage.get("recurrence_flag", False),
        "created_at": now,
        "updated_at": now,
        "triage": {
            "severity": triage.get("severity"),
            "priority_score": triage.get("priority_score"),
            "sla_hours": triage.get("sla_hours"),
            "recommended_contractor_type": triage.get("recommended_contractor_type"),
            "reasoning": triage.get("reasoning", []),
        },
    }
    await db.maintenance_issues.insert_one(doc)
    doc.pop("_id", None)
    if asset_id:
        try:
            from services.property_assets_service import add_asset_event, ASSET_EVENT_ISSUE_CREATED
            await add_asset_event(
                asset_id=asset_id,
                property_id=property_id,
                client_id=client_id,
                event_type=ASSET_EVENT_ISSUE_CREATED,
                description=(description or "")[:200] or None,
                source=source,
                related_issue_id=issue_id,
            )
        except Exception as e:
            logger.debug("Asset event issue_created skip: %s", e)
    return doc


async def list_issues(
    client_id: str,
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    asset_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """List issues for a client with optional filters."""
    db = database.get_db()
    q = {"client_id": client_id}
    if property_id is not None:
        q["property_id"] = property_id
    if status is not None:
        q["status"] = status
    if category is not None:
        q["category"] = category
    if severity is not None:
        q["severity"] = severity
    if source is not None:
        q["source"] = source
    if asset_id is not None:
        q["asset_id"] = asset_id
    if from_date or to_date:
        q["created_at"] = {}
        if from_date:
            q["created_at"]["$gte"] = from_date + "T00:00:00.000Z" if "T" not in from_date else from_date
        if to_date:
            q["created_at"]["$lte"] = to_date + "T23:59:59.999Z" if "T" not in to_date else to_date
    cursor = db.maintenance_issues.find(q).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    for d in items:
        d.pop("_id", None)
    total = await db.maintenance_issues.count_documents(q)
    return {"issues": items, "total": total, "skip": skip, "limit": limit}


async def get_issue(issue_id: str, client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get a single issue by id. If client_id provided, ensure issue belongs to client."""
    db = database.get_db()
    q = {"issue_id": issue_id}
    if client_id is not None:
        q["client_id"] = client_id
    doc = await db.maintenance_issues.find_one(q)
    if doc:
        doc.pop("_id", None)
    return doc


async def create_work_order_from_issue(
    issue_id: str,
    client_id: str,
    reporter_id: Optional[str] = None,
    initial_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a work order from an issue; links issue_id to the work order."""
    issue = await get_issue(issue_id, client_id=client_id)
    if not issue:
        raise ValueError("Issue not found")
    if issue.get("status") == STATUS_CLOSED:
        raise ValueError("Cannot create work order from closed issue")

    triage = issue.get("triage") or {}
    sla_hours = triage.get("sla_hours") or 72
    respond_dt = datetime.now(timezone.utc) + timedelta(hours=min(24, sla_hours))
    complete_dt = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

    doc = await maintenance_service.create_work_order(
        client_id=client_id,
        property_id=issue["property_id"],
        description=issue["description"],
        source=maintenance_service.SOURCE_CLIENT,
        reporter_id=reporter_id,
        category=issue.get("category"),
        severity=issue.get("severity"),
        asset_id=issue.get("asset_id"),
        issue_id=issue_id,
        initial_status=initial_status or maintenance_service.STATUS_OPEN,
        sla_respond_by=respond_dt.isoformat(),
        sla_complete_by=complete_dt.isoformat(),
        use_triage=False,
    )
    doc["triage_reasoning"] = triage.get("reasoning", [])
    doc["recommended_contractor_type"] = triage.get("recommended_contractor_type")

    # Mark issue as ready_for_work_order
    db = database.get_db()
    await db.maintenance_issues.update_one(
        {"issue_id": issue_id, "client_id": client_id},
        {"$set": {"status": STATUS_READY_FOR_WORK_ORDER, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return doc
