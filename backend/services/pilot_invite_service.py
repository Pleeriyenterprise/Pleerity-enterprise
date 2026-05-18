"""
Founding pilot invite codes — validation, Stripe discount wiring, idempotent redemption.

Stripe Checkout remains authoritative for provisioning; this service never grants entitlements directly.
Repeating discounts (e.g. 100% for 2 months) are implemented via Stripe-native coupons (duration=repeating);
the platform tags lifecycle state and records paid conversion on non-zero invoice.paid events.
"""
from __future__ import annotations

import calendar
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from models.pilot_invite import (
    PilotInviteCodeCreate,
    PilotInviteCodeUpdate,
    PilotInviteDiscountDuration,
    PilotInviteDiscountMode,
    PilotInvitePublicError,
    PilotOnboardingFeePolicy,
    PilotInviteStatus,
    PilotInviteValidateResponse,
)
from services.pilot_onboarding_fee import onboarding_policy_from_invite
from services.plan_registry import PlanCode, plan_registry, _get_stripe_mode

logger = logging.getLogger(__name__)

COL_CODES = "pilot_invite_codes"
COL_REDEMPTIONS = "pilot_invite_redemptions"

# User-safe messages (no internal Stripe IDs)
_MSG_INVALID = "This invite code is not valid."
_MSG_EXPIRED = "This invite code has expired."
_MSG_EXHAUSTED = "This invite code has already been fully used."
_MSG_PLAN = "This invite code is not valid for the selected plan."
_MSG_EMAIL = "This invite code is not valid for this email address."
_MSG_STRIPE_MISCONFIG = "Checkout is temporarily unavailable. Please contact support."
_MSG_ACCEPTED = "Pilot invite code applied. Your founding pilot access will be processed through secure checkout."
_MSG_ACCEPTED_REPEATING = (
    "Founding pilot invite applied. Your first {months} month(s) are fully discounted at secure checkout."
)
_PILOT_HEADLINE = "Founding Pilot Access Applied"
_PILOT_DETAIL_REPEATING = (
    "Your first {months} months are free, and your onboarding fee is waived. "
    "After the pilot, your selected subscription continues at the standard monthly rate "
    "unless cancelled before renewal."
)


def normalize_invite_code(raw: str) -> str:
    return re.sub(r"\s+", "", (raw or "").strip().upper())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _effective_status(doc: Dict[str, Any], now: Optional[datetime] = None) -> str:
    now = now or _utc_now()
    status = str(doc.get("status") or PilotInviteStatus.ACTIVE.value).lower()
    if status == PilotInviteStatus.DISABLED.value:
        return PilotInviteStatus.DISABLED.value
    exp = doc.get("expires_at")
    if exp is not None:
        if isinstance(exp, str):
            try:
                exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            except ValueError:
                exp = None
        if isinstance(exp, datetime):
            exp_utc = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
            if exp_utc <= now:
                return PilotInviteStatus.EXPIRED.value
    return PilotInviteStatus.ACTIVE.value if status == PilotInviteStatus.ACTIVE.value else status


