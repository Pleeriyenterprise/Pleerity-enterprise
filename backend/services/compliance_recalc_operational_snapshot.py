"""
Operational read-models for compliance recalc + regeneration reference paths.

Read-only / non-blocking markers — no enforcement, no client UX.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence

from database import database

from services.compliance_recalc_queue import (
    STATUS_DEAD,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
)
from services.risk_signal_regen_queue import STATUS_PENDING as REGEN_PENDING


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt or not isinstance(dt, str):
        return None
    s = dt.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def build_recalc_queue_health_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Pure summary over ``build_recalc_queue_operational_snapshot`` output.

    Deterministic given an identical snapshot dict (sorted keys / lists where applicable).
    """
    obs = snapshot.get("reconciliation_observability") or {}
    dup = int(snapshot.get("duplicate_suppression_enqueue_total") or 0)
    return {
        "queue_depth_pending": int(snapshot.get("pending_job_count") or 0),
        "active_running": int(snapshot.get("running_job_count") or 0),
        "retrying_failed": int(snapshot.get("failed_retry_job_count") or 0),
        "dead_letter": int(snapshot.get("dead_job_count") or 0),
        "missing_correlation_rows": int(snapshot.get("missing_correlation_job_count") or 0),
        "stale_pending_markers": int(obs.get("stale_pending_recalc_count") or 0),
        "stuck_running_markers": int(obs.get("stuck_running_count") or 0),
        "regeneration_pending_backlog": int(obs.get("regeneration_pending_backlog") or 0),
        "duplicate_suppression_observed_total": dup,
        "health_posture": "NON_BLOCKING_OBSERVABILITY_ONLY",
    }


