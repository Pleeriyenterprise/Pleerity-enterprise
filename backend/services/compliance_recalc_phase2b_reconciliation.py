"""
Read-only Phase 2B classification of historical compliance recalc rows.

Does not mutate Mongo. Used by tests and optional dry-run diagnostics.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from services.compliance_recalc_sla_eligibility import ComplianceRecalcSlaClass
from services.compliance_recalc_state import (
    classify_projection_invariants,
    is_recalc_active_pending,
    is_recalc_parked,
)

BUCKET_REMAIN_EXECUTABLE_PENDING = "would_remain_executable_pending"
BUCKET_BECOME_PARKED = "would_become_parked"
BUCKET_BECOME_TERMINAL = "would_become_terminal"
BUCKET_NEED_RESTORATION = "would_need_restoration"
BUCKET_INCONSISTENT_PROJECTION = "inconsistent_property_queue_projection"
BUCKET_GENUINE_ACTIVE_FAILURE = "genuine_active_failure"
BUCKET_UNKNOWN_ORPHAN = "unknown_orphan"
BUCKET_SEPARATE_INVESTIGATION = "requires_separate_investigation"
BUCKET_NO_CHANGE = "no_phase2b_change"


def classify_queue_row_under_phase2b(
    *,
    status: Optional[str],
    sla_class: Optional[str],
    last_error: Optional[str] = None,
) -> str:
    st = str(status or "").strip().upper()
    sla = str(sla_class or "").strip().upper()
    err = str(last_error or "")
    date_defect = "date value out of range" in err.lower()
    if sla == ComplianceRecalcSlaClass.ACTIONABLE.value and date_defect:
        return BUCKET_SEPARATE_INVESTIGATION
    if sla == ComplianceRecalcSlaClass.TERMINATED.value:
        if st in ("DEAD", "DONE"):
            return BUCKET_NO_CHANGE
        return BUCKET_BECOME_TERMINAL
    if sla in (
        ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED.value,
        ComplianceRecalcSlaClass.UNKNOWN_SAFE_SKIP.value,
    ):
        if st == "PARKED":
            return BUCKET_NO_CHANGE
        if st in ("PENDING", "FAILED"):
            return BUCKET_BECOME_PARKED
        if st == "RUNNING":
            return BUCKET_NO_CHANGE  # drain in place
        if st == "DEAD":
            return BUCKET_NO_CHANGE
        return BUCKET_UNKNOWN_ORPHAN
    if sla == ComplianceRecalcSlaClass.ACTIONABLE.value:
        if st == "PARKED":
            return BUCKET_NEED_RESTORATION
        if st == "PENDING":
            return BUCKET_REMAIN_EXECUTABLE_PENDING
        if st == "FAILED":
            return BUCKET_GENUINE_ACTIVE_FAILURE
        if st in ("RUNNING", "DONE", "DEAD"):
            return BUCKET_NO_CHANGE
        return BUCKET_UNKNOWN_ORPHAN
    return BUCKET_UNKNOWN_ORPHAN


def classify_property_under_phase2b(
    *,
    prop: Dict[str, Any],
    queue_statuses: Iterable[str],
    sla_class: Optional[str],
) -> List[str]:
    buckets: List[str] = []
    sla = str(sla_class or "").strip().upper()
    statuses = {str(s or "").strip().upper() for s in queue_statuses}
    pending = bool(prop.get("compliance_score_pending"))
    parked_proj = is_recalc_parked(prop)
    active_proj = is_recalc_active_pending(prop)
    if pending and sla in (
        ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED.value,
        ComplianceRecalcSlaClass.UNKNOWN_SAFE_SKIP.value,
    ) and not parked_proj:
        buckets.append(BUCKET_BECOME_PARKED)
    if parked_proj and sla == ComplianceRecalcSlaClass.ACTIONABLE.value and not (
        statuses & {"PENDING", "RUNNING"}
    ):
        buckets.append(BUCKET_NEED_RESTORATION)
    if pending and sla == ComplianceRecalcSlaClass.ACTIONABLE.value and not (
        statuses & {"PENDING", "RUNNING", "PARKED"}
    ):
        buckets.append(BUCKET_NEED_RESTORATION)
    for st in statuses:
        inv = classify_projection_invariants(queue_status=st, prop=prop)
        if inv:
            buckets.append(BUCKET_INCONSISTENT_PROJECTION)
            break
    if not buckets and not pending:
        buckets.append(BUCKET_NO_CHANGE)
    if not buckets:
        buckets.append(BUCKET_NO_CHANGE)
    return buckets


def tally_buckets(labels: Iterable[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for label in labels:
        out[label] = out.get(label, 0) + 1
    return out
