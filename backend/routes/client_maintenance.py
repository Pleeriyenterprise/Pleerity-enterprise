"""
Client API for maintenance work orders. Gated by MAINTENANCE_WORKFLOWS.
List own work orders, create new (client or property manager).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel
from typing import Optional

from database import database
from middleware import client_route_guard
from services import maintenance_service
from services.ops_compliance_feature_flags import get_effective_flags, MAINTENANCE_WORKFLOWS, PREDICTIVE_MAINTENANCE
from services import property_assets_service

router = APIRouter(prefix="/api/client", tags=["client-maintenance"], dependencies=[Depends(client_route_guard)])


class CreateWorkOrderBody(BaseModel):
    property_id: str
    description: str
    category: Optional[str] = None
    severity: Optional[str] = None


async def _require_maintenance_enabled(request: Request):
    """Ensure client has MAINTENANCE_WORKFLOWS enabled."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(MAINTENANCE_WORKFLOWS):
        raise HTTPException(
            status_code=403,
            detail="Maintenance workflows are not enabled for your account",
        )
    return user


@router.get("/maintenance/work-orders")
async def list_my_work_orders(
    request: Request,
    property_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List work orders for the authenticated client. Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    db = database.get_db()
    # Ensure property belongs to client if filter applied
    if property_id:
        prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 1})
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
    result = await maintenance_service.list_work_orders(
        client_id=client_id,
        property_id=property_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return result


@router.post("/maintenance/work-orders")
async def create_work_order(request: Request, body: CreateWorkOrderBody):
    """Create a work order for a property. Requires MAINTENANCE_WORKFLOWS."""
    user = await _require_maintenance_enabled(request)
    client_id = user["client_id"]
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": body.property_id, "client_id": client_id},
        {"_id": 1, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    doc = await maintenance_service.create_work_order(
        client_id=client_id,
        property_id=body.property_id,
        description=body.description,
        source=maintenance_service.SOURCE_CLIENT,
        reporter_id=user.get("portal_user_id"),
        category=body.category,
        severity=body.severity,
    )
    return doc


@router.get("/maintenance/predictive-insights")
async def get_my_predictive_insights(request: Request):
    """Get predictive maintenance insights for the authenticated client's properties. Requires PREDICTIVE_MAINTENANCE."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(PREDICTIVE_MAINTENANCE):
        raise HTTPException(
            status_code=403,
            detail="Predictive maintenance is not enabled for your account",
        )
    from services.predictive_service import get_insights_for_client
    result = await get_insights_for_client(client_id)
    return result


async def _require_predictive_enabled(request: Request):
    """Ensure client has PREDICTIVE_MAINTENANCE enabled."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(PREDICTIVE_MAINTENANCE):
        raise HTTPException(
            status_code=403,
            detail="Predictive maintenance is not enabled for your account",
        )
    return user


@router.get("/maintenance/properties/{property_id}/assets")
async def list_property_assets(request: Request, property_id: str):
    """List assets for a property (e.g. boiler). Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": user["client_id"]}, {"_id": 1})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    items = await property_assets_service.list_assets(property_id, user["client_id"])
    return {"assets": items}


class AddAssetBody(BaseModel):
    asset_type: str
    install_date: Optional[str] = None
    last_service_date: Optional[str] = None
    notes: Optional[str] = None


@router.post("/maintenance/properties/{property_id}/assets")
async def add_property_asset(request: Request, property_id: str, body: AddAssetBody):
    """Add an asset (e.g. boiler) for a property. Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    doc = await property_assets_service.add_asset(
        property_id=property_id,
        client_id=user["client_id"],
        asset_type=body.asset_type,
        install_date=body.install_date,
        last_service_date=body.last_service_date,
        notes=body.notes,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    return doc


@router.get("/maintenance/properties/{property_id}/events")
async def list_property_events(request: Request, property_id: str, limit: int = 50):
    """List maintenance events for a property. Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": user["client_id"]}, {"_id": 1})
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    items = await property_assets_service.list_events(property_id, user["client_id"], limit=limit)
    return {"events": items}


class AddEventBody(BaseModel):
    event_type: str
    occurred_at: Optional[str] = None
    outcome: Optional[str] = None
    asset_id: Optional[str] = None
    notes: Optional[str] = None


@router.post("/maintenance/properties/{property_id}/events")
async def add_property_event(request: Request, property_id: str, body: AddEventBody):
    """Add a maintenance event (e.g. boiler service). Requires PREDICTIVE_MAINTENANCE."""
    user = await _require_predictive_enabled(request)
    doc = await property_assets_service.add_event(
        property_id=property_id,
        client_id=user["client_id"],
        event_type=body.event_type,
        occurred_at=body.occurred_at,
        outcome=body.outcome,
        asset_id=body.asset_id,
        notes=body.notes,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Property not found")
    return doc
