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
from models import ClientLifecycleStatus
from services.client_lifecycle_service import (
    default_active_client_match,
    derive_client_lifecycle_status,
    latest_provisioning_jobs_for_clients,
)
from services.plan_registry import StripeModeMismatchError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/intake", tags=["admin-intake"])

# Paid/active: subscription_status in (active, trialing) OR stripe_subscription_id set and not canceled/incomplete_expired
SUBSCRIPTION_ACTIVE_STATUSES = frozenset({"active", "trialing"})
SUBSCRIPTION_TERMINAL_STATUSES = frozenset({"canceled", "incomplete_expired"})

# Brand colours for payment link email (aligned with order_email_templates / email_service)
_BRAND_PRIMARY = "#0B1D3A"
_BRAND_ACCENT = "#00B8A9"


def _build_payment_link_email_html(checkout_url: str, customer_reference: str) -> str:
    """Build branded HTML for the payment link (complete your payment) email."""
    ref_display = customer_reference if customer_reference and customer_reference != "N/A" else ""
    ref_block = ""
    if ref_display:
        ref_block = f"""
                    <p style="margin: 0 0 20px 0; font-size: 14px; color: #64748b;">Your Customer Reference</p>
                    <p style="margin: 0 0 24px 0;"><span style="background-color: {_BRAND_ACCENT}; color: white; padding: 6px 14px; border-radius: 6px; font-family: monospace; font-size: 14px; font-weight: 600;">{ref_display}</span></p>"""
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: Arial, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f1f5f9;">
    <div style="max-width: 560px; margin: 0 auto; padding: 24px 16px;">
        <div style="background-color: {_BRAND_PRIMARY}; padding: 24px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 22px; font-weight: 600;">Compliance Vault Pro</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">Complete your payment</p>
        </div>
        <div style="background-color: #ffffff; padding: 28px 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 10px 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
            <p style="margin: 0 0 16px 0; font-size: 16px; color: #334155;">You recently started your Compliance Vault Pro onboarding. Complete your payment to activate your account.</p>
            {ref_block}
            <p style="margin: 0 0 20px 0; font-size: 14px; color: #64748b;">Click the button below to pay securely. You will be taken to our payment provider to complete the transaction.</p>
            <p style="margin: 0 0 8px 0;">
                <a href="{checkout_url}" style="display: inline-block; background-color: {_BRAND_ACCENT}; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Complete payment</a>
            </p>
            <p style="margin: 12px 0 0 0; font-size: 12px; color: #94a3b8;">If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="margin: 4px 0 0 0; font-size: 12px; word-break: break-all;"><a href="{checkout_url}" style="color: {_BRAND_ACCENT}; text-decoration: underline;">{checkout_url if len(checkout_url) <= 80 else checkout_url[:80] + "..."}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;" />
            <p style="margin: 0; font-size: 13px; color: #64748b;">If you have any questions, please contact support.</p>
            <p style="margin: 8px 0 0 0; font-size: 12px; color: #94a3b8;">Pleerity Enterprise Ltd</p>
        </div>
    </div>
