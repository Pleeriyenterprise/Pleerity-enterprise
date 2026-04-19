"""Public agreement APIs (pre-auth checkout): current published version + acceptance creation."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status

from models.agreements import AgreementAcceptanceCreateBody, AgreementCurrentPublishedResponse, DEFAULT_TEMPLATE_CODE
from services.agreement_acceptance_service import create_acceptance
from services.agreement_catalog_service import acceptance_text_default, get_current_published_bundle
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from utils.request_ip import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/agreements", tags=["public-agreements"])

# Per-IP cap on acceptance creation (defense in depth; intake_session_id is the real binding).
PUBLIC_AGREEMENT_ACCEPTANCE_RATE_ATTEMPTS = 30
PUBLIC_AGREEMENT_ACCEPTANCE_RATE_WINDOW_MINUTES = 10


@router.get("/current", response_model=AgreementCurrentPublishedResponse)
async def get_current_published_agreement(template_code: str = DEFAULT_TEMPLATE_CODE):
    tpl, ver = await get_current_published_bundle(template_code)
    if not tpl or not ver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "AGREEMENT_NOT_CONFIGURED", "message": "No published agreement is available yet."},
        )
    template_name = str(tpl.get("name") or "Service Agreement")
    return AgreementCurrentPublishedResponse(
        template_id=str(tpl.get("template_id")),
        template_code=str(tpl.get("code")),
        template_version_id=str(ver.get("version_id")),
        version_number=int(ver.get("version_number") or 1),
        title=str(ver.get("title") or ""),
        subtitle=ver.get("subtitle"),
        content_blocks=list(ver.get("content_blocks") or []),
        published_at=ver.get("published_at"),
        acceptance_text_required=acceptance_text_default(template_name),
    )


@router.post("/acceptance", status_code=status.HTTP_201_CREATED)
async def post_agreement_acceptance(request: Request, body: AgreementAcceptanceCreateBody):
    ip = get_client_ip(request)
    allowed, rl_msg = await rate_limiter.check_rate_limit(
        f"public_agreement_acceptance:{ip}",
        PUBLIC_AGREEMENT_ACCEPTANCE_RATE_ATTEMPTS,
        PUBLIC_AGREEMENT_ACCEPTANCE_RATE_WINDOW_MINUTES,
    )
    if not allowed:
        log_rate_limit_event("public_agreement_acceptance", ip, ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error_code": "RATE_LIMIT_EXCEEDED", "message": rl_msg or "Too many requests. Try again shortly."},
        )
    ua = request.headers.get("user-agent")
    doc, err = await create_acceptance(
        client_id=body.client_id,
        intake_session_id=body.intake_session_id,
        template_code=body.template_code,
        acceptance_text_snapshot=body.acceptance_text_snapshot,
        accepted_by_name=body.accepted_by_name,
        accepted_by_email=body.accepted_by_email,
        ip_address=ip or None,
        user_agent=ua,
    )
    if err == "AGREEMENT_NOT_CONFIGURED":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": err, "message": "Agreement is not configured."},
        )
    if err == "CLIENT_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": err})
    if err == "INTAKE_SESSION_INVALID":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": err,
                "message": "This acceptance does not match your registration session. Refresh the page and complete intake from the start, or contact support.",
            },
        )
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": err})
    return doc
