"""Artefact storage — append-only compliance_intelligence_artefacts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import database

from services.compliance_intelligence_engine.constants import COLLECTION_ARTEFACTS

_COLLECTION = COLLECTION_ARTEFACTS


def collection_name() -> str:
    return _COLLECTION


async def insert_artefact(artefact: Dict[str, Any]) -> None:
    db = database.get_db()
    await db[_COLLECTION].insert_one(dict(artefact))


async def find_artefact_by_id(artefact_id: str, *, client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    q: Dict[str, Any] = {"artefact_id": artefact_id}
    if client_id:
        q["client_id"] = client_id
    doc = await database.get_db()[_COLLECTION].find_one(q, {"_id": 0})
    return doc


async def find_active_by_dedupe_key(
    *, client_id: str, dedupe_key: str, artefact_type: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    q: Dict[str, Any] = {
        "client_id": client_id,
        "dedupe_key": dedupe_key,
        "lifecycle_state": {"$nin": ["superseded", "cancelled", "archived"]},
    }
    if artefact_type:
        q["artefact_type"] = artefact_type
    doc = await database.get_db()[_COLLECTION].find_one(q, {"_id": 0}, sort=[("generated_at", -1)])
    return doc


async def list_artefacts(
    *,
    client_id: str,
    artefact_type: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"client_id": client_id}
    if artefact_type:
        q["artefact_type"] = artefact_type
    if lifecycle_state:
        q["lifecycle_state"] = lifecycle_state
    elif active_only:
        q["lifecycle_state"] = {"$nin": ["superseded", "cancelled", "archived"]}
    cursor = database.get_db()[_COLLECTION].find(q, {"_id": 0}).sort("generated_at", -1).limit(limit)
    return await cursor.to_list(length=limit)
