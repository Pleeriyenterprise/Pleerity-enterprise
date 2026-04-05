"""
Client (organisation) lifecycle: derive status, visibility filters, archive/restore,
purge eligibility, test-like heuristics, permanent-delete preflight (no billing/cascade deletes).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from models import (
    AuditAction,
    ClientLifecycleStatus,
    OnboardingStatus,
    SubscriptionStatus,
    UserRole,
)
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

# Collections that may not exist in all environments
_OPTIONAL_COLLECTIONS = (
    "risk_signals",
    "maintenance_issues",
    "maintenance_events",
    "tenant_requests",
    "tenant_messages",
    "message_logs",
    "reminder_item_state",
    "compliance_score_history",
    "property_score_daily",
    "score_events",
    "compliance_activity_log",
    "score_ledger_events",
    "client_feature_flags",
    "provisioning_status",
    "contractor_performance",
    "predictive_insights_cache",
    "automation_status",
    "assistant_conversations",
    "assistant_messages",
    "onboarding_email_queue",
    "communication_deliveries",
    "payments",
    "analytics_events",
    "lead_events",
    "lead_sequence_state",
    "lead_sequence_sends",
    "property_compliance_score_history",
    "reminder_evaluation_log",
    "asset_events",
)


async def _count(db, collection_name: str, query: Dict[str, Any]) -> int:
    try:
        coll = getattr(db, collection_name, None)
        if coll is None:
            return 0
        return await coll.count_documents(query)
    except Exception as e:
        logger.warning("client_lifecycle count failed %s: %s", collection_name, e)
        return 0


def default_active_client_match() -> Dict[str, Any]:
    """Exclude soft-deleted and archived / purge-queue clients from normal admin lists."""
    return {
        "$and": [
            {"$or": [{"is_deleted": {"$ne": True}}, {"is_deleted": {"$exists": False}}]},
            {
                "$or": [
                    {"client_lifecycle_status": {"$exists": False}},
                    {
                        "client_lifecycle_status": {
                            "$nin": [
                                ClientLifecycleStatus.ARCHIVED.value,
                                ClientLifecycleStatus.PURGE_ELIGIBLE.value,
                                ClientLifecycleStatus.SUSPENDED.value,
                            ]
                        }
                    },
                ]
            },
        ]
    }


def derive_client_lifecycle_status(client: Dict[str, Any]) -> str:
    """
    Derive display lifecycle when client_lifecycle_status is unset.
    Does not persist; use for API enrichment only unless caller writes back.
    """
    explicit = (client.get("client_lifecycle_status") or "").strip().upper()
    if explicit in {s.value for s in ClientLifecycleStatus}:
        return explicit

    if client.get("is_deleted") or explicit == ClientLifecycleStatus.ARCHIVED.value:
        return ClientLifecycleStatus.ARCHIVED.value

    pay_lc = (client.get("lifecycle_status") or "").strip().lower()
    ob = (client.get("onboarding_status") or "").strip().upper()
    sub = (client.get("subscription_status") or "").strip().upper()

    if ob == OnboardingStatus.PROVISIONED.value:
        if sub in (SubscriptionStatus.ACTIVE.value, "ACTIVE", "TRIALING", "trialing", "active"):
            return ClientLifecycleStatus.ACTIVE.value
        if sub == SubscriptionStatus.CANCELLED.value or (sub or "").lower() == "canceled":
            return ClientLifecycleStatus.SUSPENDED.value
        return ClientLifecycleStatus.PENDING_SETUP.value

    if ob in (OnboardingStatus.PROVISIONING.value,):
        return ClientLifecycleStatus.PENDING_SETUP.value

    if ob == OnboardingStatus.INTAKE_PENDING.value or pay_lc in ("pending_payment", "abandoned"):
        return ClientLifecycleStatus.LEAD.value if ob == OnboardingStatus.INTAKE_PENDING.value else ClientLifecycleStatus.PENDING_SETUP.value

    return ClientLifecycleStatus.PENDING_SETUP.value


def should_skip_persist_operational_lifecycle(doc: Optional[Dict[str, Any]]) -> bool:
    if not doc:
        return True
    if doc.get("is_deleted"):
        return True
    st = (doc.get("client_lifecycle_status") or "").strip().upper()
    return st in (ClientLifecycleStatus.ARCHIVED.value, ClientLifecycleStatus.PURGE_ELIGIBLE.value)


def operational_client_lifecycle_to_persist(doc: Dict[str, Any]) -> str:
    """Recompute enterprise lifecycle from onboarding/subscription/payment fields (ignore stored status)."""
    shadow = {**doc, "client_lifecycle_status": None, "is_deleted": False}
    return derive_client_lifecycle_status(shadow)


async def persist_operational_client_lifecycle_if_needed(db, client_id: str) -> None:
    """
    Persist client_lifecycle_status from operational state when the client is not archived/purge-queue.
    Idempotent; safe after subscription/onboarding writes.
    """
    try:
        doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if should_skip_persist_operational_lifecycle(doc):
            return
        target = operational_client_lifecycle_to_persist(doc)
        current = (doc.get("client_lifecycle_status") or "").strip().upper()
        if current == target:
            return
        now = datetime.now(timezone.utc)
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": {"client_lifecycle_status": target, "updated_at": now}},
        )
    except Exception as e:
        logger.warning("persist_operational_client_lifecycle_if_needed failed client_id=%s: %s", client_id, e)


async def get_latest_provisioning_job(db, client_id: str) -> Optional[Dict[str, Any]]:
    cur = db.provisioning_jobs.find({"client_id": client_id}, {"_id": 0}).sort("updated_at", -1).limit(1)
    rows = await cur.to_list(1)
    return rows[0] if rows else None


async def latest_provisioning_jobs_for_clients(db, client_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Latest provisioning job per client_id (by updated_at desc). Empty ids → {}."""
    if not client_ids:
        return {}
    try:
        pipeline = [
            {"$match": {"client_id": {"$in": list(dict.fromkeys(client_ids))}}},
            {"$sort": {"updated_at": -1}},
            {"$group": {"_id": "$client_id", "doc": {"$first": "$$ROOT"}}},
        ]
        out: Dict[str, Dict[str, Any]] = {}
        async for row in db.provisioning_jobs.aggregate(pipeline):
            cid = row.get("_id")
            d = row.get("doc") or {}
            if cid:
                out[cid] = d
        return out
    except Exception as e:
        logger.warning("latest_provisioning_jobs_for_clients failed: %s", e)
        return {}


