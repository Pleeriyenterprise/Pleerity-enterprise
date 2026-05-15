"""
Back-compat shim — GPT-first orchestration moved to support_ai_brain.py.

Prefer importing from services.support_ai_brain for new code.
"""
from __future__ import annotations

from services.support_ai_brain import (
    ALLOWED_ACTION_IDS,
    run_public_support_ai_brain as run_gpt_first_public_turn,
    run_support_ai_brain_turn,
    support_ai_brain_enabled as support_gpt_first_enabled,
    try_protected_deterministic_shortcuts as try_gpt_first_deterministic_shortcuts,
)

__all__ = [
    "ALLOWED_ACTION_IDS",
    "run_gpt_first_public_turn",
    "run_support_ai_brain_turn",
    "support_gpt_first_enabled",
    "try_gpt_first_deterministic_shortcuts",
]
