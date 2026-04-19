"""Issue immutable agreement PDF after successful subscription payment."""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from database import database
from models import AuditAction
from models.agreements import (
    COL_AGREEMENT_ACCEPTANCES,
    COL_AGREEMENT_TEMPLATE_VERSIONS,
    COL_ISSUED_AGREEMENTS,
    GRIDFS_AGREEMENT_BUCKET,
    IssuedAgreementOutcome,
)
from services.agreement_acceptance_service import mark_acceptance_payment_completed
from services.agreement_catalog_service import get_system_document_settings
from services.agreement_pdf import build_agreement_pdf_bytes
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


def _money_gbp(minor: int) -> str:
    v = int(minor or 0)
    return f"£{v / 100:.2f}"


def _build_render_context(
    *,
    version_doc: Dict[str, Any],
    acceptance_doc: Dict[str, Any],
    intake_snapshot: Dict[str, Any],
    settings: Dict[str, Any],
    crn: str,
    payment_reference: str,
    agreement_date_display: str,
) -> Dict[str, Any]:
    minor = int(intake_snapshot.get("billing_amount_minor") or 0)
    ob = int(intake_snapshot.get("onboarding_fee_minor") or 0)
    ob_line = "None (already satisfied or not applicable)." if ob <= 0 else _money_gbp(ob)

    return {
        "provider_company_name": settings.get("provider_company_name") or "Pleerity Enterprise Ltd",
        "provider_address": settings.get("provider_address") or "",
        "provider_email": settings.get("provider_email") or "",
        "provider_phone": settings.get("provider_phone") or "",
        "provider_signature_image_url": settings.get("provider_signature_image_url") or "",
        "provider_logo_image_url": settings.get("provider_logo_image_url") or "",
        "client_full_name": intake_snapshot.get("client_full_name") or "",
        "client_company_name": intake_snapshot.get("client_company_name") or "",
        "client_address": intake_snapshot.get("client_address") or "",
        "client_email": intake_snapshot.get("client_email") or "",
        "client_phone": intake_snapshot.get("client_phone") or "",
        "client_crn": crn,
        "plan_name": intake_snapshot.get("plan_label") or intake_snapshot.get("selected_plan_code") or "",
        "monthly_fee": _money_gbp(minor),
        "billing_interval": intake_snapshot.get("billing_interval") or "month",
        "currency": intake_snapshot.get("currency") or "GBP",
        "onboarding_fee_line": ob_line,
        "agreement_date": agreement_date_display,
        "agreement_version": str(version_doc.get("version_number") or 1),
        "accepted_signatory_name": acceptance_doc.get("accepted_by_name") or "",
        "acceptance_timestamp": acceptance_doc.get("accepted_at") or "",
        "payment_reference": payment_reference,
    }


async def _store_pdf_gridfs(
    *,
    pdf_bytes: bytes,
    issued_id: str,
    client_id: str,
    filename: str,
) -> str:
    db = database.get_db()
    bucket = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_AGREEMENT_BUCKET)
    grid_in = bucket.open_upload_stream(
        filename,
        metadata={"issued_id": issued_id, "client_id": client_id, "kind": "issued_agreement_pdf"},
    )
    await grid_in.write(pdf_bytes)
    await grid_in.close()
    return str(grid_in._id)


