"""
Job run persistence for enterprise observability.
Every automation execution is recorded (start/finish, status, duration, error).
Used by SLA watchdog and admin System Health / Automation Control Centre.
"""
from database import database
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging
import traceback

logger = logging.getLogger(__name__)

COLLECTION = "job_runs"

STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_DEGRADED = "degraded"
STATUS_TIMEOUT = "timeout"
STATUS_SKIPPED = "skipped"

# Outcome status for business result (success = all intended outputs; degraded = some failed/skipped; failed = could not complete)
OUTCOME_SUCCESS = "success"
OUTCOME_DEGRADED = "degraded"
OUTCOME_FAILED = "failed"

RUN_TYPE_SCHEDULE = "schedule"
RUN_TYPE_MANUAL = "manual"
RUN_TYPE_WEBHOOK = "webhook"


async def start_job_run(
    job_name: str,
    run_type: str,
    *,
    triggered_by: Optional[str] = None,
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Record job start. Returns job_run_id (str) for finish calls.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "job_name": job_name,
        "run_type": run_type,
        "status": STATUS_RUNNING,
        "started_at": now.isoformat(),
        "finished_at": None,
        "duration_ms": None,
        "error_code": None,
        "error_message": None,
        "stack_trace": None,
        "correlation_id": correlation_id,
        "triggered_by": triggered_by,
        "affected_clients_count": None,
        "metadata": metadata or {},
        "created_at": now.isoformat(),
    }
    result = await db[COLLECTION].insert_one(doc)
    job_run_id = str(result.inserted_id)
    logger.debug("job_run started job_name=%s job_run_id=%s", job_name, job_run_id)
    return job_run_id


def _parse_started_at(run: dict, now: datetime) -> datetime:
    started = run.get("started_at")
    if isinstance(started, str):
        try:
            return datetime.fromisoformat(started.replace("Z", "+00:00"))
        except Exception:
            return now
    return started or now


async def finish_job_run_success(
    job_run_id: str,
    *,
    affected_clients_count: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    outcome_status: str = OUTCOME_SUCCESS,
    outcome_metrics: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark job run as success and set duration. Optionally store outcome_status and outcome_metrics."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    from bson import ObjectId
    try:
        oid = ObjectId(job_run_id) if isinstance(job_run_id, str) else job_run_id
    except Exception:
        logger.warning("finish_job_run_success: invalid job_run_id %s", job_run_id)
        return
    run = await db[COLLECTION].find_one({"_id": oid})
    if not run:
        logger.warning("finish_job_run_success: job_run_id not found %s", job_run_id)
        return
    started_dt = _parse_started_at(run, now)
    duration_ms = int((now - started_dt).total_seconds() * 1000)
    update = {
        "status": STATUS_SUCCESS,
        "finished_at": now.isoformat(),
        "duration_ms": duration_ms,
        "error_code": None,
        "error_message": None,
        "stack_trace": None,
        "outcome_status": outcome_status,
        "outcome_metrics": outcome_metrics or {},
    }
    if affected_clients_count is not None:
        update["affected_clients_count"] = affected_clients_count
    if metadata:
        update["metadata"] = {**(run.get("metadata") or {}), **metadata}
    await db[COLLECTION].update_one({"_id": oid}, {"$set": update})
    logger.debug("job_run success job_run_id=%s duration_ms=%s outcome_status=%s", job_run_id, duration_ms, outcome_status)


async def finish_job_run_failure(
    job_run_id: str,
    *,
    error_code: str,
    error_message: str,
    stack_trace: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark job run as failed."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    from bson import ObjectId
    try:
        oid = ObjectId(job_run_id)
    except Exception:
        run = await db[COLLECTION].find_one({"_id": job_run_id})
        oid = run["_id"] if run else None
    if oid is None:
        logger.warning("finish_job_run_failure: job_run_id not found %s", job_run_id)
        return
    run = await db[COLLECTION].find_one({"_id": oid})
    if not run:
        return
    started = run.get("started_at")
    if isinstance(started, str):
        try:
            started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        except Exception:
            started_dt = now
    else:
        started_dt = started or now
    duration_ms = int((now - started_dt).total_seconds() * 1000)
    update = {
        "status": STATUS_FAILED,
        "finished_at": now.isoformat(),
        "duration_ms": duration_ms,
        "error_code": error_code,
        "error_message": error_message,
        "stack_trace": stack_trace,
    }
    if metadata:
        update["metadata"] = {**(run.get("metadata") or {}), **metadata}
    update["outcome_status"] = OUTCOME_FAILED
    update["outcome_metrics"] = {}
    await db[COLLECTION].update_one({"_id": oid}, {"$set": update})
    logger.debug("job_run failure job_run_id=%s error_code=%s", job_run_id, error_code)


async def finish_job_run_degraded(
    job_run_id: str,
    *,
    affected_clients_count: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    outcome_metrics: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> None:
    """Mark job run as degraded (completed but some outputs failed/skipped)."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    from bson import ObjectId
    try:
        oid = ObjectId(job_run_id) if isinstance(job_run_id, str) else job_run_id
    except Exception:
        logger.warning("finish_job_run_degraded: invalid job_run_id %s", job_run_id)
        return
    run = await db[COLLECTION].find_one({"_id": oid})
    if not run:
        logger.warning("finish_job_run_degraded: job_run_id not found %s", job_run_id)
        return
    started_dt = _parse_started_at(run, now)
    duration_ms = int((now - started_dt).total_seconds() * 1000)
    update = {
        "status": STATUS_DEGRADED,
        "finished_at": now.isoformat(),
        "duration_ms": duration_ms,
        "error_code": None,
        "error_message": error_message,
        "stack_trace": None,
        "outcome_status": OUTCOME_DEGRADED,
        "outcome_metrics": outcome_metrics or {},
    }
    if affected_clients_count is not None:
        update["affected_clients_count"] = affected_clients_count
    if metadata:
        update["metadata"] = {**(run.get("metadata") or {}), **metadata}
    await db[COLLECTION].update_one({"_id": oid}, {"$set": update})
    logger.debug("job_run degraded job_run_id=%s duration_ms=%s", job_run_id, duration_ms)
