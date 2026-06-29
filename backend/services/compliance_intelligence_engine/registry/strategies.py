"""Strategy registry storage stub — immutable versioned documents."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_intelligence_engine.constants import COLLECTION_STRATEGY_REGISTRY

_COLLECTION = COLLECTION_STRATEGY_REGISTRY


def collection_name() -> str:
    return _COLLECTION


async def publish_strategy_version(db: Any, entry: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1.5: strategy registry publish deferred to CIE-2")


async def update_strategy_version(db: Any, strategy_id: str, updates: Dict[str, Any]) -> None:
    raise NotImplementedError("CIE-1.5: strategy registry versions are immutable")


async def find_strategy_by_id(db: Any, strategy_id: str) -> Optional[Dict[str, Any]]:
    raise NotImplementedError("CIE-1.5: strategy registry read deferred to CIE-2")


async def list_strategy_versions(db: Any, *, family: Optional[str] = None) -> List[Dict[str, Any]]:
    raise NotImplementedError("CIE-1.5: strategy registry list deferred to CIE-2")
