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

from database import database
from middleware import admin_route_guard
from services.incident_service import list_incidents, get_incident, acknowledge_incident, resolve_incident
from services.score_ledger_service import list_ledger, list_ledger_export

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


@router.get("/health-summary")
async def get_health_summary(request: Request):
    """Summary for System Health dashboard: status badge, last success for key jobs, open incident count."""
    await admin_route_guard(request)
    db = database.get_db()
    from services.incident_service import count_open_by_severity, STATUS_OPEN

    open_p0_p1 = await count_open_by_severity(["P0", "P1"])
    status_badge = "incident" if open_p0_p1 > 0 else "ok"

    key_jobs = ["daily_reminders", "monthly_digest", "compliance_score_snapshots", "compliance_recalc_worker", "expiry_rollover_recalc"]
    last_success = {}
    for job_name in key_jobs:
        doc = await db.job_runs.find_one(
            {"job_name": job_name, "status": "success"},
            {"_id": 0, "finished_at": 1, "job_name": 1},
            sort=[("finished_at", -1)],
        )
        last_success[job_name] = doc.get("finished_at") if doc else None

    open_incidents = await db.incidents.count_documents({"status": "open"})
    recent_failures = await db.job_runs.find(
        {"status": "failed"},
        {"_id": 0, "job_name": 1, "finished_at": 1, "error_message": 1},
    ).sort("finished_at", -1).limit(10).to_list(10)

    return {
        "status": status_badge,
        "open_incidents_count": open_incidents,
        "open_p0_p1_count": open_p0_p1,
        "last_success": last_success,
        "recent_failures": recent_failures,
    }
