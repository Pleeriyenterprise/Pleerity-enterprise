"""
Admin observability API: job runs, incidents (ack/resolve), score events (ledger proxy).
All routes require admin. Export endpoints should be rate-limited in production.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import io
import csv as csv_module
import logging

from bson import ObjectId

from database import database
from middleware import admin_route_guard
from services.incident_service import list_incidents, get_incident, acknowledge_incident, resolve_incident
from services.operational_alert_presentation import build_operational_presentation_for_incident
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
    lifecycle_state: Optional[str] = Query(None, description="OPEN, DEGRADED, RECOVERED, RESOLVED"),
    deployment_related: Optional[bool] = Query(None),
    flapping: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """List incidents with optional filters. Admin only."""
    await admin_route_guard(request)
    data = await list_incidents(
        status=status,
        severity=severity,
        lifecycle_state=lifecycle_state,
        deployment_related=deployment_related,
        flapping=flapping,
        limit=limit,
        skip=skip,
    )
    for item in data.get("items") or []:
        item["presentation"] = build_operational_presentation_for_incident(item, for_email_links=False)
    return data


@router.get("/incidents/{incident_id}")
async def get_incident_by_id(
    request: Request,
    incident_id: str,
    enrich: bool = Query(True, description="Include recovery_detected and job state (last_success, expected_interval)"),
):
    """Get a single incident. Admin only. With enrich=True adds recovery_detected, recovery_hint, last_success, last_failure, expected_interval where applicable."""
    await admin_route_guard(request)
    incident = await get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if enrich:
        try:
            from services.incident_recovery import compute_recovery_state_for_incident
            state = await compute_recovery_state_for_incident(incident)
            incident["recovery_detected"] = state.get("recovery_detected", False)
            incident["recovery_hint"] = state.get("recovery_hint")
            if state.get("last_success") is not None:
                incident["last_success"] = state["last_success"]
            if state.get("last_failure") is not None:
                incident["last_failure"] = state["last_failure"]
            if state.get("expected_interval") is not None:
                incident["expected_interval"] = state["expected_interval"]
        except Exception:
            incident["recovery_detected"] = False
            incident["recovery_hint"] = None
    incident["presentation"] = build_operational_presentation_for_incident(incident, for_email_links=False)
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


@router.post("/incidents/{incident_id}/run-job")
async def run_job_for_incident(request: Request, incident_id: str):
    """
    Run the related background job for a job_monitor incident (recovery/testing).
    Only for incidents with source=job_monitor and related_job_name in JOB_RUNNERS.
    Routine jobs normally run on schedule; this is for manual recovery or verification.
    """
    user = await admin_route_guard(request)
    incident = await get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.get("source") != "job_monitor":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run job is only available for job-related incidents (source=job_monitor)",
        )
    job_name = (incident.get("related_job_name") or "").strip()
    if not job_name:
        raise HTTPException(status_code=400, detail="Incident has no related_job_name")
    from job_runner import JOB_RUNNERS, run_instrumented
    if job_name not in JOB_RUNNERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_name}' is not runnable. Use one of: {', '.join(sorted(JOB_RUNNERS.keys())[:10])}...",
        )
    try:
        result = await run_instrumented(job_name, "manual", triggered_by=user.get("portal_user_id"))
        message = (result.get("message") if result else None) or f"Job {job_name} completed"
        return {"success": True, "incident_id": incident_id, "job": job_name, "message": message}
    except Exception as e:
        logger.exception("Run job for incident %s failed: %s", incident_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to run job: {job_name}")


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
from services.risk_signal_regen_admin_surface import health_summary_reason_override

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


def _get_scheduler_job_details() -> Dict[str, Dict[str, Any]]:
    """Return scheduler runtime details keyed by job_id."""
    details: Dict[str, Dict[str, Any]] = {}
    try:
        from server import scheduler

        for job in scheduler.get_jobs():
            jid = getattr(job, "id", None)
            if not jid:
                continue
            trigger = getattr(job, "trigger", None)
            next_run = getattr(job, "next_run_time", None)
            details[jid] = {
                "job_id": jid,
                "name": getattr(job, "name", None),
                "trigger_type": trigger.__class__.__name__ if trigger is not None else None,
                "trigger_expression": str(trigger) if trigger is not None else None,
                "next_run_time": next_run.isoformat() if next_run and hasattr(next_run, "isoformat") else (str(next_run) if next_run else None),
            }
    except Exception:
        return {}
    return details


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

    # scheduler_heartbeat: scheduler_heartbeat collection is authoritative; job_runs are idle-skipped.
    if job_id == "scheduler_heartbeat":
        if heartbeat_stale:
            return (JOB_STATE_FAILED, "Scheduler heartbeat is stale; scheduler may be down.")
        return (JOB_STATE_HEALTHY, JOB_STATE_REASONS[JOB_STATE_HEALTHY])

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

    # Success path: check missed (last success/degraded too old).
    # Idle-skip jobs update last_completed via job_poll_heartbeats without refreshing last_success.
    last_ok = last_success or last_degraded
    if detail.get("poll_persist_skipped") and last_completed:
        if last_ok is None or last_completed >= last_ok:
            last_ok = last_completed
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
    zoho_integration_degraded: bool = False,
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
    if any_critical_degraded or delivery_unknown_stale_count > 0 or zoho_integration_degraded:
        return OVERALL_HEALTH_DEGRADED
    return OVERALL_HEALTH_HEALTHY


async def _fetch_jobs_detail_for_health_summary(db, job_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Batch-fetch per-job run summaries (4 aggregations instead of 4×N point queries)."""
    from services.job_run_service import STATUS_SUCCESS, STATUS_FAILED, STATUS_DEGRADED

    empty_detail: Dict[str, Any] = {
        "last_triggered": None,
        "last_completed": None,
        "last_run_status": None,
        "last_success": None,
        "last_failure": None,
        "last_failure_message": None,
        "last_degraded": None,
        "last_outcome_status": None,
        "outcome_metrics": None,
    }
    jobs_detail = {name: dict(empty_detail) for name in job_names}
    if not job_names:
        return jobs_detail

    job_filter = {"job_name": {"$in": list(job_names)}}
    finished_filter = {"finished_at": {"$exists": True, "$ne": None}}

    async def _latest_by_job(extra_match: Dict[str, Any], field_map: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        # $top avoids a collection-wide $sort before $group (memory limit on large job_runs).
        output_doc = {out_key: f"${src_key}" for out_key, src_key in field_map.items()}
        pipeline = [
            {"$match": {**job_filter, **finished_filter, **extra_match}},
            {
                "$group": {
                    "_id": "$job_name",
                    "row": {
                        "$top": {
                            "sortBy": {"finished_at": -1},
                            "output": output_doc,
                        }
                    },
                }
            },
        ]
        rows = await db.job_runs.aggregate(pipeline, allowDiskUse=True).to_list(len(job_names) + 10)
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            jid = row.get("_id")
            if not jid:
                continue
            payload = row.get("row") or {}
            out[str(jid)] = payload
        return out

    last_runs = await _latest_by_job(
        {},
        {
            "last_triggered": "started_at",
            "last_completed": "finished_at",
            "last_run_status": "status",
            "last_outcome_status": "outcome_status",
            "outcome_metrics": "outcome_metrics",
        },
    )
    last_success_rows = await _latest_by_job({"status": STATUS_SUCCESS}, {"last_success": "finished_at"})
    last_failure_rows = await _latest_by_job(
        {"status": STATUS_FAILED},
        {"last_failure": "finished_at", "last_failure_message": "error_message"},
    )
    last_degraded_rows = await _latest_by_job({"status": STATUS_DEGRADED}, {"last_degraded": "finished_at"})

    for name in job_names:
        detail = jobs_detail[name]
        if name in last_runs:
            detail.update({k: last_runs[name].get(k) for k in (
                "last_triggered", "last_completed", "last_run_status", "last_outcome_status", "outcome_metrics"
            )})
        if name in last_success_rows:
            detail["last_success"] = last_success_rows[name].get("last_success")
        if name in last_failure_rows:
            detail["last_failure"] = last_failure_rows[name].get("last_failure")
            detail["last_failure_message"] = last_failure_rows[name].get("last_failure_message")
        if name in last_degraded_rows:
            detail["last_degraded"] = last_degraded_rows[name].get("last_degraded")
    return jobs_detail


async def build_health_summary_payload() -> Dict[str, Any]:
    """
    Core observability payload (no HTTP). Used by GET /health-summary and Control Centre.
    """
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
    jobs_detail = await _fetch_jobs_detail_for_health_summary(db, HEALTH_SUMMARY_JOBS)

    last_success = {j: jobs_detail[j]["last_success"] for j in HEALTH_SUMMARY_JOBS}

    # Scheduler heartbeat (single authority)
    heartbeat_doc = await db.scheduler_heartbeat.find_one(
        {"_id": "default"},
        {"_id": 0, "last_heartbeat_at": 1},
    )
    last_heartbeat_at = heartbeat_doc.get("last_heartbeat_at") if heartbeat_doc else None
    from services.scheduler_health_authority import evaluate_scheduler_heartbeat

    sched_snap = evaluate_scheduler_heartbeat(
        last_heartbeat_at=last_heartbeat_at,
        now=now,
        stale_after_seconds=HEARTBEAT_STALE_SECONDS,
    )
    heartbeat_stale = sched_snap.stale

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

    # Merge high-frequency poll heartbeats before job state computation (idle-skip path).
    try:
        from services.job_run_idle_persist import COLLECTION_POLL_HEARTBEATS

        async for hb in db[COLLECTION_POLL_HEARTBEATS].find({}):
            jn = hb.get("job_name") or str(hb.get("_id") or "")
            if not jn or jn not in jobs_detail:
                continue
            tick = hb.get("last_tick_at")
            if tick and (
                not jobs_detail[jn].get("last_completed")
                or str(tick) > str(jobs_detail[jn].get("last_completed") or "")
            ):
                jobs_detail[jn]["last_completed"] = tick
                jobs_detail[jn]["last_poll_tick_at"] = tick
                jobs_detail[jn]["poll_persist_skipped"] = bool(hb.get("skipped_persist"))
    except Exception:
        pass

    next_runs = _get_scheduler_next_runs()
    scheduler_details = _get_scheduler_job_details()
    scheduler_runtime_available = len(scheduler_details) > 0
    # Per-job state and reason (pass heartbeat_stale and next_run for startup-aware never-ran)
    job_states = {}
    for jid in HEALTH_SUMMARY_JOBS:
        entry = registry.get(jid)
        next_run_iso = next_runs.get(jid)
        scheduler_registered = jid in scheduler_details
        state, reason = _compute_job_state_and_reason(
            jid, jobs_detail[jid], now, entry,
            heartbeat_stale=heartbeat_stale,
            next_run_iso=next_run_iso,
        )
        _regen_ov = health_summary_reason_override(jid, state, jobs_detail[jid])
        if _regen_ov:
            reason = _regen_ov
        last_run_value = jobs_detail[jid].get("last_completed")
        if scheduler_runtime_available and not scheduler_registered:
            next_run_reason = "job_not_registered_in_scheduler_runtime"
        elif not scheduler_runtime_available:
            next_run_reason = "scheduler_runtime_unavailable"
        elif scheduler_registered and not next_run_iso:
            next_run_reason = "next_run_not_exposed_by_scheduler"
        else:
            next_run_reason = "next_run_available"

        if last_run_value:
            last_run_reason = "last_run_available"
        elif state == JOB_STATE_NOT_YET_DUE_SINCE_STARTUP:
            last_run_reason = "no_run_history_not_yet_due"
        elif state in (JOB_STATE_NEVER_RAN, JOB_STATE_NEVER_RAN_AND_OVERDUE):
            last_run_reason = "no_run_history_overdue"
        else:
            last_run_reason = "no_run_history"

        recommended_action = RECOMMENDED_ACTIONS.get(state, "Review state and logs.")
        job_states[jid] = {
            "state": state,
            "reason": reason,
            "recommended_action": recommended_action,
            "last_run": last_run_value,
            "last_run_status": jobs_detail[jid].get("last_run_status"),
            "last_success": jobs_detail[jid].get("last_success"),
            "last_degraded": jobs_detail[jid].get("last_degraded"),
            "last_failure": jobs_detail[jid].get("last_failure"),
            "last_failure_message": jobs_detail[jid].get("last_failure_message"),
            "next_run": next_run_iso,
            "next_run_reason_code": next_run_reason,
            "last_run_reason_code": last_run_reason,
            "scheduler_registered": scheduler_registered,
            "schedule": entry.frequency_label if entry else None,
            "critical": entry.critical if entry else False,
        }

    # Counts for summary cards (24h); never_ran = overdue only (not not_yet_due_since_startup)
    since_24h = now - timedelta(hours=24)
    since_24h_str = since_24h.isoformat()
    failed_24h = await db.job_runs.count_documents({"status": STATUS_FAILED, "finished_at": {"$gte": since_24h_str}})
    degraded_24h = await db.job_runs.count_documents({"status": STATUS_DEGRADED, "finished_at": {"$gte": since_24h_str}})
    failed_runs_24h_by_job = await db.job_runs.aggregate(
        [
            {"$match": {"status": STATUS_FAILED, "finished_at": {"$gte": since_24h_str}, "job_name": {"$exists": True, "$ne": ""}}},
            {"$group": {"_id": "$job_name", "failure_count": {"$sum": 1}}},
            {"$sort": {"failure_count": -1}},
            {"$limit": 300},
        ]
    ).to_list(300)
    degraded_runs_24h_by_job = await db.job_runs.aggregate(
        [
            {"$match": {"status": STATUS_DEGRADED, "finished_at": {"$gte": since_24h_str}, "job_name": {"$exists": True, "$ne": ""}}},
            {"$group": {"_id": "$job_name", "degraded_count": {"$sum": 1}}},
            {"$sort": {"degraded_count": -1}},
            {"$limit": 300},
        ]
    ).to_list(300)
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

    recent_failures = await db.job_runs.find(
        {"status": STATUS_FAILED},
        {"_id": 0, "job_name": 1, "finished_at": 1, "error_message": 1},
    ).sort("finished_at", -1).limit(10).to_list(10)

    alert_emails = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    alerting_configured = bool(alert_emails)

    recalc_queue_health: Dict[str, Any] = {}
    try:
        from services.compliance_recalc_operational_snapshot import (
            build_recalc_queue_health_summary,
            build_recalc_queue_operational_snapshot,
        )

        snap = await build_recalc_queue_operational_snapshot(max_sample=15)
        recalc_queue_health = build_recalc_queue_health_summary(snap)
    except Exception:
        pass

    zoho_integration_health: Dict[str, Any] = {}
    zoho_operational_snapshot: Dict[str, Any] = {}
    try:
        from services.integrations.zoho.operational_health import (
            build_zoho_operational_health_summary,
            build_zoho_operational_snapshot,
        )

        zoho_operational_snapshot = await build_zoho_operational_snapshot()
        zoho_integration_health = build_zoho_operational_health_summary(zoho_operational_snapshot)
    except Exception:
        pass

    zoho_integration_degraded = (
        zoho_integration_health.get("overall_status") == "degraded"
        and bool(zoho_integration_health.get("zoho_integration_enabled"))
    )

    from services.incident_lifecycle_service import is_deployment_suppression_active

    deploy_active, deploy_note = is_deployment_suppression_active(now)

    # Expose DB name so operators can verify scheduler and observability use the same DB (runtime truth gap investigation)
    # PyMongo Database does not support bool(); use "is not None" to avoid NotImplementedError
    observability_db_name = getattr(db, "name", None) if db is not None else None

    overall_health = _compute_overall_health(
        job_states,
        heartbeat_stale,
        open_p0_p1,
        len(delivery_unknown_stale_runs),
        critical_job_ids,
        zoho_integration_degraded=zoho_integration_degraded,
    )
    # Backward compat: status_badge for UI that still expects ok/degraded/incident
    status_badge = "incident" if open_p0_p1 > 0 else ("degraded" if overall_health != OVERALL_HEALTH_HEALTHY else "ok")

    mongo_storage = None
    try:
        from services.mongo_storage_monitor import collect_mongo_storage_snapshot

        mongo_storage = await collect_mongo_storage_snapshot()
    except Exception:
        mongo_storage = {"available": False, "reason": "collection_failed"}

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
        "mongo_storage": mongo_storage,
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
        "failed_runs_24h_by_job": [
            {"job_name": r["_id"], "count": r.get("failure_count", 0)} for r in failed_runs_24h_by_job if r.get("_id")
        ],
        "degraded_runs_24h_by_job": [
            {"job_name": r["_id"], "count": r.get("degraded_count", 0)} for r in degraded_runs_24h_by_job if r.get("_id")
        ],
        "last_heartbeat_at": last_heartbeat_at,
        "heartbeat_stale": heartbeat_stale,
        "scheduler_health": sched_snap.as_dict(),
        "alerting_configured": alerting_configured,
        "delivery_unknown_stale_runs": delivery_unknown_stale_runs,
        "delivery_unknown_stale_hours": DELIVERY_UNKNOWN_STALE_HOURS,
        "job_state_reasons": JOB_STATE_REASONS,
        "recommended_actions": RECOMMENDED_ACTIONS,
        "scheduler_runtime": {
            "available": scheduler_runtime_available,
            "registered_jobs_count": len(scheduler_details),
        },
        "grace_period_explanation": (
            f"{not_yet_due_count} critical job(s) have not had their first scheduled run yet; no incident created (grace period)."
            if not_yet_due_count > 0 else None
        ),
        "recalc_queue_health": recalc_queue_health,
        "zoho_integration_health": zoho_integration_health,
        "integrations": {
            "zoho": zoho_integration_health,
        },
        "deployment_suppression": {
            "active": deploy_active,
            "note": deploy_note,
        },
    }


