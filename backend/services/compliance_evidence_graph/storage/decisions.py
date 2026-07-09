"""Internal storage — compliance_decisions (append-only)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import database

from services.compliance_evidence_graph.constants import COLLECTION_DECISIONS


async def insert_decision(doc: Dict[str, Any]) -> None:
    db = database.get_db()
    await db[COLLECTION_DECISIONS].insert_one(doc)


async def get_decision(decision_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COLLECTION_DECISIONS].find_one({"decision_id": decision_id}, {"_id": 0})


async def get_decision_by_dedupe(dedupe_key: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COLLECTION_DECISIONS].find_one({"dedupe_key": dedupe_key}, {"_id": 0})


async def list_decisions_for_scope(
    *,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    decision_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {}
    if client_id:
        q["client_id"] = client_id
    if property_id:
        q["property_id"] = property_id
    if requirement_id:
        q["requirement_id"] = requirement_id
    if decision_type:
        q["decision_type"] = decision_type
    if since or until:
        q["decision_timestamp"] = {}
        if since:
            q["decision_timestamp"]["$gte"] = since
        if until:
            q["decision_timestamp"]["$lte"] = until
    cursor = db[COLLECTION_DECISIONS].find(q, {"_id": 0}).sort("decision_timestamp", -1).limit(limit)
    return await cursor.to_list(limit)


async def find_decision_at_or_before(
    *,
    client_id: str,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    as_of: str,
    decision_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id, "decision_timestamp": {"$lte": as_of}}
    if property_id:
        q["property_id"] = property_id
    if requirement_id:
        q["requirement_id"] = requirement_id
    if decision_type:
        q["decision_type"] = decision_type
    return await db[COLLECTION_DECISIONS].find_one(q, {"_id": 0}, sort=[("decision_timestamp", -1)])
