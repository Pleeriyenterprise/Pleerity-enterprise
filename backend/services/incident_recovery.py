"""
Incident auto-recovery: resolve incidents when the underlying condition is cleared.
Conservative: only resolve when the same condition that created the incident is verified cleared.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from database import database

from services.incident_service import (
    SOURCE_JOB_MONITOR,
    SOURCE_HEARTBEAT,
    SOURCE_DELIVERY_UNKNOWN,
    SOURCE_RISK_REGEN_QUEUE,
    STATUS_OPEN,
    STATUS_ACKNOWLEDGED,
)
from services.incident_lifecycle_service import process_incident_recovery_lifecycle
from services.job_run_service import COLLECTION as JOB_RUNS_COLLECTION, STATUS_SUCCESS, STATUS_DEGRADED
from services.job_schedule_registry import HEARTBEAT_STALE_SECONDS, get_job_entry
from services.delivery_reconciliation import RECONCILIATION_JOBS, DELIVERY_UNKNOWN_STALE_HOURS

import logging

logger = logging.getLogger(__name__)


async def _queue_health_snapshot() -> dict:
    try:
        from services.compliance_recalc_operational_snapshot import (
            build_recalc_queue_health_summary,
            build_recalc_queue_operational_snapshot,
        )

        snap = await build_recalc_queue_operational_snapshot(max_sample=10)
        return build_recalc_queue_health_summary(snap)
    except Exception:
        return {}


async def _process_open_incidents_recovery(cursor, note: str) -> int:
    resolved = 0
    qh = await _queue_health_snapshot()
    async for doc in cursor:
        incident_id = str(doc["_id"])
        result = await process_incident_recovery_lifecycle(
            incident_id,
            note,
            queue_health=qh or None,
        )
        if result.get("auto_resolved"):
            resolved += 1
    return resolved


async def compute_recovery_state_for_incident(incident: dict) -> dict:
    """
    For an open/acknowledged incident, compute whether the underlying condition is now cleared.
    Returns { recovery_detected, recovery_hint, last_success, last_failure, expected_interval }.
    """
    db = database.get_db()
    status = incident.get("status")
    if status not in (STATUS_OPEN, STATUS_ACKNOWLEDGED):
        return {"recovery_detected": False, "recovery_hint": None, "last_success": None, "last_failure": None, "expected_interval": None}
    source = incident.get("source")
    meta = incident.get("metadata") or {}
    out = {"recovery_detected": False, "recovery_hint": None, "last_success": None, "last_failure": None, "expected_interval": None}

    if source == SOURCE_HEARTBEAT:
        hb = await db.scheduler_heartbeat.find_one({"_id": "default"}, {"_id": 0, "last_heartbeat_at": 1})
        last_hb = hb.get("last_heartbeat_at") if hb else None
        if last_hb:
            now = datetime.now(timezone.utc)
            try:
                t = datetime.fromisoformat(str(last_hb).replace("Z", "+00:00")) if isinstance(last_hb, str) else last_hb
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                if (now - t).total_seconds() <= HEARTBEAT_STALE_SECONDS:
                    out["recovery_detected"] = True
                    out["recovery_hint"] = "Recovery detected. This incident can be resolved automatically."
            except Exception:
                pass
        return out

    if source == SOURCE_DELIVERY_UNKNOWN:
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(hours=DELIVERY_UNKNOWN_STALE_HOURS)
        stale_cutoff_str = stale_cutoff.isoformat()
        count = await db[JOB_RUNS_COLLECTION].count_documents({
            "job_name": {"$in": list(RECONCILIATION_JOBS.keys())},
            "finished_at": {"$lt": stale_cutoff_str},
            "outcome_metrics.delivery_unknown": {"$gt": 0},
        })
        if count == 0:
            out["recovery_detected"] = True
            out["recovery_hint"] = "Recovery detected. This incident can be resolved automatically."
        return out

    if source == SOURCE_RISK_REGEN_QUEUE:
        try:
            from services.risk_signal_regen_queue import get_regen_queue_summary

            s = await get_regen_queue_summary(5)
            if not s.get("attention_required"):
                out["recovery_detected"] = True
                out["recovery_hint"] = "Risk regen queue health is OK (no DEAD backlog; FAILED count within threshold)."
        except Exception:
            pass
        return out

    if source == SOURCE_JOB_MONITOR:
        job_name = incident.get("related_job_name")
        if not job_name:
            return out
        entry = get_job_entry(job_name)
        if entry:
            out["expected_interval"] = entry.frequency_label
        last_success = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": job_name, "status": STATUS_SUCCESS},
            {"_id": 0, "finished_at": 1},
            sort=[("finished_at", -1)],
        )
        last_failure = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": job_name, "status": "failed"},
            {"_id": 0, "finished_at": 1},
            sort=[("finished_at", -1)],
        )
        last_run = await db[JOB_RUNS_COLLECTION].find_one(
            {"job_name": job_name},
            {"_id": 0, "finished_at": 1, "status": 1},
            sort=[("finished_at", -1)],
        )
        if last_success:
            out["last_success"] = last_success.get("finished_at")
        if last_failure:
            out["last_failure"] = last_failure.get("finished_at")
        reason = meta.get("triggering_reason", "")
        if reason == "degraded_run":
            if last_run and last_run.get("status") == STATUS_SUCCESS:
                out["recovery_detected"] = True
                out["recovery_hint"] = "Recovery detected. This incident can be resolved automatically."
        else:
            if last_run and last_run.get("status") in (STATUS_SUCCESS, STATUS_DEGRADED):
                out["recovery_detected"] = True
                out["recovery_hint"] = "Recovery detected. This incident can be resolved automatically."
        return out

    return out


async def resolve_recovered_incidents_for_job(
    job_name: str,
    latest_run_finished_at: str,
    latest_run_status: str,
    job_run_id: Optional[str] = None,
) -> int:
    """
    Resolve open/acknowledged job_monitor incidents for this job when the condition is cleared.
    - missed_sla / job_never_succeeded: resolve when latest run is success or degraded (job ran).
    - degraded_run: resolve only when latest run is success (not degraded).
    Returns count of incidents resolved.
    """
    db = database.get_db()
    cursor = db.incidents.find(
        {
            "status": {"$in": [STATUS_OPEN, STATUS_ACKNOWLEDGED]},
            "source": SOURCE_JOB_MONITOR,
            "related_job_name": job_name,
        },
        {"_id": 1, "id": 1, "metadata": 1},
    )
    resolved_count = 0
    async for doc in cursor:
        incident_id = str(doc["_id"])
        meta = doc.get("metadata") or {}
        reason = meta.get("triggering_reason", "")
        if reason == "degraded_run":
            if latest_run_status != STATUS_SUCCESS:
                continue
            note = f"Automatically resolved after successful run of job {job_name} at {latest_run_finished_at}."
        else:
            if latest_run_status not in (STATUS_SUCCESS, STATUS_DEGRADED):
                continue
            note = f"Automatically resolved after run of job {job_name} at {latest_run_finished_at} (status={latest_run_status})."
        if job_run_id:
            note += f" Run id: {job_run_id}."
        result = await process_incident_recovery_lifecycle(
            incident_id,
            note,
            queue_health=await _queue_health_snapshot() or None,
        )
        if result.get("auto_resolved"):
            resolved_count += 1
    return resolved_count


async def check_and_resolve_heartbeat_incidents() -> int:
    """
    If scheduler heartbeat is no longer stale, resolve open heartbeat incidents.
    Returns count resolved.
    """
    db = database.get_db()
    hb = await db.scheduler_heartbeat.find_one({"_id": "default"}, {"_id": 0, "last_heartbeat_at": 1})
    last_hb = hb.get("last_heartbeat_at") if hb else None
    if not last_hb:
        return 0
    now = datetime.now(timezone.utc)
    try:
        t = datetime.fromisoformat(str(last_hb).replace("Z", "+00:00")) if isinstance(last_hb, str) else last_hb
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if (now - t).total_seconds() > HEARTBEAT_STALE_SECONDS:
            return 0
    except Exception:
        return 0
    cursor = db.incidents.find(
        {"status": {"$in": [STATUS_OPEN, STATUS_ACKNOWLEDGED]}, "source": SOURCE_HEARTBEAT},
        {"_id": 1},
    )
    note = f"Recovery detected: scheduler heartbeat is fresh (last_heartbeat_at={last_hb})."
    return await _process_open_incidents_recovery(cursor, note)


async def check_and_resolve_risk_regen_queue_incidents() -> int:
    """
    If risk regen queue no longer requires attention, resolve open/ack incidents for SOURCE_RISK_REGEN_QUEUE.
    """
    try:
        from services.risk_signal_regen_queue import get_regen_queue_summary

        summary = await get_regen_queue_summary(5)
        if summary.get("attention_required"):
            return 0
    except Exception:
        return 0

    db = database.get_db()
    cursor = db.incidents.find(
        {"status": {"$in": [STATUS_OPEN, STATUS_ACKNOWLEDGED]}, "source": SOURCE_RISK_REGEN_QUEUE},
        {"_id": 1},
    )
    note = (
        "Recovery detected: risk_signal_regen_queue counts are healthy "
        "(no DEAD jobs; FAILED count at or below threshold)."
    )
    return await _process_open_incidents_recovery(cursor, note)


async def check_and_resolve_delivery_unknown_incidents() -> int:
    """
    If there are no reconciliation runs with delivery_unknown beyond the stale threshold, resolve open delivery_unknown incidents.
    Returns count resolved.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(hours=DELIVERY_UNKNOWN_STALE_HOURS)
    stale_cutoff_str = stale_cutoff.isoformat()
    count = await db[JOB_RUNS_COLLECTION].count_documents({
        "job_name": {"$in": list(RECONCILIATION_JOBS.keys())},
        "finished_at": {"$lt": stale_cutoff_str},
        "outcome_metrics.delivery_unknown": {"$gt": 0},
    })
    if count > 0:
        return 0
    cursor = db.incidents.find(
        {"status": {"$in": [STATUS_OPEN, STATUS_ACKNOWLEDGED]}, "source": SOURCE_DELIVERY_UNKNOWN},
        {"_id": 1},
    )
    note = f"Recovery detected: no runs with delivery_unknown beyond {DELIVERY_UNKNOWN_STALE_HOURS}h threshold."
    return await _process_open_incidents_recovery(cursor, note)
