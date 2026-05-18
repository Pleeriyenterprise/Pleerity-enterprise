"""
Pilot onboarding/setup fee policy — checkout line items, metadata, and permanent waiver state.

Stripe remains billing authority; waived pilots never receive onboarding line items at checkout
and are marked onboarding_fee_paid so later checkouts/renewals do not add setup fees.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from models.pilot_invite import PilotOnboardingFeePolicy
from services.plan_registry import plan_registry, PlanCode

DEFAULT_FOUNDING_ONBOARDING_POLICY = PilotOnboardingFeePolicy.WAIVED


def onboarding_policy_from_invite(doc: Optional[Dict[str, Any]]) -> PilotOnboardingFeePolicy:
    if not doc:
        return PilotOnboardingFeePolicy.CHARGE_NOW
    raw = str(doc.get("onboarding_fee_policy") or "").strip().lower()
    if raw in {p.value for p in PilotOnboardingFeePolicy}:
        return PilotOnboardingFeePolicy(raw)
    if doc.get("waive_onboarding_fee") is True:
        return PilotOnboardingFeePolicy.WAIVED
    if doc.get("waive_onboarding_fee") is False:
        return PilotOnboardingFeePolicy.CHARGE_NOW
    program = str(doc.get("program_type") or "").upper()
    if program == "FOUNDING_PILOT":
        return DEFAULT_FOUNDING_ONBOARDING_POLICY
    return PilotOnboardingFeePolicy.CHARGE_NOW


def onboarding_policy_from_client(client: Optional[Dict[str, Any]]) -> Optional[PilotOnboardingFeePolicy]:
    if not client:
        return None
    raw = str(client.get("onboarding_fee_policy") or "").strip().lower()
    if raw in {p.value for p in PilotOnboardingFeePolicy}:
        return PilotOnboardingFeePolicy(raw)
    if client.get("onboarding_fee_waived"):
        return PilotOnboardingFeePolicy.WAIVED
    return None


def is_onboarding_waived_policy(policy: PilotOnboardingFeePolicy) -> bool:
    return policy == PilotOnboardingFeePolicy.WAIVED


def should_include_onboarding_line_item(
    *,
    policy: PilotOnboardingFeePolicy,
    already_paid: bool,
    onboarding_price_id: Optional[str],
) -> bool:
    """Whether to add onboarding/setup price to Stripe Checkout line_items."""
    if not onboarding_price_id or already_paid:
        return False
    if policy == PilotOnboardingFeePolicy.WAIVED:
        return False
    if policy == PilotOnboardingFeePolicy.DEFERRED:
        return False
    return True


def plan_onboarding_amount_minor(plan_code: str) -> Tuple[int, str]:
    try:
        plan = PlanCode(plan_code)
    except ValueError:
        plan = plan_registry._resolve_plan_code(plan_code)
    plan_def = plan_registry.get_plan(plan)
    amount_gbp = float(plan_def.get("onboarding_fee") or 0)
    return int(round(amount_gbp * 100)), "gbp"


def build_onboarding_checkout_metadata(
    *,
    policy: PilotOnboardingFeePolicy,
    plan_code: str,
    invite_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    amount_minor, currency = plan_onboarding_amount_minor(plan_code)
    waived = is_onboarding_waived_policy(policy) or policy == PilotOnboardingFeePolicy.DEFERRED
    meta = {
        "onboarding_fee_policy": policy.value,
        "onboarding_fee_waived": "true" if waived and policy == PilotOnboardingFeePolicy.WAIVED else "false",
        "onboarding_fee_amount_minor": str(amount_minor),
        "onboarding_fee_currency": currency,
    }
    if invite_doc and invite_doc.get("onboarding_fee_discount_percent") is not None:
        meta["onboarding_fee_discount_percent"] = str(int(invite_doc["onboarding_fee_discount_percent"]))
    return meta


def resolve_checkout_onboarding(
    *,
    pilot_invite_doc: Optional[Dict[str, Any]],
    plan_code: str,
    already_paid: bool,
    onboarding_price_id: Optional[str],
) -> Tuple[bool, PilotOnboardingFeePolicy, Dict[str, str]]:
    """
    Returns (include_onboarding_line_item, policy, metadata_strings).
    """
    policy = onboarding_policy_from_invite(pilot_invite_doc)
    include = should_include_onboarding_line_item(
        policy=policy,
        already_paid=already_paid,
        onboarding_price_id=onboarding_price_id,
    )
    meta = build_onboarding_checkout_metadata(policy=policy, plan_code=plan_code, invite_doc=pilot_invite_doc)
    return include, policy, meta


def onboarding_fields_for_waived_client(
    *,
    policy: PilotOnboardingFeePolicy,
    plan_code: str,
    reason: Optional[str] = None,
    waived_by: Optional[str] = None,
    deferred_until: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Client + client_billing fields when onboarding is waived or deferred at checkout."""
    amount_minor, currency = plan_onboarding_amount_minor(plan_code)
    now = datetime.now(timezone.utc)
    fields: Dict[str, Any] = {
        "onboarding_fee_policy": policy.value,
        "onboarding_fee_amount": amount_minor,
        "onboarding_fee_currency": currency,
    }
    if policy == PilotOnboardingFeePolicy.WAIVED:
        fields.update(
            {
                "onboarding_fee_waived": True,
                "onboarding_fee_waived_at": now,
                "onboarding_fee_waiver_reason": reason or "Founding pilot onboarding fee waived",
            }
        )
        if waived_by:
            fields["onboarding_fee_waived_by"] = waived_by
    elif policy == PilotOnboardingFeePolicy.DEFERRED:
        fields.update(
            {
                "onboarding_fee_waived": False,
                "onboarding_fee_deferred_until": deferred_until,
            }
        )
    return fields


def resolve_webhook_onboarding_fee(
    *,
    session_metadata: Dict[str, Any],
    client: Optional[Dict[str, Any]],
    session_line_items: Optional[Dict[str, Any]],
    expected_onboarding_price_id: Optional[str],
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Determine onboarding_fee_paid, setup_fee_amount_cents, setup_fee_invoice_id for checkout webhook.

    Waived pilots: mark paid=True (satisfied permanently), amount=0, never infer from missing line_items.
    """
    meta = session_metadata or {}
    policy_raw = str(meta.get("onboarding_fee_policy") or "").lower()
    waived_meta = str(meta.get("onboarding_fee_waived") or "").lower() in ("true", "1", "yes")

    client_policy = onboarding_policy_from_client(client)
    if (
        waived_meta
        or policy_raw == PilotOnboardingFeePolicy.WAIVED.value
        or (client_policy == PilotOnboardingFeePolicy.WAIVED)
        or (client and client.get("onboarding_fee_waived"))
    ):
        return True, 0, None

    if policy_raw == PilotOnboardingFeePolicy.DEFERRED.value or (
        client_policy == PilotOnboardingFeePolicy.DEFERRED
    ):
        return False, None, None

    onboarding_fee_paid = False
    setup_fee_amount_cents = None
    setup_fee_invoice_id = None

    if session_line_items and session_line_items.get("data"):
        for item in session_line_items.get("data", []):
            item_price_id = (item.get("price") or {}).get("id")
            if item_price_id == expected_onboarding_price_id:
                onboarding_fee_paid = True
                setup_fee_amount_cents = item.get("amount", 0)
                break
        return onboarding_fee_paid, setup_fee_amount_cents, setup_fee_invoice_id

    # Missing line_items: do not assume onboarding paid (unsafe for waived pilot checkouts)
    return False, None, None
