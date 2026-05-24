"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — operational control-plane verification framework.

Infrastructure only; does not execute or classify runtime families without harness invocation.
"""
from __future__ import annotations

from .constants import (
    PROGRAMME_ID,
    PROJECTION_RESOLUTION_RANKS,
    VERIFY_01_FAMILY_SLUGS,
    Verify02Family,
)
from .classification_helpers import ClassificationAggregator, Verify02Classification

__all__ = [
    "PROGRAMME_ID",
    "PROJECTION_RESOLUTION_RANKS",
    "VERIFY_01_FAMILY_SLUGS",
    "Verify02Classification",
    "Verify02Family",
    "ClassificationAggregator",
]
