"""Feature flag: LIFECYCLE_SEMANTICS_MODE (disabled | shadow only in Phase 1)."""

from __future__ import annotations

import logging
import os
from typing import Final, Literal

logger = logging.getLogger(__name__)

LifecycleSemanticsMode = Literal["disabled", "shadow"]

_MODE_ENV: Final[str] = "LIFECYCLE_SEMANTICS_MODE"
_VALID_MODES: Final[frozenset[str]] = frozenset({"disabled", "shadow", "active"})
_DEFAULT_MODE: LifecycleSemanticsMode = "disabled"
_RESOLVER_VERSION: Final[str] = "1.0.0-phase1"


def get_lifecycle_semantics_mode() -> LifecycleSemanticsMode:
    raw = os.getenv(_MODE_ENV, _DEFAULT_MODE).strip().lower()
    if raw == "active":
        logger.warning(
            "LIFECYCLE_SEMANTICS_MODE=active is prohibited in Phase 1; treating as disabled"
        )
        return "disabled"
    if raw in ("disabled", "shadow"):
        return raw  # type: ignore[return-value]
    return _DEFAULT_MODE


def is_lifecycle_semantics_disabled() -> bool:
    return get_lifecycle_semantics_mode() == "disabled"


def is_lifecycle_semantics_shadow() -> bool:
    return get_lifecycle_semantics_mode() == "shadow"


def resolver_version() -> str:
    return _RESOLVER_VERSION
