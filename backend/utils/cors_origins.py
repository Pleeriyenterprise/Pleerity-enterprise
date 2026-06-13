"""
CORS origin allow-list for FastAPI CORSMiddleware.

Vercel preview deployments use per-deployment hostnames such as
``https://pleerity-enterprise-9jig.vercel.app``, which are not the same as the
production alias ``https://pleerity-enterprise.vercel.app``. Without a regex,
Starlette returns ``400 Disallowed CORS origin`` on OPTIONS preflight and the
browser never sends POST (e.g. admin login).
"""
from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

# Always merged when CORS_ORIGINS is set (unless CORS_ORIGINS='*').
CORS_REQUIRED_ORIGINS: Tuple[str, ...] = (
    "https://pleerityenterprise.co.uk",
    "https://www.pleerityenterprise.co.uk",
    "https://staging.pleerityenterprise.co.uk",
    "https://pleerity-enterprise.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)

# Project-scoped Vercel production alias + preview URLs (hash/git branch suffix).
PLEERITY_VERCEL_ORIGIN_REGEX = r"https://pleerity-enterprise(-[a-zA-Z0-9]+)?\.vercel\.app"


def resolve_cors_origins() -> List[str]:
    """Explicit allow-list origins (env + required defaults)."""
    cors_env = (os.environ.get("CORS_ORIGINS") or "").strip()
    if cors_env and cors_env != "*":
        from_env = [o.strip() for o in cors_env.split(",") if o.strip()]
        return list(dict.fromkeys(from_env + list(CORS_REQUIRED_ORIGINS)))
    return list(CORS_REQUIRED_ORIGINS)


def resolve_cors_origin_regex() -> Optional[str]:
    """
    Optional regex for additional allowed origins.

    Override with CORS_ORIGIN_REGEX. Set CORS_ORIGIN_REGEX=none to disable.
    """
    explicit = (os.environ.get("CORS_ORIGIN_REGEX") or "").strip()
    if explicit.lower() in ("none", "off", "false", ""):
        if explicit and explicit.lower() in ("none", "off", "false"):
            return None
    if explicit:
        return explicit
    return PLEERITY_VERCEL_ORIGIN_REGEX


def is_cors_origin_allowed(origin: str, *, origins: List[str], origin_regex: Optional[str]) -> bool:
    if origin in origins:
        return True
    if origin_regex and re.fullmatch(origin_regex, origin):
        return True
    return False
