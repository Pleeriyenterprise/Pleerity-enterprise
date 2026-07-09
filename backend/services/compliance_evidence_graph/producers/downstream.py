"""Stamp optional graph metadata on downstream authoritative collections."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def graph_metadata_fields(
    *,
    decision_id: str,
    snapshot_id: str,
    operational_correlation_id: Optional[str] = None,
    graph_emit_status: str = "emitted",
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "decision_id": decision_id,
        "snapshot_id": snapshot_id,
        "graph_emitted_at": _now_iso(),
        "graph_emit_status": graph_emit_status,
    }
    if operational_correlation_id:
        out["operational_correlation_id"] = operational_correlation_id
    return out


async def stamp_document(
    db,
    collection: str,
    query: Dict[str, Any],
    *,
    decision_id: str,
    snapshot_id: str,
    operational_correlation_id: Optional[str] = None,
) -> None:
    fields = graph_metadata_fields(
        decision_id=decision_id,
        snapshot_id=snapshot_id,
        operational_correlation_id=operational_correlation_id,
    )
    await db[collection].update_one(query, {"$set": fields})
