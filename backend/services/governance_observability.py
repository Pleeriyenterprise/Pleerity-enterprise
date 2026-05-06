"""
Governance observability foundations (additive, in-process only).

Phase 1: optional buffers for tests and future wiring. No vendor telemetry, no
automatic emission from production paths unless explicitly called.

Callers may invoke record_* from diagnostics routes or tests only.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional

_MAX_EVENTS = 2000

_governance_violations: Deque[Dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_semantic_drift: Deque[Dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_surface_fallback: Deque[Dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_noncanonical_render: Deque[Dict[str, Any]] = deque(maxlen=_MAX_EVENTS)


def record_governance_violation(
    *,
    surface: str,
    code: str,
    detail: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _governance_violations.append(
        {"surface": surface, "code": code, "detail": detail, "metadata": dict(metadata or {})}
    )


def record_semantic_drift(
    *,
    surface: str,
    drift_type: str,
    detail: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _semantic_drift.append(
        {"surface": surface, "drift_type": drift_type, "detail": detail, "metadata": dict(metadata or {})}
    )


def record_surface_fallback_usage(
    *,
    surface: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _surface_fallback.append({"surface": surface, "reason": reason, "metadata": dict(metadata or {})})


def record_noncanonical_requirement_render(
    *,
    surface: str,
    requirement_identifier: str,
    detail: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _noncanonical_render.append(
        {
            "surface": surface,
            "requirement_identifier": requirement_identifier,
            "detail": detail,
            "metadata": dict(metadata or {}),
        }
    )


def drain_governance_violations() -> List[Dict[str, Any]]:
    out = list(_governance_violations)
    _governance_violations.clear()
    return out


def drain_semantic_drift() -> List[Dict[str, Any]]:
    out = list(_semantic_drift)
    _semantic_drift.clear()
    return out


def drain_surface_fallback_usage() -> List[Dict[str, Any]]:
    out = list(_surface_fallback)
    _surface_fallback.clear()
    return out


def drain_noncanonical_renders() -> List[Dict[str, Any]]:
    out = list(_noncanonical_render)
    _noncanonical_render.clear()
    return out


def reset_all_governance_observability_buffers() -> None:
    _governance_violations.clear()
    _semantic_drift.clear()
    _surface_fallback.clear()
    _noncanonical_render.clear()
