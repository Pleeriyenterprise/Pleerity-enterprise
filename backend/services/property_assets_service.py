"""
Property assets and maintenance events for predictive maintenance.
Assets: boiler, electrical, etc. with install_date, last_service_date.
Events: repair, inspection, service with occurred_at and outcome.
Extended: status, make, model, installed_year, age_estimate, metadata; default assets on provisioning.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from database import database
import logging

logger = logging.getLogger(__name__)

EVENT_TYPE_REPAIR = "repair"
EVENT_TYPE_INSPECTION = "inspection"
EVENT_TYPE_SERVICE = "service"

# Default asset types created during property provisioning (idempotent).
DEFAULT_ASSET_TYPES_ALL = [
    "electrical_installation",
    "roof",
    "plumbing",
    "windows_doors",
    "damp_moisture",
    "smoke_co_alarm",
]
DEFAULT_ASSET_TYPES_IF_GAS = ["boiler", "heating_system"]

ASSET_STATUS_ACTIVE = "active"
ASSET_STATUS_INACTIVE = "inactive"
ASSET_STATUS_REPLACED = "replaced"
ASSET_STATUS_REMOVED = "removed"
ASSET_STATUS_VALUES = (ASSET_STATUS_ACTIVE, ASSET_STATUS_INACTIVE, ASSET_STATUS_REPLACED, ASSET_STATUS_REMOVED)


async def list_assets(property_id: str, client_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List property assets. If client_id given, verify property belongs to client."""
    db = database.get_db()
    q = {"property_id": property_id}
    if client_id:
        prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
        if not prop:
            return []
    cursor = db.property_assets.find(q).sort("asset_type", 1)
    items = await cursor.to_list(100)
    for d in items:
        d.pop("_id", None)
    return items


