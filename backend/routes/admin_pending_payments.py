"""Admin Pending Payment Recovery - RBAC owner/admin only.

Endpoints:
- GET /api/admin/intake/pending-payments - List clients pending payment
- POST /api/admin/intake/{client_id}/send-payment-link - Create checkout session and optionally email

Rules:
- NEVER call provisioning, NEVER set subscription_status, NEVER grant entitlements.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from datetime import datetime, timezone, timedelta
import os
import logging
import uuid

from database import database
from middleware import admin_route_guard, require_owner_or_admin
from services.stripe_service import stripe_service
from services.plan_registry import StripeModeMismatchError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/intake", tags=["admin-intake"])

# Paid/active: subscription_status in (active, trialing) OR stripe_subscription_id set and not canceled/incomplete_expired
SUBSCRIPTION_ACTIVE_STATUSES = frozenset({"active", "trialing"})
SUBSCRIPTION_TERMINAL_STATUSES = frozenset({"canceled", "incomplete_expired"})


def _is_paid_or_active(client: dict) -> bool:
    sub_status = (client.get("subscription_status") or "").lower()
    stripe_sub_id = (client.get("stripe_subscription_id") or "").strip()
    if sub_status in SUBSCRIPTION_ACTIVE_STATUSES:
        return True
    if stripe_sub_id and sub_status not in SUBSCRIPTION_TERMINAL_STATUSES:
        return True
    return False


def _is_provisioned(client: dict) -> bool:
    return (client.get("onboarding_status") or "") == "PROVISIONED"


@router.get("/pending-payments", dependencies=[Depends(require_owner_or_admin)])
async def get_pending_payments(request: Request):
    """
    Return clients where lifecycle_status in (pending_payment, abandoned, archived)
    OR (subscription not active AND not PROVISIONED).
    """
    await admin_route_guard(request)
    db = database.get_db()
    lifecycle_in = ["pending_payment", "abandoned", "archived"]
    cursor = db.clients.find(
        {
            "$or": [
                {"lifecycle_status": {"$in": lifecycle_in}},
                {
                    "onboarding_status": {"$ne": "PROVISIONED"},
                    "$or": [
                        {"subscription_status": {"$nin": ["active", "trialing", "ACTIVE", "TRIALING"]}},
                        {"subscription_status": {"$exists": False}},
                        {"subscription_status": None},
                        {"stripe_subscription_id": {"$in": [None, ""]}},
                        {"stripe_subscription_id": {"$exists": False}},
                    ],
                },
            ]
        },
        {
            "_id": 0,
            "client_id": 1,
            "customer_reference": 1,
            "email": 1,
            "billing_plan": 1,
            "created_at": 1,
            "lifecycle_status": 1,
            "latest_checkout_url": 1,
            "last_checkout_error_code": 1,
            "last_checkout_error_message": 1,
            "last_checkout_attempt_at": 1,
        },
    ).sort("created_at", -1)
    items = await cursor.to_list(length=500)
    # Filter out paid/active clients (defense in depth)
    result = []
    for c in items:
        if _is_paid_or_active(c) and _is_provisioned(c):
            continue
        result.append({
            "client_id": c.get("client_id"),
            "customer_reference": c.get("customer_reference"),
            "email": c.get("email"),
            "billing_plan": c.get("billing_plan"),
            "created_at": c.get("created_at"),
            "lifecycle_status": c.get("lifecycle_status", "pending_payment"),
            "latest_checkout_url": c.get("latest_checkout_url"),
            "last_checkout_error_code": c.get("last_checkout_error_code"),
            "last_checkout_error_message": c.get("last_checkout_error_message"),
            "last_checkout_attempt_at": c.get("last_checkout_attempt_at"),
        })
    return {"items": result}


@router.post("/{client_id}/send-payment-link", dependencies=[Depends(require_owner_or_admin)])
async def send_payment_link(request: Request, client_id: str):
    """
    Create Stripe checkout session for recovery; optionally send email.
    Idempotent: if recent session exists (within 30 min), return existing URL.
    NEVER modifies subscription_status or onboarding_status.
    """
    await admin_route_guard(request)
    request_id = str(uuid.uuid4())
    db = database.get_db()

    client = await db.clients.find_one(
        {"client_id": client_id},
        {
            "_id": 0,
            "client_id": 1,
            "email": 1,
            "customer_reference": 1,
            "billing_plan": 1,
            "lifecycle_status": 1,
            "latest_checkout_session_id": 1,
            "latest_checkout_url": 1,
            "checkout_link_sent_at": 1,
            "subscription_status": 1,
            "stripe_subscription_id": 1,
            "onboarding_status": 1,
        },
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    if _is_paid_or_active(client):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "CLIENT_ALREADY_ACTIVE", "message": "Client has active subscription."},
        )

    # Idempotency: if session created within last 30 min and URL exists, return it
    sent_at = client.get("checkout_link_sent_at")
    if sent_at and client.get("latest_checkout_url") and client.get("latest_checkout_session_id"):
        if isinstance(sent_at, datetime):
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
            if sent_at >= cutoff:
                return {
                    "checkout_url": client["latest_checkout_url"],
                    "session_id": client["latest_checkout_session_id"],
                    "email_sent": False,
                    "reused": True,
                }

    # Origin for redirects
    origin = (request.headers.get("origin") or os.getenv("FRONTEND_ORIGIN") or "http://localhost:3000").strip().rstrip("/")
    if not origin.startswith("http://") and not origin.startswith("https://"):
        origin = "http://localhost:3000"

    plan_code = client.get("billing_plan") or "PLAN_1_SOLO"
    customer_email = client.get("email")

    try:
        session = await stripe_service.create_checkout_session(
            client_id=client_id,
            plan_code=plan_code,
            origin_url=origin,
            customer_email=customer_email,
        )
    except StripeModeMismatchError as e:
        logger.warning("Send payment link Stripe mode mismatch client_id=%s request_id=%s: %s", client_id, request_id, e)
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "last_checkout_error_code": "STRIPE_MODE_MISMATCH",
                    "last_checkout_error_message": str(e),
                    "last_checkout_attempt_at": datetime.now(timezone.utc),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "STRIPE_MODE_MISMATCH", "message": str(e), "request_id": request_id},
        )
    except ValueError as e:
        logger.warning("Send payment link checkout failed client_id=%s request_id=%s: %s", client_id, request_id, e)
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "last_checkout_error_code": "CHECKOUT_CREATE_FAILED",
                    "last_checkout_error_message": str(e),
                    "last_checkout_attempt_at": datetime.now(timezone.utc),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHECKOUT_CREATE_FAILED", "message": str(e), "request_id": request_id},
        )
    except Exception as e:
        logger.exception("Send payment link error client_id=%s request_id=%s: %s", client_id, request_id, e)
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "last_checkout_error_code": "CHECKOUT_CREATE_FAILED",
                    "last_checkout_error_message": str(e),
                    "last_checkout_attempt_at": datetime.now(timezone.utc),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "CHECKOUT_CREATE_FAILED", "message": str(e), "request_id": request_id},
        )

    checkout_url = session.get("checkout_url")
    session_id = session.get("session_id")
    if not checkout_url:
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "last_checkout_error_code": "CHECKOUT_URL_MISSING",
                    "last_checkout_error_message": "Stripe did not return checkout URL",
                    "last_checkout_attempt_at": datetime.now(timezone.utc),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "CHECKOUT_URL_MISSING", "message": "Payment provider did not return URL", "request_id": request_id},
        )

    now = datetime.now(timezone.utc)
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "latest_checkout_session_id": session_id,
                "latest_checkout_url": checkout_url,
                "checkout_link_sent_at": now,
                "last_checkout_error_code": None,
                "last_checkout_error_message": None,
                "last_checkout_attempt_at": now,
            }
        },
    )

    email_sent = False
    postmark_token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    postmark_from = (os.getenv("POSTMARK_FROM_EMAIL") or os.getenv("EMAIL_SENDER") or "").strip()
    if postmark_token and postmark_from and client.get("email"):
        try:
            from postmarker.core import PostmarkClient
            postmark = PostmarkClient(server_token=postmark_token)
            crn = client.get("customer_reference") or "N/A"
            body = f"""You recently started your Compliance Vault Pro onboarding. Complete your payment to activate your account.

Your Customer Reference: {crn}
Payment link: {checkout_url}

If you have any questions, please contact support."""

            postmark.emails.send(
                From=postmark_from,
                To=client["email"],
                Subject="Complete your Compliance Vault Pro payment",
                TextBody=body,
            )
            email_sent = True
            logger.info("Recovery email sent to %s for client %s", client["email"], client_id)
        except Exception as send_err:
            logger.warning("Recovery email failed for client %s: %s", client_id, send_err)

    return {
        "checkout_url": checkout_url,
        "session_id": session_id,
        "email_sent": email_sent,
        "reused": False,
    }
