"""Detect MongoDB Atlas / WiredTiger capacity errors for safe 503 responses."""
from __future__ import annotations

from typing import Any, Optional


_CAPACITY_MARKERS = (
    "you exceeded the size limit",
    "disk is full",
    "out of disk space",
    "quota exceeded",
    "space quota",
    "storage limit",
    "write results unavailable",
    "cannot allocate memory",
)


def is_mongo_capacity_error(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    return any(m in text for m in _CAPACITY_MARKERS)


def capacity_unavailable_payload(detail: Optional[str] = None) -> dict[str, Any]:
    return {
        "detail": detail
        or "Database storage capacity exceeded. Writes are temporarily unavailable.",
        "code": "DATABASE_CAPACITY_EXCEEDED",
        "retryable": True,
    }
