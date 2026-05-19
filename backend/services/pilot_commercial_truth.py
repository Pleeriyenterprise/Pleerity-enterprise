"""
Unified commercial truth for founding pilot offers — agreements, intake, emails, admin summaries.

Single source for onboarding fee display, pilot duration, and post-pilot subscription pricing.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from models.pilot_invite import PilotOnboardingFeePolicy
from services.pilot_onboarding_fee import (
    is_onboarding_waived_policy,
    onboarding_policy_from_client,
    onboarding_policy_from_invite,
)
from services.plan_registry import PlanCode, plan_registry


def commercial_context_from_invite(
    invite_doc: Dict[str, Any],
    *,
    plan_code: str,
) -> Dict[str, Any]:
    """Build commercial context from a validated pilot invite document."""
    from services.pilot_invite_service import discount_config_from_doc

    cfg = discount_config_from_doc(invite_doc)
    policy = onboarding_policy_from_invite(invite_doc)
    plan_def = _plan_def(plan_code)
    monthly_gbp = float(plan_def.get("monthly_price") or 0)
    onboarding_gbp = float(plan_def.get("onboarding_fee") or 0)
    months = int(cfg.get("discount_duration_in_months") or 0)
    waived = is_onboarding_waived_policy(policy)
    return {
        "is_pilot": True,
        "program_type": str(invite_doc.get("program_type") or "FOUNDING_PILOT"),
        "plan_code": plan_code,
        "pilot_discount_percent": cfg["discount_percent"],
        "pilot_discount_months": months,
        "pilot_discount_duration": cfg["discount_duration"],
        "expected_transition_to_paid": cfg["expected_transition_to_paid"],
        "onboarding_fee_policy": policy.value,
        "onboarding_fee_waived": waived,
        "onboarding_fee_minor": 0 if waived or policy == PilotOnboardingFeePolicy.DEFERRED else int(round(onboarding_gbp * 100)),
        "onboarding_fee_display_gbp": 0.0 if waived else onboarding_gbp,
        "monthly_price_gbp": monthly_gbp,
        "monthly_price_minor": int(round(monthly_gbp * 100)),
        "first_checkout_total_minor": 0 if waived and cfg["discount_percent"] >= 100 else int(round((monthly_gbp + (0 if waived else onboarding_gbp)) * 100)),
    }


def commercial_context_from_client(client: Dict[str, Any], *, plan_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Build commercial context from persisted client pilot fields (post-checkout)."""
    if not client.get("pilot_program_type") and not client.get("pilot_status"):
        return None
    code = plan_code or str(client.get("billing_plan") or "PLAN_1_SOLO")
    policy = onboarding_policy_from_client(client) or PilotOnboardingFeePolicy.WAIVED
    plan_def = _plan_def(code)
    monthly_gbp = float(plan_def.get("monthly_price") or 0)
    onboarding_gbp = float(plan_def.get("onboarding_fee") or 0)
    waived = bool(client.get("onboarding_fee_waived")) or is_onboarding_waived_policy(policy)
    months = int(client.get("pilot_duration_months") or client.get("pilot_discount_months") or 0)
    return {
        "is_pilot": True,
        "program_type": str(client.get("pilot_program_type") or "FOUNDING_PILOT"),
        "plan_code": code,
        "pilot_discount_percent": int(client.get("pilot_discount_percent") or 100),
        "pilot_discount_months": months,
        "onboarding_fee_policy": policy.value,
        "onboarding_fee_waived": waived,
        "onboarding_fee_minor": 0 if waived else int(round(onboarding_gbp * 100)),
        "onboarding_fee_display_gbp": 0.0 if waived else onboarding_gbp,
        "monthly_price_gbp": monthly_gbp,
        "monthly_price_minor": int(round(monthly_gbp * 100)),
    }