async def issue_agreement_for_subscription_payment(
    *,
    client_id: str,
    acceptance_id: str,
    template_version_id_from_metadata: str,
    payment_reference: str,
    stripe_event_id: Optional[str],
    crn: str,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Idempotent per (client_id, acceptance_id, stripe_event_id): if already issued successfully, returns ok.

    Returns (success, error_message, issued_doc_summary).
    """
    db = database.get_db()
    idempotency_key = stripe_event_id or payment_reference

    existing_ok = await db[COL_ISSUED_AGREEMENTS].find_one(
        {
            "client_id": client_id,
            "acceptance_id": acceptance_id,
            "outcome": IssuedAgreementOutcome.ISSUED.value,
            "stripe_event_id": idempotency_key,
        },
        {"_id": 0},
    )
    if existing_ok:
        return True, None, existing_ok

    existing_same_payment = await db[COL_ISSUED_AGREEMENTS].find_one(
        {
            "client_id": client_id,
            "acceptance_id": acceptance_id,
            "payment_reference": payment_reference,
            "outcome": IssuedAgreementOutcome.ISSUED.value,
        },
        {"_id": 0},
    )
    if existing_same_payment:
        return True, None, existing_same_payment

    acc = await db[COL_AGREEMENT_ACCEPTANCES].find_one({"acceptance_id": acceptance_id}, {"_id": 0})
    if not acc or acc.get("client_id") != client_id:
        return await _fail(
            client_id=client_id,
            acceptance_id=acceptance_id,
            payment_reference=payment_reference,
            stripe_event_id=idempotency_key,
            reason="ACCEPTANCE_NOT_FOUND_OR_MISMATCH",
            template_version_id=template_version_id_from_metadata,
        )
    if (template_version_id_from_metadata or "").strip() and acc.get("template_version_id") != template_version_id_from_metadata:
        return await _fail(
            client_id=client_id,
            acceptance_id=acceptance_id,
            payment_reference=payment_reference,
            stripe_event_id=idempotency_key,
            reason="METADATA_VERSION_MISMATCH",
            template_version_id=template_version_id_from_metadata,
        )

    ver = await db[COL_AGREEMENT_TEMPLATE_VERSIONS].find_one({"version_id": acc.get("template_version_id")}, {"_id": 0})
    if not ver or ver.get("status") != "published":
        return await _fail(
            client_id=client_id,
            acceptance_id=acceptance_id,
            payment_reference=payment_reference,
            stripe_event_id=idempotency_key,
            reason="VERSION_NOT_FOUND_OR_NOT_PUBLISHED",
            template_version_id=template_version_id_from_metadata,
        )

    if not (crn or "").strip():
        return await _fail(
            client_id=client_id,
            acceptance_id=acceptance_id,
            payment_reference=payment_reference,
            stripe_event_id=idempotency_key,
            reason="CRN_MISSING",
            template_version_id=template_version_id_from_metadata,
        )

    settings = await get_system_document_settings()
    intake_snapshot = acc.get("intake_snapshot") or {}
    now = datetime.now(timezone.utc)
    agreement_date_display = now.strftime("%d %B %Y")

    render_ctx = _build_render_context(
        version_doc=ver,
        acceptance_doc=acc,
        intake_snapshot=intake_snapshot,
        settings=settings,
        crn=crn,
        payment_reference=payment_reference,
        agreement_date_display=agreement_date_display,
    )

    render_snapshot = {**render_ctx, "template_version_id": ver.get("version_id"), "template_id": acc.get("template_id")}

    issued_id = str(uuid.uuid4())
    title = str(ver.get("title") or "Service Agreement")
    subtitle = str(ver.get("subtitle") or "")
    blocks: List[Dict[str, Any]] = list(ver.get("content_blocks") or [])

    try:
        pdf_bytes = build_agreement_pdf_bytes(
            title=title,
            subtitle=subtitle,
            content_blocks=blocks,
            render_ctx=render_ctx,
            brand_primary=str(settings.get("brand_primary_color") or "#0B1D3A"),
            footer_text=str(settings.get("default_footer_text") or ""),
        )
    except Exception as e:
        logger.exception("Agreement PDF build failed client_id=%s acceptance_id=%s", client_id, acceptance_id)
        return await _fail(
            client_id=client_id,
            acceptance_id=acceptance_id,
            payment_reference=payment_reference,
            stripe_event_id=idempotency_key,
            reason=f"PDF_BUILD_ERROR:{e}",
            template_version_id=template_version_id_from_metadata,
            extra={"exception_type": type(e).__name__},
        )

    filename = f"agreement_{issued_id[:8]}_{client_id[:8]}.pdf"
    try:
        gridfs_id = await _store_pdf_gridfs(
            pdf_bytes=pdf_bytes, issued_id=issued_id, client_id=client_id, filename=filename
        )
    except Exception as e:
        logger.exception("Agreement PDF storage failed client_id=%s", client_id)
        return await _fail(
            client_id=client_id,
            acceptance_id=acceptance_id,
            payment_reference=payment_reference,
            stripe_event_id=idempotency_key,
            reason=f"PDF_STORAGE_ERROR:{e}",
            template_version_id=template_version_id_from_metadata,
        )

    now_iso = now.isoformat().replace("+00:00", "Z")
    issued_doc: Dict[str, Any] = {
        "issued_id": issued_id,
        "client_id": client_id,
        "acceptance_id": acceptance_id,
        "template_id": acc.get("template_id"),
        "template_version_id": acc.get("template_version_id"),
        "outcome": IssuedAgreementOutcome.ISSUED.value,
        "is_current": True,
        "supersedes_issued_agreement_id": None,
        "superseded_by_issued_agreement_id": None,
        "correction_reason": None,
        "issued_at": now_iso,
        "issued_by_event": "checkout.session.completed",
        "payment_reference": payment_reference,
        "stripe_event_id": idempotency_key,
        "crn": crn,
        "render_data_snapshot": render_snapshot,
        "document_files": {
            "pdf_filename": filename,
            "pdf_gridfs_id": gridfs_id,
        },
        "email_delivery": {"sent": False},
        "failure_reason": None,
        "created_at": now_iso,
    }

    await db[COL_ISSUED_AGREEMENTS].update_many(
        {"client_id": client_id, "outcome": IssuedAgreementOutcome.ISSUED.value, "is_current": True},
        {"$set": {"is_current": False, "superseded_by_issued_agreement_id": issued_id, "updated_at": now_iso}},
    )

    await db[COL_ISSUED_AGREEMENTS].insert_one(issued_doc)
    await mark_acceptance_payment_completed(acceptance_id)

    await create_audit_log(
        action=AuditAction.AGREEMENT_ISSUED,
        actor_role=None,
        client_id=client_id,
        resource_type="issued_agreement",
        resource_id=issued_id,
        metadata={
            "acceptance_id": acceptance_id,
            "template_version_id": acc.get("template_version_id"),
            "payment_reference": payment_reference,
            "stripe_event_id": idempotency_key,
        },
    )

    return True, None, {k: v for k, v in issued_doc.items() if k != "_id"}


async def _fail(
    *,
    client_id: str,
    acceptance_id: str,
    payment_reference: str,
    stripe_event_id: Optional[str],
    reason: str,
    template_version_id: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, None]:
    db = database.get_db()
    issued_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    doc: Dict[str, Any] = {
        "issued_id": issued_id,
        "client_id": client_id,
        "acceptance_id": acceptance_id,
        "template_id": None,
        "template_version_id": template_version_id,
        "outcome": IssuedAgreementOutcome.ISSUANCE_FAILED.value,
        "is_current": False,
        "issued_at": now_iso,
        "issued_by_event": "checkout.session.completed",
        "payment_reference": payment_reference,
        "stripe_event_id": stripe_event_id,
        "crn": None,
        "render_data_snapshot": {},
        "document_files": {},
        "email_delivery": {},
        "failure_reason": reason[:2000],
        "created_at": now_iso,
    }
    if extra:
        doc["failure_extra"] = extra
    try:
        await db[COL_ISSUED_AGREEMENTS].insert_one(doc)
    except Exception:
        logger.warning("Could not persist issuance failure row", exc_info=True)
    await create_audit_log(
        action=AuditAction.AGREEMENT_ISSUANCE_FAILED,
        actor_role=None,
        client_id=client_id,
        resource_type="issued_agreement",
        resource_id=issued_id,
        metadata={"acceptance_id": acceptance_id, "reason": reason, "payment_reference": payment_reference},
    )
    return False, reason, None


async def mark_issued_agreement_email_delivered(
    *,
    issued_id: str,
    client_id: str,
    template_key: str,
    stripe_event_id: Optional[str],
    message_id: Optional[str],
) -> None:
    """After SUBSCRIPTION_CONFIRMED (or equivalent) send succeeds, persist delivery proof on the issued row."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    await db[COL_ISSUED_AGREEMENTS].update_one(
        {"issued_id": issued_id, "client_id": client_id},
        {
            "$set": {
                "email_delivery": {
                    "sent": True,
                    "sent_at": now,
                    "template_key": (template_key or "")[:120],
                    "stripe_event_id": (stripe_event_id or "")[:128],
                    "message_id": (message_id or "")[:200],
                },
            }
        },
    )


