"""
Session runtime validation middleware helpers (ILP-5).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from database import database
from services.account_session_runtime_service import (
    SessionRefreshAction,
    SessionRuntimeService,
    is_client_portal_user,
)

REFRESH_HEADER = "X-Session-Refresh-Required"
REFRESH_REASON_HEADER = "X-Session-Refresh-Reason"
RUNTIME_VERSION_HEADER = "X-Lifecycle-Runtime-Version"
ENTITLEMENTS_VERSION_HEADER = "X-Session-Entitlements-Version"


def _parse_int_header(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def apply_session_runtime_validation(request: Request, user: dict) -> None:
    """
    Validate session version hints against Runtime Contract for client portal users.
    Sets request.state.session_validation; does not block on version drift (frontend refreshes).
    """
    request.state.session_validation = None
    if not is_client_portal_user(user):
        return

    header_runtime = _parse_int_header(request.headers.get("X-Client-Runtime-Version"))
    header_entitlements = _parse_int_header(request.headers.get("X-Client-Entitlements-Version"))

    service = SessionRuntimeService(database.get_db())
    validation = await service.validate_for_user(
        user,
        header_runtime_version=header_runtime,
        header_entitlements_version=header_entitlements,
    )
    request.state.session_validation = validation
    request.state.session_refresh_required = validation.force_refresh


class SessionRuntimeResponseMiddleware(BaseHTTPMiddleware):
    """Attach session runtime refresh headers when validation ran on the request."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        attach_session_runtime_response_headers(request, response)
        return response


def attach_session_runtime_response_headers(request: Request, response: Response) -> None:
    validation = getattr(request.state, "session_validation", None)
    if not validation:
        return
    if validation.runtime_version is not None:
        response.headers[RUNTIME_VERSION_HEADER] = str(validation.runtime_version)
    if validation.entitlements_version is not None:
        response.headers[ENTITLEMENTS_VERSION_HEADER] = str(validation.entitlements_version)
    if validation.force_refresh:
        response.headers[REFRESH_HEADER] = "true"
        if validation.reasons:
            response.headers[REFRESH_REASON_HEADER] = ",".join(validation.reasons)
    if validation.action == SessionRefreshAction.FORCE_REAUTH:
        response.headers[REFRESH_HEADER] = "force_reauth"
