"""
Admin API for contractors (Ops & Compliance / Contractor Network).
List, create, update, delete contractors. Optional filter by client_id.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel
from typing import Optional, List

from database import database
from middleware import admin_route_guard, require_owner_or_admin
from services import contractor_service

router = APIRouter(prefix="/api/admin/ops", tags=["ops-contractors"], dependencies=[Depends(admin_route_guard)])


class ContractorCreate(BaseModel):
    name: str
    trade_types: Optional[List[str]] = None
    vetted: bool = False
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_id: Optional[str] = None
    areas_served: Optional[List[str]] = None
    notes: Optional[str] = None
    execution_capabilities: Optional[str] = None
    supported_requirement_codes: Optional[List[str]] = None
    service_regions: Optional[List[str]] = None


class ContractorUpdate(BaseModel):
    name: Optional[str] = None
    trade_types: Optional[List[str]] = None
    vetted: Optional[bool] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_id: Optional[str] = None
    areas_served: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    credentials: Optional[List[str]] = None
    insurance_details: Optional[str] = None
    contact_name: Optional[str] = None
    region: Optional[str] = None
    execution_capabilities: Optional[str] = None
    supported_requirement_codes: Optional[List[str]] = None
    declared_execution_capabilities: Optional[str] = None
    declared_supported_requirement_codes: Optional[List[str]] = None
    declared_credentials: Optional[List[str]] = None
    verified_execution_capabilities: Optional[str] = None
    verified_supported_requirement_codes: Optional[List[str]] = None
    service_regions: Optional[List[str]] = None


class ApproveContractorBody(BaseModel):
    """Capability verification as part of approval (optional). Self-registered contractors need explicit verified_* or accept_declared_capabilities for compliance routing."""

    verified_execution_capabilities: Optional[str] = None
    verified_supported_requirement_codes: Optional[List[str]] = None
    accept_declared_capabilities: bool = False


class DisablePortalAccessBody(BaseModel):
    reason: Optional[str] = None


class ContractorInviteBody(BaseModel):
    email: str
    name: Optional[str] = None
    trade_types: Optional[List[str]] = None
    phone: Optional[str] = None
    client_id: Optional[str] = None
    property_scope: Optional[List[str]] = None
    vetted: Optional[bool] = None


class ContractorNetworkCreate(BaseModel):
    company_name: str
    trade_types: List[str]
    phone: Optional[str] = None
    email: Optional[str] = None
    region: Optional[str] = None
    credentials: Optional[List[str]] = None
    insurance_details: Optional[str] = None
    areas_served: Optional[List[str]] = None
    contact_name: Optional[str] = None
    notes: Optional[str] = None


@router.get("/contractors/analytics")
async def contractor_analytics(
    request: Request,
    view: str = Query("top_performers", description="top_performers | sla_issues | high_rejection"),
    client_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Contractor intelligence analytics: top performers, SLA issues, high rejection rates. Admin only."""
    await admin_route_guard(request)
    from services.contractor_intelligence_service import list_contractor_analytics
    return await list_contractor_analytics(view=view, client_id=client_id, limit=limit)