async def build_recalc_queue_operational_snapshot(
    *,
    generated_at_iso: Optional[str] = None,
    stale_pending_after_seconds: int = 3600,
    stuck_running_after_seconds: int = 1800,
    regeneration_stale_after_seconds: int = 7200,
    max_sample: int = 25,
) -> Dict[str, Any]:
    """
    Aggregate queue / regen visibility for ops and stabilization audits.

    Does not mutate data. Heavy scans are capped by ``max_sample`` for samples only;
    counts use count_documents where feasible.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    if generated_at_iso:
        parsed = _parse_iso(generated_at_iso)
        if parsed:
            now = parsed.astimezone(timezone.utc)
    now_iso = now.isoformat()
    stale_cut = (now - timedelta(seconds=stale_pending_after_seconds)).isoformat()
    stuck_cut = (now - timedelta(seconds=stuck_running_after_seconds)).isoformat()
    regen_cut = (now - timedelta(seconds=regeneration_stale_after_seconds)).isoformat()

    pending_job_count = await db.compliance_recalc_queue.count_documents({"status": STATUS_PENDING})
    running_job_count = await db.compliance_recalc_queue.count_documents({"status": STATUS_RUNNING})
    failed_retry_job_count = await db.compliance_recalc_queue.count_documents({"status": STATUS_FAILED})
    dead_job_count = await db.compliance_recalc_queue.count_documents({"status": STATUS_DEAD})
    missing_correlation_job_count = await db.compliance_recalc_queue.count_documents(
        {
            "$or": [
                {"correlation_id": {"$exists": False}},
                {"correlation_id": None},
                {"correlation_id": ""},
            ]
        }
    )

    stale_pending_recalc_count = await db.compliance_recalc_queue.count_documents(
        {"status": STATUS_PENDING, "created_at": {"$lt": stale_cut}}
    )
    stuck_running_count = await db.compliance_recalc_queue.count_documents(
        {"status": STATUS_RUNNING, "updated_at": {"$lt": stuck_cut}}
    )

    dup_field = "suppressed_duplicate_enqueue_count"
    sum_path = f"${dup_field}"
    dup_cursor = db.compliance_recalc_queue.aggregate(
        [
            {"$match": {dup_field: {"$gt": 0}}},
            {"$group": {"_id": None, "total": {"$sum": sum_path}}},
        ]
    )
    duplicate_suppression_enqueue_total = 0
    async for row in dup_cursor:
        duplicate_suppression_enqueue_total = int(row.get("total") or 0)

    active_jobs: List[Dict[str, Any]] = []
    cursor = (
        db.compliance_recalc_queue.find({"status": STATUS_RUNNING}, {"_id": 1, "property_id": 1, "correlation_id": 1, "updated_at": 1})
        .sort("updated_at", 1)
        .limit(max_sample)
    )
    async for doc in cursor:
        active_jobs.append(
            {
                "queue_id": str(doc.get("_id")),
                "property_id": doc.get("property_id"),
                "correlation_id": doc.get("correlation_id"),
                "updated_at": doc.get("updated_at"),
            }
        )

    longest_running_jobs = list(active_jobs)

    retrying_jobs: List[Dict[str, Any]] = []
    rc = (
        db.compliance_recalc_queue.find(
            {"status": STATUS_FAILED},
            {"_id": 1, "property_id": 1, "correlation_id": 1, "attempts": 1, "retry_count": 1, "next_run_at": 1, "last_retry_at": 1},
        )
        .sort("next_run_at", 1)
        .limit(max_sample)
    )
    async for doc in rc:
        retrying_jobs.append(
            {
                "queue_id": str(doc.get("_id")),
                "property_id": doc.get("property_id"),
                "correlation_id": doc.get("correlation_id"),
                "attempts": doc.get("attempts"),
                "retry_count": doc.get("retry_count"),
                "next_run_at": doc.get("next_run_at"),
                "last_retry_at": doc.get("last_retry_at"),
            }
        )

    dead_jobs: List[Dict[str, Any]] = []
    dc = (
        db.compliance_recalc_queue.find(
            {"status": STATUS_DEAD},
            {"_id": 1, "property_id": 1, "correlation_id": 1, "dead_state_at": 1, "dead_state_reason": 1, "retry_exhausted": 1},
        )
        .sort("dead_state_at", -1)
        .limit(max_sample)
    )
    async for doc in dc:
        dead_jobs.append(
            {
                "queue_id": str(doc.get("_id")),
                "property_id": doc.get("property_id"),
                "correlation_id": doc.get("correlation_id"),
                "dead_state_at": doc.get("dead_state_at"),
                "dead_state_reason": (doc.get("dead_state_reason") or doc.get("last_error") or "")[:500],
                "retry_exhausted": doc.get("retry_exhausted"),
            }
        )

    pending_for_age: List[Dict[str, Any]] = []
    pc = db.compliance_recalc_queue.find({"status": STATUS_PENDING}, {"created_at": 1}).limit(2000)
    async for doc in pc:
        pending_for_age.append(doc)

    ages_sec: List[float] = []
    for doc in pending_for_age:
        cdt = _parse_iso(doc.get("created_at"))
        if cdt:
            ages_sec.append(max(0.0, (now - cdt.astimezone(timezone.utc)).total_seconds()))
    avg_queue_age_seconds = round(statistics.mean(ages_sec), 3) if ages_sec else None

    regeneration_pending_backlog = await db.risk_signal_regen_queue.count_documents({"status": REGEN_PENDING})
    regeneration_stale_pending = await db.risk_signal_regen_queue.count_documents(
        {"status": REGEN_PENDING, "updated_at": {"$lt": regen_cut}}
    )

    missing_correlation_jobs_sample: List[Dict[str, Any]] = []
    mc = (
        db.compliance_recalc_queue.find(
            {
                "$or": [
                    {"correlation_id": {"$exists": False}},
                    {"correlation_id": None},
                    {"correlation_id": ""},
                ]
            },
            {"_id": 1, "property_id": 1, "status": 1},
        )
        .sort("updated_at", -1)
        .limit(max_sample)
    )
    async for doc in mc:
        missing_correlation_jobs_sample.append(
            {"queue_id": str(doc.get("_id")), "property_id": doc.get("property_id"), "status": doc.get("status")}
        )

    inconsistent_notes: List[str] = []
    if missing_correlation_job_count:
        inconsistent_notes.append("QUEUE_ROWS_MISSING_CORRELATION_ID")

    reconciliation_observability = {
        "stale_pending_recalc_count": stale_pending_recalc_count,
        "stuck_running_count": stuck_running_count,
        "orphaned_running_sample": longest_running_jobs[:5],
        "regeneration_pending_backlog": regeneration_pending_backlog,
        "regeneration_stale_pending_estimate": regeneration_stale_pending,
        "inconsistent_state_warnings": inconsistent_notes,
        "queue_age_visibility": {
            "average_pending_age_seconds": avg_queue_age_seconds,
            "pending_rows_sampled_for_age": len(ages_sec),
        },
        "non_blocking": True,
    }

    stale_regeneration_candidates: List[Dict[str, Any]] = []
    if regeneration_stale_pending:
        sc = (
            db.risk_signal_regen_queue.find(
                {"status": REGEN_PENDING, "updated_at": {"$lt": regen_cut}},
                {"_id": 1, "property_id": 1, "client_id": 1, "updated_at": 1, "next_run_at": 1},
            )
            .sort("updated_at", 1)
            .limit(max_sample)
        )
        async for doc in sc:
            stale_regeneration_candidates.append(
                {
                    "regen_queue_id": str(doc.get("_id")),
                    "property_id": doc.get("property_id"),
                    "client_id": doc.get("client_id"),
                    "updated_at": doc.get("updated_at"),
                    "next_run_at": doc.get("next_run_at"),
                }
            )

    return {
        "schema_version": "compliance_recalc_operational_snapshot_v1",
        "generated_at": now_iso,
        "pending_job_count": pending_job_count,
        "running_job_count": running_job_count,
        "failed_retry_job_count": failed_retry_job_count,
        "dead_job_count": dead_job_count,
        "missing_correlation_job_count": missing_correlation_job_count,
        "duplicate_suppression_enqueue_total": duplicate_suppression_enqueue_total,
        "average_queue_age_seconds_pending_sample": avg_queue_age_seconds,
        "active_jobs_sample": sorted(active_jobs, key=lambda x: (x.get("queue_id") or "")),
        "retrying_jobs_sample": sorted(retrying_jobs, key=lambda x: (x.get("queue_id") or "")),
        "dead_jobs_sample": sorted(dead_jobs, key=lambda x: (x.get("queue_id") or "")),
        "longest_running_jobs": longest_running_jobs,
        "missing_correlation_jobs_sample": sorted(
            missing_correlation_jobs_sample, key=lambda x: (str(x.get("queue_id")), str(x.get("property_id")))
        ),
        "stale_regeneration_candidates": stale_regeneration_candidates,
        "reconciliation_observability": reconciliation_observability,
        "audit_only_visibility": True,
    }


def build_recalc_reconciliation_marker_view(queue_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Pure helper: derive non-blocking markers from an in-memory batch (tests / tooling).

    Does not hit the database.
    """
    markers: List[Dict[str, str]] = []
    for row in queue_rows:
        fam = str(row.get("property_id") or "")
        st = str(row.get("status") or "")
        if st == STATUS_PENDING and row.get("created_at"):
            markers.append({"property_id": fam, "code": "PENDING_ROW_PRESENT", "severity": "INFO"})
        if st == STATUS_RUNNING:
            markers.append({"property_id": fam, "code": "RUNNING_ROW_PRESENT", "severity": "INFO"})
        if st == STATUS_DEAD:
            markers.append({"property_id": fam, "code": "DEAD_LETTER_PRESENT", "severity": "WARNING"})
    return {"markers": sorted(markers, key=lambda m: (m["property_id"], m["code"])), "non_blocking": True}