async def permanent_delete_preflight(db, client_id: str) -> Tuple[bool, List[str]]:
    """Return (allowed, blockers). Never mutates data."""
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return False, ["client_not_found"]

    blockers: List[str] = []

    st_lc = (client.get("client_lifecycle_status") or "").strip().upper()
    if st_lc not in (
        ClientLifecycleStatus.ARCHIVED.value,
        ClientLifecycleStatus.PURGE_ELIGIBLE.value,
    ):
        blockers.append("client_not_archived_or_purge_eligible")

    if (client.get("stripe_customer_id") or "").strip():
        blockers.append("stripe_customer_id_present")
    if (client.get("stripe_subscription_id") or "").strip():
        blockers.append("stripe_subscription_id_present")
    sub = (client.get("subscription_status") or "").strip().upper()
    if sub in (SubscriptionStatus.ACTIVE.value, "TRIALING", "ACTIVE"):
        blockers.append("subscription_active_or_trialing")

    pairs = [
        ("invoices", {"client_id": client_id}),
        ("stripe_checkout_invoices", {"client_id": client_id}),
        ("properties", {"client_id": client_id}),
        ("requirements", {"client_id": client_id}),
        ("documents", {"client_id": client_id}),
        ("work_orders", {"client_id": client_id}),
        ("portal_users", {"client_id": client_id}),
        ("provisioning_jobs", {"client_id": client_id}),
        ("client_billing", {"client_id": client_id}),
        ("contractors", {"client_id": client_id}),
        ("orders", {"client_id": client_id}),
        ("compliance_evidence_pack_jobs", {"client_id": client_id}),
        ("client_read_api_keys", {"client_id": client_id}),
        ("product_analytics_events", {"client_id": client_id}),
    ]
    for name, q in pairs:
        n = await _count(db, name, q)
        if n > 0:
            blockers.append(f"{name}_count:{n}")

    n_audit = await _count(db, "audit_logs", {"client_id": client_id})
    if n_audit > 0:
        blockers.append(f"audit_logs_count:{n_audit}")

    for name in _OPTIONAL_COLLECTIONS:
        n = await _count(db, name, {"client_id": client_id})
        if n > 0:
            blockers.append(f"{name}_count:{n}")

    return len(blockers) == 0, blockers


