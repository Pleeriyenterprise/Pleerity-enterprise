"""Onboarding status endpoint for post-payment progress screen.

GET /api/onboarding/status?client_id=xxx
- Returns flat status fields for polling; DB only, no Stripe calls.
"""
from fastapi import APIRouter, HTTPException, Query, status

from database import database

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


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
