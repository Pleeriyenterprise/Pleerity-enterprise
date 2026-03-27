"""
Admin API for contractors (Ops & Compliance / Contractor Network).
List, create, update, delete contractors. Optional filter by client_id.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
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


class DisablePortalAccessBody(BaseModel):
    reason: Optional[str] = None


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
    )
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
    )
    return doc


@router.patch("/contractors/{contractor_id}/approve", dependencies=[Depends(require_owner_or_admin)])
async def approve_contractor(request: Request, contractor_id: str):
    """Set contractor status=active and vetted=True (e.g. after reviewing self-registered)."""
    await admin_route_guard(request)
    doc = await contractor_service.approve_contractor(contractor_id)
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
    )
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
    """Delete a contractor. Owner or Admin only."""
    user = await admin_route_guard(request)
    if user.get("role") not in ("ROLE_OWNER", "ROLE_ADMIN"):
        raise HTTPException(status_code=403, detail="Only Owner or Admin can delete contractors")
    deleted = await contractor_service.delete_contractor(contractor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return {"ok": True, "contractor_id": contractor_id}


async def _issue_contractor_portal_invite(request: Request, contractor_id: str, resend: bool = False):
    """Create contractor invite token (24h), send email, and persist invite lifecycle state."""
    from datetime import datetime, timezone, timedelta
    from auth import generate_secure_token, hash_token
    from database import database
    from utils.audit import create_audit_log
    from models import AuditAction
    from utils.public_app_url import get_frontend_base_url
    user = await admin_route_guard(request)
    doc = await contractor_service.get_contractor(contractor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    email = (doc.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Contractor has no email; add one before inviting to portal")
    from services.contractor_portal_auth_service import get_account_by_contractor_id
    existing = await get_account_by_contractor_id(contractor_id)
    if existing and (existing.get("status") or "").lower() == "active":
        raise HTTPException(status_code=400, detail="Contractor already has a portal account; they can use forgot-password if needed")
    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)
    db = database.get_db()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)
    await db.password_tokens.update_many(
        {
            "purpose": "contractor_invite",
            "metadata.contractor_id": contractor_id,
            "used": {"$ne": True},
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now.isoformat(), "revoked_reason": "invite_replaced"}},
    )
    await db.password_tokens.insert_one({
        "token_hash": token_hash,
        "purpose": "contractor_invite",
        "metadata": {"contractor_id": contractor_id, "email": email},
        "expires_at": expires_at,
        "used": False,
        "revoked_at": None,
        "created_at": now.isoformat(),
    })
    await contractor_service.update_contractor(
        contractor_id,
        portal_access_status=contractor_service.PORTAL_ACCESS_INVITE_PENDING,
        portal_invite_sent_at=now.isoformat(),
        portal_invite_expires_at=expires_at.isoformat(),
        portal_invite_last_token_id=token_hash,
    )
    base_url = get_frontend_base_url().rstrip("/")
    setup_url = f"{base_url}/contractor-set-password?token={raw_token}"
    try:
        from services.notification_orchestrator import notification_orchestrator
        await notification_orchestrator.send(
            template_key="ADMIN_MANUAL",
            client_id=None,
            context={
                "recipient": email,
                "subject": "You're invited to the Pleerity Contractor Portal",
                "message": f"Use the link below to set your password and access your assigned work orders.<br><br><a href=\"{setup_url}\">Set password</a><br><br>Link valid for 24 hours.",
                "company_name": "Pleerity Enterprise Ltd",
            },
            idempotency_key=f"contractor_invite_{contractor_id}_{now.timestamp()}",
            event_type="contractor_portal_invite",
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Contractor invite email send failed: %s", e)
    await create_audit_log(
        action=AuditAction.CONTRACTOR_INVITE_RESENT if resend else AuditAction.CONTRACTOR_INVITE_SENT,
        actor_id=user.get("portal_user_id"),
        actor_role=user.get("role"),
        resource_type="contractor",
        resource_id=contractor_id,
        metadata={"email": email, "expires_at": expires_at.isoformat()},
    )
    return {
        "ok": True,
        "message": "Invite sent. Contractor can set password via the link.",
        "setup_url": setup_url,
        "expires_at": expires_at.isoformat(),
        "portal_access_status": contractor_service.PORTAL_ACCESS_INVITE_PENDING,
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
