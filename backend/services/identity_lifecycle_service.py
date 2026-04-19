"""
Unified identity lifecycle facade (clients, contractors, portal users).
Profiles remain in their collections; this module dispatches actions and emits IDENTITY_* audit events.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from models import AuditAction, ClientLifecycleStatus, IdentityKind, UserRole
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


async def set_identity_test_like(
    db,
    kind: str,
    resource_id: str,
    is_test_like: bool,
    actor_id: str,
    *,
    actor_role: UserRole,
) -> None:
    k = _norm_kind(kind)
    if k != IdentityKind.PORTAL_USER.value:
        raise ValueError("test_flag_portal_users_only")
    from services.portal_user_lifecycle_service import set_portal_user_test_like_flag

    await set_portal_user_test_like_flag(
        db,
        resource_id.strip(),
        is_test_like,
        actor_id,
        actor_role=actor_role,
    )


def _norm_kind(kind: str) -> str:
    return (kind or "").strip().lower()


async def _audit_identity(
    *,
    action: AuditAction,
    actor_id: str,
    actor_role: UserRole,
    identity_kind: str,
    resource_id: str,
    client_id: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    meta = {"identity_kind": identity_kind, "resource_id": resource_id}
    if metadata:
        meta.update(metadata)
    await create_audit_log(
        action=action,
        actor_role=actor_role,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="identity",
        resource_id=f"{identity_kind}:{resource_id}",
        metadata=meta,
    )


async def resolve_client_id_for_identity(db, kind: str, resource_id: str) -> Optional[str]:
    k = _norm_kind(kind)
    if k == IdentityKind.CLIENT.value:
        return resource_id.strip()
    if k == IdentityKind.PORTAL_USER.value:
        u = await db.portal_users.find_one({"portal_user_id": resource_id.strip()}, {"_id": 0, "client_id": 1})
        return (u or {}).get("client_id")
    if k == IdentityKind.CONTRACTOR.value:
        c = await db.contractors.find_one({"contractor_id": resource_id.strip()}, {"_id": 0, "client_id": 1})
        cid = (c or {}).get("client_id")
        return str(cid).strip() if cid else None
    return None


async def archive_identity(
    db,
    kind: str,
    resource_id: str,
    actor_id: str,
    *,
    actor_role: UserRole,
    archive_reason: Optional[str] = None,
) -> None:
    k = _norm_kind(kind)
    if k == IdentityKind.CLIENT.value:
        from services.client_lifecycle_service import archive_client

        await archive_client(db, resource_id.strip(), actor_id, actor_role=actor_role, archive_reason=archive_reason)
    elif k == IdentityKind.CONTRACTOR.value:
        from services.contractor_identity_lifecycle import archive_contractor_identity

        await archive_contractor_identity(db, resource_id.strip(), actor_id, actor_role=actor_role)
    elif k == IdentityKind.PORTAL_USER.value:
        from services.portal_user_lifecycle_service import archive_portal_user

        await archive_portal_user(db, resource_id.strip(), actor_id, actor_role=actor_role)
    else:
        raise ValueError("invalid_identity_kind")
    cid = await resolve_client_id_for_identity(db, k, resource_id)
    await _audit_identity(
        action=AuditAction.IDENTITY_ARCHIVED,
        actor_id=actor_id,
        actor_role=actor_role,
        identity_kind=k,
        resource_id=resource_id.strip(),
        client_id=cid,
        metadata={"archive_reason": archive_reason} if archive_reason else None,
    )


async def restore_identity(
    db,
    kind: str,
    resource_id: str,
    actor_id: str,
    *,
    actor_role: UserRole,
) -> None:
    k = _norm_kind(kind)
    if k == IdentityKind.CLIENT.value:
        from services.client_lifecycle_service import restore_client

        await restore_client(db, resource_id.strip(), actor_id, actor_role=actor_role)
    elif k == IdentityKind.CONTRACTOR.value:
        from services.contractor_identity_lifecycle import restore_contractor_identity

        await restore_contractor_identity(db, resource_id.strip(), actor_id, actor_role=actor_role)
    elif k == IdentityKind.PORTAL_USER.value:
        from services.portal_user_lifecycle_service import restore_portal_user

        await restore_portal_user(db, resource_id.strip(), actor_id, actor_role=actor_role)
    else:
        raise ValueError("invalid_identity_kind")
    cid = await resolve_client_id_for_identity(db, k, resource_id)
    await _audit_identity(
        action=AuditAction.IDENTITY_RESTORED,
        actor_id=actor_id,
        actor_role=actor_role,
        identity_kind=k,
        resource_id=resource_id.strip(),
        client_id=cid,
    )


async def suspend_identity(
    db,
    kind: str,
    resource_id: str,
    actor_id: str,
    *,
    actor_role: UserRole,
) -> None:
    k = _norm_kind(kind)
    if k == IdentityKind.CLIENT.value:
        from services.client_lifecycle_service import suspend_client_org

        await suspend_client_org(db, resource_id.strip(), actor_id, actor_role=actor_role)
    elif k == IdentityKind.CONTRACTOR.value:
        from services.contractor_identity_lifecycle import suspend_contractor_identity

        await suspend_contractor_identity(db, resource_id.strip(), actor_id, actor_role=actor_role)
    elif k == IdentityKind.PORTAL_USER.value:
        from services.portal_user_lifecycle_service import suspend_portal_user_identity

        await suspend_portal_user_identity(db, resource_id.strip(), actor_id, actor_role=actor_role)
    else:
        raise ValueError("invalid_identity_kind")
    cid = await resolve_client_id_for_identity(db, k, resource_id)
    await _audit_identity(
        action=AuditAction.IDENTITY_SUSPENDED,
        actor_id=actor_id,
        actor_role=actor_role,
        identity_kind=k,
        resource_id=resource_id.strip(),
        client_id=cid,
    )


async def resume_identity(
    db,
    kind: str,
    resource_id: str,
    actor_id: str,
    *,
    actor_role: UserRole,
) -> None:
    k = _norm_kind(kind)
    if k == IdentityKind.CLIENT.value:
        from services.client_lifecycle_service import resume_client_org

        await resume_client_org(db, resource_id.strip(), actor_id, actor_role=actor_role)
    elif k == IdentityKind.CONTRACTOR.value:
        from services.contractor_identity_lifecycle import resume_contractor_identity

        await resume_contractor_identity(db, resource_id.strip(), actor_id, actor_role=actor_role)
    elif k == IdentityKind.PORTAL_USER.value:
        from services.portal_user_lifecycle_service import resume_portal_user_identity

        await resume_portal_user_identity(db, resource_id.strip(), actor_id, actor_role=actor_role)
    else:
        raise ValueError("invalid_identity_kind")
    cid = await resolve_client_id_for_identity(db, k, resource_id)
    await _audit_identity(
        action=AuditAction.IDENTITY_RESTORED,
        actor_id=actor_id,
        actor_role=actor_role,
        identity_kind=k,
        resource_id=resource_id.strip(),
        client_id=cid,
        metadata={"resume_from": "suspended"},
    )


async def mark_purge_eligible_identity(
    db,
    kind: str,
    resource_id: str,
    actor_id: str,
    *,
    actor_role: UserRole,
) -> None:
    k = _norm_kind(kind)
    if k != IdentityKind.CLIENT.value:
        raise ValueError("purge_eligible_clients_only")
    from services.client_lifecycle_service import mark_purge_eligible

    await mark_purge_eligible(db, resource_id.strip(), actor_id, actor_role=actor_role)
    await _audit_identity(
        action=AuditAction.IDENTITY_MARKED_PURGE_ELIGIBLE,
        actor_id=actor_id,
        actor_role=actor_role,
        identity_kind=k,
        resource_id=resource_id.strip(),
        client_id=resource_id.strip(),
    )


async def permanent_delete_preflight_identity(db, kind: str, resource_id: str) -> Tuple[bool, List[str]]:
    k = _norm_kind(kind)
    if k == IdentityKind.CLIENT.value:
        from services.client_lifecycle_service import permanent_delete_preflight

        return await permanent_delete_preflight(db, resource_id.strip())
    if k == IdentityKind.CONTRACTOR.value:
        from services.contractor_identity_lifecycle import contractor_permanent_delete_preflight

        return await contractor_permanent_delete_preflight(db, resource_id.strip())
    if k == IdentityKind.PORTAL_USER.value:
        from services.portal_user_lifecycle_service import permanent_delete_preflight as pu_preflight

        return await pu_preflight(db, resource_id.strip())
    return False, ["invalid_identity_kind"]


async def permanent_delete_identity(
    db,
    kind: str,
    resource_id: str,
    actor_id: str,
    *,
    actor_role: UserRole,
) -> None:
    k = _norm_kind(kind)
    cid = await resolve_client_id_for_identity(db, k, resource_id)
    if k == IdentityKind.CLIENT.value:
        from services.client_lifecycle_service import permanent_delete_client

        await permanent_delete_client(db, resource_id.strip(), actor_id, actor_role=actor_role)
    elif k == IdentityKind.CONTRACTOR.value:
        from services import contractor_service

        ok = await contractor_service.delete_contractor(resource_id.strip())
        if not ok:
            raise ValueError("contractor_not_found")
    elif k == IdentityKind.PORTAL_USER.value:
        from services.portal_user_lifecycle_service import permanent_delete_portal_user

        await permanent_delete_portal_user(db, resource_id.strip(), actor_id, actor_role=actor_role)
    else:
        raise ValueError("invalid_identity_kind")
    await _audit_identity(
        action=AuditAction.IDENTITY_DELETED,
        actor_id=actor_id,
        actor_role=actor_role,
        identity_kind=k,
        resource_id=resource_id.strip(),
        client_id=cid,
    )


def _client_lifecycle_label(doc: Dict[str, Any]) -> str:
    from services.client_lifecycle_service import derive_client_lifecycle_status

    return derive_client_lifecycle_status(doc)


def _contractor_lifecycle_label(doc: Dict[str, Any]) -> str:
    from services.contractor_service import LC_ARCHIVED, LC_SUSPENDED, normalize_lifecycle_status

    st = normalize_lifecycle_status(doc.get("status"))
    if st == LC_ARCHIVED:
        return ClientLifecycleStatus.ARCHIVED.value
    if st in (LC_SUSPENDED, "suspended"):
        return ClientLifecycleStatus.SUSPENDED.value
    if (doc.get("status") or "").strip().lower() == "active":
        return ClientLifecycleStatus.ACTIVE.value
    return ClientLifecycleStatus.PENDING_SETUP.value


def _portal_user_lifecycle_label(doc: Dict[str, Any]) -> str:
    if doc.get("is_deleted") is True:
        return ClientLifecycleStatus.ARCHIVED.value
    from models import UserStatus

    if doc.get("status") == UserStatus.DISABLED.value:
        return ClientLifecycleStatus.SUSPENDED.value
    return ClientLifecycleStatus.ACTIVE.value


async def list_unified_identities(
    db,
    *,
    kind_filter: Optional[str] = None,
    lifecycle_filter: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = 0,
    limit: int = 40,
    flags_filter: Optional[str] = None,
    include_hard_delete_eligibility: bool = False,
) -> Dict[str, Any]:
    """Merge recent rows from up to three collections (best-effort; not a full-text index)."""
    kf = _norm_kind(kind_filter) if kind_filter else None
    lf = (lifecycle_filter or "").strip().upper() or None
    ff = (flags_filter or "").strip().lower() or None
    qstrip = (q or "").strip()
    search_regex = {"$regex": re.escape(qstrip), "$options": "i"} if len(qstrip) >= 2 else None

    items: List[Dict[str, Any]] = []

    async def _push_client_rows() -> None:
        if kf and kf != IdentityKind.CLIENT.value:
            return
        match: Dict[str, Any] = {}
        if search_regex:
            match["$or"] = [
                {"customer_reference": search_regex},
                {"email": search_regex},
                {"full_name": search_regex},
            ]
        cur = db.clients.find(
            match if match else {},
            {
                "_id": 0,
                "client_id": 1,
                "email": 1,
                "full_name": 1,
                "client_lifecycle_status": 1,
                "is_deleted": 1,
                "subscription_status": 1,
                "onboarding_status": 1,
                "is_test_like": 1,
            },
        ).sort("updated_at", -1).limit(200)
        rows = await cur.to_list(200)
        for c in rows:
            label = _client_lifecycle_label(c)
            if lf and label != lf:
                continue
            if ff == "test_like" and not bool(c.get("is_test_like")):
                continue
            if ff == "live" and bool(c.get("is_test_like")):
                continue
            items.append(
                {
                    "kind": IdentityKind.CLIENT.value,
                    "id": c.get("client_id"),
                    "email": c.get("email"),
                    "name": c.get("full_name"),
                    "roles": ["CLIENT"],
                    "lifecycle_status": label,
                    "is_test_like": bool(c.get("is_test_like")),
                }
            )

    async def _push_contractor_rows() -> None:
        if ff in ("test_like", "live"):
            return
        if kf and kf != IdentityKind.CONTRACTOR.value:
            return
        match: Dict[str, Any] = {}
        if search_regex:
            match["$or"] = [
                {"email": search_regex},
                {"name": search_regex},
                {"company_name": search_regex},
                {"contractor_id": search_regex},
            ]
        cur = db.contractors.find(
            match if match else {},
            {"_id": 0, "contractor_id": 1, "email": 1, "name": 1, "company_name": 1, "status": 1},
        ).sort("updated_at", -1).limit(200)
        rows = await cur.to_list(200)
        for c in rows:
            label = _contractor_lifecycle_label(c)
            if lf and label != lf:
                continue
            nm = c.get("name") or c.get("company_name") or "—"
            items.append(
                {
                    "kind": IdentityKind.CONTRACTOR.value,
                    "id": c.get("contractor_id"),
                    "email": c.get("email"),
                    "name": nm,
                    "roles": ["CONTRACTOR"],
                    "lifecycle_status": label,
                }
            )

    async def _push_portal_rows() -> None:
        if kf and kf != IdentityKind.PORTAL_USER.value:
            return
        match: Dict[str, Any] = {}
        if search_regex:
            match["$or"] = [
                {"auth_email": search_regex},
                {"email": search_regex},
                {"portal_user_id": search_regex},
            ]
        cur = db.portal_users.find(
            match if match else {},
            {
                "_id": 0,
                "portal_user_id": 1,
                "auth_email": 1,
                "role": 1,
                "status": 1,
                "is_deleted": 1,
                "is_test_like": 1,
            },
        ).sort("_id", -1).limit(200)
        rows = await cur.to_list(200)
        for u in rows:
            label = _portal_user_lifecycle_label(u)
            if lf and label != lf:
                continue
            if ff == "test_like" and not bool(u.get("is_test_like")):
                continue
            if ff == "live" and bool(u.get("is_test_like")):
                continue
            role = (u.get("role") or "").upper()
            rlabels = []
            if role == UserRole.ROLE_TENANT.value:
                rlabels.append("TENANT")
            elif role in (UserRole.ROLE_CLIENT.value, UserRole.ROLE_CLIENT_ADMIN.value):
                rlabels.append("CLIENT")
            else:
                rlabels.append(role.replace("ROLE_", "") or "PORTAL")
            items.append(
                {
                    "kind": IdentityKind.PORTAL_USER.value,
                    "id": u.get("portal_user_id"),
                    "email": u.get("auth_email") or u.get("email"),
                    "name": u.get("auth_email") or u.get("email") or "—",
                    "roles": rlabels,
                    "lifecycle_status": label,
                    "is_test_like": bool(u.get("is_test_like")),
                }
            )

    await _push_client_rows()
    await _push_contractor_rows()
    await _push_portal_rows()

    items.sort(key=lambda x: (x.get("name") or ""))
    total = len(items)
    page = items[skip : skip + limit]

    if include_hard_delete_eligibility:
        from services.portal_user_lifecycle_service import permanent_delete_preflight as _pu_preflight

        for item in page:
            if item.get("kind") != IdentityKind.PORTAL_USER.value:
                continue
            pid = item.get("id")
            if not pid:
                continue
            ok, blockers = await _pu_preflight(db, str(pid))
            item["hard_delete_allowed"] = ok
            item["hard_delete_blockers"] = [] if ok else blockers

    return {"items": page, "total": total, "skip": skip, "limit": limit}


def identity_http_detail(exc: ValueError) -> Tuple[int, Any]:
    key = str(exc)
    if key.startswith("preflight_failed:"):
        blockers = [b for b in key.split(":", 1)[1].split(",") if b]
        return 400, {"message": "Permanent delete not allowed", "blockers": blockers}
    static = {
        "test_flag_portal_users_only": (400, "Test/dummy flag applies to portal_user identities only"),
        "owner_cannot_be_flagged_test_like": (403, "Owner accounts cannot be marked as test or dummy"),
        "invalid_identity_kind": (400, "Invalid identity kind (use client, contractor, portal_user)"),
        "purge_eligible_clients_only": (400, "Purge eligibility applies to client organisations only"),
        "contractor_not_found": (404, "Contractor not found"),
        "client_not_found": (404, "Client not found"),
        "user_not_found": (404, "User not found"),
        "already_archived": (400, "Already archived"),
        "not_archived": (400, "Not archived"),
        "already_suspended": (400, "Already suspended"),
        "not_suspended": (400, "Not suspended"),
        "client_archived_use_restore": (400, "Client is archived — restore before suspend/resume"),
        "archived_use_restore_first": (400, "Restore archived account before this action"),
        "cannot_suspend_self": (400, "Cannot suspend your own account"),
        "owner_cannot_be_suspended": (403, "Owner cannot be suspended"),
        "cannot_archive_self": (400, "Cannot archive your own account"),
        "owner_cannot_be_archived": (403, "Owner cannot be archived"),
        "last_active_admin": (400, "Cannot archive the last active admin"),
        "must_be_archived_first": (400, "Archive before marking purge eligible"),
    }
    if key in static:
        return static[key]
    return 400, key
