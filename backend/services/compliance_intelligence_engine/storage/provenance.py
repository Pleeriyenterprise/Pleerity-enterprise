"""Provenance storage stub — append-only persistence deferred to CIE-2."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_intelligence_engine.constants import COLLECTION_PROVENANCE

_COLLECTION = COLLECTION_PROVENANCE


def collection_name() -> str:
    return _COLLECTION


async def insert_provenance(db: Any, provenance: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1.5: provenance insert deferred to CIE-2")


async def update_provenance(db: Any, provenance_id: str, updates: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1.5: provenance records are immutable")


async def find_provenance_by_id(
    db: Any, provenance_id: str, *, client_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    raise NotImplementedError("CIE-1.5: provenance read deferred to CIE-2")


async def find_provenance_by_artefact_id(
    db: Any, artefact_id: str, *, client_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    raise NotImplementedError("CIE-1.5: provenance read deferred to CIE-2")
