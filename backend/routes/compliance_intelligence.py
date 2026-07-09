"""
Compliance Intelligence Layer — admin HTTP routes (Phase 5).

All reads go through Graph Service via investigate(); no graph storage access.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from middleware import admin_route_guard
from services.compliance_graph_service.access import ActorContext, actor_from_request_user
from services.compliance_intelligence.investigate import investigate

router = APIRouter(tags=["compliance-intelligence"])


class InvestigateRequest(BaseModel):
    method: str = Field(..., description="Graph Service method name")
    params: Dict[str, Any] = Field(default_factory=dict)
    client_id: Optional[str] = None
    question: Optional[str] = None
    narrate: bool = False


async def _admin_actor(request: Request) -> ActorContext:
    await admin_route_guard(request)
    user = getattr(request.state, "user", None) or {}
    return actor_from_request_user(user, is_admin=True)


@router.post("/api/admin/compliance/intelligence/investigate")
async def admin_investigate(request: Request, body: InvestigateRequest):
    """Dispatch to Graph Service; optional Tier 2 narration when enabled."""
    actor = await _admin_actor(request)
    cid = body.client_id or body.params.get("client_id")
    if cid:
        from services.compliance_graph_service.access import enforce_tenant_access

        enforce_tenant_access(actor, client_id=cid)

    try:
        return await investigate(
            method=body.method,
            params=body.params,
            actor=actor,
            client_id=cid,
            question=body.question,
            narrate=body.narrate,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
