from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from middleware import admin_route_guard
from services.security_monitoring_service import (
    get_security_dashboard_summary,
    list_security_events,
    list_security_incidents,
    resolve_security_incident,
)

router = APIRouter(prefix="/api/admin/security", tags=["admin-security"])


@router.get("/dashboard")
async def security_dashboard(days: int = Query(7, ge=1, le=90), user: dict = Depends(admin_route_guard)):
    _ = user
    return await get_security_dashboard_summary(days=days)


@router.get("/events")
async def security_events(
    event_type: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    skip: int = Query(0, ge=0),
    user: dict = Depends(admin_route_guard),
):
    _ = user
    return await list_security_events(event_type=event_type, limit=limit, skip=skip)


@router.get("/incidents")
async def security_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, ge=1, le=300),
    skip: int = Query(0, ge=0),
    user: dict = Depends(admin_route_guard),
):
    _ = user
    return await list_security_incidents(status=status, severity=severity, limit=limit, skip=skip)


class ResolveIncidentBody(BaseModel):
    note: Optional[str] = None


@router.post("/incidents/{incident_key}/resolve")
async def resolve_incident(incident_key: str, body: ResolveIncidentBody, user: dict = Depends(admin_route_guard)):
    ok = await resolve_security_incident(
        incident_key=incident_key,
        actor_id=user.get("portal_user_id") or user.get("user_id") or "unknown",
        note=body.note,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Incident not found or already resolved")
    return {"success": True, "incident_key": incident_key}