def discount_config_from_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalised discount shape from invite record (Stripe coupon must match duration/percent in Dashboard)."""
    duration = str(doc.get("discount_duration") or PilotInviteDiscountDuration.FOREVER.value).lower()
    months_raw = doc.get("discount_duration_in_months")
    months = int(months_raw) if months_raw not in (None, "", 0) else 0
    percent = int(doc.get("discount_percent") or 100)
    dtype = str(doc.get("discount_type") or "percent").lower()
    expected_transition = duration == PilotInviteDiscountDuration.REPEATING.value and months > 0
    return {
        "discount_type": dtype,
        "discount_percent": max(1, min(100, percent)),
        "discount_duration": duration,
        "discount_duration_in_months": months if duration == PilotInviteDiscountDuration.REPEATING.value else 0,
        "expected_transition_to_paid": expected_transition,
    }


def _add_calendar_months(start: datetime, months: int) -> datetime:
    if months <= 0:
        return start
    y, m = start.year, start.month + months
    while m > 12:
        m -= 12
        y += 1
    last_day = calendar.monthrange(y, m)[1]
    d = min(start.day, last_day)
    return start.replace(
        year=y, month=m, day=d,
        hour=start.hour, minute=start.minute, second=start.second, microsecond=start.microsecond,
    )


def _expected_first_paid_invoice_at(start: datetime, discount_months: int) -> Optional[datetime]:
    if discount_months <= 0:
        return None
    return _add_calendar_months(start, discount_months)


def _build_validate_response(doc: Dict[str, Any], plan_code: str) -> PilotInviteValidateResponse:
    cfg = discount_config_from_doc(doc)
    months = cfg["discount_duration_in_months"]
    onb_policy = onboarding_policy_from_invite(doc)
    onb_waived = onb_policy == PilotOnboardingFeePolicy.WAIVED
    if cfg["expected_transition_to_paid"]:
        message = _MSG_ACCEPTED_REPEATING.format(months=months)
        detail = _PILOT_DETAIL_REPEATING.format(months=months)
        headline = _PILOT_HEADLINE
    else:
        message = _MSG_ACCEPTED
        headline = _PILOT_HEADLINE if onb_waived else None
        detail = (
            "Your onboarding fee is waived at secure checkout."
            if onb_waived
            else None
        )
    return PilotInviteValidateResponse(
        valid=True,
        message=message,
        program_type=str(doc.get("program_type") or "FOUNDING_PILOT"),
        plan_code=plan_code,
        discount_applied=True,
        discount_percent=cfg["discount_percent"],
        discount_duration=cfg["discount_duration"],
        discount_duration_in_months=months or None,
        expected_transition_to_paid=cfg["expected_transition_to_paid"],
        headline=headline,
        detail=detail,
        onboarding_fee_policy=onb_policy.value,
        onboarding_fee_waived=onb_waived,
    )


def _plan_allowed(doc: Dict[str, Any], plan_code: str) -> bool:
    allowed = doc.get("applies_to_plan_codes") or []
    if not allowed:
        return True
    try:
        resolved = PlanCode(plan_code).value
    except ValueError:
        resolved = plan_registry._resolve_plan_code(plan_code).value
    return resolved in {str(x).strip() for x in allowed}


def _email_matches(doc: Dict[str, Any], email: Optional[str]) -> bool:
    restriction = (doc.get("email_restriction") or "").strip().lower()
    if not restriction:
        return True
    if not email or not str(email).strip():
        return False
    return str(email).strip().lower() == restriction


def _stripe_discounts_for_doc(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build Stripe Checkout `discounts` array from stored invite configuration."""
    mode = str(doc.get("discount_mode") or PilotInviteDiscountMode.COUPON.value)
    coupon_id = (doc.get("stripe_coupon_id") or "").strip()
    promo_id = (doc.get("stripe_promotion_code_id") or "").strip()
    if mode == PilotInviteDiscountMode.PROMOTION_CODE.value and promo_id:
        return [{"promotion_code": promo_id}]
    if coupon_id:
        return [{"coupon": coupon_id}]
    if promo_id:
        return [{"promotion_code": promo_id}]
    return []


def _require_stripe_discount_configured(doc: Dict[str, Any]) -> None:
    if not _stripe_discounts_for_doc(doc):
        logger.error(
            "Pilot invite %s missing Stripe coupon/promotion configuration (discount_mode=%s)",
            doc.get("code"),
            doc.get("discount_mode"),
        )
        raise PilotInvitePublicError("PILOT_INVITE_MISCONFIGURED", _MSG_STRIPE_MISCONFIG)


