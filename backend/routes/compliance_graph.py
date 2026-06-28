"""
Compliance Evidence Graph — Graph Service HTTP routes.

Graph storage is internal only. All access via compliance_graph_service.
Phase 1: admin routes + tenant-scoped compliance routes. No raw storage API.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from middleware import admin_route_guard, require_auth
from services.compliance_graph_service.access import ActorContext, actor_from_request_user
from services.compliance_graph_service import service as graph_service
from services.compliance_graph_service.fixtures import seed_fixture_decision
from services.compliance_evidence_graph.config import graph_debug_storage_api

router = APIRouter(tags=["compliance-evidence-graph"])


async def _admin_actor(request: Request) -> ActorContext:
    await admin_route_guard(request)
    user = getattr(request.state, "user", None) or {}
    return actor_from_request_user(user, is_admin=True)


async def _auth_actor(request: Request) -> ActorContext:
    user = await require_auth(request)
    request.state.user = user
    is_admin = (user.get("role") or "").upper() in ("ADMIN", "SUPER_ADMIN", "STAFF")
    return actor_from_request_user(user, is_admin=is_admin)


@router.get("/api/admin/compliance/graph/decisions/{decision_id}/explain")
async def admin_explain_decision(request: Request, decision_id: str):
    actor = await _admin_actor(request)
    return await graph_service.explain_decision(decision_id, actor=actor)


@router.get("/api/admin/compliance/graph/decisions/{decision_id}/replay")
async def admin_replay_decision(request: Request, decision_id: str):
    actor = await _admin_actor(request)
    return await graph_service.replay_decision(decision_id, actor=actor)


@router.get("/api/admin/compliance/graph/decisions/compare")
async def admin_compare_decision(
    request: Request,
    left: str = Query(..., alias="left"),
    right: str = Query(..., alias="right"),
):
    actor = await _admin_actor(request)
    return await graph_service.compare_decision(left, right, actor=actor)


@router.get("/api/admin/compliance/graph/snapshots/compare")
async def admin_compare_snapshots(
    request: Request,
    left: str = Query(..., alias="left"),
    right: str = Query(..., alias="right"),
):
    actor = await _admin_actor(request)
    return await graph_service.compare_decision_snapshots(left, right, actor=actor)


@router.get("/api/admin/compliance/graph/historical")
async def admin_find_historical(
    request: Request,
    client_id: str = Query(...),
    as_of: str = Query(...),
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    decision_type: Optional[str] = None,
):
    actor = await _admin_actor(request)
    return await graph_service.find_historical_decision(
        client_id=client_id,
        as_of=as_of,
        actor=actor,
        property_id=property_id,
        requirement_id=requirement_id,
        decision_type=decision_type,
    )


@router.get("/api/admin/compliance/graph/decisions/{decision_id}/dependencies")
async def admin_decision_dependencies(request: Request, decision_id: str):
    actor = await _admin_actor(request)
    return await graph_service.find_decision_dependencies(decision_id, actor=actor)


@router.get("/api/admin/compliance/graph/decisions/{decision_id}/operational-impact")
async def admin_operational_impact(request: Request, decision_id: str):
    actor = await _admin_actor(request)
    return await graph_service.trace_operational_impact(decision_id, actor=actor)


@router.post("/api/admin/compliance/graph/fixtures/seed")
async def admin_seed_fixture(request: Request, dedupe_suffix: str = Query("v1")):
    """Phase 1 controlled fixture — admin only, not a live producer."""
    actor = await _admin_actor(request)
    decision_id = await seed_fixture_decision(dedupe_suffix=dedupe_suffix)
    if not decision_id:
        raise HTTPException(status_code=500, detail="Fixture emit failed or disallowed")
    return {"decision_id": decision_id, "actor_admin": actor.is_admin}


# Tenant-scoped compliance graph routes (admin or owning client)
@router.get("/api/compliance/graph/decisions/{decision_id}/explain")
async def explain_decision(request: Request, decision_id: str):
    actor = await _auth_actor(request)
    return await graph_service.explain_decision(decision_id, actor=actor)


@router.get("/api/compliance/graph/decisions/{decision_id}/replay")
async def replay_decision(request: Request, decision_id: str):
    actor = await _auth_actor(request)
    return await graph_service.replay_decision(decision_id, actor=actor)


@router.get("/api/compliance/graph/decisions/compare")
async def compare_decision(
    request: Request,
    left: str = Query(..., alias="left"),
    right: str = Query(..., alias="right"),
):
    actor = await _auth_actor(request)
    return await graph_service.compare_decision(left, right, actor=actor)


@router.get("/api/compliance/graph/historical")
async def find_historical(
    request: Request,
    client_id: str = Query(...),
    as_of: str = Query(...),
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    decision_type: Optional[str] = None,
):
    actor = await _auth_actor(request)
    return await graph_service.find_historical_decision(
        client_id=client_id,
        as_of=as_of,
        actor=actor,
        property_id=property_id,
        requirement_id=requirement_id,
        decision_type=decision_type,
    )


@router.get("/api/compliance/graph/requirements/{requirement_id}/trace")
async def trace_requirement(
    request: Request,
    requirement_id: str,
    client_id: str = Query(...),
):
    actor = await _auth_actor(request)
    return await graph_service.trace_requirement(requirement_id, actor=actor, client_id=client_id)


@router.get("/api/compliance/graph/evidence/trace")
async def trace_evidence(
    request: Request,
    anchor_type: str = Query(...),
    anchor_id: str = Query(...),
    client_id: str = Query(...),
):
    actor = await _auth_actor(request)
    return await graph_service.trace_evidence(
        anchor_type=anchor_type, anchor_id=anchor_id, actor=actor, client_id=client_id
    )


@router.get("/api/compliance/graph/internal/storage-debug")
async def storage_debug_blocked(request: Request):
    """Raw storage API is not publicly exposed."""
    if not graph_debug_storage_api():
        raise HTTPException(status_code=404, detail="Not found")
    await admin_route_guard(request)
    return {"warning": "debug only", "collections": "use Graph Service methods"}
