"""Feature flag for PR5 policy-backed portfolio override switch."""

from __future__ import annotations

import os


def is_feature_policy_backed_portfolio_override_enabled(client_id: str | None = None) -> bool:
    enabled = os.getenv("FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE", "").strip().lower() in ("1", "true", "yes")
    if not enabled:
        return False
    raw = (os.getenv("FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE_TENANT_ALLOWLIST") or "").strip()
    if not raw:
        return True
    if not client_id:
        return False
    allowed = {x.strip() for x in raw.split(",") if x.strip()}
    return client_id in allowed
