"""Portal endpoints - setup status for post-payment onboarding.

GET /api/portal/setup-status - Read-only; JWT optional, client_id query for post-checkout.
"""
from fastapi import APIRouter, HTTPException, Request, Query, status
from datetime import datetime, timezone

from database import database
from middleware import get_current_user

router = APIRouter(prefix="/api/portal", tags=["portal"])

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
    """UNPAID | CONFIRMING | PAID."""
    sub = (client.get("subscription_status") or "").strip().upper()
    if sub in PAID_SUBSCRIPTION_STATUSES:
        return "PAID"
    age_sec = _parse_created(client.get("created_at"))
    if age_sec is not None and (job_exists or (0 <= age_sec < 600)):
        return "CONFIRMING"
    return "UNPAID"


def _provisioning_state(client: dict, job: dict | None) -> str:
    """NOT_STARTED | RUNNING | PROVISIONED | FAILED."""
    onb = (client.get("onboarding_status") or "").strip()
    if onb == "PROVISIONED":
        return "PROVISIONED"
    if onb == "FAILED":
        return "FAILED"
    if job:
        js = (job.get("status") or "").strip()
        if js == "FAILED":
            return "FAILED"
        if js in PROVISIONING_RUNNING_STATUSES or onb == "PROVISIONING":
            return "RUNNING"
    return "NOT_STARTED"


def _password_state(portal_user: dict | None) -> str:
    """NOT_SET | SET."""
    if not portal_user:
        return "NOT_SET"
    ps = (portal_user.get("password_status") or "").strip().upper()
    return "SET" if ps == "SET" else "NOT_SET"


def _next_action(payment_state: str, provisioning_state: str, password_state: str) -> str:
    """PAYMENT | WAIT_PROVISIONING | SET_PASSWORD | DASHBOARD."""
    if payment_state == "UNPAID":
        return "PAYMENT"
    if payment_state == "CONFIRMING":
        return "WAIT_PROVISIONING"
    if provisioning_state != "PROVISIONED":
        return "WAIT_PROVISIONING"
    if password_state == "NOT_SET":
        return "SET_PASSWORD"
    return "DASHBOARD"


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
         "subscription_status": 1, "onboarding_status": 1, "created_at": 1, "full_name": 1},
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

    return {
        "client_id": client["client_id"],
        "customer_reference": client.get("customer_reference"),
        "client_name": client.get("full_name"),
        "billing_plan": client.get("billing_plan"),
        "payment_state": payment_state,
        "provisioning_state": provisioning_state,
        "password_state": password_state,
        "next_action": next_action,
        "last_error": last_error,
        "properties_count": properties_count,
        "requirements_count": requirements_count,
    }
