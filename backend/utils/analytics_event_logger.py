"""
First-party product analytics helpers: consistent user_id / role envelope for Mongo events.

Callers should use record_portal_analytics_event from client (or similar) so inserts stay
non-blocking and allowlisted in product_analytics_service.

Today event meanings and dashboard cutover (legacy ``today_*`` vs ``TODAY_*``) are documented in
``services.product_analytics_service`` module docstring.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def analytics_role_from_jwt_role(role: Optional[str]) -> str:
    """Map portal JWT role to analytics bucket: client | admin | contractor."""
    r = (role or "").strip().upper()
    if r in ("ROLE_CLIENT", "ROLE_CLIENT_ADMIN"):
        return "client"
    if r == "ROLE_ADMIN":
        return "admin"
    if "CONTRACTOR" in r:
        return "contractor"
    return "client"


async def record_portal_analytics_event(
    *,
    client_id: str,
    portal_user_id: Optional[str],
    jwt_role: Optional[str],
    event: str,
    properties: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
) -> None:
    """Fire-and-forget wrapper; failures are logged inside record_event."""
    from services.product_analytics_service import record_event

    role = analytics_role_from_jwt_role(jwt_role)
    await record_event(
        client_id,
        portal_user_id,
        event,
        properties,
        path,
        role=role,
    )