def heuristics_test_like(client: Dict[str, Any]) -> bool:
    email = (client.get("email") or "").lower()
    name = (client.get("full_name") or "").lower()
    company = (client.get("company_name") or "").lower()
    if not email:
        return False
    if re.search(r"@example\.(com|org|net|test)\b", email):
        return True
    if email.endswith("@test.com") or email.startswith("test+"):
        return True
    if email in {"fake@pleerity.test", "test@test.com"}:
        return True
    if name in {"test user", "test", "asdf", "fake name"} or company in {"test co", "test company"}:
        return True
    return False


async def archive_client(
    db,
    client_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
    archive_reason: Optional[str] = None,
) -> None:
    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise ValueError("client_not_found")
    if doc.get("is_deleted") or doc.get("client_lifecycle_status") == ClientLifecycleStatus.ARCHIVED.value:
        raise ValueError("already_archived")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "client_lifecycle_status": ClientLifecycleStatus.ARCHIVED.value,
                "is_deleted": True,
                "archived_at": now_iso,
                "archived_by": actor_portal_user_id,
                "archive_reason": (archive_reason or "").strip() or None,
                "purge_eligible": False,
                "updated_at": now,
            }
        },
    )

    await create_audit_log(
        action=AuditAction.CLIENT_ARCHIVED,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        metadata={"archive_reason": archive_reason, "email": doc.get("email")},
    )


async def restore_client(
    db,
    client_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise ValueError("client_not_found")
    st = (doc.get("client_lifecycle_status") or "").upper()
    if not doc.get("is_deleted") and st not in (
        ClientLifecycleStatus.ARCHIVED.value,
        ClientLifecycleStatus.PURGE_ELIGIBLE.value,
    ):
        raise ValueError("not_archived")

    now = datetime.now(timezone.utc)
    # Restore to derived operational state (active funnel)
    derived = derive_client_lifecycle_status({**doc, "client_lifecycle_status": None, "is_deleted": False})
    if derived in (ClientLifecycleStatus.ARCHIVED.value, ClientLifecycleStatus.PURGE_ELIGIBLE.value):
        derived = ClientLifecycleStatus.PENDING_SETUP.value

    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "client_lifecycle_status": derived,
                "is_deleted": False,
                "purge_eligible": False,
                "updated_at": now,
            },
            "$unset": {
                "archived_at": "",
                "archived_by": "",
                "archive_reason": "",
                "purge_checked_at": "",
            },
        },
    )

    await create_audit_log(
        action=AuditAction.CLIENT_RESTORED,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        metadata={"restored_to_status": derived},
    )


async def mark_purge_eligible(
    db,
    client_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise ValueError("client_not_found")
    if doc.get("client_lifecycle_status") != ClientLifecycleStatus.ARCHIVED.value and not doc.get("is_deleted"):
        raise ValueError("must_be_archived_first")

    now = datetime.now(timezone.utc)
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "client_lifecycle_status": ClientLifecycleStatus.PURGE_ELIGIBLE.value,
                "purge_eligible": True,
                "purge_checked_at": now.isoformat(),
                "updated_at": now,
            }
        },
    )
    await create_audit_log(
        action=AuditAction.CLIENT_MARKED_PURGE_ELIGIBLE,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        metadata={},
    )


async def flag_test_like_client(
    db,
    client_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
    duplicate_of_client_id: Optional[str] = None,
) -> None:
    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise ValueError("client_not_found")
    now = datetime.now(timezone.utc)
    upd: Dict[str, Any] = {
        "is_test_like": True,
        "updated_at": now,
    }
    if duplicate_of_client_id:
        upd["duplicate_of_client_id"] = duplicate_of_client_id.strip()
    await db.clients.update_one({"client_id": client_id}, {"$set": upd})
    await create_audit_log(
        action=AuditAction.CLIENT_FLAGGED_TEST_LIKE,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        metadata={"duplicate_of_client_id": duplicate_of_client_id},
    )