def apply_pilot_to_commercial_snapshot(
    snapshot: Dict[str, Any],
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """Adjust authoritative commercial snapshot fields for pilot terms."""
    out = dict(snapshot)
    out["onboarding_fee_minor"] = int(ctx.get("onboarding_fee_minor") or 0)
    out["first_checkout_total_minor"] = int(ctx.get("first_checkout_total_minor") or 0)
    out["recurring_monthly_minor"] = int(ctx.get("monthly_price_minor") or snapshot.get("billing_amount_minor") or 0)
    out["pilot_program_type"] = ctx.get("program_type")
    out["pilot_discount_percent"] = ctx.get("pilot_discount_percent")
    out["pilot_discount_months"] = ctx.get("pilot_discount_months")
    out["pilot_discount_duration"] = ctx.get("pilot_discount_duration")
    out["onboarding_fee_policy"] = ctx.get("onboarding_fee_policy")
    out["onboarding_fee_waived"] = bool(ctx.get("onboarding_fee_waived"))
    out["pilot_commercial_summary"] = build_pilot_offer_summary(ctx)
    return out


def build_pilot_offer_summary(ctx: Dict[str, Any]) -> str:
    """Human-readable founding pilot commercial summary (agreements, emails, intake)."""
    months = int(ctx.get("pilot_discount_months") or 0)
    monthly = float(ctx.get("monthly_price_gbp") or 0)
    waived = bool(ctx.get("onboarding_fee_waived"))
    lines = ["Founding Pilot Offer:"]
    if waived:
        lines.append("Your onboarding fee has been waived.")
    elif ctx.get("onboarding_fee_policy") == PilotOnboardingFeePolicy.DEFERRED.value:
        lines.append("Your onboarding fee is deferred (charged separately when configured).")
    else:
        setup = float(ctx.get("onboarding_fee_display_gbp") or 0)
        lines.append(f"One-time onboarding fee: £{setup:.2f}.")
    if months > 0 and int(ctx.get("pilot_discount_percent") or 0) >= 100:
        lines.append(f"Your first {months} month{'s' if months != 1 else ''} are free.")
    elif months > 0:
        pct = int(ctx.get("pilot_discount_percent") or 0)
        lines.append(f"Your first {months} month{'s' if months != 1 else ''} are {pct}% off.")
    lines.append(
        f"After the pilot, your subscription continues at £{monthly:.2f}/month unless cancelled before renewal."
    )
    return " ".join(lines)


def build_onboarding_fee_line(ctx: Optional[Dict[str, Any]], *, onboarding_minor: int = 0) -> str:
    if not ctx or not ctx.get("is_pilot"):
        minor = int((ctx or {}).get("onboarding_fee_minor") or onboarding_minor or 0)
        return f"One-time onboarding fee: £{minor / 100:.2f}" if minor > 0 else "One-time onboarding fee: None"
    if ctx.get("onboarding_fee_waived"):
        return "One-time onboarding fee: Waived (Founding Pilot)"
    if ctx.get("onboarding_fee_policy") == PilotOnboardingFeePolicy.DEFERRED.value:
        return "One-time onboarding fee: Deferred"
    minor = int(ctx.get("onboarding_fee_minor") or onboarding_minor or 0)
    return f"One-time onboarding fee: £{minor / 100:.2f}" if minor > 0 else "One-time onboarding fee: None"


def build_payment_confirmation_pricing_line(ctx: Optional[Dict[str, Any]], *, amount_total_cents: Optional[int] = None) -> str:
    """Stripe payment confirmation email pricing line."""
    if ctx and ctx.get("is_pilot"):
        monthly = float(ctx.get("monthly_price_gbp") or 0)
        if amount_total_cents is not None:
            return (
                f"Founding Pilot checkout: £{amount_total_cents / 100:.2f} due today. "
                f"Onboarding fee waived. Subscription continues at £{monthly:.2f}/month after your pilot period."
            )
        return build_pilot_offer_summary(ctx)
    monthly = float((ctx or {}).get("monthly_price_gbp") or 0)
    setup = float((ctx or {}).get("onboarding_fee_display_gbp") or 0)
    return f"£{monthly:.2f}/month + £{setup:.2f} setup"


def intake_plan_pricing_overlay(plan: Dict[str, Any], ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Adjust intake /plans row when a valid pilot invite applies."""
    row = dict(plan)
    if not ctx or not ctx.get("is_pilot"):
        return row
    monthly = float(ctx.get("monthly_price_gbp") or row.get("monthly_price") or 0)
    setup = float(ctx.get("onboarding_fee_display_gbp") or 0)
    row["setup_fee"] = setup
    row["setup_fee_label"] = "Waived" if ctx.get("onboarding_fee_waived") else row.get("setup_fee")
    row["total_first_payment"] = 0.0 if ctx.get("onboarding_fee_waived") and ctx.get("pilot_discount_percent", 0) >= 100 else monthly + setup
    row["pilot_applied"] = True
    row["pilot_commercial_summary"] = build_pilot_offer_summary(ctx)
    row["onboarding_fee_waived"] = bool(ctx.get("onboarding_fee_waived"))
    return row


def validate_response_commercial_fields(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Extra fields for PilotInviteValidateResponse."""
    monthly = float(ctx.get("monthly_price_gbp") or 0)
    return {
        "setup_fee_effective": float(ctx.get("onboarding_fee_display_gbp") or 0),
        "monthly_price_after_pilot": monthly,
        "first_payment_estimate": float(ctx.get("first_checkout_total_minor") or 0) / 100.0,
        "commercial_summary": build_pilot_offer_summary(ctx),
    }


def _plan_def(plan_code: str) -> Dict[str, Any]:
    try:
        plan = PlanCode(plan_code)
    except ValueError:
        plan = plan_registry._resolve_plan_code(plan_code)
    return plan_registry.get_plan(plan)
