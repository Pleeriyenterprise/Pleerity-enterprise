"""Shared hourly rate limit for public marketing / contact forms (single policy surface)."""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from config.security_limits import security_limits
from models import AuditAction
from utils.audit import create_audit_log
from utils.rate_limiter import rate_limiter, log_rate_limit_event


def client_ip_from_request(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"


async def enforce_public_form_rate(request: Request, scope: str) -> None:
    """
    Per-IP hourly cap for public submissions (contact, partnerships, etc.).
    scope: short label for the rate key (e.g. contact, partnership).
    """
    ip = client_ip_from_request(request)
    key = f"public_form:{scope}:{ip}"
    ok, msg = await rate_limiter.check_rate_limit(
        key,
        security_limits.public_form_per_ip_per_hour,
        60,
    )
    if not ok:
        log_rate_limit_event("public_form", f"{scope}:{ip}", ip)
        await create_audit_log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            metadata={"scope": "public_form", "form": scope, "ip": ip},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=msg or "Too many submissions from this network. Please try again later.",
        )
