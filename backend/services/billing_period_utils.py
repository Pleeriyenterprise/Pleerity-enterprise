"""Helpers for Stripe subscription period boundaries (avoid invalid / epoch dates)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

# Reject Unix 0 and other pre-2000 timestamps (bad sync / missing Stripe field)
MIN_VALID_PERIOD_END_TS = 946684800  # 2000-01-01 00:00:00 UTC


def period_end_from_stripe_unix(ts: Any) -> Optional[datetime]:
    """Return timezone-aware UTC datetime or None if Stripe value is missing/invalid."""
    if ts is None:
        return None
    try:
        t = int(ts)
    except (TypeError, ValueError):
        return None
    if t < MIN_VALID_PERIOD_END_TS:
        return None
    return datetime.fromtimestamp(t, tz=timezone.utc)


def period_start_from_stripe_unix(ts: Any) -> Optional[datetime]:
    """Same validation as period end — subscription current_period_start must not be epoch garbage."""
    return period_end_from_stripe_unix(ts)


def period_end_stored_value_is_valid(cpe: Any) -> bool:
    """True if Mongo/datetime value is a real renewal date (not epoch)."""
    if cpe is None:
        return False
    if isinstance(cpe, datetime):
        try:
            return cpe.timestamp() >= MIN_VALID_PERIOD_END_TS
        except (OSError, OverflowError, ValueError):
            return False
    return False


def normalize_stored_period_end_for_api(cpe: Any) -> Optional[datetime]:
    """Return datetime suitable for JSON encoding, or None."""
    if not period_end_stored_value_is_valid(cpe):
        return None
    if isinstance(cpe, datetime):
        if cpe.tzinfo is None:
            return cpe.replace(tzinfo=timezone.utc)
        return cpe
    return None
