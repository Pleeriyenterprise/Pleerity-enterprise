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
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Enhanced fallback compliance requirement rules with property attribute conditions
FALLBACK_REQUIREMENT_RULES = [
    {
        "type": "gas_safety", 
        "description": "Gas Safety Certificate", 
        "frequency_days": 365,
        "condition": "has_gas_supply"  # Only if property has gas
    },
    {
        "type": "eicr", 
        "description": "Electrical Installation Condition Report", 
        "frequency_days": 1825,  # 5 years default
        "frequency_by_age": {  # Dynamic frequency based on building age
            "old": 1095,  # 3 years for buildings > 50 years
            "standard": 1825  # 5 years standard
        }
    },
    {
        "type": "epc", 
        "description": "Energy Performance Certificate", 
        "frequency_days": 3650
    },
    {
        "type": "fire_alarm", 
        "description": "Fire Alarm Inspection", 
        "frequency_days": 365
    },
    {
        "type": "legionella", 
        "description": "Legionella Risk Assessment", 
        "frequency_days": 730
    }
]

# HMO-specific requirements
HMO_REQUIREMENTS = [
    {
        "type": "hmo_license",
        "description": "HMO License",
        "frequency_days": 1825,  # 5 years
        "condition": "hmo_license_required"
    },
    {
        "type": "fire_risk_assessment",
        "description": "Fire Risk Assessment",
        "frequency_days": 365
    },
    {
        "type": "emergency_lighting",
        "description": "Emergency Lighting Test",
        "frequency_days": 365
    },
    {
        "type": "fire_extinguisher",
        "description": "Fire Extinguisher Service",
        "frequency_days": 365
    }
]

# Communal area requirements
COMMUNAL_REQUIREMENTS = [
    {
        "type": "communal_cleaning",
        "description": "Communal Area Cleaning Schedule",
        "frequency_days": 30
    },
    {
        "type": "communal_fire_doors",
        "description": "Fire Door Inspection",
        "frequency_days": 365
    }
]

