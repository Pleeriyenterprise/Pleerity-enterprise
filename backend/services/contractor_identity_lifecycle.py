"""
Contractor identity lifecycle: dependency-safe hard delete, archive/restore for portal and assignment gates.
Contractor profile data remains in `contractors`; this module adds governance operations.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from models import UserRole
from services.contractor_service import LC_ARCHIVED, get_contractor, normalize_lifecycle_status

logger = logging.getLogger(__name__)

_OPTIONAL = (
    "contractor_performance",
    "contractor_ratings",
    "tenant_requests",
)


async def _count(db, collection_name: str, query: Dict[str, Any]) -> int:
    try:
        coll = getattr(db, collection_name, None)
        if coll is None:
            return 0
        return await coll.count_documents(query)
    except Exception as e:
        logger.warning("contractor_identity count failed %s: %s", collection_name, e)
        return 0


async def contractor_permanent_delete_preflight(db, contractor_id: str) -> Tuple[bool, List[str]]:
    """Return (allowed, blockers). Never deletes."""
    cid = (contractor_id or "").strip()
    if not cid:
        return False, ["contractor_id_required"]
    doc = await db.contractors.find_one({"contractor_id": cid}, {"_id": 0, "contractor_id": 1})
    if not doc:
        return False, ["contractor_not_found"]

    blockers: List[str] = []
    pairs = [
        ("work_orders", {"contractor_id": cid}),
        ("invoices", {"contractor_id": cid}),
        ("documents", {"linked_contractor_id": cid}),
    ]
    for name, q in pairs:
        n = await _count(db, name, q)
        if n > 0:
            blockers.append(f"{name}_count:{n}")

    n_audit = await _count(db, "audit_logs", {"resource_id": cid})
    if n_audit > 0:
        blockers.append(f"audit_logs_count:{n_audit}")

    n_acct = await _count(db, "contractor_portal_accounts", {"contractor_id": cid})
    if n_acct > 0:
        blockers.append(f"contractor_portal_accounts_count:{n_acct}")

    for name in _OPTIONAL:
        n = await _count(db, name, {"contractor_id": cid})
        if n > 0:
            blockers.append(f"{name}_count:{n}")

    return len(blockers) == 0, blockers


async def archive_contractor_identity(
    db,
    contractor_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    doc = await get_contractor((contractor_id or "").strip())
    if not doc:
        raise ValueError("contractor_not_found")
    st = normalize_lifecycle_status(doc.get("status"))
    if st == LC_ARCHIVED:
        raise ValueError("already_archived")
    prev = (doc.get("status") or "").strip() or "approved"
    now = datetime.now(timezone.utc)
    await db.contractors.update_one(
        {"contractor_id": contractor_id.strip()},
        {
            "$set": {
                "status": LC_ARCHIVED,
                "archived_at": now.isoformat(),
                "archived_by": actor_portal_user_id,
                "pre_archive_contractor_status": prev,
                "updated_at": now,
            }
        },
    )


async def restore_contractor_identity(
    db,
    contractor_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    doc = await get_contractor((contractor_id or "").strip())
    if not doc:
        raise ValueError("contractor_not_found")
    st = normalize_lifecycle_status(doc.get("status"))
    if st != LC_ARCHIVED:
        raise ValueError("not_archived")
    prev = (doc.get("pre_archive_contractor_status") or "").strip() or "approved"
    now = datetime.now(timezone.utc)
    await db.contractors.update_one(
        {"contractor_id": contractor_id.strip()},
        {
            "$set": {"status": prev, "updated_at": now},
            "$unset": {"archived_at": "", "archived_by": "", "pre_archive_contractor_status": ""},
        },
    )


async def suspend_contractor_identity(
    db,
    contractor_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    doc = await get_contractor((contractor_id or "").strip())
    if not doc:
        raise ValueError("contractor_not_found")
    st = normalize_lifecycle_status(doc.get("status"))
    if st == LC_ARCHIVED:
        raise ValueError("archived_use_restore_first")
    from services.contractor_service import LC_SUSPENDED

    prev = (doc.get("status") or "").strip() or "approved"
    now = datetime.now(timezone.utc)
    await db.contractors.update_one(
        {"contractor_id": contractor_id.strip()},
        {
            "$set": {
                "status": LC_SUSPENDED,
                "pre_suspend_contractor_status": prev,
                "updated_at": now,
            }
        },
    )


async def resume_contractor_identity(
    db,
    contractor_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    doc = await get_contractor((contractor_id or "").strip())
    if not doc:
        raise ValueError("contractor_not_found")
    st = normalize_lifecycle_status(doc.get("status"))
    from services.contractor_service import LC_SUSPENDED

    if st != LC_SUSPENDED and (doc.get("status") or "").strip().lower() != "suspended":
        raise ValueError("not_suspended")
    target = (doc.get("pre_suspend_contractor_status") or "").strip() or "approved"
    now = datetime.now(timezone.utc)
    await db.contractors.update_one(
        {"contractor_id": contractor_id.strip()},
        {
            "$set": {"status": target, "updated_at": now},
            "$unset": {"pre_suspend_contractor_status": ""},
        },
    )
