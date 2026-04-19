"""
Enterprise portal user archive / restore / conditional permanent delete.
Does not remove clients, Stripe IDs, invoices, or subscriptions — permanent delete
only removes the portal_users document when preflight checks pass.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from models import AuditAction, UserRole, UserStatus, SubscriptionStatus
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

async def get_portal_user_any_status(db, portal_user_id: str) -> Optional[Dict[str, Any]]:
    return await db.portal_users.find_one({"portal_user_id": portal_user_id}, {"_id": 0})


async def permanent_delete_preflight(db, portal_user_id: str) -> Tuple[bool, List[str]]:
    """
    Returns (allowed, blockers). Never deletes. Billing-safe: blocks on client Stripe
    links, invoices, properties, and material audit history.
    """
    user = await get_portal_user_any_status(db, portal_user_id)
    if not user:
        return False, ["user_not_found"]

    blockers: List[str] = []
    cid = user.get("client_id")

    if cid:
        client = await db.clients.find_one(
            {"client_id": cid},
            {
                "_id": 0,
                "client_id": 1,
                "stripe_customer_id": 1,
                "stripe_subscription_id": 1,
                "subscription_status": 1,
            },
        )
        if client:
            if client.get("stripe_customer_id") or client.get("stripe_subscription_id"):
                blockers.append("client_stripe_linked")
            st = client.get("subscription_status")
            if st == SubscriptionStatus.ACTIVE.value:
                blockers.append("subscription_active")

        inv_ops = await db.invoices.count_documents({"client_id": cid})
        if inv_ops > 0:
            blockers.append("client_has_invoices")

        checkout_inv = await db.stripe_checkout_invoices.count_documents({"client_id": cid})
        if checkout_inv > 0:
            blockers.append("client_has_checkout_invoices")

        props = await db.properties.count_documents({"client_id": cid})
        if props > 0:
            blockers.append("client_has_properties")

    # Tenant-specific: preserve tenancy and tenant-facing compliance / ops history.
    if user.get("role") == UserRole.ROLE_TENANT.value:
        if await db.tenant_assignments.count_documents({"tenant_id": portal_user_id}) > 0:
            blockers.append("tenant_assignments_exist")
        if await db.tenant_requests.count_documents({"tenant_id": portal_user_id}) > 0:
            blockers.append("tenant_requests_exist")
        if await db.maintenance_issues.count_documents({"reporter_id": portal_user_id}) > 0:
            blockers.append("tenant_maintenance_issues_exist")

    # Block when this user has audit history as actor — unless explicitly flagged test/dummy
    # (narrow bypass: does not waive Stripe, invoices, properties, or tenant artefacts).
    if await db.audit_logs.count_documents({"actor_id": portal_user_id}) > 0:
        if not bool(user.get("is_test_like")):
            blockers.append("audit_logs_present")

    return len(blockers) == 0, blockers


async def set_portal_user_test_like_flag(
    db,
    portal_user_id: str,
    is_test_like: bool,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    """Mark a portal user as test/dummy for admin cleanup policy (never on OWNER)."""
    target = await get_portal_user_any_status(db, portal_user_id)
    if not target:
        raise ValueError("user_not_found")
    if target.get("role") == UserRole.ROLE_OWNER.value:
        raise ValueError("owner_cannot_be_flagged_test_like")

    now = datetime.now(timezone.utc).isoformat()
    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {"$set": {"is_test_like": bool(is_test_like), "updated_at": now}},
    )

    await create_audit_log(
        action=AuditAction.PORTAL_USER_TEST_LIKE_SET,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=target.get("client_id"),
        resource_type="portal_user",
        resource_id=portal_user_id,
        metadata={
            "is_test_like": bool(is_test_like),
            "target_email": target.get("auth_email") or target.get("email"),
            "target_role": target.get("role"),
        },
    )


async def archive_portal_user(
    db,
    portal_user_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    if portal_user_id == actor_portal_user_id:
        raise ValueError("cannot_archive_self")

    target = await get_portal_user_any_status(db, portal_user_id)
    if not target:
        raise ValueError("user_not_found")
    if target.get("is_deleted") is True:
        raise ValueError("already_archived")

    if target.get("role") == UserRole.ROLE_OWNER.value:
        raise ValueError("owner_cannot_be_archived")

    if target.get("role") == UserRole.ROLE_ADMIN.value and target.get("status") == UserStatus.ACTIVE.value:
        active_admin_count = await db.portal_users.count_documents(
            {
                "role": UserRole.ROLE_ADMIN.value,
                "status": UserStatus.ACTIVE.value,
                "is_deleted": {"$ne": True},
            }
        )
        if active_admin_count <= 1:
            raise ValueError("last_active_admin")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {
            "$set": {
                "is_deleted": True,
                "deleted_at": now_iso,
                "deleted_by": actor_portal_user_id,
                "status": UserStatus.DISABLED.value,
                "updated_at": now_iso,
            },
            "$inc": {"session_version": 1},
        },
    )

    await create_audit_log(
        action=AuditAction.USER_ARCHIVED,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=target.get("client_id"),
        resource_type="portal_user",
        resource_id=portal_user_id,
        metadata={
            "target_email": target.get("auth_email") or target.get("email"),
            "target_role": target.get("role"),
        },
    )


async def restore_portal_user(
    db,
    portal_user_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    target = await get_portal_user_any_status(db, portal_user_id)
    if not target:
        raise ValueError("user_not_found")
    if target.get("is_deleted") is not True:
        raise ValueError("not_archived")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {
            "$set": {
                "is_deleted": False,
                "status": UserStatus.ACTIVE.value,
                "updated_at": now_iso,
            },
            "$unset": {"deleted_at": "", "deleted_by": ""},
        },
    )

    await create_audit_log(
        action=AuditAction.USER_RESTORED,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=target.get("client_id"),
        resource_type="portal_user",
        resource_id=portal_user_id,
        metadata={
            "target_email": target.get("auth_email") or target.get("email"),
        },
    )


async def permanent_delete_portal_user(
    db,
    portal_user_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    if portal_user_id == actor_portal_user_id:
        raise ValueError("cannot_delete_self")

    target = await get_portal_user_any_status(db, portal_user_id)
    if not target:
        raise ValueError("user_not_found")

    if target.get("role") == UserRole.ROLE_OWNER.value:
        raise ValueError("owner_cannot_be_deleted")

    await create_audit_log(
        action=AuditAction.USER_HARD_DELETE_ATTEMPTED,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=target.get("client_id"),
        resource_type="portal_user",
        resource_id=portal_user_id,
        metadata={
            "target_email": target.get("auth_email") or target.get("email"),
            "target_role": target.get("role"),
            "is_test_like": bool(target.get("is_test_like")),
        },
    )

    allowed, blockers = await permanent_delete_preflight(db, portal_user_id)
    if not allowed:
        await create_audit_log(
            action=AuditAction.USER_HARD_DELETE_BLOCKED,
            actor_role=actor_role,
            actor_id=actor_portal_user_id,
            client_id=target.get("client_id"),
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={
                "blockers": blockers,
                "is_test_like": bool(target.get("is_test_like")),
            },
        )
        raise ValueError("preflight_failed:" + ",".join(blockers))

    res = await db.portal_users.delete_one({"portal_user_id": portal_user_id})
    if res.deleted_count != 1:
        raise ValueError("user_not_found")

    await create_audit_log(
        action=AuditAction.USER_DELETED_PERMANENTLY,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=target.get("client_id"),
        resource_type="portal_user",
        resource_id=portal_user_id,
        metadata={
            "target_email": target.get("auth_email") or target.get("email"),
            "target_role": target.get("role"),
            "blockers_checked": "passed",
        },
    )


async def suspend_portal_user_identity(
    db,
    portal_user_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    """Disable login without soft-delete (distinct from archive)."""
    if portal_user_id == actor_portal_user_id:
        raise ValueError("cannot_suspend_self")
    target = await get_portal_user_any_status(db, portal_user_id)
    if not target:
        raise ValueError("user_not_found")
    if target.get("is_deleted") is True:
        raise ValueError("archived_use_restore_first")
    if target.get("role") == UserRole.ROLE_OWNER.value:
        raise ValueError("owner_cannot_be_suspended")
    if target.get("status") == UserStatus.DISABLED.value:
        raise ValueError("already_suspended")
    now = datetime.now(timezone.utc).isoformat()
    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {"$set": {"status": UserStatus.DISABLED.value, "updated_at": now}, "$inc": {"session_version": 1}},
    )


async def resume_portal_user_identity(
    db,
    portal_user_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    """Re-enable login after suspend (not for archived users)."""
    target = await get_portal_user_any_status(db, portal_user_id)
    if not target:
        raise ValueError("user_not_found")
    if target.get("is_deleted") is True:
        raise ValueError("archived_use_restore_first")
    if target.get("status") != UserStatus.DISABLED.value:
        raise ValueError("not_suspended")
    now = datetime.now(timezone.utc).isoformat()
    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {"$set": {"status": UserStatus.ACTIVE.value, "updated_at": now}, "$inc": {"session_version": 1}},
    )
