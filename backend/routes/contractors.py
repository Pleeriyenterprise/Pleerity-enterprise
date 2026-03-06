"""
Admin API for contractors (Ops & Compliance / Contractor Network).
List, create, update, delete contractors. Optional filter by client_id.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel
from typing import Optional, List

from database import database
from middleware import admin_route_guard, require_owner_or_admin
from services import contractor_service

router = APIRouter(prefix="/api/admin/ops", tags=["ops-contractors"], dependencies=[Depends(admin_route_guard)])


class ContractorCreate(BaseModel):
    name: str
    trade_types: Optional[List[str]] = None
    vetted: bool = False
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_id: Optional[str] = None
    areas_served: Optional[List[str]] = None
    notes: Optional[str] = None


class ContractorUpdate(BaseModel):
    name: Optional[str] = None
    trade_types: Optional[List[str]] = None
    vetted: Optional[bool] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_id: Optional[str] = None
    areas_served: Optional[List[str]] = None
    notes: Optional[str] = None


@router.get("/contractors")
async def list_contractors(
    request: Request,
    client_id: Optional[str] = Query(None, description="Filter by client_id"),
    vetted_only: bool = Query(False, description="Only vetted contractors"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """List contractors. Admin only."""
    await admin_route_guard(request)
    result = await contractor_service.list_contractors(
        client_id=client_id,
        vetted_only=vetted_only,
        skip=skip,
        limit=limit,
    )
    return result


@router.get("/contractors/{contractor_id}")
async def get_contractor(request: Request, contractor_id: str):
    """Get one contractor by id."""
    await admin_route_guard(request)
    doc = await contractor_service.get_contractor(contractor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return doc


@router.post("/contractors", dependencies=[Depends(require_owner_or_admin)])
async def create_contractor(request: Request, body: ContractorCreate):
    """Create a contractor. Owner or Admin only."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can create contractors")
    doc = await contractor_service.create_contractor(
        name=body.name,
        trade_types=body.trade_types,
        vetted=body.vetted,
        email=body.email,
        phone=body.phone,
        company_name=body.company_name,
        client_id=body.client_id,
        areas_served=body.areas_served,
        notes=body.notes,
    )
    return doc


@router.patch("/contractors/{contractor_id}", dependencies=[Depends(require_owner_or_admin)])
async def update_contractor(request: Request, contractor_id: str, body: ContractorUpdate):
    """Update a contractor. Owner or Admin only."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can update contractors")
    doc = await contractor_service.update_contractor(
        contractor_id,
        name=body.name,
        trade_types=body.trade_types,
        vetted=body.vetted,
        email=body.email,
        phone=body.phone,
        company_name=body.company_name,
        client_id=body.client_id,
        areas_served=body.areas_served,
        notes=body.notes,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return doc


@router.delete("/contractors/{contractor_id}", dependencies=[Depends(require_owner_or_admin)])
async def delete_contractor(request: Request, contractor_id: str):
    """Delete a contractor. Owner or Admin only."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can delete contractors")
    deleted = await contractor_service.delete_contractor(contractor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return {"ok": True, "contractor_id": contractor_id}
