"""Admin onboarding continuation & recovery assessment (Phase 1 — read-only)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from middleware import admin_route_guard
from services.onboarding_recovery_service import build_onboarding_recovery_assessment

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/clients",
    tags=["admin-onboarding-recovery"],
    dependencies=[Depends(admin_route_guard)],
)


@router.get("/{client_id}/onboarding-recovery/assessment")
async def get_onboarding_recovery_assessment(client_id: str) -> dict:
    """
    Read-only onboarding recovery assessment: classification, blockage, recommendation.
    Phase 1 does not execute recovery actions — assessment only.
    """
    assessment = await build_onboarding_recovery_assessment(client_id)
    if not assessment.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return assessment
