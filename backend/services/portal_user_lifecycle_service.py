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

    # Block only when this user has acted in the system (preserves compliance trail).
    if await db.audit_logs.count_documents({"actor_id": portal_user_id}) > 0:
        blockers.append("audit_logs_present")

    return len(blockers) == 0, blockers


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

    allowed, blockers = await permanent_delete_preflight(db, portal_user_id)
    if not allowed:
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
