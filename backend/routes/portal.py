"""Portal endpoints - setup status for post-payment onboarding.

GET /api/portal/setup-status - Read-only; JWT optional, client_id query for post-checkout.
POST /api/portal/resend-activation - Resend activation (password setup) email; same auth as setup-status.
"""
import os
from fastapi import APIRouter, HTTPException, Request, Query, Body, status
from datetime import datetime, timezone
from pydantic import BaseModel

from database import database
from middleware import get_current_user

router = APIRouter(prefix="/api/portal", tags=["portal"])

SUPPORT_EMAIL = (os.getenv("SUPPORT_EMAIL") or os.getenv("REACT_APP_SUPPORT_EMAIL") or "info@pleerityenterprise.co.uk").strip()


class ResendActivationBody(BaseModel):
    """Optional email to require match (case-insensitive)."""
    email: str | None = None

PAID_SUBSCRIPTION_STATUSES = frozenset({"ACTIVE", "PAID", "TRIALING"})
PROVISIONING_RUNNING_STATUSES = frozenset({
    "PROVISIONING_STARTED", "PROVISIONING_COMPLETED", "WELCOME_EMAIL_SENT",
    "PAYMENT_CONFIRMED",
})


def _parse_created(created) -> float | None:
    """Return age in seconds, or None if not parseable."""
    if not created:
        return None
    try:
        if hasattr(created, "timestamp"):
            dt = created
        else:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def _payment_state(client: dict, job_exists: bool) -> str:
    """Returns: unpaid | pending_webhook | paid. paid only from webhook-driven subscription_status. pending_webhook = awaiting Stripe webhook."""
    sub = (client.get("subscription_status") or "").strip().upper()
    if sub in PAID_SUBSCRIPTION_STATUSES:
        return "paid"
    age_sec = _parse_created(client.get("created_at"))
    if age_sec is not None and (job_exists or (0 <= age_sec < 600)):
        return "pending_webhook"
    return "unpaid"


def _provisioning_state(client: dict, job: dict | None) -> str:
    """Returns: not_started | queued | running | completed | failed."""
    onb = (client.get("onboarding_status") or "").strip()
    if onb == "PROVISIONED":
        return "completed"
    if onb == "FAILED":
        return "failed"
    if job:
        js = (job.get("status") or "").strip()
        if js == "FAILED":
            return "failed"
        if js == "PAYMENT_CONFIRMED":
            return "queued"
        if js in PROVISIONING_RUNNING_STATUSES or onb == "PROVISIONING":
            return "running"
    return "not_started"


def _password_state(portal_user: dict | None) -> str:
    """Returns: not_sent | sent | set."""
    if not portal_user:
        return "not_sent"
    ps = (portal_user.get("password_status") or "").strip().upper()
    return "set" if ps == "SET" else "not_sent"


def _next_action(payment_state: str, provisioning_state: str, password_state: str) -> str:
    """Returns: pay | wait_provisioning | set_password | go_to_dashboard."""
    if payment_state == "unpaid":
        return "pay"
    if payment_state == "pending_webhook":
        return "wait_provisioning"
    if provisioning_state == "failed":
        return "wait_provisioning"  # retry possible; do not show set_password
    if provisioning_state not in ("completed", "failed"):
        return "wait_provisioning"
    if password_state != "set":
        return "set_password"
    return "go_to_dashboard"


