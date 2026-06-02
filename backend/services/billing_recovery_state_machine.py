"""
Billing recovery state machine — audited, idempotent transitions.

Recovery orchestration assists billing truth; it does not replace it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, Optional, Tuple

STATE_MODE_UNVERIFIED = "MODE_UNVERIFIED"
STATE_RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
STATE_CHECKOUT_REGENERATED = "CHECKOUT_REGENERATED"
STATE_ADMIN_VERIFIED = "ADMIN_VERIFIED"
STATE_CUSTOMER_PENDING = "CUSTOMER_PENDING"
STATE_CUSTOMER_COMPLETED = "CUSTOMER_COMPLETED"
STATE_RECOVERY_RESOLVED = "RECOVERY_RESOLVED"
STATE_RECOVERY_FAILED = "RECOVERY_FAILED"
STATE_ESCALATED_TO_SUPPORT = "ESCALATED_TO_SUPPORT"

ALL_RECOVERY_STATES = frozenset(
    {
        STATE_MODE_UNVERIFIED,
        STATE_RECOVERY_REQUIRED,
        STATE_CHECKOUT_REGENERATED,
        STATE_ADMIN_VERIFIED,
        STATE_CUSTOMER_PENDING,
        STATE_CUSTOMER_COMPLETED,
        STATE_RECOVERY_RESOLVED,
        STATE_RECOVERY_FAILED,
        STATE_ESCALATED_TO_SUPPORT,
    }
)

ESCALATION_NORMAL = "normal"
ESCALATION_AWAITING_CUSTOMER = "awaiting_customer"
ESCALATION_AWAITING_SUPPORT = "awaiting_support"
ESCALATION_REQUIRED = "escalation_required"
ESCALATION_OPERATIONAL_RISK = "operational_risk"
ESCALATION_UNRESOLVED_BACKLOG = "unresolved_backlog"

ALL_ESCALATION_STATES = frozenset(
    {
        ESCALATION_NORMAL,
        ESCALATION_AWAITING_CUSTOMER,
        ESCALATION_AWAITING_SUPPORT,
        ESCALATION_REQUIRED,
        ESCALATION_OPERATIONAL_RISK,
        ESCALATION_UNRESOLVED_BACKLOG,
    }
)

# allowed transitions: from_state -> {to_state, ...}
_ALLOWED_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    STATE_MODE_UNVERIFIED: frozenset(
        {
            STATE_RECOVERY_REQUIRED,
            STATE_ADMIN_VERIFIED,
            STATE_ESCALATED_TO_SUPPORT,
            STATE_RECOVERY_FAILED,
        }
    ),
    STATE_RECOVERY_REQUIRED: frozenset(
        {
            STATE_CHECKOUT_REGENERATED,
            STATE_ADMIN_VERIFIED,
            STATE_CUSTOMER_PENDING,
            STATE_ESCALATED_TO_SUPPORT,
            STATE_RECOVERY_FAILED,
        }
    ),
    STATE_CHECKOUT_REGENERATED: frozenset(
        {STATE_CUSTOMER_PENDING, STATE_CUSTOMER_COMPLETED, STATE_RECOVERY_FAILED, STATE_ESCALATED_TO_SUPPORT}
    ),
    STATE_ADMIN_VERIFIED: frozenset(
        {STATE_CUSTOMER_PENDING, STATE_RECOVERY_RESOLVED, STATE_RECOVERY_FAILED, STATE_ESCALATED_TO_SUPPORT}
    ),
    STATE_CUSTOMER_PENDING: frozenset(
        {
            STATE_ADMIN_VERIFIED,
            STATE_CUSTOMER_COMPLETED,
            STATE_RECOVERY_RESOLVED,
            STATE_RECOVERY_FAILED,
            STATE_ESCALATED_TO_SUPPORT,
        }
    ),
    STATE_CUSTOMER_COMPLETED: frozenset({STATE_RECOVERY_RESOLVED, STATE_ESCALATED_TO_SUPPORT}),
    STATE_ESCALATED_TO_SUPPORT: frozenset(
        {
            STATE_RECOVERY_REQUIRED,
            STATE_CHECKOUT_REGENERATED,
            STATE_ADMIN_VERIFIED,
            STATE_RECOVERY_RESOLVED,
            STATE_RECOVERY_FAILED,
        }
    ),
    STATE_RECOVERY_FAILED: frozenset(
        {STATE_RECOVERY_REQUIRED, STATE_ESCALATED_TO_SUPPORT, STATE_CHECKOUT_REGENERATED}
    ),
    STATE_RECOVERY_RESOLVED: frozenset({STATE_RECOVERY_REQUIRED}),  # reopen only explicitly
}


class BillingRecoveryTransitionError(Exception):
    def __init__(self, message: str, *, from_state: str, to_state: str):
        super().__init__(message)
        self.from_state = from_state
        self.to_state = to_state


def initial_recovery_state(*, verification_status: Optional[str] = None) -> str:
    if (verification_status or "").strip() == "MODE_UNVERIFIED":
        return STATE_MODE_UNVERIFIED
    return STATE_RECOVERY_REQUIRED


def can_transition(from_state: str, to_state: str) -> bool:
    fs = (from_state or STATE_MODE_UNVERIFIED).strip()
    ts = (to_state or "").strip()
    if fs == ts:
        return True
    allowed = _ALLOWED_TRANSITIONS.get(fs, frozenset())
    return ts in allowed


def transition_recovery_state(
    current_state: str,
    target_state: str,
    *,
    action: str,
    actor_id: str,
    idempotency_key: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (new_state, transition_record).
    Idempotent when current == target.
    """
    cur = (current_state or STATE_MODE_UNVERIFIED).strip()
    tgt = (target_state or "").strip()
    if tgt not in ALL_RECOVERY_STATES:
        raise BillingRecoveryTransitionError(
            f"Invalid target state: {tgt}", from_state=cur, to_state=tgt
        )
    if cur == tgt:
        return cur, {
            "action": action,
            "from_state": cur,
            "to_state": tgt,
            "idempotent": True,
            "actor_id": actor_id,
            "idempotency_key": idempotency_key,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    if not can_transition(cur, tgt):
        raise BillingRecoveryTransitionError(
            f"Transition not allowed: {cur} -> {tgt}",
            from_state=cur,
            to_state=tgt,
        )
    record = {
        "action": action,
        "from_state": cur,
        "to_state": tgt,
        "idempotent": False,
        "actor_id": actor_id,
        "idempotency_key": idempotency_key,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    return tgt, record
