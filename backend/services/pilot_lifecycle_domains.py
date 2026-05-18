"""
Separated pilot lifecycle domains — explicit ownership:

- Stripe → pilot_billing_status
- Platform governance → pilot_governance_status (from pilot_status)
- Entitlement engine → pilot_entitlement_status (from canonical_entitlement_state)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from models.pilot_lifecycle import PilotStatus
from models.pilot_operational import (
    PilotBillingStatus,
    PilotEntitlementStatus,
    PilotGovernanceStatus,
)
from services.entitlement_access import compute_canonical_entitlement_state

logger = logging.getLogger(__name__)

_CANON_TO_ENTITLEMENT = {
    "ENABLED": PilotEntitlementStatus.ENABLED.value,
    "GRACE": PilotEntitlementStatus.GRACE_PERIOD.value,
    "SUSPENDED": PilotEntitlementStatus.SUSPENDED.value,
    "CANCELLED": PilotEntitlementStatus.REVOKED.value,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def derive_pilot_governance_status(client: Dict[str, Any]) -> str:
    raw = str(client.get("pilot_status") or "").lower()
    if raw == PilotStatus.CONVERTED_TO_PAID.value:
        return PilotGovernanceStatus.CONVERTED.value
    mapping = {
        PilotStatus.ACTIVE.value: PilotGovernanceStatus.ACTIVE.value,
        PilotStatus.EXTENDED.value: PilotGovernanceStatus.EXTENDED.value,
        PilotStatus.EXPIRED.value: PilotGovernanceStatus.EXPIRED.value,
        PilotStatus.CANCELLED.value: PilotGovernanceStatus.CANCELLED.value,
        PilotStatus.COMPED.value: PilotGovernanceStatus.COMPED.value,
        PilotStatus.PAUSED.value: PilotGovernanceStatus.PAUSED.value,
    }
    return mapping.get(raw, PilotGovernanceStatus.ACTIVE.value if raw else "")


def derive_pilot_billing_status(
    client: Dict[str, Any],
    billing: Optional[Dict[str, Any]] = None,
) -> str:
    billing = billing or {}
    sub = (
        str(billing.get("subscription_status") or client.get("subscription_status") or "")
        .strip()
        .upper()
    )
    lc = str(billing.get("billing_lifecycle_state") or client.get("billing_lifecycle_state") or "").lower()

    if lc == "cancelled" or sub in ("CANCELED", "CANCELLED"):
        return PilotBillingStatus.CANCELLED.value
    if sub == "UNPAID":
        return PilotBillingStatus.UNPAID.value
    if sub == "PAST_DUE" or lc == "past_due":
        return PilotBillingStatus.PAST_DUE.value
    if sub in ("INCOMPLETE", "INCOMPLETE_EXPIRED"):
        return PilotBillingStatus.INCOMPLETE.value
    if sub == "TRIALING":
        return PilotBillingStatus.TRIALING.value
    if sub == "ACTIVE" or lc in ("active", "renewing"):
        return PilotBillingStatus.ACTIVE.value
    if not sub and not billing.get("stripe_subscription_id"):
        return PilotBillingStatus.NONE.value
    return PilotBillingStatus.NONE.value


def derive_pilot_entitlement_status(
    client: Dict[str, Any],
    billing: Optional[Dict[str, Any]] = None,
) -> str:
    billing = billing or {}
    if str(client.get("pilot_status") or "").lower() == PilotStatus.COMPED.value:
        return PilotEntitlementStatus.ENABLED.value
    if client.get("pilot_governance_revoke_access") and str(client.get("pilot_status") or "").lower() == PilotStatus.CANCELLED.value:
        return PilotEntitlementStatus.REVOKED.value

    canon = billing.get("canonical_entitlement_state") or client.get("canonical_entitlement_state")
    if not canon:
        lc = str(billing.get("billing_lifecycle_state") or client.get("billing_lifecycle_state") or "active")
        sub = str(billing.get("subscription_status") or client.get("subscription_status") or "")
        canon = compute_canonical_entitlement_state(
            billing_lifecycle_state=lc,
            subscription_status_upper=sub,
        )
    return _CANON_TO_ENTITLEMENT.get(str(canon).upper(), PilotEntitlementStatus.SUSPENDED.value)


def build_lifecycle_domains_snapshot(
    client: Dict[str, Any],
    billing: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    return {
        "pilot_governance_status": derive_pilot_governance_status(client),
        "pilot_billing_status": derive_pilot_billing_status(client, billing),
        "pilot_entitlement_status": derive_pilot_entitlement_status(client, billing),
    }


def detect_domain_inconsistencies(
    client: Dict[str, Any],
    billing: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return structured inconsistency records (feeds anomaly engine)."""
    billing = billing or {}
    gov = derive_pilot_governance_status(client)
    bill = derive_pilot_billing_status(client, billing)
    ent = derive_pilot_entitlement_status(client, billing)
    issues: List[Dict[str, Any]] = []

    if gov == PilotGovernanceStatus.EXPIRED.value and bill in (
        PilotBillingStatus.ACTIVE.value,
        PilotBillingStatus.TRIALING.value,
    ):
        issues.append(
            {
                "code": "expired_pilot_active_paid_sub",
                "message": "Pilot governance expired while Stripe subscription remains active/trialing",
                "governance": gov,
                "billing": bill,
            }
        )

    if gov == PilotGovernanceStatus.CONVERTED.value and not client.get("pilot_stripe_payment_method_collected"):
        if bill not in (PilotBillingStatus.NONE.value, PilotBillingStatus.CANCELLED.value):
            issues.append(
                {
                    "code": "converted_without_payment_method",
                    "message": "Pilot marked converted but no default payment method on file",
                    "governance": gov,
                    "billing": bill,
                }
            )

    if gov == PilotGovernanceStatus.COMPED.value and bill == PilotBillingStatus.CANCELLED.value:
        issues.append(
            {
                "code": "comped_cancelled_subscription",
                "message": "Comped pilot account has cancelled Stripe subscription",
                "governance": gov,
                "billing": bill,
            }
        )

    if ent == PilotEntitlementStatus.ENABLED.value and bill in (
        PilotBillingStatus.CANCELLED.value,
        PilotBillingStatus.NONE.value,
        PilotBillingStatus.UNPAID.value,
    ):
        if gov != PilotGovernanceStatus.COMPED.value:
            issues.append(
                {
                    "code": "entitlement_without_billing_basis",
                    "message": "Portal entitlement enabled without active Stripe billing basis",
                    "governance": gov,
                    "billing": bill,
                    "entitlement": ent,
                }
            )

    if gov == PilotGovernanceStatus.CANCELLED.value and ent == PilotEntitlementStatus.ENABLED.value:
        if not client.get("pilot_governance_revoke_access"):
            issues.append(
                {
                    "code": "invalid_state_combination",
                    "message": "Pilot cancelled in governance but entitlement still enabled",
                    "governance": gov,
                    "entitlement": ent,
                }
            )

    if gov == PilotGovernanceStatus.EXPIRED.value and not client.get("pilot_converted_to_paid_at"):
        issues.append(
            {
                "code": "pilot_expired_without_conversion",
                "message": "Pilot expired without paid conversion recorded",
                "governance": gov,
            }
        )

    return issues


async def sync_lifecycle_domains_to_client(
    client_id: str,
    *,
    client: Optional[Dict[str, Any]] = None,
    billing: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    from database import database

    db = database.get_db()
    if client is None:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise ValueError("CLIENT_NOT_FOUND")
    if billing is None:
        billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}

    domains = build_lifecycle_domains_snapshot(client, billing)
    domains["pilot_lifecycle_domains_updated_at"] = _utc_now()
    await db.clients.update_one({"client_id": client_id}, {"$set": domains})
    return domains
