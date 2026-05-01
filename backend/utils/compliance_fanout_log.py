"""Structured ``extra`` for compliance fan-out observability (Stream E phase 3)."""
from __future__ import annotations

from typing import Any, Dict, Optional


def compliance_fanout_extra(
    *,
    op: str,
    stage: str,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    trigger_reason: Optional[str] = None,
    error_count: Optional[int] = None,
    exc_type: Optional[str] = None,
    dedupe: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Build a consistent ``logging`` ``extra`` payload. Values omitted when unknown.
    Callers pass ``extra=compliance_fanout_extra(...)`` — do not merge with other extras
    that reuse these keys unless intentional.
    """
    out: Dict[str, Any] = {
        "event": "compliance_fanout",
        "op": op,
        "stage": stage,
    }
    if dedupe is not None:
        out["dedupe"] = dedupe
    if client_id is not None:
        out["client_id"] = client_id
    if property_id is not None:
        out["property_id"] = property_id
    if requirement_id is not None:
        out["requirement_id"] = requirement_id
    if correlation_id is not None:
        out["correlation_id"] = correlation_id
    if trigger_reason is not None:
        out["trigger_reason"] = trigger_reason
    if error_count is not None:
        out["error_count"] = error_count
    if exc_type is not None:
        out["exc_type"] = exc_type
    return out