@router.get("/health-summary")
async def get_health_summary(request: Request):
    """Summary for System Health dashboard: strict overall health, per-job states (never_ran, missed, healthy, etc.), summary counts."""
    await admin_route_guard(request)
    return await build_health_summary_payload()


@router.get("/storage-paths")
async def get_storage_paths_report(request: Request):
    """Effective DATA_DIR / document vault / intake dirs with exists + writable (admin)."""
    await admin_route_guard(request)
    from utils.storage_paths import build_storage_health_report

    return build_storage_health_report()


@router.get("/framework-audit")
async def get_automation_framework_audit(request: Request):
    """
    Read-only framework audit matrix for automation jobs.
    Reconciles registry, scheduler runtime, runner map, run history, and incident state.
    """
    await admin_route_guard(request)
    db = database.get_db()
    now = datetime.now(timezone.utc)

    from job_runner import JOB_RUNNERS
    from services.startup_reconciliation import STARTUP_RECOVERY_JOB_IDS

    registry = get_registry_by_id()
    health_ids = set(HEALTH_SUMMARY_JOBS)
    scheduler_details = _get_scheduler_job_details()
    scheduler_ids = set(scheduler_details.keys())
    runner_ids = set(JOB_RUNNERS.keys())
    startup_recovery_ids = set(STARTUP_RECOVERY_JOB_IDS)

    # Run history (production-safe: avoid global sort+group that can exceed Mongo memory).
    # Use distinct job names + per-job indexed lookups (job_name, created_at desc).
    runs_map: Dict[str, Dict[str, Any]] = {}
    raw_job_names = await db.job_runs.distinct("job_name")
    run_history_ids = {j for j in raw_job_names if isinstance(j, str) and j.strip()}
    for jid in run_history_ids:
        latest = await db.job_runs.find_one(
            {"job_name": jid},
            {"_id": 1, "started_at": 1, "finished_at": 1, "status": 1, "outcome_status": 1, "outcome_metrics": 1},
            sort=[("created_at", -1)],
        )
        total_runs = await db.job_runs.count_documents({"job_name": jid})
        runs_map[jid] = {
            "total_runs": total_runs,
            "last_run_id": str((latest or {}).get("_id")) if (latest or {}).get("_id") is not None else None,
            "last_started_at": (latest or {}).get("started_at"),
            "last_finished_at": (latest or {}).get("finished_at"),
            "last_status": (latest or {}).get("status"),
            "last_outcome_status": (latest or {}).get("outcome_status"),
            "last_outcome_metrics": (latest or {}).get("outcome_metrics") or {},
        }

    # Incident state by related_job_name
    incident_cursor = db.incidents.find(
        {"related_job_name": {"$exists": True, "$ne": None}, "status": {"$in": ["open", "acknowledged"]}},
        {"_id": 0, "incident_id": 1, "related_job_name": 1, "status": 1, "severity": 1, "title": 1, "created_at": 1},
    )
    incident_map: Dict[str, Dict[str, Any]] = {}
    async for inc in incident_cursor:
        jid = inc.get("related_job_name")
        if not jid:
            continue
        prev = incident_map.get(jid)
        # Keep highest severity/open-most signal (simple lexical severity order)
        sev_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        rank = sev_rank.get(inc.get("severity"), 9)
        prev_rank = sev_rank.get((prev or {}).get("severity"), 9)
        if prev is None or rank < prev_rank:
            incident_map[jid] = inc

    all_job_ids = sorted(set().union(registry.keys(), scheduler_ids, runner_ids, run_history_ids, incident_map.keys()))

    def _classify(jid: str, row: Dict[str, Any]) -> str:
        registered = row["registered"]
        total_runs = row["total_runs"] or 0
        next_run = _parse_iso(row.get("next_run_time"))
        last_status = (row.get("last_status") or "").lower()
        last_outcome = (row.get("last_outcome_status") or "").lower()
        attempted = (row.get("last_outcome_metrics") or {}).get("attempted_count")

        if registered and total_runs == 0:
            if next_run and (next_run - now).total_seconds() > NEXT_RUN_FUTURE_TOLERANCE_SEC:
                return "registered_not_yet_due"
            if jid in startup_recovery_ids:
                return "startup_reconciliation_issue"
            return "registered_overdue_never_ran"
        if total_runs > 0 and not registered:
            return "database/environment_mismatch"
        if total_runs > 0 and row["included_in_automation_centre"] is False:
            return "UI_state_bug"
        if total_runs > 0 and last_status == "success" and last_outcome == "conditional_no_output":
            return "conditionally_no_output"
        if total_runs > 0 and last_status == "success" and last_outcome == "success" and (attempted == 0):
            return "conditionally_no_output"
        if registered and total_runs == 0 and row["can_run_manually"]:
            return "triggered_but_uninstrumented"
        return "none"

    inventory: List[Dict[str, Any]] = []
    for jid in all_job_ids:
        sched = scheduler_details.get(jid, {})
        run = runs_map.get(jid, {})
        incident = incident_map.get(jid)
        registered = jid in scheduler_ids
        can_manual = jid in runner_ids
        in_health = jid in health_ids
        # Current Automation Centre behavior is scheduler jobs + run history rows.
        in_automation = registered or (jid in run_history_ids)

        row = {
            "job_name": jid,
            "purpose": sched.get("name") or (f"{registry[jid].frequency_label} automation job" if jid in registry else "No declared purpose in scheduler runtime"),
            "registered": registered,
            "registration_reason": (
                "registered_in_scheduler_runtime"
                if registered
                else ("scheduler_runtime_unavailable" if not scheduler_details else "not_registered_in_scheduler_runtime")
            ),
            "trigger_type": sched.get("trigger_type"),
            "trigger_expression": sched.get("trigger_expression"),
            "next_run_time": sched.get("next_run_time"),
            "next_run_reason": (
                "next_run_available"
                if sched.get("next_run_time")
                else (
                    "scheduler_runtime_unavailable"
                    if not scheduler_details
                    else ("not_registered_in_scheduler_runtime" if not registered else "next_run_not_exposed_by_scheduler")
                )
            ),
            "included_in_health_summary": in_health,
            "included_in_automation_centre": in_automation,
            "can_be_run_manually": can_manual,
            "total_runs": run.get("total_runs", 0),
            "last_run_id": run.get("last_run_id"),
            "last_started_at": run.get("last_started_at"),
            "last_finished_at": run.get("last_finished_at"),
            "last_run_reason": (
                "last_run_available"
                if run.get("last_finished_at")
                else (
                    "no_run_history_not_yet_due"
                    if (registered and _parse_iso(sched.get("next_run_time")) and (_parse_iso(sched.get("next_run_time")) - now).total_seconds() > NEXT_RUN_FUTURE_TOLERANCE_SEC)
                    else "no_run_history"
                )
            ),
            "last_status": run.get("last_status"),
            "last_outcome_status": run.get("last_outcome_status"),
            "last_outcome_metrics": run.get("last_outcome_metrics") or {},
            "current_incident_state": (
                {
                    "status": incident.get("status"),
                    "severity": incident.get("severity"),
                    "incident_id": incident.get("incident_id"),
                    "title": incident.get("title"),
                    "created_at": incident.get("created_at"),
                }
                if incident
                else None
            ),
            "startup_reconciliation_included": jid in startup_recovery_ids,
        }
        row["diagnostic_category"] = _classify(jid, row)
        inventory.append(row)

    registry_only = sorted(list(set(registry.keys()) - scheduler_ids))
    scheduler_only = sorted(list(scheduler_ids - set(registry.keys())))
    runner_only = sorted(list(runner_ids - scheduler_ids))

    return {
        "generated_at": now.isoformat(),
        "inventory": inventory,
        "summary": {
            "total_jobs": len(inventory),
            "registered_count": sum(1 for i in inventory if i["registered"]),
            "manual_runnable_count": sum(1 for i in inventory if i["can_be_run_manually"]),
            "health_summary_count": sum(1 for i in inventory if i["included_in_health_summary"]),
            "automation_centre_count": sum(1 for i in inventory if i["included_in_automation_centre"]),
            "open_or_ack_incident_jobs": sum(1 for i in inventory if i["current_incident_state"] is not None),
        },
        "reconciliation": {
            "registry_only": registry_only,
            "scheduler_only": scheduler_only,
            "runner_only": runner_only,
            "notes": [
                "registry_only jobs are expected in health metadata but not currently registered in the in-process scheduler.",
                "scheduler_only jobs are scheduled but not part of health-summary critical/all list.",
                "runner_only jobs are manually runnable but not currently registered in scheduler runtime.",
            ],
        },
    }
