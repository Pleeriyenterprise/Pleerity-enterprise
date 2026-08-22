"""
Property-level compliance recalculation projection (Phase 2B).

Queue status is operational authority. ``compliance_score_pending`` means
recalculation is still owed. ``compliance_score_recalc_state`` distinguishes
actively executable work from lifecycle-parked debt.

Legacy rows (pending=true, state absent) are treated as active_pending until
a Phase 2B writer touches them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Iterable

RECALC_STATE_ACTIVE_PENDING = "active_pending"
RECALC_STATE_PARKED = "parked"
RECALC_STATE_CURRENT = "current"

PARKED_SCORE_STATUS_MESSAGE = (
    "Monitoring is paused. This score will refresh when monitoring resumes."
)

INVARIANT_PARKED_QUEUE_ACTIVE_PROPERTY = "queue_parked_property_active_pending"
INVARIANT_PENDING_QUEUE_PARKED_PROPERTY = "queue_pending_property_parked"
INVARIANT_PENDING_FALSE_ACTIVE_STATE = "pending_false_active_pending"
INVARIANT_TERMINAL_QUEUE_ACTIVE_PROPERTY = "terminal_queue_property_active_pending"
INVARIANT_DONE_QUEUE_PENDING_TRUE = "done_queue_pending_true_without_outstanding_debt"


def normalize_recalc_state(raw: Any) -> Optional[str]:
    s = str(raw or "").strip().lower()
    if s in (RECALC_STATE_ACTIVE_PENDING, RECALC_STATE_PARKED, RECALC_STATE_CURRENT):
        return s
    return None


def is_recalc_obligation(prop: Optional[Dict[str, Any]]) -> bool:
    return bool((prop or {}).get("compliance_score_pending"))


def is_recalc_parked(prop: Optional[Dict[str, Any]]) -> bool:
    if not is_recalc_obligation(prop):
        return False
    return normalize_recalc_state((prop or {}).get("compliance_score_recalc_state")) == RECALC_STATE_PARKED


def is_recalc_active_pending(prop: Optional[Dict[str, Any]]) -> bool:
    """Executable/active calculating projection, including legacy pending=true with absent state."""
    if not is_recalc_obligation(prop):
        return False
    state = normalize_recalc_state((prop or {}).get("compliance_score_recalc_state"))
    if state == RECALC_STATE_PARKED:
        return False
    if state == RECALC_STATE_CURRENT:
        return False
    return True


def resolve_recalc_projection(prop: Optional[Dict[str, Any]]) -> str:
    if is_recalc_parked(prop):
        return RECALC_STATE_PARKED
    if is_recalc_active_pending(prop):
        return RECALC_STATE_ACTIVE_PENDING
    return RECALC_STATE_CURRENT


def property_recalc_set_fields(state: str) -> Dict[str, Any]:
    """Fields to $set on properties for a projection write."""
    if state == RECALC_STATE_PARKED:
        return {
            "compliance_score_pending": True,
            "compliance_score_recalc_state": RECALC_STATE_PARKED,
        }
    if state == RECALC_STATE_ACTIVE_PENDING:
        return {
            "compliance_score_pending": True,
            "compliance_score_recalc_state": RECALC_STATE_ACTIVE_PENDING,
        }
    return {
        "compliance_score_pending": False,
        "compliance_score_recalc_state": RECALC_STATE_CURRENT,
    }


def classify_projection_invariants(
    *,
    queue_status: Optional[str],
    prop: Optional[Dict[str, Any]],
) -> List[str]:
    """Return invariant codes that currently hold as violations (empty = consistent)."""
    status = str(queue_status or "").strip().upper()
    proj = resolve_recalc_projection(prop)
    pending = is_recalc_obligation(prop)
    violations: List[str] = []
    if status == "PARKED" and proj == RECALC_STATE_ACTIVE_PENDING:
        violations.append(INVARIANT_PARKED_QUEUE_ACTIVE_PROPERTY)
    if status == "PENDING" and proj == RECALC_STATE_PARKED:
        violations.append(INVARIANT_PENDING_QUEUE_PARKED_PROPERTY)
    if (not pending) and normalize_recalc_state((prop or {}).get("compliance_score_recalc_state")) == (
        RECALC_STATE_ACTIVE_PENDING
    ):
        violations.append(INVARIANT_PENDING_FALSE_ACTIVE_STATE)
    if status in ("DEAD",) and proj == RECALC_STATE_ACTIVE_PENDING:
        violations.append(INVARIANT_TERMINAL_QUEUE_ACTIVE_PROPERTY)
    return violations


def classify_done_pending_without_outstanding_debt(
    *,
    queue_statuses: Iterable[str],
    prop: Optional[Dict[str, Any]],
) -> List[str]:
    """Diagnostic only: DONE exists, pending=true, and no PENDING/RUNNING/PARKED/FAILED debt."""
    if not is_recalc_obligation(prop):
        return []
    statuses = {str(s or "").strip().upper() for s in queue_statuses}
    outstanding = statuses & {"PENDING", "RUNNING", "PARKED", "FAILED"}
    if "DONE" in statuses and not outstanding:
        return [INVARIANT_DONE_QUEUE_PENDING_TRUE]
    return []


def invariant_codes_for_pair(queue_row: Optional[Dict[str, Any]], prop: Optional[Dict[str, Any]]) -> Tuple[str, ...]:
    return tuple(classify_projection_invariants(queue_status=(queue_row or {}).get("status"), prop=prop))
