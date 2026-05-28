"""
Idempotent replay for risk signal → active work order lineage.

Prevents duplicate operational workflows when propagation or linked WO already exists.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from services import maintenance_service

WO_TERMINAL = frozenset({"COMPLETED", "VERIFIED", "CLOSED", "CANCELLED", "cancelled"})


async def find_active_work_order_for_risk_signal(
    db,
    *,
    signal_id: str,
    client_id: str,
) -> Optional[Dict[str, Any]]:
    """Latest non-terminal work order linked to this risk signal."""
    row = await db.work_orders.find_one(
        {
            "client_id": client_id,
            "risk_signal_id": signal_id,
            "status": {"$nin": list(WO_TERMINAL)},
        },
        {"_id": 0, "work_order_id": 1},
        sort=[("created_at", -1)],
    )
    if not row or not row.get("work_order_id"):
        return None
    doc = await maintenance_service.get_work_order(str(row["work_order_id"]))
    if not doc:
        return None
    out = dict(doc)
    out["idempotent_replay"] = True
    return out


async def replay_active_work_order_for_risk_signal(
    signal_id: str,
    client_id: str,
) -> Optional[Dict[str, Any]]:
    from database import database

    db = database.get_db()
    return await find_active_work_order_for_risk_signal(db, signal_id=signal_id, client_id=client_id)