async def validate_invite_for_checkout(
    *,
    code: str,
    plan_code: str,
    email: Optional[str] = None,
    for_checkout: bool = False,
) -> Tuple[Dict[str, Any], PilotInviteValidateResponse]:
    """
    Validate invite code. When for_checkout=True, also requires Stripe discount IDs configured.

    Returns (invite_doc, response). Raises PilotInvitePublicError on failure.
    """
    normalized = normalize_invite_code(code)
    if not normalized:
        raise PilotInvitePublicError("PILOT_INVITE_INVALID", _MSG_INVALID)

    db = database.get_db()
    doc = await db[COL_CODES].find_one({"code": normalized}, {"_id": 0})
    if not doc:
        raise PilotInvitePublicError("PILOT_INVITE_INVALID", _MSG_INVALID)

    eff = _effective_status(doc)
    if eff == PilotInviteStatus.DISABLED.value:
        raise PilotInvitePublicError("PILOT_INVITE_INVALID", _MSG_INVALID)
    if eff == PilotInviteStatus.EXPIRED.value:
        raise PilotInvitePublicError("PILOT_INVITE_EXPIRED", _MSG_EXPIRED)

    used = int(doc.get("used_count") or 0)
    max_uses = int(doc.get("max_uses") or 1)
    if used >= max_uses:
        raise PilotInvitePublicError("PILOT_INVITE_EXHAUSTED", _MSG_EXHAUSTED)

    if not _plan_allowed(doc, plan_code):
        raise PilotInvitePublicError("PILOT_INVITE_PLAN_NOT_ELIGIBLE", _MSG_PLAN)

    if not _email_matches(doc, email):
        raise PilotInvitePublicError("PILOT_INVITE_EMAIL_NOT_ELIGIBLE", _MSG_EMAIL)

    if for_checkout:
        _require_stripe_discount_configured(doc)
        _validate_discount_stripe_alignment(doc)

    resp = _build_validate_response(doc, plan_code)
    return doc, resp


def _validate_discount_stripe_alignment(doc: Dict[str, Any]) -> None:
    """Ensure invite record has coherent discount fields (Stripe coupon must be pre-created to match)."""
    cfg = discount_config_from_doc(doc)
    if cfg["discount_duration"] not in (
        PilotInviteDiscountDuration.FOREVER.value,
        PilotInviteDiscountDuration.ONCE.value,
        PilotInviteDiscountDuration.REPEATING.value,
    ):
        logger.error("Pilot invite %s invalid discount_duration=%s", doc.get("code"), cfg["discount_duration"])
        raise PilotInvitePublicError("PILOT_INVITE_MISCONFIGURED", _MSG_STRIPE_MISCONFIG)
    if cfg["discount_duration"] == PilotInviteDiscountDuration.REPEATING.value and cfg["discount_duration_in_months"] < 1:
        logger.error("Pilot invite %s repeating discount missing duration_in_months", doc.get("code"))
        raise PilotInvitePublicError("PILOT_INVITE_MISCONFIGURED", _MSG_STRIPE_MISCONFIG)


def build_checkout_pilot_metadata(doc: Dict[str, Any], *, plan_code: str) -> Dict[str, str]:
    """Metadata fields to attach to Stripe Checkout / subscription (string values only)."""
    stripe_mode = _get_stripe_mode()
    cfg = discount_config_from_doc(doc)
    months = cfg["discount_duration_in_months"]
    meta = {
        "program_type": str(doc.get("program_type") or "FOUNDING_PILOT"),
        "invite_code": str(doc.get("code") or ""),
        "plan_code": str(plan_code or ""),
        "selected_plan_code": str(plan_code or ""),
        "pilot_invite_code_id": str(doc.get("invite_code_id") or ""),
        "stripe_environment": stripe_mode,
        "pilot_discount_percent": str(cfg["discount_percent"]),
        "pilot_discount_duration": cfg["discount_duration"],
        "expected_transition_to_paid": "true" if cfg["expected_transition_to_paid"] else "false",
    }
    if months > 0:
        meta["pilot_discount_months"] = str(months)
        meta["pilot_duration_months"] = str(months)
    return meta


