"""Unified identity lifecycle admin API (clients, contractors, portal users)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from database import database
from middleware import admin_route_guard, require_owner, require_owner_or_admin
from middleware.step_up_auth import require_recent_step_up
from models import IdentityKind, UserRole
from services.identity_lifecycle_service import (
    archive_identity,
    identity_http_detail,
    list_unified_identities,
    mark_purge_eligible_identity,
    permanent_delete_identity,
    permanent_delete_preflight_identity,
    resume_identity,
    restore_identity,
    suspend_identity,
    set_identity_test_like,
)

router = APIRouter(
    prefix="/api/admin/identities",
    tags=["admin-identity-lifecycle"],
    dependencies=[Depends(admin_route_guard)],
)


class ArchiveIdentityBody(BaseModel):
    archive_reason: Optional[str] = Field(None, max_length=2000)


class IdentityTestLikeBody(BaseModel):
    is_test_like: bool = Field(..., description="Mark portal user as test/dummy (portal_user kind only)")


@router.get("/meta/enums")
async def get_identity_meta(request: Request):
    await admin_route_guard(request)
    return {
        "identity_kinds": [k.value for k in IdentityKind],
        "lifecycle_statuses": ["LEAD", "PENDING_SETUP", "ACTIVE", "SUSPENDED", "ARCHIVED", "PURGE_ELIGIBLE"],
        "flags_filters": ["test_like", "live"],
        "note": "Profiles stay in clients / contractors / portal_users; this API is the cross-type control plane.",
    }


@router.get("")
async def get_identity_list(
    request: Request,
    kind: Optional[str] = Query(None, description="client | contractor | portal_user"),
    lifecycle: Optional[str] = Query(None, description="LEAD | PENDING_SETUP | ACTIVE | SUSPENDED | ARCHIVED | PURGE_ELIGIBLE"),
    q: Optional[str] = Query(None),
    flags: Optional[str] = Query(None, description="Optional filter: test_like"),
    include_hard_delete_eligibility: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=100),
):
    await admin_route_guard(request)
    db = database.get_db()
    return await list_unified_identities(
        db,
        kind_filter=kind,
        lifecycle_filter=lifecycle,
        q=q,
        skip=skip,
        limit=limit,
        flags_filter=flags,
        include_hard_delete_eligibility=include_hard_delete_eligibility,
    )


@router.post("/{kind}/{resource_id}/archive")
async def post_identity_archive(
    request: Request,
    kind: str,
    resource_id: str,
    body: Optional[ArchiveIdentityBody] = None,
):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await archive_identity(
            db,
            kind,
            resource_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
            archive_reason=body.archive_reason if body else None,
        )
        return {"ok": True, "kind": kind, "id": resource_id}
    except ValueError as e:
        code, detail = identity_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.post("/{kind}/{resource_id}/restore")
async def post_identity_restore(request: Request, kind: str, resource_id: str):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await restore_identity(db, kind, resource_id, user["portal_user_id"], actor_role=UserRole(user["role"]))
        return {"ok": True, "kind": kind, "id": resource_id}
    except ValueError as e:
        code, detail = identity_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.post("/{kind}/{resource_id}/test-like")
async def post_identity_test_like(
    request: Request,
    kind: str,
    resource_id: str,
    body: IdentityTestLikeBody,
):
    user = await require_owner_or_admin(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await set_identity_test_like(
            db,
            kind,
            resource_id,
            body.is_test_like,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {"ok": True, "kind": kind, "id": resource_id, "is_test_like": body.is_test_like}
    except ValueError as e:
        code, detail = identity_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.post("/{kind}/{resource_id}/suspend")
async def post_identity_suspend(request: Request, kind: str, resource_id: str):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await suspend_identity(db, kind, resource_id, user["portal_user_id"], actor_role=UserRole(user["role"]))
        return {"ok": True, "kind": kind, "id": resource_id}
    except ValueError as e:
        code, detail = identity_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.post("/{kind}/{resource_id}/resume")
async def post_identity_resume(request: Request, kind: str, resource_id: str):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await resume_identity(db, kind, resource_id, user["portal_user_id"], actor_role=UserRole(user["role"]))
        return {"ok": True, "kind": kind, "id": resource_id}
    except ValueError as e:
        code, detail = identity_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.post("/{kind}/{resource_id}/mark-purge-eligible")
async def post_identity_mark_purge(request: Request, kind: str, resource_id: str):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await mark_purge_eligible_identity(db, kind, resource_id, user["portal_user_id"], actor_role=UserRole(user["role"]))
        return {"ok": True, "kind": kind, "id": resource_id}
    except ValueError as e:
        code, detail = identity_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.get("/{kind}/{resource_id}/permanent-delete-check")
async def get_identity_permanent_delete_check(request: Request, kind: str, resource_id: str):
    await require_owner_or_admin(request)
    db = database.get_db()
    allowed, blockers = await permanent_delete_preflight_identity(db, kind, resource_id)
    return {"allowed": allowed, "blockers": blockers}


@router.delete("/{kind}/{resource_id}/permanent")
async def delete_identity_permanent(request: Request, kind: str, resource_id: str):
    user = await require_owner(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await permanent_delete_identity(db, kind, resource_id, user["portal_user_id"], actor_role=UserRole(user["role"]))
        return {"ok": True, "kind": kind, "id": resource_id}
    except ValueError as e:
        code, detail = identity_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)
