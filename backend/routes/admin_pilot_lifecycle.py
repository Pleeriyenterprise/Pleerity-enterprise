"""Admin pilot lifecycle governance — extend, cancel, convert, comp, history."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from middleware import admin_route_guard
from middleware.step_up_auth import require_recent_step_up
from models.pilot_lifecycle import (
    PilotCancelBody,
    PilotCompBody,
    PilotConvertBody,
    PilotCreateOverrideBody,
    PilotExtendBody,
    PilotNotesBody,
    PilotSetExpiryBody,
    PilotSetOnboardingFeeBody,
)
from services import pilot_lifecycle_service as pls

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/pilot-lifecycle",
    tags=["admin-pilot-lifecycle"],
    dependencies=[Depends(admin_route_guard)],
)


def _actor(user: dict) -> Dict[str, Any]:
    return {
        "type": "admin",
        "id": user.get("portal_user_id"),
        "email": user.get("email"),
    }


def _http_from_value_error(e: ValueError) -> HTTPException:
    msg = str(e)
    code = msg.split(":")[0] if ":" in msg else msg
    status_code = status.HTTP_400_BAD_REQUEST
    if code == "CLIENT_NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif code == "NOT_PILOT":
        status_code = status.HTTP_404_NOT_FOUND
    return HTTPException(status_code=status_code, detail=msg)


@router.get("/accounts")
async def list_accounts(
    pilot_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=500),
    skip: int = Query(0, ge=0),
    _user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    accounts = await pls.list_pilot_accounts(status=pilot_status, limit=limit, skip=skip)
    return {"accounts": accounts, "count": len(accounts), "skip": skip, "limit": limit}


@router.get("/accounts/{client_id}")
async def get_account(client_id: str, _user: dict = Depends(admin_route_guard)) -> Dict[str, Any]:
    try:
        return await pls.get_pilot_state(client_id)
    except ValueError as e:
        raise _http_from_value_error(e)


@router.get("/accounts/{client_id}/history")
async def get_history(
    client_id: str,
    limit: int = Query(100, ge=1, le=500),
    _user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    history = await pls.get_lifecycle_history(client_id, limit=limit)
    return {"client_id": client_id, "history": history, "count": len(history)}


@router.post("/accounts/{client_id}/create")
async def create_pilot_override(
    request: Request,
    client_id: str,
    body: PilotCreateOverrideBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.admin_create_override(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            program_type=body.program_type,
            duration_months=body.duration_months,
            expires_at=body.expires_at,
            discount_percent=body.discount_percent,
            invite_code=body.invite_code,
            reason=body.reason,
            notes=body.notes,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/extend")
async def extend_account(
    request: Request,
    client_id: str,
    body: PilotExtendBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.extend_pilot(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            reason=body.reason,
            days=body.days,
            weeks=body.weeks,
            months=body.months,
            until=body.until,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/set-expiry")
async def set_expiry(
    request: Request,
    client_id: str,
    body: PilotSetExpiryBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.set_pilot_expiry(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            reason=body.reason,
            expires_at=body.expires_at,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/cancel")
async def cancel_account(
    request: Request,
    client_id: str,
    body: PilotCancelBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.cancel_pilot(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            reason=body.reason,
            cancel_stripe_subscription=body.cancel_stripe_subscription,
            revoke_access_immediately=body.revoke_access_immediately,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/convert-to-paid")
async def convert_account(
    request: Request,
    client_id: str,
    body: PilotConvertBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.convert_to_paid(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            reason=body.reason,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/comp")
async def comp_account(
    request: Request,
    client_id: str,
    body: PilotCompBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.comp_account(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            reason=body.reason,
            notes=body.notes,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/pause")
async def pause_account(
    request: Request,
    client_id: str,
    body: PilotConvertBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.pause_pilot(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            reason=body.reason,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/resume")
async def resume_account(
    request: Request,
    client_id: str,
    body: PilotConvertBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.resume_pilot(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            reason=body.reason,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/onboarding-fee-policy")
async def set_onboarding_fee_policy(
    request: Request,
    client_id: str,
    body: PilotSetOnboardingFeeBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.admin_set_onboarding_fee_policy(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            policy=body.onboarding_fee_policy.value,
            reason=body.reason,
            waiver_reason=body.waiver_reason,
            deferred_until=body.deferred_until,
            mark_charged=body.mark_charged,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.patch("/accounts/{client_id}/notes")
async def patch_notes(
    request: Request,
    client_id: str,
    body: PilotNotesBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.update_notes(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            notes=body.notes,
        )
        return {"ok": True, "client_id": client_id, "pilot": doc}
    except ValueError as e:
        raise _http_from_value_error(e)
