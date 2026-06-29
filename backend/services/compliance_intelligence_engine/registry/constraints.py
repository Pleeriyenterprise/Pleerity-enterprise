"""Constraint registry storage stub — immutable versioned constraint sets."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_intelligence_engine.constants import COLLECTION_CONSTRAINT_REGISTRY

_COLLECTION = COLLECTION_CONSTRAINT_REGISTRY


def collection_name() -> str:
    return _COLLECTION


async def publish_constraint_set(db: Any, entry: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1.5: constraint registry publish deferred to CIE-2")


async def update_constraint_set(db: Any, constraint_set_id: str, updates: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1.5: constraint registry versions are immutable")


async def find_constraint_set_by_id(db: Any, constraint_set_id: str) -> Optional[Dict[str, Any]]:
    raise NotImplementedError("CIE-1.5: constraint registry read deferred to CIE-2")


async def list_constraint_sets(db: Any) -> List[Dict[str, Any]]:
    raise NotImplementedError("CIE-1.5: constraint registry list deferred to CIE-2")