def stripe_session_discounts(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    return _stripe_discounts_for_doc(doc)


def payment_method_collection_for_pilot(doc: Dict[str, Any]) -> str:
    """
    Repeating pilot discounts: collect payment method at checkout (`always`) so Stripe can bill
    automatically after the discounted period without custom delayed-billing jobs.

    Forever/once 100% off: `if_required` (no card when checkout total is £0).
    """
    cfg = discount_config_from_doc(doc)
    if cfg["expected_transition_to_paid"]:
        return "always"
    return "if_required"


async def record_checkout_session_pilot_link(
    *,
    session_id: str,
    client_id: str,
    invite_doc: Dict[str, Any],
) -> None:
    """Persist pilot invite on checkout_sessions row for operational traceability."""
    db = database.get_db()
    await db.checkout_sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "pilot_invite_code": invite_doc.get("code"),
                "pilot_invite_code_id": invite_doc.get("invite_code_id"),
                "program_type": invite_doc.get("program_type") or "FOUNDING_PILOT",
            }
        },
    )


async def register_pending_redemption(
    *,
    checkout_session_id: str,
    client_id: str,
    invite_doc: Dict[str, Any],
    stripe_event_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
) -> None:
    """Create pending redemption (idempotent on checkout_session_id). Usage counted after provisioning."""
    if not checkout_session_id:
        return
    db = database.get_db()
    now = _utc_now()
    doc = {
        "redemption_id": str(uuid.uuid4()),
        "invite_code_id": invite_doc.get("invite_code_id"),
        "code": invite_doc.get("code"),
        "program_type": invite_doc.get("program_type") or "FOUNDING_PILOT",
        "client_id": client_id,
        "checkout_session_id": checkout_session_id,
        "stripe_event_id": stripe_event_id,
        "stripe_subscription_id": stripe_subscription_id,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    try:
        await db[COL_REDEMPTIONS].insert_one(doc)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            logger.info("Pilot redemption already registered for session %s", checkout_session_id)
        else:
            raise


async def apply_pilot_tags_to_client(
    *,
    client_id: str,
    invite_doc: Dict[str, Any],
    plan_code: Optional[str] = None,
    checkout_session_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    stripe_event_id: Optional[str] = None,
) -> None:
    """Create canonical pilot lifecycle state after checkout (delegates to pilot_lifecycle_service)."""
    from services.pilot_lifecycle_service import create_from_invite_checkout

    cfg = discount_config_from_doc(invite_doc)
    months = cfg.get("discount_duration_in_months") or None
    await create_from_invite_checkout(
        client_id=client_id,
        invite_doc=invite_doc,
        checkout_session_id=checkout_session_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_event_id=stripe_event_id,
        duration_months_override=months,
    )
    # Backward-compat legacy fields not in lifecycle patch
    db = database.get_db()
    legacy: Dict[str, Any] = {
        "pilot_discount_duration": cfg["discount_duration"],
        "pilot_expected_transition_to_paid": cfg["expected_transition_to_paid"],
    }
    if cfg["discount_duration_in_months"]:
        legacy["pilot_discount_months"] = cfg["discount_duration_in_months"]
    from services.pilot_onboarding_fee import (
        onboarding_fields_for_waived_client,
        onboarding_policy_from_invite,
    )

    resolved_plan = str(plan_code or invite_doc.get("selected_plan_code") or invite_doc.get("plan_code") or "PLAN_1_SOLO")
    onb_policy = onboarding_policy_from_invite(invite_doc)
    onb_fields = onboarding_fields_for_waived_client(policy=onb_policy, plan_code=resolved_plan)
    legacy.update(onb_fields)
    billing_set: Dict[str, Any] = {k: v for k, v in onb_fields.items() if k.startswith("onboarding_fee")}
    if onb_policy == PilotOnboardingFeePolicy.WAIVED:
        billing_set["onboarding_fee_paid"] = True
    elif onb_policy == PilotOnboardingFeePolicy.DEFERRED:
        billing_set["onboarding_fee_paid"] = False
    await db.clients.update_one({"client_id": client_id}, {"$set": legacy})
    if billing_set:
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": billing_set},
            upsert=True,
        )


