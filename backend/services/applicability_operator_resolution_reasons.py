"""
Structured resolution_reason_code values for operator applicability actions (PR4).

Freeform text is not accepted as the sole justification; use ``notes`` only with a code from this set.
"""
from __future__ import annotations

from typing import FrozenSet

APPLICABILITY_OPERATOR_REASON_CODES: FrozenSet[str] = frozenset(
    {
        "HMO_CONFIRMED",
        "JURISDICTION_REQUIRED",
        "PROPERTY_TYPE_EXEMPT",
        "DUPLICATE_REQUIREMENT",
        "REGISTRY_ERROR",
        "MANUAL_LEGAL_REVIEW",
        "INSUFFICIENT_PROPERTY_METADATA",
        "DATA_CORRECTION_PENDING",
        "OTHER_GOVERNED",
    }
)


def validate_operator_resolution_reason_code(code: str) -> None:
    c = str(code or "").strip().upper()
    if c not in APPLICABILITY_OPERATOR_REASON_CODES:
        raise ValueError(
            f"invalid resolution_reason_code {code!r}; must be one of: {sorted(APPLICABILITY_OPERATOR_REASON_CODES)}"
        )
