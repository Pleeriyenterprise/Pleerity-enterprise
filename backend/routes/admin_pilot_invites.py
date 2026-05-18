"""Admin Founding Pilot invite codes — list, create, update, validate, distribute."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from middleware import require_owner_or_admin
from models.pilot_invite import (
    PilotInviteCodeCreate,
    PilotInviteCodeUpdate,
    PilotInviteStatus,
)
from services.pilot_invite_service import (
    build_invite_distribution,
    create_invite_code,
    get_invite_code,
    get_invite_usage,
    get_pilot_invite_operational_config,
    list_invite_codes,
    normalize_invite_code,
    preview_stripe_coupon_validation,
    suggest_invite_code,
    update_invite_code,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/pilot-invites", tags=["admin-pilot-invites"])


class PilotInviteStripeValidateBody(BaseModel):
    stripe_coupon_id: Optional[str] = Field(default=None, max_length=128)
    stripe_promotion_code_id: Optional[str] = Field(default=None, max_length=128)
    discount_mode: str = Field(default="coupon", max_length=64)
    discount_percent: int = Field(default=100, ge=1, le=100)
    discount_duration: str = Field(default="repeating", max_length=32)
    discount_duration_in_months: Optional[int] = Field(default=2, ge=1, le=36)


class PilotInviteDistributionQuery(BaseModel):
    plan_code: str = Field(default="PLAN_1_SOLO", max_length=64)


@router.get("/operational-config")
async def get_operational_config(_user: dict = Depends(require_owner_or_admin)) -> Dict[str, Any]:
    """Safe operational/env requirements for pilot invite rollout (no secrets)."""
    return get_pilot_invite_operational_config()


@router.get("")
async def get_pilot_invites(
    status: Optional[str] = Query(None, description="active|expired|disabled|exhausted|waived_onboarding"),
    onboarding_policy: Optional[str] = Query(None),
    duration_months: Optional[int] = Query(None, ge=1, le=36),
    plan_code: Optional[str] = Query(None),
    exhausted_only: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    codes = await list_invite_codes(
        limit=limit,
        status_filter=status,
        onboarding_policy=onboarding_policy,
        duration_months=duration_months,
        plan_code=plan_code,
        exhausted_only=exhausted_only,
    )
    return {"invite_codes": codes, "count": len(codes)}


@router.get("/suggest-code")
async def suggest_code(
    prefix: str = Query("FOUNDING", max_length=32),
    variant: str = Query("", max_length=32),
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    code = suggest_invite_code(prefix=prefix, variant=variant)
    return {"code": code, "normalized": normalize_invite_code(code)}


@router.post("/validate-stripe")
async def validate_stripe_coupon(
    body: PilotInviteStripeValidateBody,
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    """Validate Stripe coupon/promotion against invite discount fields (no persist)."""
    fields = {
        "stripe_coupon_id": (body.stripe_coupon_id or "").strip() or None,
        "stripe_promotion_code_id": (body.stripe_promotion_code_id or "").strip() or None,
        "discount_mode": body.discount_mode,
        "discount_percent": body.discount_percent,
        "discount_duration": body.discount_duration,
        "discount_duration_in_months": body.discount_duration_in_months,
        "discount_type": "percent",
    }
    return await preview_stripe_coupon_validation(fields)


@router.post("")
async def post_pilot_invite(
    body: PilotInviteCodeCreate,
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    try:
        created_by = _user.get("email") or _user.get("portal_user_id")
        payload = body.model_copy(update={"created_by": body.created_by or created_by})
        doc = await create_invite_code(payload)
        return {"invite_code": doc}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/accounts")
async def get_pilot_accounts(_user: dict = Depends(require_owner_or_admin)) -> Dict[str, Any]:
    from services.pilot_lifecycle_service import list_pilot_accounts as list_lifecycle

    accounts = await list_lifecycle()
    return {"accounts": accounts, "count": len(accounts)}


@router.get("/{code}")
async def get_pilot_invite(
    code: str,
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    doc = await get_invite_code(code)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    return {"invite_code": doc}


@router.patch("/{code}")
async def patch_pilot_invite(
    code: str,
    body: PilotInviteCodeUpdate,
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    try:
        doc = await update_invite_code(code, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    return {"invite_code": doc}


@router.patch("/{code}/disable")
async def disable_pilot_invite(
    code: str,
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    doc = await update_invite_code(
        code,
        PilotInviteCodeUpdate(status=PilotInviteStatus.DISABLED),
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    return {"invite_code": doc}


@router.get("/{code}/usage")
async def get_pilot_invite_usage(
    code: str,
    limit: int = Query(100, ge=1, le=500),
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    usage = await get_invite_usage(code, limit=limit)
    if not usage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    return {"client_id": code, **usage}


@router.get("/{code}/distribution")
async def get_pilot_invite_distribution(
    request: Request,
    code: str,
    plan_code: str = Query("PLAN_1_SOLO", max_length=64),
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    doc = await get_invite_code(code)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        origin = str(request.base_url).rstrip("/")
    from services.pilot_invite_service import build_invite_commercial_summary

    dist = build_invite_distribution(doc, base_url=origin, plan_code=plan_code)
    commercial = build_invite_commercial_summary(doc, plan_code=plan_code)
    return {"distribution": dist, "commercial": commercial}
