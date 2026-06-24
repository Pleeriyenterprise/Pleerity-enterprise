"""Feature flag: LIFECYCLE_AWARE_CONFIRM (off | shadow only in Phase 2 S1–S3)."""

from __future__ import annotations

import logging
import os
from typing import Final, Literal

logger = logging.getLogger(__name__)

LifecycleAwareConfirmMode = Literal["off", "shadow"]

_MODE_ENV: Final[str] = "LIFECYCLE_AWARE_CONFIRM"
_DEFAULT_MODE: LifecycleAwareConfirmMode = "off"
_CONTRACT_VERSION: Final[str] = "1.0.0-phase2"


def get_lifecycle_aware_confirm_mode() -> LifecycleAwareConfirmMode:
    raw = os.getenv(_MODE_ENV, _DEFAULT_MODE).strip().lower()
    if raw == "active":
        logger.warning(
            "LIFECYCLE_AWARE_CONFIRM=active is prohibited in Phase 2 S1–S3; treating as off"
        )
        return "off"
    if raw == "shadow":
        return "shadow"
    return "off"


def is_lifecycle_aware_confirm_off() -> bool:
    return get_lifecycle_aware_confirm_mode() == "off"


def is_lifecycle_aware_confirm_shadow() -> bool:
    return get_lifecycle_aware_confirm_mode() == "shadow"


def contract_version() -> str:
    return _CONTRACT_VERSION
