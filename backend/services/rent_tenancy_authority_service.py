"""
Tenancy authority for Rent Operations — Property → Tenancy → Tenant(s) → Schedule → Ledger → Payment.

Bounded operational model; not accounting. Preserves historical lineage on move-out / replacement.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database

COLLECTION_TENANCIES = "property_tenancies"
TENANCY_STATUS_ACTIVE = "active"
TENANCY_STATUS_ENDING_SOON = "ending_soon"
TENANCY_STATUS_MOVED_OUT = "moved_out"
TENANCY_STATUS_ARCHIVED = "archived"
DEFAULT_RENT_TYPE = "residential_rent"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tenant_display_from_assignments(assignments: List[Dict[str, Any]], tenants_by_id: Dict[str, Dict]) -> str:
    names: List[str] = []
    for a in assignments:
        t = tenants_by_id.get(a.get("tenant_id") or "")
        if not t:
            continue
        label = (t.get("full_name") or t.get("name") or t.get("auth_email") or "").strip()
        if label:
            names.append(label)
    return ", ".join(names) if names else "Tenant"


async def _load_property(db, client_id: str, property_id: str) -> Dict[str, Any]:
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    if not prop:
        raise ValueError("PROPERTY_NOT_FOUND")
    return prop


async def list_property_tenancies(
    client_id: str,
    property_id: str,
    *,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    await _load_property(database.get_db(), client_id, property_id)
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id, "property_id": property_id}
    if active_only:
        q["status"] = {"$in": [TENANCY_STATUS_ACTIVE, TENANCY_STATUS_ENDING_SOON]}
    rows = await db[COLLECTION_TENANCIES].find(q, {"_id": 0}).sort("started_at", -1).to_list(50)
    return rows


async def get_tenancy(tenancy_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COLLECTION_TENANCIES].find_one(
        {"tenancy_id": tenancy_id, "client_id": client_id},
        {"_id": 0},
    )


async def resolve_or_create_active_tenancy(
    client_id: str,
    property_id: str,
    *,
    tenant_ids: Optional[List[str]] = None,
    tenant_display_name: Optional[str] = None,
    rent_tracking_enabled: bool = False,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return active tenancy for property or create one from tenant assignments."""
    db = database.get_db()
    await _load_property(db, client_id, property_id)

    existing = await db[COLLECTION_TENANCIES].find_one(
        {
            "client_id": client_id,
            "property_id": property_id,
            "status": {"$in": [TENANCY_STATUS_ACTIVE, TENANCY_STATUS_ENDING_SOON]},
        },
        {"_id": 0},
    )
    if existing:
        if rent_tracking_enabled and not existing.get("rent_tracking_enabled"):
            await db[COLLECTION_TENANCIES].update_one(
                {"tenancy_id": existing["tenancy_id"]},
                {"$set": {"rent_tracking_enabled": True, "updated_at": _now_iso()}},
            )
            existing["rent_tracking_enabled"] = True
        return existing

    display = (tenant_display_name or "").strip()
    resolved_tenant_ids: List[str] = list(tenant_ids or [])
    if not display or not resolved_tenant_ids:
        tenants = await db.portal_users.find(
            {"client_id": client_id, "role": "ROLE_TENANT"},
            {"_id": 0, "password_hash": 0},
        ).to_list(200)
        tenant_map = {t["portal_user_id"]: t for t in tenants}
        assignments = await db.tenant_assignments.find(
            {"property_id": property_id, "tenant_id": {"$in": list(tenant_map.keys())}},
            {"_id": 0},
        ).to_list(50)
        resolved_tenant_ids = [a["tenant_id"] for a in assignments]
        if not display:
            display = _tenant_display_from_assignments(assignments, tenant_map)

    if not display:
        display = "Occupancy tenant"

    tenancy_id = f"pty_{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    doc = {
        "tenancy_id": tenancy_id,
        "client_id": client_id,
        "property_id": property_id,
        "tenant_ids": resolved_tenant_ids,
        "tenant_display_name": display,
        "status": TENANCY_STATUS_ACTIVE,
        "rent_tracking_enabled": rent_tracking_enabled,
        "rent_type": DEFAULT_RENT_TYPE,
        "lineage_parent_tenancy_id": None,
        "started_at": now,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
        "created_by": actor_id,
    }
    await db[COLLECTION_TENANCIES].insert_one(doc)
    return doc


