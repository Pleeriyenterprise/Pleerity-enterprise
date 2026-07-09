"""Internal storage — compliance_evidence_nodes (append-only)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import database

from services.compliance_evidence_graph.constants import COLLECTION_NODES


async def insert_node(doc: Dict[str, Any]) -> None:
    db = database.get_db()
    await db[COLLECTION_NODES].insert_one(doc)


async def get_node(node_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COLLECTION_NODES].find_one({"node_id": node_id}, {"_id": 0})


async def list_nodes_for_decision(decision_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = (
        db[COLLECTION_NODES]
        .find({"decision_id": decision_id}, {"_id": 0})
        .sort("occurred_at", 1)
        .limit(limit)
    )
    return await cursor.to_list(limit)


async def list_nodes_by_ids(node_ids: List[str]) -> List[Dict[str, Any]]:
    if not node_ids:
        return []
    db = database.get_db()
    cursor = db[COLLECTION_NODES].find({"node_id": {"$in": node_ids}}, {"_id": 0})
    return await cursor.to_list(len(node_ids))
