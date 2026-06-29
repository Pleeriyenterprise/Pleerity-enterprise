"""Artefact storage stub — persistence deferred to CIE-2+."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_intelligence_engine.constants import COLLECTION_ARTEFACTS

_COLLECTION = COLLECTION_ARTEFACTS


def collection_name() -> str:
    return _COLLECTION


async def insert_artefact(db: Any, artefact: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1: artefact insert deferred to CIE-2")


async def find_artefact_by_id(db: Any, artefact_id: str, *, client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    raise NotImplementedError("CIE-1: artefact read deferred to CIE-2")
