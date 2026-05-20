"""
Founding pilot invite codes — validation, Stripe discount wiring, idempotent redemption.

Stripe Checkout remains authoritative for provisioning; this service never grants entitlements directly.
Repeating discounts (e.g. 100% for 2 months) are implemented via Stripe-native coupons (duration=repeating);
the platform tags lifecycle state and records paid conversion on non-zero invoice.paid events.
"""
from __future__ import annotations

import calendar
import html
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from database import database
from models.pilot_invite import (
    PilotCampaignState,
    PilotCampaignStatus,
    PilotInviteCodeCreate,
    PilotInviteCodeType,
    PilotInviteCodeUpdate,
    PilotInviteDiscountDuration,
    PilotInviteDiscountMode,
    PilotLaunchVisibility,
    PilotInvitePublicError,
    PilotOnboardingFeePolicy,
    PilotInviteStatus,
    PilotInviteValidateResponse,
)

_DEFERRED_EXPERIMENTAL_MSG = (
    "onboarding_fee_policy=deferred is experimental and requires owner approval"
)
from services.pilot_onboarding_fee import onboarding_policy_from_invite
from services.pilot_invite_code_governance import (
    assert_abuse_rules,
    assert_public_entry_and_campaign,
    invite_code_type,
    record_validation_attempt,
)
from services.plan_registry import PlanCode, plan_registry, _get_stripe_mode

logger = logging.getLogger(__name__)

COL_CODES = "pilot_invite_codes"
COL_REDEMPTIONS = "pilot_invite_redemptions"
COL_CAMPAIGN_SNAPSHOTS = "pilot_redeemed_campaign_snapshots"
COL_SEND_ATTEMPTS = "pilot_invite_send_attempts"

_PUBLIC_CODE_TYPES = frozenset(
    {
        PilotInviteCodeType.PUBLIC_PROMO.value,
        PilotInviteCodeType.REFERRAL.value,
        PilotInviteCodeType.PARTNER.value,
    }
)

_CAMPAIGN_MUTATION_FIELDS = frozenset(
    {
        "applies_to_plan_codes",
        "max_uses_per_account",
        "stripe_coupon_id",
        "stripe_promotion_code_id",
        "discount_mode",
        "discount_type",
        "discount_percent",
        "discount_duration",
        "discount_duration_in_months",
        "waive_onboarding_fee",
        "onboarding_fee_policy",
        "onboarding_fee_discount_percent",
    }
)

_PILOT_INVITE_ABUSE_AUDIT_CODES = frozenset(
    {
        "PILOT_INVITE_NOT_FIRST_TIME_CUSTOMER",
        "PILOT_INVITE_EMAIL_DOMAIN_NOT_ALLOWED",
        "PILOT_INVITE_ALREADY_REDEEMED_EMAIL",
        "PILOT_INVITE_ALREADY_REDEEMED_CUSTOMER",
        "PILOT_INVITE_ACCOUNT_LIMIT_EXCEEDED",
        "PILOT_INVITE_DAILY_LIMIT_EXCEEDED",
        "PILOT_INVITE_ALREADY_REDEEMED_PAYMENT_METHOD",
    }
)

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
    from services.pilot_invite_code_generation import normalize_invite_code as _norm

    return _norm(raw=raw, strict=True)


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


def _code_type_value(doc: Dict[str, Any]) -> str:
    raw = str(doc.get("code_type") or PilotInviteCodeType.PRIVATE_INVITE.value).strip().lower()
    return raw if raw in {e.value for e in PilotInviteCodeType} else PilotInviteCodeType.PRIVATE_INVITE.value


def _campaign_state_from_doc(doc: Dict[str, Any]) -> str:
    state = str(doc.get("campaign_state") or "").strip().lower()
    if state in {e.value for e in PilotCampaignState}:
        return state
    legacy = str(doc.get("campaign_status") or "").strip().lower()
    if legacy == PilotCampaignStatus.ACTIVE.value:
        return PilotCampaignState.ACTIVE.value
    if legacy == PilotCampaignStatus.PAUSED.value:
        return PilotCampaignState.PAUSED.value
    if legacy == PilotCampaignStatus.ENDED.value:
        return PilotCampaignState.EXPIRED.value
    return PilotCampaignState.DRAFT.value


def _campaign_status_from_state(state: str, *, code_type: str) -> str:
    if code_type == PilotInviteCodeType.PRIVATE_INVITE.value:
        return PilotCampaignStatus.NOT_APPLICABLE.value
    if state == PilotCampaignState.ACTIVE.value:
        return PilotCampaignStatus.ACTIVE.value
    if state == PilotCampaignState.PAUSED.value:
        return PilotCampaignStatus.PAUSED.value
    if state in (PilotCampaignState.EXPIRED.value, PilotCampaignState.ARCHIVED.value):
        return PilotCampaignStatus.ENDED.value
    return PilotCampaignStatus.DRAFT.value


def _default_launch_visibility(code_type: str, public_entry_enabled: bool) -> str:
    if code_type == PilotInviteCodeType.INTERNAL_TEST.value:
        return PilotLaunchVisibility.INTERNAL.value
    if code_type in _PUBLIC_CODE_TYPES:
        return PilotLaunchVisibility.PUBLIC.value if public_entry_enabled else PilotLaunchVisibility.RESTRICTED.value
    return PilotLaunchVisibility.PRIVATE.value


