"""
Read-only HTTP API for integrations (API keys).

Management (JWT): /api/client/integrations/read-api-keys — gated by webhooks entitlement (Professional).
Data (API key):    /api/client-data/v1/... — Authorization: Bearer ple_read_... or X-Pleerity-Read-Key.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from database import database
from middleware import client_route_guard
from models import AuditAction
from services import client_read_api_service as read_api
from services.compliance_score import calculate_compliance_score
from services.plan_registry import plan_registry
from utils.audit import create_audit_log
from utils.rate_limiter import log_rate_limit_event, rate_limiter

logger = logging.getLogger(__name__)

mgmt_router = APIRouter(prefix="/api/client/integrations/read-api-keys", tags=["client-read-api"])
data_router = APIRouter(
    prefix="/api/client-data/v1",
    tags=["client-read-api-data"],
)


class CreateReadApiKeyBody(BaseModel):
    name: Optional[str] = None


async def _ensure_webhooks(client_id: str) -> None:
    allowed, error_msg, error_details = await plan_registry.enforce_feature(client_id, "webhooks")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details
            or {
                "message": error_msg,
                "feature": "webhooks",
                "upgrade_required": True,
            },
        )


def _extract_read_api_token(request: Request) -> Optional[str]:
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("X-Pleerity-Read-Key") or "").strip() or None


async def _authenticate_read_request(request: Request) -> Dict[str, Any]:
    token = _extract_read_api_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Use Authorization: Bearer <ple_read_...> or X-Pleerity-Read-Key.",
        )
    ctx = await read_api.resolve_token(token)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )
    allowed, error_msg, error_details = await plan_registry.enforce_feature(ctx["client_id"], "webhooks")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details
            or {
                "message": error_msg,
                "feature": "webhooks",
                "upgrade_required": True,
            },
        )
    ok, err_msg = await rate_limiter.check_rate_limit(
        f"read_api:{ctx['key_id']}",
        max_attempts=120,
        window_minutes=1,
    )
    if not ok:
        log_rate_limit_event(
            "client_read_api",
            str(ctx.get("key_id", ""))[:8],
            request.client.host if request.client else None,
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_msg)
    return ctx


def _require_scope(ctx: Dict[str, Any], scope: str) -> None:
    if not read_api.has_scope(ctx, scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key missing required scope: {scope}",
        )


# --- Management (JWT) ---


@mgmt_router.get("")
async def list_read_api_keys(request: Request):
    user = await client_route_guard(request)
    await _ensure_webhooks(user["client_id"])
    keys = await read_api.list_keys(user["client_id"])
    return {
        "keys": keys,
        "data_base_path": "/api/client-data/v1",
        "auth_headers": ["Authorization: Bearer <token>", "X-Pleerity-Read-Key: <token>"],
        "scopes": list(read_api.DEFAULT_SCOPES),
    }


@mgmt_router.post("")
async def create_read_api_key(request: Request, body: CreateReadApiKeyBody):
    user = await client_route_guard(request)
    await _ensure_webhooks(user["client_id"])
    try:
        secret, key_meta = await read_api.create_key(
            user["client_id"],
            user["portal_user_id"],
            body.name,
        )
    except ValueError as e:
        if str(e) == "MAX_KEYS":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum number of read API keys reached for this account",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user["portal_user_id"],
        client_id=user["client_id"],
        resource_type="client_read_api_key",
        resource_id=key_meta["key_id"],
        metadata={"action": "read_api_key_created", "name": key_meta.get("name")},
    )
    return {
        "key": key_meta,
        "secret": secret,
        "warning": "Copy this secret now; it cannot be shown again.",
    }


@mgmt_router.delete("/{key_id}")
async def revoke_read_api_key(request: Request, key_id: str):
    user = await client_route_guard(request)
    await _ensure_webhooks(user["client_id"])
    ok = await read_api.revoke_key(user["client_id"], key_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found or already revoked")
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user["portal_user_id"],
        client_id=user["client_id"],
        resource_type="client_read_api_key",
        resource_id=key_id,
        metadata={"action": "read_api_key_revoked"},
    )
    return {"ok": True}


# --- Data (API key) ---


@data_router.get("/capabilities")
async def data_capabilities(request: Request):
    """Discovery document for integrators: paths, required scopes, and scopes on this key."""
    ctx = await _authenticate_read_request(request)
    return {
        "version": "v1",
        "resources": [
            {
                "id": "capabilities",
                "path": "/capabilities",
                "method": "GET",
                "required_scope": None,
                "description": "This document",
            },
            {
                "id": "properties",
                "path": "/properties",
                "method": "GET",
                "required_scope": read_api.SCOPE_PROPERTIES,
            },
            {
                "id": "property_requirements",
                "path": "/properties/{property_id}/requirements",
                "method": "GET",
                "required_scope": read_api.SCOPE_REQUIREMENTS,
            },
            {
                "id": "priorities",
                "path": "/priorities",
                "method": "GET",
                "required_scope": read_api.SCOPE_TASKS,
            },
            {
                "id": "compliance_score",
                "path": "/compliance-score",
                "method": "GET",
                "required_scope": read_api.SCOPE_COMPLIANCE,
            },
        ],
        "scopes_on_key": ctx.get("scopes") or [],
        "auth": {
            "headers": ["Authorization: Bearer <ple_read_…>", "X-Pleerity-Read-Key: <ple_read_…>"],
        },
        "rate_limit_hint": "120 requests per minute per key",
    }


@data_router.get("/properties")
async def data_list_properties(request: Request):
    ctx = await _authenticate_read_request(request)
    _require_scope(ctx, read_api.SCOPE_PROPERTIES)
    db = database.get_db()
    try:
        properties: List[Dict[str, Any]] = await db.properties.find(
            {"client_id": ctx["client_id"]},
            {"_id": 0},
        ).to_list(500)
        return {"properties": properties}
    except Exception as e:
        logger.error("read-api properties error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load properties")


@data_router.get("/properties/{property_id}/requirements")
async def data_property_requirements(request: Request, property_id: str):
    ctx = await _authenticate_read_request(request)
    _require_scope(ctx, read_api.SCOPE_REQUIREMENTS)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": ctx["client_id"]},
        {"_id": 0},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    try:
        requirements = await db.requirements.find(
            {"property_id": property_id, "client_id": ctx["client_id"]},
            {"_id": 0},
        ).to_list(500)
        return {"requirements": requirements}
    except Exception as e:
        logger.error("read-api requirements error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requirements",
        )


@data_router.get("/priorities")
async def data_priorities(
    request: Request,
    property_id: Optional[str] = Query(None),
    limit: int = Query(120, ge=1, le=200),
):
    ctx = await _authenticate_read_request(request)
    _require_scope(ctx, read_api.SCOPE_TASKS)
    try:
        from services.unified_tasks_service import get_unified_tasks_for_client

        return await get_unified_tasks_for_client(
            client_id=ctx["client_id"],
            property_id_filter=property_id,
            raw_limit=limit,
        )
    except Exception as e:
        logger.error("read-api priorities error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load priorities",
        )


@data_router.get("/compliance-score")
async def data_compliance_score(request: Request):
    ctx = await _authenticate_read_request(request)
    _require_scope(ctx, read_api.SCOPE_COMPLIANCE)
    try:
        return await calculate_compliance_score(ctx["client_id"])
    except Exception as e:
        logger.error("read-api compliance-score error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate compliance score",
        )
