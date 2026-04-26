"""Checkout-grade agreement preview for intake (same compile path as acceptance)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from database import database
from models.core import IntakeFormData
from services.agreement_catalog_service import acceptance_text_default, get_current_published_bundle, get_system_document_settings
from services.agreement_commercial_snapshot import (
    build_commercial_snapshot,
    build_commercial_snapshot_from_intake_form,
)
from services.agreement_document_authority import compile_agreement_document
from services.agreement_render_context import (
    PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
    build_agreement_render_context,
    validate_checkout_grade_render_context,
)

logger = logging.getLogger(__name__)


async def build_intake_agreement_preview(
    *,
    intake_session_id: str,
    client_id: Optional[str],
    intake: Optional[IntakeFormData],
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[list]]:
    """
    Returns (payload_dict, error_code, validation_errors).

    When ``client_id`` is set, the commercial snapshot is read from Mongo (authoritative post-submit).
    Otherwise ``intake`` must be provided and must carry the same ``intake_session_id`` as the wizard.
    """
    sid = (intake_session_id or "").strip()
    if len(sid) < 8:
        return None, "INTAKE_SESSION_INVALID", None

    tpl, ver = await get_current_published_bundle()
    if not tpl or not ver:
        return None, "AGREEMENT_NOT_CONFIGURED", None

    template_id = str(tpl.get("template_id") or "")
    version_id = str(ver.get("version_id") or "")
    if not template_id or not version_id or ver.get("status") != "published":
        return None, "AGREEMENT_NOT_CONFIGURED", None

    db = database.get_db()
    snap: Optional[Dict[str, Any]] = None

    if client_id and str(client_id).strip():
        cid = str(client_id).strip()
        client = await db.clients.find_one({"client_id": cid}, {"_id": 0, "client_id": 1, "intake_session_id": 1})
        if not client:
            return None, "CLIENT_NOT_FOUND", None
        if str(client.get("intake_session_id") or "").strip() != sid:
            return None, "INTAKE_SESSION_INVALID", None
        snap = await build_commercial_snapshot(client_id=cid, template_id=template_id, template_version_id=version_id)
    else:
        if intake is None:
            return None, "INTAKE_BODY_REQUIRED", None
        if str(intake.intake_session_id or "").strip() != sid:
            return None, "INTAKE_SESSION_INVALID", None
        snap = build_commercial_snapshot_from_intake_form(intake, template_id, version_id)

    if not snap:
        return None, "CLIENT_NOT_FOUND", None

    settings = await get_system_document_settings()
    signatory = str(snap.get("client_full_name") or "").strip()
    if intake and not client_id:
        signatory = (intake.full_name or "").strip() or signatory

    render_ctx = build_agreement_render_context(
        commercial_snapshot=snap,
        settings=settings,
        accepted_signatory_name=signatory,
        acceptance_timestamp_display=PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
        agreement_version_number=int(ver.get("version_number") or 1),
    )
    ok, v_errs = validate_checkout_grade_render_context(
        render_ctx,
        billing_amount_minor=int(snap.get("billing_amount_minor") or 0),
        preview_mode=True,
    )
    if not ok:
        logger.info("Agreement preview validation failed: %s", v_errs)
        return None, "AGREEMENT_RENDER_INVALID", v_errs

    template_name = str(tpl.get("name") or "Service Agreement")
    rendered = compile_agreement_document(
        template_name=template_name,
        template_code=str(tpl.get("code") or ""),
        template_id=template_id,
        version_id=version_id,
        version_number=int(ver.get("version_number") or 1),
        published_at=ver.get("published_at"),
        effective_from=ver.get("effective_from"),
        title=str(ver.get("title") or ""),
        subtitle=str(ver.get("subtitle") or ""),
        content_blocks=list(ver.get("content_blocks") or []),
        render_context=render_ctx,
    )
    if not rendered.get("valid"):
        return None, "AGREEMENT_RENDER_INVALID", list(rendered.get("issues") or [])

    doc = rendered.get("document") or {}
    payload: Dict[str, Any] = {
        "template_id": template_id,
        "template_code": str(tpl.get("code") or ""),
        "template_version_id": version_id,
        "version_number": int(ver.get("version_number") or 1),
        "title": str(ver.get("title") or ""),
        "subtitle": ver.get("subtitle"),
        "content_blocks": list(ver.get("content_blocks") or []),
        "document_structure": doc,
        "published_at": ver.get("published_at"),
        "effective_from": ver.get("effective_from"),
        "acceptance_text_required": acceptance_text_default(template_name),
        "render_hash_sha256": str(rendered.get("render_hash_sha256") or ""),
        "acceptance_timestamp_note": PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER,
    }
    return payload, None, None