async def close_tenancy_rent_lineage(
    tenancy_id: str,
    client_id: str,
    *,
    status: str = TENANCY_STATUS_MOVED_OUT,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Moved-out: close active schedules; preserve ledger/payment history."""
    db = database.get_db()
    tenancy = await get_tenancy(tenancy_id, client_id)
    if not tenancy:
        raise ValueError("TENANCY_NOT_FOUND")

    now = _now_iso()
    await db[COLLECTION_TENANCIES].update_one(
        {"tenancy_id": tenancy_id, "client_id": client_id},
        {
            "$set": {
                "status": status,
                "ended_at": now,
                "rent_tracking_enabled": False,
                "updated_at": now,
                "updated_by": actor_id,
            }
        },
    )

    await db.rent_schedules.update_many(
        {
            "client_id": client_id,
            "tenancy_id": tenancy_id,
            "is_active": True,
        },
        {"$set": {"is_active": False, "closed_reason": "tenancy_moved_out", "updated_at": now}},
    )
    tenancy["status"] = status
    tenancy["ended_at"] = now
    return tenancy


async def create_replacement_tenancy(
    client_id: str,
    property_id: str,
    parent_tenancy_id: str,
    *,
    tenant_ids: Optional[List[str]] = None,
    tenant_display_name: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """New tenancy lineage after move-out; does not mutate historical payments."""
    parent = await get_tenancy(parent_tenancy_id, client_id)
    if not parent or parent.get("property_id") != property_id:
        raise ValueError("TENANCY_LINEAGE_INVALID")

    if parent.get("status") not in (TENANCY_STATUS_MOVED_OUT, TENANCY_STATUS_ARCHIVED):
        await close_tenancy_rent_lineage(parent_tenancy_id, client_id, actor_id=actor_id)

    db = database.get_db()
    tenancy_id = f"pty_{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    display = (tenant_display_name or parent.get("tenant_display_name") or "Tenant").strip()
    doc = {
        "tenancy_id": tenancy_id,
        "client_id": client_id,
        "property_id": property_id,
        "tenant_ids": tenant_ids if tenant_ids is not None else parent.get("tenant_ids") or [],
        "tenant_display_name": display,
        "status": TENANCY_STATUS_ACTIVE,
        "rent_tracking_enabled": False,
        "rent_type": parent.get("rent_type") or DEFAULT_RENT_TYPE,
        "lineage_parent_tenancy_id": parent_tenancy_id,
        "started_at": now,
        "ended_at": None,
        "created_at": now,
        "updated_at": now,
        "created_by": actor_id,
    }
    await db[COLLECTION_TENANCIES].insert_one(doc)
    return doc


async def validate_schedule_authority(
    client_id: str,
    body: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], bool]:
    """
    Validate schedule creation authority.
    Returns (property, tenancy_or_synthetic, is_external_payer).
    """
    property_id = body["property_id"]
    db = database.get_db()
    prop = await _load_property(db, client_id, property_id)

    is_external = bool(body.get("is_external_payer"))
    external_name = (body.get("external_payer_name") or "").strip()

    if is_external:
        if not external_name:
            raise ValueError("EXTERNAL_PAYER_NAME_REQUIRED")
        synthetic = {
            "tenancy_id": f"ext_{property_id}_{uuid.uuid4().hex[:8]}",
            "client_id": client_id,
            "property_id": property_id,
            "tenant_display_name": external_name,
            "is_external_payer": True,
            "status": TENANCY_STATUS_ACTIVE,
        }
        return prop, synthetic, True

    tenancy_id = body.get("tenancy_id")
    if not tenancy_id:
        raise ValueError("TENANCY_ID_REQUIRED")

    tenancy = await get_tenancy(tenancy_id, client_id)
    if not tenancy or tenancy.get("property_id") != property_id:
        raise ValueError("TENANCY_NOT_FOUND")
    if tenancy.get("status") in (TENANCY_STATUS_MOVED_OUT, TENANCY_STATUS_ARCHIVED):
        raise ValueError("TENANCY_NOT_ACTIVE")
    return prop, tenancy, False


async def assert_payment_authority(
    client_id: str,
    *,
    ledger_id: Optional[str] = None,
    property_id: Optional[str] = None,
    tenancy_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Ensure payment has explicit property + tenancy + ledger context."""
    db = database.get_db()
    if ledger_id:
        ledger = await db.rent_ledger_periods.find_one(
            {"ledger_id": ledger_id, "client_id": client_id, "is_deleted": {"$ne": True}},
            {"_id": 0},
        )
        if not ledger:
            raise ValueError("LEDGER_NOT_FOUND")
        return ledger

    if not property_id or not tenancy_id:
        raise ValueError("PAYMENT_AUTHORITY_INCOMPLETE")
    await _load_property(db, client_id, property_id)
    tenancy = await get_tenancy(tenancy_id, client_id)
    if not tenancy or tenancy.get("property_id") != property_id:
        raise ValueError("TENANCY_NOT_FOUND")
    raise ValueError("LEDGER_ID_REQUIRED")
