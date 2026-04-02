"""
Structured API errors for client/contractor-facing flows: consistent JSON detail + server logging.
FastAPI accepts dict ``detail``; clients should read ``message`` and ``error_code``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def structured_error(
    error_code: str,
    message: str,
    *,
    retry_suggested: bool = False,
    **extra: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "error_code": error_code,
        "message": message,
        "retry_suggested": retry_suggested,
    }
    for k, v in extra.items():
        if v is not None:
            payload[k] = v
    return payload


def validation_error_detail(
    message: str,
    *,
    error_code: str = "VALIDATION_ERROR",
    retry_suggested: bool = False,
) -> Dict[str, Any]:
    """FastAPI HTTPException ``detail`` payload for 400-style validation failures."""
    return structured_error(error_code, message, retry_suggested=retry_suggested)


def conflict_error_detail(
    message: str,
    *,
    error_code: str = "CONFLICT",
) -> Dict[str, Any]:
    return structured_error(error_code, message, retry_suggested=False)


def log_api_error(
    log: logging.Logger,
    *,
    endpoint: str,
    error_type: str,
    message: str,
    user_id: Optional[str] = None,
    exc: Optional[BaseException] = None,
    level: int = logging.WARNING,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    log.log(
        level,
        "api_error ts=%s endpoint=%s error_type=%s user_id=%s message=%s",
        ts,
        endpoint,
        error_type,
        user_id or "-",
        message,
        exc_info=exc is not None,
    )
