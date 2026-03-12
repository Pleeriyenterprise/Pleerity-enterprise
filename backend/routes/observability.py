"""
Admin observability API: job runs, incidents (ack/resolve), score events (ledger proxy).
All routes require admin. Export endpoints should be rate-limited in production.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
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


@router.get("/delivery-state-definitions")
async def get_delivery_state_definitions(request: Request):
    """Return human-readable explanations for delivery states used in outcome_metrics. Admin only."""
    await admin_route_guard(request)
    return {"definitions": DELIVERY_STATE_DEFINITIONS}


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


# Critical jobs for system health (expanded so admin sees all important automations)
HEALTH_SUMMARY_JOBS = [
    "daily_reminders",
    "pending_verification_digest",
    "monthly_digest",
    "compliance_check_morning",
    "compliance_check_evening",
    "scheduled_reports",
    "compliance_score_snapshots",
    "expiry_rollover_recalc",
    "compliance_recalc_worker",
    "notification_retry_worker",
    "notification_failure_spike_monitor",
    "sla_watchdog",
    "scheduler_heartbeat",
]


@router.get("/health-summary")
async def get_health_summary(request: Request):
    """Summary for System Health dashboard: status badge, per-job last run/success/failure/degraded, heartbeat, alerting config."""
    await admin_route_guard(request)
    import os
    from datetime import datetime, timezone, timedelta
    from services.job_run_service import STATUS_SUCCESS, STATUS_FAILED, STATUS_DEGRADED

    db = database.get_db()
    from services.incident_service import count_open_by_severity

    open_p0_p1 = await count_open_by_severity(["P0", "P1"])

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
            "last_success": last_success_doc.get("finished_at") if last_success_doc else None,
            "last_failure": last_failure_doc.get("finished_at") if last_failure_doc else None,
            "last_failure_message": last_failure_doc.get("error_message") if last_failure_doc else None,
            "last_degraded": last_degraded_doc.get("finished_at") if last_degraded_doc else None,
            "last_outcome_status": last_run.get("outcome_status") if last_run else None,
            "outcome_metrics": last_run.get("outcome_metrics") if last_run else None,
        }

    # Backward compat: last_success map for keys that UI may still expect
    last_success = {j: jobs_detail[j]["last_success"] for j in HEALTH_SUMMARY_JOBS}

    # Scheduler heartbeat (from dedicated collection, not job_runs)
    heartbeat_doc = await db.scheduler_heartbeat.find_one(
        {"_id": "default"},
        {"_id": 0, "last_heartbeat_at": 1},
    )
    last_heartbeat_at = heartbeat_doc.get("last_heartbeat_at") if heartbeat_doc else None
    heartbeat_stale = False
    if last_heartbeat_at:
        try:
            if isinstance(last_heartbeat_at, str):
                t = datetime.fromisoformat(last_heartbeat_at.replace("Z", "+00:00"))
            else:
                t = last_heartbeat_at
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - t).total_seconds() > 300:  # 5 min
                heartbeat_stale = True
        except Exception:
            heartbeat_stale = True

    no_job_runs_recorded = all(jobs_detail[j]["last_success"] is None for j in HEALTH_SUMMARY_JOBS if j != "scheduler_heartbeat")
    any_degraded = any(jobs_detail[j]["last_outcome_status"] == "degraded" for j in HEALTH_SUMMARY_JOBS if jobs_detail[j].get("last_outcome_status"))

    if open_p0_p1 > 0:
        status_badge = "incident"
    elif no_job_runs_recorded or heartbeat_stale:
        status_badge = "degraded"
    elif any_degraded:
        status_badge = "degraded"
    else:
        status_badge = "ok"

    open_incidents = await db.incidents.count_documents({"status": "open"})
    recent_failures = await db.job_runs.find(
        {"status": STATUS_FAILED},
        {"_id": 0, "job_name": 1, "finished_at": 1, "error_message": 1},
    ).sort("finished_at", -1).limit(10).to_list(10)

    # Alerting config: surface so admin knows if alerts are disabled
    alert_emails = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    alerting_configured = bool(alert_emails)

    return {
        "status": status_badge,
        "open_incidents_count": open_incidents,
        "open_p0_p1_count": open_p0_p1,
        "last_success": last_success,
        "recent_failures": recent_failures,
        "jobs": jobs_detail,
        "last_heartbeat_at": last_heartbeat_at,
        "heartbeat_stale": heartbeat_stale,
        "alerting_configured": alerting_configured,
    }
