from database import database
from models import (
    Client, PortalUser, Property, Requirement, OnboardingStatus,
    UserRole, UserStatus, PasswordStatus, ComplianceStatus, RequirementStatus,
    AuditAction, SubscriptionStatus
)
from services.email_service import email_service
from utils.audit import create_audit_log
from auth import generate_secure_token, hash_token
from datetime import datetime, timedelta, timezone
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Compliance requirement rules
REQUIREMENT_RULES = [
    {"type": "gas_safety", "description": "Gas Safety Certificate", "frequency_days": 365},
    {"type": "eicr", "description": "Electrical Installation Condition Report", "frequency_days": 1825},
    {"type": "epc", "description": "Energy Performance Certificate", "frequency_days": 3650},
    {"type": "fire_alarm", "description": "Fire Alarm Inspection", "frequency_days": 365},
    {"type": "legionella", "description": "Legionella Risk Assessment", "frequency_days": 730}
]

class ProvisioningService:
    async def provision_client_portal(self, client_id: str) -> tuple[bool, str]:
        """Provision a client's portal access. This is the SINGLE SOURCE OF TRUTH for provisioning."""
        db = database.get_db()
        
        try:
            # Get client
            client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
            if not client:
                return False, "Client not found"
            
            # Precondition checks
            if client["onboarding_status"] not in [
                OnboardingStatus.INTAKE_PENDING.value,
                OnboardingStatus.PROVISIONING.value
            ]:
                logger.warning(f"Client {client_id} already provisioned or failed")
                return True, "Already provisioned"
            
            # In production, check subscription status
            # For development, allow PENDING status
            env = os.getenv("ENVIRONMENT", "development")
            if env == "production" and client["subscription_status"] != SubscriptionStatus.ACTIVE.value:
                return False, "Subscription not active"
            
            # STEP 1: Set provisioning status
            await db.clients.update_one(
                {"client_id": client_id},
                {"$set": {"onboarding_status": OnboardingStatus.PROVISIONING.value}}
            )
            
            await create_audit_log(
                action=AuditAction.PROVISIONING_STARTED,
                client_id=client_id
            )
            
            # STEP 2: Validate properties exist
            properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(100)
            if not properties:
                await self._fail_provisioning(client_id, "No properties found")
                return False, "No properties found"
            
            # STEP 3: Generate requirements for each property
            for prop in properties:
                await self._generate_requirements(client_id, prop["property_id"])
            
            # STEP 4: Compute initial compliance status
            for prop in properties:
                await self._update_property_compliance(prop["property_id"])
            
            # STEP 5: Create PortalUser if doesn't exist (idempotent)
            existing_user = await db.portal_users.find_one(
                {"client_id": client_id, "role": UserRole.ROLE_CLIENT_ADMIN.value},
                {"_id": 0}
            )
            
            if not existing_user:
                portal_user = PortalUser(
                    client_id=client_id,
                    auth_email=client["email"],
                    role=UserRole.ROLE_CLIENT_ADMIN,
                    status=UserStatus.INVITED,
                    password_status=PasswordStatus.NOT_SET,
                    must_set_password=True
                )
                
                doc = portal_user.model_dump()
                doc["created_at"] = doc["created_at"].isoformat()
                await db.portal_users.insert_one(doc)
                
                user_id = portal_user.portal_user_id
            else:
                user_id = existing_user["portal_user_id"]
            
            # STEP 6: Set onboarding status to PROVISIONED
            await db.clients.update_one(
                {"client_id": client_id},
                {"$set": {"onboarding_status": OnboardingStatus.PROVISIONED.value}}
            )
            
            await create_audit_log(
                action=AuditAction.PROVISIONING_COMPLETE,
                client_id=client_id,
                metadata={"portal_user_id": user_id}
            )
            
            # STEP 7: Generate and send password setup token
            await self._send_password_setup_link(client_id, user_id, client["email"], client["full_name"])
            
            logger.info(f"Provisioning complete for client {client_id}")
            return True, "Provisioning successful"
        
        except Exception as e:
            logger.error(f"Provisioning failed for client {client_id}: {e}")
            await self._fail_provisioning(client_id, str(e))
            return False, str(e)
    
    async def _generate_requirements(self, client_id: str, property_id: str):
        """Generate deterministic requirements for a property (idempotent)."""
        db = database.get_db()
        
        for rule in REQUIREMENT_RULES:
            # Check if requirement already exists
            existing = await db.requirements.find_one({
                "client_id": client_id,
                "property_id": property_id,
                "requirement_type": rule["type"]
            })
            
            if existing:
                continue
            
            # Create new requirement
            requirement = Requirement(
                client_id=client_id,
                property_id=property_id,
                requirement_type=rule["type"],
                description=rule["description"],
                frequency_days=rule["frequency_days"],
                due_date=datetime.now(timezone.utc) + timedelta(days=30),
                status=RequirementStatus.PENDING
            )
            
            doc = requirement.model_dump()
            for key in ["due_date", "created_at", "updated_at"]:
                if doc.get(key):
                    doc[key] = doc[key].isoformat()
            
            await db.requirements.insert_one(doc)
        
        await create_audit_log(
            action=AuditAction.REQUIREMENTS_GENERATED,
            client_id=client_id,
            resource_type="property",
            resource_id=property_id
        )
    
    async def _update_property_compliance(self, property_id: str):
        """Compute deterministic compliance status based on requirements."""
        db = database.get_db()
        
        requirements = await db.requirements.find(
            {"property_id": property_id},
            {"_id": 0}
        ).to_list(100)
        
        # Deterministic compliance logic
        red_count = sum(1 for r in requirements if r["status"] == RequirementStatus.OVERDUE.value)
        amber_count = sum(1 for r in requirements if r["status"] == RequirementStatus.EXPIRING_SOON.value)
        
        if red_count > 0:
            status = ComplianceStatus.RED
        elif amber_count > 0:
            status = ComplianceStatus.AMBER
        else:
            status = ComplianceStatus.GREEN
        
        await db.properties.update_one(
            {"property_id": property_id},
            {"$set": {"compliance_status": status.value}}
        )
    
    async def _send_password_setup_link(self, client_id: str, user_id: str, email: str, name: str):
        """Generate token and send password setup email."""
        db = database.get_db()
        
        # Generate token
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        
        # Create password token record
        from models import PasswordToken
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=user_id,
            client_id=client_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by="SYSTEM",
            send_count=1
        )
        
        doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if doc.get(key) and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()
        
        await db.password_tokens.insert_one(doc)
        
        # Create setup link
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        setup_link = f"{frontend_url}/set-password?token={raw_token}"
        
        # Send email
        await email_service.send_password_setup_email(
            recipient=email,
            client_name=name,
            setup_link=setup_link,
            client_id=client_id
        )
        
        await create_audit_log(
            action=AuditAction.PASSWORD_TOKEN_GENERATED,
            client_id=client_id,
            actor_id=user_id,
            metadata={"email": email}
        )
    
    async def _fail_provisioning(self, client_id: str, reason: str):
        """Mark provisioning as failed."""
        db = database.get_db()
        
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": {"onboarding_status": OnboardingStatus.FAILED.value}}
        )
        
        await create_audit_log(
            action=AuditAction.PROVISIONING_FAILED,
            client_id=client_id,
            metadata={"reason": reason}
        )

provisioning_service = ProvisioningService()
