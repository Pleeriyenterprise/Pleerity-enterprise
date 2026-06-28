"""Compliance Evidence Graph feature flag and emit guards."""
from __future__ import annotations

import os


def graph_mode() -> str:
    return (os.getenv("COMPLIANCE_EVIDENCE_GRAPH_MODE") or "disabled").strip().lower()


def graph_producers_enabled() -> bool:
    """Live mutation producers (Phase 2+) — disabled in Phase 1."""
    return graph_mode() in ("shadow", "enabled")


def graph_emit_allowed() -> bool:
    """Internal emit for tests, fixtures, and shadow/enabled producers."""
    mode = graph_mode()
    if mode in ("shadow", "enabled", "phase1_validation"):
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    return False


def graph_debug_storage_api() -> bool:
    return (os.getenv("COMPLIANCE_EVIDENCE_GRAPH_DEBUG") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