# Location-specific requirements (by local authority)
LOCATION_RULES = {
    "LONDON": [
        {
            "type": "selective_license",
            "description": "Selective Licensing (London)",
            "frequency_days": 1825
        }
    ],
    "MANCHESTER": [
        {
            "type": "selective_license",
            "description": "Selective Licensing (Manchester)",
            "frequency_days": 1825
        }
    ]
}

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
        """Generate deterministic requirements for a property based on its attributes.
        
        Uses rules from the database if available, otherwise falls back to enhanced
        rules that consider property type, HMO status, building age, and location.
        """
        db = database.get_db()
        
        # Get property details for dynamic rule application
        property_doc = await db.properties.find_one(
            {"property_id": property_id},
            {"_id": 0}
        )
        
        if not property_doc:
            logger.warning(f"Property {property_id} not found for requirement generation")
            return
        
        property_type = property_doc.get("property_type", "residential").upper()
        is_hmo = property_doc.get("is_hmo", False)
        hmo_license_required = property_doc.get("hmo_license_required", False)
        has_gas_supply = property_doc.get("has_gas_supply", True)
        building_age_years = property_doc.get("building_age_years")
        has_communal_areas = property_doc.get("has_communal_areas", False)
        local_authority = property_doc.get("local_authority", "").upper()
        
        # Try to get rules from database first
        db_rules = await db.requirement_rules.find(
            {"is_active": True},
            {"_id": 0}
        ).to_list(100)
        
        if db_rules:
            # Use database rules with property type filtering
            await self._apply_db_rules(db_rules, client_id, property_id, property_type)
        else:
            # Use enhanced fallback rules with dynamic conditions
            await self._apply_dynamic_rules(
                client_id, 
                property_id, 
                property_type,
                is_hmo,
                hmo_license_required,
                has_gas_supply,
                building_age_years,
                has_communal_areas,
                local_authority
            )
        
        await create_audit_log(
            action=AuditAction.REQUIREMENTS_GENERATED,
            client_id=client_id,
            resource_type="property",
            resource_id=property_id,
            metadata={
                "property_type": property_type,
                "is_hmo": is_hmo,
                "has_gas_supply": has_gas_supply,
                "building_age_years": building_age_years,
                "local_authority": local_authority
            }
        )
    
    async def _apply_db_rules(self, rules: List[Dict], client_id: str, property_id: str, property_type: str):
        """Apply database rules to generate requirements."""
        db = database.get_db()
        
        for rule in rules:
            # Check if rule applies to this property type
            applicable_to = rule.get("applicable_to", "ALL")
            if applicable_to != "ALL" and applicable_to != property_type:
                continue
            
            await self._create_requirement_if_not_exists(
                client_id,
                property_id,
                rule["rule_type"],
                rule["name"],
                rule["frequency_days"],
                rule.get("warning_days", 30)
            )
    
    async def _apply_dynamic_rules(
        self,
        client_id: str,
        property_id: str,
        property_type: str,
        is_hmo: bool,
        hmo_license_required: bool,
        has_gas_supply: bool,
        building_age_years: Optional[int],
        has_communal_areas: bool,
        local_authority: str
    ):
        """Apply enhanced dynamic rules based on property attributes."""
        db = database.get_db()
        
        # 1. Apply base requirements
        for rule in FALLBACK_REQUIREMENT_RULES:
            # Check gas supply condition
            if rule.get("condition") == "has_gas_supply" and not has_gas_supply:
                logger.info(f"Skipping {rule['type']} - no gas supply")
                continue
            
            # Calculate frequency based on building age for EICR
            frequency_days = rule["frequency_days"]
            if rule["type"] == "eicr" and building_age_years:
                if building_age_years > 50:
                    frequency_days = rule.get("frequency_by_age", {}).get("old", 1095)
                    logger.info(f"Using shorter EICR frequency ({frequency_days} days) for old building")
            
            await self._create_requirement_if_not_exists(
                client_id,
                property_id,
                rule["type"],
                rule["description"],
                frequency_days
            )
        
        # 2. Apply HMO-specific requirements
        if is_hmo or property_type == "HMO":
            logger.info(f"Applying HMO requirements for property {property_id}")
            for rule in HMO_REQUIREMENTS:
                # Check HMO license condition
                if rule.get("condition") == "hmo_license_required" and not hmo_license_required:
                    continue
                
                await self._create_requirement_if_not_exists(
                    client_id,
                    property_id,
                    rule["type"],
                    rule["description"],
                    rule["frequency_days"]
                )
        
        # 3. Apply communal area requirements
        if has_communal_areas:
            logger.info(f"Applying communal area requirements for property {property_id}")
            for rule in COMMUNAL_REQUIREMENTS:
                await self._create_requirement_if_not_exists(
                    client_id,
                    property_id,
                    rule["type"],
                    rule["description"],
                    rule["frequency_days"]
                )
        
        # 4. Apply location-specific requirements
        if local_authority and local_authority in LOCATION_RULES:
            logger.info(f"Applying {local_authority} location-specific requirements")
            for rule in LOCATION_RULES[local_authority]:
                await self._create_requirement_if_not_exists(
                    client_id,
                    property_id,
                    rule["type"],
                    rule["description"],
                    rule["frequency_days"]
                )
    
    async def _create_requirement_if_not_exists(
        self,
        client_id: str,
        property_id: str,
        requirement_type: str,
        description: str,
        frequency_days: int,
        warning_days: int = 30
    ):
        """Create a requirement if it doesn't already exist (idempotent)."""
        db = database.get_db()
        
        # Check if requirement already exists
        existing = await db.requirements.find_one({
            "client_id": client_id,
            "property_id": property_id,
            "requirement_type": requirement_type
        })
        
        if existing:
            return
        
        # Create new requirement
        requirement = Requirement(
            client_id=client_id,
            property_id=property_id,
            requirement_type=requirement_type,
            description=description,
            frequency_days=frequency_days,
            due_date=datetime.now(timezone.utc) + timedelta(days=warning_days),
            status=RequirementStatus.PENDING
        )
        
        doc = requirement.model_dump()
        for key in ["due_date", "created_at", "updated_at"]:
            if doc.get(key):
                doc[key] = doc[key].isoformat()
        
        await db.requirements.insert_one(doc)
    
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