@router.get("/contractors")
async def list_contractors(
    request: Request,
    client_id: Optional[str] = Query(None, description="Filter by client_id"),
    vetted_only: bool = Query(False, description="Only vetted contractors"),
    source_type: Optional[str] = Query(None, description="Filter by source_type"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. pending_review)"),
    pending_network_review: bool = Query(
        False,
        description="Landlord contractors awaiting admin approve-to-network (submitted, not approved, not rejected)",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """List contractors. Admin only."""
    await admin_route_guard(request)
    result = await contractor_service.list_contractors(
        client_id=client_id,
        vetted_only=vetted_only,
        source_type=source_type,
        status=status,
        skip=skip,
        limit=limit,
        pending_network_review=pending_network_review,
    )
    return result


@router.get("/contractors/{contractor_id}")
async def get_contractor(request: Request, contractor_id: str):
    """Get one contractor by id."""
    await admin_route_guard(request)
    doc = await contractor_service.get_contractor(contractor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return doc


@router.get("/contractors/{contractor_id}/explanation")
async def get_contractor_explanation(request: Request, contractor_id: str):
    """Get explanation for contractor reliability/performance score (why it matters, usage guidance). Admin only."""
    await admin_route_guard(request)
    doc = await contractor_service.get_contractor(contractor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    from services.explanation_engine import explain_contractor_score
    return explain_contractor_score(doc)


@router.post("/contractors", dependencies=[Depends(require_owner_or_admin)])
async def create_contractor(request: Request, body: ContractorCreate):
    """Create a contractor. Owner or Admin only."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can create contractors")
    try:
        doc = await contractor_service.create_contractor(
            name=body.name,
            trade_types=body.trade_types,
            vetted=body.vetted,
            email=body.email,
            phone=body.phone,
            company_name=body.company_name,
            client_id=body.client_id,
            areas_served=body.areas_served,
            notes=body.notes,
            execution_capabilities=body.execution_capabilities,
            supported_requirement_codes=body.supported_requirement_codes,
            service_regions=body.service_regions,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    from utils.audit import create_audit_log
    from models import AuditAction
    await create_audit_log(
        action=AuditAction.CONTRACTOR_CREATED,
        actor_id=user.get("portal_user_id"),
        actor_role=user.get("role"),
        client_id=body.client_id,
        resource_type="contractor",
        resource_id=doc.get("contractor_id"),
        metadata={"source_type": doc.get("source_type"), "portal_access_status": doc.get("portal_access_status")},
    )
    return doc


@router.post("/contractors/network", dependencies=[Depends(require_owner_or_admin)])
async def create_network_contractor(request: Request, body: ContractorNetworkCreate):
    """Add contractor to platform network (visible to all orgs). client_id=null, vetted=True, status=active."""
    await admin_route_guard(request)
    doc = await contractor_service.create_contractor_network(
        company_name=body.company_name.strip(),
        trade_types=[t.strip() for t in body.trade_types if t and t.strip()] or ["general"],
        phone=body.phone.strip() if body.phone else None,
        email=body.email.strip() if body.email else None,
        region=body.region.strip() if body.region else None,
        credentials=body.credentials,
        insurance_details=body.insurance_details.strip() if body.insurance_details else None,
        areas_served=body.areas_served,
        contact_name=body.contact_name.strip() if body.contact_name else None,
        notes=body.notes.strip() if body.notes else None,
        service_regions=body.service_regions,
    )
    return doc


@router.post("/contractors/invite", dependencies=[Depends(require_owner_or_admin)])
async def invite_contractor(request: Request, body: ContractorInviteBody):
    """Create or update contractor by email, issue portal invite (rotates unused tokens)."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can invite contractors")
    actor_id = user.get("user_id") or user.get("email") or user.get("portal_user_id")
    try:
        result = await contractor_service.invite_contractor_by_admin(
            email=body.email.strip(),
            name=body.name,
            trade_types=body.trade_types,
            phone=body.phone,
            client_id=body.client_id,
            property_scope=body.property_scope,
            vetted=body.vetted,
            actor_id=actor_id,
            actor_role=user.get("role"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.patch("/contractors/{contractor_id}/approve", dependencies=[Depends(require_owner_or_admin)])
async def approve_contractor(
    request: Request,
    contractor_id: str,
    body: ApproveContractorBody = Body(default_factory=ApproveContractorBody),
):
    """Approve contractor (vetted, lifecycle status, portal invite when not yet activated)."""
    user = await admin_route_guard(request)
    admin_id = user.get("user_id") or user.get("email") or user.get("portal_user_id")
    doc = await contractor_service.approve_contractor(
        contractor_id,
        approved_by=admin_id,
        approved_by_role=user.get("role"),
        verified_execution_capabilities=body.verified_execution_capabilities,
        verified_supported_requirement_codes=body.verified_supported_requirement_codes,
        accept_declared_capabilities=body.accept_declared_capabilities,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return doc


class RejectNetworkSubmissionBody(BaseModel):
    reason: Optional[str] = None


@router.patch("/contractors/{contractor_id}/approve-to-network", dependencies=[Depends(require_owner_or_admin)])
async def approve_contractor_to_network(request: Request, contractor_id: str):
    """Approve a landlord-submitted contractor for the platform network. Creates a new network contractor and marks the private record as approved."""
    user = await admin_route_guard(request)
    admin_id = user.get("user_id") or user.get("email") or user.get("portal_user_id") or "admin"
    doc = await contractor_service.approve_contractor_to_network(contractor_id, approved_by_admin_id=admin_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Contractor not found or not submitted for network review.",
        )
    from utils.audit import create_audit_log
    from models import AuditAction
    await create_audit_log(
        action=AuditAction.CONTRACTOR_APPROVED_FOR_NETWORK,
        actor_role=user.get("role"),
        actor_id=admin_id,
        resource_type="contractor",
        resource_id=contractor_id,
        metadata={"new_network_contractor_id": doc.get("contractor_id")},
    )
    return doc


@router.patch("/contractors/{contractor_id}/reject-network-submission", dependencies=[Depends(require_owner_or_admin)])
async def reject_contractor_network_submission(request: Request, contractor_id: str, body: RejectNetworkSubmissionBody):
    """Reject a landlord-submitted contractor's network submission."""
    user = await admin_route_guard(request)
    admin_id = user.get("user_id") or user.get("email") or user.get("portal_user_id")
    doc = await contractor_service.reject_contractor_network_submission(
        contractor_id,
        reason=body.reason,
        rejected_by_admin_id=admin_id,
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Contractor not found or not submitted for network review.",
        )
    from utils.audit import create_audit_log
    from models import AuditAction
    await create_audit_log(
        action=AuditAction.CONTRACTOR_NETWORK_SUBMISSION_REJECTED,
        actor_role=user.get("role"),
        actor_id=admin_id,
        resource_type="contractor",
        resource_id=contractor_id,
        metadata={"reason": (body.reason or "")[:500]},
    )
    return doc


@router.patch("/contractors/{contractor_id}", dependencies=[Depends(require_owner_or_admin)])
async def update_contractor(request: Request, contractor_id: str, body: ContractorUpdate):
    """Update a contractor. Owner or Admin only."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can update contractors")
    try:
        doc = await contractor_service.update_contractor(
            contractor_id,
            name=body.name,
            trade_types=body.trade_types,
            vetted=body.vetted,
            email=body.email,
            phone=body.phone,
            company_name=body.company_name,
            client_id=body.client_id,
            areas_served=body.areas_served,
            notes=body.notes,
            status=body.status,
            credentials=body.credentials,
            insurance_details=body.insurance_details,
            contact_name=body.contact_name,
            region=body.region,
            execution_capabilities=body.execution_capabilities,
            supported_requirement_codes=body.supported_requirement_codes,
            declared_execution_capabilities=body.declared_execution_capabilities,
            declared_supported_requirement_codes=body.declared_supported_requirement_codes,
            declared_credentials=body.declared_credentials,
            verified_execution_capabilities=body.verified_execution_capabilities,
            verified_supported_requirement_codes=body.verified_supported_requirement_codes,
            verified_by=user.get("user_id") or user.get("email") or user.get("portal_user_id"),
            service_regions=body.service_regions,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    if body.status and body.status.strip().lower() == "suspended":
        from utils.audit import create_audit_log
        from models import AuditAction
        await create_audit_log(
            action=AuditAction.CONTRACTOR_SUSPENDED,
            actor_role=user.get("role"),
            actor_id=user.get("user_id") or user.get("email") or user.get("portal_user_id"),
            resource_type="contractor",
            resource_id=contractor_id,
        )
    return doc


@router.delete("/contractors/{contractor_id}", dependencies=[Depends(require_owner_or_admin)])
async def delete_contractor(request: Request, contractor_id: str):
    """Hard-delete a contractor only when no work orders, invoices, or audit trail references block it."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can delete contractors")
    try:
        deleted = await contractor_service.delete_contractor(contractor_id)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("preflight_failed:"):
            blockers = [b for b in msg.split(":", 1)[1].split(",") if b]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Contractor delete blocked", "blockers": blockers},
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return {"ok": True, "contractor_id": contractor_id}


async def _issue_contractor_portal_invite(request: Request, contractor_id: str, resend: bool = False):
    """Create contractor invite token (24h), send email, and persist invite lifecycle state."""
    user = await admin_route_guard(request)
    doc = await contractor_service.get_contractor(contractor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    actor_id = user.get("user_id") or user.get("email") or user.get("portal_user_id")
    try:
        payload = await contractor_service.issue_contractor_portal_invite(
            contractor_id,
            actor_id=actor_id,
            actor_role=user.get("role"),
            resend=resend,
            include_next_steps=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "ok": True,
        "message": "Invite sent. Contractor can set password via the link.",
        "setup_url": payload.get("setup_url"),
        "expires_at": payload.get("expires_at"),
        "portal_access_status": payload.get("portal_access_status"),
    }


@router.post("/contractors/{contractor_id}/invite-portal", dependencies=[Depends(require_owner_or_admin)])
async def invite_contractor_to_portal(request: Request, contractor_id: str):
    """Send first contractor portal invite (24h expiry)."""
    return await _issue_contractor_portal_invite(request, contractor_id, resend=False)


@router.post("/contractors/{contractor_id}/invite-portal/resend", dependencies=[Depends(require_owner_or_admin)])
async def resend_contractor_portal_invite(request: Request, contractor_id: str):
    """Resend contractor portal invite (revokes previous active invite)."""
    return await _issue_contractor_portal_invite(request, contractor_id, resend=True)


@router.post("/contractors/{contractor_id}/portal-access/disable", dependencies=[Depends(require_owner_or_admin)])
async def disable_contractor_portal_access(request: Request, contractor_id: str, body: DisablePortalAccessBody):
    """Disable contractor portal access, revoke invite/job tokens, and return jobs requiring reassignment."""
    user = await admin_route_guard(request)
    result = await contractor_service.disable_portal_access(contractor_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="Contractor not found")
    from utils.audit import create_audit_log
    from models import AuditAction
    await create_audit_log(
        action=AuditAction.CONTRACTOR_PORTAL_ACCESS_DISABLED,
        actor_id=user.get("portal_user_id"),
        actor_role=user.get("role"),
        resource_type="contractor",
        resource_id=contractor_id,
        metadata={
            "reason": (body.reason or "disabled_by_admin")[:500],
            "revoked_invite_tokens": result.get("revoked_invite_tokens", 0),
            "revoked_job_tokens": result.get("revoked_job_tokens", 0),
            "reassignment_required_count": result.get("reassignment_required_count", 0),
        },
    )
    return result


@router.get("/contractors/{contractor_id}/assigned-jobs")
async def list_contractor_assigned_jobs(request: Request, contractor_id: str, include_closed: bool = Query(False), limit: int = Query(200, ge=1, le=500)):
    """List jobs currently assigned to a contractor for admin reassignment workflow."""
    await admin_route_guard(request)
    contractor = await contractor_service.get_contractor(contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return await contractor_service.list_assigned_jobs(contractor_id=contractor_id, include_closed=include_closed, limit=limit)
