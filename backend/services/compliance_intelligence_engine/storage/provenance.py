"""Provenance storage — append-only compliance_intelligence_provenance."""
from __future__ import annotations

from typing import Any, Dict, Optional

from database import database

from services.compliance_intelligence_engine.constants import COLLECTION_PROVENANCE

_COLLECTION = COLLECTION_PROVENANCE


def collection_name() -> str:
    return _COLLECTION


async def insert_provenance(provenance: Dict[str, Any]) -> None:
    db = database.get_db()
    await db[_COLLECTION].insert_one(dict(provenance))


async def update_provenance(db: Any, provenance_id: str, updates: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE: provenance records are immutable")


async def find_provenance_by_id(provenance_id: str, *, client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    q: Dict[str, Any] = {"provenance_id": provenance_id}
    if client_id:
        q["client_id"] = client_id
    return await database.get_db()[_COLLECTION].find_one(q, {"_id": 0})


async def find_provenance_by_artefact_id(artefact_id: str, *, client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    q: Dict[str, Any] = {"artefact_id": artefact_id}
    if client_id:
        q["client_id"] = client_id
    return await database.get_db()[_COLLECTION].find_one(q, {"_id": 0})
