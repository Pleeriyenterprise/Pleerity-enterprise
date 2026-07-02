"""Governed actor labels for report chronology."""

from __future__ import annotations

from typing import Any, Optional


def present_actor_label(
    role: Any = None,
    *,
    actor_id: Any = None,
    metadata: Optional[dict] = None,
) -> str:
    """Return a professional actor label; fall back to System only when unknown."""
    md = metadata or {}
    raw = str(role or md.get("actor_role") or "").strip()
    upper = raw.upper()

    if upper in ("ROLE_CLIENT", "CLIENT", "PORTAL_USER", "USER"):
        return "Landlord"
    if upper in ("ROLE_PROPERTY_MANAGER", "PROPERTY_MANAGER"):
        return "Property Manager"
    if upper in ("ROLE_ADMIN", "ADMIN", "SUPPORT"):
        return "Compliance Administrator"
    if upper in ("SYSTEM", "ROLE_SYSTEM", ""):
        action = str(md.get("action") or md.get("event_type") or "").upper()
        if "DOCUMENT" in action and ("VERIFY" in action or "UPLOAD" in action):
            return "Evidence Verification Service"
        if any(p in action for p in ("RISK", "SCORE", "COMPLIANCE", "RECALC", "REGEN")):
            return "Automated Compliance Monitoring"
        if "REPORT" in action or "AUDIT_PACK" in action:
            return "Portfolio Monitoring"
        if actor_id and str(actor_id).strip() and str(actor_id).lower() not in ("system", "none"):
            return "Automated Compliance Monitoring"
        return "Automated Compliance Monitoring"
    if upper.startswith("ROLE_"):
        return raw[5:].replace("_", " ").title()
    if raw:
        return raw.replace("_", " ").title()
    return "Automated Compliance Monitoring"
