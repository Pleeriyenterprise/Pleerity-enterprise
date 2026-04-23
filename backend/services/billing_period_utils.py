"""Helpers for Stripe subscription period boundaries (avoid invalid / epoch dates)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Reject Unix 0 and other pre-2000 timestamps (bad sync / missing Stripe field)
MIN_VALID_PERIOD_END_TS = 946684800  # 2000-01-01 00:00:00 UTC


def coerce_stored_period_end_to_datetime(cpe: Any) -> Optional[datetime]:
    """
    Normalize values read from ``client_billing`` (Mongo may store datetime, ISO string, or unix int).
    Returns timezone-aware UTC datetime or None.
    """
    if cpe is None:
        return None
    if isinstance(cpe, datetime):
        if cpe.tzinfo is None:
            dt = cpe.replace(tzinfo=timezone.utc)
        else:
            dt = cpe.astimezone(timezone.utc)
        try:
            if dt.timestamp() < MIN_VALID_PERIOD_END_TS:
                return None
        except (OSError, OverflowError, ValueError):
            return None
        return dt
    if isinstance(cpe, (int, float)):
        try:
            t = int(cpe)
        except (TypeError, ValueError):
            return None
        if t < MIN_VALID_PERIOD_END_TS:
            return None
        return datetime.fromtimestamp(t, tz=timezone.utc)
    if isinstance(cpe, str):
        s = cpe.strip()
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        try:
            if dt.timestamp() < MIN_VALID_PERIOD_END_TS:
                return None
        except (OSError, OverflowError, ValueError):
            return None
        return dt
    return None


def period_end_from_stripe_unix(ts: Any) -> Optional[datetime]:
    """Return timezone-aware UTC datetime or None if Stripe value is missing/invalid."""
    if ts is None:
        return None
    if isinstance(ts, str):
        s = ts.strip()
        if not s:
            return None
        try:
            t = int(float(s))
        except (TypeError, ValueError):
            return None
    else:
        try:
            t = int(ts)
        except (TypeError, ValueError):
            return None
    if t < MIN_VALID_PERIOD_END_TS:
        return None
    return datetime.fromtimestamp(t, tz=timezone.utc)


def period_end_from_stripe_subscription_dict(sub_d: Dict[str, Any]) -> Optional[datetime]:
    """
    Resolve subscription period end for persistence and UI.

    Stripe's subscription object may omit top-level ``current_period_end`` (e.g. flexible billing);
    subscription items still expose ``current_period_end`` per line. Prefer the latest end among items.
    """
    top = period_end_from_stripe_unix(sub_d.get("current_period_end"))
    if top:
        return top
    best: Optional[datetime] = None
    for item in (sub_d.get("items") or {}).get("data") or []:
        if not isinstance(item, dict):
            continue
        cand = period_end_from_stripe_unix(item.get("current_period_end"))
        if cand and (best is None or cand > best):
            best = cand
    return best


def period_start_from_stripe_subscription_dict(sub_d: Dict[str, Any]) -> Optional[datetime]:
    """Same as period end: top-level first, then earliest valid start among subscription items."""
    top = period_start_from_stripe_unix(sub_d.get("current_period_start"))
    if top:
        return top
    best: Optional[datetime] = None
    for item in (sub_d.get("items") or {}).get("data") or []:
        if not isinstance(item, dict):
            continue
        cand = period_start_from_stripe_unix(item.get("current_period_start"))
        if cand and (best is None or cand < best):
            best = cand
    return best


def period_start_from_stripe_unix(ts: Any) -> Optional[datetime]:
    """Same validation as period end — subscription current_period_start must not be epoch garbage."""
    return period_end_from_stripe_unix(ts)


def period_end_stored_value_is_valid(cpe: Any) -> bool:
    """True if stored value is a real renewal date (not epoch)."""
    return coerce_stored_period_end_to_datetime(cpe) is not None


def normalize_stored_period_end_for_api(cpe: Any) -> Optional[datetime]:
    """Return datetime suitable for JSON encoding, or None."""
    return coerce_stored_period_end_to_datetime(cpe)
