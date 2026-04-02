"""Hard caps for monthly digest assembly and PDF (portfolio scale)."""
from __future__ import annotations

import os


def _int_env(name: str, default: int, *, min_v: int = 1, max_v: int = 50_000) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        return max(min_v, min(v, max_v))
    except ValueError:
        return default


# Override via environment for large portfolios (ops-tuned).
DIGEST_MAX_PROPERTIES_FETCH = _int_env("DIGEST_MAX_PROPERTIES_FETCH", 500)
DIGEST_MAX_REQUIREMENTS_FETCH = _int_env("DIGEST_MAX_REQUIREMENTS_FETCH", 5000)
DIGEST_PDF_MAX_REQUIREMENT_ROWS = _int_env("DIGEST_PDF_MAX_REQUIREMENT_ROWS", 200)
# 0 = omit “top properties at risk” block from digest email
DIGEST_EMAIL_TOP_PROPERTIES_AT_RISK = _int_env("DIGEST_EMAIL_TOP_PROPERTIES_AT_RISK", 5, min_v=0, max_v=50)
