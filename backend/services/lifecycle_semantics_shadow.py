"""Shadow-only lifecycle semantics observation — Phase 1."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from services.lifecycle_semantics_config import is_lifecycle_semantics_shadow
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_types import ResolvedLifecycle

logger = logging.getLogger(__name__)

_SHADOW_LOG_INTERVAL_SEC = 60.0
_last_shadow_log_at: float = 0.0
_shadow_divergence_count: int = 0


def _legacy_would_treat_as_expiry(legacy: Dict[str, Any]) -> bool:
    return bool(legacy.get("expects_expiry")) or legacy.get("expiry_type") == "EXPIRING"


def _compute_divergence(resolved: ResolvedLifecycle) -> Optional[Dict[str, Any]]:
    legacy = resolved.legacy_signals.to_dict()
    legacy_expiry = _legacy_would_treat_as_expiry(legacy)
    resolver_expiry = resolved.lifecycle_semantics == "EXPIRY_BASED"
    if legacy_expiry != resolver_expiry:
        return {
            "type": "semantics_mismatch",
            "legacy_would_treat_as_expiry": legacy_expiry,
            "resolver_lifecycle_semantics": resolved.lifecycle_semantics,
        }
    if resolved.validation_issues:
        return {
            "type": "validation_issue",
            "issues": list(resolved.validation_issues),
        }
    return None


def build_shadow_payload(
    requirement: Dict[str, Any],
    *,
    registry_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved = resolve_lifecycle_semantics(requirement, registry_row=registry_row)
    divergence = _compute_divergence(resolved)
    return {
        "requirement_id": resolved.requirement_id,
        "requirement_type": resolved.requirement_code,
        "legacy_authority": resolved.legacy_signals.to_dict(),
        "lifecycle_semantics": resolved.lifecycle_semantics,
        "attention_kind": resolved.attention_kind,
        "resolution_source": resolved.resolution_source,
        "resolver_version": resolved.resolver_version,
        "divergence": divergence,
        "validation_issues": list(resolved.validation_issues),
    }


def observe_lifecycle_semantics_shadow_if_enabled(
    requirement: Dict[str, Any],
    *,
    registry_row: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Shadow-only path: log classification metadata. Does not mutate requirement or affect runtime.
  Safe to disable via LIFECYCLE_SEMANTICS_MODE=disabled.
    """
    global _last_shadow_log_at, _shadow_divergence_count
    if not is_lifecycle_semantics_shadow():
        return

    payload = build_shadow_payload(requirement, registry_row=registry_row)
    now = time.monotonic()
    if payload.get("divergence"):
        _shadow_divergence_count += 1
        logger.info(
            "lifecycle_semantics_shadow_divergence",
            extra={"lifecycle_shadow": payload},
        )
    elif now - _last_shadow_log_at >= _SHADOW_LOG_INTERVAL_SEC:
        _last_shadow_log_at = now
        logger.debug(
            "lifecycle_semantics_shadow_observed",
            extra={"lifecycle_shadow": payload},
        )


def shadow_divergence_count() -> int:
    """Test helper — divergences logged in-process."""
    return _shadow_divergence_count


def reset_shadow_counters() -> None:
    global _last_shadow_log_at, _shadow_divergence_count
    _last_shadow_log_at = 0.0
    _shadow_divergence_count = 0
