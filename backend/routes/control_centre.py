"""Unified Pleerity Control Centre API — single snapshot for ops leadership."""
from fastapi import APIRouter, Depends

from middleware import admin_route_guard
from services.control_centre_service import get_control_centre_snapshot

router = APIRouter(prefix="/api/admin/control-centre", tags=["admin-control-centre"])


@router.get("/snapshot")
async def control_centre_snapshot(user: dict = Depends(admin_route_guard)):
    return await get_control_centre_snapshot(viewer_role=user.get("role"))
