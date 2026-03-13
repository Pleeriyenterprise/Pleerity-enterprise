"""
Admin observability API: job runs, incidents (ack/resolve), score events (ledger proxy).
All routes require admin. Export endpoints should be rate-limited in production.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import io
import csv as csv_module
import logging

from bson import ObjectId

from database import database
from middleware import admin_route_guard
from services.incident_service import list_incidents, get_incident, acknowledge_incident, resolve_incident
from services.score_ledger_service import list_ledger, list_ledger_export
from services.delivery_reconciliation import get_message_logs_for_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/observability", tags=["admin-observability"], dependencies=[Depends(admin_route_guard)])


@router.get("/job-runs")
async def get_job_runs(
    request: Request,
    job_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """List job runs with optional filters (job_name, status). Admin only."""
    await admin_route_guard(request)
    db = database.get_db()
    query = {}
    if job_name:
        query["job_name"] = job_name
    if status:
        query["status"] = status
    total = await db.job_runs.count_documents(query)
    cursor = db.job_runs.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(limit)
    items = []
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
        items.append(d)
    return {"items": items, "total": total}


# Admin-facing explanations for delivery states (outcome_metrics.delivery_*)
DELIVERY_STATE_DEFINITIONS = {
    "provider_accepted": "Email/SMS was accepted by the provider (e.g. Postmark) for delivery. The message left our system successfully; final delivery or bounce may not yet be confirmed.",
    "delivered": "Provider confirmed delivery (e.g. via webhook). The message reached the recipient's mailbox or device.",
    "bounced": "Provider reported a bounce (invalid address, mailbox full, or similar). The message was not delivered.",
    "unknown": "Accepted by the provider but no delivery or bounce event received yet. Often temporary until webhooks arrive (typically within minutes to hours).",
    "failed": "Send failed before provider acceptance (e.g. validation error, rate limit, or provider API error). No message was handed off.",
}

# Staff guidance for interpreting delivery states (when to act, especially "unknown")
DELIVERY_STATE_GUIDANCE = {
    "summary": "Use outcome_metrics.delivery_* to see how many messages were accepted, delivered, bounced, or still unknown. Failed means the send never reached the provider.",
    "provider_accepted": "Normal. No action unless you need delivery proof; then wait for delivered/bounced or check again after the run.",
    "delivered": "Best outcome. No action needed.",
    "bounced": "Recipient address or mailbox issue. Consider updating or removing the address; no urgent automation fix unless bounces are widespread.",
    "unknown": "Messages were accepted by the provider but we have not yet received a delivery or bounce webhook. This is normal for a short time (minutes to a few hours) after a run. If unknown remains high for more than 6 hours after the run finished, check: (1) provider webhook configuration and delivery, (2) message_logs for those messages. A persistent high unknown count may indicate webhook or provider delays.",
    "failed": "The send failed before the provider accepted it. Check error_message and message_logs; fix configuration, rate limits, or template issues. Repeated failures for the same job need investigation.",
}

@router.get("/delivery-state-definitions")
async def get_delivery_state_definitions(request: Request):
    """Return human-readable definitions and staff guidance for delivery states. Admin only."""
    await admin_route_guard(request)
    from services.delivery_reconciliation import DELIVERY_UNKNOWN_STALE_HOURS as RECONC_HOURS
    return {
        "definitions": DELIVERY_STATE_DEFINITIONS,
        "guidance": DELIVERY_STATE_GUIDANCE,
        "delivery_unknown_stale_hours": RECONC_HOURS,
    }


@router.get("/job-runs/{run_id}/message-logs")
async def get_job_run_message_logs(
    request: Request,
    run_id: str,
    format: str = Query("json", description="Response format: json or csv"),
    limit: int = Query(500, ge=1, le=2000),
):
    """Drill-down: message_logs for a given job run (degraded/failed runs). Time window and template_keys match delivery reconciliation. Admin only."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        oid = ObjectId(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid run_id")
    run = await db.job_runs.find_one({"_id": oid})
    if not run:
        raise HTTPException(status_code=404, detail="Job run not found")
    run["id"] = str(run.get("_id", ""))
    logs = await get_message_logs_for_run(db, run, limit=limit)
    if format == "csv":
        out = io.StringIO()
        w = csv_module.writer(out)
        w.writerow(["message_id", "template_key", "channel", "status", "client_id", "recipient", "error_message", "created_at", "sent_at", "delivered_at", "bounced_at"])
        for r in logs:
            w.writerow([
                r.get("message_id", ""),
                r.get("template_key", ""),
                r.get("channel", ""),
                r.get("status", ""),
                r.get("client_id", ""),
                r.get("recipient", ""),
                r.get("error_message", ""),
                r.get("created_at", ""),
                r.get("sent_at", ""),
                r.get("delivered_at", ""),
                r.get("bounced_at", ""),
            ])
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=message_logs_run_{run_id}.csv"},
        )
    return {"job_run_id": run_id, "job_name": run.get("job_name"), "items": logs, "total": len(logs)}


