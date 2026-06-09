"""
Bounded regen governance for operational risk signal lifecycle (F4 remediation).

Protects signals with propagation lineage from hard deletion during heuristic regen.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

ISSUE_TERMINAL_STATUSES = frozenset({"closed", "cancelled", "resolved"})
WO_TERMINAL_STATUSES = frozenset({"COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"})

# Non-terminal lifecycle states that regen must never hard-delete.
REGEN_PROTECTED_STATUSES = frozenset({"acknowledged", "remediation_in_progress"})


def stable_signal_key(risk_type: str, asset_id: Optional[str]) -> Tuple[str, Optional[str]]:
    rt = (risk_type or "").strip()
    aid = (asset_id or "").strip() or None
    return rt, aid


async def collect_operational_debt_signal_ids(db, client_id: str, property_id: str) -> Set[str]:
    """Signal IDs linked to unresolved propagated issues or work orders."""
    from services.unified_tasks_operational_convergence import issue_is_stale_operational_residue

    debt: Set[str] = set()
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
    prop_doc = await db.properties.find_one(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0, "property_id": 1, "jurisdiction": 1, "tenancy_active": 1, "furnished": 1, "is_hmo": 1},
    ) or {}
    async for issue in db.maintenance_issues.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "risk_signal_id": {"$exists": True, "$nin": [None, ""]},
            "status": {"$nin": list(ISSUE_TERMINAL_STATUSES)},
        },
        {"_id": 0},
    ):
        if await issue_is_stale_operational_residue(
            db,
            client_id=client_id,
            issue=issue,
            client_doc=client_doc if isinstance(client_doc, dict) else {},
            prop_doc=prop_doc if isinstance(prop_doc, dict) else {},
        ):
            continue
        sid = (issue.get("risk_signal_id") or "").strip()
        if sid:
            debt.add(sid)
    async for wo in db.work_orders.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "risk_signal_id": {"$exists": True, "$nin": [None, ""]},
            "status": {"$nin": list(WO_TERMINAL_STATUSES)},
        },
        {"_id": 0, "risk_signal_id": 1},
    ):
        sid = (wo.get("risk_signal_id") or "").strip()
        if sid:
            debt.add(sid)
    return debt


def should_retain_signal_on_regen(
    doc: Dict[str, Any],
    *,
    operational_debt_ids: Set[str],
    merged_retained_ids: Set[str],
) -> bool:
    sid = doc.get("signal_id")
    if not sid:
        return False
    if sid in operational_debt_ids or sid in merged_retained_ids:
        return True
    status = (doc.get("status") or "").lower()
    if status in REGEN_PROTECTED_STATUSES:
        return True
    return False
