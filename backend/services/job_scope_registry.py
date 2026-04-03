"""
Which background jobs accept client_id / property_id / property_ids when run manually via admin API.

Scheduled runs omit scope; validation applies to POST /api/admin/jobs/run only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class JobRunScope:
    accepts_client_id: bool = False
    accepts_property_id: bool = False
    """Monthly digest: optional filter to specific properties (requires client_id)."""
    accepts_property_ids_filter: bool = False
    """Manual run must include property_id (e.g. enqueue recalc)."""
    manual_requires_property_id: bool = False


# Overrides; all other job ids default to global-only (no scope arguments).
_JOB_SCOPE_OVERRIDES: dict[str, JobRunScope] = {
    "monthly_digest": JobRunScope(
        accepts_client_id=True,
        accepts_property_id=False,
        accepts_property_ids_filter=True,
    ),
    "daily_reminders": JobRunScope(accepts_client_id=True),
    "compliance_check_morning": JobRunScope(accepts_client_id=True),
    "compliance_check_evening": JobRunScope(accepts_client_id=True),
    "compliance_score_snapshots": JobRunScope(accepts_client_id=True),
    "risk_signals_job": JobRunScope(accepts_client_id=True),
    # Manual API must include property_id. Scheduler runs the same job id without scope → batch enqueue.
    "compliance_recalc_enqueue_property": JobRunScope(
        accepts_client_id=False,
        accepts_property_id=True,
        manual_requires_property_id=True,
    ),
}


def get_job_run_scope(job_id: str) -> JobRunScope:
    return _JOB_SCOPE_OVERRIDES.get(job_id, JobRunScope())


def validate_manual_job_scope(
    job_id: str,
    *,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    property_ids: Optional[List[str]] = None,
) -> Optional[str]:
    """
    If the admin supplied scope the job cannot use, return an error message.
    None means valid.
    """
    cid = (client_id or "").strip()
    pid = (property_id or "").strip()
    pids = [str(x).strip() for x in (property_ids or []) if x and str(x).strip()]
    scope = get_job_run_scope(job_id)

    if scope.manual_requires_property_id and not pid:
        return (
            f"Job '{job_id}' requires 'property_id' in the request body. "
            "Provide the target property_id to enqueue a compliance recalculation."
        )

    if cid and not scope.accepts_client_id:
        return (
            f"Job '{job_id}' runs for all clients when scheduled; it does not accept 'client_id'. "
            "Omit client_id or pick a job that supports client scope (e.g. monthly_digest, daily_reminders)."
        )
    if pid and not scope.accepts_property_id:
        return (
            f"Job '{job_id}' does not accept 'property_id'. "
            "Use 'compliance_recalc_enqueue_property' to enqueue a recalc for one property."
        )
    if pids and not scope.accepts_property_ids_filter:
        return (
            f"Job '{job_id}' does not accept 'property_ids'. "
            "Only monthly_digest supports an optional property subset (with client_id)."
        )
    if pids and not cid:
        return "'property_ids' requires 'client_id' (monthly digest subset for one account)."

    return None
