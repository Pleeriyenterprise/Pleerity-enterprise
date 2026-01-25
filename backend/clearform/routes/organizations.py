"""ClearForm Organization Routes

API endpoints for institutional/team accounts.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from clearform.routes.auth import get_current_clearform_user
from clearform.services.organization_service import organization_service
from clearform.models.organizations import OrgMemberRole, OrganizationType

router = APIRouter(prefix="/api/clearform/organizations", tags=["ClearForm Organizations"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateOrganizationRequest(BaseModel):
    name: str
    description: Optional[str] = None
    org_type: Optional[str] = "SMALL_BUSINESS"


class UpdateOrganizationRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    monthly_credit_budget: Optional[int] = None
    settings: Optional[dict] = None


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "MEMBER"
    message: Optional[str] = None


class UpdateMemberRoleRequest(BaseModel):
    role: str


# ============================================================================
# Organization CRUD
# ============================================================================

@router.post("")
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Create a new organization."""
    try:
        # Check if user already owns an org
        existing_orgs = await organization_service.get_user_organizations(current_user["user_id"])
        owned = [o for o in existing_orgs if o.get("user_role") == "OWNER"]
        if owned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already own an organization"
            )
        
        org = await organization_service.create_organization(
            owner_id=current_user["user_id"],
            name=request.name,
            description=request.description,
            org_type=request.org_type,
        )
        
        return {
            "success": True,
            "organization": org.model_dump(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("")
async def get_user_organizations(
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get all organizations the current user belongs to."""
    orgs = await organization_service.get_user_organizations(current_user["user_id"])
    return {
        "success": True,
        "organizations": orgs,
    }


@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get organization details."""
    # Verify membership
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization"
        )
    
    org = await organization_service.get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return {
        "success": True,
        "organization": org,
        "user_role": member.get("role"),
    }


@router.patch("/{org_id}")
async def update_organization(
    org_id: str,
    request: UpdateOrganizationRequest,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Update organization settings."""
    # Verify admin/owner
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member or member.get("role") not in ["OWNER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates provided"
        )
    
    org = await organization_service.update_organization(
        org_id=org_id,
        updates=updates,
        actor_id=current_user["user_id"],
    )
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return {
        "success": True,
        "organization": org,
    }


# ============================================================================
# Member Management
# ============================================================================

@router.get("/{org_id}/members")
async def get_members(
    org_id: str,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get organization members."""
    # Verify membership
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization"
        )
    
    members = await organization_service.get_members(org_id, include_inactive)
    return {
        "success": True,
        "members": members,
    }


@router.post("/{org_id}/invitations")
async def invite_member(
    org_id: str,
    request: InviteMemberRequest,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Invite a user to join the organization."""
    # Verify admin/owner/manager
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member or member.get("role") not in ["OWNER", "ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required to invite members"
        )
    
    try:
        role = OrgMemberRole(request.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {request.role}"
        )
    
    # Can't invite with higher role
    role_hierarchy = {"OWNER": 5, "ADMIN": 4, "MANAGER": 3, "MEMBER": 2, "VIEWER": 1}
    if role_hierarchy.get(role.value, 0) >= role_hierarchy.get(member.get("role"), 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite with equal or higher role than your own"
        )
    
    try:
        invitation = await organization_service.create_invitation(
            org_id=org_id,
            email=request.email,
            role=role,
            inviter_id=current_user["user_id"],
            message=request.message,
        )
        
        return {
            "success": True,
            "invitation": invitation.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{org_id}/invitations")
async def get_pending_invitations(
    org_id: str,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get pending invitations for the organization."""
    # Verify admin/owner/manager
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member or member.get("role") not in ["OWNER", "ADMIN", "MANAGER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required"
        )
    
    invitations = await organization_service.get_pending_invitations(org_id)
    return {
        "success": True,
        "invitations": invitations,
    }


@router.patch("/{org_id}/members/{user_id}/role")
async def update_member_role(
    org_id: str,
    user_id: str,
    request: UpdateMemberRoleRequest,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Update a member's role."""
    # Verify admin/owner
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member or member.get("role") not in ["OWNER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        new_role = OrgMemberRole(request.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {request.role}"
        )
    
    try:
        success = await organization_service.update_member_role(
            org_id=org_id,
            user_id=user_id,
            new_role=new_role,
            actor_id=current_user["user_id"],
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        return {"success": True}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{org_id}/members/{user_id}")
async def remove_member(
    org_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Remove a member from the organization."""
    # Verify admin/owner
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member or member.get("role") not in ["OWNER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Can't remove self (use leave endpoint)
    if user_id == current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use leave endpoint to leave organization"
        )
    
    try:
        success = await organization_service.remove_member(
            org_id=org_id,
            user_id=user_id,
            actor_id=current_user["user_id"],
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        return {"success": True}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# User Invitations
# ============================================================================

@router.get("/invitations/pending")
async def get_my_invitations(
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get pending invitations for the current user."""
    invitations = await organization_service.get_user_invitations(current_user["email"])
    return {
        "success": True,
        "invitations": invitations,
    }


@router.post("/invitations/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Accept an invitation to join an organization."""
    try:
        member = await organization_service.accept_invitation(
            invitation_id=invitation_id,
            user_id=current_user["user_id"],
        )
        
        return {
            "success": True,
            "membership": member.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# Shared Credit Pool
# ============================================================================

@router.get("/{org_id}/credits")
async def get_org_credits(
    org_id: str,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get organization credit balance and stats."""
    # Verify membership
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization"
        )
    
    org = await organization_service.get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return {
        "success": True,
        "credit_balance": org.get("credit_balance", 0),
        "lifetime_credits_purchased": org.get("lifetime_credits_purchased", 0),
        "lifetime_credits_used": org.get("lifetime_credits_used", 0),
        "monthly_credit_budget": org.get("monthly_credit_budget"),
    }


# ============================================================================
# Compliance Packs
# ============================================================================

@router.get("/compliance-packs/list")
async def list_compliance_packs(
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get available compliance packs."""
    packs = await organization_service.get_compliance_packs()
    return {
        "success": True,
        "packs": packs,
    }


@router.get("/compliance-packs/{pack_id}")
async def get_compliance_pack(
    pack_id: str,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get compliance pack details."""
    pack = await organization_service.get_compliance_pack(pack_id)
    if not pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compliance pack not found"
        )
    
    return {
        "success": True,
        "pack": pack,
    }