</body>
</html>"""


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


_PENDING_BUCKET_VALUES = frozenset({"pending", "archived", "purge_eligible", "test_like", "all"})


@router.get("/pending-payments", dependencies=[Depends(require_owner_or_admin)])
async def get_pending_payments(request: Request, q: str = None, bucket: str = "pending"):
    """
    Return clients where lifecycle_status in (pending_payment, abandoned, archived)
    OR (subscription not active AND not PROVISIONED).
    Optional search: q filters by CRN or email (case-insensitive substring).

    bucket:
    - pending (default): same funnel, exclude enterprise-archived / purge-queue clients
    - archived: funnel + client_lifecycle_status ARCHIVED or PURGE_ELIGIBLE
    - purge_eligible: funnel + purge_eligible or status PURGE_ELIGIBLE
    - test_like: funnel + is_test_like (includes archived test-like rows)
    - all: funnel only (no enterprise lifecycle filter)
    """
    await admin_route_guard(request)
    db = database.get_db()
    b = (bucket or "pending").strip().lower()
    if b not in _PENDING_BUCKET_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bucket (use pending, archived, purge_eligible, test_like, all)",
        )

    lifecycle_in = ["pending_payment", "abandoned", "archived"]
    match_filter: dict = {
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
    }
    if q and (q := (q or "").strip()):
        search_regex = {"$regex": q, "$options": "i"}
        match_filter = {"$and": [match_filter, {"$or": [{"customer_reference": search_regex}, {"email": search_regex}, {"full_name": search_regex}]}]}

    if b == "pending":
        match_filter = {"$and": [match_filter, default_active_client_match()]}
    elif b == "archived":
        arch = {
            "$or": [
                {"client_lifecycle_status": ClientLifecycleStatus.ARCHIVED.value},
                {"client_lifecycle_status": ClientLifecycleStatus.PURGE_ELIGIBLE.value},
            ]
        }
        match_filter = {"$and": [match_filter, arch]}
    elif b == "purge_eligible":
        pe = {
            "$or": [
                {"client_lifecycle_status": ClientLifecycleStatus.PURGE_ELIGIBLE.value},
                {"purge_eligible": True},
            ]
        }
        match_filter = {"$and": [match_filter, pe]}
    elif b == "test_like":
        match_filter = {"$and": [match_filter, {"is_test_like": True}]}
    # b == "all": funnel only

    cursor = db.clients.find(
        match_filter,
        {
            "_id": 0,
            "client_id": 1,
            "customer_reference": 1,
            "email": 1,
            "full_name": 1,
            "billing_plan": 1,
            "created_at": 1,
            "lifecycle_status": 1,
            "client_lifecycle_status": 1,
            "is_deleted": 1,
            "subscription_status": 1,
            "onboarding_status": 1,
            "stripe_customer_id": 1,
            "stripe_subscription_id": 1,
            "latest_checkout_url": 1,
            "checkout_link_sent_at": 1,
            "last_checkout_error_code": 1,
            "last_checkout_error_message": 1,
            "last_checkout_attempt_at": 1,
            "purge_eligible": 1,
            "is_test_like": 1,
            "archive_reason": 1,
            "archived_at": 1,
            "purge_checked_at": 1,
            "duplicate_of_client_id": 1,
        },
    ).sort("created_at", -1)
    items = await cursor.to_list(length=500)
    # Filter out paid/active clients (defense in depth)
    filtered = [c for c in items if not (_is_paid_or_active(c) and _is_provisioned(c))]
    cids = [c.get("client_id") for c in filtered if c.get("client_id")]
    jobs_by_cid = await latest_provisioning_jobs_for_clients(db, cids)

    result = []
    for c in filtered:
        last_err = None
        if c.get("last_checkout_error_code") or c.get("last_checkout_error_message"):
            last_err = {
                "code": c.get("last_checkout_error_code"),
                "message": c.get("last_checkout_error_message"),
                "occurred_at": c.get("last_checkout_attempt_at"),
            }
        job = jobs_by_cid.get(c.get("client_id"))
        derived = derive_client_lifecycle_status(c)
        result.append({
            "client_id": c.get("client_id"),
            "customer_reference": c.get("customer_reference"),
            "email": c.get("email"),
            "full_name": c.get("full_name"),
            "billing_plan": c.get("billing_plan"),
            "created_at": c.get("created_at"),
            "lifecycle_status": c.get("lifecycle_status", "pending_payment"),
            "client_lifecycle_status": c.get("client_lifecycle_status"),
            "derived_client_lifecycle_status": derived,
            "subscription_status": c.get("subscription_status"),
            "onboarding_status": c.get("onboarding_status"),
            "billing_state": {
                "stripe_customer_id": bool((c.get("stripe_customer_id") or "").strip()),
                "stripe_subscription_id": bool((c.get("stripe_subscription_id") or "").strip()),
                "subscription_status": c.get("subscription_status"),
            },
            "provisioning_state": {"job_status": job.get("status") if job else None, "job_id": job.get("job_id") if job else None},
            "purge_eligible": bool(c.get("purge_eligible")),
            "is_test_like": bool(c.get("is_test_like")),
            "archive_reason": c.get("archive_reason"),
            "archived_at": c.get("archived_at"),
            "purge_checked_at": c.get("purge_checked_at"),
            "duplicate_of_client_id": c.get("duplicate_of_client_id"),
            "latest_checkout_url": c.get("latest_checkout_url"),
            "checkout_link_sent_at": c.get("checkout_link_sent_at"),
            "last_checkout_error": last_err,
            "last_checkout_error_code": c.get("last_checkout_error_code"),
            "last_checkout_error_message": c.get("last_checkout_error_message"),
            "last_checkout_attempt_at": c.get("last_checkout_attempt_at"),
        })
    return {"items": result, "bucket": b}


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
            customer_reference=(client.get("customer_reference") or "").strip() or None,
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
    if client.get("email"):
        try:
            from services.notification_orchestrator import notification_orchestrator
            crn = (client.get("customer_reference") or "N/A").strip()
            html_body = _build_payment_link_email_html(checkout_url=checkout_url, customer_reference=crn)
            result = await notification_orchestrator.send(
                template_key="ADMIN_MANUAL",
                client_id=None,
                context={
                    "recipient": client["email"],
                    "client_name": client.get("full_name") or "there",
                    "subject": "Complete your Compliance Vault Pro payment",
                    "message": html_body,
                    "customer_reference": crn,
                },
                idempotency_key=f"{client_id}_pending_payment_link_{session_id or 'no_session'}",
                event_type="pending_payment_link_sent",
            )
            email_sent = result.outcome in ("sent", "duplicate_ignored")
            if email_sent:
                logger.info("Recovery email sent to %s for client %s", client["email"], client_id)
            else:
                logger.warning(
                    "Recovery email blocked/failed for client %s: outcome=%s reason=%s error=%s",
                    client_id,
                    result.outcome,
                    result.block_reason,
                    result.error_message,
                )
        except Exception as send_err:
            logger.warning("Recovery email failed for client %s: %s", client_id, send_err)

    return {
        "checkout_url": checkout_url,
        "session_id": session_id,
        "email_sent": email_sent,
        "reused": False,
    }
