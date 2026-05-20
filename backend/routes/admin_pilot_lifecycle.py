"""Admin pilot lifecycle governance — extend, cancel, convert, comp, history."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from middleware import admin_route_guard, require_owner
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


class PilotAccountEligibilityOverrideBody(BaseModel):
    override_type: str = Field(
        ...,
        description="bypass_first_time | allow_promo_retry | manual_attach_promo | recover_onboarding",
    )
    override_reason: str = Field(..., min_length=3, max_length=500)
    override_expires_at: Optional[datetime] = None
    scope: str = Field(default="client_id", description="email | client_id")
    scope_value: Optional[str] = Field(default=None, max_length=320)
    invite_code: Optional[str] = Field(default=None, max_length=64)


def _http_from_value_error(e: ValueError) -> HTTPException:
    msg = str(e)
    code = msg.split(":")[0] if ":" in msg else msg
    status_code = status.HTTP_400_BAD_REQUEST
    if code == "CLIENT_NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif code == "NOT_PILOT":
        status_code = status.HTTP_404_NOT_FOUND
    return HTTPException(status_code=status_code, detail=msg)


@router.get("/ops-dashboard")
async def ops_dashboard(
    pilot_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=500),
    skip: int = Query(0, ge=0),
    _user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    """Operational pilot lifecycle summary for founding-pilot rollout."""
    return await pls.list_pilot_ops_dashboard(status=pilot_status, limit=limit, skip=skip)


@router.post("/accounts/{client_id}/sync-stripe-payment-method")
async def sync_stripe_payment_method(
    client_id: str,
    _user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    """Refresh whether Stripe has a default payment method on file (conversion readiness)."""
    result = await pls.sync_stripe_payment_method_status(client_id)
    return {"ok": True, "client_id": client_id, **result}


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


@router.get("/accounts/{client_id}/operational-profile")
async def get_operational_profile(
    client_id: str,
    _user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    """Pilot timeline, lifecycle domains, health, conversion risk, and open anomalies."""
    try:
        return await pls.get_pilot_operational_profile(client_id)
    except ValueError as e:
        raise _http_from_value_error(e)


@router.post("/accounts/{client_id}/reconcile")
async def reconcile_account(
    client_id: str,
    _user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    """Reconcile lifecycle domains, health scoring, and anomaly detection for one account."""
    try:
        result = await pls.reconcile_pilot_operational_state(client_id)
        return {"ok": True, "client_id": client_id, **result}
    except ValueError as e:
        raise _http_from_value_error(e)


@router.get("/anomalies")
async def list_anomalies(
    client_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    _user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    from services.pilot_operational_anomalies import list_open_anomalies

    rows = await list_open_anomalies(client_id=client_id, limit=limit)
    return {"anomalies": rows, "count": len(rows)}


@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly_route(
    request: Request,
    anomaly_id: str,
    body: Dict[str, Any],
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    from services.pilot_operational_anomalies import resolve_anomaly

    notes = str(body.get("resolution_notes") or "").strip()
    if len(notes) < 3:
        raise HTTPException(status_code=400, detail="resolution_notes required")
    ok = await resolve_anomaly(
        anomaly_id,
        resolution_notes=notes,
        resolved_by=user.get("portal_user_id"),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Anomaly not found or already resolved")
    return {"ok": True, "anomaly_id": anomaly_id}


@router.get("/accounts/{client_id}/redemptions")
async def list_account_redemptions(
    client_id: str,
    limit: int = Query(50, ge=1, le=200),
    _user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    from services.pilot_promo_recovery_service import get_account_promo_recovery_context

    return await get_account_promo_recovery_context(client_id, limit=limit)


@router.post("/accounts/{client_id}/eligibility-overrides")
async def create_account_eligibility_override(
    request: Request,
    client_id: str,
    body: PilotAccountEligibilityOverrideBody,
    user: dict = Depends(admin_route_guard),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    from services.pilot_invite_service import get_invite_code
    from services.pilot_redemption_eligibility_service import create_eligibility_override

    scope = (body.scope or "client_id").strip().lower()
    if scope not in ("email", "client_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope must be email or client_id")
    scope_value = (body.scope_value or "").strip()
    if scope == "client_id":
        scope_value = scope_value or client_id
    if not scope_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope_value required")

    invite_code_id = None
    invite_code = (body.invite_code or "").strip().upper() or None
    if invite_code:
        doc = await get_invite_code(invite_code)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
        invite_code_id = str(doc.get("invite_code_id") or "")

    actor = _actor(user)
    try:
        override = await create_eligibility_override(
            scope=scope,
            scope_value=scope_value,
            override_type=body.override_type,
            override_reason=body.override_reason,
            override_actor=actor,
            invite_code=invite_code,
            invite_code_id=invite_code_id,
            override_expires_at=body.override_expires_at,
            metadata={"client_id": client_id},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True, "override": override}


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
    user: dict = Depends(require_owner),
) -> Dict[str, Any]:
    await require_recent_step_up(request, user)
    try:
        doc = await pls.comp_account(
            client_id=client_id,
            actor_id=user["portal_user_id"],
            actor_email=user.get("email"),
            reason=body.reason,
            notes=body.notes,
            review_expires_at=body.review_expires_at,
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
