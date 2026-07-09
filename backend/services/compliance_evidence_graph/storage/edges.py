"""Internal storage — compliance_evidence_edges with provenance (append-only)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import database

from services.compliance_evidence_graph.constants import COLLECTION_EDGES


async def insert_edge(doc: Dict[str, Any]) -> None:
    db = database.get_db()
    await db[COLLECTION_EDGES].insert_one(doc)


async def get_edge_by_dedupe(dedupe_key: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COLLECTION_EDGES].find_one({"dedupe_key": dedupe_key}, {"_id": 0})


async def list_edges_for_decision(decision_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = (
        db[COLLECTION_EDGES]
        .find({"provenance.decision_id": decision_id}, {"_id": 0})
        .sort("recorded_at", 1)
        .limit(limit)
    )
    return await cursor.to_list(limit)


async def list_edges_from_node(node_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = (
        db[COLLECTION_EDGES]
        .find({"from_node_id": node_id, "provenance.is_active": True}, {"_id": 0})
        .limit(limit)
    )
    return await cursor.to_list(limit)


async def list_edges_to_node(node_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = (
        db[COLLECTION_EDGES]
        .find({"to_node_id": node_id, "provenance.is_active": True}, {"_id": 0})
        .limit(limit)
    )
    return await cursor.to_list(limit)