@router.get("/setup-status")
async def get_setup_status(
    request: Request,
    client_id: str | None = Query(None, description="Client ID (required when not authenticated)"),
):
    """
    Read-only setup status for polling. No side effects. No Stripe calls.
    Auth: JWT (portal user) or client_id query param (post-checkout).
    """
    user = await get_current_user(request)
    resolved_client_id = None
    if user and user.get("client_id"):
        resolved_client_id = user["client_id"]
    if not resolved_client_id and client_id:
        resolved_client_id = client_id
    if not resolved_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id required (or authenticate with portal JWT)",
        )

    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": resolved_client_id},
        {"_id": 0, "client_id": 1, "customer_reference": 1, "billing_plan": 1,
         "subscription_status": 1, "onboarding_status": 1, "created_at": 1, "full_name": 1,
         "provisioning_status": 1, "provisioning_started_at": 1, "provisioning_completed_at": 1, "last_provisioning_error": 1,
         "portal_user_created_at": 1, "activation_email_status": 1, "activation_email_sent_at": 1, "activation_email_error": 1, "email": 1},
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    job = await db.provisioning_jobs.find_one(
        {"client_id": resolved_client_id},
        {"_id": 0, "status": 1, "last_error": 1},
        sort=[("created_at", -1)],
    )
    portal_user = await db.portal_users.find_one(
        {"client_id": resolved_client_id},
        {"_id": 0, "password_status": 1},
    )
    properties_count = await db.properties.count_documents({"client_id": resolved_client_id})
    property_ids = [p["property_id"] async for p in db.properties.find(
        {"client_id": resolved_client_id}, {"property_id": 1})]
    requirements_count = await db.requirements.count_documents(
        {"property_id": {"$in": property_ids}}) if property_ids else 0

    payment_state = _payment_state(client, job is not None)
    provisioning_state = _provisioning_state(client, job)
    password_state = _password_state(portal_user)
    next_action = _next_action(payment_state, provisioning_state, password_state)

    last_error = None
    if job and job.get("last_error"):
        last_error = {"code": "PROVISIONING_FAILED", "message": str(job["last_error"])}
    elif client.get("last_provisioning_error"):
        last_error = {"code": "PROVISIONING_FAILED", "message": str(client["last_provisioning_error"])}

    # provisioning_status on client: NOT_STARTED | IN_PROGRESS | COMPLETED | FAILED
    provisioning_status = (client.get("provisioning_status") or "NOT_STARTED").strip()
    if not provisioning_status and job:
        js = (job.get("status") or "").strip()
        if js == "PAYMENT_CONFIRMED":
            provisioning_status = "NOT_STARTED"
        elif js in ("PROVISIONING_STARTED", "PROVISIONING_COMPLETED"):
            provisioning_status = "IN_PROGRESS"
        elif js == "WELCOME_EMAIL_SENT":
            provisioning_status = "COMPLETED"
        elif js == "FAILED":
            provisioning_status = "FAILED"
        else:
            provisioning_status = "NOT_STARTED"
    if not provisioning_status:
        provisioning_status = "NOT_STARTED"

    # Authoritative flags (exact state mapping)
    portal_user_exists = portal_user is not None
    password_set = (portal_user or {}).get("password_status") == "SET"
    act_raw = (client.get("activation_email_status") or "").strip().upper()
    if act_raw in ("SENT", "FAILED"):
        activation_email_status_api = act_raw
    elif act_raw == "NOT_CONFIGURED":
        activation_email_status_api = "FAILED"
    else:
        activation_email_status_api = "NOT_SENT"
    activation_email_sent_at = client.get("activation_email_sent_at")
    if hasattr(activation_email_sent_at, "isoformat"):
        activation_email_sent_at = activation_email_sent_at.isoformat()
    portal_user_created_at = client.get("portal_user_created_at")
    if hasattr(portal_user_created_at, "isoformat"):
        portal_user_created_at = portal_user_created_at.isoformat()
    # Masked email for activation recipient (e.g. "abc***@xy***")
    def _mask_email(addr):
        if not addr or "@" not in str(addr):
            return None
        local, domain = str(addr).split("@", 1)
        return f"{local[:3]}***@{domain[:2]}***" if len(local) >= 3 else "***@***"
    activation_email_to_masked = _mask_email(client.get("email")) if (activation_email_status_api == "SENT" or client.get("activation_email_sent_at")) else None
    if last_error is None and activation_email_status_api == "FAILED" and client.get("activation_email_error"):
        last_error = {"code": "ACTIVATION_EMAIL_FAILED", "message": str(client.get("activation_email_error"))[:500]}

    # Legacy / backward compat
    provisioning_state = _provisioning_state(client, job)
    password_reset_sent = bool(job and (job.get("status") or "").strip() == "WELCOME_EMAIL_SENT") or activation_email_status_api == "SENT"
    password_state = "set" if password_set else "not_sent"

    crn = client.get("customer_reference") or ""
    return {
        "client_id": client["client_id"],
        "customer_reference": crn,
        "crn": crn,
        "client_name": client.get("full_name"),
        "billing_plan": client.get("billing_plan"),
        "intake_submitted": True,
        "payment_state": payment_state,
        "subscription_status": (client.get("subscription_status") or "").strip() or None,
        "provisioning_status": provisioning_status,
        "provisioning_state": provisioning_state,
        "portal_user_exists": portal_user_exists,
        "portal_user_created": portal_user_exists,
        "portal_user_created_at": portal_user_created_at,
        "activation_email_status": activation_email_status_api,
        "activation_email_sent_at": activation_email_sent_at,
        "activation_email_last_sent_at": activation_email_sent_at,
        "activation_email_to_masked": activation_email_to_masked,
        "masked_email": activation_email_to_masked,
        "activation_email_error": (client.get("activation_email_error") or "").strip() or None,
        "password_set": password_set,
        "password_reset_sent": password_reset_sent,
        "password_state": password_state,
        "next_action": next_action,
        "last_error": last_error,
        "properties_count": properties_count,
        "requirements_count": requirements_count,
        "support_email": SUPPORT_EMAIL,
    }


