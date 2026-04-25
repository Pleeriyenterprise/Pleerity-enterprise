"""
Governed tenant compliance delivery proof: push email + immutable Mongo record.

Links ``tenant_delivery_proofs`` to ``message_logs`` (provider receipt when Postmark returns MessageID).
Does not fabricate open/delivery events beyond what the provider stores on ``message_logs``.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from database import database
from models import AuditAction, UserRole
from utils.audit import create_audit_log

from services.compliance_gap_sync import sync_compliance_gaps_for_requirement
from services.compliance_pack import compliance_pack_service
from services.notification_orchestrator import NotificationOrchestrator

logger = logging.getLogger(__name__)

TEMPLATE_KEY = "TENANT_COMPLIANCE_PACKAGE_DELIVERY"


def _parse_actor_role(role: Optional[str]) -> Optional[UserRole]:
    if not role:
        return None
    try:
        return UserRole(str(role))
    except ValueError:
        return None


async def _ensure_tenant_and_property(
    db,
    *,
    client_id: str,
    property_id: str,
    tenant_portal_user_id: str,
) -> Dict[str, Any]:
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    if not prop:
        raise ValueError("property_not_found")
    tenant = await db.portal_users.find_one(
        {
            "portal_user_id": tenant_portal_user_id,
            "client_id": client_id,
            "role": UserRole.ROLE_TENANT.value,
        },
        {"_id": 0, "auth_email": 1, "full_name": 1, "first_name": 1, "last_name": 1, "status": 1},
    )
    if not tenant or (tenant.get("status") or "").upper() != "ACTIVE":
        raise ValueError("tenant_not_found_or_inactive")
    n_assign = await db.tenant_assignments.count_documents({"tenant_id": tenant_portal_user_id})
    if n_assign > 0:
        assn = await db.tenant_assignments.find_one(
            {"tenant_id": tenant_portal_user_id, "property_id": property_id},
            {"_id": 0},
        )
        if not assn:
            raise ValueError("tenant_not_assigned_to_property")
    return {"property": prop, "tenant": tenant}


async def _resolve_requirement_ids_for_delivery(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_ids_covered: Optional[Sequence[str]],
) -> List[str]:
    if requirement_ids_covered:
        ids = [str(x).strip() for x in requirement_ids_covered if str(x).strip()]
        for rid in ids:
            row = await db.requirements.find_one(
                {"requirement_id": rid, "client_id": client_id, "property_id": property_id},
                {"_id": 0, "requirement_id": 1},
            )
            if not row:
                raise ValueError(f"requirement_not_on_property:{rid}")
        return ids
    rows = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id, "tenant_delivery_required": True},
        {"_id": 0, "requirement_id": 1},
    ).to_list(500)
    return [str(r["requirement_id"]) for r in rows if r.get("requirement_id")]


async def initiate_tenant_compliance_delivery(
    *,
    client_id: str,
    property_id: str,
    tenant_portal_user_id: str,
    recipient_email: str,
    initiated_by_user_id: str,
    initiated_by_role: Optional[str],
    purpose: str = "compliance_tenant_push",
    requirement_ids_covered: Optional[Sequence[str]] = None,
    correlation_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate compliance pack PDF, persist an immutable delivery row, send governed email, audit lifecycle.
    """
    db = database.get_db()
    await _ensure_tenant_and_property(
        db, client_id=client_id, property_id=property_id, tenant_portal_user_id=tenant_portal_user_id
    )
    req_ids = await _resolve_requirement_ids_for_delivery(
        db, client_id=client_id, property_id=property_id, requirement_ids_covered=requirement_ids_covered
    )

    pdf_bytes = await compliance_pack_service.generate_compliance_pack(
        property_id=property_id,
        client_id=client_id,
        include_expired=False,
        requested_by=initiated_by_user_id,
        requested_by_role=initiated_by_role,
    )
    pack_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    delivery_id = (correlation_id or "").strip() or f"td_{uuid.uuid4().hex[:24]}"
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    client_row = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "full_name": 1, "company_name": 1, "customer_reference": 1},
    )
    tenant_row = await db.portal_users.find_one(
        {"portal_user_id": tenant_portal_user_id},
        {"_id": 0, "first_name": 1, "last_name": 1, "full_name": 1},
    )
    tenant_name = (
        (tenant_row or {}).get("full_name")
        or " ".join(
            x
            for x in (
                (tenant_row or {}).get("first_name"),
                (tenant_row or {}).get("last_name"),
            )
            if x
        ).strip()
        or "there"
    )
    client_display = (client_row or {}).get("company_name") or (client_row or {}).get("full_name") or "your landlord"

    base_doc: Dict[str, Any] = {
        "delivery_id": delivery_id,
        "correlation_id": delivery_id,
        "client_id": client_id,
        "property_id": property_id,
        "tenant_portal_user_id": tenant_portal_user_id,
        "recipient_email": recipient_email.strip(),
        "document_types_delivered": ["COMPLIANCE_PACK_PDF"],
        "requirement_ids_covered": req_ids,
        "generated_pack_kind": "compliance_pack_pdf_v1",
        "generated_pack_sha256": pack_sha256,
        "lifecycle_pack": "GENERATED",
        "lifecycle_send": "PENDING",
        "delivery_channel": "EMAIL",
        "delivery_status": "PENDING_SEND",
        "provider_message_id": None,
        "message_log_id": None,
        "provider_opened_at": None,
        "provider_delivered_at": None,
        "initiated_by_user_id": initiated_by_user_id,
        "initiated_by_role": initiated_by_role,
        "purpose": purpose,
        "created_at": now_iso,
        "updated_at": now_iso,
        "last_error": None,
        "audit_log_ids": [],
    }
    await db.tenant_delivery_proofs.insert_one(base_doc)

    actor_role = _parse_actor_role(initiated_by_role)
    init_audit = await create_audit_log(
        action=AuditAction.TENANT_DELIVERY_INITIATED,
        actor_role=actor_role,
        actor_id=initiated_by_user_id,
        client_id=client_id,
        resource_type="tenant_delivery_proof",
        resource_id=delivery_id,
        metadata={
            "property_id": property_id,
            "tenant_portal_user_id": tenant_portal_user_id,
            "recipient_email": recipient_email.strip(),
            "requirement_ids_covered": req_ids,
            "purpose": purpose,
        },
        ip_address=ip_address,
    )
    audit_ids = [x for x in [init_audit] if x]
    await db.tenant_delivery_proofs.update_one(
        {"delivery_id": delivery_id},
        {"$set": {"audit_log_ids": audit_ids, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    orch = NotificationOrchestrator()
    idem = f"tenant_deliver|{delivery_id}"
    subject = "[Compliance] Your property compliance pack"
    html_msg = (
        f"<p>{client_display} has sent you the compliance certificate summary for your property.</p>"
        f"<p>Delivery reference: <code>{delivery_id}</code></p>"
        f"<p>The PDF is attached to this email.</p>"
    )
    ctx: Dict[str, Any] = {
        "recipient": recipient_email.strip(),
        "subject": subject,
        "message": html_msg,
        "body": html_msg,
        "client_name": tenant_name,
        "customer_reference": (client_row or {}).get("customer_reference") or "",
        "attachments": [
            {
                "Name": "compliance-pack.pdf",
                "Content": base64.b64encode(pdf_bytes).decode("ascii"),
                "ContentType": "application/pdf",
            }
        ],
    }
    result = await orch.send(
        TEMPLATE_KEY,
        client_id,
        ctx,
        idempotency_key=idem,
        event_type="TENANT_COMPLIANCE_DELIVERY",
    )

    msg_id = result.message_id
    provider_message_id = (result.details or {}).get("provider_message_id")
    opened_at = None
    delivered_at = None
    if msg_id:
        await db.message_logs.update_one(
            {"message_id": msg_id},
            {
                "$set": {
                    "metadata.tenant_delivery_id": delivery_id,
                    "metadata.delivery_proof_intent": "TENANT_COMPLIANCE_PACK",
                }
            },
        )
        log = await db.message_logs.find_one({"message_id": msg_id}, {"_id": 0})
        if log:
            provider_message_id = provider_message_id or log.get("provider_message_id") or log.get("postmark_message_id")
            oa = log.get("opened_at")
            da = log.get("delivered_at")
            if oa is not None:
                opened_at = oa.isoformat() if hasattr(oa, "isoformat") else str(oa)
            if da is not None:
                delivered_at = da.isoformat() if hasattr(da, "isoformat") else str(da)

    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 0})

    if result.outcome == "sent" or (
        result.outcome == "duplicate_ignored"
        and msg_id
        and (await db.message_logs.find_one({"message_id": msg_id}, {"_id": 0, "status": 1}) or {}).get("status") == "SENT"
    ):
        sent_iso = datetime.now(timezone.utc).isoformat()
        ok_audit = await create_audit_log(
            action=AuditAction.TENANT_DELIVERY_SUCCEEDED,
            actor_role=actor_role,
            actor_id=initiated_by_user_id,
            client_id=client_id,
            resource_type="tenant_delivery_proof",
            resource_id=delivery_id,
            metadata={
                "message_log_id": msg_id,
                "provider_message_id": provider_message_id,
                "outcome": result.outcome,
                "property_id": property_id,
            },
            ip_address=ip_address,
        )
        if ok_audit:
            audit_ids.append(ok_audit)
        await db.tenant_delivery_proofs.update_one(
            {"delivery_id": delivery_id},
            {
                "$set": {
                    "lifecycle_pack": "GENERATED",
                    "lifecycle_send": "SENT",
                    "delivery_status": "SENT",
                    "message_log_id": msg_id,
                    "provider_message_id": provider_message_id,
                    "sent_at": sent_iso,
                    "provider_opened_at": opened_at,
                    "provider_delivered_at": delivered_at,
                    "audit_log_ids": audit_ids,
                    "updated_at": sent_iso,
                    "last_error": None,
                }
            },
        )
        if req_ids:
            # MTA acceptance (SENT): gap remains until Postmark Delivery webhook sets DELIVERED on proof + requirements.
            await db.requirements.update_many(
                {"client_id": client_id, "property_id": property_id, "requirement_id": {"$in": req_ids}},
                {
                    "$set": {
                        "tenant_delivery_proof_status": "SENT",
                        "tenant_last_delivery_id": delivery_id,
                        "updated_at": sent_iso,
                    }
                },
            )
            for rid in req_ids:
                full = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0})
                if full:
                    try:
                        await sync_compliance_gaps_for_requirement(db, full, property_doc=prop)
                    except Exception as sync_e:
                        logger.warning("gap sync after tenant delivery failed rid=%s: %s", rid, sync_e)
        return {
            "delivery_id": delivery_id,
            "outcome": "sent",
            "message_log_id": msg_id,
            "provider_message_id": provider_message_id,
            "notification_outcome": result.outcome,
            "audit_log_ids": audit_ids,
        }

    err = result.error_message or result.block_reason or "send_failed"
    fail_audit = await create_audit_log(
        action=AuditAction.TENANT_DELIVERY_FAILED,
        actor_role=actor_role,
        actor_id=initiated_by_user_id,
        client_id=client_id,
        resource_type="tenant_delivery_proof",
        resource_id=delivery_id,
        metadata={
            "message_log_id": msg_id,
            "error": err,
            "notification_outcome": result.outcome,
            "block_reason": result.block_reason,
            "property_id": property_id,
        },
        ip_address=ip_address,
    )
    if fail_audit:
        audit_ids.append(fail_audit)
    fail_iso = datetime.now(timezone.utc).isoformat()
    await db.tenant_delivery_proofs.update_one(
        {"delivery_id": delivery_id},
        {
            "$set": {
                "lifecycle_send": "FAILED",
                "delivery_status": "FAILED" if result.outcome == "failed" else "BLOCKED",
                "message_log_id": msg_id,
                "provider_message_id": provider_message_id,
                "last_error": err[:2000],
                "audit_log_ids": audit_ids,
                "updated_at": fail_iso,
            }
        },
    )
    return {
        "delivery_id": delivery_id,
        "outcome": "failed",
        "message_log_id": msg_id,
        "provider_message_id": provider_message_id,
        "notification_outcome": result.outcome,
        "error": err,
        "audit_log_ids": audit_ids,
    }


async def list_tenant_delivery_proofs_for_scope(
    *,
    client_id: str,
    property_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id}
    if property_id:
        q["property_id"] = property_id
    cur = db.tenant_delivery_proofs.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cur.to_list(length=limit)
