"""
Client + admin APIs: governed tenant delivery proof and single compliance audit pack contract.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database import database
from middleware import admin_route_guard, client_route_guard
from models import AuditAction
from utils.audit import create_audit_log
from utils.request_ip import get_client_ip

from services.plan_registry import plan_registry
from services import tenant_delivery_proof_service as td_proof
from services import compliance_audit_pack_service as audit_pack

logger = logging.getLogger(__name__)

EMAIL_PROVIDER_PROOF_NOTICE = (
    "Delivery and open/bounce signals come from the email provider when available. "
    "They are operational telemetry, not registered-mail or standalone proof that the tenant received or read the message."
)

client_router = APIRouter(
    prefix="/api/client/compliance",
    tags=["client-compliance-delivery-audit"],
)

admin_router = APIRouter(
    prefix="/api/admin/compliance",
    tags=["admin-compliance-delivery-audit"],
)


def serialize_tenant_delivery_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Stable API shape for UI: explicit lifecycle flags (no fabricated provider events)."""
    r = dict(row)
    ds = str(r.get("delivery_status") or "").upper()
    r["ui_status"] = {
        "initiated": bool(r.get("created_at") or r.get("audit_log_ids")),
        "sent": ds in ("SENT", "DELIVERED", "BOUNCED", "FAILED") or bool(r.get("sent_at")),
        "failed": ds in ("FAILED", "BLOCKED"),
        "bounced": ds == "BOUNCED",
        "delivered": ds == "DELIVERED",
        "opened": bool(r.get("provider_opened_at")),
        "acknowledged": bool(r.get("tenant_acknowledged_at")),
    }
    r["provider_evidence_notice"] = EMAIL_PROVIDER_PROOF_NOTICE
    return r


class TenantDeliveryBody(BaseModel):
    property_id: str = Field(..., min_length=1)
    tenant_portal_user_id: str = Field(..., min_length=1)
    recipient_email: Optional[str] = Field(None, description="Override tenant email; default portal auth email")
    requirement_ids_covered: Optional[List[str]] = None
    purpose: str = Field(default="compliance_tenant_push", max_length=500)
    correlation_id: Optional[str] = Field(None, max_length=128)


class AuditPackGenerateBody(BaseModel):
    property_id: str = Field(..., min_length=1)
    purpose: str = Field(default="governed_audit_export", max_length=500)


@client_router.post("/tenant-delivery")
async def post_tenant_compliance_delivery(request: Request, body: TenantDeliveryBody):
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")

    allowed, msg, details = await plan_registry.enforce_feature(client_id, "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": (details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": msg,
                "feature": "tenant_portal",
                **(details or {}),
            },
        )
    allowed_pdf, msg_pdf, det_pdf = await plan_registry.enforce_feature(client_id, "reports_pdf")
    if not allowed_pdf:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": (det_pdf or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": msg_pdf,
                "feature": "reports_pdf",
                **(det_pdf or {}),
            },
        )

    db = database.get_db()
    tenant_row = await db.portal_users.find_one(
        {"portal_user_id": body.tenant_portal_user_id, "client_id": client_id},
        {"_id": 0, "auth_email": 1},
    )
    recipient = (body.recipient_email or (tenant_row or {}).get("auth_email") or "").strip()
    if not recipient:
        raise HTTPException(status_code=400, detail="recipient_email required (no tenant auth email on file)")

    try:
        result = await td_proof.initiate_tenant_compliance_delivery(
            client_id=client_id,
            property_id=body.property_id.strip(),
            tenant_portal_user_id=body.tenant_portal_user_id.strip(),
            recipient_email=recipient,
            initiated_by_user_id=user.get("portal_user_id") or "",
            initiated_by_role=user.get("role"),
            purpose=body.purpose.strip(),
            requirement_ids_covered=body.requirement_ids_covered,
            correlation_id=body.correlation_id,
            ip_address=get_client_ip(request),
        )
    except ValueError as ve:
        code = str(ve)
        if code == "property_not_found":
            raise HTTPException(status_code=404, detail="Property not found")
        if code.startswith("requirement_not_on_property"):
            raise HTTPException(status_code=400, detail=code)
        if code in ("tenant_not_found_or_inactive", "tenant_not_assigned_to_property"):
            raise HTTPException(status_code=400, detail=code)
        raise HTTPException(status_code=400, detail=code)

    if result.get("outcome") != "sent":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "tenant_delivery_failed", **result},
        )
    return result


@client_router.get("/tenant-deliveries")
async def get_client_tenant_deliveries(request: Request, property_id: Optional[str] = None):
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    rows = await td_proof.list_tenant_delivery_proofs_for_scope(
        client_id=client_id,
        property_id=(property_id.strip() if property_id else None),
        limit=100,
    )
    return {
        "items": [serialize_tenant_delivery_row(x) for x in rows],
        "provider_evidence_notice": EMAIL_PROVIDER_PROOF_NOTICE,
    }


@client_router.post("/audit-pack/generate")
async def post_generate_audit_pack(request: Request, body: AuditPackGenerateBody):
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")

    allowed, msg, details = await plan_registry.enforce_feature(client_id, "reports_pdf")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": (details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": msg,
                "feature": "reports_pdf",
                **(details or {}),
            },
        )

    try:
        summary = await audit_pack.build_compliance_audit_pack(
            client_id=client_id,
            property_id=body.property_id.strip(),
            initiated_by_user_id=user.get("portal_user_id") or "",
            initiated_by_role=user.get("role"),
            purpose=body.purpose.strip(),
            ip_address=get_client_ip(request),
        )
    except ValueError as ve:
        if str(ve) == "property_not_found":
            raise HTTPException(status_code=404, detail="Property not found")
        raise HTTPException(status_code=400, detail=str(ve))
    return summary


