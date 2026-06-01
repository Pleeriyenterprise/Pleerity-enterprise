"""Admin onboarding continuation & recovery — assessment and governed execution."""
from __future__ import annotations

import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from middleware import admin_route_guard, require_owner_or_admin
from middleware.step_up_auth import require_recent_step_up
from services.admin_action_governance import enforce_governed_admin_action
from services.onboarding_recovery_execution_service import (
    OnboardingRecoveryExecutionError,
    execute_onboarding_recovery,
)
from services.onboarding_recovery_service import build_onboarding_recovery_assessment

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/clients",
    tags=["admin-onboarding-recovery"],
    dependencies=[Depends(admin_route_guard)],
)


class OnboardingRecoveryExecuteBody(BaseModel):
    mode: str = Field(..., description="regenerate_payment | resend_activation")
    reason: str = Field(..., min_length=10)
    send_customer_email: bool = True
    preserve_promo_eligibility: bool = True
    apply_recovery_waiver: bool = False


@router.get("/{client_id}/onboarding-recovery/assessment")
async def get_onboarding_recovery_assessment(client_id: str) -> dict:
    """Read-only onboarding recovery assessment: classification, blockage, recommendation."""
    assessment = await build_onboarding_recovery_assessment(client_id)
    if not assessment.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return assessment


@router.post(
    "/{client_id}/onboarding-recovery/execute",
    dependencies=[Depends(require_owner_or_admin)],
)
async def execute_onboarding_recovery_route(
    request: Request,
    client_id: str,
    body: OnboardingRecoveryExecuteBody,
) -> dict:
    """
    Governed onboarding recovery execution (Phase 2): payment checkout regeneration or activation resend.
    Requires step-up, support reason, and delivers customer continuation when configured.
    """
    user = await admin_route_guard(request)
    support_reason = await enforce_governed_admin_action(
        request,
        user,
        "onboarding_recovery_execute",
        reason=body.reason,
        resource_key=client_id,
        require_recent_step_up=require_recent_step_up,
    )

    origin = (request.headers.get("origin") or os.getenv("FRONTEND_ORIGIN") or "http://localhost:3000").strip().rstrip("/")
    if not origin.startswith("http://") and not origin.startswith("https://"):
        origin = "http://localhost:3000"

    actor = {
        "portal_user_id": user.get("portal_user_id"),
        "email": user.get("email"),
        "role": user.get("role"),
    }
    ip_address = request.client.host if request.client else None

    try:
        return await execute_onboarding_recovery(
            client_id=client_id,
            mode=body.mode.strip().lower(),
            reason=support_reason,
            actor=actor,
            origin_url=origin,
            send_customer_email=body.send_customer_email,
            preserve_promo_eligibility=body.preserve_promo_eligibility,
            apply_recovery_waiver=body.apply_recovery_waiver,
            actor_id=user.get("portal_user_id"),
            ip_address=ip_address,
        )
    except OnboardingRecoveryExecutionError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error_code": e.code, "message": e.message},
        ) from e
