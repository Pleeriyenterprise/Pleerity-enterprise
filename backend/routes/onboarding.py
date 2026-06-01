"""Onboarding status and secure continuation landing (Phase 3).

GET /api/onboarding/status?client_id=xxx — polling; DB only.
GET /api/onboarding/continuation/resolve?token= — public continuation landing context.
POST /api/onboarding/continuation/checkout — token-gated checkout for unpaid recovery.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from database import database
from services.onboarding_continuation_service import (
    OnboardingContinuationError,
    build_continuation_landing_context,
    create_continuation_checkout,
)
from utils.rate_limiter import rate_limiter

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

CONTINUATION_RESOLVE_RATE_ATTEMPTS = 30
CONTINUATION_RESOLVE_RATE_WINDOW_MINUTES = 5


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"


class ContinuationCheckoutBody(BaseModel):
    token: str = Field(..., min_length=16)
    preserve_promo_eligibility: bool = True


def _payment_status(subscription_status: str) -> str:
    """Derive payment_status from subscription_status (set by webhook)."""
    if not subscription_status:
        return "pending"
    s = (subscription_status or "").strip().upper()
    if s in ("ACTIVE", "PAID", "TRIALING"):
        return "paid"
    return "pending"


@router.get("/status")
async def get_onboarding_status(client_id: str = Query(..., description="Client ID")):
    """
    Get onboarding status for polling. Read from DB only; no Stripe calls.

    Fields: payment_status (from subscription_status), provisioning_status
    (from onboarding_status), portal_user_exists, password_set, created_at, updated_at.
    """
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "client_id": 1, "customer_reference": 1, "subscription_status": 1,
         "onboarding_status": 1, "created_at": 1, "updated_at": 1},
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    portal_user = await db.portal_users.find_one(
        {"client_id": client_id},
        {"_id": 0, "password_status": 1},
    )

    sub = client.get("subscription_status") or ""
    prov = client.get("onboarding_status") or "INTAKE_PENDING"
    created = client.get("created_at")
    updated = client.get("updated_at")
    if hasattr(created, "isoformat"):
        created = created.isoformat() if created else None
    if hasattr(updated, "isoformat"):
        updated = updated.isoformat() if updated else None

    return {
        "customer_reference": client.get("customer_reference"),
        "payment_status": _payment_status(sub),
        "subscription_status": sub,
        "provisioning_status": prov,
        "portal_user_exists": portal_user is not None,
        "password_set": bool(portal_user and (portal_user.get("password_status") or "").upper() == "SET"),
        "created_at": created,
        "updated_at": updated,
    }


@router.get("/continuation/resolve")
async def resolve_onboarding_continuation(request: Request, token: str = Query(..., min_length=16)):
    """Validate continuation token and return customer-safe landing context."""
    ip = _client_ip(request)
    allowed, err_msg = await rate_limiter.check_rate_limit(
        f"onboarding_continuation_resolve:{ip}",
        CONTINUATION_RESOLVE_RATE_ATTEMPTS,
        CONTINUATION_RESOLVE_RATE_WINDOW_MINUTES,
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_msg or "Too many requests.")

    try:
        return await build_continuation_landing_context(token)
    except OnboardingContinuationError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error_code": e.code, "message": e.message},
        ) from e


@router.post("/continuation/checkout")
async def onboarding_continuation_checkout(request: Request, body: ContinuationCheckoutBody):
    """Create Stripe checkout for unpaid client using a valid continuation token."""
    ip = _client_ip(request)
    allowed, err_msg = await rate_limiter.check_rate_limit(
        f"onboarding_continuation_checkout:{ip}",
        CONTINUATION_RESOLVE_RATE_ATTEMPTS,
        CONTINUATION_RESOLVE_RATE_WINDOW_MINUTES,
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_msg or "Too many requests.")

    origin = (request.headers.get("origin") or os.getenv("FRONTEND_ORIGIN") or "http://localhost:3000").strip().rstrip("/")
    if not origin.startswith("http://") and not origin.startswith("https://"):
        origin = "http://localhost:3000"

    try:
        return await create_continuation_checkout(
            body.token.strip(),
            origin_url=origin,
            preserve_promo=body.preserve_promo_eligibility,
        )
    except OnboardingContinuationError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"error_code": e.code, "message": e.message},
        ) from e
