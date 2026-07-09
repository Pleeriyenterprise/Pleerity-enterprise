"""Internal storage — compliance_decision_snapshots (immutable)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from database import database

from services.compliance_evidence_graph.constants import COLLECTION_SNAPSHOTS


async def insert_snapshot(doc: Dict[str, Any]) -> None:
    db = database.get_db()
    await db[COLLECTION_SNAPSHOTS].insert_one(doc)


async def get_snapshot(snapshot_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COLLECTION_SNAPSHOTS].find_one({"snapshot_id": snapshot_id}, {"_id": 0})


async def get_snapshot_by_decision(decision_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COLLECTION_SNAPSHOTS].find_one({"decision_id": decision_id}, {"_id": 0})
