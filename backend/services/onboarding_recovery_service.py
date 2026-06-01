"""Onboarding continuation & recovery orchestration — Phase 1 classification and assessment."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from models import OnboardingStatus, PasswordStatus
from services.pilot_promo_recovery_service import get_account_promo_recovery_context
from services.pilot_redemption_lifecycle import (
    PilotRedemptionStatus,
    normalize_redemption_status,
)

logger = logging.getLogger(__name__)

# Canonical recovery classifications (Part 1)
CLASS_PAYMENT_ABANDONED = "PAYMENT_ABANDONED"
CLASS_EXPIRED_CHECKOUT = "EXPIRED_CHECKOUT"
CLASS_PROMO_REDEMPTION_FAILED = "PROMO_REDEMPTION_FAILED"
CLASS_FIRST_TIME_RESTRICTION_COLLISION = "FIRST_TIME_RESTRICTION_COLLISION"
CLASS_PARTIAL_PROVISIONING = "PARTIAL_PROVISIONING"
CLASS_ACTIVATION_INCOMPLETE = "ACTIVATION_INCOMPLETE"
CLASS_SUBSCRIPTION_DRIFT = "SUBSCRIPTION_DRIFT"
CLASS_DUPLICATE_RECOVERY_RISK = "DUPLICATE_RECOVERY_RISK"
CLASS_RECOVERY_ALREADY_ACTIVE = "RECOVERY_ALREADY_ACTIVE"
CLASS_UNKNOWN_RECOVERY_STATE = "UNKNOWN_RECOVERY_STATE"

ALL_RECOVERY_CLASSIFICATIONS = frozenset(
    {
        CLASS_PAYMENT_ABANDONED,
        CLASS_EXPIRED_CHECKOUT,
        CLASS_PROMO_REDEMPTION_FAILED,
        CLASS_FIRST_TIME_RESTRICTION_COLLISION,
        CLASS_PARTIAL_PROVISIONING,
        CLASS_ACTIVATION_INCOMPLETE,
        CLASS_SUBSCRIPTION_DRIFT,
        CLASS_DUPLICATE_RECOVERY_RISK,
        CLASS_RECOVERY_ALREADY_ACTIVE,
        CLASS_UNKNOWN_RECOVERY_STATE,
    }
)

# Recovery modes (Part 3 — recommendation only in Phase 1)
MODE_RESUME_ONBOARDING = "resume_onboarding"
MODE_REGENERATE_PAYMENT = "regenerate_payment"
MODE_RESEND_ACTIVATION = "resend_activation"
MODE_MANUAL_ESCALATION = "manual_escalation"

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

CHECKOUT_FRESH_MINUTES = 30
_SUBSCRIPTION_ACTIVE = frozenset({"active", "trialing"})
_SUBSCRIPTION_TERMINAL = frozenset({"canceled", "incomplete_expired"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _is_paid_or_active(client: Dict[str, Any], billing: Optional[Dict[str, Any]]) -> bool:
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


def _checkout_is_fresh(client: Dict[str, Any]) -> bool:
    sent_at = _parse_iso(client.get("checkout_link_sent_at"))
    if not sent_at or not client.get("latest_checkout_url"):
        return False
    return sent_at >= _now() - timedelta(minutes=CHECKOUT_FRESH_MINUTES)


def _has_checkout_history(client: Dict[str, Any]) -> bool:
    return bool(client.get("latest_checkout_session_id") or client.get("latest_checkout_url"))


def classify_recovery_state(signals: Dict[str, Any]) -> Optional[str]:
    """Deterministic primary recovery classification from gathered signals."""
    if not signals.get("is_stranded"):
        return None

    client = signals.get("client") or {}
    indicators = signals.get("indicators") or {}
    redemptions = signals.get("redemptions") or []
    portal_user = signals.get("portal_user") or {}

    if _checkout_is_fresh(client) and not _is_paid_or_active(client, signals.get("billing")):
        return CLASS_RECOVERY_ALREADY_ACTIVE

    if _is_paid_or_active(client, signals.get("billing")):
        onboarding = (client.get("onboarding_status") or "").upper()
        password_set = portal_user.get("password_status") == PasswordStatus.SET.value
        if onboarding == OnboardingStatus.PROVISIONED.value and not password_set:
            return CLASS_ACTIVATION_INCOMPLETE
        if signals.get("subscription_drift"):
            return CLASS_SUBSCRIPTION_DRIFT
        if indicators.get("stranded_onboarding"):
            return CLASS_DUPLICATE_RECOVERY_RISK

    prov = str(client.get("provisioning_status") or client.get("onboarding_status") or "").upper()
    if prov in ("FAILED", "PROVISIONING_FAILED") or indicators.get("provisioning_failed"):
        return CLASS_PARTIAL_PROVISIONING

    latest_redemption = redemptions[0] if redemptions else None
    if latest_redemption:
        st = normalize_redemption_status(latest_redemption.get("status"))
        if st == PilotRedemptionStatus.PAYMENT_FAILED.value:
            return CLASS_PROMO_REDEMPTION_FAILED
        if st == PilotRedemptionStatus.PROVISIONING_FAILED.value:
            return CLASS_PARTIAL_PROVISIONING

    if indicators.get("retry_blocked") and not indicators.get("override_active"):
        return CLASS_FIRST_TIME_RESTRICTION_COLLISION

    if _has_checkout_history(client) and not _checkout_is_fresh(client):
        if not _is_paid_or_active(client, signals.get("billing")):
            return CLASS_EXPIRED_CHECKOUT

    ob = (client.get("onboarding_status") or "").upper()
    lifecycle = (client.get("lifecycle_status") or "").lower()
    has_crn = bool((client.get("customer_reference") or "").strip())
    unpaid = not _is_paid_or_active(client, signals.get("billing"))
    if unpaid and (has_crn or ob != OnboardingStatus.INTAKE_PENDING.value or lifecycle in ("pending_payment", "abandoned")):
        return CLASS_PAYMENT_ABANDONED

    if indicators.get("payment_failed") or indicators.get("incomplete_redemption"):
        return CLASS_PROMO_REDEMPTION_FAILED

    if indicators.get("stranded_onboarding"):
        return CLASS_UNKNOWN_RECOVERY_STATE

    return CLASS_UNKNOWN_RECOVERY_STATE


EXECUTABLE_MODES_PHASE2 = frozenset(
    {MODE_REGENERATE_PAYMENT, MODE_RESEND_ACTIVATION, MODE_RESUME_ONBOARDING}
)

_MODE_CLASSIFICATIONS_ALLOWED: Dict[str, frozenset] = {
    MODE_REGENERATE_PAYMENT: frozenset(
        {
            CLASS_PAYMENT_ABANDONED,
            CLASS_EXPIRED_CHECKOUT,
            CLASS_PROMO_REDEMPTION_FAILED,
            CLASS_FIRST_TIME_RESTRICTION_COLLISION,
        }
    ),
    MODE_RESUME_ONBOARDING: frozenset(
        {
            CLASS_PAYMENT_ABANDONED,
            CLASS_EXPIRED_CHECKOUT,
            CLASS_PROMO_REDEMPTION_FAILED,
            CLASS_FIRST_TIME_RESTRICTION_COLLISION,
        }
    ),
    MODE_RESEND_ACTIVATION: frozenset({CLASS_ACTIVATION_INCOMPLETE}),
}


def derive_executable_modes(
    classification: Optional[str],
    strategy: Dict[str, Any],
    eligibility: Dict[str, Any],
) -> List[str]:
    if not classification or not eligibility.get("eligible"):
        return []
    seen: List[str] = []
    for mode in list(strategy.get("available_modes") or []) + [strategy.get("recommended_mode")]:
        if not mode or mode in seen:
            continue
        if mode not in EXECUTABLE_MODES_PHASE2:
            continue
        if classification not in _MODE_CLASSIFICATIONS_ALLOWED.get(mode, frozenset()):
            continue
        seen.append(mode)
    return seen


def derive_execution_availability(
    classification: Optional[str],
    strategy: Dict[str, Any],
    eligibility: Dict[str, Any],
) -> Tuple[bool, int]:
    """Whether governed execution (Phase 2) is available for this assessment."""
    executable = derive_executable_modes(classification, strategy, eligibility)
    return bool(executable), 2


def derive_recovery_strategy(
    classification: Optional[str],
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    """Recommended recovery mode; execution flags are set in build_onboarding_recovery_assessment."""
    if not classification:
        return {
            "recommended_mode": None,
            "available_modes": [],
            "execution_available": False,
            "phase": 2,
        }

    mode_map: Dict[str, Tuple[str, List[str]]] = {
        CLASS_PAYMENT_ABANDONED: (MODE_REGENERATE_PAYMENT, [MODE_REGENERATE_PAYMENT, MODE_RESUME_ONBOARDING]),
        CLASS_EXPIRED_CHECKOUT: (MODE_REGENERATE_PAYMENT, [MODE_REGENERATE_PAYMENT]),
        CLASS_PROMO_REDEMPTION_FAILED: (
            MODE_REGENERATE_PAYMENT,
            [MODE_REGENERATE_PAYMENT, MODE_RESUME_ONBOARDING],
        ),
        CLASS_FIRST_TIME_RESTRICTION_COLLISION: (
            MODE_REGENERATE_PAYMENT,
            [MODE_REGENERATE_PAYMENT, MODE_MANUAL_ESCALATION],
        ),
        CLASS_PARTIAL_PROVISIONING: (MODE_MANUAL_ESCALATION, [MODE_MANUAL_ESCALATION, MODE_RESEND_ACTIVATION]),
        CLASS_ACTIVATION_INCOMPLETE: (MODE_RESEND_ACTIVATION, [MODE_RESEND_ACTIVATION]),
        CLASS_SUBSCRIPTION_DRIFT: (MODE_MANUAL_ESCALATION, [MODE_MANUAL_ESCALATION]),
        CLASS_DUPLICATE_RECOVERY_RISK: (MODE_MANUAL_ESCALATION, [MODE_MANUAL_ESCALATION]),
        CLASS_RECOVERY_ALREADY_ACTIVE: (None, []),
        CLASS_UNKNOWN_RECOVERY_STATE: (MODE_MANUAL_ESCALATION, [MODE_MANUAL_ESCALATION]),
    }
    recommended, available = mode_map.get(classification, (MODE_MANUAL_ESCALATION, [MODE_MANUAL_ESCALATION]))
    if classification == CLASS_RECOVERY_ALREADY_ACTIVE:
        return {
            "recommended_mode": None,
            "available_modes": [],
            "execution_available": False,
            "phase": 2,
            "note": "A recovery checkout link was sent recently. Wait for customer action or allow the link to expire before regenerating.",
        }
    return {
        "recommended_mode": recommended,
        "available_modes": available,
        "execution_available": False,
        "phase": 2,
    }


def derive_recovery_risk(classification: Optional[str], signals: Dict[str, Any]) -> str:
    if not classification:
        return RISK_LOW
    if classification in (CLASS_SUBSCRIPTION_DRIFT, CLASS_DUPLICATE_RECOVERY_RISK, CLASS_PARTIAL_PROVISIONING):
        return RISK_HIGH
    if classification in (
        CLASS_FIRST_TIME_RESTRICTION_COLLISION,
        CLASS_PROMO_REDEMPTION_FAILED,
        CLASS_UNKNOWN_RECOVERY_STATE,
    ):
        return RISK_MEDIUM
    return RISK_LOW


def derive_customer_continuation_mode(
    classification: Optional[str],
    strategy: Dict[str, Any],
) -> Optional[str]:
    mode = strategy.get("recommended_mode")
    if not mode:
        return None
    return {
        MODE_RESUME_ONBOARDING: "continue_saved_setup",
        MODE_REGENERATE_PAYMENT: "secure_payment_checkout",
        MODE_RESEND_ACTIVATION: "portal_activation",
        MODE_MANUAL_ESCALATION: "support_escalation",
    }.get(mode)


def validate_recovery_eligibility(
    classification: Optional[str],
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    if not classification:
        return {"eligible": False, "reason": "No stranded onboarding detected for this account."}
    if classification == CLASS_RECOVERY_ALREADY_ACTIVE:
        return {
            "eligible": False,
            "reason": "A recovery checkout link is still active. Customer should use the existing link first.",
        }
    if classification == CLASS_DUPLICATE_RECOVERY_RISK:
        return {
            "eligible": False,
            "reason": "Account appears paid or active while recovery signals remain. Review billing before recovery.",
        }
    if classification == CLASS_SUBSCRIPTION_DRIFT:
        return {
            "eligible": False,
            "reason": "Billing records disagree with subscription state. Manual reconciliation required.",
        }
    return {"eligible": True, "reason": None}


def derive_recovery_recommendation_copy(
    classification: Optional[str],
    signals: Dict[str, Any],
    strategy: Dict[str, Any],
) -> Dict[str, str]:
    if not classification:
        return {
            "blockage_summary": "No onboarding recovery is required for this account.",
            "recommended_action": "No action needed.",
            "expected_customer_outcome": "Customer can continue using the portal normally.",
            "operational_impact": "None.",
        }

    client = signals.get("client") or {}
    crn = (client.get("customer_reference") or "").strip() or "—"
    copies: Dict[str, Dict[str, str]] = {
        CLASS_PAYMENT_ABANDONED: {
            "blockage_summary": f"Customer reference {crn} completed intake but has not paid.",
            "recommended_action": "Generate a new secure checkout link and send continuation guidance (Phase 2).",
            "expected_customer_outcome": "Customer receives an email with a link to complete subscription payment.",
            "operational_impact": "Preserves intake and property setup; does not create a duplicate account.",
        },
        CLASS_EXPIRED_CHECKOUT: {
            "blockage_summary": "Previous payment link has expired or is no longer valid.",
            "recommended_action": "Generate a fresh checkout link with preserved onboarding context (Phase 2).",
            "expected_customer_outcome": "Customer receives a new secure payment link.",
            "operational_impact": "Old checkout sessions should be treated as expired before sending a new link.",
        },
        CLASS_PROMO_REDEMPTION_FAILED: {
            "blockage_summary": "Promo redemption did not complete payment successfully.",
            "recommended_action": "Regenerate checkout with promo eligibility review (Phase 2).",
            "expected_customer_outcome": "Customer can retry payment with promo terms preserved where valid.",
            "operational_impact": "May require promo preservation or support waiver before checkout regeneration.",
        },
        CLASS_FIRST_TIME_RESTRICTION_COLLISION: {
            "blockage_summary": "First-time promo restriction is blocking a retry.",
            "recommended_action": "Review bypass options, then regenerate checkout (Phase 2).",
            "expected_customer_outcome": "Customer can retry onboarding with cleared eligibility.",
            "operational_impact": "Requires explicit admin choice on promo/bypass — not a silent override.",
        },
        CLASS_PARTIAL_PROVISIONING: {
            "blockage_summary": "Payment may have succeeded but provisioning did not complete.",
            "recommended_action": "Escalate for provisioning review before customer-facing recovery.",
            "expected_customer_outcome": "Customer receives activation only after provisioning is reconciled.",
            "operational_impact": "High impact — avoid duplicate provisioning or subscriptions.",
        },
        CLASS_ACTIVATION_INCOMPLETE: {
            "blockage_summary": "Subscription is active but portal activation is incomplete.",
            "recommended_action": "Resend activation and password setup email.",
            "expected_customer_outcome": "Customer receives activation email and can set a password.",
            "operational_impact": "No payment regeneration required.",
        },
        CLASS_SUBSCRIPTION_DRIFT: {
            "blockage_summary": "Stripe or billing records disagree with client onboarding state.",
            "recommended_action": "Manual billing reconciliation required before any customer recovery.",
            "expected_customer_outcome": "No customer communication until billing state is verified.",
            "operational_impact": "Engineering or billing specialist escalation.",
        },
        CLASS_DUPLICATE_RECOVERY_RISK: {
            "blockage_summary": "Recovery signals conflict with an active or paid subscription.",
            "recommended_action": "Verify billing and activation state before running recovery.",
            "expected_customer_outcome": "Depends on verification — may only need activation resend.",
            "operational_impact": "Prevents duplicate subscriptions or duplicate provisioning.",
        },
        CLASS_RECOVERY_ALREADY_ACTIVE: {
            "blockage_summary": "A recovery checkout link was sent recently and may still be valid.",
            "recommended_action": "Wait for customer action or confirm the prior link expired before regenerating.",
            "expected_customer_outcome": "Customer should use the existing payment link if still valid.",
            "operational_impact": "Avoid stacking multiple active checkout sessions.",
        },
        CLASS_UNKNOWN_RECOVERY_STATE: {
            "blockage_summary": "Onboarding appears stranded but the blockage could not be classified confidently.",
            "recommended_action": "Review redemption, billing, and provisioning history; escalate if unclear.",
            "expected_customer_outcome": "Determined after manual review.",
            "operational_impact": "Do not run hidden overrides — use guided recovery once classified.",
        },
    }
    base = copies.get(classification, copies[CLASS_UNKNOWN_RECOVERY_STATE])
    if strategy.get("phase") == 1 and strategy.get("recommended_mode"):
        base = {
            **base,
            "recommended_action": base["recommended_action"].replace("(Phase 2)", "(coming in Phase 2)"),
        }
    return base


async def detect_stranded_onboarding(client_id: str) -> Dict[str, Any]:
    """Gather detection inputs for classification."""
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return {"client_id": client_id, "found": False, "is_stranded": False}

    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    portal_user = await db.portal_users.find_one(
        {"client_id": client_id},
        {"_id": 0, "portal_user_id": 1, "password_status": 1, "status": 1, "auth_email": 1},
    )
    promo_context = await get_account_promo_recovery_context(client_id, limit=50)
    indicators = promo_context.get("indicators") or {}
    redemptions = promo_context.get("redemptions") or []

    subscription_drift = _detect_subscription_drift(client, billing)
    is_stranded = _compute_is_stranded(client, indicators, portal_user, billing)

    provisioning_rows = (
        await db.provisioning_jobs.find(
            {"client_id": client_id},
            {"_id": 0, "job_id": 1, "status": 1, "updated_at": 1, "last_error": 1},
        )
        .sort("updated_at", -1)
        .limit(1)
        .to_list(1)
    )
    provisioning_job = provisioning_rows[0] if provisioning_rows else None

    recovery_history = _build_recovery_history(client, redemptions, promo_context.get("waiver_history") or [])

    return {
        "client_id": client_id,
        "found": True,
        "client": client,
        "billing": billing,
        "portal_user": portal_user,
        "indicators": indicators,
        "redemptions": redemptions,
        "promo_context": promo_context,
        "subscription_drift": subscription_drift,
        "is_stranded": is_stranded,
        "provisioning_job": provisioning_job,
        "recovery_history": recovery_history,
        "checkout_fresh": _checkout_is_fresh(client),
        "paid_or_active": _is_paid_or_active(client, billing),
    }


def _detect_subscription_drift(client: Dict[str, Any], billing: Optional[Dict[str, Any]]) -> bool:
    if not billing:
        return False
    client_sub = (client.get("stripe_subscription_id") or "").strip()
    billing_sub = (billing.get("stripe_subscription_id") or "").strip()
    if client_sub and billing_sub and client_sub != billing_sub:
        return True
    client_status = (client.get("subscription_status") or "").lower()
    billing_status = (billing.get("subscription_status") or "").lower()
    if client_status and billing_status and client_status != billing_status:
        active_pair = client_status in _SUBSCRIPTION_ACTIVE
        billing_active = billing_status in _SUBSCRIPTION_ACTIVE
        if active_pair != billing_active:
            return True
    return False


def _compute_is_stranded(
    client: Dict[str, Any],
    indicators: Dict[str, Any],
    portal_user: Optional[Dict[str, Any]],
    billing: Optional[Dict[str, Any]],
) -> bool:
    if indicators.get("stranded_onboarding"):
        return True
    if not _is_paid_or_active(client, billing):
        ob = (client.get("onboarding_status") or "").upper()
        if ob != OnboardingStatus.PROVISIONED.value:
            return True
        lifecycle = (client.get("lifecycle_status") or "").lower()
        if lifecycle in ("pending_payment", "abandoned"):
            return True
    if portal_user and portal_user.get("password_status") != PasswordStatus.SET.value:
        if _is_paid_or_active(client, billing) and (client.get("onboarding_status") or "").upper() == OnboardingStatus.PROVISIONED.value:
            return True
    return False


def _build_recovery_history(
    client: Dict[str, Any],
    redemptions: List[Dict[str, Any]],
    waiver_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    if client.get("checkout_link_sent_at"):
        attempts.append(
            {
                "type": "checkout_link_sent",
                "at": client.get("checkout_link_sent_at"),
                "session_id": client.get("latest_checkout_session_id"),
                "fresh": _checkout_is_fresh(client),
            }
        )
    for w in waiver_history[:5]:
        attempts.append(
            {
                "type": "eligibility_override",
                "override_type": w.get("override_type"),
                "at": w.get("override_created_at"),
                "reason_preview": (w.get("override_reason") or "")[:120],
            }
        )
    for r in redemptions[:3]:
        attempts.append(
            {
                "type": "redemption_attempt",
                "status": r.get("status"),
                "at": r.get("created_at"),
                "redemption_id": r.get("redemption_id"),
            }
        )
    return {
        "attempts": attempts,
        "recovery_attempt_count": len(attempts),
        "last_checkout_sent_at": client.get("checkout_link_sent_at"),
        "last_recovery_checkout_id": client.get("latest_checkout_session_id"),
    }


async def build_onboarding_recovery_assessment(client_id: str) -> Dict[str, Any]:
    """Full read-only assessment payload for admin UI."""
    signals = await detect_stranded_onboarding(client_id)
    if not signals.get("found"):
        return {"client_id": client_id, "found": False}

    classification = classify_recovery_state(signals)
    strategy = derive_recovery_strategy(classification, signals)
    risk = derive_recovery_risk(classification, signals)
    continuation_mode = derive_customer_continuation_mode(classification, strategy)
    eligibility = validate_recovery_eligibility(classification, signals)
    execution_available, phase = derive_execution_availability(classification, strategy, eligibility)
    executable_modes = derive_executable_modes(classification, strategy, eligibility)
    strategy = {
        **strategy,
        "execution_available": execution_available,
        "executable_modes": executable_modes,
        "phase": phase,
    }

    recommendation = derive_recovery_recommendation_copy(classification, signals, strategy)

    client = signals.get("client") or {}
    portal_user = signals.get("portal_user") or {}

    from services.onboarding_recovery_observability_service import get_client_onboarding_recovery_observability

    observability = await get_client_onboarding_recovery_observability(client_id)
    recovery_history = signals.get("recovery_history") or {}
    governed_events = observability.get("events") or []
    if governed_events:
        merged_attempts = list(recovery_history.get("attempts") or [])
        for ev in governed_events[:10]:
            merged_attempts.insert(
                0,
                {
                    "type": "governed_recovery",
                    "event_type": ev.get("event_type"),
                    "mode": ev.get("mode"),
                    "at": ev.get("created_at"),
                    "continuation_delivered": ev.get("continuation_delivered"),
                    "email_sent": ev.get("email_sent"),
                },
            )
        recovery_history = {
            **recovery_history,
            "attempts": merged_attempts,
            "governed_event_count": len(governed_events),
        }

    return {
        "client_id": client_id,
        "found": True,
        "is_stranded": signals.get("is_stranded"),
        "classification": classification,
        "risk": risk,
        "strategy": strategy,
        "customer_continuation_mode": continuation_mode,
        "eligibility": eligibility,
        "recommendation": recommendation,
        "state_summary": {
            "customer_reference": client.get("customer_reference"),
            "onboarding_status": client.get("onboarding_status"),
            "provisioning_status": client.get("provisioning_status"),
            "subscription_status": client.get("subscription_status"),
            "lifecycle_status": client.get("lifecycle_status"),
            "billing_lifecycle_state": (signals.get("billing") or {}).get("billing_lifecycle_state")
            or client.get("billing_lifecycle_state"),
            "password_set": portal_user.get("password_status") == PasswordStatus.SET.value if portal_user else None,
            "checkout_link_sent_at": client.get("checkout_link_sent_at"),
            "checkout_fresh": signals.get("checkout_fresh"),
            "paid_or_active": signals.get("paid_or_active"),
            "activation_email_sent": bool(client.get("activation_email_sent_at")),
        },
        "recovery_history": signals.get("recovery_history"),
        "indicators": signals.get("indicators"),
        "completion_rule": (
            "Recovery is complete only when the customer has a valid, observable continuation path — "
            "not when internal state mutation succeeds."
        ),
        "phase": phase,
        "execution_available": execution_available,
        "executable_modes": executable_modes,
        "observability": observability if observability.get("found") else None,
    }
