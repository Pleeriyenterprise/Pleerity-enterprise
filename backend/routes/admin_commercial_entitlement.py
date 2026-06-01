"""Admin commercial entitlement governance — assessment, preview, execution (Phase 2C)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from middleware import admin_route_guard, require_owner_or_admin
from middleware.step_up_auth import require_recent_step_up
from services.admin_action_governance import enforce_governed_admin_action
from services.commercial_entitlement_execution_service import (
    CommercialEntitlementExecutionError,
    apply_governed_entitlement_action,
    derive_customer_impact_preview,
)
from services.commercial_entitlement_observability_service import (
    get_client_commercial_entitlement_observability,
    get_fleet_commercial_entitlement_metrics,
)
from services.commercial_entitlement_service import build_commercial_entitlement_assessment

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/clients",
    tags=["admin-commercial-entitlement"],
    dependencies=[Depends(admin_route_guard)],
)


def _parse_expiry(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class CommercialEntitlementImpactPreviewBody(BaseModel):
    action: str = Field(..., description="Governed commercial action id")
    duration_days: Optional[int] = Field(None, ge=1, le=365)
    entitlement_expiry_at: Optional[str] = None
    sponsor_reference: Optional[str] = None
    access_policy: Optional[str] = None
    customer_note: Optional[str] = None


class CommercialEntitlementExecuteBody(CommercialEntitlementImpactPreviewBody):
    reason: str = Field(..., min_length=10)
    send_customer_email: bool = False
    entitlement_review_required: bool = False
    entitlement_review_at: Optional[str] = None
    scope: str = "account"


@router.get("/commercial-entitlement/fleet-metrics", dependencies=[Depends(require_owner_or_admin)])
async def get_commercial_entitlement_fleet_metrics() -> dict:
    return await get_fleet_commercial_entitlement_metrics()


@router.get("/{client_id}/commercial-entitlement/observability")
async def get_commercial_entitlement_observability(client_id: str) -> dict:
    payload = await get_client_commercial_entitlement_observability(client_id)
    if not payload.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return payload


@router.get("/{client_id}/commercial-entitlement/assessment")
async def get_commercial_entitlement_assessment(client_id: str) -> dict:
    assessment = await build_commercial_entitlement_assessment(client_id)
    if not assessment.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return assessment


@router.post("/{client_id}/commercial-entitlement/impact-preview")
async def post_commercial_entitlement_impact_preview(
    client_id: str,
    body: CommercialEntitlementImpactPreviewBody,
) -> dict:
    assessment = await build_commercial_entitlement_assessment(client_id)
    if not assessment.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    from services.commercial_entitlement_execution_service import _ACTION_TO_EXCEPTION, _EXCEPTION_DEFAULT_ACCESS

    exception_type = _ACTION_TO_EXCEPTION.get(body.action)
    policy = body.access_policy or _EXCEPTION_DEFAULT_ACCESS.get(exception_type or "", "full_access")
    preview = derive_customer_impact_preview(
        action=body.action,
        duration_days=body.duration_days,
        entitlement_expiry_at=_parse_expiry(body.entitlement_expiry_at),
        sponsor_reference=body.sponsor_reference,
        access_policy=policy,
        customer_note=body.customer_note,
    )
    return {
        "client_id": client_id,
        "action": body.action,
        "impact_preview": preview,
        "has_active_exception": assessment.get("has_active_exception"),
    }


@router.post(
    "/{client_id}/commercial-entitlement/execute",
    dependencies=[Depends(require_owner_or_admin)],
)
async def execute_commercial_entitlement_route(
    request: Request,
    client_id: str,
    body: CommercialEntitlementExecuteBody,
) -> dict:
    user = await admin_route_guard(request)
    support_reason = await enforce_governed_admin_action(
        request,
        user,
        "commercial_entitlement_execute",
        reason=body.reason,
        resource_key=client_id,
        require_recent_step_up=require_recent_step_up,
    )
    actor = {
        "id": user.get("portal_user_id"),
        "email": user.get("email"),
        "role": user.get("role"),
    }
    ip_address = request.client.host if request.client else None
    try:
        return await apply_governed_entitlement_action(
            client_id=client_id,
            action=body.action.strip(),
            reason=support_reason,
            actor=actor,
            duration_days=body.duration_days,
            entitlement_expiry_at=_parse_expiry(body.entitlement_expiry_at),
            entitlement_review_at=_parse_expiry(body.entitlement_review_at),
            entitlement_review_required=body.entitlement_review_required,
            sponsor_reference=body.sponsor_reference,
            access_policy=body.access_policy,
            scope=body.scope,
            send_customer_email=body.send_customer_email,
            customer_note=body.customer_note,
            actor_id=user.get("portal_user_id"),
            ip_address=ip_address,
        )
    except CommercialEntitlementExecutionError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error_code": e.code, "message": e.message},
        ) from e
