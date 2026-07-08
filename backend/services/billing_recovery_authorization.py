"""
Governed billing recovery authorization helpers (customer portal).

Used by billing routes to decide when Stripe portal preflight failures may fall back
to deployment Checkout without loosening global CAP_* or Runtime Contract rules.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from services.account_capability_enforcement import CapabilityEnforcementService

GRANT_ALLOW = "ALLOW"

_TERMINAL_BILLING_LIFECYCLES = frozenset({"ARCHIVED", "ACCOUNT_DELETED"})


def billing_recovery_write_allowed(contract: Optional[Mapping[str, Any]]) -> bool:
    """
    True when Runtime Contract permits billing recovery write (checkout / portal fallback).
    Requires CAP_BILLING_CHECKOUT write semantics and non-terminal lifecycle.
    """
    if not contract:
        return False
    lifecycle = str(contract.get("lifecycle_state") or "")
    if lifecycle in _TERMINAL_BILLING_LIFECYCLES:
        return False
    return CapabilityEnforcementService(None).evaluate_from_contract(
        contract,
        "CAP_BILLING_CHECKOUT",
        "write",
    ).allowed


def resolve_recovery_plan_code(
    billing: Optional[Mapping[str, Any]],
    client: Optional[Mapping[str, Any]] = None,
) -> Optional[str]:
    """Best-effort plan code for recovery checkout (no hard-coded account defaults)."""
    for source in (billing, client):
        if not source:
            continue
        for key in ("current_plan_code", "billing_plan", "plan_code"):
            value = source.get(key)
            if value and str(value).strip():
                return str(value).strip()
    return None
