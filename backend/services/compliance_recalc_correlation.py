"""
Correlation and job-context helpers for compliance recalc queue (additive discipline).

Planning / operational visibility only — does not change scoring semantics.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Mapping, Optional


def ensure_correlation_id(
    *,
    trigger_reason: str,
    property_id: str,
    correlation_id: Optional[str],
) -> str:
    """
    Return a non-empty correlation id for enqueue operations.

    Preserves explicit caller-provided ids (trimmed). When missing, generates a
    stable random suffix (uuid) under a trigger/property prefix — same uniqueness
    contract as historical timestamp-based defaults without wall-clock coupling.
    """
    raw = (correlation_id or "").strip()
    if raw:
        return raw
    return f"{trigger_reason}:{property_id}:{uuid.uuid4().hex}"


def normalize_recalc_job_context(job: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Normalize queue row fields for worker / audit consumers (additive shape).

    Never raises; missing keys become None or empty string as appropriate.
    """
    cid = job.get("correlation_id")
    if cid is not None:
        cid = str(cid).strip() or None
    return {
        "property_id": job.get("property_id"),
        "client_id": job.get("client_id"),
        "trigger_reason": job.get("trigger_reason") or "",
        "actor_type": job.get("actor_type") or "",
        "actor_id": job.get("actor_id"),
        "correlation_id": cid,
        "status": job.get("status"),
        "attempts": int(job.get("attempts") or 0),
        "retry_count": int(job.get("retry_count") if job.get("retry_count") is not None else job.get("attempts") or 0),
        "next_run_at": job.get("next_run_at"),
        "last_error": job.get("last_error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "recalc_execution_signals": job.get("recalc_execution_signals"),
    }


def classify_duplicate_suppression_reason(
    *,
    existing_status: Optional[str],
) -> str:
    """
    Map existing queue row status to a deterministic duplicate-suppression label.

    Values align with operational vocabulary (not persisted as enums on insert).
    """
    st = (existing_status or "").strip().upper()
    if st == "RUNNING":
        return "already_running"
    if st == "FAILED":
        return "retry_requeued"
    if st == "PENDING":
        return "duplicate_pending"
    if st == "DONE":
        return "duplicate_pending"
    if st == "DEAD":
        return "duplicate_pending"
    return "duplicate_pending"
