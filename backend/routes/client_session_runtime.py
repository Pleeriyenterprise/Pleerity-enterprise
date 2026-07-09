"""Client session runtime API (ILP-5)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from auth import create_access_token
from database import database
from middleware import client_route_guard
from middleware.capability_gating import assert_client_capability
from services.account_lifecycle_runtime_contract import CONTRACT_VERSION, runtime_contract_to_dict
from services.account_session_runtime_service import SessionRuntimeService
from utils.portal_user_scope import merge_active_portal_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/client", tags=["client-session-runtime"], dependencies=[Depends(client_route_guard)])


class SessionValidateBody(BaseModel):
    runtime_version: Optional[int] = None
    entitlements_version: Optional[int] = None
    contract_version: Optional[str] = None


def _attach_runtime_headers(response: Response, payload: dict) -> None:
    response.headers["X-Lifecycle-Contract-Version"] = CONTRACT_VERSION
    response.headers["X-Lifecycle-Runtime-Version"] = str(payload.get("runtime_version", ""))


@router.get("/session-runtime/status")
async def session_runtime_status(request: Request, response: Response):
    """Lightweight session validation without full contract payload."""
    user = await client_route_guard(request)
    await assert_client_capability(user, "CAP_PROFILE_VIEW", "read")
    service = SessionRuntimeService(database.get_db())
    validation = await service.validate_for_user(user)
    response.headers["X-Session-Refresh-Required"] = "true" if validation.force_refresh else "false"
    if validation.runtime_version is not None:
        response.headers["X-Lifecycle-Runtime-Version"] = str(validation.runtime_version)
    return {"validation": validation.to_dict()}


@router.post("/session-runtime/validate")
async def session_runtime_validate(request: Request, response: Response, body: SessionValidateBody):
    """Validate client-held version hints against authoritative Runtime Contract."""
    user = await client_route_guard(request)
    await assert_client_capability(user, "CAP_PROFILE_VIEW", "read")
    service = SessionRuntimeService(database.get_db())
    validation = await service.validate_for_user(
        user,
        header_runtime_version=body.runtime_version,
        header_entitlements_version=body.entitlements_version,
    )
    if body.contract_version and body.contract_version != validation.contract_version:
        validation_dict = validation.to_dict()
        validation_dict["reasons"] = [*validation_dict.get("reasons", []), "contract_version_changed"]
        validation_dict["action"] = "REFRESH_RUNTIME"
        validation_dict["force_refresh"] = True
        return {"validation": validation_dict}
    response.headers["X-Session-Refresh-Required"] = "true" if validation.force_refresh else "false"
    return {"validation": validation.to_dict()}


@router.post("/session-runtime/refresh")
async def session_runtime_refresh(request: Request, response: Response):
    """
    Refresh session runtime metadata and return authoritative Runtime Contract.
    May issue a new access token when entitlements_version changed (authentication only).
    """
    user = await client_route_guard(request)
    await assert_client_capability(user, "CAP_PROFILE_VIEW", "read")
    db = database.get_db()
    portal_user = await db.portal_users.find_one(
        merge_active_portal_user({"portal_user_id": user["portal_user_id"]}),
        {"_id": 0},
    )
    if not portal_user:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    refresh_reason = (request.headers.get("X-Session-Refresh-Reason") or "client_refresh").strip()[:128]
    service = SessionRuntimeService(db)
    payload = await service.build_refresh_payload(user, portal_user, refresh_reason=refresh_reason)
    lifecycle = payload["lifecycle_runtime"]
    _attach_runtime_headers(response, lifecycle)

    validation = payload["validation"]
    result = {
        "session_runtime": payload["session_runtime"],
        "lifecycle_runtime": lifecycle,
        "validation": validation,
    }

    if validation.get("action") in ("REFRESH_TOKEN", "REFRESH_RUNTIME") or validation.get("force_refresh"):
        claims = payload["auth_claims"]
        if user.get("impersonation"):
            claims = {
                **claims,
                "impersonation": True,
                "impersonated_by_portal_user_id": user.get("impersonated_by_portal_user_id"),
                "impersonated_by_role": user.get("impersonated_by_role"),
                "impersonation_started_at": user.get("impersonation_started_at"),
            }
        result["access_token"] = create_access_token(dict(claims))
        result["user"] = {
            "portal_user_id": portal_user["portal_user_id"],
            "email": portal_user["auth_email"],
            "role": portal_user["role"],
            "client_id": portal_user.get("client_id"),
            "session_id": payload["session_runtime"]["session_id"],
            "runtime_version": lifecycle.get("runtime_version"),
            "entitlements_version": payload["session_runtime"].get("entitlements_version"),
        }
    return result
