"""
Bounded rent arrears projection into Today and Command Centre.

Does not replace unified task prioritisation — appends operational rent attention when RENT_OPERATIONS is on.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import database
from models.rent_operations import RentLedgerStatus
from services.ops_compliance_feature_flags import RENT_OPERATIONS, get_effective_flags

SOURCE_RENT_OPS = "rent_operations"
MAX_RENT_TODAY_ITEMS = 12


def _ledger_payable(row: Dict[str, Any]) -> bool:
    if (row.get("status") or "") in (RentLedgerStatus.PAID.value, RentLedgerStatus.WAIVED.value):
        return False
    return int(row.get("outstanding_balance_minor") or 0) > 0


def _rent_task_from_ledger(row: Dict[str, Any]) -> Dict[str, Any]:
    ledger_id = row["ledger_id"]
    property_id = row.get("property_id")
    outstanding = int(row.get("outstanding_balance_minor") or 0)
    legacy = row.get("tenancy_id") is None
    title = f"Rent overdue — {row.get('tenant_name') or 'Tenant'}"
    if legacy:
        title = f"Rent overdue (legacy) — {row.get('tenant_name') or 'Tenant'}"
    route = f"/operations/rent?property_id={property_id}&tab=attention"
    return {
        "id": f"rent_ledger_{ledger_id}",
        "task_id": f"rent_ledger_{ledger_id}",
        "title": title,
        "description": (
            f"{row.get('period_key')} due {row.get('due_date')} — "
            f"£{outstanding / 100:.2f} outstanding"
        ),
        "section": "urgent",
        "source_type": SOURCE_RENT_OPS,
        "source_id": ledger_id,
        "source_entity_type": "rent_ledger_period",
        "source_entity_id": ledger_id,
        "property_id": property_id,
        "tenancy_id": row.get("tenancy_id"),
        "ledger_id": ledger_id,
        "urgency_level": "high" if row.get("is_overdue") else "medium",
        "primary_action_type": "record_rent_payment",
        "primary_action_label": "Record payment",
        "primary_action_url": f"/operations/rent?property_id={property_id}&tab=ledger&ledger_id={ledger_id}",
        "metadata": {
            "rent_ledger_id": ledger_id,
            "legacy_rent_authority": legacy,
            "outstanding_balance_minor": outstanding,
            "status": row.get("status"),
        },
        "business_actions": [
            {
                "label": "Record payment",
                "route": f"/operations/rent?property_id={property_id}&tab=ledger&ledger_id={ledger_id}",
                "intent": "record_rent_payment",
                "primary": True,
            }
        ],
        "visibility_actions": [],
    }


async def list_rent_attention_tasks(
    client_id: str,
    *,
    property_id_filter: Optional[str] = None,
    limit: int = MAX_RENT_TODAY_ITEMS,
) -> List[Dict[str, Any]]:
    flags = await get_effective_flags(client_id)
    if not flags.get(RENT_OPERATIONS):
        return []

    db = database.get_db()
    q: Dict[str, Any] = {
        "client_id": client_id,
        "is_deleted": {"$ne": True},
        "is_overdue": True,
        "status": {
            "$nin": [RentLedgerStatus.PAID.value, RentLedgerStatus.WAIVED.value],
        },
    }
    if property_id_filter:
        q["property_id"] = property_id_filter

    rows = (
        await db.rent_ledger_periods.find(q, {"_id": 0})
        .sort("due_date", 1)
        .limit(limit * 2)
        .to_list(limit * 2)
    )
    tasks: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not _ledger_payable(row):
            continue
        lid = row["ledger_id"]
        if lid in seen:
            continue
        seen.add(lid)
        tasks.append(_rent_task_from_ledger(row))
        if len(tasks) >= limit:
            break
    return tasks


def merge_rent_into_today_payload(
    payload: Dict[str, Any],
    rent_tasks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not rent_tasks:
        return payload

    flat_items_included = payload.get("flat_items_included") is True
    items = list(payload.get("items") or []) if flat_items_included else []
    tasks_root = payload.get("tasks") or {}
    urgent = list(tasks_root.get("urgent") or [])
    existing_ids = {i.get("id") for i in items}
    existing_urgent_ids = {t.get("id") for t in urgent}

    for t in rent_tasks:
        tid = t["id"]
        if tid not in existing_urgent_ids:
            urgent.append(t)
            existing_urgent_ids.add(tid)
        if flat_items_included and tid not in existing_ids:
            items.append(
                {
                    "id": tid,
                    "section": "urgent",
                    "title": t.get("title"),
                    "description": t.get("description"),
                    "property_id": t.get("property_id"),
                    "task": t,
                    "business_actions": t.get("business_actions") or [],
                    "visibility_actions": [],
                }
            )
            existing_ids.add(tid)

    tasks_root["urgent"] = urgent
    payload["tasks"] = tasks_root
    if flat_items_included:
        payload["items"] = items
    else:
        payload.setdefault("items", [])
    payload["rent_attention_count"] = len(rent_tasks)
    return payload


def append_rent_to_command_center_urgent(
    urgent_actions: List[Dict[str, Any]],
    rent_tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not rent_tasks:
        return urgent_actions
    existing = {a.get("id") for a in urgent_actions}
    out = list(urgent_actions)
    for t in rent_tasks:
        tid = t.get("id")
        if tid in existing:
            continue
        out.append(
            {
                "id": tid,
                "task_id": tid,
                "title": t.get("title"),
                "description": t.get("description"),
                "section": "urgent",
                "source_type": SOURCE_RENT_OPS,
                "property_id": t.get("property_id"),
                "primary_action_type": "record_rent_payment",
                "primary_action_label": "Record payment",
                "primary_action_url": t.get("primary_action_url"),
                "metadata": t.get("metadata") or {},
            }
        )
    return out
