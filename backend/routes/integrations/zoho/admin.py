"""Admin routes for Zoho integration visibility and replay."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from middleware import admin_route_guard
from services.integrations.zoho.config import integration_status_snapshot, zoho_integration_enabled
from services.integrations.zoho.service import zoho_integration_service
from services.integrations.zoho.sync_store import zoho_sync_store

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/integrations/zoho",
    tags=["admin-zoho-integration"],
    dependencies=[Depends(admin_route_guard)],
)


def _guard() -> None:
    if not zoho_integration_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


class ReplayBody(BaseModel):
    dead_letter_id: str = Field(..., min_length=1)


class ManualSyncBody(BaseModel):
    integration: str = Field(..., min_length=1)
    operation: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
async def zoho_integration_status(current_user: dict = Depends(admin_route_guard)) -> Dict[str, Any]:
    _guard()
    return integration_status_snapshot()


@router.get("/sync-runs")
async def list_sync_runs(
    integration: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    _guard()
    runs = await zoho_sync_store.list_recent_runs(integration, min(limit, 200))
    return {"runs": runs, "count": len(runs)}


@router.post("/replay")
async def replay_dead_letter(
    body: ReplayBody,
    current_user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    _guard()
    actor_id = current_user.get("user_id") or current_user.get("admin_id")
    result = await zoho_integration_service.replay_dead_letter(body.dead_letter_id, actor_id=actor_id)
    return {
        "success": result.success,
        "sync_id": result.sync_id,
        "status": result.status.value,
        "message": result.message,
    }


@router.post("/sync")
async def manual_sync(
    body: ManualSyncBody,
    current_user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    _guard()
    actor_id = current_user.get("user_id") or current_user.get("admin_id")
    result = await zoho_integration_service.run_sync(
        body.integration,
        body.operation,
        body.payload,
        actor_id=actor_id,
    )
    return {
        "success": result.success,
        "sync_id": result.sync_id,
        "status": result.status.value,
        "message": result.message,
        "skip_reason": result.skip_reason.value if result.skip_reason else None,
    }


@router.post("/process-queue")
async def process_sync_queue(
    integration: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    _guard()
    return await zoho_integration_service.process_queue(integration)