async def _resolve_portal_client_id(request: Request, client_id: str | None) -> str:
    """Same resolution as setup-status: JWT client_id or query client_id."""
    user = await get_current_user(request)
    if user and user.get("client_id"):
        return user["client_id"]
    if client_id:
        return client_id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="client_id required (or authenticate with portal JWT)",
    )


@router.post("/resend-activation")
async def resend_activation(
    request: Request,
    client_id: str | None = Query(None, description="Client ID (required when not authenticated)"),
    body: ResendActivationBody | None = Body(None),
):
    """
    Resend activation (password setup) email. Does NOT provision or change subscription.
    Requires: portal user exists and client onboarding_status == PROVISIONED.
    Auth: same as setup-status (JWT or client_id query).
    """
    resolved_client_id = await _resolve_portal_client_id(request, client_id)
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": resolved_client_id},
        {"_id": 0, "client_id": 1, "onboarding_status": 1, "email": 1, "full_name": 1},
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    if (client.get("onboarding_status") or "").strip() != "PROVISIONED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provisioning not complete. Activation email can only be sent after portal setup is complete.",
        )
    portal_user = await db.portal_users.find_one(
        {"client_id": resolved_client_id, "role": "ROLE_CLIENT_ADMIN"},
        {"_id": 0, "portal_user_id": 1, "auth_email": 1},
    )
    if not portal_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portal user not found. Cannot send activation email.",
        )
    if body and body.email and (client.get("email") or "").strip().lower() != (body.email or "").strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email does not match.",
        )
    from services.provisioning import provisioning_service
    import time
    idempotency_key = f"resend_activation_{resolved_client_id}_{int(time.time())}"
    ok, act_status, act_err = await provisioning_service._send_password_setup_link(
        resolved_client_id,
        portal_user["portal_user_id"],
        client.get("email") or portal_user.get("auth_email") or "",
        client.get("full_name") or "Valued Customer",
        idempotency_key=idempotency_key,
    )
    now = datetime.now(timezone.utc)
    set_fields = {"activation_email_status": act_status}
    unset_fields = {}
    if ok:
        set_fields["activation_email_sent_at"] = now
        unset_fields = {"activation_email_error": "", "last_invite_error": ""}
    else:
        if act_err:
            set_fields["activation_email_error"] = act_err[:1000]
            set_fields["last_invite_error"] = act_err[:500]
    payload = {"$set": set_fields}
    if unset_fields:
        payload["$unset"] = unset_fields
    await db.clients.update_one({"client_id": resolved_client_id}, payload)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "EMAIL_SEND_FAILED", "message": act_err or act_status or "Failed to send activation email"},
        )
    return {"message": "Activation email sent"}
