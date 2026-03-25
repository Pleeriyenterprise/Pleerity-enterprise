"""
Re-authentication for sensitive operations: valid X-Step-Up-Token matching the logged-in user.
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from auth import decode_step_up_token


async def require_recent_step_up(request: Request, user: dict) -> None:
    """
    Require a fresh step-up JWT in X-Step-Up-Token whose portal_user_id matches Bearer user.
    Raises 403 with machine-readable detail for the SPA to prompt for password.
    """
    raw = (request.headers.get("X-Step-Up-Token") or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "STEP_UP_REQUIRED",
                "message": "Confirm your password to continue.",
            },
        )
    payload = decode_step_up_token(raw)
    uid = user.get("portal_user_id")
    if not payload or payload.get("portal_user_id") != uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "STEP_UP_INVALID",
                "message": "Step-up confirmation expired or invalid. Please verify your password again.",
            },
        )
