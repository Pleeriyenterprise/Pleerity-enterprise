"""
Property assets and maintenance events for predictive maintenance.
Assets: boiler, electrical, etc. with install_date, last_service_date.
Events: repair, inspection, service with occurred_at and outcome.
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


async def add_asset(
    property_id: str,
    client_id: str,
    asset_type: str,
    install_date: Optional[str] = None,
    last_service_date: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a property asset. Verifies property belongs to client."""
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
    if not prop:
        return None
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