async def load_issued_pdf_bytes(issued_id: str, client_id: str) -> Optional[bytes]:
    db = database.get_db()
    doc = await db[COL_ISSUED_AGREEMENTS].find_one(
        {"issued_id": issued_id, "client_id": client_id, "outcome": IssuedAgreementOutcome.ISSUED.value},
        {"_id": 0, "document_files": 1},
    )
    if not doc:
        return None
    gf_id = (doc.get("document_files") or {}).get("pdf_gridfs_id")
    if not gf_id:
        return None
    try:
        _oid = ObjectId(str(gf_id))
    except Exception:
        return None
    bucket = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_AGREEMENT_BUCKET)
    buf = io.BytesIO()
    try:
        await bucket.download_to_stream(_oid, buf)
    except Exception:
        return None
    return buf.getvalue()


async def issue_agreement_for_subscription_payment_retry(
    *,
    client_id: str,
    acceptance_id: str,
    payment_reference: str,
    crn: str,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Admin retry after failure: new idempotency key; version taken from acceptance."""
    db = database.get_db()
    acc = await db[COL_AGREEMENT_ACCEPTANCES].find_one({"acceptance_id": acceptance_id, "client_id": client_id}, {"_id": 0})
    if not acc:
        return False, "ACCEPTANCE_NOT_FOUND", None
    vid = str(acc.get("template_version_id") or "")
    rid = f"admin_retry_{uuid.uuid4().hex}"
    await create_audit_log(
        action=AuditAction.AGREEMENT_ISSUANCE_RETRY_SCHEDULED,
        actor_role=None,
        client_id=client_id,
        resource_type="agreement_acceptance",
        resource_id=acceptance_id,
        metadata={"payment_reference": payment_reference, "idempotency": rid},
    )
    return await issue_agreement_for_subscription_payment(
        client_id=client_id,
        acceptance_id=acceptance_id,
        template_version_id_from_metadata=vid,
        payment_reference=payment_reference,
        stripe_event_id=rid,
        crn=crn,
    )
