"""Admin Lifecycle Operations — governed diagnostics and recovery actions per client."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database import database
from middleware import admin_route_guard
from middleware.step_up_auth import require_recent_step_up
from models import AuditAction, UserRole
from services.admin_action_governance import enforce_governed_admin_action
from services.admin_lifecycle_operations_service import (
    admin_reconcile_from_stripe,
    admin_refresh_runtime_contract,
    admin_resume_scheduled_cancellation,
    build_lifecycle_operations_snapshot,
    build_support_bundle_for_client,
)
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/clients",
    tags=["admin-lifecycle-operations"],
    dependencies=[Depends(admin_route_guard)],
)


class LifecycleOpsReasonBody(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)


@router.get("/{client_id}/lifecycle-operations")
async def get_lifecycle_operations_snapshot(request: Request, client_id: str):
    """Read-only lifecycle / billing / runtime / webhook operations view for support."""
    await admin_route_guard(request)
    try:
        return await build_lifecycle_operations_snapshot(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{client_id}/lifecycle-operations/refresh-runtime-contract")
async def post_refresh_runtime_contract(request: Request, client_id: str, body: LifecycleOpsReasonBody):
    user = await admin_route_guard(request)
    await enforce_governed_admin_action(
        request,
        user,
        "lifecycle_ops_refresh_runtime",
        reason=body.reason,
        resource_key=client_id,
        require_recent_step_up=require_recent_step_up,
    )
    try:
        result = await admin_refresh_runtime_contract(
            client_id,
            actor_id=user.get("portal_user_id"),
            actor_role=user.get("role", UserRole.ROLE_ADMIN.value),
            reason=body.reason.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=user.get("role", UserRole.ROLE_ADMIN.value),
        actor_id=user.get("portal_user_id"),
        client_id=client_id,
        metadata={"action_type": "LIFECYCLE_OPS_REFRESH_RUNTIME", **result},
    )
    return result


@router.post("/{client_id}/lifecycle-operations/reconcile-stripe")
async def post_reconcile_from_stripe(request: Request, client_id: str, body: LifecycleOpsReasonBody):
    user = await admin_route_guard(request)
    await enforce_governed_admin_action(
        request,
        user,
        "lifecycle_ops_reconcile_stripe",
        reason=body.reason,
        resource_key=client_id,
        require_recent_step_up=require_recent_step_up,
    )
    try:
        result = await admin_reconcile_from_stripe(
            client_id,
            actor_id=user.get("portal_user_id"),
            actor_role=user.get("role", UserRole.ROLE_ADMIN.value),
            reason=body.reason.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=user.get("role", UserRole.ROLE_ADMIN.value),
        actor_id=user.get("portal_user_id"),
        client_id=client_id,
        metadata={"action_type": "LIFECYCLE_OPS_RECONCILE_STRIPE", **result},
    )
    return result


@router.post("/{client_id}/lifecycle-operations/resume-subscription")
async def post_resume_subscription(request: Request, client_id: str, body: LifecycleOpsReasonBody):
    user = await admin_route_guard(request)
    await enforce_governed_admin_action(
        request,
        user,
        "lifecycle_ops_resume_subscription",
        reason=body.reason,
        resource_key=client_id,
        require_recent_step_up=require_recent_step_up,
    )
    try:
        result = await admin_resume_scheduled_cancellation(
            client_id,
            actor_id=user.get("portal_user_id"),
            actor_role=user.get("role", UserRole.ROLE_ADMIN.value),
            reason=body.reason.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=user.get("role", UserRole.ROLE_ADMIN.value),
        actor_id=user.get("portal_user_id"),
        client_id=client_id,
        metadata={"action_type": "LIFECYCLE_OPS_RESUME_SUBSCRIPTION", **result},
    )
    return result


@router.post("/{client_id}/lifecycle-operations/mark-support-review")
async def post_mark_support_review(request: Request, client_id: str, body: LifecycleOpsReasonBody):
    user = await admin_route_guard(request)
    await enforce_governed_admin_action(
        request,
        user,
        "lifecycle_ops_mark_support_review",
        reason=body.reason,
        resource_key=client_id,
        require_recent_step_up=require_recent_step_up,
    )
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    reason = body.reason.strip()
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=user.get("role", UserRole.ROLE_ADMIN.value),
        actor_id=user.get("portal_user_id"),
        client_id=client_id,
        metadata={
            "action_type": "LIFECYCLE_OPS_SUPPORT_REVIEW_FLAGGED",
            "reason": reason,
            "escalation": "billing_lifecycle_support_review",
        },
    )
    return {"success": True, "flagged": True, "reason": reason}


@router.post("/{client_id}/lifecycle-operations/export-support-bundle")
async def post_export_support_bundle(request: Request, client_id: str, body: LifecycleOpsReasonBody):
    user = await admin_route_guard(request)
    await enforce_governed_admin_action(
        request,
        user,
        "lifecycle_ops_export_support_bundle",
        reason=body.reason,
        resource_key=client_id,
        require_recent_step_up=require_recent_step_up,
    )
    try:
        snapshot, zip_bytes = await build_support_bundle_for_client(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=user.get("role", UserRole.ROLE_ADMIN.value),
        actor_id=user.get("portal_user_id"),
        client_id=client_id,
        metadata={
            "action_type": "LIFECYCLE_OPS_EXPORT_SUPPORT_BUNDLE",
            "reason": body.reason.strip(),
            "bundle_size_bytes": len(zip_bytes),
            "health_overall": (snapshot.get("customer_health") or {}).get("overall"),
        },
    )
    filename = f"support-bundle-{client_id}.zip"
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
