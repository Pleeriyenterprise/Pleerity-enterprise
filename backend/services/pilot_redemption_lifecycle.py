"""
Redemption lifecycle states for pilot/promo invite attempts.

Only terminal redeemed/completed states consume first-time eligibility and duplicate caps.
Recoverable states allow automatic retry without admin intervention (within grace window).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set


class PilotRedemptionStatus(str, Enum):
    PENDING = "pending"
    PAYMENT_STARTED = "payment_started"
    PAYMENT_FAILED = "payment_failed"
    PROVISIONING_FAILED = "provisioning_failed"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    REVOKED = "revoked"
    # Legacy alias — reads/writes may still encounter this until fully migrated
    COMPLETED = "completed"


TERMINAL_CONSUMING_STATUSES: FrozenSet[str] = frozenset(
    {PilotRedemptionStatus.REDEEMED.value, PilotRedemptionStatus.COMPLETED.value}
)

RECOVERABLE_STATUSES: FrozenSet[str] = frozenset(
    {
        PilotRedemptionStatus.PENDING.value,
        PilotRedemptionStatus.PAYMENT_STARTED.value,
        PilotRedemptionStatus.PAYMENT_FAILED.value,
        PilotRedemptionStatus.PROVISIONING_FAILED.value,
        PilotRedemptionStatus.EXPIRED.value,
        PilotRedemptionStatus.REVOKED.value,
    }
)

# Statuses that block duplicate redemption while still recoverable (within grace only for pending)
ACTIVE_RESERVATION_STATUSES: FrozenSet[str] = frozenset(
    {
        PilotRedemptionStatus.PENDING.value,
        PilotRedemptionStatus.PAYMENT_STARTED.value,
    }
)


def redemption_retry_grace_hours() -> int:
    try:
        return max(1, int(os.environ.get("PILOT_REDEMPTION_RETRY_GRACE_HOURS", "72")))
    except (TypeError, ValueError):
        return 72


def normalize_redemption_status(raw: Optional[str]) -> str:
    s = str(raw or "").strip().lower()
    if s == PilotRedemptionStatus.COMPLETED.value:
        return PilotRedemptionStatus.REDEEMED.value
    if s in {e.value for e in PilotRedemptionStatus}:
        return s
    return PilotRedemptionStatus.PENDING.value


def is_terminal_consuming(status: Optional[str]) -> bool:
    return normalize_redemption_status(status) in TERMINAL_CONSUMING_STATUSES


def is_recoverable(status: Optional[str]) -> bool:
    return normalize_redemption_status(status) in RECOVERABLE_STATUSES


def status_filter_terminal_consuming() -> Dict[str, Any]:
    """Mongo filter matching legacy completed + redeemed."""
    return {"status": {"$in": list(TERMINAL_CONSUMING_STATUSES)}}


def status_filter_blocks_duplicate(include_grace_pending: bool = True) -> Dict[str, Any]:
    """
    Statuses that should block a new redemption for same email/customer.
    Pending only counts if include_grace_pending and not past grace (handled in query layer).
    """
    statuses = list(TERMINAL_CONSUMING_STATUSES)
    if include_grace_pending:
        statuses.extend(ACTIVE_RESERVATION_STATUSES)
    return {"status": {"$in": statuses}}


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def pending_within_grace(redemption: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    """True if a pending/payment_started row is still inside the automatic retry window."""
    now = now or datetime.now(timezone.utc)
    st = normalize_redemption_status(redemption.get("status"))
    if st not in ACTIVE_RESERVATION_STATUSES:
        return False
    created = _parse_dt(redemption.get("created_at"))
    if not created:
        return True
    grace = timedelta(hours=redemption_retry_grace_hours())
    return (now - created) <= grace


def redemption_retry_eligible(redemption: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    """Whether this attempt no longer blocks the user from trying again (without override)."""
    st = normalize_redemption_status(redemption.get("status"))
    if st in TERMINAL_CONSUMING_STATUSES:
        return False
    if st in (
        PilotRedemptionStatus.PAYMENT_FAILED.value,
        PilotRedemptionStatus.PROVISIONING_FAILED.value,
        PilotRedemptionStatus.EXPIRED.value,
        PilotRedemptionStatus.REVOKED.value,
    ):
        return True
    if st in ACTIVE_RESERVATION_STATUSES:
        return not pending_within_grace(redemption, now=now)
    return True


def summarize_redemption_for_admin(redemption: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    st = normalize_redemption_status(redemption.get("status"))
    return {
        "redemption_id": redemption.get("redemption_id"),
        "status": st,
        "legacy_status": redemption.get("status"),
        "invite_code_id": redemption.get("invite_code_id"),
        "code": redemption.get("code"),
        "code_type": redemption.get("code_type"),
        "campaign_name": redemption.get("campaign_name"),
        "client_id": redemption.get("client_id"),
        "checkout_session_id": redemption.get("checkout_session_id"),
        "redemption_email": redemption.get("redemption_email"),
        "plan_code": redemption.get("plan_code"),
        "created_at": redemption.get("created_at"),
        "updated_at": redemption.get("updated_at"),
        "completed_at": redemption.get("completed_at"),
        "failure_reason": redemption.get("failure_reason"),
        "retry_eligible": redemption_retry_eligible(redemption, now=now),
        "within_grace": pending_within_grace(redemption, now=now) if st in ACTIVE_RESERVATION_STATUSES else False,
        "consumes_eligibility": is_terminal_consuming(st),
    }
