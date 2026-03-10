"""
Admin API for maintenance work orders (Ops & Compliance).
List, get, update, assign contractor. Owner/Admin for write.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel
from typing import Optional, List

from database import database
from middleware import admin_route_guard, require_owner_or_admin
from services import maintenance_service
from services import contractor_service

router = APIRouter(prefix="/api/admin/ops", tags=["ops-maintenance"], dependencies=[Depends(admin_route_guard)])


class WorkOrderCreateBody(BaseModel):
    client_id: str
    property_id: str
    description: str
    category: Optional[str] = None
    severity: Optional[str] = None
    asset_id: Optional[str] = None
    issue_id: Optional[str] = None
    cost_estimate_min: Optional[float] = None
    cost_estimate_max: Optional[float] = None


class WorkOrderUpdateBody(BaseModel):
    status: Optional[str] = None
    contractor_id: Optional[str] = None
    resolution_outcome: Optional[str] = None
    cost_estimate_min: Optional[float] = None
    cost_estimate_max: Optional[float] = None


@router.post("/work-orders", dependencies=[Depends(require_owner_or_admin)])
async def create_work_order(request: Request, body: WorkOrderCreateBody):
    """Create a work order (admin). Owner or Admin only."""
    await admin_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": body.property_id, "client_id": body.client_id},
        {"_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found for this client")
    doc = await maintenance_service.create_work_order(
        client_id=body.client_id,
        property_id=body.property_id,
        description=body.description,
        source=maintenance_service.SOURCE_ADMIN,
        reporter_id=None,
        category=body.category,
        severity=body.severity,
        asset_id=body.asset_id,
        issue_id=body.issue_id,
        cost_estimate_min=body.cost_estimate_min,
        cost_estimate_max=body.cost_estimate_max,
    )
    return doc


@router.get("/work-orders")
async def list_work_orders(
    request: Request,
    client_id: Optional[str] = Query(None),
    property_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    contractor_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """List work orders. Admin only."""
    await admin_route_guard(request)
    result = await maintenance_service.list_work_orders(
        client_id=client_id,
        property_id=property_id,
        status=status,
        contractor_id=contractor_id,
        skip=skip,
        limit=limit,
    )
    return result


@router.get("/work-orders/{work_order_id}")
async def get_work_order(request: Request, work_order_id: str):
    """Get one work order by id."""
    await admin_route_guard(request)
    doc = await maintenance_service.get_work_order(work_order_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Work order not found")
    return doc


@router.get("/work-orders/{work_order_id}/recommend-contractors")
async def recommend_contractors(request: Request, work_order_id: str, limit: int = Query(10, ge=1, le=50)):
    """Get suggested contractors for this work order (by trade match and performance). No auto-assign."""
    await admin_route_guard(request)
    wo = await maintenance_service.get_work_order(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    result = await contractor_service.recommend_contractors_for_work_order(
        work_order_id=work_order_id,
        client_id=wo.get("client_id"),
        limit=limit,
    )
    return result


@router.patch("/work-orders/{work_order_id}", dependencies=[Depends(require_owner_or_admin)])
async def update_work_order(request: Request, work_order_id: str, body: WorkOrderUpdateBody):
    """Update work order status and/or assign contractor. Owner or Admin only."""
    await admin_route_guard(request)
    user = getattr(request.state, "user", None) or {}
    assigned_by = (body.contractor_id and (user.get("email") or user.get("portal_user_id") or user.get("user_id"))) or None
    doc = await maintenance_service.update_work_order(
        work_order_id,
        status=body.status,
        contractor_id=body.contractor_id,
        resolution_outcome=body.resolution_outcome,
        cost_estimate_min=body.cost_estimate_min,
        cost_estimate_max=body.cost_estimate_max,
        assigned_by=assigned_by,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Work order not found")
    return doc
