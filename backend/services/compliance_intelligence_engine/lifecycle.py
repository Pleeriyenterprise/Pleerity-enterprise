"""Intelligence artefact lifecycle states and transition rules (base)."""
from __future__ import annotations

from typing import Dict, FrozenSet, Tuple

LIFECYCLE_GENERATED = "generated"
LIFECYCLE_VALIDATED = "validated"
LIFECYCLE_PUBLISHED = "published"
LIFECYCLE_CONSUMED = "consumed"
LIFECYCLE_SUPERSEDED = "superseded"
LIFECYCLE_CANCELLED = "cancelled"
LIFECYCLE_EXPIRED = "expired"
LIFECYCLE_ARCHIVED = "archived"

# Recommendation extension states (CIE-2+)
LIFECYCLE_ACCEPTED = "accepted"
LIFECYCLE_SCHEDULED = "scheduled"
LIFECYCLE_IN_PROGRESS = "in_progress"
LIFECYCLE_COMPLETED = "completed"

BASE_LIFECYCLE_STATES: FrozenSet[str] = frozenset(
    {
        LIFECYCLE_GENERATED,
        LIFECYCLE_VALIDATED,
        LIFECYCLE_PUBLISHED,
        LIFECYCLE_CONSUMED,
        LIFECYCLE_SUPERSEDED,
        LIFECYCLE_CANCELLED,
        LIFECYCLE_EXPIRED,
        LIFECYCLE_ARCHIVED,
    }
)

RECOMMENDATION_LIFECYCLE_STATES: FrozenSet[str] = BASE_LIFECYCLE_STATES | frozenset(
    {
        LIFECYCLE_ACCEPTED,
        LIFECYCLE_SCHEDULED,
        LIFECYCLE_IN_PROGRESS,
        LIFECYCLE_COMPLETED,
    }
)

ALL_LIFECYCLE_STATES: FrozenSet[str] = RECOMMENDATION_LIFECYCLE_STATES

BASE_VALID_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    LIFECYCLE_GENERATED: frozenset(
        {LIFECYCLE_VALIDATED, LIFECYCLE_PUBLISHED, LIFECYCLE_SUPERSEDED, LIFECYCLE_CANCELLED}
    ),
    LIFECYCLE_VALIDATED: frozenset({LIFECYCLE_PUBLISHED, LIFECYCLE_SUPERSEDED, LIFECYCLE_CANCELLED}),
    LIFECYCLE_PUBLISHED: frozenset({LIFECYCLE_CONSUMED, LIFECYCLE_SUPERSEDED, LIFECYCLE_CANCELLED, LIFECYCLE_EXPIRED}),
    LIFECYCLE_CONSUMED: frozenset({LIFECYCLE_ARCHIVED}),
    LIFECYCLE_SUPERSEDED: frozenset({LIFECYCLE_ARCHIVED}),
    LIFECYCLE_CANCELLED: frozenset({LIFECYCLE_ARCHIVED}),
    LIFECYCLE_EXPIRED: frozenset({LIFECYCLE_ARCHIVED}),
    LIFECYCLE_ARCHIVED: frozenset(),
}


def is_valid_lifecycle_state(state: str) -> bool:
    return (state or "").strip().lower() in ALL_LIFECYCLE_STATES


def can_transition(from_state: str, to_state: str, *, matrix: Dict[str, FrozenSet[str]] | None = None) -> bool:
    matrix = matrix or BASE_VALID_TRANSITIONS
    allowed = matrix.get((from_state or "").strip().lower(), frozenset())
    return (to_state or "").strip().lower() in allowed


def validate_transition(from_state: str, to_state: str) -> Tuple[bool, str]:
    if not is_valid_lifecycle_state(from_state):
        return False, f"invalid_from_state:{from_state}"
    if not is_valid_lifecycle_state(to_state):
        return False, f"invalid_to_state:{to_state}"
    if not can_transition(from_state, to_state):
        return False, f"transition_not_allowed:{from_state}->{to_state}"
    return True, "ok"
