"""
Governed customer-facing copy for lifecycle recovery and capability denial.

CAP_* identifiers belong in logs, diagnostics, and audit evidence — not customer UI.
"""
from __future__ import annotations

from typing import Literal, Optional

from services.account_lifecycle_runtime_contract import GRANT_DENY, GRANT_HIDDEN, GRANT_PLAN_GATED, GRANT_READ

CapabilityAction = Literal["read", "write"]

# Portal-mode denial copy for restricted lifecycle states (P0 lifecycle recovery UX).
PORTAL_MODE_CAPABILITY_DENIAL: dict[str, str] = {
    "SUSPENDED": (
        "This area is unavailable while your account is suspended. "
        "Resolve payment to restore access."
    ),
    "BILLING_RECOVERY": (
        "This area is unavailable while your subscription is inactive. "
        "Resubscribe in Billing to restore access."
    ),
    "PAYMENT_REQUIRED": (
        "This area is unavailable until setup is complete. "
        "Choose a plan in Billing to continue."
    ),
    "GRACE": (
        "This area is unavailable until your payment issue is resolved. "
        "Update your payment method in Billing."
    ),
    "READ_ONLY": (
        "This area is in view-only mode. Subscribe in Billing to make changes."
    ),
    "ARCHIVED": (
        "This area is unavailable while your account is archived. "
        "Contact support for assistance."
    ),
    "ACCOUNT_DELETED": "This area is unavailable. This account has been removed.",
}

DEFAULT_CAPABILITY_DENIAL = "This action is not available for your account."
PLAN_GATED_DENIAL = (
    "This feature is not included in your current plan. "
    "View plans in Billing to upgrade."
)
HIDDEN_DENIAL = "This area is not available for your account."
READ_ONLY_WRITE_DENIAL = (
    "This area is view-only for your account. Subscribe in Billing to make changes."
)


def is_lifecycle_restricted_portal_mode(portal_mode: Optional[str]) -> bool:
    return bool(portal_mode and portal_mode != "FULL_ACCESS")


def capability_denial_customer_message(
    *,
    portal_mode: Optional[str] = None,
    grant: str = GRANT_DENY,
    action: CapabilityAction = "read",
) -> str:
    """Customer-safe denial message — never exposes raw CAP_* identifiers."""
    if is_lifecycle_restricted_portal_mode(portal_mode):
        return PORTAL_MODE_CAPABILITY_DENIAL.get(portal_mode or "", DEFAULT_CAPABILITY_DENIAL)

    if grant == GRANT_PLAN_GATED:
        return PLAN_GATED_DENIAL
    if grant == GRANT_HIDDEN:
        return HIDDEN_DENIAL
    if grant == GRANT_READ and action == "write":
        return READ_ONLY_WRITE_DENIAL
    return DEFAULT_CAPABILITY_DENIAL


def contains_internal_capability_language(message: str) -> bool:
    if not message:
        return False
    upper = message.upper()
    return "CAP_" in upper and (
        " IS NOT PERMITTED" in upper
        or " IS NOT AVAILABLE" in upper
        or "ACCESS REQUIRES CAP_" in upper
    )
