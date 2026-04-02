"""
Tenant request -> compliance execution bridge.

Creates a real COMPLIANCE work order directly from a linked tenant request, with
duplicate-prevention and auditable outcomes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from models import AuditAction
from utils.audit import create_audit_log
from services.compliance_booking_service import create_compliance_execution_work_order

_TERMINAL_WO_STATUSES = frozenset({"COMPLETED", "CANCELLED", "CLOSED", "VERIFIED"})


async def start_compliance_job_from_tenant_request(
    *,
    client_id: str,
    tenant_request_id: str,
    actor_portal_user_id: Optional[str],
    actor_role: Optional[str] = None,
    allow_duplicate: bool = False,
) -> Dict[str, Any]:
    db = database.get_db()
    req = await db.tenant_requests.find_one(
        {"request_id": tenant_request_id, "client_id": client_id},
        {"_id": 0},
    )
    if not req:
        raise LookupError("Tenant request not found")

    property_id = (req.get("property_id") or "").strip()
    requirement_id = (req.get("requirement_id") or "").strip()
    requirement_code = (req.get("requirement_code") or "").strip()
    if not property_id or not requirement_id or not requirement_code:
        raise ValueError("Tenant request is missing linked requirement context")

    await create_audit_log(
        action=AuditAction.TENANT_REQUEST_JOB_INITIATION_ATTEMPT,
        actor_id=actor_portal_user_id,
        actor_role=actor_role,
        client_id=client_id,
        resource_type="tenant_request",
        resource_id=tenant_request_id,
        metadata={
            "tenant_request_id": tenant_request_id,
            "property_id": property_id,
            "requirement_id": requirement_id,
            "requirement_code": requirement_code,
            "allow_duplicate": bool(allow_duplicate),
        },
    )

    active_dup_query = {
        "client_id": client_id,
        "work_order_kind": "COMPLIANCE",
        "status": {"$nin": list(_TERMINAL_WO_STATUSES)},
        "$or": [
            {"tenant_request_id": tenant_request_id},
            {
                "linked_property_requirement_id": requirement_id,
                "property_id": property_id,
            },
        ],
    }
    existing_active = await db.work_orders.find_one(active_dup_query, {"_id": 0, "work_order_id": 1, "status": 1})
    if existing_active and not allow_duplicate:
        await create_audit_log(
            action=AuditAction.TENANT_REQUEST_JOB_DUPLICATE_PREVENTED,
            actor_id=actor_portal_user_id,
            actor_role=actor_role,
            client_id=client_id,
            resource_type="tenant_request",
            resource_id=tenant_request_id,
            metadata={
                "tenant_request_id": tenant_request_id,
                "existing_work_order_id": existing_active.get("work_order_id"),
                "existing_work_order_status": existing_active.get("status"),
                "requirement_id": requirement_id,
                "requirement_code": requirement_code,
            },
        )
        raise ValueError("An active compliance job already exists for this tenant request or requirement")

    tenant_name = (req.get("tenant_name") or "").strip() or "Tenant"
    message = (req.get("message") or "").strip()
    description_override = (
        f"Tenant request compliance action: {requirement_code.replace('_', ' ').title()}. "
        f"Requested by {tenant_name}. "
        + (f"Request note: {message}" if message else "No additional tenant note provided.")
    )

    wo = await create_compliance_execution_work_order(
        client_id=client_id,
        property_id=property_id,
        requirement_code_raw=requirement_code,
        compliance_purpose="inspection",
        compliance_generated_from="requirement",
        actor_portal_user_id=actor_portal_user_id,
        description_override=description_override,
        linked_property_requirement_id=requirement_id,
        source="tenant_request",
    )
    work_order_id = (wo or {}).get("work_order_id")
    if not work_order_id:
        raise RuntimeError("Compliance work order creation failed")

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.work_orders.update_one(
        {"work_order_id": work_order_id, "client_id": client_id},
        {
            "$set": {
                "tenant_request_id": tenant_request_id,
                "linked_property_requirement_id": requirement_id,
                "requirement_code": requirement_code,
                "updated_at": now_iso,
            }
        },
    )
    await db.tenant_requests.update_one(
        {"request_id": tenant_request_id, "client_id": client_id},
        {
            "$set": {
                "linked_work_order_id": work_order_id,
                "status": "IN_PROGRESS",
                "updated_at": now_iso,
            }
        },
    )

    await create_audit_log(
        action=AuditAction.TENANT_REQUEST_JOB_CREATED,
        actor_id=actor_portal_user_id,
        actor_role=actor_role,
        client_id=client_id,
        resource_type="tenant_request",
        resource_id=tenant_request_id,
        metadata={
            "tenant_request_id": tenant_request_id,
            "work_order_id": work_order_id,
            "property_id": property_id,
            "requirement_id": requirement_id,
            "requirement_code": requirement_code,
        },
    )
    return {
        "tenant_request_id": tenant_request_id,
        "work_order": {**wo, "tenant_request_id": tenant_request_id},
    }

