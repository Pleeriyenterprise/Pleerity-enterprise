"""
Feature flag: LIFECYCLE_AWARE_KPIS (off | shadow | active).

Phase 5 P5-S1: infrastructure only — no KPI or dashboard wiring in this slice.

Shadow: legacy KPI behaviour authoritative; lifecycle-gated observe in P5-S2+.
Active: lifecycle-gated KPIs (preview-tier only; staging downgrades to shadow).
"""

from __future__ import annotations

import logging
import os
from typing import Final, Literal

logger = logging.getLogger(__name__)

LifecycleAwareKpiMode = Literal["off", "shadow", "active"]
EffectiveKpiMode = Literal["off", "shadow", "active"]

_MODE_ENV: Final[str] = "LIFECYCLE_AWARE_KPIS"
_PREVIEW_OVERRIDE_ENV: Final[str] = "LIFECYCLE_AWARE_KPIS_PREVIEW_OVERRIDE"
_DEFAULT_MODE: LifecycleAwareKpiMode = "off"


def _skipped() -> bool:
    return os.getenv("PYTEST_RUNNING") == "1"


def _read_requested_kpi_mode() -> LifecycleAwareKpiMode:
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


def get_effective_kpi_mode() -> EffectiveKpiMode:
    """
    Resolve runtime mode after deployment-tier guards.

    - off / shadow: unchanged
    - active on staging → shadow (warning)
    - active on production → off (warning); preview override never enables active on production
    - active on preview or with preview override (non-production) → active
    """
    requested = _read_requested_kpi_mode()
    if requested != "active":
        return requested

    tier = _lifecycle_deployment_tier()
    if tier == "production":
        logger.warning(
            "LIFECYCLE_AWARE_KPIS=active on production tier; downgrading effective mode to off"
        )
        return "off"

    if _preview_override_enabled():
        return "active"

    if tier == "staging":
        logger.warning(
            "LIFECYCLE_AWARE_KPIS=active on staging tier; downgrading effective mode to shadow"
        )
        return "shadow"

    if tier == "preview":
        return "active"

    logger.warning(
        "LIFECYCLE_AWARE_KPIS=active without preview tier or %s; downgrading to off",
        _PREVIEW_OVERRIDE_ENV,
    )
    return "off"


def get_lifecycle_aware_kpi_mode() -> EffectiveKpiMode:
    """Backward-compatible alias for :func:`get_effective_kpi_mode`."""
    return get_effective_kpi_mode()


def is_lifecycle_aware_kpi_off() -> bool:
    return get_effective_kpi_mode() == "off"


def is_lifecycle_aware_kpi_shadow() -> bool:
    return get_effective_kpi_mode() == "shadow"


def is_lifecycle_aware_kpi_active() -> bool:
    return get_effective_kpi_mode() == "active"


def validate_lifecycle_kpi_boot() -> EffectiveKpiMode:
    """
    Boot guard: production must never run with effective active mode.

    When ``LIFECYCLE_AWARE_KPIS=active`` is set on production, effective mode is
    forced to ``off``. Does not abort startup.
    """
    if _skipped():
        return get_effective_kpi_mode()

    requested = _read_requested_kpi_mode()
    tier = _lifecycle_deployment_tier()
    effective = get_effective_kpi_mode()

    if requested == "active" and tier == "production":
        logger.critical(
            "lifecycle_kpi_boot_guard: LIFECYCLE_AWARE_KPIS=active on production; "
            "effective mode enforced as off (no lifecycle KPI gates on production)"
        )
    if effective == "active":
        logger.info(
            "lifecycle_kpi_boot_guard: effective mode=active tier=%s preview_override=%s",
            tier,
            _preview_override_enabled(),
        )
    return effective
