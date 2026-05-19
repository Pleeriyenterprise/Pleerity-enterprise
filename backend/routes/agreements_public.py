"""Public agreement APIs (pre-auth checkout): current published version + acceptance creation."""

from __future__ import annotations

import logging

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
    """
    Published template **metadata** for catalog/health checks.

    Does **not** return a checkout-grade ``document_structure`` (no demo-filled placeholders).
    Intake Step 5 must use ``POST /api/intake/agreement-preview`` for an authoritative preview.
    """
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
        content_blocks=[],
        document_structure=None,
        published_at=ver.get("published_at"),
        effective_from=ver.get("effective_from"),
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
    pilot_invite_doc = None
    invite_raw = (body.invite_code or "").strip()
    if invite_raw:
        from database import database
        from models.pilot_invite import PilotInvitePublicError
        from services.pilot_invite_service import validate_invite_for_checkout

        db = database.get_db()
        client = await db.clients.find_one(
            {"client_id": body.client_id},
            {"_id": 0, "billing_plan": 1, "contact_email": 1, "email": 1},
        )
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": "CLIENT_NOT_FOUND"})
        try:
            pilot_invite_doc, _ = await validate_invite_for_checkout(
                code=invite_raw,
                plan_code=str(client.get("billing_plan") or "PLAN_1_SOLO"),
                email=client.get("contact_email") or client.get("email"),
                for_checkout=False,
                entry_channel=body.invite_entry_channel,
                log_audit=False,
                record_attempts=False,
            )
        except PilotInvitePublicError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": e.error_code, "message": e.message},
            )
    doc, err = await create_acceptance(
        client_id=body.client_id,
        intake_session_id=body.intake_session_id,
        template_code=body.template_code,
        acceptance_text_snapshot=body.acceptance_text_snapshot,
        accepted_by_name=body.accepted_by_name,
        accepted_by_email=body.accepted_by_email,
        document_submission_method=body.document_submission_method,
        assisted_upload_consent_accepted=body.assisted_upload_consent_accepted,
        assisted_upload_consent_timestamp=body.assisted_upload_consent_timestamp,
        client_rendered_agreement_hash=body.rendered_agreement_hash,
        client_rendered_agreement_snapshot=body.rendered_agreement_snapshot,
        pilot_invite_doc=pilot_invite_doc,
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
    if err == "AGREEMENT_RENDER_INVALID":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": err,
                "message": "The service agreement could not be safely rendered. Please refresh and review the agreement again.",
            },
        )
    if err == "AGREEMENT_RENDER_HASH_MISSING":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": err,
                "message": "Agreement render digest is required. Refresh the page and review the agreement again.",
            },
        )
    if err == "AGREEMENT_RENDER_HASH_MISMATCH":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": err,
                "message": "The agreement shown no longer matches the server. Refresh and review the agreement again before paying.",
            },
        )
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": err})
    return doc
