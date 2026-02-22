"""
AI provider configuration from environment variables.
- When AI_ENABLED=false: no AI env vars are required.
- When AI_ENABLED=true: OPENAI_API_KEY is required; if missing, return 503 with error_code AI_NOT_CONFIGURED.
- Never expose OPENAI_API_KEY to the frontend.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Backend root (parent of utils/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("true", "1", "yes")


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Canonical AI config (read once at import; override in tests via patch/env)
# ---------------------------------------------------------------------------

AI_ENABLED = _bool_env("AI_ENABLED", False)
AI_PROVIDER = (os.getenv("AI_PROVIDER") or "openai").strip().lower()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip() or None
AI_MODEL = (os.getenv("AI_MODEL") or "gpt-4o-mini").strip()
AI_TEMPERATURE = _float_env("AI_TEMPERATURE", 0.2)
AI_MAX_OUTPUT_TOKENS = _int_env("AI_MAX_OUTPUT_TOKENS", 500)
# Default relative to backend dir: backend/docs/assistant_kb
_ASSISTANT_KB_PATH_RAW = (os.getenv("ASSISTANT_KB_PATH") or "docs/assistant_kb").strip()
ASSISTANT_DISCLAIMER_MODE = (os.getenv("ASSISTANT_DISCLAIMER_MODE") or "strict").strip().lower()


def is_configured() -> bool:
    """
    True only when AI is enabled and the provider has the required key.
    When AI_ENABLED=false, returns False and no env vars are required.
    """
    if not AI_ENABLED:
        return False
    if AI_PROVIDER == "openai":
        return bool(OPENAI_API_KEY)
    # Future: other providers
    return False


def get_openai_api_key() -> Optional[str]:
    """Returns OPENAI_API_KEY or None. Never expose this to the frontend."""
    return OPENAI_API_KEY


def get_assistant_kb_path() -> Path:
    """Resolved path to assistant KB directory (default backend/docs/assistant_kb)."""
    p = Path(_ASSISTANT_KB_PATH_RAW)
    if not p.is_absolute():
        p = _BACKEND_DIR / p
    return p


def get_public_config() -> Dict[str, Any]:
    """
    Safe config for any frontend or status endpoint. Never includes API keys.
    """
    return {
        "ai_enabled": AI_ENABLED,
        "ai_configured": is_configured(),
        "ai_provider": AI_PROVIDER,
        "ai_model": AI_MODEL,
        "assistant_disclaimer_mode": ASSISTANT_DISCLAIMER_MODE,
    }
