"""Deterministic conversion-risk flags for pilot accounts (no LLM)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from models.pilot_lifecycle import PilotStatus
from models.pilot_operational import PilotGovernanceStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _effective_expiry(client: Dict[str, Any]) -> Optional[datetime]:
    candidates = []
    for key in ("pilot_expires_at", "pilot_extended_until"):
        dt = _parse_dt(client.get(key))
        if dt:
            candidates.append(dt)
    return max(candidates) if candidates else None


def compute_conversion_risk_flags(
    client: Dict[str, Any],
    *,
    billing: Optional[Dict[str, Any]] = None,
    days_to_expiry_warning: int = 14,
) -> Dict[str, Any]:
    billing = billing or {}
    now = _utc_now()
    gov = str(client.get("pilot_governance_status") or client.get("pilot_status") or "").lower()
    if gov == PilotStatus.CONVERTED_TO_PAID.value:
        gov = PilotGovernanceStatus.CONVERTED.value

    eff = _effective_expiry(client)
    days_remaining = None
    if eff:
        days_remaining = max(0, (eff - now).days)

    expected_paid = _parse_dt(client.get("pilot_expected_first_paid_invoice_at"))
    approaching_paid = False
    if expected_paid:
        approaching_paid = 0 <= (expected_paid - now).days <= days_to_expiry_warning

    pm_collected = bool(client.get("pilot_stripe_payment_method_collected"))
    onboarding_done = str(client.get("onboarding_status") or "").upper() == "PROVISIONED"

    active_gov = gov in (
        PilotGovernanceStatus.ACTIVE.value,
        PilotGovernanceStatus.EXTENDED.value,
        PilotStatus.ACTIVE.value,
        PilotStatus.EXTENDED.value,
    )
    inactive_before_conversion = active_gov and not onboarding_done and (days_remaining is not None and days_remaining <= 21)

    sub_status = str(billing.get("subscription_status") or client.get("subscription_status") or "").upper()
    likely_conversion = (
        active_gov
        and pm_collected
        and onboarding_done
        and days_remaining is not None
        and days_remaining <= days_to_expiry_warning
        and sub_status in ("TRIALING", "ACTIVE", "")
    )
    likely_churn = (
        (gov == PilotGovernanceStatus.EXPIRED.value or gov == PilotStatus.EXPIRED.value)
        and not client.get("pilot_converted_to_paid_at")
    ) or bool(client.get("pilot_cancelled_before_paid_conversion"))

    return {
        "likely_conversion": likely_conversion,
        "likely_churn": likely_churn,
        "missing_payment_method": active_gov and not pm_collected,
        "inactive_before_conversion": inactive_before_conversion,
        "approaching_paid_transition": approaching_paid or (
            days_remaining is not None and days_remaining <= days_to_expiry_warning and active_gov
        ),
        "pilot_expired_without_conversion": gov in (
            PilotGovernanceStatus.EXPIRED.value,
            PilotStatus.EXPIRED.value,
        )
        and not client.get("pilot_converted_to_paid_at"),
        "days_remaining": days_remaining,
        "onboarding_completed": onboarding_done,
        "payment_method_collected": pm_collected,
    }
