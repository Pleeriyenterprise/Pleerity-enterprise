"""
Admin Operational Evidence Platform API.

Presentation-agnostic read model: timeline, execution trees, operational stories.
All routes require admin. Does not duplicate authoritative operational stores.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from database import database
from middleware import admin_route_guard
from services.operational_evidence.constants import COLLECTION_ANNOTATIONS
from services.operational_evidence.query_service import (
    get_event_chain_from_event,
    get_evidence_event,
    get_execution_chain,
    get_intelligence_shortcuts,
    list_evidence_events,
)
from services.operational_evidence.story_service import get_operational_story
from services.operational_evidence.backfill_service import run_operational_evidence_backfill
from services.operational_evidence.portfolio_service import get_portfolio_evidence_view
from services.operational_evidence.retention_service import apply_warm_retention_tier, get_retention_stats

router = APIRouter(
    prefix="/api/admin/observability/evidence",
    tags=["admin-operational-evidence"],
    dependencies=[Depends(admin_route_guard)],
)


class AnnotationCreate(BaseModel):
    event_id: Optional[str] = None
    root_execution_id: Optional[str] = None
    correlation_id: Optional[str] = None
    note: str = Field(..., min_length=1, max_length=4000)


class BackfillRequest(BaseModel):
    days: int = Field(7, ge=1, le=90)
    limit_per_source: int = Field(500, ge=1, le=2000)
    sources: Optional[list[str]] = None


class RetentionApplyRequest(BaseModel):
    warm_after_days: int = Field(90, ge=1, le=365)
    batch_limit: int = Field(2000, ge=1, le=10000)


def _filter_kwargs(**kwargs: Any) -> Dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None and v != ""}


@router.get("/events")
async def list_events(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    cursor_occurred_at: Optional[str] = None,
    cursor_event_id: Optional[str] = None,
    category: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    job_run_id: Optional[str] = None,
    incident_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    root_execution_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    document_id: Optional[str] = None,
    notification_id: Optional[str] = None,
    environment: Optional[str] = None,
    customer_impact_classification: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    search: Optional[str] = None,
    include_archived: bool = False,
):
    await admin_route_guard(request)
    return await list_evidence_events(
        limit=limit,
        cursor_occurred_at=cursor_occurred_at,
        cursor_event_id=cursor_event_id,
        include_archived=include_archived,
        **_filter_kwargs(
            category=category,
            event_type=event_type,
            severity=severity,
            status=status,
            client_id=client_id,
            property_id=property_id,
            requirement_id=requirement_id,
            job_run_id=job_run_id,
            incident_id=incident_id,
            correlation_id=correlation_id,
            root_execution_id=root_execution_id,
            execution_id=execution_id,
            notification_id=notification_id,
            document_id=document_id,
            environment=environment,
            customer_impact_classification=customer_impact_classification,
            since=since,
            until=until,
            search=search,
        ),
    )


@router.get("/events/{event_id}")
async def get_event(request: Request, event_id: str):
    await admin_route_guard(request)
    doc = await get_evidence_event(event_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Evidence event not found")
    return doc


@router.get("/chains")
async def get_chain(
    request: Request,
    root_execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    limit: int = Query(500, ge=1, le=1000),
):
    await admin_route_guard(request)
    if not root_execution_id and not correlation_id:
        raise HTTPException(status_code=400, detail="root_execution_id or correlation_id required")
    return await get_execution_chain(
        root_execution_id=root_execution_id,
        correlation_id=correlation_id,
        limit=limit,
    )


@router.get("/chains/from-event/{event_id}")
async def get_chain_from_event(request: Request, event_id: str):
    await admin_route_guard(request)
    result = await get_event_chain_from_event(event_id)
    if not result.get("event"):
        raise HTTPException(status_code=404, detail="Evidence event not found")
    return result


@router.get("/stories")
async def get_story(
    request: Request,
    root_execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
):
    await admin_route_guard(request)
    if not root_execution_id and not correlation_id:
        raise HTTPException(status_code=400, detail="root_execution_id or correlation_id required")
    return await get_operational_story(
        root_execution_id=root_execution_id,
        correlation_id=correlation_id,
    )


@router.get("/views/global")
async def view_global(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = None,
    severity: Optional[str] = None,
    since: Optional[str] = None,
    search: Optional[str] = None,
):
    await admin_route_guard(request)
    return await list_evidence_events(
        limit=limit,
        **_filter_kwargs(category=category, severity=severity, since=since, search=search),
    )


@router.get("/views/tenant/{client_id}")
async def view_tenant(
    request: Request,
    client_id: str,
    limit: int = Query(50, ge=1, le=200),
    include_archived: bool = False,
):
    await admin_route_guard(request)
    return await list_evidence_events(limit=limit, client_id=client_id, include_archived=include_archived)


@router.get("/views/portfolio/{client_id}")
async def view_portfolio(
    request: Request,
    client_id: str,
    hours: int = Query(168, ge=1, le=720),
    limit: int = Query(50, ge=1, le=200),
    include_archived: bool = False,
):
    await admin_route_guard(request)
    return await get_portfolio_evidence_view(
        client_id,
        hours=hours,
        limit=limit,
        include_archived=include_archived,
    )


@router.get("/views/property/{property_id}")
async def view_property(request: Request, property_id: str, limit: int = Query(50, ge=1, le=200)):
    await admin_route_guard(request)
    return await list_evidence_events(limit=limit, property_id=property_id)


@router.get("/views/requirement/{requirement_id}")
async def view_requirement(request: Request, requirement_id: str, limit: int = Query(50, ge=1, le=200)):
    await admin_route_guard(request)
    return await list_evidence_events(limit=limit, requirement_id=requirement_id)


@router.get("/views/job-run/{job_run_id}")
async def view_job_run(request: Request, job_run_id: str, limit: int = Query(200, ge=1, le=500)):
    await admin_route_guard(request)
    items = await list_evidence_events(limit=limit, job_run_id=job_run_id)
    story = await get_operational_story(correlation_id=None, root_execution_id=None)
    if items.get("items"):
        root = items["items"][0].get("root_execution_id")
        if root:
            story = await get_operational_story(root_execution_id=root)
    return {"timeline": items, "story": story}


@router.get("/views/incident/{incident_id}")
async def view_incident(request: Request, incident_id: str, limit: int = Query(200, ge=1, le=500)):
    await admin_route_guard(request)
    items = await list_evidence_events(limit=limit, incident_id=incident_id)
    story = None
    if items.get("items"):
        root = items["items"][0].get("root_execution_id")
        corr = items["items"][0].get("correlation_id")
        story = await get_operational_story(root_execution_id=root, correlation_id=corr if not root else None)
    return {"timeline": items, "story": story}


@router.get("/views/notification/{notification_id}")
async def view_notification(request: Request, notification_id: str, limit: int = Query(100, ge=1, le=300)):
    await admin_route_guard(request)
    return await list_evidence_events(limit=limit, notification_id=notification_id)


@router.get("/intelligence/shortcuts")
async def intelligence_shortcuts(request: Request, hours: int = Query(24, ge=1, le=168)):
    await admin_route_guard(request)
    return await get_intelligence_shortcuts(hours=hours)


@router.post("/backfill")
async def trigger_backfill(request: Request, body: BackfillRequest):
    """Admin-triggered historical backfill from authoritative sources (bounded, idempotent)."""
    await admin_route_guard(request)
    return await run_operational_evidence_backfill(
        days=body.days,
        limit_per_source=body.limit_per_source,
        sources=body.sources,
    )


@router.get("/retention/stats")
async def retention_stats(request: Request):
    await admin_route_guard(request)
    return await get_retention_stats()


@router.post("/retention/apply")
async def retention_apply(request: Request, body: RetentionApplyRequest):
    """Admin-triggered warm-tier retention pass (bounded batch)."""
    await admin_route_guard(request)
    return await apply_warm_retention_tier(
        warm_after_days=body.warm_after_days,
        batch_limit=body.batch_limit,
    )


@router.post("/annotations")
async def create_annotation(request: Request, body: AnnotationCreate):
    await admin_route_guard(request)
    user = getattr(request.state, "user", None) or {}
    actor_id = user.get("portal_user_id") or user.get("sub") or "admin"
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "annotation_id": f"ann_{now}_{actor_id}"[:80],
        "event_id": body.event_id,
        "root_execution_id": body.root_execution_id,
        "correlation_id": body.correlation_id,
        "note": body.note.strip(),
        "actor_id": actor_id,
        "created_at": now,
        "updated_at": now,
    }
    await db[COLLECTION_ANNOTATIONS].insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/annotations")
async def list_annotations(
    request: Request,
    event_id: Optional[str] = None,
    root_execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    await admin_route_guard(request)
    db = database.get_db()
    q: Dict[str, Any] = {}
    if event_id:
        q["event_id"] = event_id
    if root_execution_id:
        q["root_execution_id"] = root_execution_id
    if correlation_id:
        q["correlation_id"] = correlation_id
    docs = (
        await db[COLLECTION_ANNOTATIONS]
        .find(q)
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
    return {"items": docs, "total": len(docs)}
