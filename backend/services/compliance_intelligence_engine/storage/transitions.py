"""Lifecycle transition storage — append-only."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import database

from services.compliance_intelligence_engine.constants import COLLECTION_TRANSITIONS

_COLLECTION = COLLECTION_TRANSITIONS


def collection_name() -> str:
    return _COLLECTION


async def insert_transition(transition: Dict[str, Any]) -> None:
    db = database.get_db()
    await db[_COLLECTION].insert_one(dict(transition))


async def list_transitions_for_artefact(artefact_id: str, *, client_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"artefact_id": artefact_id}
    if client_id:
        q["client_id"] = client_id
    cursor = database.get_db()[_COLLECTION].find(q, {"_id": 0}).sort("transitioned_at", -1)
    return await cursor.to_list(length=100)