async def permanent_delete_client(
    db,
    client_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    allowed, blockers = await permanent_delete_preflight(db, client_id)
    if not allowed:
        raise ValueError("preflight_failed:" + ",".join(blockers))

    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise ValueError("client_not_found")

    res = await db.clients.delete_one({"client_id": client_id})
    if res.deleted_count != 1:
        raise ValueError("client_not_found")

    now = datetime.now(timezone.utc).isoformat()
    await create_audit_log(
        action=AuditAction.CLIENT_DELETED_PERMANENTLY,
        actor_role=actor_role,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        metadata={
            "email": doc.get("email"),
            "purged_at": now,
            "purged_by": actor_portal_user_id,
            "prior_client_lifecycle_status": (doc.get("client_lifecycle_status") or "").strip().upper() or None,
        },
    )


async def suspend_client_org(
    db,
    client_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise ValueError("client_not_found")
    st = (doc.get("client_lifecycle_status") or "").strip().upper()
    if st in (ClientLifecycleStatus.ARCHIVED.value, ClientLifecycleStatus.PURGE_ELIGIBLE.value):
        raise ValueError("client_archived_use_restore")
    if st == ClientLifecycleStatus.SUSPENDED.value:
        raise ValueError("already_suspended")
    now = datetime.now(timezone.utc)
    await db.clients.update_one(
        {"client_id": client_id},
        {"$set": {"client_lifecycle_status": ClientLifecycleStatus.SUSPENDED.value, "updated_at": now}},
    )


async def resume_client_org(
    db,
    client_id: str,
    actor_portal_user_id: str,
    *,
    actor_role: UserRole,
) -> None:
    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise ValueError("client_not_found")
    st = (doc.get("client_lifecycle_status") or "").strip().upper()
    if st != ClientLifecycleStatus.SUSPENDED.value:
        raise ValueError("not_suspended")
    shadow = {**doc, "client_lifecycle_status": None}
    target = operational_client_lifecycle_to_persist(shadow)
    now = datetime.now(timezone.utc)
    await db.clients.update_one(
        {"client_id": client_id},
        {"$set": {"client_lifecycle_status": target, "updated_at": now}},
    )


def _lifecycle_http_detail(exc: ValueError) -> Tuple[int, Any]:
    key = str(exc)
    if key.startswith("preflight_failed:"):
        blockers = [b for b in key.split(":", 1)[1].split(",") if b]
        return 400, {"message": "Permanent delete not allowed", "blockers": blockers}
    static = {
        "client_not_found": (404, "Client not found"),
        "already_archived": (400, "Client is already archived"),
        "not_archived": (400, "Client is not archived"),
        "must_be_archived_first": (400, "Mark archive before purge eligibility"),
    }
    if key in static:
        return static[key]
    return 400, key


# --- Housekeeping (called from job_runner) ---


async def job_archive_stale_pending_clients(
    db,
    *,
    stale_days: int = 45,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Archive LEAD / PENDING_SETUP clients with no Stripe, no properties, older than threshold."""
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - stale_days * 86400
    query: Dict[str, Any] = {
        "$and": [
            {
                "$or": [
                    {"client_lifecycle_status": {"$in": [ClientLifecycleStatus.LEAD.value, ClientLifecycleStatus.PENDING_SETUP.value]}},
                    {"client_lifecycle_status": {"$exists": False}},
                ]
            },
            {"$or": [{"is_deleted": {"$ne": True}}, {"is_deleted": {"$exists": False}}]},
            {
                "$or": [
                    {"stripe_customer_id": {"$in": [None, ""]}},
                    {"stripe_customer_id": {"$exists": False}},
                ]
            },
            {
                "$or": [
                    {"stripe_subscription_id": {"$in": [None, ""]}},
                    {"stripe_subscription_id": {"$exists": False}},
                ]
            },
        ]
    }
    cursor = db.clients.find(query, {"_id": 0, "client_id": 1, "created_at": 1})
    candidates = await cursor.to_list(2000)
    archived = 0
    skipped = 0
    for c in candidates:
        cid = c.get("client_id")
        if not cid:
            skipped += 1
            continue
        created = c.get("created_at")
        if isinstance(created, str):
            try:
                created_ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
            except Exception:
                skipped += 1
                continue
        elif isinstance(created, datetime):
            created_ts = created.timestamp() if created.tzinfo else created.replace(tzinfo=timezone.utc).timestamp()
        else:
            skipped += 1
            continue
        if created_ts > cutoff:
            continue
        props = await _count(db, "properties", {"client_id": cid})
        if props > 0:
            skipped += 1
            continue
        pu = await _count(db, "portal_users", {"client_id": cid})
        if pu > 0:
            skipped += 1
            continue
        if dry_run:
            archived += 1
            continue
        await db.clients.update_one(
            {"client_id": cid},
            {
                "$set": {
                    "client_lifecycle_status": ClientLifecycleStatus.ARCHIVED.value,
                    "is_deleted": True,
                    "archived_at": now.isoformat(),
                    "archived_by": "SYSTEM_HOUSEKEEPING",
                    "archive_reason": f"auto_stale_{stale_days}d",
                    "updated_at": now,
                }
            },
        )
        await create_audit_log(
            action=AuditAction.CLIENT_ARCHIVED,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id="SYSTEM_HOUSEKEEPING",
            client_id=cid,
            resource_type="client",
            resource_id=cid,
            metadata={"source": "job_archive_stale_pending_clients", "stale_days": stale_days},
        )
        archived += 1
    return {"archived": archived, "skipped": skipped, "dry_run": dry_run}


async def job_evaluate_purge_eligibility(
    db,
    *,
    archived_min_days: int = 60,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Set PURGE_ELIGIBLE when archived long enough and preflight would pass."""
    now = datetime.now(timezone.utc)
    cursor = db.clients.find(
        {
            "client_lifecycle_status": ClientLifecycleStatus.ARCHIVED.value,
            "is_deleted": True,
            "purge_eligible": {"$ne": True},
        },
        {"_id": 0, "client_id": 1, "archived_at": 1},
    )
    rows = await cursor.to_list(2000)
    marked = 0
    for c in rows:
        cid = c.get("client_id")
        if not cid:
            continue
        aa = c.get("archived_at")
        if isinstance(aa, str):
            try:
                at = datetime.fromisoformat(aa.replace("Z", "+00:00"))
            except Exception:
                continue
        elif isinstance(aa, datetime):
            at = aa
        else:
            continue
        if (now - at).days < archived_min_days:
            continue
        ok, _ = await permanent_delete_preflight(db, cid)
        if not ok:
            await db.clients.update_one(
                {"client_id": cid},
                {"$set": {"purge_checked_at": now.isoformat(), "updated_at": now}},
            )
            continue
        if dry_run:
            marked += 1
            continue
        await db.clients.update_one(
            {"client_id": cid},
            {
                "$set": {
                    "client_lifecycle_status": ClientLifecycleStatus.PURGE_ELIGIBLE.value,
                    "purge_eligible": True,
                    "purge_checked_at": now.isoformat(),
                    "updated_at": now,
                }
            },
        )
        await create_audit_log(
            action=AuditAction.CLIENT_MARKED_PURGE_ELIGIBLE,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id="SYSTEM_HOUSEKEEPING",
            client_id=cid,
            resource_type="client",
            resource_id=cid,
            metadata={"source": "job_evaluate_purge_eligibility"},
        )
        marked += 1
    return {"marked_purge_eligible": marked, "dry_run": dry_run}


async def job_flag_test_like_records(db, *, limit: int = 500, dry_run: bool = False) -> Dict[str, Any]:
    """Flag obvious test-like clients; never deletes."""
    cursor = db.clients.find(
        {"is_test_like": {"$ne": True}},
        {"_id": 0},
    ).limit(limit)
    rows = await cursor.to_list(limit)
    flagged = 0
    for c in rows:
        if not heuristics_test_like(c):
            continue
        cid = c.get("client_id")
        if not cid:
            continue
        if dry_run:
            flagged += 1
            continue
        await db.clients.update_one(
            {"client_id": cid},
            {"$set": {"is_test_like": True, "updated_at": datetime.now(timezone.utc)}},
        )
        await create_audit_log(
            action=AuditAction.CLIENT_FLAGGED_TEST_LIKE,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id="SYSTEM_HEURISTICS",
            client_id=cid,
            resource_type="client",
            resource_id=cid,
            metadata={"source": "job_flag_test_like_records"},
        )
        flagged += 1
    return {"flagged": flagged, "dry_run": dry_run}
