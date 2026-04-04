"""Client lifecycle: archive, restore, purge eligibility, permanent delete, test-like flags."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from database import database
from middleware import admin_route_guard
from middleware.step_up_auth import require_recent_step_up
from models import UserRole, ClientLifecycleStatus
from services.client_lifecycle_service import (
    archive_client,
    restore_client,
    mark_purge_eligible,
    flag_test_like_client,
    permanent_delete_client,
    permanent_delete_preflight,
    derive_client_lifecycle_status,
    _lifecycle_http_detail,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-client-lifecycle"],
    dependencies=[Depends(admin_route_guard)],
)


class ArchiveClientBody(BaseModel):
    archive_reason: Optional[str] = Field(None, max_length=2000)


class FlagTestLikeBody(BaseModel):
    duplicate_of_client_id: Optional[str] = Field(None, max_length=80)


@router.post("/clients/{client_id}/archive")
async def post_archive_client(
    request: Request,
    client_id: str,
    body: Optional[ArchiveClientBody] = None,
):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    reason = body.archive_reason if body else None
    try:
        await archive_client(
            db,
            client_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
            archive_reason=reason,
        )
        return {"ok": True, "client_id": client_id}
    except ValueError as e:
        code, detail = _lifecycle_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.post("/clients/{client_id}/restore")
async def post_restore_client(request: Request, client_id: str):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await restore_client(
            db,
            client_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {"ok": True, "client_id": client_id}
    except ValueError as e:
        code, detail = _lifecycle_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.post("/clients/{client_id}/mark-purge-eligible")
async def post_mark_purge_eligible(request: Request, client_id: str):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await mark_purge_eligible(
            db,
            client_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {"ok": True, "client_id": client_id}
    except ValueError as e:
        code, detail = _lifecycle_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.post("/clients/{client_id}/flag-test-like")
async def post_flag_test_like(
    request: Request,
    client_id: str,
    body: Optional[FlagTestLikeBody] = None,
):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    dup = body.duplicate_of_client_id if body else None
    try:
        await flag_test_like_client(
            db,
            client_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
            duplicate_of_client_id=dup,
        )
        return {"ok": True, "client_id": client_id}
    except ValueError as e:
        code, detail = _lifecycle_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.get("/clients/{client_id}/permanent-delete-check")
async def get_permanent_delete_check(request: Request, client_id: str):
    await admin_route_guard(request)
    db = database.get_db()
    allowed, blockers = await permanent_delete_preflight(db, client_id)
    return {"allowed": allowed, "blockers": blockers}


@router.delete("/clients/{client_id}/permanent")
async def delete_client_permanent(request: Request, client_id: str):
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await permanent_delete_client(
            db,
            client_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {"ok": True, "client_id": client_id}
    except ValueError as e:
        code, detail = _lifecycle_http_detail(e)
        raise HTTPException(status_code=code, detail=detail)


@router.get("/client-lifecycle/meta")
async def get_lifecycle_meta(request: Request):
    """Enumerations for admin UI (path avoids clash with /clients/{client_id})."""
    await admin_route_guard(request)
    return {
        "client_lifecycle_statuses": [s.value for s in ClientLifecycleStatus],
        "derived_hint": "When client_lifecycle_status is null, API lists derive display status from onboarding + subscription.",
    }


@router.get("/clients/{client_id}/lifecycle-summary")
async def get_client_lifecycle_summary(request: Request, client_id: str):
    await admin_route_guard(request)
    db = database.get_db()
    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    derived = derive_client_lifecycle_status(doc)
    allowed, blockers = await permanent_delete_preflight(db, client_id)
    from services.client_lifecycle_service import get_latest_provisioning_job

    job = await get_latest_provisioning_job(db, client_id)
    return {
        "client_id": client_id,
        "stored_client_lifecycle_status": doc.get("client_lifecycle_status"),
        "derived_client_lifecycle_status": derived,
        "payment_lifecycle_status": doc.get("lifecycle_status"),
        "onboarding_status": doc.get("onboarding_status"),
        "subscription_status": doc.get("subscription_status"),
        "is_deleted": doc.get("is_deleted", False),
        "purge_eligible": doc.get("purge_eligible", False),
        "is_test_like": doc.get("is_test_like", False),
        "archived_at": doc.get("archived_at"),
        "archive_reason": doc.get("archive_reason"),
        "duplicate_of_client_id": doc.get("duplicate_of_client_id"),
        "provisioning_job": {"status": job.get("status"), "job_id": job.get("job_id")} if job else None,
        "permanent_delete_allowed": allowed,
        "permanent_delete_blockers": blockers,
    }
