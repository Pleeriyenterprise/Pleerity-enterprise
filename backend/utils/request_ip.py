"""Consistent client IP for security telemetry and rate limiting (proxy-aware)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request


def get_client_ip(request: "Request") -> str:
    """Prefer X-Forwarded-For, then X-Real-IP, then direct client host."""
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    xr = (request.headers.get("x-real-ip") or "").strip()
    if xr:
        return xr
    return (request.client.host if request.client else "") or "unknown"