async def maybe_record_pilot_paid_transition(
    *,
    client_id: str,
    invoice: Dict[str, Any],
    stripe_event_id: Optional[str] = None,
) -> bool:
    """Delegate to pilot_lifecycle_service (idempotent on invoice id)."""
    from services.pilot_lifecycle_service import record_stripe_paid_transition

    return await record_stripe_paid_transition(
        client_id=client_id,
        invoice=invoice,
        stripe_event_id=stripe_event_id,
    )


async def maybe_record_pilot_cancelled_before_paid(
    *,
    client_id: str,
    stripe_event_id: Optional[str] = None,
) -> bool:
    """Delegate to pilot_lifecycle_service."""
    from services.pilot_lifecycle_service import record_stripe_cancelled_before_paid

    return await record_stripe_cancelled_before_paid(
        client_id=client_id,
        stripe_event_id=stripe_event_id,
    )


async def complete_redemption_after_provisioning(*, checkout_session_id: str) -> bool:
    """
    Increment invite used_count once after successful provisioning.
    Idempotent on checkout_session_id (safe for webhook retries / reprovisioning).
    """
    if not checkout_session_id:
        return False
    db = database.get_db()
    now = _utc_now()

    redemption = await db[COL_REDEMPTIONS].find_one_and_update(
        {"checkout_session_id": checkout_session_id, "status": "pending"},
        {"$set": {"status": "completed", "completed_at": now, "updated_at": now}},
    )
    if not redemption:
        done = await db[COL_REDEMPTIONS].find_one(
            {"checkout_session_id": checkout_session_id, "status": "completed"},
            {"_id": 0, "invite_code_id": 1},
        )
        return bool(done)

    invite_code_id = redemption.get("invite_code_id")
    if not invite_code_id:
        return False

    updated = await db[COL_CODES].find_one_and_update(
        {
            "invite_code_id": invite_code_id,
            "$expr": {"$lt": [{"$ifNull": ["$used_count", 0]}, {"$ifNull": ["$max_uses", 1]}]},
        },
        {"$inc": {"used_count": 1}, "$set": {"updated_at": now}},
    )
    if not updated:
        logger.warning(
            "Pilot invite usage not incremented (at capacity) invite_code_id=%s session=%s",
            invite_code_id,
            checkout_session_id,
        )
        return False
    logger.info(
        "Pilot invite redemption completed code=%s session=%s",
        updated.get("code"),
        checkout_session_id,
    )
    return True


# --- Admin CRUD ---


async def create_invite_code(body: PilotInviteCodeCreate) -> Dict[str, Any]:
    db = database.get_db()
    normalized = normalize_invite_code(body.code)
    if not normalized:
        raise ValueError("Invite code is required")
    existing = await db[COL_CODES].find_one({"code": normalized}, {"_id": 1})
    if existing:
        raise ValueError("Invite code already exists")

    now = _utc_now()
    duration = body.discount_duration.value
    months = body.discount_duration_in_months
    if duration != PilotInviteDiscountDuration.REPEATING.value:
        months = None
    doc = {
        "invite_code_id": str(uuid.uuid4()),
        "code": normalized,
        "status": PilotInviteStatus.ACTIVE.value,
        "program_type": (body.program_type or "FOUNDING_PILOT").strip(),
        "applies_to_plan_codes": list(body.applies_to_plan_codes or []),
        "max_uses": int(body.max_uses),
        "used_count": 0,
        "expires_at": body.expires_at,
        "email_restriction": (body.email_restriction or "").strip().lower() or None,
        "stripe_coupon_id": (body.stripe_coupon_id or "").strip() or None,
        "stripe_promotion_code_id": (body.stripe_promotion_code_id or "").strip() or None,
        "discount_mode": body.discount_mode.value,
        "discount_type": body.discount_type.value,
        "discount_percent": int(body.discount_percent),
        "discount_duration": duration,
        "discount_duration_in_months": months,
        "waive_onboarding_fee": bool(body.waive_onboarding_fee),
        "onboarding_fee_policy": body.onboarding_fee_policy.value,
        "onboarding_fee_discount_percent": body.onboarding_fee_discount_percent,
        "metadata": body.metadata or {},
        "created_at": now,
        "updated_at": now,
        "created_by": body.created_by,
    }
    await db[COL_CODES].insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_invite_codes(*, limit: int = 200) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = db[COL_CODES].find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    rows = []
    async for doc in cursor:
        doc["effective_status"] = _effective_status(doc)
        doc["remaining_uses"] = max(0, int(doc.get("max_uses") or 0) - int(doc.get("used_count") or 0))
        rows.append(doc)
    return rows


