"""Admin Founding Pilot invite codes — list, create, disable; pilot account visibility."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from middleware import require_owner_or_admin
from models.pilot_invite import (
    PilotInviteCodeCreate,
    PilotInviteCodeUpdate,
    PilotInviteStatus,
)
from services.pilot_invite_service import (
    create_invite_code,
    list_invite_codes,
    list_pilot_accounts,
    normalize_invite_code,
    update_invite_code,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/pilot-invites", tags=["admin-pilot-invites"])


@router.get("")
async def get_pilot_invites(_user: dict = Depends(require_owner_or_admin)) -> Dict[str, Any]:
    """List pilot invite codes with usage and effective status."""
    codes = await list_invite_codes()
    return {"invite_codes": codes, "count": len(codes)}


@router.post("")
async def post_pilot_invite(
    body: PilotInviteCodeCreate,
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    """Create a pilot invite code (Stripe coupon/promotion IDs must be set in Stripe Dashboard first)."""
    try:
        created_by = _user.get("email") or _user.get("portal_user_id")
        payload = body.model_copy(update={"created_by": body.created_by or created_by})
        doc = await create_invite_code(payload)
        return {"invite_code": doc}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{code}/disable")
async def disable_pilot_invite(
    code: str,
    _user: dict = Depends(require_owner_or_admin),
) -> Dict[str, Any]:
    """Disable an invite code (does not revoke existing subscriptions)."""
    normalized = normalize_invite_code(code)
    doc = await update_invite_code(
        normalized,
        PilotInviteCodeUpdate(status=PilotInviteStatus.DISABLED),
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    return {"invite_code": doc}


@router.get("/accounts")
async def get_pilot_accounts(_user: dict = Depends(require_owner_or_admin)) -> Dict[str, Any]:
    """Clients with pilot lifecycle (legacy path — prefer GET /api/admin/pilot-lifecycle/accounts)."""
    from services.pilot_lifecycle_service import list_pilot_accounts as list_lifecycle

    accounts = await list_lifecycle()
    return {"accounts": accounts, "count": len(accounts)}
