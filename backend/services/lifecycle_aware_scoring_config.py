"""
Feature flag: LIFECYCLE_AWARE_SCORING (off | shadow | active).

Phase 3 S3.1: infrastructure. S3.2/S3.3: shadow telemetry + active penalty gates in lifecycle_scoring_gates.py.

Shadow: legacy scoring authoritative; parallel lifecycle-gated compute logs divergences.
Active: lifecycle-gated penalties (preview-tier only; staging downgrades to shadow).
"""

from __future__ import annotations

import logging
import os
from typing import Final, Literal

logger = logging.getLogger(__name__)

LifecycleAwareScoringMode = Literal["off", "shadow", "active"]
EffectiveScoringMode = Literal["off", "shadow", "active"]

_MODE_ENV: Final[str] = "LIFECYCLE_AWARE_SCORING"
_PREVIEW_OVERRIDE_ENV: Final[str] = "LIFECYCLE_AWARE_SCORING_PREVIEW_OVERRIDE"
_DEFAULT_MODE: LifecycleAwareScoringMode = "off"


def _skipped() -> bool:
    return os.getenv("PYTEST_RUNNING") == "1"


def _read_requested_scoring_mode() -> LifecycleAwareScoringMode:
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


def get_effective_scoring_mode() -> EffectiveScoringMode:
    """
    Resolve runtime mode after deployment-tier guards.

    - off / shadow: unchanged
    - active on staging → shadow (warning)
    - active on production / unknown without preview override → off (warning)
    - active on preview or with preview override → active
    """
    requested = _read_requested_scoring_mode()
    if requested != "active":
        return requested

    tier = _lifecycle_deployment_tier()
    if tier == "production":
        logger.warning(
            "LIFECYCLE_AWARE_SCORING=active on production tier; downgrading effective mode to off"
        )
        return "off"

    if _preview_override_enabled():
        return "active"

    if tier == "staging":
        logger.warning(
            "LIFECYCLE_AWARE_SCORING=active on staging tier; downgrading effective mode to shadow"
        )
        return "shadow"

    if tier == "preview":
        return "active"

    logger.warning(
        "LIFECYCLE_AWARE_SCORING=active without preview tier or %s; downgrading to off",
        _PREVIEW_OVERRIDE_ENV,
    )
    return "off"


def get_lifecycle_aware_scoring_mode() -> EffectiveScoringMode:
    """Backward-compatible alias for :func:`get_effective_scoring_mode`."""
    return get_effective_scoring_mode()


def is_lifecycle_aware_scoring_off() -> bool:
    return get_effective_scoring_mode() == "off"


def is_lifecycle_aware_scoring_shadow() -> bool:
    return get_effective_scoring_mode() == "shadow"


def is_lifecycle_aware_scoring_active() -> bool:
    return get_effective_scoring_mode() == "active"


def validate_lifecycle_scoring_boot() -> EffectiveScoringMode:
    """
    Boot guard: production must never run with effective active mode.

    When ``LIFECYCLE_AWARE_SCORING=active`` is set on production, effective mode is
    forced to ``off``. Does not abort startup.
    """
    if _skipped():
        return get_effective_scoring_mode()

    requested = _read_requested_scoring_mode()
    tier = _lifecycle_deployment_tier()
    effective = get_effective_scoring_mode()

    if requested == "active" and tier == "production":
        logger.critical(
            "lifecycle_scoring_boot_guard: LIFECYCLE_AWARE_SCORING=active on production; "
            "effective mode enforced as off (no lifecycle scoring gates on production)"
        )
    if effective == "active":
        logger.info(
            "lifecycle_scoring_boot_guard: effective mode=active tier=%s preview_override=%s",
            tier,
            _preview_override_enabled(),
        )
    return effective
