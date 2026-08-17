"""Governed execution for onboarding recovery modes B and C (Phase 2)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from database import database
from models import AuditAction, OnboardingStatus, PasswordStatus, PasswordToken, UserRole
from utils.audit import create_audit_log
from services.onboarding_recovery_notification_service import (
    send_recovery_activation_email,
    send_recovery_payment_email,
)
from services.onboarding_continuation_service import (
    OnboardingContinuationError,
    create_secure_continuation_link,
    derive_customer_next_step,
)
from services.onboarding_recovery_service import (
    MODE_REGENERATE_PAYMENT,
    MODE_RELEASE_AND_RESTART,
    MODE_RESEND_ACTIVATION,
    MODE_RESUME_ONBOARDING,
    _checkout_is_fresh,
    _is_paid_or_active,
    build_onboarding_recovery_assessment,
    classify_recovery_state,
    detect_stranded_onboarding,
    validate_recovery_eligibility,
)
from utils.client_email import (
    ONBOARDING_IDENTITY_RELEASED,
    canonical_client_email,
    is_released_onboarding_identity,
)
from services.plan_registry import StripeModeMismatchError
logger = logging.getLogger(__name__)

EXECUTABLE_MODES = frozenset(
    {MODE_REGENERATE_PAYMENT, MODE_RESEND_ACTIVATION, MODE_RESUME_ONBOARDING, MODE_RELEASE_AND_RESTART}
)

_MODE_CLASSIFICATIONS: Dict[str, frozenset] = {
    MODE_REGENERATE_PAYMENT: frozenset(
        {
            "PAYMENT_ABANDONED",
            "EXPIRED_CHECKOUT",
            "PROMO_REDEMPTION_FAILED",
            "FIRST_TIME_RESTRICTION_COLLISION",
            "EMAIL_RESERVED_NO_CHECKOUT",
            "PROMO_CONTEXT_LOST",
        }
    ),
    MODE_RESUME_ONBOARDING: frozenset(
        {
            "PAYMENT_ABANDONED",
            "EXPIRED_CHECKOUT",
            "PROMO_REDEMPTION_FAILED",
            "FIRST_TIME_RESTRICTION_COLLISION",
            "EMAIL_RESERVED_NO_CHECKOUT",
        }
    ),
    MODE_RESEND_ACTIVATION: frozenset({"ACTIVATION_INCOMPLETE", "PASSWORD_SETUP_PENDING"}),
    MODE_RELEASE_AND_RESTART: frozenset(
        {
            "EMAIL_RESERVED_NO_CHECKOUT",
            "EXPIRED_CHECKOUT",
            "PAYMENT_ABANDONED",
            "PROMO_REDEMPTION_FAILED",
            "PROMO_CONTEXT_LOST",
            "FIRST_TIME_RESTRICTION_COLLISION",
            "UNKNOWN_RECOVERY_STATE",
        }
    ),
}


class OnboardingRecoveryExecutionError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def validate_mode_for_classification(mode: str, classification: Optional[str]) -> None:
    if mode not in EXECUTABLE_MODES:
        raise OnboardingRecoveryExecutionError(
            "MODE_NOT_SUPPORTED",
            f"Recovery mode '{mode}' is not executable.",
        )
    allowed = _MODE_CLASSIFICATIONS.get(mode, frozenset())
    if classification not in allowed:
        raise OnboardingRecoveryExecutionError(
            "MODE_CLASSIFICATION_MISMATCH",
            f"Mode '{mode}' is not valid for classification '{classification}'.",
        )


async def resolve_pilot_invite_for_client(client: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    code = (client.get("pilot_invite_code") or "").strip().upper()
    if not code:
        from services.pilot_redemption_eligibility_service import (
            EligibilityOverrideType,
            find_active_overrides,
        )

        overrides = await find_active_overrides(
            email=client.get("email") or client.get("contact_email"),
            client_id=client.get("client_id"),
            override_types=[
                EligibilityOverrideType.MANUAL_ATTACH_PROMO.value,
                EligibilityOverrideType.ALLOW_PROMO_RETRY.value,
            ],
        )
        for row in overrides:
            code = (row.get("invite_code") or "").strip().upper()
            if code:
                break
    if not code:
        return None
    from services.pilot_invite_service import get_invite_code

    return await get_invite_code(code)


async def _apply_recovery_waiver_if_requested(
    *,
    client_id: str,
    client: Dict[str, Any],
    reason: str,
    actor: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    from services.pilot_redemption_eligibility_service import (
        EligibilityOverrideScope,
        EligibilityOverrideType,
        create_eligibility_override,
    )

    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    return await create_eligibility_override(
        scope=EligibilityOverrideScope.CLIENT_ID.value,
        scope_value=client_id,
        override_type=EligibilityOverrideType.RECOVER_ONBOARDING.value,
        override_reason=reason.strip(),
        override_actor=actor,
        invite_code=(client.get("pilot_invite_code") or "").strip().upper() or None,
        override_expires_at=expires_at,
        metadata={"source": "onboarding_recovery_execute"},
    )


async def _record_recovery_client_update(
    db,
    *,
    client_id: str,
    mode: str,
    classification: Optional[str],
    extra_set: Optional[Dict[str, Any]] = None,
) -> None:
    now = datetime.now(timezone.utc)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "recovery_attempt_count": 1})
    attempt_count = int((client or {}).get("recovery_attempt_count") or 0) + 1
    payload: Dict[str, Any] = {
        "last_recovery_at": now,
        "last_recovery_mode": mode,
        "last_recovery_classification": classification,
        "recovery_attempt_count": attempt_count,
        "recovery_origin_reference": f"admin_onboarding_recovery_{mode}",
    }
    if extra_set:
        payload.update(extra_set)
    await db.clients.update_one({"client_id": client_id}, {"$set": payload})


async def execute_regenerate_payment(
    *,
    client_id: str,
    signals: Dict[str, Any],
    classification: Optional[str],
    reason: str,
    actor: Dict[str, Any],
    origin_url: str,
    send_customer_email: bool,
    preserve_promo_eligibility: bool,
    apply_recovery_waiver: bool,
    promo_decision: Optional[str] = None,
    selected_invite_code: Optional[str] = None,
) -> Dict[str, Any]:
    client = signals["client"]
    if _is_paid_or_active(client, signals.get("billing")):
        raise OnboardingRecoveryExecutionError(
            "CLIENT_ALREADY_ACTIVE",
            "Client already has an active subscription; payment regeneration is not allowed.",
        )
    if _checkout_is_fresh(client) and classification != "EXPIRED_CHECKOUT":
        raise OnboardingRecoveryExecutionError(
            "RECOVERY_CHECKOUT_STILL_FRESH",
            "A checkout link was sent recently. Wait for expiry or confirm the customer cannot use it.",
        )

    db = database.get_db()
    waiver = None
    if apply_recovery_waiver:
        waiver = await _apply_recovery_waiver_if_requested(
            client_id=client_id,
            client=client,
            reason=reason,
            actor=actor,
        )

    decision = (promo_decision or "").strip().lower()
    if not decision:
        decision = "preserve_existing" if preserve_promo_eligibility else "none"
    if decision not in ("none", "preserve_existing", "apply_selected"):
        raise OnboardingRecoveryExecutionError(
            "INVALID_PROMO_DECISION",
            "Promo decision must be none, preserve_existing, or apply_selected.",
        )

    from services.pilot_invite_service import get_invite_code

    pilot_invite_doc = None
    applied_invite_code = None
    if decision == "preserve_existing":
        pilot_invite_doc = await resolve_pilot_invite_for_client(client)
        applied_invite_code = (pilot_invite_doc or {}).get("code")
        if preserve_promo_eligibility and not pilot_invite_doc:
            logger.warning("preserve_existing requested but no validated invite for client_id=%s", client_id)
    elif decision == "apply_selected":
        code = (selected_invite_code or "").strip().upper()
        if not code:
            raise OnboardingRecoveryExecutionError(
                "PROMO_CODE_REQUIRED",
                "Select an active approved promotion.",
            )
        invite = await get_invite_code(code)
        if not invite:
            raise OnboardingRecoveryExecutionError("PROMO_NOT_FOUND", "That promotion is not available.")
        if str(invite.get("effective_status") or "").lower() != "active":
            raise OnboardingRecoveryExecutionError(
                "PROMO_NOT_ACTIVE",
                "That promotion is not currently active.",
            )
        remaining = invite.get("remaining_uses")
        if remaining is not None and int(remaining) <= 0:
            raise OnboardingRecoveryExecutionError(
                "PROMO_EXHAUSTED",
                "That promotion has no remaining uses.",
            )
        pilot_invite_doc = invite
        applied_invite_code = code

    plan_code = client.get("billing_plan") or "PLAN_1_SOLO"
    customer_email = (client.get("email") or client.get("contact_email") or "").strip() or None

    from services.stripe_service import stripe_service

    prior_session_id = (client.get("latest_checkout_session_id") or "").strip() or None
    if prior_session_id:
        await stripe_service.expire_checkout_session(prior_session_id)

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
        raise OnboardingRecoveryExecutionError("STRIPE_MODE_MISMATCH", str(e), 400) from e
    except ValueError as e:
        msg = str(e)
        lowered = msg.lower()
        if "live mode" in lowered or "no such coupon" in lowered or "no such promotion code" in lowered:
            raise OnboardingRecoveryExecutionError(
                "STRIPE_PROMO_MODE_MISMATCH",
                "This promotion is not available in the current payment environment. "
                "Select a staging-valid approved promo or generate a normal paid checkout.",
                409,
            ) from e
        raise OnboardingRecoveryExecutionError("CHECKOUT_CREATE_FAILED", msg, 500) from e

    checkout_url = session.get("checkout_url")
    session_id = session.get("session_id")
    if not checkout_url:
        raise OnboardingRecoveryExecutionError(
            "CHECKOUT_URL_MISSING",
            "Payment provider did not return a checkout URL.",
            502,
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
                "recovery_checkout_context": {
                    "classification": classification,
                    "promo_decision": decision,
                    "preserve_promo": decision != "none",
                    "applied_invite_code": applied_invite_code,
                    "prior_session_id": prior_session_id,
                    "prior_session_superseded": bool(prior_session_id),
                    "customer_entered_promo": False,
                },
                "last_recovery_checkout_id": session_id,
                **({"pilot_invite_code": applied_invite_code} if applied_invite_code else {}),
            }
        },
    )
    await _record_recovery_client_update(
        db,
        client_id=client_id,
        mode=MODE_REGENERATE_PAYMENT,
        classification=classification,
    )

    email_sent = False
    email_result: Dict[str, Any] = {}
    if send_customer_email and customer_email:
        email_result = await send_recovery_payment_email(
            client_id=client_id,
            recipient=customer_email,
            checkout_url=checkout_url,
            customer_reference=(client.get("customer_reference") or "N/A"),
            session_id=session_id,
        )
        email_sent = bool(email_result.get("email_sent"))
        if email_sent:
            await db.clients.update_one(
                {"client_id": client_id},
                {"$set": {"continuation_delivered_at": now}},
            )

    continuation_delivered = email_sent or (not send_customer_email and bool(checkout_url))

    return {
        "mode": MODE_REGENERATE_PAYMENT,
        "checkout_url": checkout_url,
        "session_id": session_id,
        "email_sent": email_sent,
        "email_result": email_result,
        "waiver_applied": bool(waiver),
        "waiver_override_id": (waiver or {}).get("override_id"),
        "promo_preserved": bool(pilot_invite_doc) and decision == "preserve_existing",
        "promo_decision": decision,
        "applied_invite_code": applied_invite_code,
        "prior_session_id": prior_session_id,
        "prior_session_superseded": bool(prior_session_id),
        "continuation_delivered": continuation_delivered,
        "completion_status": "CHECKOUT_RECOVERY_COMPLETE" if continuation_delivered else "CHECKOUT_CREATED_DELIVERY_UNCONFIRMED",
    }


async def execute_resume_onboarding(
    *,
    client_id: str,
    signals: Dict[str, Any],
    classification: Optional[str],
    reason: str,
    actor: Dict[str, Any],
    send_customer_email: bool,
    apply_recovery_waiver: bool,
) -> Dict[str, Any]:
    client = signals["client"]
    if _is_paid_or_active(client, signals.get("billing")):
        raise OnboardingRecoveryExecutionError(
            "CLIENT_ALREADY_ACTIVE",
            "Client already has an active subscription; onboarding resume is not allowed.",
        )
    if _checkout_is_fresh(client) and classification != "EXPIRED_CHECKOUT":
        raise OnboardingRecoveryExecutionError(
            "RECOVERY_CHECKOUT_STILL_FRESH",
            "A checkout link was sent recently. Wait for expiry or confirm the customer cannot use it.",
        )

    db = database.get_db()
    waiver = None
    if apply_recovery_waiver:
        waiver = await _apply_recovery_waiver_if_requested(
            client_id=client_id,
            client=client,
            reason=reason,
            actor=actor,
        )

    actor_id = (actor.get("id") or actor.get("portal_user_id") or "admin").strip()
    try:
        link = await create_secure_continuation_link(
            client_id=client_id,
            classification=classification,
            created_by=f"admin_onboarding_recovery:{actor_id}",
            recovery_mode=MODE_RESUME_ONBOARDING,
        )
    except OnboardingContinuationError as exc:
        raise OnboardingRecoveryExecutionError(exc.code, exc.message, exc.status_code) from exc

    continuation_url = link["continuation_url"]
    continuation_token_id = link["continuation_token_id"]
    properties_count = await db.properties.count_documents({"client_id": client_id})

    customer_email = (client.get("email") or client.get("contact_email") or "").strip() or None
    email_sent = False
    email_result: Dict[str, Any] = {}
    if send_customer_email and customer_email:
        from services.onboarding_recovery_notification_service import send_recovery_continuation_email

        email_result = await send_recovery_continuation_email(
            client_id=client_id,
            recipient=customer_email,
            continuation_url=continuation_url,
            customer_reference=(client.get("customer_reference") or "N/A"),
            properties_count=properties_count,
            continuation_token_id=continuation_token_id,
        )
        email_sent = bool(email_result.get("email_sent"))
        if email_sent:
            await db.clients.update_one(
                {"client_id": client_id},
                {"$set": {"continuation_delivered_at": datetime.now(timezone.utc)}},
            )

    await _record_recovery_client_update(
        db,
        client_id=client_id,
        mode=MODE_RESUME_ONBOARDING,
        classification=classification,
        extra_set={
            "recovery_checkout_context": {
                "classification": classification,
                "source": "resume_onboarding",
                "continuation_token_id": continuation_token_id,
            },
        },
    )

    continuation_delivered = email_sent or (not send_customer_email and bool(continuation_url))

    return {
        "mode": MODE_RESUME_ONBOARDING,
        "continuation_url": continuation_url,
        "continuation_token_id": continuation_token_id,
        "email_sent": email_sent,
        "email_result": email_result,
        "waiver_applied": bool(waiver),
        "waiver_override_id": (waiver or {}).get("override_id"),
        "continuation_delivered": continuation_delivered,
    }


async def execute_resend_activation(
    *,
    client_id: str,
    signals: Dict[str, Any],
    reason: str,
    actor: Dict[str, Any],
    send_customer_email: bool,
) -> Dict[str, Any]:
    del reason, actor  # reserved for audit at caller
    db = database.get_db()
    client = signals["client"]
    if (client.get("onboarding_status") or "").upper() != OnboardingStatus.PROVISIONED.value:
        raise OnboardingRecoveryExecutionError(
            "ACCOUNT_NOT_READY",
            "Provisioning must be complete before resending activation.",
            403,
        )

    portal_user = signals.get("portal_user")
    if not portal_user:
        raise OnboardingRecoveryExecutionError("PORTAL_USER_NOT_FOUND", "Portal user not found.", 404)

    from utils.rate_limiter import rate_limiter

    allowed, error_msg = await rate_limiter.check_rate_limit(
        key=f"onboarding_recovery_activation_{client_id}",
        max_attempts=3,
        window_minutes=60,
    )
    if not allowed:
        raise OnboardingRecoveryExecutionError("RATE_LIMITED", error_msg or "Rate limit exceeded.", 429)

    from auth import generate_secure_token, hash_token
    from utils.app_urls import get_app_base_url

    await db.password_tokens.update_many(
        {
            "portal_user_id": portal_user["portal_user_id"],
            "used_at": None,
            "revoked_at": None,
        },
        {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}},
    )

    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)
    password_token = PasswordToken(
        token_hash=token_hash,
        portal_user_id=portal_user["portal_user_id"],
        client_id=client_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        created_by="ADMIN_ONBOARDING_RECOVERY",
        send_count=1,
    )
    doc = password_token.model_dump()
    for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
        if doc.get(key) and isinstance(doc[key], datetime):
            doc[key] = doc[key].isoformat()
    await db.password_tokens.insert_one(doc)

    base_url = get_app_base_url(for_email_links=True)
    setup_link = f"{base_url}/set-password?token={raw_token}"
    client_email = (
        client.get("email") or client.get("contact_email") or portal_user.get("auth_email") or ""
    ).strip()
    if not client_email:
        raise OnboardingRecoveryExecutionError(
            "EMAIL_MISSING",
            "Client has no email on file.",
            400,
        )

    classification = classify_recovery_state(signals)
    email_sent = False
    email_result: Dict[str, Any] = {}
    if send_customer_email:
        email_result = await send_recovery_activation_email(
            client_id=client_id,
            recipient=client_email,
            setup_link=setup_link,
            client_name=client.get("full_name") or "Customer",
        )
        email_sent = bool(email_result.get("email_sent"))

    now = datetime.now(timezone.utc)
    status = "SENT" if email_sent else ("SKIPPED" if not send_customer_email else "FAILED")
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "activation_email_status": status,
                "activation_email_sent_at": now.isoformat(),
                "activation_link_last_url": setup_link,
                "activation_email_error": None if email_sent else email_result.get("block_reason"),
            }
        },
    )
    if email_sent:
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": {"continuation_delivered_at": now}},
        )

    await _record_recovery_client_update(
        db,
        client_id=client_id,
        mode=MODE_RESEND_ACTIVATION,
        classification=classification,
    )

    if send_customer_email and not email_sent and email_result.get("outcome") == "blocked":
        raise OnboardingRecoveryExecutionError(
            "EMAIL_SEND_BLOCKED",
            email_result.get("block_reason") or "Activation email blocked.",
            502,
        )

    return {
        "mode": MODE_RESEND_ACTIVATION,
        "email_sent": email_sent,
        "email_result": email_result,
        "setup_link_domain": urlparse(setup_link).netloc or "",
        "continuation_delivered": email_sent or not send_customer_email,
    }


def _release_blockers(signals: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    client = signals.get("client") or {}
    portal_user = signals.get("portal_user") or {}
    if is_released_onboarding_identity(client):
        blockers.append("already_released")
    if _is_paid_or_active(client, signals.get("billing")):
        blockers.append("paid_or_active_subscription")
    ob = (client.get("onboarding_status") or "").upper()
    if ob == OnboardingStatus.PROVISIONED.value:
        blockers.append("already_provisioned")
    if portal_user and portal_user.get("password_status") == PasswordStatus.SET.value:
        blockers.append("portal_password_set")
    sub = (client.get("subscription_status") or "").lower()
    if (client.get("stripe_subscription_id") or "").strip() and sub not in ("canceled", "cancelled", "incomplete_expired"):
        blockers.append("stripe_subscription_present")
    return blockers


async def execute_release_and_restart(
    *,
    client_id: str,
    signals: Dict[str, Any],
    classification: Optional[str],
    reason: str,
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    blockers = _release_blockers(signals)
    if blockers:
        raise OnboardingRecoveryExecutionError(
            "RELEASE_NOT_ALLOWED",
            "This onboarding cannot be released: " + ", ".join(blockers) + ". Use payment or account recovery instead.",
        )

    client = signals["client"]
    db = database.get_db()
    canonical = canonical_client_email(client.get("email") or client.get("contact_email"))
    if not canonical:
        raise OnboardingRecoveryExecutionError("EMAIL_MISSING", "Client has no email to release.")

    from services.stripe_service import stripe_service
    from services.onboarding_continuation_service import expire_old_continuation_tokens

    prior_session_id = (client.get("latest_checkout_session_id") or "").strip() or None
    if prior_session_id:
        await stripe_service.expire_checkout_session(prior_session_id)
    tokens_revoked = await expire_old_continuation_tokens(client_id)

    now = datetime.now(timezone.utc)
    vacated_email = f"released.{client_id}@released.invalid"
    contact = (client.get("contact_email") or "").strip()
    set_fields: Dict[str, Any] = {
        "onboarding_identity_status": ONBOARDING_IDENTITY_RELEASED,
        "released_canonical_email": canonical,
        "released_at": now,
        "released_reason": reason[:500],
        "email": vacated_email,
        "latest_checkout_url": None,
        "continuation_links_invalidated_at": now,
    }
    if contact and canonical_client_email(contact) == canonical:
        set_fields["contact_email"] = vacated_email

    released = await db.clients.find_one_and_update(
        {
            "client_id": client_id,
            "onboarding_identity_status": {"$ne": ONBOARDING_IDENTITY_RELEASED},
        },
        {"$set": set_fields},
    )
    if not released:
        raise OnboardingRecoveryExecutionError(
            "RELEASE_NOT_ALLOWED",
            "This onboarding cannot be released: already_released. Use payment or account recovery instead.",
        )
    await _record_recovery_client_update(
        db,
        client_id=client_id,
        mode=MODE_RELEASE_AND_RESTART,
        classification=classification,
    )

    portal_user = signals.get("portal_user") or {}
    if portal_user and portal_user.get("password_status") != PasswordStatus.SET.value:
        await db.portal_users.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "auth_email": vacated_email,
                    "status": "DISABLED",
                    "is_deleted": True,
                    "released_canonical_email": canonical,
                }
            },
        )

    actor_role = UserRole.ROLE_ADMIN
    raw_role = (actor.get("role") or "").strip()
    try:
        if raw_role:
            actor_role = UserRole(raw_role)
    except ValueError:
        actor_role = UserRole.ROLE_ADMIN

    await create_audit_log(
        action=AuditAction.ONBOARDING_RELEASED_FOR_RESTART,
        actor_role=actor_role,
        actor_id=actor.get("portal_user_id") or "unknown",
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        metadata={
            "classification": classification,
            "released_canonical_email": canonical,
            "prior_session_id": prior_session_id,
            "tokens_revoked": tokens_revoked,
            "reason_preview": reason[:200],
            "identities_checked": ["clients", "portal_users", "subscription", "onboarding_status"],
        },
    )

    return {
        "mode": MODE_RELEASE_AND_RESTART,
        "released_canonical_email": canonical,
        "prior_session_id": prior_session_id,
        "prior_session_superseded": bool(prior_session_id),
        "tokens_revoked": tokens_revoked,
        "email_reservation_released": True,
        "continuation_delivered": False,
        "completion_status": "RESTART_RELEASE_COMPLETE",
    }


async def _invite_usable_in_current_stripe_mode(row: Dict[str, Any]) -> bool:
    """Recovery checkout can only apply coupons that exist in the current Stripe mode."""
    coupon_id = (row.get("stripe_coupon_id") or "").strip()
    promo_id = (row.get("stripe_promotion_code_id") or "").strip()
    if not coupon_id and not promo_id:
        return False
    from services.pilot_invite_service import preview_stripe_coupon_validation

    preview = await preview_stripe_coupon_validation(
        {
            "stripe_coupon_id": coupon_id or None,
            "stripe_promotion_code_id": promo_id or None,
            "discount_mode": row.get("discount_mode") or "coupon",
            "discount_percent": row.get("discount_percent"),
            "discount_duration": row.get("discount_duration"),
            "discount_duration_in_months": row.get("discount_duration_in_months"),
            "discount_type": row.get("discount_type") or "percent",
        }
    )
    return bool(preview.get("valid"))


async def list_approved_recovery_promos(*, limit: int = 50) -> list[Dict[str, Any]]:
    from services.pilot_invite_service import list_invite_codes

    rows = await list_invite_codes(limit=limit, status_filter="active")
    out = []
    for row in rows:
        remaining = row.get("remaining_uses")
        if remaining is not None and int(remaining) <= 0:
            continue
        if not await _invite_usable_in_current_stripe_mode(row):
            continue
        out.append(
            {
                "code": row.get("code"),
                "campaign_name": row.get("campaign_name"),
                "effective_status": row.get("effective_status"),
                "remaining_uses": remaining,
                "discount_percent": row.get("discount_percent"),
                "applies_to_plan_codes": row.get("applies_to_plan_codes") or [],
                "stripe_coupon_id": row.get("stripe_coupon_id"),
            }
        )
    return out


async def execute_onboarding_recovery(
    *,
    client_id: str,
    mode: str,
    reason: str,
    actor: Dict[str, Any],
    origin_url: str,
    send_customer_email: bool = True,
    preserve_promo_eligibility: bool = True,
    apply_recovery_waiver: bool = False,
    promo_decision: Optional[str] = None,
    selected_invite_code: Optional[str] = None,
    actor_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    signals = await detect_stranded_onboarding(client_id)
    if not signals.get("found"):
        raise OnboardingRecoveryExecutionError("CLIENT_NOT_FOUND", "Client not found.", 404)

    classification = classify_recovery_state(signals)
    eligibility = validate_recovery_eligibility(classification, signals)
    if not eligibility.get("eligible"):
        raise OnboardingRecoveryExecutionError(
            "NOT_ELIGIBLE",
            eligibility.get("reason") or "Recovery is not eligible for this account.",
        )

    validate_mode_for_classification(mode, classification)

    if mode == MODE_REGENERATE_PAYMENT:
        result = await execute_regenerate_payment(
            client_id=client_id,
            signals=signals,
            classification=classification,
            reason=reason,
            actor=actor,
            origin_url=origin_url,
            send_customer_email=send_customer_email,
            preserve_promo_eligibility=preserve_promo_eligibility,
            apply_recovery_waiver=apply_recovery_waiver,
            promo_decision=promo_decision,
            selected_invite_code=selected_invite_code,
        )
    elif mode == MODE_RESUME_ONBOARDING:
        result = await execute_resume_onboarding(
            client_id=client_id,
            signals=signals,
            classification=classification,
            reason=reason,
            actor=actor,
            send_customer_email=send_customer_email,
            apply_recovery_waiver=apply_recovery_waiver,
        )
    elif mode == MODE_RESEND_ACTIVATION:
        if apply_recovery_waiver:
            raise OnboardingRecoveryExecutionError(
                "WAIVER_NOT_APPLICABLE",
                "Recovery waiver applies only to payment or continuation recovery.",
            )
        result = await execute_resend_activation(
            client_id=client_id,
            signals=signals,
            reason=reason,
            actor=actor,
            send_customer_email=send_customer_email,
        )
    elif mode == MODE_RELEASE_AND_RESTART:
        if apply_recovery_waiver:
            raise OnboardingRecoveryExecutionError(
                "WAIVER_NOT_APPLICABLE",
                "Recovery waiver does not apply to release and restart.",
            )
        result = await execute_release_and_restart(
            client_id=client_id,
            signals=signals,
            classification=classification,
            reason=reason,
            actor=actor,
        )
    else:
        raise OnboardingRecoveryExecutionError("MODE_NOT_SUPPORTED", f"Unknown mode: {mode}")

    from services.onboarding_recovery_observability_service import (
        EVENT_CONTINUATION_DELIVERED,
        EVENT_CONTINUATION_FAILED,
        EVENT_RECOVERY_EXECUTED,
        record_onboarding_recovery_event,
        reconcile_recovery_outcome,
    )

    event_type = EVENT_RECOVERY_EXECUTED
    if result.get("continuation_delivered"):
        event_type = EVENT_CONTINUATION_DELIVERED
    elif result.get("email_sent") is False and send_customer_email:
        event_type = EVENT_CONTINUATION_FAILED

    await record_onboarding_recovery_event(
        event_type=event_type,
        client_id=client_id,
        mode=mode,
        classification=classification,
        actor_id=actor_id,
        continuation_delivered=result.get("continuation_delivered"),
        email_sent=result.get("email_sent"),
        metadata={
            "action_id": "onboarding_recovery_execute",
            "reason_preview": reason[:200],
            "ip_address": ip_address,
            "execution_summary": {
                k: result.get(k)
                for k in (
                    "checkout_url",
                    "session_id",
                    "continuation_url",
                    "waiver_applied",
                    "promo_preserved",
                    "promo_decision",
                    "applied_invite_code",
                    "prior_session_id",
                    "released_canonical_email",
                    "completion_status",
                )
                if result.get(k) is not None
            },
        },
    )
    await reconcile_recovery_outcome(client_id)

    assessment = await build_onboarding_recovery_assessment(client_id)
    return {
        "ok": True,
        "client_id": client_id,
        "classification": classification,
        "execution": result,
        "assessment": assessment,
    }
