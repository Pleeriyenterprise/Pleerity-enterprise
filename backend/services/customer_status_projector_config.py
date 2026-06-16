"""Feature flag: CUSTOMER_STATUS_PROJECTOR_V2_MODE (disabled | shadow | active)."""

from __future__ import annotations

import os
from typing import Final, Literal

ProjectorMode = Literal["disabled", "shadow", "active"]

_MODE_ENV: Final[str] = "CUSTOMER_STATUS_PROJECTOR_V2_MODE"
_VALID_MODES: Final[frozenset[str]] = frozenset({"disabled", "shadow", "active"})
_DEFAULT_MODE: ProjectorMode = "disabled"


def get_customer_status_projector_mode() -> ProjectorMode:
    raw = os.getenv(_MODE_ENV, _DEFAULT_MODE).strip().lower()
    if raw in _VALID_MODES:
        return raw  # type: ignore[return-value]
    return _DEFAULT_MODE


def is_customer_status_projector_disabled() -> bool:
    return get_customer_status_projector_mode() == "disabled"


def is_customer_status_projector_shadow() -> bool:
    return get_customer_status_projector_mode() == "shadow"


def is_customer_status_projector_active() -> bool:
    return get_customer_status_projector_mode() == "active"


def is_customer_status_projector_enabled() -> bool:
    return get_customer_status_projector_mode() in ("shadow", "active")