@router.get("/incidents")
async def get_incidents_list(
    request: Request,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """List incidents with optional filters. Admin only."""
    await admin_route_guard(request)
    data = await list_incidents(status=status, severity=severity, limit=limit, skip=skip)
    return data


@router.get("/incidents/{incident_id}")
async def get_incident_by_id(request: Request, incident_id: str):
    """Get a single incident. Admin only."""
    await admin_route_guard(request)
    incident = await get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


class AckBody(BaseModel):
    note: Optional[str] = None


class ResolveBody(BaseModel):
    note: Optional[str] = None


@router.post("/incidents/{incident_id}/ack")
async def ack_incident(request: Request, incident_id: str, body: AckBody = None):
    """Acknowledge an open incident. Admin only."""
    user = await admin_route_guard(request)
    body = body or AckBody()
    ok = await acknowledge_incident(incident_id, user.get("portal_user_id") or user.get("user_id", ""), note=body.note)
    if not ok:
        raise HTTPException(status_code=404, detail="Incident not found or not open")
    return {"success": True, "incident_id": incident_id}


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident_route(request: Request, incident_id: str, body: ResolveBody = None):
    """Resolve an incident. Admin only."""
    user = await admin_route_guard(request)
    body = body or ResolveBody()
    ok = await resolve_incident(incident_id, user.get("portal_user_id") or user.get("user_id", ""), note=body.note)
    if not ok:
        raise HTTPException(status_code=404, detail="Incident not found or already resolved")
    return {"success": True, "incident_id": incident_id}


@router.get("/score-events")
async def get_score_events(
    request: Request,
    client_id: str = Query(..., description="Client ID (required)"),
    property_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = None,
):
    """List score ledger events for a client (observability alias for ledger). Admin only."""
    await admin_route_guard(request)
    data = await list_ledger(
        client_id=client_id,
        property_id=property_id,
        trigger_type=trigger_type,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        cursor=cursor,
    )
    return data


@router.get("/score-events/export")
async def export_score_events_csv(
    request: Request,
    client_id: str = Query(..., description="Client ID (required)"),
    property_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    """Export score ledger as CSV for a client. Admin only. Prefer rate-limiting in production."""
    await admin_route_guard(request)
    items = await list_ledger_export(
        client_id=client_id,
        property_id=property_id,
        trigger_type=trigger_type,
        from_date=from_date,
        to_date=to_date,
        limit=5000,
    )
    out = io.StringIO()
    w = csv_module.writer(out)
    w.writerow([
        "created_at", "property_id", "trigger_type", "trigger_label", "actor_type",
        "before_score", "after_score", "delta", "before_grade", "after_grade",
        "drivers_before_status", "drivers_before_timeline", "drivers_before_documents", "drivers_before_overdue_penalty",
        "drivers_after_status", "drivers_after_timeline", "drivers_after_documents", "drivers_after_overdue_penalty",
        "rule_version",
    ])
    for r in items:
        db_obj = r.get("drivers_before") or {}
        da = r.get("drivers_after") or {}
        w.writerow([
            r.get("created_at", ""),
            r.get("property_id", ""),
            r.get("trigger_type", ""),
            r.get("trigger_label", ""),
            r.get("actor_type", ""),
            r.get("before_score", ""),
            r.get("after_score", ""),
            r.get("delta", ""),
            r.get("before_grade", ""),
            r.get("after_grade", ""),
            db_obj.get("status"), db_obj.get("timeline"), db_obj.get("documents"), db_obj.get("overdue_penalty"),
            da.get("status"), da.get("timeline"), da.get("documents"), da.get("overdue_penalty"),
            r.get("rule_version", ""),
        ])
    out.seek(0)
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=score_events_export.csv"},
    )


# Critical jobs for system health (must match job_schedule_registry.ALL_JOB_IDS_FOR_HEALTH)
from services.job_schedule_registry import (
    ALL_JOB_IDS_FOR_HEALTH,
    get_registry_by_id,
    get_critical_job_ids,
    OVERALL_HEALTH_HEALTHY,
    OVERALL_HEALTH_DEGRADED,
    OVERALL_HEALTH_FAILED,
    OVERALL_HEALTH_ATTENTION_REQUIRED,
    JOB_STATE_HEALTHY,
    JOB_STATE_DEGRADED,
    JOB_STATE_FAILED,
    JOB_STATE_MISSED,
    JOB_STATE_NEVER_RAN,
    JOB_STATE_NOT_YET_DUE_SINCE_STARTUP,
    JOB_STATE_NEVER_RAN_AND_OVERDUE,
    JOB_STATE_NOT_DUE,
    JOB_STATE_CONDITIONAL_NO_OUTPUT,
    HEARTBEAT_STALE_SECONDS,
)

HEALTH_SUMMARY_JOBS = ALL_JOB_IDS_FOR_HEALTH

# Human-readable reason for each job state (for UI)
JOB_STATE_REASONS = {
    JOB_STATE_HEALTHY: "Ran within SLA with acceptable outcome.",
    JOB_STATE_DEGRADED: "Job ran but some outputs failed or were skipped; review outcome_metrics.",
    JOB_STATE_FAILED: "Job raised or completed unsuccessfully.",
    JOB_STATE_MISSED: "Expected run window exceeded; job did not run in time.",
    JOB_STATE_NEVER_RAN: "Registered job has no run history.",
    JOB_STATE_NOT_YET_DUE_SINCE_STARTUP: "No run yet; next scheduled run has not passed. Wait for next run.",
    JOB_STATE_NEVER_RAN_AND_OVERDUE: "Critical job has never run and its first due time has passed; may need manual recovery.",
    JOB_STATE_NOT_DUE: "Job not yet due based on schedule.",
    JOB_STATE_CONDITIONAL_NO_OUTPUT: "Ran successfully; no qualifying records (e.g. no reminders due).",
}

# Recommended next action per state (for UI)
RECOMMENDED_ACTIONS = {
    JOB_STATE_HEALTHY: "None.",
    JOB_STATE_DEGRADED: "Review message logs and outcome_metrics; act if failures repeat.",
    JOB_STATE_FAILED: "Check error_message and logs; manual recovery only if needed.",
    JOB_STATE_MISSED: "Manual recovery only if overdue; otherwise wait for next run.",
    JOB_STATE_NEVER_RAN: "Wait until next scheduled run or manual recovery if overdue.",
    JOB_STATE_NOT_YET_DUE_SINCE_STARTUP: "Wait until next scheduled run.",
    JOB_STATE_NEVER_RAN_AND_OVERDUE: "Manual recovery recommended; check scheduler and qualifying data.",
    JOB_STATE_NOT_DUE: "Wait until next scheduled run.",
    JOB_STATE_CONDITIONAL_NO_OUTPUT: "None; check qualifying data if output was expected.",
}


def _get_scheduler_next_runs() -> dict:
    """Return dict job_id -> next_run_iso from in-process scheduler, or {} if unavailable."""
    try:
        from server import scheduler
        jobs = scheduler.get_jobs()
        out = {}
        for j in jobs:
            jid = getattr(j, "id", None)
            next_run = getattr(j, "next_run_time", None)
            if jid and next_run:
                out[jid] = next_run.isoformat() if hasattr(next_run, "isoformat") else str(next_run)
        return out
    except Exception:
        return {}


def _parse_iso(ts) -> Optional[datetime]:
    """Parse ISO timestamp to datetime (timezone-aware)."""
    if ts is None:
        return None
    try:
        if isinstance(ts, datetime):
            t = ts
        else:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t
    except Exception:
        return None


# Tolerance: if next_run is within this many seconds of now, treat as "not yet due" (scheduler about to run)
NEXT_RUN_FUTURE_TOLERANCE_SEC = 60


def _compute_job_state_and_reason(
    job_id: str,
    detail: dict,
    now: datetime,
    registry_entry: Optional[object],
    heartbeat_stale: bool = False,
    next_run_iso: Optional[str] = None,
) -> tuple:
    """Returns (state, reason). Uses job_schedule_registry and optional next_run for startup-aware never-ran."""
    last_completed = _parse_iso(detail.get("last_completed"))
    last_success = _parse_iso(detail.get("last_success"))
    last_failure = _parse_iso(detail.get("last_failure"))
    last_degraded = _parse_iso(detail.get("last_degraded"))
    last_status = (detail.get("last_outcome_status") or "").strip().lower()
    outcome_metrics = detail.get("outcome_metrics") or {}

    # scheduler_heartbeat: state must reflect heartbeat collection staleness, not just last job run
    if job_id == "scheduler_heartbeat":
        if heartbeat_stale:
            return (JOB_STATE_FAILED, "Scheduler heartbeat is stale; scheduler may be down.")
        if last_success:
            return (JOB_STATE_HEALTHY, JOB_STATE_REASONS[JOB_STATE_HEALTHY])
        return (JOB_STATE_NEVER_RAN, JOB_STATE_REASONS[JOB_STATE_NEVER_RAN])

    if not last_completed:
        # Startup-aware: if next scheduled run is still in the future, not yet due; else overdue
        next_run_dt = _parse_iso(next_run_iso) if next_run_iso else None
        if next_run_dt and (next_run_dt - now).total_seconds() > NEXT_RUN_FUTURE_TOLERANCE_SEC:
            return (JOB_STATE_NOT_YET_DUE_SINCE_STARTUP, JOB_STATE_REASONS[JOB_STATE_NOT_YET_DUE_SINCE_STARTUP])
        return (JOB_STATE_NEVER_RAN_AND_OVERDUE, JOB_STATE_REASONS[JOB_STATE_NEVER_RAN_AND_OVERDUE])

    last_run_status = (detail.get("last_run_status") or "").strip().lower()
    if last_run_status == "failed":
        return (JOB_STATE_FAILED, JOB_STATE_REASONS[JOB_STATE_FAILED])
    if last_run_status == "degraded":
        return (JOB_STATE_DEGRADED, JOB_STATE_REASONS[JOB_STATE_DEGRADED])

    # Success path: check missed (last success/degraded too old)
    last_ok = last_success or last_degraded
    if registry_entry and last_ok:
        delay_minutes = (now - last_ok).total_seconds() / 60
        if delay_minutes > registry_entry.max_delay_minutes:
            return (JOB_STATE_MISSED, JOB_STATE_REASONS[JOB_STATE_MISSED])

    # Zero output: conditional_no_output if registry says zero_output_ok and attempted/expected are 0
    if registry_entry and registry_entry.zero_output_ok:
        attempted = outcome_metrics.get("attempted_count") or outcome_metrics.get("expected_count") or 0
        if last_success and attempted == 0:
            return (JOB_STATE_CONDITIONAL_NO_OUTPUT, JOB_STATE_REASONS[JOB_STATE_CONDITIONAL_NO_OUTPUT])

    return (JOB_STATE_HEALTHY, JOB_STATE_REASONS[JOB_STATE_HEALTHY])


def _compute_overall_health(
    job_states: dict,
    heartbeat_stale: bool,
    open_p0_p1: int,
    delivery_unknown_stale_count: int,
    critical_job_ids: list,
) -> str:
    """Strict overall health: never show healthy when critical jobs are never_ran, missed, or failed."""
    if open_p0_p1 > 0:
        return OVERALL_HEALTH_ATTENTION_REQUIRED  # or "failed" for P0; keep attention_required for P1
    if heartbeat_stale:
        return OVERALL_HEALTH_FAILED
    any_critical_missed = any(
        job_states.get(jid, {}).get("state") == JOB_STATE_MISSED for jid in critical_job_ids
    )
    any_critical_never_ran = any(
        job_states.get(jid, {}).get("state") in (JOB_STATE_NEVER_RAN, JOB_STATE_NEVER_RAN_AND_OVERDUE)
        for jid in critical_job_ids
    )
    any_critical_failed = any(
        job_states.get(jid, {}).get("state") == JOB_STATE_FAILED for jid in critical_job_ids
    )
    any_critical_degraded = any(
        job_states.get(jid, {}).get("state") == JOB_STATE_DEGRADED for jid in critical_job_ids
    )
    if any_critical_failed or any_critical_missed or any_critical_never_ran:
        return OVERALL_HEALTH_DEGRADED if not any_critical_failed else OVERALL_HEALTH_ATTENTION_REQUIRED
    if any_critical_degraded or delivery_unknown_stale_count > 0:
        return OVERALL_HEALTH_DEGRADED
    return OVERALL_HEALTH_HEALTHY


@router.get("/health-summary")
async def get_health_summary(request: Request):
    """Summary for System Health dashboard: strict overall health, per-job states (never_ran, missed, healthy, etc.), summary counts."""
    await admin_route_guard(request)
    import os
    from datetime import datetime, timezone, timedelta
    from services.job_run_service import STATUS_SUCCESS, STATUS_FAILED, STATUS_DEGRADED

    db = database.get_db()
    from services.incident_service import count_open_by_severity

    open_p0_p1 = await count_open_by_severity(["P0", "P1"])
    now = datetime.now(timezone.utc)
    registry = get_registry_by_id()
    critical_job_ids = get_critical_job_ids()

    # Per-job: last_run (any), last_success, last_failure, last_degraded, last_outcome_status, outcome_metrics
    jobs_detail = {}
    for job_name in HEALTH_SUMMARY_JOBS:
        last_run = await db.job_runs.find_one(
            {"job_name": job_name},
            {"_id": 0, "finished_at": 1, "status": 1, "outcome_status": 1, "outcome_metrics": 1, "started_at": 1},
            sort=[("finished_at", -1)],
        )
        last_success_doc = await db.job_runs.find_one(
            {"job_name": job_name, "status": STATUS_SUCCESS},
            {"_id": 0, "finished_at": 1},
            sort=[("finished_at", -1)],
        )
        last_failure_doc = await db.job_runs.find_one(
            {"job_name": job_name, "status": STATUS_FAILED},
            {"_id": 0, "finished_at": 1, "error_message": 1},
            sort=[("finished_at", -1)],
        )
        last_degraded_doc = await db.job_runs.find_one(
            {"job_name": job_name, "status": STATUS_DEGRADED},
            {"_id": 0, "finished_at": 1, "outcome_metrics": 1},
            sort=[("finished_at", -1)],
        )
        jobs_detail[job_name] = {
            "last_triggered": last_run.get("started_at") if last_run else None,
            "last_completed": last_run.get("finished_at") if last_run else None,
            "last_run_status": last_run.get("status") if last_run else None,
            "last_success": last_success_doc.get("finished_at") if last_success_doc else None,
            "last_failure": last_failure_doc.get("finished_at") if last_failure_doc else None,
            "last_failure_message": last_failure_doc.get("error_message") if last_failure_doc else None,
            "last_degraded": last_degraded_doc.get("finished_at") if last_degraded_doc else None,
            "last_outcome_status": last_run.get("outcome_status") if last_run else None,
            "outcome_metrics": last_run.get("outcome_metrics") if last_run else None,
        }

    last_success = {j: jobs_detail[j]["last_success"] for j in HEALTH_SUMMARY_JOBS}

    # Scheduler heartbeat
    heartbeat_doc = await db.scheduler_heartbeat.find_one(
        {"_id": "default"},
        {"_id": 0, "last_heartbeat_at": 1},
    )
    last_heartbeat_at = heartbeat_doc.get("last_heartbeat_at") if heartbeat_doc else None
    heartbeat_stale = False
    if last_heartbeat_at:
        try:
            t = _parse_iso(last_heartbeat_at)
            if t and (now - t).total_seconds() > HEARTBEAT_STALE_SECONDS:
                heartbeat_stale = True
        except Exception:
            heartbeat_stale = True

    # Delivery unknown stale
    from services.delivery_reconciliation import RECONCILIATION_JOBS, DELIVERY_UNKNOWN_STALE_HOURS
    stale_cutoff = now - timedelta(hours=DELIVERY_UNKNOWN_STALE_HOURS)
    stale_cutoff_str = stale_cutoff.isoformat()
    delivery_unknown_stale_runs = []
    try:
        cursor = db.job_runs.find(
            {
                "job_name": {"$in": list(RECONCILIATION_JOBS.keys())},
                "finished_at": {"$lt": stale_cutoff_str},
                "outcome_metrics.delivery_unknown": {"$gt": 0},
            },
            {"_id": 1, "job_name": 1, "finished_at": 1, "outcome_metrics.delivery_unknown": 1},
        ).sort("finished_at", -1).limit(20)
        async for doc in cursor:
            om = doc.get("outcome_metrics") or {}
            delivery_unknown_stale_runs.append({
                "job_name": doc.get("job_name"),
                "run_id": str(doc.get("_id", "")),
                "finished_at": doc.get("finished_at"),
                "delivery_unknown": om.get("delivery_unknown", 0),
            })
    except Exception:
        pass

    next_runs = _get_scheduler_next_runs()
    # Per-job state and reason (pass heartbeat_stale and next_run for startup-aware never-ran)
    job_states = {}
    for jid in HEALTH_SUMMARY_JOBS:
        entry = registry.get(jid)
        next_run_iso = next_runs.get(jid)
        state, reason = _compute_job_state_and_reason(
            jid, jobs_detail[jid], now, entry,
            heartbeat_stale=heartbeat_stale,
            next_run_iso=next_run_iso,
        )
        recommended_action = RECOMMENDED_ACTIONS.get(state, "Review state and logs.")
        job_states[jid] = {
            "state": state,
            "reason": reason,
            "recommended_action": recommended_action,
            "last_run": jobs_detail[jid].get("last_completed"),
            "last_success": jobs_detail[jid].get("last_success"),
            "last_degraded": jobs_detail[jid].get("last_degraded"),
            "last_failure": jobs_detail[jid].get("last_failure"),
            "schedule": entry.frequency_label if entry else None,
            "critical": entry.critical if entry else False,
        }

    # Counts for summary cards (24h); never_ran = overdue only (not not_yet_due_since_startup)
    since_24h = now - timedelta(hours=24)
    since_24h_str = since_24h.isoformat()
    failed_24h = await db.job_runs.count_documents({"status": STATUS_FAILED, "finished_at": {"$gte": since_24h_str}})
    degraded_24h = await db.job_runs.count_documents({"status": STATUS_DEGRADED, "finished_at": {"$gte": since_24h_str}})
    critical_missed_count = sum(1 for jid in critical_job_ids if job_states.get(jid, {}).get("state") == JOB_STATE_MISSED)
    never_ran_overdue_count = sum(
        1 for jid in critical_job_ids
        if job_states.get(jid, {}).get("state") in (JOB_STATE_NEVER_RAN_AND_OVERDUE, JOB_STATE_NEVER_RAN)
    )
    not_yet_due_count = sum(
        1 for jid in critical_job_ids
        if job_states.get(jid, {}).get("state") == JOB_STATE_NOT_YET_DUE_SINCE_STARTUP
    )
    open_incidents = await db.incidents.count_documents({"status": "open"})

    overall_health = _compute_overall_health(
        job_states, heartbeat_stale, open_p0_p1, len(delivery_unknown_stale_runs), critical_job_ids
    )
    # Backward compat: status_badge for UI that still expects ok/degraded/incident
    status_badge = "incident" if open_p0_p1 > 0 else ("degraded" if overall_health != OVERALL_HEALTH_HEALTHY else "ok")

    recent_failures = await db.job_runs.find(
        {"status": STATUS_FAILED},
        {"_id": 0, "job_name": 1, "finished_at": 1, "error_message": 1},
    ).sort("finished_at", -1).limit(10).to_list(10)

    alert_emails = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    alerting_configured = bool(alert_emails)

    # Expose DB name so operators can verify scheduler and observability use the same DB (runtime truth gap investigation)
    observability_db_name = getattr(db, "name", None) if db else None

    return {
        "observability_db_name": observability_db_name,
        "status": status_badge,
        "overall_health": overall_health,
        "open_incidents_count": open_incidents,
        "open_p0_p1_count": open_p0_p1,
        "last_success": last_success,
        "recent_failures": recent_failures,
        "jobs": jobs_detail,
        "job_states": job_states,
        "summary_counts": {
            "critical_missed": critical_missed_count,
            "never_ran": never_ran_overdue_count,
            "never_ran_overdue": never_ran_overdue_count,
            "not_yet_due_since_startup": not_yet_due_count,
            "degraded_24h": degraded_24h,
            "failed_24h": failed_24h,
            "open_incidents": open_incidents,
            "heartbeat_stale": 1 if heartbeat_stale else 0,
            "delivery_unknown_stale": len(delivery_unknown_stale_runs),
        },
        "last_heartbeat_at": last_heartbeat_at,
        "heartbeat_stale": heartbeat_stale,
        "alerting_configured": alerting_configured,
        "delivery_unknown_stale_runs": delivery_unknown_stale_runs,
        "delivery_unknown_stale_hours": DELIVERY_UNKNOWN_STALE_HOURS,
        "job_state_reasons": JOB_STATE_REASONS,
        "recommended_actions": RECOMMENDED_ACTIONS,
        "grace_period_explanation": (
            f"{not_yet_due_count} critical job(s) have not had their first scheduled run yet; no incident created (grace period)."
            if not_yet_due_count > 0 else None
        ),
    }
