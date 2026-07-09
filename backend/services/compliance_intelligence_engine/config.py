"""Feature flags for Compliance Intelligence Engine."""
from __future__ import annotations

import os

_VALID_MODES = frozenset({"disabled", "shadow", "enabled"})


def intelligence_engine_mode() -> str:
    raw = (os.getenv("COMPLIANCE_INTELLIGENCE_ENGINE_MODE") or "disabled").strip().lower()
    return raw if raw in _VALID_MODES else "disabled"


def intelligence_engine_enabled() -> bool:
    """Engine may run (shadow observe or enabled operational)."""
    return intelligence_engine_mode() in ("shadow", "enabled")


def intelligence_engine_operational_effects() -> bool:
    """Side-effects on work orders, reminders, etc. — enabled only."""
    return intelligence_engine_mode() == "enabled"


def intelligence_engine_shadow_validation() -> bool:
    """Internal/admin validation paths in shadow mode."""
    return intelligence_engine_mode() == "shadow"
