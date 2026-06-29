"""Weight registry storage stub — immutable versioned weight sets."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_intelligence_engine.constants import COLLECTION_WEIGHT_REGISTRY

_COLLECTION = COLLECTION_WEIGHT_REGISTRY


def collection_name() -> str:
    return _COLLECTION


async def publish_weight_set(db: Any, entry: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1.5: weight registry publish deferred to CIE-2")


async def update_weight_set(db: Any, weight_set_id: str, updates: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1.5: weight registry versions are immutable")


async def find_weight_set_by_id(db: Any, weight_set_id: str) -> Optional[Dict[str, Any]]:
    raise NotImplementedError("CIE-1.5: weight registry read deferred to CIE-2")


async def list_weight_sets(db: Any) -> List[Dict[str, Any]]:
    raise NotImplementedError("CIE-1.5: weight registry list deferred to CIE-2")