async def _per_asset_map(
    db,
    property_id: str,
    asset_ids: List[str],
    insights_list: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Build per-asset open_issues count and risk from insights. Returns { asset_id: { open_issues, risk } }."""
    out = {aid: {"open_issues": 0, "risk": None} for aid in asset_ids}
    if not asset_ids:
        return out
    # Open issues per asset
    pipeline = [
        {"$match": {"property_id": property_id, "asset_id": {"$in": asset_ids}, "status": {"$in": ["OPEN", "OPENED", "PENDING", "TRIAGED"]}}},
        {"$group": {"_id": "$asset_id", "count": {"$sum": 1}}},
    ]
    async for doc in db.maintenance_issues.aggregate(pipeline):
        aid = doc.get("_id")
        if aid and aid in out:
            out[aid]["open_issues"] = doc.get("count", 0)
    # Risk from insights (last/highest risk per asset)
    for i in insights_list:
        aid = i.get("asset_id")
        if aid and aid in out:
            r = (i.get("risk") or "").lower()
            if r in ("high", "urgent", "medium", "low"):
                out[aid]["risk"] = r
    return out


async def ensure_default_assets_for_property(client_id: str, property_id: str) -> None:
    """
    Create default assets for a property if they do not exist (idempotent).
    Call after property create/update (e.g. from provisioning status hook).
    """
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "has_gas_supply": 1},
    )
    if not prop:
        return
    types_to_ensure = list(DEFAULT_ASSET_TYPES_ALL)
    if prop.get("has_gas_supply"):
        types_to_ensure.extend(DEFAULT_ASSET_TYPES_IF_GAS)
    for asset_type in types_to_ensure:
        existing = await db.property_assets.find_one(
            {"property_id": property_id, "asset_type": asset_type}
        )
        if not existing:
            await add_asset(
                property_id=property_id,
                client_id=client_id,
                asset_type=asset_type,
                install_date=None,
                last_service_date=None,
                notes=None,
                status=ASSET_STATUS_ACTIVE,
            )
            logger.debug("Created default asset property_id=%s asset_type=%s", property_id, asset_type)


async def get_asset(
    property_id: str,
    asset_id: str,
    client_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get a single asset by property_id and asset_id. If client_id given, verify property belongs to client."""
    db = database.get_db()
    q = {"property_id": property_id, "asset_id": asset_id}
    if client_id:
        prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
        if not prop:
            return None
    doc = await db.property_assets.find_one(q)
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


async def update_asset(
    property_id: str,
    asset_id: str,
    client_id: str,
    name: Optional[str] = None,
    status: Optional[str] = None,
    last_service_date: Optional[str] = None,
    make: Optional[str] = None,
    model: Optional[str] = None,
    installed_year: Optional[int] = None,
    age_estimate: Optional[int] = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Update an asset. Only provided fields are updated. Verifies property belongs to client."""
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        return None
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if name is not None:
        update["name"] = (name or "").strip() or None
    if status is not None:
        update["status"] = status.lower() if status.lower() in ASSET_STATUS_VALUES else ASSET_STATUS_ACTIVE
    if last_service_date is not None:
        update["last_service_date"] = last_service_date
    if make is not None:
        update["make"] = (make or "").strip() or None
    if model is not None:
        update["model"] = (model or "").strip() or None
    if installed_year is not None:
        update["installed_year"] = installed_year
    if age_estimate is not None:
        update["age_estimate"] = age_estimate
    if notes is not None:
        update["notes"] = (notes or "").strip() or None
    if metadata is not None:
        update["metadata"] = metadata
    result = await db.property_assets.find_one_and_update(
        {"property_id": property_id, "asset_id": asset_id},
        {"$set": update},
        return_document=True,
    )
    if not result:
        return None
    result.pop("_id", None)
    return result


async def get_assets_summary(
    property_id: str,
    client_id: str,
    assets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute summary counts for the assets list: total, with_open_issues, with_elevated_risk,
    recent_work_orders, with_compliance_linkage.
    with_compliance_linkage is 0 until evidence->asset linking is implemented.
    """
    db = database.get_db()
    total = len(assets)
    asset_ids = [a.get("asset_id") for a in assets if a.get("asset_id")]

    open_issues = 0
    if asset_ids:
        cursor = db.maintenance_issues.find(
            {
                "property_id": property_id,
                "asset_id": {"$in": asset_ids},
                "status": {"$in": ["OPEN", "OPENED", "PENDING", "TRIAGED"]},
            },
            {"asset_id": 1},
        )
        seen = set()
        async for d in cursor:
            aid = d.get("asset_id")
            if aid:
                seen.add(aid)
        open_issues = len(seen)

    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    recent_wo = 0
    if asset_ids:
        recent_wo = await db.work_orders.count_documents({
            "property_id": property_id,
            "asset_id": {"$in": asset_ids},
            "created_at": {"$gte": cutoff},
        })

    with_elevated_risk = 0
    insights_list = []
    try:
        from services.predictive_maintenance_service import get_insights_for_property
        insights_list = await get_insights_for_property(property_id, client_id)
        risk_asset_ids = {i.get("asset_id") for i in insights_list if i.get("asset_id") and (i.get("risk") or "").lower() in ("high", "urgent")}
        with_elevated_risk = sum(1 for a in assets if a.get("asset_id") in risk_asset_ids)
    except Exception:
        pass

    return {
        "total": total,
        "with_open_issues": open_issues,
        "with_elevated_risk": with_elevated_risk,
        "recent_work_orders": recent_wo,
        "with_compliance_linkage": 0,
        "per_asset": await _per_asset_map(db, property_id, asset_ids, insights_list),
    }


async def add_asset(
    property_id: str,
    client_id: str,
    asset_type: str,
    install_date: Optional[str] = None,
    last_service_date: Optional[str] = None,
    notes: Optional[str] = None,
    name: Optional[str] = None,
    status: Optional[str] = None,
    make: Optional[str] = None,
    model: Optional[str] = None,
    installed_year: Optional[int] = None,
    age_estimate: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Add a property asset. Verifies property belongs to client."""
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        return None
    if status and status.lower() not in ASSET_STATUS_VALUES:
        status = ASSET_STATUS_ACTIVE
    asset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "asset_id": asset_id,
        "property_id": property_id,
        "client_id": client_id,
        "asset_type": (asset_type or "general").strip().lower(),
        "install_date": install_date,
        "last_service_date": last_service_date,
        "notes": (notes or "").strip() or None,
        "name": (name or "").strip() or None,
        "status": (status or ASSET_STATUS_ACTIVE).lower() if status else ASSET_STATUS_ACTIVE,
        "make": (make or "").strip() or None,
        "model": (model or "").strip() or None,
        "installed_year": installed_year,
        "age_estimate": age_estimate,
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
    }
    await db.property_assets.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_events(property_id: str, client_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List maintenance events for a property. If client_id given, verify property belongs to client."""
    db = database.get_db()
    q = {"property_id": property_id}
    if client_id:
        prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
        if not prop:
            return []
    cursor = db.maintenance_events.find(q).sort("occurred_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    for d in items:
        d.pop("_id", None)
    return items


# Asset events (task schema: issue_created, repair_completed, inspection_completed, document_linked, risk_signal_updated)
ASSET_EVENT_ISSUE_CREATED = "issue_created"
ASSET_EVENT_REPAIR_COMPLETED = "repair_completed"
ASSET_EVENT_INSPECTION_COMPLETED = "inspection_completed"
ASSET_EVENT_DOCUMENT_LINKED = "document_linked"
ASSET_EVENT_RISK_SIGNAL_UPDATED = "risk_signal_updated"

# Map requirement_type (catalog code) to asset_type for evidence→asset linking
REQUIREMENT_TYPE_TO_ASSET_TYPE = {
    "gas_safety": "boiler",
    "eicr": "electrical_installation",
}

# Map issue category / keywords to asset_type for auto-linking (first match wins)
CATEGORY_TO_ASSET_TYPE = [
    ("heating", "boiler"),
    ("boiler", "boiler"),
    ("electrical", "electrical_installation"),
    ("plumbing", "plumbing"),
    ("leak", "plumbing"),
    ("roof", "roof"),
    ("damp", "damp_moisture"),
    ("moisture", "damp_moisture"),
    ("smoke", "smoke_co_alarm"),
    ("alarm", "smoke_co_alarm"),
]


async def list_asset_events(
    asset_id: str,
    property_id: str,
    client_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List events for an asset. If client_id given, verify property belongs to client."""
    db = database.get_db()
    q = {"asset_id": asset_id, "property_id": property_id}
    if client_id:
        prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
        if not prop:
            return []
    cursor = db.asset_events.find(q).sort("timestamp", -1).limit(limit)
    items = await cursor.to_list(limit)
    for d in items:
        d.pop("_id", None)
    return items


async def add_asset_event(
    asset_id: str,
    property_id: str,
    client_id: str,
    event_type: str,
    description: Optional[str] = None,
    source: Optional[str] = None,
    related_issue_id: Optional[str] = None,
    related_work_order_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Append an event to asset history. Verifies property belongs to client."""
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        return None
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    ts = timestamp or now
    doc = {
        "event_id": event_id,
        "asset_id": asset_id,
        "property_id": property_id,
        "client_id": client_id,
        "event_type": (event_type or "").strip().lower(),
        "description": (description or "").strip() or None,
        "source": (source or "").strip() or None,
        "related_issue_id": related_issue_id,
        "related_work_order_id": related_work_order_id,
        "timestamp": ts,
        "created_at": now,
    }
    await db.asset_events.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def update_asset_last_service_from_requirement(
    property_id: str,
    client_id: str,
    requirement_type: str,
    last_service_date: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Optional[str]:
    """
    When evidence is confirmed (e.g. Gas Safety, EICR), update the matching asset's last_service_date
    and write a document_linked asset event. Returns asset_id if updated, else None.
    """
    if not requirement_type:
        return None
    rt = (requirement_type or "").strip().lower()
    asset_type = REQUIREMENT_TYPE_TO_ASSET_TYPE.get(rt)
    if not asset_type:
        return None
    db = database.get_db()
    asset = await db.property_assets.find_one(
        {"property_id": property_id, "client_id": client_id, "asset_type": asset_type},
        {"_id": 0, "asset_id": 1},
    )
    if not asset:
        return None
    asset_id = asset.get("asset_id")
    if not asset_id or not last_service_date:
        return asset_id
    now = datetime.now(timezone.utc).isoformat()
    await db.property_assets.update_one(
        {"property_id": property_id, "asset_id": asset_id},
        {"$set": {"last_service_date": last_service_date, "updated_at": now}},
    )
    await add_asset_event(
        asset_id=asset_id,
        property_id=property_id,
        client_id=client_id,
        event_type=ASSET_EVENT_DOCUMENT_LINKED,
        description=f"Certificate confirmed: {rt}",
        source="evidence",
        timestamp=now,
    )
    logger.debug("Updated asset last_service_date property_id=%s asset_id=%s requirement_type=%s", property_id, asset_id, rt)
    return asset_id


async def infer_asset_id_from_category(
    property_id: str,
    client_id: str,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[str]:
    """
    Infer an asset_id for this property from issue category or description keywords.
    Returns the first matching asset's asset_id, or None. User can override when creating issue.
    """
    text = " ".join(
        filter(None, [(category or "").strip().lower(), (description or "").strip().lower()])
    )
    if not text:
        return None
    db = database.get_db()
    for keyword, asset_type in CATEGORY_TO_ASSET_TYPE:
        if keyword in text:
            asset = await db.property_assets.find_one(
                {"property_id": property_id, "client_id": client_id, "asset_type": asset_type},
                {"_id": 0, "asset_id": 1},
            )
            if asset and asset.get("asset_id"):
                return asset["asset_id"]
    return None


async def list_asset_events_for_property(
    property_id: str,
    client_id: str,
    limit: int = 100,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all asset events for a property (for timeline merge)."""
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        return []
    q = {"property_id": property_id, "client_id": client_id}
    if from_date or to_date:
        q["timestamp"] = {}
        if from_date:
            q["timestamp"]["$gte"] = from_date
        if to_date:
            q["timestamp"]["$lte"] = to_date
    cursor = db.asset_events.find(q).sort("timestamp", -1).limit(limit)
    items = await cursor.to_list(limit)
    for d in items:
        d.pop("_id", None)
    return items


async def add_event(
    property_id: str,
    client_id: str,
    event_type: str,
    occurred_at: Optional[str] = None,
    outcome: Optional[str] = None,
    asset_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a maintenance event (e.g. boiler service, repair). Verifies property belongs to client."""
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        return None
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    at = occurred_at or now
    doc = {
        "event_id": event_id,
        "property_id": property_id,
        "client_id": client_id,
        "event_type": (event_type or EVENT_TYPE_SERVICE).strip().lower(),
        "occurred_at": at,
        "outcome": (outcome or "").strip() or None,
        "asset_id": asset_id,
        "notes": (notes or "").strip() or None,
        "created_at": now,
    }
    await db.maintenance_events.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def upsert_property_asset(
    property_id: str,
    client_id: str,
    asset_type: str,
    name: Optional[str] = None,
    install_date: Optional[str] = None,
    last_service_date: Optional[str] = None,
    asset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update a property asset (admin / data for predictive)."""
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        raise ValueError("Property not found for this client")
    now = datetime.now(timezone.utc).isoformat()
    if asset_id:
        doc = await db.property_assets.find_one({"asset_id": asset_id, "property_id": property_id})
        if doc:
            update = {"updated_at": now, "asset_type": (asset_type or "general").strip().lower()}
            if name is not None:
                update["name"] = name
            if install_date is not None:
                update["install_date"] = install_date
            if last_service_date is not None:
                update["last_service_date"] = last_service_date
            await db.property_assets.update_one(
                {"asset_id": asset_id, "property_id": property_id},
                {"$set": update},
            )
            doc.update(update)
            doc.pop("_id", None)
            return doc
    aid = asset_id or str(uuid.uuid4())
    doc = {
        "asset_id": aid,
        "property_id": property_id,
        "client_id": client_id,
        "asset_type": (asset_type or "general").strip().lower(),
        "name": (name or "").strip() or None,
        "install_date": install_date,
        "last_service_date": last_service_date,
        "status": ASSET_STATUS_ACTIVE,
        "created_at": now,
        "updated_at": now,
    }
    await db.property_assets.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def record_maintenance_event(
    client_id: str,
    property_id: str,
    event_type: str,
    asset_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a maintenance event (admin / data for predictive). Uses current time as occurred_at."""
    return await add_event(
        property_id=property_id,
        client_id=client_id,
        event_type=event_type,
        occurred_at=None,
        outcome=None,
        asset_id=asset_id,
        notes=notes,
    )
