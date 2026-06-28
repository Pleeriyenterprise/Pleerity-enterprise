"""
Compliance Graph Health — admin-only HTTP routes.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

from middleware import admin_route_guard
from services.compliance_evidence_graph.producers.registry import list_producer_registry
from services.compliance_graph_health.service import (
    generate_health_report,
    generate_health_summary,
    run_validation_on_demand,
)

router = APIRouter(tags=["compliance-graph-health"])


@router.get("/api/admin/compliance/graph/health")
async def admin_graph_health(
    request: Request,
    client_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    await admin_route_guard(request)
    return await generate_health_report(client_id=client_id, since=since, until=until)


@router.get("/api/admin/compliance/graph/health/summary")
async def admin_graph_health_summary(
    request: Request,
    client_id: Optional[str] = None,
    since: Optional[str] = None,
):
    await admin_route_guard(request)
    return await generate_health_summary(client_id=client_id, since=since)


@router.post("/api/admin/compliance/graph/health/validate")
async def admin_graph_validate(
    request: Request,
    client_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    await admin_route_guard(request)
    return await run_validation_on_demand(client_id=client_id, since=since, until=until)


@router.get("/api/admin/compliance/graph/producers/registry")
async def admin_producer_registry(request: Request):
    """Phase 2A — producer metadata catalogue (no live emit)."""
    await admin_route_guard(request)
    return {
        "service": "compliance_evidence_graph.producers",
        "entries": list_producer_registry(),
        "live_emit_active": False,
    }
