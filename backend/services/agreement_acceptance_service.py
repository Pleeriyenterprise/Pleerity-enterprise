"""Create and validate agreement acceptances (pre-payment)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from database import database
from models import AuditAction
from models.agreements import (
    COL_AGREEMENT_ACCEPTANCES,
    COL_AGREEMENT_TEMPLATE_VERSIONS,
    COL_AGREEMENT_TEMPLATES,
    DEFAULT_TEMPLATE_CODE,
    AgreementAcceptanceStatus,
)
from services.agreement_catalog_service import get_current_published_bundle, get_system_document_settings
from services.agreement_commercial_snapshot import build_commercial_snapshot, commercial_snapshots_match
from services.agreement_document_authority import compile_agreement_document
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


def _build_render_context(
    *,
    snap: Dict[str, Any],
    settings: Dict[str, Any],
    accepted_by_name: str,
    acceptance_timestamp: str,
    version_number: int,
) -> Dict[str, Any]:
    return {
        "provider_company_name": settings.get("provider_company_name") or "Pleerity Enterprise Ltd",
        "client_full_name": snap.get("client_full_name") or "",
        "client_company_name": snap.get("client_company_name") or "",
        "client_email": snap.get("client_email") or "",
        "client_address": snap.get("client_address") or "",
        "plan_name": snap.get("plan_label") or snap.get("selected_plan_code") or "",
        "billing_interval": snap.get("billing_interval") or "month",
        "monthly_fee": f"£{int(snap.get('billing_amount_minor') or 0) / 100:.2f}",
        "currency": snap.get("currency") or "GBP",
        "onboarding_fee_line": (
            f"£{int(snap.get('onboarding_fee_minor') or 0) / 100:.2f}"
            if int(snap.get("onboarding_fee_minor") or 0) > 0
            else "None"
        ),
        "accepted_signatory_name": accepted_by_name.strip()[:200],
        "acceptance_timestamp": acceptance_timestamp,
        "agreement_version": str(version_number or 1),
        "support_email": settings.get("provider_email") or "",
    }


async def create_acceptance(
    *,
    client_id: str,
    intake_session_id: str,
    template_code: str,
    acceptance_text_snapshot: str,
    accepted_by_name: str,
    accepted_by_email: str,
    document_submission_method: Optional[str] = None,
    assisted_upload_consent_accepted: Optional[bool] = None,
    assisted_upload_consent_timestamp: Optional[str] = None,
    client_rendered_agreement_hash: Optional[str] = None,
    client_rendered_agreement_snapshot: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Create acceptance row. Returns (acceptance_doc_without_internal_keys, error_message).
    """
    db = database.get_db()
    tpl, ver = await get_current_published_bundle(template_code or DEFAULT_TEMPLATE_CODE)
    if not tpl or not ver:
        return None, "AGREEMENT_NOT_CONFIGURED"
    template_id = str(tpl.get("template_id") or "")
    version_id = str(ver.get("version_id") or "")
    if not template_id or not version_id or ver.get("status") != "published":
        return None, "AGREEMENT_NOT_CONFIGURED"

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1, "intake_session_id": 1})
    if not client:
        return None, "CLIENT_NOT_FOUND"
    stored_session = str(client.get("intake_session_id") or "").strip()
    provided_session = str(intake_session_id or "").strip()
    if not stored_session or stored_session != provided_session:
        return None, "INTAKE_SESSION_INVALID"

    snap = await build_commercial_snapshot(
        client_id=client_id,
        template_id=template_id,
        template_version_id=version_id,
    )
    if not snap:
        return None, "CLIENT_NOT_FOUND"

    settings = await get_system_document_settings()

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")
    intake_snapshot: Dict[str, Any] = {
        **snap,
        "acceptance_timestamp": now_iso,
        "acceptance_text_shown": acceptance_text_snapshot.strip()[:4000],
        "service_code": "COMPLIANCE_VAULT_PRO",
    }
    render_context = _build_render_context(
        snap=snap,
        settings=settings,
        accepted_by_name=accepted_by_name,
        acceptance_timestamp=now_iso,
        version_number=int(ver.get("version_number") or 1),
    )
    rendered_result = compile_agreement_document(
        template_name=str(tpl.get("name") or "Service Agreement"),
        template_code=str(tpl.get("code") or DEFAULT_TEMPLATE_CODE),
        template_id=template_id,
        version_id=version_id,
        version_number=int(ver.get("version_number") or 1),
        published_at=ver.get("published_at"),
        effective_from=ver.get("effective_from"),
        title=str(ver.get("title") or ""),
        subtitle=str(ver.get("subtitle") or ""),
        content_blocks=list(ver.get("content_blocks") or []),
        render_context=render_context,
    )
    if not rendered_result.get("valid"):
        logger.warning(
            "Agreement acceptance blocked due to invalid render client_id=%s issues=%s",
            client_id,
            rendered_result.get("issues"),
        )
        return None, "AGREEMENT_RENDER_INVALID"

    acceptance_id = str(uuid.uuid4())
    doc: Dict[str, Any] = {
        "acceptance_id": acceptance_id,
        "client_id": client_id,
        "intake_session_id": stored_session or provided_session,
        "template_id": template_id,
        "template_version_id": version_id,
        "template_code": template_code or DEFAULT_TEMPLATE_CODE,
        "status": AgreementAcceptanceStatus.RECORDED.value,
        "accepted_at": now_iso,
        "accepted_by_name": accepted_by_name.strip()[:200],
        "accepted_by_email": accepted_by_email.strip()[:320],
        "accepted_via": "checkout",
        "ip_address": (ip_address or "")[:120] or None,
        "user_agent": (user_agent or "")[:500] or None,
        "acceptance_text_snapshot": acceptance_text_snapshot.strip()[:4000],
        "intake_snapshot": intake_snapshot,
        "document_submission_method": (document_submission_method or "").strip()[:32] or None,
        "assisted_upload_consent_accepted": bool(assisted_upload_consent_accepted),
        "assisted_upload_consent_timestamp": (
            (assisted_upload_consent_timestamp or "").strip()[:64]
            if bool(assisted_upload_consent_accepted)
            else None
        ),
        "agreement_render_validation": {
            "valid": True,
            "issues": [],
            "render_hash_sha256": str(rendered_result.get("render_hash_sha256") or ""),
            "validated_at": now_iso,
            "client_render_hash": (client_rendered_agreement_hash or "").strip()[:128] or None,
        },
        "rendered_agreement_snapshot": rendered_result.get("document") or {},
        "client_rendered_agreement_snapshot_ref": (
            str(client_rendered_agreement_snapshot.get("template_version_id") or "")[:120]
            if isinstance(client_rendered_agreement_snapshot, dict)
            else None
        ),
        "payment_status_at_acceptance": "pending",
        "stripe_checkout_session_id": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await db[COL_AGREEMENT_ACCEPTANCES].insert_one(doc)
    await create_audit_log(
        action=AuditAction.AGREEMENT_ACCEPTANCE_RECORDED,
        actor_role=None,
        client_id=client_id,
        resource_type="agreement_acceptance",
        resource_id=acceptance_id,
        metadata={
            "template_id": template_id,
            "template_version_id": version_id,
            "template_code": template_code or DEFAULT_TEMPLATE_CODE,
        },
    )
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out, None


async def validate_acceptance_for_checkout(
    *,
    client_id: str,
    acceptance_id: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Returns (acceptance_doc, error_code) where error_code is machine string for HTTP mapping.
    """
    db = database.get_db()
    acc = await db[COL_AGREEMENT_ACCEPTANCES].find_one({"acceptance_id": acceptance_id}, {"_id": 0})
    if not acc:
        return None, "ACCEPTANCE_NOT_FOUND"
    if acc.get("client_id") != client_id:
        return None, "ACCEPTANCE_CLIENT_MISMATCH"
    if acc.get("status") not in (
        AgreementAcceptanceStatus.RECORDED.value,
        AgreementAcceptanceStatus.CHECKOUT_SESSION_CREATED.value,
    ):
        return None, "ACCEPTANCE_NOT_VALID_FOR_CHECKOUT"
    render_validation = acc.get("agreement_render_validation") or {}
    if render_validation.get("valid") is not True:
        return None, "ACCEPTANCE_RENDER_INVALID"
    stored_hash = str(render_validation.get("render_hash_sha256") or "").strip()
    if not stored_hash:
        return None, "ACCEPTANCE_RENDER_INVALID"

    ver = await db[COL_AGREEMENT_TEMPLATE_VERSIONS].find_one({"version_id": acc.get("template_version_id")}, {"_id": 0})
    if not ver or ver.get("status") != "published":
        return None, "AGREEMENT_VERSION_NOT_PUBLISHED"

    tpl = await db[COL_AGREEMENT_TEMPLATES].find_one({"template_id": acc.get("template_id")}, {"_id": 0})
    if not tpl or tpl.get("status") != "active":
        return None, "AGREEMENT_TEMPLATE_INACTIVE"

    settings = await get_system_document_settings()
    render_check = compile_agreement_document(
        template_name=str(tpl.get("name") or "Service Agreement"),
        template_code=str(tpl.get("code") or DEFAULT_TEMPLATE_CODE),
        template_id=str(acc.get("template_id") or ""),
        version_id=str(acc.get("template_version_id") or ""),
        version_number=int(ver.get("version_number") or 1),
        published_at=ver.get("published_at"),
        effective_from=ver.get("effective_from"),
        title=str(ver.get("title") or ""),
        subtitle=str(ver.get("subtitle") or ""),
        content_blocks=list(ver.get("content_blocks") or []),
        render_context=_build_render_context(
            snap=acc.get("intake_snapshot") or {},
            settings=settings,
            accepted_by_name=str(acc.get("accepted_by_name") or ""),
            acceptance_timestamp=str(acc.get("accepted_at") or ""),
            version_number=int(ver.get("version_number") or 1),
        ),
    )
    if (not render_check.get("valid")) or str(render_check.get("render_hash_sha256") or "") != stored_hash:
        return None, "ACCEPTANCE_RENDER_INVALID"

    snap_accepted = acc.get("intake_snapshot") or {}
    current = await build_commercial_snapshot(
        client_id=client_id,
        template_id=str(acc.get("template_id") or ""),
        template_version_id=str(acc.get("template_version_id") or ""),
    )
    if not current:
        return None, "CLIENT_NOT_FOUND"
    ok, mismatches = commercial_snapshots_match(snap_accepted, current)
    if not ok:
        await create_audit_log(
            action=AuditAction.AGREEMENT_CHECKOUT_BLOCKED_MISMATCH,
            actor_role=None,
            client_id=client_id,
            resource_type="agreement_acceptance",
            resource_id=acceptance_id,
            metadata={"mismatches": mismatches},
        )
        return None, "ACCEPTANCE_COMMERCIAL_MISMATCH"

    return acc, None


async def mark_acceptance_checkout_started(acceptance_id: str, stripe_checkout_session_id: str) -> None:
    """Persist Stripe session on acceptance. Raises if acceptance row missing (checkout must not succeed silently)."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    res = await db[COL_AGREEMENT_ACCEPTANCES].update_one(
        {"acceptance_id": acceptance_id},
        {
            "$set": {
                "stripe_checkout_session_id": stripe_checkout_session_id,
                "status": AgreementAcceptanceStatus.CHECKOUT_SESSION_CREATED.value,
                "updated_at": now,
            }
        },
    )
    if res.matched_count == 0:
        raise ValueError(f"acceptance_not_found:{acceptance_id}")


async def mark_acceptance_payment_completed(acceptance_id: str) -> None:
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    await db[COL_AGREEMENT_ACCEPTANCES].update_one(
        {"acceptance_id": acceptance_id},
        {"$set": {"status": AgreementAcceptanceStatus.PAYMENT_COMPLETED.value, "updated_at": now}},
    )
