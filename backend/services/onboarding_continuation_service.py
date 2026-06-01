"""Secure onboarding continuation links — preserve progress, guide customer next step (Phase 3)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from database import database
from models import OnboardingStatus, PasswordStatus

logger = logging.getLogger(__name__)

COL_CONTINUATION_TOKENS = "onboarding_continuation_tokens"
CONTINUATION_TTL_HOURS = 168

_SUBSCRIPTION_ACTIVE = frozenset({"active", "trialing"})
_SUBSCRIPTION_TERMINAL = frozenset({"canceled", "incomplete_expired"})


class OnboardingContinuationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_paid_or_active(client: Dict[str, Any], billing: Optional[Dict[str, Any]] = None) -> bool:
    sub_status = (client.get("subscription_status") or "").lower()
    stripe_sub_id = (client.get("stripe_subscription_id") or "").strip()
    if billing:
        sub_status = sub_status or (billing.get("subscription_status") or "").lower()
        stripe_sub_id = stripe_sub_id or (billing.get("stripe_subscription_id") or "").strip()
    if sub_status in _SUBSCRIPTION_ACTIVE:
        return True
    if stripe_sub_id and sub_status not in _SUBSCRIPTION_TERMINAL:
        return True
    return False


def _mask_email(email: str) -> str:
    raw = (email or "").strip()
    if "@" not in raw:
        return "***"
    local, domain = raw.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def derive_customer_next_step(
    client: Dict[str, Any],
    portal_user: Optional[Dict[str, Any]],
    *,
    paid_or_active: Optional[bool] = None,
) -> str:
    """Customer-facing next step key for continuation landing."""
    paid = paid_or_active if paid_or_active is not None else _is_paid_or_active(client, None)
    onboarding = (client.get("onboarding_status") or "").upper()
    password_set = portal_user and portal_user.get("password_status") == PasswordStatus.SET.value

    if password_set and onboarding == OnboardingStatus.PROVISIONED.value:
        return "go_to_dashboard"
    if paid and onboarding == OnboardingStatus.PROVISIONED.value and not password_set:
        return "set_password"
    if paid and onboarding in (OnboardingStatus.PROVISIONING.value, OnboardingStatus.PROVISIONED.value):
        return "wait_provisioning"
    if not paid:
        return "complete_payment"
    return "track_progress"


async def expire_old_continuation_tokens(client_id: str) -> int:
    db = database.get_db()
    now = _now()
    res = await db[COL_CONTINUATION_TOKENS].update_many(
        {"client_id": client_id, "revoked_at": None, "used_at": None},
        {"$set": {"revoked_at": now.isoformat()}},
    )
    return res.modified_count


async def create_secure_continuation_link(
    *,
    client_id: str,
    classification: Optional[str],
    created_by: str,
    recovery_mode: str = "resume_onboarding",
    ttl_hours: int = CONTINUATION_TTL_HOURS,
) -> Dict[str, Any]:
    """Issue a single-use-capable continuation token and customer-facing URL."""
    from auth import generate_secure_token, hash_token
    from utils.app_urls import get_app_base_url

    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise OnboardingContinuationError("CLIENT_NOT_FOUND", "Client not found.", 404)

    await expire_old_continuation_tokens(client_id)

    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)
    token_id = str(uuid.uuid4())
    expires_at = _now() + timedelta(hours=ttl_hours)

    doc = {
        "continuation_token_id": token_id,
        "token_hash": token_hash,
        "client_id": client_id,
        "classification": classification,
        "recovery_mode": recovery_mode,
        "created_by": created_by,
        "created_at": _now().isoformat(),
        "expires_at": expires_at.isoformat(),
        "revoked_at": None,
        "used_at": None,
        "access_count": 0,
    }
    await db[COL_CONTINUATION_TOKENS].insert_one(doc)

    base_url = get_app_base_url(for_email_links=True).rstrip("/")
    continuation_url = f"{base_url}/onboarding/continue?token={raw_token}"

    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "last_continuation_token_id": token_id,
                "last_continuation_url": continuation_url,
                "last_continuation_at": _now().isoformat(),
                "recovery_origin_reference": f"onboarding_continuation_{recovery_mode}",
            }
        },
    )

    return {
        "continuation_url": continuation_url,
        "continuation_token_id": token_id,
        "expires_at": expires_at.isoformat(),
    }


async def _load_token_doc(raw_token: str) -> Dict[str, Any]:
    from auth import hash_token

    trimmed = (raw_token or "").strip()
    if len(trimmed) < 16:
        raise OnboardingContinuationError("TOKEN_INVALID", "Invalid continuation link.", 400)

    db = database.get_db()
    doc = await db[COL_CONTINUATION_TOKENS].find_one(
        {"token_hash": hash_token(trimmed)},
        {"_id": 0},
    )
    if not doc:
        raise OnboardingContinuationError("TOKEN_INVALID", "This continuation link is not valid.", 404)
    if doc.get("revoked_at"):
        raise OnboardingContinuationError(
            "TOKEN_REVOKED",
            "This continuation link has expired. Contact support for a new link.",
            410,
        )
    expires_at = doc.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < _now():
                raise OnboardingContinuationError(
                    "TOKEN_EXPIRED",
                    "This continuation link has expired. Contact support for a new link.",
                    410,
                )
        except ValueError:
            pass
    return doc


async def build_continuation_landing_context(raw_token: str) -> Dict[str, Any]:
    """Public-safe landing payload after token validation."""
    doc = await _load_token_doc(raw_token)
    client_id = doc["client_id"]
    db = database.get_db()

    await db[COL_CONTINUATION_TOKENS].update_one(
        {"continuation_token_id": doc["continuation_token_id"]},
        {"$inc": {"access_count": 1}, "$set": {"last_accessed_at": _now().isoformat()}},
    )

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise OnboardingContinuationError("CLIENT_NOT_FOUND", "Account not found.", 404)

    portal_user = await db.portal_users.find_one(
        {"client_id": client_id},
        {"_id": 0, "password_status": 1},
    )
    properties_count = await db.properties.count_documents({"client_id": client_id})
    paid = _is_paid_or_active(client, None)
    next_step = derive_customer_next_step(client, portal_user, paid_or_active=paid)

    first_name = (client.get("full_name") or "there").split()[0]
    crn = (client.get("customer_reference") or "").strip()

    welcome_message = (
        "Welcome back. Your property setup has been saved. "
        "Complete your subscription to activate your compliance workspace."
        if next_step == "complete_payment"
        else "Welcome back. Your onboarding progress has been saved."
    )

    return {
        "valid": True,
        "client_id": client_id,
        "customer_reference": crn or None,
        "client_first_name": first_name,
        "properties_count": properties_count,
        "billing_plan": client.get("billing_plan"),
        "next_step": next_step,
        "payment_required": next_step == "complete_payment",
        "welcome_message": welcome_message,
        "masked_email": _mask_email(client.get("email") or client.get("contact_email") or ""),
        "continuation_token_id": doc["continuation_token_id"],
        "expires_at": doc.get("expires_at"),
    }


async def create_continuation_checkout(
    raw_token: str,
    *,
    origin_url: str,
    preserve_promo: bool = True,
) -> Dict[str, Any]:
    """Create Stripe checkout for an unpaid client using a valid continuation token."""
    doc = await _load_token_doc(raw_token)
    client_id = doc["client_id"]
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise OnboardingContinuationError("CLIENT_NOT_FOUND", "Account not found.", 404)
    if _is_paid_or_active(client, None):
        raise OnboardingContinuationError(
            "ALREADY_PAID",
            "Payment is already complete for this account.",
            400,
        )

    pilot_invite_doc = None
    if preserve_promo:
        from services.onboarding_recovery_execution_service import resolve_pilot_invite_for_client

        pilot_invite_doc = await resolve_pilot_invite_for_client(client)

    plan_code = client.get("billing_plan") or "PLAN_1_SOLO"
    customer_email = (client.get("email") or client.get("contact_email") or "").strip() or None

    from services.stripe_service import stripe_service
    from services.plan_registry import StripeModeMismatchError

    try:
        session = await stripe_service.create_checkout_session(
            client_id=client_id,
            plan_code=plan_code,
            origin_url=origin_url,
            customer_email=customer_email,
            customer_reference=(client.get("customer_reference") or "").strip() or None,
            pilot_invite_doc=pilot_invite_doc,
        )
    except StripeModeMismatchError as e:
        raise OnboardingContinuationError("STRIPE_MODE_MISMATCH", str(e), 400) from e
    except ValueError as e:
        raise OnboardingContinuationError("CHECKOUT_CREATE_FAILED", str(e), 500) from e

    checkout_url = session.get("checkout_url")
    session_id = session.get("session_id")
    if not checkout_url:
        raise OnboardingContinuationError(
            "CHECKOUT_URL_MISSING",
            "Payment provider did not return a checkout URL.",
            502,
        )

    now = _now()
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "latest_checkout_session_id": session_id,
                "latest_checkout_url": checkout_url,
                "checkout_link_sent_at": now,
                "recovery_checkout_context": {
                    "source": "continuation_token",
                    "continuation_token_id": doc["continuation_token_id"],
                    "classification": doc.get("classification"),
                },
                "last_recovery_checkout_id": session_id,
            }
        },
    )
    await db[COL_CONTINUATION_TOKENS].update_one(
        {"continuation_token_id": doc["continuation_token_id"]},
        {"$set": {"checkout_session_id": session_id, "checkout_created_at": now.isoformat()}},
    )

    try:
        from services.onboarding_recovery_observability_service import (
            EVENT_CONTINUATION_CHECKOUT,
            record_onboarding_recovery_event,
        )

        await record_onboarding_recovery_event(
            event_type=EVENT_CONTINUATION_CHECKOUT,
            client_id=client_id,
            classification=doc.get("classification"),
            metadata={
                "continuation_token_id": doc.get("continuation_token_id"),
                "session_id": session_id,
                "source": "customer_continuation_landing",
            },
        )
    except Exception as exc:
        logger.warning("continuation checkout observability failed client_id=%s: %s", client_id, exc)

    return {
        "checkout_url": checkout_url,
        "session_id": session_id,
        "client_id": client_id,
    }
