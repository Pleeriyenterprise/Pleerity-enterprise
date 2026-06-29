"""Lifecycle transition storage stub — persistence deferred to CIE-2+."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_intelligence_engine.constants import COLLECTION_TRANSITIONS

_COLLECTION = COLLECTION_TRANSITIONS


def collection_name() -> str:
    return _COLLECTION


async def insert_transition(db: Any, transition: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1: transition insert deferred to CIE-2")


async def list_transitions_for_artefact(
    db: Any, artefact_id: str, *, client_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    raise NotImplementedError("CIE-1: transition list deferred to CIE-2")
