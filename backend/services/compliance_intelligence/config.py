"""Feature flags for Compliance Intelligence Layer (Phase 5)."""
from __future__ import annotations

import os

from services.compliance_evidence_graph.config import graph_consumers_enabled


def intelligence_enabled() -> bool:
    """Tier 1 investigate (Graph Service dispatch) — requires graph mode enabled."""
    return graph_consumers_enabled()


def intelligence_narration_enabled() -> bool:
    """Tier 2 optional LLM narration — graph enabled + AI_ENABLED + explicit opt-in."""
    if not intelligence_enabled():
        return False
    from utils import ai_config

    if not ai_config.AI_ENABLED or not ai_config.is_configured():
        return False
    return (os.getenv("COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