async def update_invite_code(code: str, body: PilotInviteCodeUpdate) -> Optional[Dict[str, Any]]:
    from pymongo import ReturnDocument

    db = database.get_db()
    normalized = normalize_invite_code(code)
    patch: Dict[str, Any] = {"updated_at": _utc_now()}
    if body.status is not None:
        patch["status"] = body.status.value
    if body.max_uses is not None:
        patch["max_uses"] = body.max_uses
    if body.expires_at is not None:
        patch["expires_at"] = body.expires_at
    if body.email_restriction is not None:
        patch["email_restriction"] = (body.email_restriction or "").strip().lower() or None
    if body.stripe_coupon_id is not None:
        patch["stripe_coupon_id"] = (body.stripe_coupon_id or "").strip() or None
    if body.stripe_promotion_code_id is not None:
        patch["stripe_promotion_code_id"] = (body.stripe_promotion_code_id or "").strip() or None
    if body.discount_mode is not None:
        patch["discount_mode"] = body.discount_mode.value
    if body.discount_type is not None:
        patch["discount_type"] = body.discount_type.value
    if body.discount_percent is not None:
        patch["discount_percent"] = body.discount_percent
    if body.discount_duration is not None:
        patch["discount_duration"] = body.discount_duration.value
        if body.discount_duration != PilotInviteDiscountDuration.REPEATING:
            patch["discount_duration_in_months"] = None
    if body.discount_duration_in_months is not None:
        patch["discount_duration_in_months"] = body.discount_duration_in_months
    if body.waive_onboarding_fee is not None:
        patch["waive_onboarding_fee"] = body.waive_onboarding_fee
    if body.onboarding_fee_policy is not None:
        patch["onboarding_fee_policy"] = body.onboarding_fee_policy.value
    if body.onboarding_fee_discount_percent is not None:
        patch["onboarding_fee_discount_percent"] = body.onboarding_fee_discount_percent
    if body.metadata is not None:
        patch["metadata"] = body.metadata
    res = await db[COL_CODES].find_one_and_update(
        {"code": normalized},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    if not res:
        return None
    res.pop("_id", None)
    res["effective_status"] = _effective_status(res)
    return res


async def list_pilot_accounts(*, limit: int = 200) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = (
        db.clients.find(
            {"pilot_program_type": {"$exists": True, "$ne": None}},
            {
                "_id": 0,
                "client_id": 1,
                "email": 1,
                "contact_email": 1,
                "full_name": 1,
                "billing_plan": 1,
                "pilot_program_type": 1,
                "pilot_invite_code": 1,
                "pilot_started_at": 1,
                "pilot_discount_applied": 1,
                "pilot_discount_percent": 1,
                "pilot_discount_months": 1,
                "pilot_discount_duration": 1,
                "pilot_expected_first_paid_invoice_at": 1,
                "pilot_expected_transition_to_paid": 1,
                "pilot_transitioned_to_paid_at": 1,
                "pilot_cancelled_before_paid_conversion": 1,
                "subscription_status": 1,
                "pilot": 1,
                "created_at": 1,
            },
        )
        .sort("pilot_started_at", -1)
        .limit(limit)
    )
    return [doc async for doc in cursor]
