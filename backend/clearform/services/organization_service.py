"""ClearForm Organization Service

Manages institutional accounts, team membership, and shared credit pools.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import logging
import re

from database import database
from clearform.models.organizations import (
    Organization,
    OrgMember,
    OrgInvitation,
    OrgMemberRole,
    InvitationStatus,
    CompliancePack,
    DEFAULT_COMPLIANCE_PACKS,
)
from clearform.services.audit_service import audit_service
from clearform.models.audit import AuditAction

logger = logging.getLogger(__name__)


class OrganizationService:
    """Service for organization management."""
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        return slug[:50]
    
    # =========================================================================
    # Organization CRUD
    # =========================================================================
    
    async def create_organization(
        self,
        owner_id: str,
        name: str,
        description: Optional[str] = None,
        org_type: str = "SMALL_BUSINESS",
    ) -> Organization:
        """Create a new organization."""
        db = self._get_db()
        
        slug = self._generate_slug(name)
        
        # Ensure unique slug
        existing = await db.clearform_organizations.find_one({"slug": slug})
        if existing:
            slug = f"{slug}-{datetime.now().strftime('%H%M%S')}"
        
        org = Organization(
            owner_id=owner_id,
            name=name,
            slug=slug,
            description=description,
            org_type=org_type,
        )
        
        await db.clearform_organizations.insert_one(org.model_dump())
        
        # Add owner as member
        owner_member = OrgMember(
            org_id=org.org_id,
            user_id=owner_id,
            role=OrgMemberRole.OWNER,
        )
        await db.clearform_org_members.insert_one(owner_member.model_dump())
        
        # Update user with org
        await db.clearform_users.update_one(
            {"user_id": owner_id},
            {"$set": {"org_id": org.org_id, "updated_at": datetime.now(timezone.utc)}}
        )
        
        # Audit
        await audit_service.log(
            action=AuditAction.ORG_CREATED,
            user_id=owner_id,
            org_id=org.org_id,
            resource_type="organization",
            resource_id=org.org_id,
            description=f"Organization '{name}' created",
        )
        
        logger.info(f"Created organization: {org.org_id} by {owner_id}")
        return org
    
    async def get_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        """Get organization by ID."""
        db = self._get_db()
        return await db.clearform_organizations.find_one({"org_id": org_id}, {"_id": 0})
    
    async def get_organization_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get organization by slug."""
        db = self._get_db()
        return await db.clearform_organizations.find_one({"slug": slug}, {"_id": 0})
    
    async def update_organization(
        self,
        org_id: str,
        updates: Dict[str, Any],
        actor_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Update organization."""
        db = self._get_db()
        
        updates["updated_at"] = datetime.now(timezone.utc)
        updates.pop("org_id", None)
        updates.pop("owner_id", None)
        
        result = await db.clearform_organizations.update_one(
            {"org_id": org_id},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            await audit_service.log(
                action=AuditAction.ORG_UPDATED,
                user_id=actor_id,
                org_id=org_id,
                resource_type="organization",
                resource_id=org_id,
                description="Organization settings updated",
                details={"updates": list(updates.keys())},
            )
            return await self.get_organization(org_id)
        return None
    
    async def get_user_organizations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all organizations a user belongs to."""
        db = self._get_db()
        
        # Get user's memberships
        memberships = await db.clearform_org_members.find(
            {"user_id": user_id, "is_active": True},
            {"_id": 0}
        ).to_list(20)
        
        org_ids = [m["org_id"] for m in memberships]
        
        if not org_ids:
            return []
        
        orgs = await db.clearform_organizations.find(
            {"org_id": {"$in": org_ids}, "is_active": True},
            {"_id": 0}
        ).to_list(20)
        
        # Enrich with user's role
        membership_map = {m["org_id"]: m for m in memberships}
        for org in orgs:
            membership = membership_map.get(org["org_id"])
            if membership:
                org["user_role"] = membership.get("role")
                org["member_id"] = membership.get("member_id")
        
        return orgs
    
    # =========================================================================
    # Member Management
    # =========================================================================
    
    async def get_members(self, org_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get organization members."""
        db = self._get_db()
        
        query = {"org_id": org_id}
        if not include_inactive:
            query["is_active"] = True
        
        members = await db.clearform_org_members.find(query, {"_id": 0}).to_list(100)
        
        # Enrich with user info
        user_ids = [m["user_id"] for m in members]
        users = await db.clearform_users.find(
            {"user_id": {"$in": user_ids}},
            {"_id": 0, "user_id": 1, "email": 1, "full_name": 1}
        ).to_list(100)
        
        user_map = {u["user_id"]: u for u in users}
        for member in members:
            user = user_map.get(member["user_id"], {})
            member["email"] = user.get("email")
            member["full_name"] = user.get("full_name")
        
        return members
    
    async def get_member(self, org_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get specific member."""
        db = self._get_db()
        return await db.clearform_org_members.find_one(
            {"org_id": org_id, "user_id": user_id},
            {"_id": 0}
        )
    
    async def update_member_role(
        self,
        org_id: str,
        user_id: str,
        new_role: OrgMemberRole,
        actor_id: str,
    ) -> bool:
        """Update member role."""
        db = self._get_db()
        
        # Can't change owner role
        if new_role == OrgMemberRole.OWNER:
            raise ValueError("Cannot assign owner role")
        
        result = await db.clearform_org_members.update_one(
            {"org_id": org_id, "user_id": user_id},
            {"$set": {"role": new_role.value}}
        )
        
        if result.modified_count > 0:
            await audit_service.log(
                action=AuditAction.ORG_MEMBER_ROLE_CHANGED,
                user_id=actor_id,
                org_id=org_id,
                resource_type="org_member",
                resource_id=user_id,
                description=f"Member role changed to {new_role.value}",
            )
            return True
        return False
    
    async def remove_member(
        self,
        org_id: str,
        user_id: str,
        actor_id: str,
    ) -> bool:
        """Remove member from organization."""
        db = self._get_db()
        
        # Get member
        member = await self.get_member(org_id, user_id)
        if not member:
            return False
        
        # Can't remove owner
        if member.get("role") == OrgMemberRole.OWNER.value:
            raise ValueError("Cannot remove organization owner")
        
        # Soft delete
        result = await db.clearform_org_members.update_one(
            {"org_id": org_id, "user_id": user_id},
            {"$set": {"is_active": False}}
        )
        
        if result.modified_count > 0:
            # Update member count
            await db.clearform_organizations.update_one(
                {"org_id": org_id},
                {"$inc": {"member_count": -1}}
            )
            
            # Remove org from user
            await db.clearform_users.update_one(
                {"user_id": user_id, "org_id": org_id},
                {"$set": {"org_id": None, "updated_at": datetime.now(timezone.utc)}}
            )
            
            await audit_service.log(
                action=AuditAction.ORG_MEMBER_REMOVED,
                user_id=actor_id,
                org_id=org_id,
                resource_type="org_member",
                resource_id=user_id,
                description="Member removed from organization",
            )
            return True
        return False
    
    # =========================================================================
    # Invitations
    # =========================================================================
    
    async def create_invitation(
        self,
        org_id: str,
        email: str,
        role: OrgMemberRole,
        inviter_id: str,
        message: Optional[str] = None,
    ) -> OrgInvitation:
        """Create invitation to join organization."""
        db = self._get_db()
        
        # Check if already member
        existing_user = await db.clearform_users.find_one({"email": email.lower()})
        if existing_user:
            existing_member = await self.get_member(org_id, existing_user["user_id"])
            if existing_member and existing_member.get("is_active"):
                raise ValueError("User is already a member")
        
        # Check for pending invitation
        existing_inv = await db.clearform_org_invitations.find_one({
            "org_id": org_id,
            "email": email.lower(),
            "status": InvitationStatus.PENDING.value,
        })
        if existing_inv:
            raise ValueError("Invitation already pending for this email")
        
        invitation = OrgInvitation(
            org_id=org_id,
            email=email.lower(),
            role=role,
            message=message,
            invited_by=inviter_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        
        await db.clearform_org_invitations.insert_one(invitation.model_dump())
        
        # TODO: Send invitation email
        
        logger.info(f"Created invitation {invitation.invitation_id} for {email}")
        return invitation
    
    async def accept_invitation(
        self,
        invitation_id: str,
        user_id: str,
    ) -> OrgMember:
        """Accept invitation and join organization."""
        db = self._get_db()
        
        # Get invitation
        invitation = await db.clearform_org_invitations.find_one(
            {"invitation_id": invitation_id},
            {"_id": 0}
        )
        
        if not invitation:
            raise ValueError("Invitation not found")
        
        if invitation["status"] != InvitationStatus.PENDING.value:
            raise ValueError(f"Invitation is {invitation['status']}")
        
        if datetime.fromisoformat(str(invitation["expires_at"]).replace("Z", "+00:00")) < datetime.now(timezone.utc):
            await db.clearform_org_invitations.update_one(
                {"invitation_id": invitation_id},
                {"$set": {"status": InvitationStatus.EXPIRED.value}}
            )
            raise ValueError("Invitation has expired")
        
        # Verify email matches
        user = await db.clearform_users.find_one({"user_id": user_id}, {"_id": 0})
        if not user or user["email"].lower() != invitation["email"].lower():
            raise ValueError("Email does not match invitation")
        
        # Create membership
        member = OrgMember(
            org_id=invitation["org_id"],
            user_id=user_id,
            role=invitation["role"],
            invited_by=invitation["invited_by"],
            invitation_email=invitation["email"],
        )
        
        await db.clearform_org_members.insert_one(member.model_dump())
        
        # Update invitation
        await db.clearform_org_invitations.update_one(
            {"invitation_id": invitation_id},
            {
                "$set": {
                    "status": InvitationStatus.ACCEPTED.value,
                    "accepted_by_user_id": user_id,
                    "responded_at": datetime.now(timezone.utc),
                }
            }
        )
        
        # Update org member count
        await db.clearform_organizations.update_one(
            {"org_id": invitation["org_id"]},
            {"$inc": {"member_count": 1}}
        )
        
        # Update user with org
        await db.clearform_users.update_one(
            {"user_id": user_id},
            {"$set": {"org_id": invitation["org_id"], "updated_at": datetime.now(timezone.utc)}}
        )
        
        await audit_service.log(
            action=AuditAction.ORG_MEMBER_ADDED,
            user_id=user_id,
            org_id=invitation["org_id"],
            resource_type="org_member",
            resource_id=user_id,
            description="User joined organization via invitation",
        )
        
        return member
    
    async def get_pending_invitations(self, org_id: str) -> List[Dict[str, Any]]:
        """Get pending invitations for an organization."""
        db = self._get_db()
        return await db.clearform_org_invitations.find(
            {"org_id": org_id, "status": InvitationStatus.PENDING.value},
            {"_id": 0}
        ).to_list(50)
    
    async def get_user_invitations(self, email: str) -> List[Dict[str, Any]]:
        """Get pending invitations for a user by email."""
        db = self._get_db()
        invitations = await db.clearform_org_invitations.find(
            {"email": email.lower(), "status": InvitationStatus.PENDING.value},
            {"_id": 0}
        ).to_list(20)
        
        # Enrich with org info
        org_ids = [inv["org_id"] for inv in invitations]
        orgs = await db.clearform_organizations.find(
            {"org_id": {"$in": org_ids}},
            {"_id": 0, "org_id": 1, "name": 1}
        ).to_list(20)
        
        org_map = {o["org_id"]: o for o in orgs}
        for inv in invitations:
            org = org_map.get(inv["org_id"], {})
            inv["org_name"] = org.get("name")
        
        return invitations
    
    # =========================================================================
    # Shared Credit Pool
    # =========================================================================
    
    async def add_org_credits(
        self,
        org_id: str,
        amount: int,
        description: str,
        reference_id: Optional[str] = None,
    ) -> int:
        """Add credits to organization pool."""
        db = self._get_db()
        
        result = await db.clearform_organizations.update_one(
            {"org_id": org_id},
            {
                "$inc": {
                    "credit_balance": amount,
                    "lifetime_credits_purchased": amount,
                },
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        if result.modified_count > 0:
            org = await self.get_organization(org_id)
            
            await audit_service.log(
                action=AuditAction.CREDITS_GRANTED,
                org_id=org_id,
                resource_type="organization",
                resource_id=org_id,
                description=description,
                details={"amount": amount, "reference_id": reference_id},
            )
            
            return org.get("credit_balance", 0)
        return 0
    
    async def deduct_org_credits(
        self,
        org_id: str,
        user_id: str,
        amount: int,
        description: str,
        reference_id: Optional[str] = None,
    ) -> bool:
        """Deduct credits from organization pool."""
        db = self._get_db()
        
        # Check balance
        org = await self.get_organization(org_id)
        if not org or org.get("credit_balance", 0) < amount:
            return False
        
        # Check member credit limit
        member = await self.get_member(org_id, user_id)
        if member and member.get("credit_limit"):
            # TODO: Track monthly usage per member
            pass
        
        result = await db.clearform_organizations.update_one(
            {"org_id": org_id, "credit_balance": {"$gte": amount}},
            {
                "$inc": {
                    "credit_balance": -amount,
                    "lifetime_credits_used": amount,
                },
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        if result.modified_count > 0:
            await audit_service.log(
                action=AuditAction.CREDITS_DEDUCTED,
                user_id=user_id,
                org_id=org_id,
                resource_type="organization",
                resource_id=org_id,
                description=description,
                details={"amount": amount, "reference_id": reference_id},
            )
            return True
        return False
    
    # =========================================================================
    # Compliance Packs
    # =========================================================================
    
    async def initialize_compliance_packs(self) -> int:
        """Initialize default compliance packs."""
        db = self._get_db()
        count = 0
        
        for pack in DEFAULT_COMPLIANCE_PACKS:
            existing = await db.clearform_compliance_packs.find_one({"code": pack.code})
            if not existing:
                await db.clearform_compliance_packs.insert_one(pack.model_dump())
                count += 1
        
        return count
    
    async def get_compliance_packs(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all compliance packs."""
        db = self._get_db()
        
        query = {}
        if active_only:
            query["is_active"] = True
        
        return await db.clearform_compliance_packs.find(query, {"_id": 0}).sort("display_order", 1).to_list(50)
    
    async def get_compliance_pack(self, pack_id: str) -> Optional[Dict[str, Any]]:
        """Get a compliance pack by ID."""
        db = self._get_db()
        return await db.clearform_compliance_packs.find_one({"pack_id": pack_id}, {"_id": 0})


# Global instance
organization_service = OrganizationService()
