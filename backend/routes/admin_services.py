"""
Canonical Admin Services API – /api/admin/services

Task requirement: GET /api/admin/services, GET /api/admin/services/:service_code,
POST /api/admin/services, PUT /api/admin/services/:service_code,
PATCH /api/admin/services/:service_code/activate, PATCH /api/admin/services/:service_code/deactivate.

Delegates to service_catalogue_v2. Register this router so /api/admin/services/*
is handled here; /api/admin/services/v2/* is handled by admin_services_v2.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from middleware import admin_route_guard
from services.service_catalogue_v2 import (
    service_catalogue_v2,
    ServiceCategory,
)
from routes.admin_services_v2 import (
    CreateServiceRequest,
    UpdateServiceRequest,
    create_service_impl,
    update_service_impl,
)

router = APIRouter(prefix="/api/admin/services", tags=["admin-services"])


@router.get("")
async def list_services(
    category: Optional[str] = None,
    include_inactive: bool = False,
    current_user: dict = Depends(admin_route_guard),
):
    """List services (admin). Same behaviour as v2 list."""
    cat = ServiceCategory(category) if category else None
    services = await service_catalogue_v2.list_services(
        category=cat,
        active_only=not include_inactive,
    )
    return {
        "services": [s.to_dict() for s in services],
        "total": len(services),
    }


@router.get("/{service_code}")
async def get_service(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get one service by service_code (admin)."""
    if service_code.lower() == "v2":
        raise HTTPException(status_code=404, detail="Use /api/admin/services/v2 for v2 endpoints")
    service = await service_catalogue_v2.get_service(service_code)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    return service.to_dict()


@router.post("")
async def create_service(
    request: CreateServiceRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """Create a service. Same body as POST /api/admin/services/v2 (CreateServiceRequest)."""
    try:
        created = await create_service_impl(request, current_user.get("email", "admin"))
        return {
            "success": True,
            "service": created.to_dict(),
            "message": f"Service {request.service_code} created successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{service_code}")
async def update_service(
    service_code: str,
    request: UpdateServiceRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """Update a service. Same body as PUT /api/admin/services/v2/:service_code (UpdateServiceRequest)."""
    if service_code.lower() == "v2":
        raise HTTPException(status_code=404, detail="Invalid path")
    try:
        updated = await update_service_impl(
            service_code, request, current_user.get("email", "admin")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    return {
        "success": True,
        "service": updated.to_dict(),
        "message": f"Service {service_code} updated successfully",
    }


@router.patch("/{service_code}/activate")
async def activate_service(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Activate a service (PATCH)."""
    if service_code.lower() == "v2":
        raise HTTPException(status_code=404, detail="Invalid path")
    success = await service_catalogue_v2.activate_service(
        service_code=service_code,
        updated_by=current_user.get("email", "admin"),
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    return {"success": True, "message": f"Service {service_code} activated"}


@router.patch("/{service_code}/deactivate")
async def deactivate_service(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Deactivate a service (PATCH)."""
    if service_code.lower() == "v2":
        raise HTTPException(status_code=404, detail="Invalid path")
    success = await service_catalogue_v2.deactivate_service(
        service_code=service_code,
        updated_by=current_user.get("email", "admin"),
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    return {"success": True, "message": f"Service {service_code} deactivated"}
