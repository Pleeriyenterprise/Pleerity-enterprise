"""
Applicability provenance enums and validation (PR1 governance spine).

v1 actively persists only PIPELINE and OPERATOR_OVERRIDE.
RECONCILIATION_LOCK and SYSTEM_FALLBACK are reserved for future use — do not
emit them from selector or backfill in v1.
"""
from __future__ import annotations

from typing import FrozenSet, Literal, Tuple

ApplicabilityTriState = Literal["REQUIRED", "NOT_REQUIRED", "UNKNOWN"]

PIPELINE = "PIPELINE"
OPERATOR_OVERRIDE = "OPERATOR_OVERRIDE"
# Reserved — not used by selector or backfill in v1
RECONCILIATION_LOCK = "RECONCILIATION_LOCK"
SYSTEM_FALLBACK = "SYSTEM_FALLBACK"

ApplicabilityResolutionSourceV1 = Literal["PIPELINE", "OPERATOR_OVERRIDE"]

ACTIVE_RESOLUTION_SOURCES_V1: FrozenSet[str] = frozenset({PIPELINE, OPERATOR_OVERRIDE})
RESERVED_RESOLUTION_SOURCES: FrozenSet[str] = frozenset({RECONCILIATION_LOCK, SYSTEM_FALLBACK})
ALL_KNOWN_RESOLUTION_SOURCES: FrozenSet[str] = frozenset(
    {PIPELINE, OPERATOR_OVERRIDE, RECONCILIATION_LOCK, SYSTEM_FALLBACK}
)


def is_active_resolution_source_v1(value: str) -> bool:
    return str(value or "").strip().upper() in ACTIVE_RESOLUTION_SOURCES_V1


def validate_resolution_source_for_persist(value: str) -> Tuple[bool, str]:
    v = str(value or "").strip().upper()
    if v in RESERVED_RESOLUTION_SOURCES:
        return False, f"resolution source {v} is reserved and not supported in v1"
    if v not in ACTIVE_RESOLUTION_SOURCES_V1:
        return False, f"unknown applicability_resolution_source: {value!r}"
    return True, ""


def normalize_applicability_tri_state(raw: object) -> ApplicabilityTriState:
    s = str(raw or "").strip().upper()
    if s in ("REQUIRED", "NOT_REQUIRED", "UNKNOWN"):
        return s  # type: ignore[return-value]
    return "UNKNOWN"
