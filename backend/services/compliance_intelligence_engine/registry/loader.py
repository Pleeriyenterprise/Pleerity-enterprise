"""In-memory registry resolution — v1 seeds (CIE-2)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_intelligence_engine.registry.seeds_v1 import (
    all_registry_seeds_v1,
    constraint_seed_v1,
    strategy_seed_v1,
    weight_seed_v1,
)
from services.compliance_intelligence_engine.registry.versions import (
    CONSTRAINT_SET_V1,
    PRIORITY_STRATEGY_V1,
    REC_STRATEGY_V1,
    WEIGHT_SET_V1,
)


def get_weight_set_v1() -> Dict[str, Any]:
    return weight_seed_v1()


def get_constraint_set_v1() -> Dict[str, Any]:
    return constraint_seed_v1()


def get_strategy_v1(strategy_id: str) -> Optional[Dict[str, Any]]:
    for s in strategy_seed_v1():
        if s["strategy_id"] == strategy_id:
            return s
    return None


def get_rec_strategy_v1() -> Dict[str, Any]:
    s = get_strategy_v1(REC_STRATEGY_V1)
    if not s:
        raise ValueError("rec_strategy_v1_missing")
    return s


def get_priority_strategy_v1() -> Dict[str, Any]:
    s = get_strategy_v1(PRIORITY_STRATEGY_V1)
    if not s:
        raise ValueError("priority_strategy_v1_missing")
    return s


def registry_pins_for_recommendation() -> Dict[str, str]:
    return {
        "recommendation_strategy_version": REC_STRATEGY_V1,
        "priority_strategy_version": PRIORITY_STRATEGY_V1,
        "weight_set_version": WEIGHT_SET_V1,
        "constraint_set_version": CONSTRAINT_SET_V1,
    }