def _apply_campaign_governance_defaults(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalised campaign config candidate before validation/persistence."""
    out = dict(doc)
    ct = _code_type_value(out)
    out["code_type"] = ct
    out["campaign_config_version"] = int(out.get("campaign_config_version") or 1)
    out["campaign_state"] = _campaign_state_from_doc(out)
    out["campaign_status"] = _campaign_status_from_state(out["campaign_state"], code_type=ct)
    if not out.get("analytics_family"):
        out["analytics_family"] = ct
    if not out.get("launch_visibility"):
        out["launch_visibility"] = _default_launch_visibility(ct, bool(out.get("public_entry_enabled")))

    if ct == PilotInviteCodeType.INTERNAL_TEST.value:
        max_uses = int(out.get("max_uses") or 5)
        if max_uses == 1:
            max_uses = 5
        if max_uses > 10:
            raise ValueError("internal_test campaigns are capped at max_uses=10")
        out.update(
            {
                "max_uses": max_uses,
                "public_entry_enabled": False,
                "is_publicly_enterable": False,
                "launch_visibility": PilotLaunchVisibility.INTERNAL.value,
                "analytics_family": "internal_test",
                "internal_live_test": True,
                "onboarding_fee_policy": PilotOnboardingFeePolicy.WAIVED.value,
                "waive_onboarding_fee": True,
            }
        )
    elif ct == PilotInviteCodeType.PRIVATE_INVITE.value:
        out["launch_visibility"] = out.get("launch_visibility") or PilotLaunchVisibility.PRIVATE.value
        out["public_entry_enabled"] = False
    return out


def _validate_campaign_governance(doc: Dict[str, Any]) -> None:
    ct = _code_type_value(doc)
    state = _campaign_state_from_doc(doc)
    visibility = str(doc.get("launch_visibility") or _default_launch_visibility(ct, bool(doc.get("public_entry_enabled"))))
    if visibility not in {e.value for e in PilotLaunchVisibility}:
        raise ValueError("Invalid launch_visibility")
    if ct == PilotInviteCodeType.INTERNAL_TEST.value:
        if bool(doc.get("public_entry_enabled")) or bool(doc.get("is_publicly_enterable")):
            raise ValueError("internal_test campaigns cannot be publicly enterable")
        if visibility != PilotLaunchVisibility.INTERNAL.value:
            raise ValueError("internal_test campaigns must use launch_visibility=internal")
        if str(doc.get("analytics_family") or "") != "internal_test":
            raise ValueError("internal_test campaigns must use analytics_family=internal_test")
        if str(doc.get("onboarding_fee_policy") or "") != PilotOnboardingFeePolicy.WAIVED.value:
            raise ValueError("internal_test campaigns must waive onboarding")
        if int(doc.get("max_uses") or 0) > 10:
            raise ValueError("internal_test campaigns are capped at max_uses=10")
    if ct in _PUBLIC_CODE_TYPES and bool(doc.get("public_entry_enabled")) and state != PilotCampaignState.ACTIVE.value:
        raise ValueError("public_entry_enabled requires campaign_state=active")
    if doc.get("max_uses_per_account") is not None and int(doc.get("max_uses_per_account") or 0) < 1:
        raise ValueError("max_uses_per_account must be >= 1 when set")


async def _validate_invite_candidate_for_persistence(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Validate complete invite/campaign candidate before writing it."""
    candidate = _apply_campaign_governance_defaults(doc)
    _validate_campaign_governance(candidate)
    if candidate.get("onboarding_fee_policy") == PilotOnboardingFeePolicy.DEFERRED.value:
        raise ValueError(_DEFERRED_EXPERIMENTAL_MSG)
    cfg = discount_config_from_doc(candidate)
    if cfg["discount_duration"] == PilotInviteDiscountDuration.REPEATING.value and cfg["discount_duration_in_months"] < 1:
        raise ValueError("discount_duration_in_months is required for repeating discounts")
    if candidate.get("stripe_coupon_id") or candidate.get("stripe_promotion_code_id"):
        from services.pilot_stripe_coupon_validation import (
            PilotStripeCouponValidationError,
            validate_pilot_stripe_discount_config,
        )

        try:
            await validate_pilot_stripe_discount_config(
                stripe_coupon_id=candidate.get("stripe_coupon_id"),
                stripe_promotion_code_id=candidate.get("stripe_promotion_code_id"),
                discount_mode=candidate.get("discount_mode") or "coupon",
                invite_fields=candidate,
            )
        except PilotStripeCouponValidationError as e:
            detail = "; ".join(e.details) if e.details else str(e)
            raise ValueError(detail) from e
    return candidate


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
        code_type=invite_code_type(doc),
        campaign_name=(doc.get("campaign_name") or None) or None,
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


def _resolved_plan_code(plan_code: str) -> str:
    raw = str(plan_code or "").strip()
    legacy = {
        "PLAN_1": PlanCode.PLAN_1_SOLO.value,
        "PLAN_2_5": PlanCode.PLAN_2_PORTFOLIO.value,
        "PLAN_6_15": PlanCode.PLAN_3_PRO.value,
    }
    if raw in legacy:
        return legacy[raw]
    try:
        return PlanCode(raw).value
    except ValueError:
        raise ValueError("Unsupported plan_code")


def assert_invite_distribution_allowed(invite_doc: Dict[str, Any], *, plan_code: str) -> str:
    """Validate an invite can be shared/sent for the selected plan without consuming usage."""
    if not invite_doc:
        raise ValueError("Invite code not found")
    eff = _effective_status(invite_doc)
    if eff != PilotInviteStatus.ACTIVE.value:
        raise ValueError("Invite code is not active")
    state = _campaign_state_from_doc(invite_doc)
    if state in (PilotCampaignState.EXPIRED.value, PilotCampaignState.ARCHIVED.value):
        raise ValueError("Invite campaign is not active")
    resolved = _resolved_plan_code(plan_code)
    if not _plan_allowed(invite_doc, resolved):
        raise ValueError("Invite code is not valid for the selected plan")
    return resolved


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
    entry_channel: str = "manual",
    client_id: Optional[str] = None,
    log_audit: bool = True,
    record_attempts: bool = True,
) -> Tuple[Dict[str, Any], PilotInviteValidateResponse]:
    """
    Validate invite code. When for_checkout=True, also requires Stripe discount IDs configured.

    entry_channel: ``manual`` (typed) vs ``link`` (invite URL) — governs public promo manual entry rules.

    Returns (invite_doc, response). Raises PilotInvitePublicError on failure.
    """
    from models import AuditAction, UserRole
    from utils.audit import create_audit_log

    db = database.get_db()
    ec_raw = (entry_channel or "manual").strip().lower()
    entry_ch = ec_raw if ec_raw in ("manual", "link") else "manual"
    normalized = normalize_invite_code(code)
    invite_code_id: Optional[str] = None

    async def _attempt(outcome: str, reason_code: Optional[str]) -> None:
        if not record_attempts:
            return
        await record_validation_attempt(
            db,
            code_normalized=normalized or "",
            invite_code_id=invite_code_id,
            outcome=outcome,
            reason_code=reason_code,
            entry_channel=entry_ch,
            email=email,
            client_id=client_id,
        )

    async def _audit_validation_failed(exc: PilotInvitePublicError) -> None:
        if not log_audit:
            return
        action = (
            AuditAction.PILOT_INVITE_ABUSE_BLOCKED
            if exc.error_code in _PILOT_INVITE_ABUSE_AUDIT_CODES
            else AuditAction.PILOT_INVITE_CODE_VALIDATION_FAILED
        )
        meta: Dict[str, Any] = {
            "error_code": exc.error_code,
            "entry_channel": entry_ch,
            "plan_code": plan_code,
            "invite_code_id": invite_code_id,
        }
        if normalized:
            meta["code_masked"] = (normalized[:4] + "***") if len(normalized) > 4 else "****"
        try:
            await create_audit_log(
                action=action,
                actor_role=UserRole.SYSTEM,
                client_id=client_id,
                resource_type="pilot_invite_code",
                resource_id=invite_code_id,
                metadata=meta,
            )
        except Exception as audit_ex:
            logger.warning("pilot invite validation audit failed: %s", audit_ex)

    async def _audit_validation_ok(doc: Dict[str, Any]) -> None:
        if not log_audit:
            return
        try:
            await create_audit_log(
                action=AuditAction.PILOT_INVITE_CODE_VALIDATED,
                actor_role=UserRole.SYSTEM,
                client_id=client_id,
                resource_type="pilot_invite_code",
                resource_id=str(doc.get("invite_code_id") or ""),
                metadata={
                    "entry_channel": entry_ch,
                    "plan_code": plan_code,
                    "code_type": invite_code_type(doc),
                },
            )
        except Exception as audit_ex:
            logger.warning("pilot invite validation audit failed: %s", audit_ex)

    if not normalized:
        await _attempt("failed", "PILOT_INVITE_INVALID")
        exc = PilotInvitePublicError("PILOT_INVITE_INVALID", _MSG_INVALID)
        await _audit_validation_failed(exc)
        raise exc

    doc = await db[COL_CODES].find_one({"code": normalized}, {"_id": 0})
    if not doc:
        await _attempt("failed", "PILOT_INVITE_INVALID")
        exc = PilotInvitePublicError("PILOT_INVITE_INVALID", _MSG_INVALID)
        await _audit_validation_failed(exc)
        raise exc

    invite_code_id = str(doc.get("invite_code_id") or "") or None

    eff = _effective_status(doc)
    if eff == PilotInviteStatus.DISABLED.value:
        await _attempt("failed", "PILOT_INVITE_INVALID")
        exc = PilotInvitePublicError("PILOT_INVITE_INVALID", _MSG_INVALID)
        await _audit_validation_failed(exc)
        raise exc
    if eff == PilotInviteStatus.EXPIRED.value:
        await _attempt("failed", "PILOT_INVITE_EXPIRED")
        exc = PilotInvitePublicError("PILOT_INVITE_EXPIRED", _MSG_EXPIRED)
        await _audit_validation_failed(exc)
        raise exc

    used = int(doc.get("used_count") or 0)
    max_uses = int(doc.get("max_uses") or 1)
    if used >= max_uses:
        await _attempt("failed", "PILOT_INVITE_EXHAUSTED")
        exc = PilotInvitePublicError("PILOT_INVITE_EXHAUSTED", _MSG_EXHAUSTED)
        await _audit_validation_failed(exc)
        raise exc

    if not _plan_allowed(doc, plan_code):
        await _attempt("failed", "PILOT_INVITE_PLAN_NOT_ELIGIBLE")
        exc = PilotInvitePublicError("PILOT_INVITE_PLAN_NOT_ELIGIBLE", _MSG_PLAN)
        await _audit_validation_failed(exc)
        raise exc

    if not _email_matches(doc, email):
        await _attempt("failed", "PILOT_INVITE_EMAIL_NOT_ELIGIBLE")
        exc = PilotInvitePublicError("PILOT_INVITE_EMAIL_NOT_ELIGIBLE", _MSG_EMAIL)
        await _audit_validation_failed(exc)
        raise exc

    try:
        assert_public_entry_and_campaign(doc, entry_channel=entry_ch)
    except PilotInvitePublicError as e:
        await _attempt("failed", e.error_code)
        await _audit_validation_failed(e)
        raise

    try:
        await assert_abuse_rules(db, doc, email=email, client_id=client_id)
    except PilotInvitePublicError as e:
        await _attempt("failed", e.error_code)
        await _audit_validation_failed(e)
        raise

    if for_checkout:
        _require_stripe_discount_configured(doc)
        _validate_discount_stripe_alignment(doc)
        _reject_public_deferred_onboarding(doc)

    resp = _build_validate_response(doc, plan_code)
    await _attempt("success", None)
    await _audit_validation_ok(doc)
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