@client_router.get("/audit-pack/{pack_id}/download")
async def get_download_audit_pack(request: Request, pack_id: str):
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")

    allowed, msg, details = await plan_registry.enforce_feature(client_id, "reports_pdf")
    if not allowed:
        raise HTTPException(status_code=403, detail={"message": msg, **(details or {})})

    rec = await audit_pack.get_audit_pack_record(client_id=client_id, pack_id=pack_id)
    if not rec or not rec.get("gridfs_id"):
        raise HTTPException(status_code=404, detail="Audit pack not found")
    data = await audit_pack.read_audit_pack_zip_bytes(str(rec["gridfs_id"]))
    if not data:
        raise HTTPException(status_code=410, detail="Audit pack blob is no longer available")
    await create_audit_log(
        action=AuditAction.COMPLIANCE_AUDIT_PACK_DOWNLOADED,
        actor_id=user.get("portal_user_id"),
        client_id=client_id,
        resource_type="compliance_audit_pack",
        resource_id=pack_id,
        metadata={"property_id": rec.get("property_id"), "filename": rec.get("filename")},
        ip_address=get_client_ip(request),
    )
    filename = rec.get("filename") or f"{pack_id}.zip"
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Pack-Id": pack_id},
    )


@admin_router.get("/tenant-deliveries", dependencies=[Depends(admin_route_guard)])
async def admin_list_tenant_deliveries(
    request: Request,
    client_id: str,
    property_id: Optional[str] = None,
):
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1}):
        raise HTTPException(status_code=404, detail="Client not found")
    rows = await td_proof.list_tenant_delivery_proofs_for_scope(
        client_id=client_id,
        property_id=(property_id.strip() if property_id else None),
        limit=200,
    )
    return {
        "items": [serialize_tenant_delivery_row(x) for x in rows],
        "provider_evidence_notice": EMAIL_PROVIDER_PROOF_NOTICE,
    }


@admin_router.get(
    "/tenant-deliveries/{delivery_id}",
    dependencies=[Depends(admin_route_guard)],
)
async def admin_get_tenant_delivery_detail(
    request: Request,
    delivery_id: str,
    client_id: str,
):
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1}):
        raise HTTPException(status_code=404, detail="Client not found")
    proof = await db.tenant_delivery_proofs.find_one(
        {"delivery_id": delivery_id, "client_id": client_id},
        {"_id": 0},
    )
    if not proof:
        raise HTTPException(status_code=404, detail="Delivery not found")
    msg_log = None
    mid = proof.get("message_log_id")
    if mid:
        msg_log = await db.message_logs.find_one({"message_id": mid}, {"_id": 0})
    tenant = await db.portal_users.find_one(
        {"portal_user_id": proof.get("tenant_portal_user_id")},
        {"_id": 0, "portal_user_id": 1, "full_name": 1, "first_name": 1, "last_name": 1, "status": 1},
    )
    reqs = []
    for rid in proof.get("requirement_ids_covered") or []:
        r = await db.requirements.find_one(
            {"requirement_id": rid, "client_id": client_id},
            {"_id": 0, "requirement_id": 1, "title": 1, "requirement_type": 1, "tenant_delivery_proof_status": 1, "tenant_delivery_required": 1},
        )
        if r:
            reqs.append(r)
    detail = {
        "delivery": serialize_tenant_delivery_row(proof),
        "tenant": tenant,
        "requirements": reqs,
        "message_log": msg_log,
        "provider_evidence_notice": EMAIL_PROVIDER_PROOF_NOTICE,
    }
    return detail


@admin_router.get("/audit-packs", dependencies=[Depends(admin_route_guard)])
async def admin_list_audit_packs(
    request: Request,
    client_id: str,
    property_id: Optional[str] = None,
):
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1}):
        raise HTTPException(status_code=404, detail="Client not found")
    rows = await audit_pack.list_audit_packs_for_scope(
        client_id=client_id,
        property_id=(property_id.strip() if property_id else None),
        limit=100,
    )
    return {"items": rows}


@admin_router.get("/audit-packs/{pack_id}/download")
async def admin_download_audit_pack(
    request: Request,
    pack_id: str,
    client_id: str,
):
    user = await admin_route_guard(request)
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1}):
        raise HTTPException(status_code=404, detail="Client not found")
    rec = await audit_pack.get_audit_pack_record(client_id=client_id, pack_id=pack_id)
    if not rec or not rec.get("gridfs_id"):
        raise HTTPException(status_code=404, detail="Audit pack not found")
    data = await audit_pack.read_audit_pack_zip_bytes(str(rec["gridfs_id"]))
    if not data:
        raise HTTPException(status_code=410, detail="Audit pack blob is no longer available")
    user = await admin_route_guard(request)
    await create_audit_log(
        action=AuditAction.COMPLIANCE_AUDIT_PACK_DOWNLOADED,
        actor_id=user.get("portal_user_id"),
        client_id=client_id,
        resource_type="compliance_audit_pack",
        resource_id=pack_id,
        metadata={"property_id": rec.get("property_id"), "filename": rec.get("filename"), "via": "admin"},
        ip_address=get_client_ip(request),
    )
    filename = rec.get("filename") or f"{pack_id}.zip"
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Pack-Id": pack_id},
    )
