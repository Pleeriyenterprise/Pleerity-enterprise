"""
Admin API for predictive maintenance data: property_assets and maintenance_events.
Enables populating data so predictive insights have something to run on.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel
from typing import Optional, List

from database import database
from middleware import admin_route_guard, require_owner_or_admin
from services.property_assets_service import (
    upsert_property_asset,
    record_maintenance_event,
)

router = APIRouter(prefix="/api/admin/ops", tags=["ops-predictive-data"], dependencies=[Depends(admin_route_guard)])


class PropertyAssetBody(BaseModel):
    property_id: str
    client_id: str
    asset_type: str  # boiler, electrical, heating, general
    name: Optional[str] = None
    install_date: Optional[str] = None  # ISO date
    last_service_date: Optional[str] = None
    asset_id: Optional[str] = None


class MaintenanceEventBody(BaseModel):
    client_id: str
    property_id: str
    event_type: str  # repair, inspection, service
    asset_id: Optional[str] = None
    notes: Optional[str] = None


@router.get("/properties/{property_id}/assets")
async def list_property_assets(request: Request, property_id: str):
    """List property assets for a property. Admin only."""
    await admin_route_guard(request)
    db = database.get_db()
    cursor = db.property_assets.find({"property_id": property_id}).sort("asset_type", 1)
    items = await cursor.to_list(100)
    for d in items:
        d.pop("_id", None)
    return {"assets": items}


@router.post("/properties/assets", dependencies=[Depends(require_owner_or_admin)])
async def create_or_update_asset(request: Request, body: PropertyAssetBody):
    """Create or update a property asset for predictive insights. Owner or Admin only."""
    await admin_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": body.property_id, "client_id": body.client_id},
        {"_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found for this client")
    try:
        doc = await upsert_property_asset(
            property_id=body.property_id,
            client_id=body.client_id,
            asset_type=body.asset_type,
            name=body.name,
            install_date=body.install_date,
            last_service_date=body.last_service_date,
            asset_id=body.asset_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return doc


@router.get("/properties/{property_id}/maintenance-events")
async def list_maintenance_events(
    request: Request,
    property_id: str,
    limit: int = Query(50, ge=1, le=200),
):
    """List maintenance events for a property. Admin only."""
    await admin_route_guard(request)
    db = database.get_db()
    cursor = (
        db.maintenance_events.find({"property_id": property_id})
        .sort("occurred_at", -1)
        .limit(limit)
    )
    items = await cursor.to_list(limit)
    for d in items:
        d.pop("_id", None)
    return {"events": items}


@router.post("/maintenance-events", dependencies=[Depends(require_owner_or_admin)])
async def create_maintenance_event(request: Request, body: MaintenanceEventBody):
    """Record a maintenance event (repair, inspection, service) for predictive history. Owner or Admin only."""
    await admin_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": body.property_id, "client_id": body.client_id},
        {"_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found for this client")
    doc = await record_maintenance_event(
        client_id=body.client_id,
        property_id=body.property_id,
        event_type=body.event_type,
        asset_id=body.asset_id,
        notes=body.notes,
    )
    return doc
