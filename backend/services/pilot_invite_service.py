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

_DEFERRED_EXPERIMENTAL_MSG = (
    "onboarding_fee_policy=deferred is experimental and requires owner approval"
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
    from services.pilot_commercial_truth import commercial_context_from_invite, validate_response_commercial_fields

    ctx = commercial_context_from_invite(doc, plan_code=plan_code)
    commercial = validate_response_commercial_fields(ctx)
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
        setup_fee_effective=commercial.get("setup_fee_effective"),
        monthly_price_after_pilot=commercial.get("monthly_price_after_pilot"),
        first_payment_estimate=commercial.get("first_payment_estimate"),
        commercial_summary=commercial.get("commercial_summary"),
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
        _reject_public_deferred_onboarding(doc)

    resp = _build_validate_response(doc, plan_code)
    return doc, resp


def _reject_public_deferred_onboarding(doc: Dict[str, Any]) -> None:
    """Deferred onboarding is experimental — not available at public checkout."""
    policy = onboarding_policy_from_invite(doc)
    if policy == PilotOnboardingFeePolicy.DEFERRED:
        raise PilotInvitePublicError(
            "PILOT_ONBOARDING_DEFERRED_NOT_AVAILABLE",
            "This invite configuration is not available for checkout. Contact support.",
        )


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
    from services.pilot_stripe_coupon_validation import (
        PilotStripeCouponValidationError,
        validate_pilot_stripe_discount_config,
    )

    if body.onboarding_fee_policy == PilotOnboardingFeePolicy.DEFERRED:
        raise ValueError(_DEFERRED_EXPERIMENTAL_MSG)

    try:
        await validate_pilot_stripe_discount_config(
            stripe_coupon_id=doc.get("stripe_coupon_id"),
            stripe_promotion_code_id=doc.get("stripe_promotion_code_id"),
            discount_mode=doc.get("discount_mode") or "coupon",
            invite_fields=doc,
        )
    except PilotStripeCouponValidationError as e:
        detail = "; ".join(e.details) if e.details else str(e)
        raise ValueError(detail) from e

    await db[COL_CODES].insert_one(doc)
    doc.pop("_id", None)
    return doc


def suggest_invite_code(*, prefix: str = "FOUNDING", variant: str = "") -> str:
    """Deterministic-style invite code suggestion (caller must check uniqueness)."""
    base = re.sub(r"[^A-Z0-9-]", "", (prefix or "FOUNDING").strip().upper()) or "FOUNDING"
    var = re.sub(r"[^A-Z0-9-]", "", (variant or "").strip().upper())
    year = str(_utc_now().year)
    if var:
        return f"{base}-{var}-{year}"[:64]
    import secrets

    token = secrets.token_hex(2).upper()
    return f"{base}-{year}-{token}"[:64]


def _enrich_invite_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(doc)
    doc["effective_status"] = _effective_status(doc)
    doc["remaining_uses"] = max(0, int(doc.get("max_uses") or 0) - int(doc.get("used_count") or 0))
    return doc


async def list_invite_codes(
    *,
    limit: int = 200,
    status_filter: Optional[str] = None,
    onboarding_policy: Optional[str] = None,
    duration_months: Optional[int] = None,
    plan_code: Optional[str] = None,
    exhausted_only: bool = False,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    mongo_q: Dict[str, Any] = {}
    if onboarding_policy:
        mongo_q["onboarding_fee_policy"] = onboarding_policy.strip().lower()
    if duration_months is not None:
        mongo_q["discount_duration_in_months"] = int(duration_months)
    if plan_code:
        mongo_q["applies_to_plan_codes"] = plan_code.strip().upper()

    cursor = db[COL_CODES].find(mongo_q, {"_id": 0}).sort("created_at", -1).limit(limit * 3)
    rows = []
    async for doc in cursor:
        row = _enrich_invite_row(doc)
        if exhausted_only and row["remaining_uses"] > 0:
            continue
        if status_filter:
            sf = status_filter.strip().lower()
            if sf == "exhausted":
                if row["remaining_uses"] > 0:
                    continue
            elif sf == "waived_onboarding":
                if str(row.get("onboarding_fee_policy") or "") != PilotOnboardingFeePolicy.WAIVED.value:
                    continue
            elif row["effective_status"] != sf:
                continue
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


async def get_invite_code(code: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    normalized = normalize_invite_code(code)
    doc = await db[COL_CODES].find_one({"code": normalized}, {"_id": 0})
    if not doc:
        return None
    return _enrich_invite_row(doc)


async def get_invite_usage(code: str, *, limit: int = 100) -> Dict[str, Any]:
    db = database.get_db()
    normalized = normalize_invite_code(code)
    invite = await get_invite_code(normalized)
    if not invite:
        return {}
    redemptions = []
    cursor = (
        db[COL_REDEMPTIONS].find({"code": normalized}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    async for r in cursor:
        redemptions.append(r)
    accounts = []
    acursor = (
        db.clients.find(
            {"pilot_invite_code": normalized},
            {
                "_id": 0,
                "client_id": 1,
                "email": 1,
                "contact_email": 1,
                "full_name": 1,
                "pilot_status": 1,
                "pilot_governance_status": 1,
                "pilot_started_at": 1,
                "pilot_converted_to_paid_at": 1,
                "billing_plan": 1,
                "created_at": 1,
            },
        )
        .sort("pilot_started_at", -1)
        .limit(limit)
    )
    async for c in acursor:
        accounts.append(c)
    return {"redemptions": redemptions, "accounts": accounts}


def build_invite_commercial_summary(invite_doc: Dict[str, Any], *, plan_code: str) -> Dict[str, Any]:
    from services.pilot_commercial_truth import (
        build_pilot_offer_summary,
        commercial_context_from_invite,
        validate_response_commercial_fields,
    )

    ctx = commercial_context_from_invite(invite_doc, plan_code=plan_code)
    fields = validate_response_commercial_fields(ctx)
    return {
        "plan_code": plan_code,
        "commercial_summary": build_pilot_offer_summary(ctx),
        "commercial_fields": fields,
        "discount_months": ctx.get("pilot_discount_months"),
        "onboarding_fee_policy": ctx.get("onboarding_fee_policy"),
        "onboarding_fee_waived": ctx.get("onboarding_fee_waived"),
    }


def build_invite_distribution(
    invite_doc: Dict[str, Any],
    *,
    base_url: str,
    plan_code: str,
) -> Dict[str, Any]:
    """Shareable invite URL and message from commercial truth (no hardcoded months)."""
    code = str(invite_doc.get("code") or "")
    base = (base_url or "").rstrip("/")
    commercial = build_invite_commercial_summary(invite_doc, plan_code=plan_code)
    params = f"invite={code}&plan={plan_code}"
    invite_url = f"{base}/intake?{params}"
    summary = commercial.get("commercial_summary") or ""
    message_template = (
        f"You're invited to join Compliance Vault Pro with our Founding Pilot programme.\n\n"
        f"{summary}\n\n"
        f"Use invite code: {code}\n"
        f"Start here: {invite_url}\n\n"
        f"Complete secure checkout to activate your account."
    )
    return {
        "invite_code": code,
        "invite_url": invite_url,
        "plan_code": plan_code,
        "commercial_summary": summary,
        "message_template": message_template,
        "copy_block": f"{summary}\n\nCode: {code}\n{invite_url}",
    }


async def preview_stripe_coupon_validation(invite_fields: Dict[str, Any]) -> Dict[str, Any]:
    from services.pilot_stripe_coupon_validation import (
        PilotStripeCouponValidationError,
        validate_pilot_stripe_discount_config,
    )

    try:
        await validate_pilot_stripe_discount_config(
            stripe_coupon_id=invite_fields.get("stripe_coupon_id"),
            stripe_promotion_code_id=invite_fields.get("stripe_promotion_code_id"),
            discount_mode=invite_fields.get("discount_mode") or "coupon",
            invite_fields=invite_fields,
        )
    except PilotStripeCouponValidationError as e:
        return {
            "valid": False,
            "message": str(e),
            "details": list(e.details or []),
        }

    import stripe

    coupon_id = (invite_fields.get("stripe_coupon_id") or "").strip()
    promo_id = (invite_fields.get("stripe_promotion_code_id") or "").strip()
    mode = str(invite_fields.get("discount_mode") or "coupon").lower()
    coupon: Dict[str, Any] = {}
    try:
        if mode == PilotInviteDiscountMode.PROMOTION_CODE.value and promo_id:
            promo = stripe.PromotionCode.retrieve(promo_id, expand=["coupon"])
            coupon = promo.get("coupon") or {}
            if isinstance(coupon, str):
                coupon = stripe.Coupon.retrieve(coupon)
        elif coupon_id:
            coupon = stripe.Coupon.retrieve(coupon_id)
        if hasattr(coupon, "to_dict"):
            coupon = coupon.to_dict()
    except Exception as ex:
        return {"valid": False, "message": str(ex), "details": []}

    cfg = discount_config_from_doc(invite_fields)
    return {
        "valid": True,
        "message": "Stripe coupon matches invite configuration.",
        "coupon": {
            "id": coupon.get("id"),
            "valid": coupon.get("valid", True),
            "percent_off": coupon.get("percent_off"),
            "duration": coupon.get("duration"),
            "duration_in_months": coupon.get("duration_in_months"),
        },
        "invite_expects": {
            "discount_percent": cfg["discount_percent"],
            "discount_duration": cfg["discount_duration"],
            "discount_duration_in_months": cfg["discount_duration_in_months"],
        },
    }


def get_pilot_invite_operational_config() -> Dict[str, Any]:
    from services.stripe_mode_authority import build_stripe_operational_config

    cfg = build_stripe_operational_config()
    cfg.update(
        {
            "intake_invite_query_param": "invite",
            "intake_plan_query_param": "plan",
            "coupon_guidance": {
                "repeating_pilot": "Create percent_off coupon with duration=repeating and duration_in_months matching invite pilot duration.",
                "payment_method": "Repeating pilots use payment_method_collection=always at checkout.",
                "onboarding_fee": "Waived onboarding omits setup line item from checkout when policy=waived.",
                "mode_live_testing": "In live mode, use 100% pilot coupons for safe end-to-end testing — never test-mode coupons.",
                "mode_test": "Use STRIPE_MODE=test in staging/dev with test Dashboard objects only.",
            },
            "deferred_onboarding_public": False,
        }
    )
    return cfg


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
    res = _enrich_invite_row(res)

    stripe_fields_changed = any(
        x is not None
        for x in (
            body.stripe_coupon_id,
            body.stripe_promotion_code_id,
            body.discount_mode,
            body.discount_percent,
            body.discount_duration,
            body.discount_duration_in_months,
        )
    )
    if stripe_fields_changed and (res.get("stripe_coupon_id") or res.get("stripe_promotion_code_id")):
        from services.pilot_stripe_coupon_validation import (
            PilotStripeCouponValidationError,
            validate_pilot_stripe_discount_config,
        )

        try:
            await validate_pilot_stripe_discount_config(
                stripe_coupon_id=res.get("stripe_coupon_id"),
                stripe_promotion_code_id=res.get("stripe_promotion_code_id"),
                discount_mode=res.get("discount_mode") or "coupon",
                invite_fields=res,
            )
        except PilotStripeCouponValidationError as e:
            detail = "; ".join(e.details) if e.details else str(e)
            raise ValueError(detail) from e

    if body.onboarding_fee_policy == PilotOnboardingFeePolicy.DEFERRED:
        raise ValueError(_DEFERRED_EXPERIMENTAL_MSG)

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