def build_redeemed_campaign_snapshot(
    invite_doc: Dict[str, Any],
    *,
    client_id: Optional[str],
    checkout_session_id: Optional[str],
    plan_code: Optional[str],
    redeemed_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Immutable account-level truth captured from the campaign at redemption time."""
    cfg = discount_config_from_doc(invite_doc)
    ct = _code_type_value(invite_doc)
    when = redeemed_at or _utc_now()
    snapshot_id = f"{invite_doc.get('invite_code_id') or invite_doc.get('code')}:{checkout_session_id or client_id or when.isoformat()}"
    return {
        "snapshot_id": snapshot_id,
        "client_id": client_id,
        "checkout_session_id": checkout_session_id,
        "invite_code_id": invite_doc.get("invite_code_id"),
        "redeemed_code": invite_doc.get("code"),
        "code_type": ct,
        "campaign_name": invite_doc.get("campaign_name"),
        "campaign_config_version": int(invite_doc.get("campaign_config_version") or 1),
        "campaign_state_at_redemption": _campaign_state_from_doc(invite_doc),
        "discount_duration": cfg["discount_duration"],
        "discount_duration_in_months": cfg["discount_duration_in_months"] or None,
        "discount_percent": cfg["discount_percent"],
        "onboarding_fee_policy": str(invite_doc.get("onboarding_fee_policy") or PilotOnboardingFeePolicy.WAIVED.value),
        "allowed_plan": plan_code,
        "applies_to_plan_codes": list(invite_doc.get("applies_to_plan_codes") or []),
        "stripe_coupon_id": invite_doc.get("stripe_coupon_id"),
        "stripe_promotion_code_id": invite_doc.get("stripe_promotion_code_id"),
        "analytics_family": invite_doc.get("analytics_family") or ct,
        "launch_visibility": invite_doc.get("launch_visibility")
        or _default_launch_visibility(ct, bool(invite_doc.get("public_entry_enabled"))),
        "internal_live_test": bool(invite_doc.get("internal_live_test") or ct == PilotInviteCodeType.INTERNAL_TEST.value),
        "redeemed_at": when,
        "completed_at": when,
        "created_at": when,
    }


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
    redemption_email: Optional[str] = None,
    stripe_payment_method_id: Optional[str] = None,
    plan_code: Optional[str] = None,
) -> bool:
    """Create pending redemption (idempotent on checkout_session_id). Usage counted after provisioning."""
    if not checkout_session_id:
        return False
    db = database.get_db()
    now = _utc_now()
    from services.pilot_invite_code_governance import normalize_email as _norm_em

    iid = invite_doc.get("invite_code_id")
    fresh = None
    if iid:
        fresh = await db[COL_CODES].find_one({"invite_code_id": iid}, {"_id": 0})
    doc = fresh or invite_doc
    em = _norm_em(redemption_email) if redemption_email else None
    pm = (stripe_payment_method_id or "").strip() or None
    try:
        await assert_abuse_rules(db, doc, email=em, client_id=client_id, stripe_payment_method_id=pm)
    except PilotInvitePublicError as e:
        logger.warning(
            "Pilot redemption blocked at webhook (abuse/eligibility) client_id=%s session=%s code=%s err=%s",
            client_id,
            checkout_session_id,
            doc.get("code"),
            e.error_code,
        )
        try:
            from models import AuditAction, UserRole
            from utils.audit import create_audit_log

            await create_audit_log(
                action=AuditAction.PILOT_INVITE_ABUSE_BLOCKED,
                actor_role=UserRole.SYSTEM,
                client_id=client_id,
                resource_type="pilot_invite_code",
                resource_id=str(doc.get("invite_code_id") or ""),
                metadata={
                    "error_code": e.error_code,
                    "checkout_session_id": checkout_session_id,
                    "stage": "register_pending_redemption",
                },
            )
        except Exception as audit_ex:
            logger.warning("pilot redemption abuse audit failed: %s", audit_ex)
        return False

    doc_insert: Dict[str, Any] = {
        "redemption_id": str(uuid.uuid4()),
        "invite_code_id": invite_doc.get("invite_code_id"),
        "code": invite_doc.get("code"),
        "program_type": invite_doc.get("program_type") or "FOUNDING_PILOT",
        "client_id": client_id,
        "checkout_session_id": checkout_session_id,
        "stripe_event_id": stripe_event_id,
        "stripe_subscription_id": stripe_subscription_id,
        "plan_code": plan_code,
        "redemption_email": em or None,
        "stripe_payment_method_id": pm,
        "campaign_config_version": int(doc.get("campaign_config_version") or 1),
        "analytics_family": doc.get("analytics_family") or invite_code_type(doc),
        "code_type": invite_code_type(doc),
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    try:
        await db[COL_REDEMPTIONS].insert_one(doc_insert)
        return True
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            logger.info("Pilot redemption already registered for session %s", checkout_session_id)
            return True
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
    lifecycle_invite_doc = {
        **invite_doc,
        "selected_plan_code": plan_code,
        "plan_code": plan_code,
    }
    await create_from_invite_checkout(
        client_id=client_id,
        invite_doc=lifecycle_invite_doc,
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

    from services.pilot_redemption_lifecycle import PilotRedemptionStatus

    redeemed_status = PilotRedemptionStatus.REDEEMED.value
    redemption = await db[COL_REDEMPTIONS].find_one_and_update(
        {
            "checkout_session_id": checkout_session_id,
            "status": {"$in": [PilotRedemptionStatus.PENDING.value, "pending"]},
        },
        {"$set": {"status": redeemed_status, "completed_at": now, "updated_at": now}},
    )
    if not redemption:
        done = await db[COL_REDEMPTIONS].find_one(
            {
                "checkout_session_id": checkout_session_id,
                "status": {"$in": [redeemed_status, PilotRedemptionStatus.COMPLETED.value, "completed"]},
            },
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
    try:
        snapshot = build_redeemed_campaign_snapshot(
            updated,
            client_id=redemption.get("client_id"),
            checkout_session_id=checkout_session_id,
            plan_code=redemption.get("plan_code"),
            redeemed_at=now,
        )
        await db[COL_CAMPAIGN_SNAPSHOTS].update_one(
            {"checkout_session_id": checkout_session_id},
            {"$setOnInsert": snapshot},
            upsert=True,
        )
        await db.clients.update_one(
            {"client_id": redemption.get("client_id")},
            {
                "$set": {
                    "pilot_redeemed_campaign_snapshot_id": snapshot["snapshot_id"],
                    "pilot_redeemed_campaign_snapshot": snapshot,
                    "pilot_campaign_config_version": snapshot["campaign_config_version"],
                    "pilot_analytics_family": snapshot["analytics_family"],
                    "pilot_launch_visibility": snapshot["launch_visibility"],
                    "pilot_code_type": snapshot["code_type"],
                }
            },
        )
    except Exception as snap_ex:
        logger.warning("pilot redeemed campaign snapshot failed session=%s: %s", checkout_session_id, snap_ex)
    try:
        from models import AuditAction, UserRole
        from utils.audit import create_audit_log

        await create_audit_log(
            action=AuditAction.PILOT_INVITE_REDEMPTION_COMPLETED,
            actor_role=UserRole.SYSTEM,
            client_id=redemption.get("client_id"),
            resource_type="pilot_invite_code",
            resource_id=str(invite_code_id),
            metadata={
                "checkout_session_id": checkout_session_id,
                "code": updated.get("code") or redemption.get("code"),
            },
        )
    except Exception as audit_ex:
        logger.warning("pilot redemption completed audit failed: %s", audit_ex)
    return True


# --- Admin CRUD ---


async def create_invite_code(body: PilotInviteCodeCreate) -> Dict[str, Any]:
    from services.pilot_invite_code_generation import (
        InviteCodeValidationError,
        assert_manual_code_allowed,
        generate_unique_invite_code,
    )

    db = database.get_db()
    ct = body.code_type.value
    if body.auto_generate or not (body.code or "").strip():
        try:
            normalized = await generate_unique_invite_code(
                db,
                code_type=ct,
                prefix=(body.metadata or {}).get("generation_prefix") or "",
                variant=(body.metadata or {}).get("generation_variant") or "",
                campaign_name=body.campaign_name or "",
            )
        except InviteCodeValidationError as e:
            raise ValueError(str(e)) from e
    else:
        try:
            normalized = assert_manual_code_allowed(body.code)
        except InviteCodeValidationError as e:
            raise ValueError(str(e)) from e
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
        "code_type": body.code_type.value,
        "is_publicly_enterable": bool(body.is_publicly_enterable),
        "public_entry_enabled": bool(body.public_entry_enabled),
        "campaign_name": (body.campaign_name or "").strip() or None,
        "public_description": (body.public_description or "").strip() or None,
        "campaign_status": body.campaign_status.value,
        "campaign_state": body.campaign_state.value,
        "launch_visibility": body.launch_visibility.value,
        "campaign_config_version": int(body.campaign_config_version or 1),
        "campaign_locked_at": body.campaign_locked_at,
        "campaign_launched_at": body.campaign_launched_at,
        "analytics_family": (body.analytics_family or "").strip().lower() or None,
        "max_uses_per_account": body.max_uses_per_account,
        "internal_live_test": bool(body.internal_live_test),
        "first_time_customer_only": bool(body.first_time_customer_only),
        "one_redemption_per_email": bool(body.one_redemption_per_email),
        "one_redemption_per_customer": bool(body.one_redemption_per_customer),
        "one_redemption_per_payment_method": bool(body.one_redemption_per_payment_method),
        "allowed_email_domains": list(body.allowed_email_domains or []),
        "blocked_email_domains": list(body.blocked_email_domains or []),
        "max_uses_per_day": body.max_uses_per_day,
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
    doc = await _validate_invite_candidate_for_persistence(doc)

    await db[COL_CODES].insert_one(doc)
    doc.pop("_id", None)
    return doc


def suggest_invite_code(
    *,
    prefix: str = "FOUNDING",
    variant: str = "",
    code_type: str = "private_invite",
    campaign_name: str = "",
) -> str:
    """Non-authoritative preview candidate (prefer generate_unique_invite_code for persistence)."""
    from services.pilot_invite_code_generation import generate_code_candidate

    return generate_code_candidate(
        code_type=code_type,
        prefix=prefix,
        variant=variant,
        campaign_name=campaign_name,
    )


async def generate_invite_code_authoritative(
    db,
    *,
    code_type: str = "private_invite",
    prefix: str = "",
    variant: str = "",
    campaign_name: str = "",
) -> Dict[str, Any]:
    """Allocate a unique code (admin generate action)."""
    from services.pilot_invite_code_generation import (
        InviteCodeValidationError,
        generate_unique_invite_code,
        generation_profile_for_type,
    )

    try:
        code = await generate_unique_invite_code(
            db,
            code_type=code_type,
            prefix=prefix,
            variant=variant,
            campaign_name=campaign_name,
        )
    except InviteCodeValidationError as e:
        raise ValueError(str(e)) from e
    return {
        "code": code,
        "normalized": code,
        "code_type": code_type,
        "profile": generation_profile_for_type(code_type),
    }


def _enrich_invite_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(doc)
    ct = _code_type_value(doc)
    doc["code_type"] = ct
    doc["campaign_state"] = _campaign_state_from_doc(doc)
    doc["launch_visibility"] = doc.get("launch_visibility") or _default_launch_visibility(
        ct, bool(doc.get("public_entry_enabled"))
    )
    doc["analytics_family"] = doc.get("analytics_family") or ct
    doc["effective_status"] = _effective_status(doc)
    doc["remaining_uses"] = max(0, int(doc.get("max_uses") or 0) - int(doc.get("used_count") or 0))
    doc["max_uses_total"] = int(doc.get("max_uses") or 0)
    return doc


async def list_invite_codes(
    *,
    limit: int = 200,
    status_filter: Optional[str] = None,
    onboarding_policy: Optional[str] = None,
    duration_months: Optional[int] = None,
    plan_code: Optional[str] = None,
    code_type: Optional[str] = None,
    exhausted_only: bool = False,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    mongo_q: Dict[str, Any] = {}
    if code_type:
        mongo_q["code_type"] = str(code_type).strip().lower()
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


async def list_invite_validation_attempts(code: str, *, limit: int = 500) -> List[Dict[str, Any]]:
    from services.pilot_invite_code_governance import COL_ATTEMPTS

    db = database.get_db()
    normalized = normalize_invite_code(code)
    invite = await get_invite_code(normalized)
    if not invite:
        return []
    iid = invite.get("invite_code_id")
    filt: Dict[str, Any] = (
        {"$or": [{"code": normalized}, {"invite_code_id": iid}]} if iid else {"code": normalized}
    )
    cur = db[COL_ATTEMPTS].find(filt, {"_id": 0}).sort("created_at", -1).limit(limit)
    return [row async for row in cur]


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
    resolved_plan = assert_invite_distribution_allowed(invite_doc, plan_code=plan_code)
    commercial = build_invite_commercial_summary(invite_doc, plan_code=resolved_plan)
    params = urlencode({"invite": code, "plan": resolved_plan})
    invite_url = f"{base}/intake/start?{params}"
    summary = commercial.get("commercial_summary") or ""
    expiry = invite_doc.get("expires_at")
    expiry_line = ""
    if expiry:
        expiry_line = f"\nThis invite expires on {expiry.date().isoformat() if isinstance(expiry, datetime) else expiry}."
    usage_line = ""
    max_uses = invite_doc.get("max_uses")
    remaining = invite_doc.get("remaining_uses")
    if max_uses:
        usage_line = f"\nUsage is limited; {remaining if remaining is not None else max_uses} redemption(s) remain."
    message_template = (
        f"You're invited to join Compliance Vault Pro with our Founding Pilot programme.\n\n"
        f"{summary}\n\n"
        f"Use invite code: {code}\n"
        f"Start here: {invite_url}{expiry_line}{usage_line}\n\n"
        f"Complete secure checkout to activate your account."
    )
    email_style_message = (
        f"Hello,\n\n"
        f"You've been invited to start founding pilot access for Compliance Vault Pro.\n\n"
        f"{summary}\n\n"
        f"Invite code: {code}\n"
        f"Start your founding pilot access: {invite_url}{expiry_line}{usage_line}\n\n"
        f"After the pilot, your selected subscription continues at the standard monthly rate unless cancelled before renewal."
    )
    return {
        "invite_code": code,
        "invite_url": invite_url,
        "canonical_intake_path": "/intake/start",
        "legacy_intake_path": "/intake",
        "plan_code": resolved_plan,
        "commercial_summary": summary,
        "message_template": message_template,
        "plain_message": message_template,
        "email_style_message": email_style_message,
        "copy_block": f"{summary}\n\nCode: {code}\n{invite_url}",
    }


def render_pilot_invite_email(
    invite_doc: Dict[str, Any],
    distribution: Dict[str, Any],
    *,
    recipient_name: Optional[str] = None,
    personal_note: Optional[str] = None,
) -> Dict[str, str]:
    """Render founding pilot invite email bodies. Delivery remains in notification_orchestrator."""
    code = str(distribution.get("invite_code") or invite_doc.get("code") or "")
    invite_url = str(distribution.get("invite_url") or "")
    summary = str(distribution.get("commercial_summary") or "")
    name = (recipient_name or "").strip()
    greeting = f"Hello {html.escape(name)}," if name else "Hello,"
    note = (personal_note or "").strip()
    safe_note = html.escape(note).replace("\n", "<br />") if note else ""
    expiry = invite_doc.get("expires_at")
    expiry_text = ""
    if expiry:
        expiry_text = f"This invite expires on {expiry.date().isoformat() if isinstance(expiry, datetime) else expiry}."
    max_uses = invite_doc.get("max_uses")
    remaining = invite_doc.get("remaining_uses")
    usage_text = ""
    if max_uses:
        usage_text = f"Usage is limited; {remaining if remaining is not None else max_uses} redemption(s) remain."
    html_body = f"""<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #17233c; line-height: 1.5; margin: 0; padding: 24px; background: #f8fafc;">
    <div style="max-width: 640px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 28px;">
      <p>{greeting}</p>
      <p>You have been invited to start founding pilot access for <strong>Compliance Vault Pro</strong>.</p>
      <p>{html.escape(summary)}</p>
      {'<p style="border-left: 3px solid #0f766e; padding-left: 12px;">' + safe_note + '</p>' if safe_note else ''}
      <p><strong>Invite code:</strong> <span style="font-family: monospace;">{html.escape(code)}</span></p>
      <p style="margin: 28px 0;">
        <a href="{html.escape(invite_url)}" style="background: #0f766e; color: #ffffff; padding: 12px 18px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: 700;">
          Start your founding pilot access
        </a>
      </p>
      <p>If the button does not work, copy and paste this link into your browser:</p>
      <p><a href="{html.escape(invite_url)}">{html.escape(invite_url)}</a></p>
      {f'<p>{html.escape(expiry_text)}</p>' if expiry_text else ''}
      {f'<p>{html.escape(usage_text)}</p>' if usage_text else ''}
      <p>After the pilot, your selected subscription continues at the standard monthly rate unless cancelled before renewal.</p>
    </div>
  </body>
</html>"""
    text_lines = [
        f"Hello {name}," if name else "Hello,",
        "",
        "You have been invited to start founding pilot access for Compliance Vault Pro.",
        "",
        summary,
    ]
    if note:
        text_lines.extend(["", note])
    text_lines.extend(
        [
            "",
            f"Invite code: {code}",
            f"Start your founding pilot access: {invite_url}",
            "",
            "If the button does not work, copy and paste the raw link above into your browser.",
        ]
    )
    if expiry_text:
        text_lines.append(expiry_text)
    if usage_text:
        text_lines.append(usage_text)
    text_lines.append("After the pilot, your selected subscription continues at the standard monthly rate unless cancelled before renewal.")
    return {
        "subject": "Your founding pilot invite to Compliance Vault Pro",
        "html": html_body,
        "text": "\n".join(text_lines),
    }


async def send_pilot_invite_email(
    invite_doc: Dict[str, Any],
    *,
    base_url: str,
    recipient_email: str,
    recipient_name: Optional[str],
    plan_code: str,
    personal_note: Optional[str],
    sent_by: Optional[str],
) -> Dict[str, Any]:
    """Send a pilot invite via notification_orchestrator and persist a send audit record."""
    db = database.get_db()
    email = (recipient_email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("recipient_email is required")
    dist = build_invite_distribution(invite_doc, base_url=base_url, plan_code=plan_code)
    rendered = render_pilot_invite_email(
        invite_doc,
        dist,
        recipient_name=recipient_name,
        personal_note=personal_note,
    )
    now = _utc_now()
    attempt_id = str(uuid.uuid4())
    audit_doc = {
        "attempt_id": attempt_id,
        "invite_code_id": invite_doc.get("invite_code_id"),
        "invite_code": invite_doc.get("code"),
        "recipient_email": email,
        "recipient_name": (recipient_name or "").strip() or None,
        "selected_plan": dist["plan_code"],
        "sent_by": sent_by,
        "sent_at": now,
        "status": "queued",
        "provider_message_id": None,
        "failure_reason": None,
        "invite_url": dist["invite_url"],
        "created_at": now,
        "updated_at": now,
    }
    await db[COL_SEND_ATTEMPTS].insert_one(dict(audit_doc))
    try:
        from services.notification_orchestrator import notification_orchestrator

        result = await notification_orchestrator.send(
            template_key="PILOT_INVITE_SEND",
            client_id=None,
            context={
                "recipient": email,
                "subject": rendered["subject"],
                "message": rendered["html"],
                "text_message": rendered["text"],
                "invite_code": invite_doc.get("code"),
                "invite_url": dist["invite_url"],
                "plan_code": dist["plan_code"],
                "commercial_summary": dist.get("commercial_summary"),
            },
            idempotency_key=f"pilot_invite_send:{invite_doc.get('code')}:{email}:{dist['plan_code']}",
            event_type="founding_pilot_invite",
        )
        provider_id = (result.details or {}).get("provider_message_id")
        status_value = "sent" if result.outcome in ("sent", "duplicate_ignored") else "failed"
        failure_reason = None
        if result.outcome not in ("sent", "duplicate_ignored"):
            failure_reason = result.error_message or result.block_reason or result.outcome
        await db[COL_SEND_ATTEMPTS].update_one(
            {"attempt_id": attempt_id},
            {
                "$set": {
                    "status": status_value,
                    "provider_message_id": provider_id,
                    "notification_message_id": result.message_id,
                    "failure_reason": failure_reason,
                    "updated_at": _utc_now(),
                }
            },
        )
        return {
            "attempt_id": attempt_id,
            "status": status_value,
            "provider_message_id": provider_id,
            "notification_message_id": result.message_id,
            "distribution": dist,
            "email_preview": rendered,
        }
    except Exception as exc:
        await db[COL_SEND_ATTEMPTS].update_one(
            {"attempt_id": attempt_id},
            {"$set": {"status": "failed", "failure_reason": str(exc), "updated_at": _utc_now()}},
        )
        raise


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
            "code_generation": {
                "authoritative_endpoint": "/api/admin/pilot-invites/generate",
                "reserved_prefixes": sorted(
                    __import__(
                        "services.pilot_invite_code_generation",
                        fromlist=["_RESERVED_PREFIXES"],
                    )._RESERVED_PREFIXES
                ),
                "charset": "A-Z (no I,O) and 2-9 (no 0,1)",
            },
        }
    )
    return cfg


async def get_invite_operational_metrics(code: str) -> Dict[str, Any]:
    """Per-code operational metrics for admin dashboards."""
    from services.pilot_invite_code_governance import COL_ATTEMPTS

    db = database.get_db()
    inv = await get_invite_code(code)
    if not inv:
        return {}
    iid = inv.get("invite_code_id")
    now = _utc_now()
    max_uses = int(inv.get("max_uses") or 1)
    used = int(inv.get("used_count") or 0)
    remaining = max(0, max_uses - used)

    val_success = await db[COL_ATTEMPTS].count_documents(
        {"invite_code_id": iid, "outcome": "success"}
    )
    val_failed = await db[COL_ATTEMPTS].count_documents(
        {"invite_code_id": iid, "outcome": "failed"}
    )
    abuse_attempts = await db[COL_ATTEMPTS].count_documents(
        {
            "invite_code_id": iid,
            "outcome": "failed",
            "reason_code": {
                "$in": list(_PILOT_INVITE_ABUSE_AUDIT_CODES),
            },
        },
    )
    from services.pilot_redemption_lifecycle import (
        PilotRedemptionStatus,
        RECOVERABLE_STATUSES,
        TERMINAL_CONSUMING_STATUSES,
    )

    pending_redemptions = await db[COL_REDEMPTIONS].count_documents(
        {
            "invite_code_id": iid,
            "status": {
                "$in": [
                    PilotRedemptionStatus.PENDING.value,
                    PilotRedemptionStatus.PAYMENT_STARTED.value,
                    "pending",
                ]
            },
        }
    )
    completed_redemptions = await db[COL_REDEMPTIONS].count_documents(
        {"invite_code_id": iid, "status": {"$in": list(TERMINAL_CONSUMING_STATUSES)}}
    )
    recoverable_redemptions = await db[COL_REDEMPTIONS].count_documents(
        {"invite_code_id": iid, "status": {"$in": list(RECOVERABLE_STATUSES)}}
    )
    stranded_redemptions = await db[COL_REDEMPTIONS].count_documents(
        {
            "invite_code_id": iid,
            "status": {
                "$in": [
                    PilotRedemptionStatus.PENDING.value,
                    PilotRedemptionStatus.PROVISIONING_FAILED.value,
                    "pending",
                ]
            },
        }
    )

    exp = inv.get("expires_at")
    nearing_expiry = False
    if exp is not None:
        if isinstance(exp, str):
            try:
                exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            except ValueError:
                exp = None
        if isinstance(exp, datetime):
            exp_utc = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
            days_left = (exp_utc - now).total_seconds() / 86400
            nearing_expiry = 0 <= days_left <= 7

    total_validations = val_success + val_failed
    return {
        "code": inv.get("code"),
        "invite_code_id": iid,
        "code_type": inv.get("code_type") or "private_invite",
        "analytics_family": inv.get("analytics_family") or inv.get("code_type") or "private_invite",
        "included_in_public_launch_analytics": (inv.get("analytics_family") or inv.get("code_type")) != "internal_test",
        "launch_visibility": inv.get("launch_visibility") or "private",
        "used_count": used,
        "max_uses": max_uses,
        "remaining_uses": remaining,
        "redemption_rate": round(used / max_uses, 4) if max_uses else 0,
        "validation_success_count": val_success,
        "validation_failed_count": val_failed,
        "failed_validation_rate": round(val_failed / total_validations, 4)
        if total_validations
        else 0,
        "abuse_attempt_count": abuse_attempts,
        "pending_redemptions": pending_redemptions,
        "completed_redemptions": completed_redemptions,
        "redeemed_redemptions": completed_redemptions,
        "recoverable_redemptions": recoverable_redemptions,
        "stranded_redemptions": stranded_redemptions,
        "nearing_exhaustion": remaining <= max(1, int(max_uses * 0.1)) and remaining > 0,
        "nearing_expiry": nearing_expiry,
        "effective_status": inv.get("effective_status"),
    }


async def duplicate_invite_campaign(
    source_code: str,
    *,
    created_by: Optional[str] = None,
    campaign_name_suffix: str = " (copy)",
) -> Dict[str, Any]:
    """Clone invite configuration with a newly generated unique code (used_count reset)."""
    db = database.get_db()
    src = await get_invite_code(source_code)
    if not src:
        raise ValueError("Source invite code not found")
    ct = str(src.get("code_type") or "private_invite")
    new_code = await generate_invite_code_authoritative(
        db,
        code_type=ct,
        prefix=str(src.get("code") or "")[:12],
        campaign_name=(src.get("campaign_name") or "") + campaign_name_suffix,
    )
    body = PilotInviteCodeCreate(
        code=new_code["code"],
        code_type=PilotInviteCodeType(ct) if ct in {e.value for e in PilotInviteCodeType} else PilotInviteCodeType.PRIVATE_INVITE,
        program_type=str(src.get("program_type") or "FOUNDING_PILOT"),
        applies_to_plan_codes=list(src.get("applies_to_plan_codes") or []),
        max_uses=int(src.get("max_uses") or 1),
        expires_at=src.get("expires_at"),
        email_restriction=src.get("email_restriction"),
        stripe_coupon_id=src.get("stripe_coupon_id"),
        stripe_promotion_code_id=src.get("stripe_promotion_code_id"),
        discount_mode=PilotInviteDiscountMode(str(src.get("discount_mode") or "coupon")),
        discount_percent=int(src.get("discount_percent") or 100),
        discount_duration=PilotInviteDiscountDuration(str(src.get("discount_duration") or "repeating")),
        discount_duration_in_months=src.get("discount_duration_in_months"),
        waive_onboarding_fee=bool(src.get("waive_onboarding_fee")),
        onboarding_fee_policy=PilotOnboardingFeePolicy(str(src.get("onboarding_fee_policy") or "waived")),
        is_publicly_enterable=bool(src.get("is_publicly_enterable")),
        public_entry_enabled=bool(src.get("public_entry_enabled")),
        campaign_name=((src.get("campaign_name") or "") + campaign_name_suffix).strip() or None,
        public_description=src.get("public_description"),
        campaign_status=PilotCampaignStatus(str(src.get("campaign_status") or "draft")),
        first_time_customer_only=bool(src.get("first_time_customer_only")),
        one_redemption_per_email=bool(src.get("one_redemption_per_email")),
        one_redemption_per_customer=bool(src.get("one_redemption_per_customer")),
        one_redemption_per_payment_method=bool(src.get("one_redemption_per_payment_method")),
        allowed_email_domains=list(src.get("allowed_email_domains") or []),
        blocked_email_domains=list(src.get("blocked_email_domains") or []),
        max_uses_per_day=src.get("max_uses_per_day"),
        metadata={
            **(src.get("metadata") or {}),
            "duplicated_from": src.get("code"),
        },
        created_by=created_by,
    )
    return await create_invite_code(body)


async def regenerate_invite_code_if_unused(code: str) -> Dict[str, Any]:
    """Assign a new code only when invite has zero redemptions (used_count must be 0)."""
    db = database.get_db()
    inv = await get_invite_code(code)
    if not inv:
        raise ValueError("Invite code not found")
    if int(inv.get("used_count") or 0) > 0:
        raise ValueError("Cannot regenerate a code that has already been redeemed")
    from services.pilot_redemption_lifecycle import TERMINAL_CONSUMING_STATUSES

    redemptions = await db[COL_REDEMPTIONS].count_documents(
        {
            "invite_code_id": inv.get("invite_code_id"),
            "status": {"$in": list(TERMINAL_CONSUMING_STATUSES)},
        }
    )
    if redemptions > 0:
        raise ValueError("Cannot regenerate: redemption records exist")

    new_code_payload = await generate_invite_code_authoritative(
        db,
        code_type=str(inv.get("code_type") or "private_invite"),
        campaign_name=str(inv.get("campaign_name") or ""),
    )
    new_code = new_code_payload["code"]
    old_code = inv["code"]
    now = _utc_now()
    await db[COL_CODES].update_one(
        {"invite_code_id": inv["invite_code_id"]},
        {
            "$set": {
                "code": new_code,
                "updated_at": now,
                "metadata": {
                    **(inv.get("metadata") or {}),
                    "regenerated_from": old_code,
                    "regenerated_at": now.isoformat(),
                },
            }
        },
    )
    updated = await get_invite_code(new_code)
    return {"invite_code": updated, "previous_code": old_code}


async def update_invite_code(code: str, body: PilotInviteCodeUpdate) -> Optional[Dict[str, Any]]:
    from pymongo import ReturnDocument

    db = database.get_db()
    normalized = normalize_invite_code(code)
    current = await db[COL_CODES].find_one({"code": normalized}, {"_id": 0})
    if not current:
        return None
    now = _utc_now()
    patch: Dict[str, Any] = {"updated_at": now}
    if body.status is not None:
        patch["status"] = body.status.value
    if body.code_type is not None:
        patch["code_type"] = body.code_type.value
    if body.is_publicly_enterable is not None:
        patch["is_publicly_enterable"] = body.is_publicly_enterable
    if body.public_entry_enabled is not None:
        patch["public_entry_enabled"] = body.public_entry_enabled
    if body.campaign_name is not None:
        patch["campaign_name"] = (body.campaign_name or "").strip() or None
    if body.public_description is not None:
        patch["public_description"] = (body.public_description or "").strip() or None
    if body.campaign_status is not None:
        patch["campaign_status"] = body.campaign_status.value
        patch["campaign_state"] = _campaign_state_from_doc({"campaign_status": body.campaign_status.value})
    if body.campaign_state is not None:
        patch["campaign_state"] = body.campaign_state.value
        patch["campaign_status"] = _campaign_status_from_state(
            body.campaign_state.value,
            code_type=str(patch.get("code_type") or current.get("code_type") or "private_invite"),
        )
    if body.launch_visibility is not None:
        patch["launch_visibility"] = body.launch_visibility.value
    if body.campaign_config_version is not None:
        patch["campaign_config_version"] = body.campaign_config_version
    if body.campaign_locked_at is not None:
        patch["campaign_locked_at"] = body.campaign_locked_at
    if body.campaign_launched_at is not None:
        patch["campaign_launched_at"] = body.campaign_launched_at
    if body.analytics_family is not None:
        patch["analytics_family"] = (body.analytics_family or "").strip().lower() or None
    if body.max_uses_per_account is not None:
        patch["max_uses_per_account"] = body.max_uses_per_account
    if body.internal_live_test is not None:
        patch["internal_live_test"] = bool(body.internal_live_test)
    if body.deactivated_by is not None:
        patch["deactivated_by"] = (body.deactivated_by or "").strip() or None
    if body.deactivated_reason is not None:
        patch["deactivated_reason"] = (body.deactivated_reason or "").strip() or None
    if body.archived is True:
        patch["archived_at"] = now
        patch["campaign_status"] = "ended"
        patch["campaign_state"] = PilotCampaignState.ARCHIVED.value
    elif body.archived is False:
        patch["archived_at"] = None
    if body.first_time_customer_only is not None:
        patch["first_time_customer_only"] = body.first_time_customer_only
    if body.one_redemption_per_email is not None:
        patch["one_redemption_per_email"] = body.one_redemption_per_email
    if body.one_redemption_per_customer is not None:
        patch["one_redemption_per_customer"] = body.one_redemption_per_customer
    if body.one_redemption_per_payment_method is not None:
        patch["one_redemption_per_payment_method"] = body.one_redemption_per_payment_method
    if body.allowed_email_domains is not None:
        patch["allowed_email_domains"] = list(body.allowed_email_domains)
    if body.blocked_email_domains is not None:
        patch["blocked_email_domains"] = list(body.blocked_email_domains)
    if body.max_uses_per_day is not None:
        patch["max_uses_per_day"] = body.max_uses_per_day
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

    candidate = {**current, **patch}
    changed_campaign_fields = {
        field
        for field in _CAMPAIGN_MUTATION_FIELDS
        if field in patch and patch.get(field) != current.get(field)
    }
    if changed_campaign_fields:
        from services.pilot_redemption_lifecycle import TERMINAL_CONSUMING_STATUSES

        completed = await db[COL_REDEMPTIONS].count_documents(
            {
                "invite_code_id": current.get("invite_code_id"),
                "status": {"$in": list(TERMINAL_CONSUMING_STATUSES)},
            }
        )
        if completed > 0:
            previous_version = int(current.get("campaign_config_version") or 1)
            requested_version = int(candidate.get("campaign_config_version") or previous_version)
            candidate["campaign_previous_config_version"] = previous_version
            candidate["campaign_config_version"] = max(requested_version, previous_version + 1)
            candidate["campaign_versioned_at"] = now
            candidate["campaign_mutation_applies_to"] = "future_redemptions_only"
            candidate["campaign_mutated_fields"] = sorted(changed_campaign_fields)

    candidate = await _validate_invite_candidate_for_persistence(candidate)
    res = await db[COL_CODES].find_one_and_update(
        {"code": normalized},
        {"$set": candidate},
        return_document=ReturnDocument.AFTER,
    )
    if not res:
        return None
    res.pop("_id", None)
    return _enrich_invite_row(res)


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


# --- Redemption recovery & admin operations ---


async def update_redemption_status(
    *,
    redemption_id: str,
    new_status: str,
    failure_reason: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    from services.pilot_redemption_lifecycle import PilotRedemptionStatus, normalize_redemption_status

    db = database.get_db()
    now = _utc_now()
    st = normalize_redemption_status(new_status)
    patch: Dict[str, Any] = {"status": st, "updated_at": now}
    if failure_reason:
        patch["failure_reason"] = failure_reason[:500]
    if st in (PilotRedemptionStatus.REDEEMED.value, PilotRedemptionStatus.COMPLETED.value):
        patch["completed_at"] = now
    res = await db[COL_REDEMPTIONS].find_one_and_update(
        {"redemption_id": redemption_id},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
    )
    if not res:
        return None
    res.pop("_id", None)
    if actor:
        try:
            from models import AuditAction, UserRole
            from utils.audit import create_audit_log

            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole.ADMIN,
                actor_id=str(actor.get("id") or ""),
                client_id=res.get("client_id"),
                resource_type="pilot_invite_redemption",
                resource_id=redemption_id,
                metadata={
                    "action_type": "PILOT_REDEMPTION_STATUS_UPDATE",
                    "new_status": st,
                    "failure_reason": failure_reason,
                },
            )
        except Exception:
            pass
    return res


async def list_invite_redemptions(
    invite_code: str,
    *,
    limit: int = 100,
    include_recoverable_only: bool = False,
) -> List[Dict[str, Any]]:
    from services.pilot_redemption_lifecycle import RECOVERABLE_STATUSES, summarize_redemption_for_admin

    db = database.get_db()
    normalized = normalize_invite_code(invite_code)
    inv = await db[COL_CODES].find_one({"code": normalized}, {"_id": 0, "invite_code_id": 1})
    if not inv:
        return []
    filt: Dict[str, Any] = {"invite_code_id": inv.get("invite_code_id")}
    if include_recoverable_only:
        filt["status"] = {"$in": list(RECOVERABLE_STATUSES)}
    cursor = (
        db[COL_REDEMPTIONS].find(filt, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    rows = [doc async for doc in cursor]
    return [summarize_redemption_for_admin(r) for r in rows]


async def list_client_redemptions(client_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    from services.pilot_promo_recovery_service import list_redemptions_for_account

    return await list_redemptions_for_account(client_id, limit=limit)


async def admin_allow_redemption_retry(
    *,
    redemption_id: str,
    actor: Dict[str, Any],
    reason: str,
    create_override: bool = True,
    override_expires_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Release an incomplete redemption so the user can retry (revoked/expired, optional eligibility override)."""
    from services.pilot_redemption_eligibility_service import (
        EligibilityOverrideScope,
        EligibilityOverrideType,
        create_eligibility_override,
    )
    from services.pilot_redemption_lifecycle import (
        PilotRedemptionStatus,
        is_terminal_consuming,
        normalize_redemption_status,
    )

    db = database.get_db()
    row = await db[COL_REDEMPTIONS].find_one({"redemption_id": redemption_id}, {"_id": 0})
    if not row:
        raise ValueError("REDEMPTION_NOT_FOUND")
    if is_terminal_consuming(row.get("status")):
        raise ValueError("REDEMPTION_ALREADY_REDEEMED")

    updated = await update_redemption_status(
        redemption_id=redemption_id,
        new_status=PilotRedemptionStatus.REVOKED.value,
        failure_reason=f"admin_retry_allowed: {reason[:200]}",
        actor=actor,
    )
    override_doc = None
    if create_override and updated:
        scope = EligibilityOverrideScope.CLIENT_ID.value
        scope_value = str(updated.get("client_id") or "")
        if not scope_value and updated.get("redemption_email"):
            scope = EligibilityOverrideScope.EMAIL.value
            scope_value = str(updated.get("redemption_email")).lower()
        if scope_value:
            override_doc = await create_eligibility_override(
                scope=scope,
                scope_value=scope_value,
                override_type=EligibilityOverrideType.ALLOW_PROMO_RETRY.value,
                override_reason=reason,
                override_actor=actor,
                invite_code=updated.get("code"),
                invite_code_id=updated.get("invite_code_id"),
                override_expires_at=override_expires_at,
                metadata={"redemption_id": redemption_id, "prior_status": normalize_redemption_status(row.get("status"))},
            )
    return {"redemption": updated, "override": override_doc}


async def admin_reset_incomplete_redemption(
    *,
    redemption_id: str,
    actor: Dict[str, Any],
    reason: str,
) -> Dict[str, Any]:
    """Expire/revoke an incomplete attempt without granting a promo retry override."""
    from services.pilot_redemption_lifecycle import (
        PilotRedemptionStatus,
        is_recoverable,
        is_terminal_consuming,
        normalize_redemption_status,
    )

    db = database.get_db()
    row = await db[COL_REDEMPTIONS].find_one({"redemption_id": redemption_id}, {"_id": 0})
    if not row:
        raise ValueError("REDEMPTION_NOT_FOUND")
    if is_terminal_consuming(row.get("status")):
        raise ValueError("REDEMPTION_ALREADY_REDEEMED")
    if not is_recoverable(row.get("status")):
        raise ValueError("REDEMPTION_NOT_RESETTABLE")

    prior = normalize_redemption_status(row.get("status"))
    new_status = (
        PilotRedemptionStatus.EXPIRED.value
        if prior in (PilotRedemptionStatus.PENDING.value, PilotRedemptionStatus.PAYMENT_STARTED.value)
        else PilotRedemptionStatus.REVOKED.value
    )
    updated = await update_redemption_status(
        redemption_id=redemption_id,
        new_status=new_status,
        failure_reason=f"admin_reset_incomplete: {reason[:200]}",
        actor=actor,
    )
    if not updated:
        raise ValueError("REDEMPTION_NOT_FOUND")
    return {"redemption": updated}


async def mark_redemption_payment_failed(*, checkout_session_id: str, reason: str = "checkout_abandoned") -> bool:
    from services.pilot_redemption_lifecycle import PilotRedemptionStatus

    db = database.get_db()
    now = _utc_now()
    res = await db[COL_REDEMPTIONS].update_one(
        {
            "checkout_session_id": checkout_session_id,
            "status": {
                "$in": [
                    PilotRedemptionStatus.PENDING.value,
                    PilotRedemptionStatus.PAYMENT_STARTED.value,
                    "pending",
                ]
            },
        },
        {
            "$set": {
                "status": PilotRedemptionStatus.PAYMENT_FAILED.value,
                "updated_at": now,
                "failure_reason": reason[:500],
            }
        },
    )
    return res.modified_count > 0


async def mark_redemption_provisioning_failed(
    *, checkout_session_id: str, reason: str = "provisioning_failed"
) -> bool:
    from services.pilot_redemption_lifecycle import PilotRedemptionStatus

    db = database.get_db()
    now = _utc_now()
    res = await db[COL_REDEMPTIONS].update_one(
        {
            "checkout_session_id": checkout_session_id,
            "status": {
                "$in": [
                    PilotRedemptionStatus.PENDING.value,
                    PilotRedemptionStatus.PAYMENT_STARTED.value,
                    "pending",
                ]
            },
        },
        {
            "$set": {
                "status": PilotRedemptionStatus.PROVISIONING_FAILED.value,
                "updated_at": now,
                "failure_reason": reason[:500],
            }
        },
    )
    return res.modified_count > 0


async def reconcile_redemption_recovery_batch(*, limit: int = 200) -> Dict[str, Any]:
    """Expire stale pending redemptions and surface stranded onboarding attempts."""
    from datetime import timedelta

    from services.pilot_invite_code_governance import _expire_stale_pending_for_identity
    from services.pilot_redemption_lifecycle import PilotRedemptionStatus, redemption_retry_grace_hours

    db = database.get_db()
    now = _utc_now()
    grace_cutoff = now - timedelta(hours=redemption_retry_grace_hours())
    expired_count = 0
    provisioning_failed_marked = 0

    cursor = db[COL_REDEMPTIONS].find(
        {
            "status": {
                "$in": [
                    PilotRedemptionStatus.PENDING.value,
                    PilotRedemptionStatus.PAYMENT_STARTED.value,
                    "pending",
                ]
            },
            "created_at": {"$lt": grace_cutoff},
        },
        {"_id": 0, "redemption_id": 1, "redemption_email": 1, "client_id": 1, "invite_code_id": 1},
    ).limit(limit)

    async for row in cursor:
        n = await _expire_stale_pending_for_identity(
            db,
            invite_code_id=str(row.get("invite_code_id") or ""),
            email=row.get("redemption_email"),
            client_id=row.get("client_id"),
        )
        expired_count += n

    fail_cursor = db.clients.find(
        {"onboarding_status": "FAILED", "pilot_invite_code": {"$exists": True, "$ne": None}},
        {"_id": 0, "client_id": 1},
    ).limit(limit)
    async for client in fail_cursor:
        cid = client.get("client_id")
        if not cid:
            continue
        jobs = (
            await db.provisioning_jobs.find(
                {"client_id": cid},
                {"_id": 0, "checkout_session_id": 1},
            )
            .sort("created_at", -1)
            .limit(1)
            .to_list(length=1)
        )
        job = jobs[0] if jobs else None
        cs = (job or {}).get("checkout_session_id")
        if cs and await mark_redemption_provisioning_failed(
            checkout_session_id=str(cs), reason="provisioning_job_failed"
        ):
            provisioning_failed_marked += 1

    return {
        "expired_stale_pending": expired_count,
        "provisioning_failed_marked": provisioning_failed_marked,
        "completed_at": now.isoformat(),
    }
