"""
Pure applicability parsing from requirement-shaped rows (no policy fact resolution).

Separated to avoid import cycles between ``policy_field_normalizer`` and ``applicability_effective_resolver``.
"""
from __future__ import annotations

from typing import Any, Dict

APPLICABILITY_VALUES = frozenset({"REQUIRED", "NOT_REQUIRED", "UNKNOWN"})


def normalize_applicability_state(requirement_row: Dict[str, Any]) -> str:
    raw = requirement_row.get("applicability_state")
    if raw is None:
        raw = requirement_row.get("applicability")
    if raw is None and str(requirement_row.get("status") or "").strip().upper() == "NOT_REQUIRED":
        return "NOT_REQUIRED"
    st = str(raw or "").strip().upper()
    if st in APPLICABILITY_VALUES:
        return st
    return "UNKNOWN"
