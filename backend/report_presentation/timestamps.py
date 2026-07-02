"""Customer-facing vs forensic timestamp formatting."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("Z", "+00:00")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def format_customer_timestamp(value: Any, *, precision: str = "minute") -> str:
    """Professional chronology timestamp — no microseconds."""
    dt = _parse_ts(value)
    if not dt:
        return "—"
    if precision == "day":
        return dt.strftime("%d %B %Y")
    ts = dt.strftime("%d %B %Y, %H:%M")
    if dt.tzinfo is not None:
        return f"{ts} UTC"
    return ts


def format_technical_timestamp(value: Any) -> str:
    """Forensic appendix timestamp — preserves full precision from source."""
    if value is None:
        return "—"
    s = str(value).strip().replace("Z", "+00:00")
    if "T" in s:
        s = s.replace("T", " ", 1)
    s = s.replace("+00:00", " UTC")
    return s
