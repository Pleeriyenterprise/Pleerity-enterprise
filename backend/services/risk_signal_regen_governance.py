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
    debt: Set[str] = set()
    async for issue in db.maintenance_issues.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "risk_signal_id": {"$exists": True, "$nin": [None, ""]},
            "status": {"$nin": list(ISSUE_TERMINAL_STATUSES)},
        },
        {"_id": 0, "risk_signal_id": 1},
    ):
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
