"""
Feature flag: LIFECYCLE_AWARE_CONFIRM (off | shadow | active).

S5.4: ``active`` is permitted only on preview tier or with
``LIFECYCLE_AWARE_CONFIRM_PREVIEW_OVERRIDE=1``. Staging downgrades active → shadow;
production downgrades active → off. Boot validation documents production guard.
"""

from __future__ import annotations

import logging
import os
from typing import Final, Literal

logger = logging.getLogger(__name__)

LifecycleAwareConfirmMode = Literal["off", "shadow", "active"]
EffectiveConfirmMode = Literal["off", "shadow", "active"]

_MODE_ENV: Final[str] = "LIFECYCLE_AWARE_CONFIRM"
_PREVIEW_OVERRIDE_ENV: Final[str] = "LIFECYCLE_AWARE_CONFIRM_PREVIEW_OVERRIDE"
_DEFAULT_MODE: LifecycleAwareConfirmMode = "off"
_CONTRACT_VERSION: Final[str] = "1.0.0-phase2"


def _skipped() -> bool:
    return os.getenv("PYTEST_RUNNING") == "1"


def _read_requested_confirm_mode() -> LifecycleAwareConfirmMode:
    raw = os.getenv(_MODE_ENV, _DEFAULT_MODE).strip().lower()
    if raw == "active":
        return "active"
    if raw == "shadow":
        return "shadow"
    if raw not in ("off", "shadow", "active"):
        logger.warning("Unknown %s=%r; treating as off", _MODE_ENV, raw)
    return "off"


def _preview_override_enabled() -> bool:
    return os.getenv(_PREVIEW_OVERRIDE_ENV, "").strip().lower() in ("1", "true", "yes")


def _lifecycle_deployment_tier() -> str:
    explicit = (os.getenv("DEPLOYMENT_TIER") or "").strip().lower()
    if explicit == "preview":
        return "preview"
    from utils.deployment_environment_guard import resolve_deployment_tier

    return resolve_deployment_tier()


def get_effective_confirm_mode() -> EffectiveConfirmMode:
    """
    Resolve runtime mode after deployment-tier guards.

    - off / shadow: unchanged
    - active on staging → shadow (warning)
    - active on production / unknown without preview override → off (warning)
    - active on preview or with preview override → active
    """
    requested = _read_requested_confirm_mode()
    if requested != "active":
        return requested

    tier = _lifecycle_deployment_tier()
    if tier == "production":
        logger.warning(
            "LIFECYCLE_AWARE_CONFIRM=active on production tier; downgrading effective mode to off"
        )
        return "off"

    if _preview_override_enabled():
        return "active"

    if tier == "staging":
        logger.warning(
            "LIFECYCLE_AWARE_CONFIRM=active on staging tier; downgrading effective mode to shadow"
        )
        return "shadow"

    if tier == "preview":
        return "active"

    logger.warning(
        "LIFECYCLE_AWARE_CONFIRM=active without preview tier or %s; downgrading to off",
        _PREVIEW_OVERRIDE_ENV,
    )
    return "off"


def get_lifecycle_aware_confirm_mode() -> EffectiveConfirmMode:
    """Backward-compatible alias for :func:`get_effective_confirm_mode`."""
    return get_effective_confirm_mode()


def is_lifecycle_aware_confirm_off() -> bool:
    return get_effective_confirm_mode() == "off"


def is_lifecycle_aware_confirm_shadow() -> bool:
    return get_effective_confirm_mode() == "shadow"


def is_lifecycle_aware_confirm_active() -> bool:
    return get_effective_confirm_mode() == "active"


def validate_lifecycle_confirm_boot() -> EffectiveConfirmMode:
    """
  Boot guard: production must never run with effective active mode.

  When ``LIFECYCLE_AWARE_CONFIRM=active`` is set on production, effective mode is
  forced to ``off`` (see :func:`get_effective_confirm_mode`). This function logs
  a critical warning and returns the effective mode. It does not abort startup so
  mis-set env vars cannot take production offline; runtime enforcement remains off.
    """
    if _skipped():
        return get_effective_confirm_mode()

    requested = _read_requested_confirm_mode()
    tier = _lifecycle_deployment_tier()
    effective = get_effective_confirm_mode()

    if requested == "active" and tier == "production":
        logger.critical(
            "lifecycle_confirm_boot_guard: LIFECYCLE_AWARE_CONFIRM=active on production; "
            "effective mode enforced as off (no blocking enforcement on production)"
        )
    if effective == "active":
        logger.info(
            "lifecycle_confirm_boot_guard: effective mode=active tier=%s preview_override=%s",
            tier,
            _preview_override_enabled(),
        )
    return effective


def contract_version() -> str:
    return _CONTRACT_VERSION
