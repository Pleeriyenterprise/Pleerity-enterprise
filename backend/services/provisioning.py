from database import database
from models import (
    Client, PortalUser, Property, Requirement, OnboardingStatus,
    UserRole, UserStatus, PasswordStatus, ComplianceStatus, RequirementStatus,
    AuditAction, SubscriptionStatus
)
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
    async def provision_client_portal_core(
        self, client_id: str
    ) -> tuple[bool, str, Optional[str]]:
        """
        Run provisioning steps 1-6 only (through PROVISIONED + enablement).
        Idempotent: no duplicate portal users/requirements. Returns (success, message, portal_user_id).
        Used by provisioning job runner; migrate + welcome email are done by runner.
        """
        db = database.get_db()
        try:
            client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
            if not client:
                return False, "Client not found", None
            if client["onboarding_status"] == OnboardingStatus.PROVISIONED.value:
                existing_user = await db.portal_users.find_one(
                    {"client_id": client_id, "role": UserRole.ROLE_CLIENT_ADMIN.value},
                    {"_id": 0, "portal_user_id": 1}
                )
                return True, "Already provisioned", (existing_user["portal_user_id"] if existing_user else None)
            env = os.getenv("ENVIRONMENT", "development")
            if env == "production" and client["subscription_status"] != SubscriptionStatus.ACTIVE.value:
                return False, "Subscription not active", None
            now_utc = datetime.now(timezone.utc)
            await db.clients.update_one(
                {"client_id": client_id},
                {
                    "$set": {
                        "onboarding_status": OnboardingStatus.PROVISIONING.value,
                        "provisioning_status": "IN_PROGRESS",
                        "provisioning_started_at": now_utc,
                    },
                    "$unset": {"last_invite_error": "", "last_provisioning_error": ""},
                }
            )
            await create_audit_log(action=AuditAction.PROVISIONING_STARTED, client_id=client_id)
            properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(100)
            if not properties:
                await self._fail_provisioning(client_id, "No properties found")
                return False, "No properties found", None
            for prop in properties:
                await self._generate_requirements(client_id, prop["property_id"])
            for prop in properties:
                await self._update_property_compliance(prop["property_id"])
            from services.compliance_recalc_queue import enqueue_compliance_recalc, TRIGGER_PROVISIONING, ACTOR_SYSTEM
            for prop in properties:
                await enqueue_compliance_recalc(
                    property_id=prop["property_id"],
                    client_id=client_id,
                    trigger_reason=TRIGGER_PROVISIONING,
                    actor_type=ACTOR_SYSTEM,
                    actor_id=None,
                    correlation_id=f"PROVISIONING:{prop['property_id']}:{client_id}",
                )
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
                now_utc = datetime.now(timezone.utc)
                await db.clients.update_one(
                    {"client_id": client_id},
                    {"$set": {"portal_user_created_at": now_utc}}
                )
            else:
                user_id = existing_user["portal_user_id"]
            now_utc = datetime.now(timezone.utc)
            await db.clients.update_one(
                {"client_id": client_id},
                {
                    "$set": {
                        "onboarding_status": OnboardingStatus.PROVISIONED.value,
                        "provisioning_status": "COMPLETED",
                        "provisioning_completed_at": now_utc,
                    },
                    "$unset": {"last_provisioning_error": ""},
                }
            )
            await create_audit_log(
                action=AuditAction.PROVISIONING_COMPLETE,
                client_id=client_id,
                metadata={"portal_user_id": user_id}
            )
            try:
                from services.enablement_service import emit_enablement_event
                from models.enablement import EnablementEventType
                plan_code = client.get("billing_plan") or client.get("plan_code")
                await emit_enablement_event(
                    event_type=EnablementEventType.PROVISIONING_COMPLETED,
                    client_id=client_id,
                    plan_code=plan_code,
                    context_payload={"portal_user_id": user_id}
                )
            except Exception as enable_err:
                logger.warning(f"Failed to emit enablement event: {enable_err}")
            return True, "OK", user_id
        except Exception as e:
            logger.error(f"Provisioning core failed for client {client_id}: {e}", exc_info=True)
            await self._fail_provisioning(client_id, str(e))
            return False, str(e), None

    async def provision_client_portal(self, client_id: str) -> tuple[bool, str]:
        """Full provisioning: core + migrate CLEAN uploads + send password setup email. Backward-compat / admin."""
        success, message, user_id = await self.provision_client_portal_core(client_id)
        if not success:
            return False, message
        if user_id is None and message == "Already provisioned":
            # Resolve user_id for migrate/email
            db = database.get_db()
            client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
            existing_user = await db.portal_users.find_one(
                {"client_id": client_id, "role": UserRole.ROLE_CLIENT_ADMIN.value},
                {"_id": 0, "portal_user_id": 1}
            )
            user_id = existing_user["portal_user_id"] if existing_user else None
        if not user_id:
            return True, message
        db = database.get_db()
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        try:
            from services.intake_upload_migration import migrate_intake_uploads_to_vault
            result = await migrate_intake_uploads_to_vault(client_id)
            if result.get("migrated", 0) > 0:
                logger.info(f"Migrated {result['migrated']} intake upload(s) for client {client_id}")
            if result.get("errors"):
                logger.warning(f"Intake upload migration errors for {client_id}: {result['errors']}")
        except Exception as mig_err:
            logger.warning(f"Intake upload migration failed for {client_id}: {mig_err}")
        try:
            ok, act_status, act_err = await self._send_password_setup_link(client_id, user_id, client["email"], client.get("full_name", "Valued Customer"))
            now_act = datetime.now(timezone.utc)
            set_fields = {"activation_email_status": act_status}
            unset_fields = {}
            if ok:
                set_fields["activation_email_sent_at"] = now_act
                unset_fields = {"last_invite_error": "", "activation_email_error": ""}
            else:
                if act_err:
                    set_fields["activation_email_error"] = act_err[:1000]
                    set_fields["last_invite_error"] = act_err[:500]
            payload = {"$set": set_fields}
            if unset_fields:
                payload["$unset"] = unset_fields
            await db.clients.update_one({"client_id": client_id}, payload)
            if not ok:
                await create_audit_log(
                    action=AuditAction.PORTAL_INVITE_EMAIL_FAILED,
                    client_id=client_id,
                    metadata={"error": (act_err or act_status)[:500], "portal_user_id": user_id, "activation_email_status": act_status}
                )
                return True, "Provisioning successful but invite email failed; use resend invite to retry"
        except Exception as email_err:
            logger.error(f"Portal invite email failed for client {client_id}: {email_err}")
            err_msg = str(email_err)[:500]
            await db.clients.update_one(
                {"client_id": client_id},
                {"$set": {"last_invite_error": err_msg, "activation_email_status": "FAILED", "activation_email_error": err_msg[:1000]}}
            )
            await create_audit_log(
                action=AuditAction.PORTAL_INVITE_EMAIL_FAILED,
                client_id=client_id,
                metadata={"error": err_msg, "portal_user_id": user_id}
            )
            return True, "Provisioning successful but invite email failed; use resend invite to retry"
        logger.info(f"Provisioning complete for client {client_id}")
        return True, "Provisioning successful"
    
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
        
        property_type = (property_doc.get("property_type") or "residential").upper()
        is_hmo = property_doc.get("is_hmo", False)
        hmo_license_required = property_doc.get("hmo_license_required", False)
        has_gas_supply = property_doc.get("has_gas_supply", True)
        building_age_years = property_doc.get("building_age_years")
        has_communal_areas = property_doc.get("has_communal_areas", False)
        local_authority = (property_doc.get("local_authority") or "").upper()
        
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
    
    async def _send_password_setup_link(
        self,
        client_id: str,
        user_id: str,
        email: str,
        name: str,
        idempotency_key: Optional[str] = None,
    ) -> tuple[bool, str, Optional[str]]:
        """
        Generate token and send password setup email via NotificationOrchestrator.
        Returns (success, status, error_message) where status is SENT | FAILED | NOT_CONFIGURED.
        Does not raise; callers should persist activation_email_* on client from return value.
        """
        db = database.get_db()

        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)

        from models import PasswordToken
        link_expiry_hours = 24
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=user_id,
            client_id=client_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=link_expiry_hours),
            created_by="SYSTEM",
            send_count=1
        )

        doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if doc.get(key) and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()

        await db.password_tokens.insert_one(doc)

        from utils.public_app_url import get_frontend_base_url
        try:
            base_url = get_frontend_base_url()
        except ValueError as e:
            logger.error("Activation link not sent: %s", e)
            return False, "FAILED", str(e)[:500]
        setup_link = f"{base_url.rstrip('/')}/set-password?token={raw_token}"
        logger.info("Activation email link generated base=%s path=/set-password?token=***", base_url.rstrip("/"))

        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "customer_reference": 1})
        crn = (client or {}).get("customer_reference") or ""
        first_name = (name or "").strip().split()[0] if (name and (name or "").strip()) else "there"
        support_email = os.getenv("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk") or "info@pleerityenterprise.co.uk"

        from services.notification_orchestrator import notification_orchestrator
        result = await notification_orchestrator.send(
            template_key="WELCOME_EMAIL",
            client_id=client_id,
            context={
                "setup_link": setup_link,
                "client_name": name,
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance",
                "crn": crn,
                "first_name": first_name,
                "support_email": support_email,
                "link_expiry_hours": link_expiry_hours,
                "if_you_did_not_request": "If you didn't request this link, you can safely ignore this email.",
            },
            idempotency_key=idempotency_key,
            event_type="provisioning_welcome",
        )
        def _mask_email(addr: str) -> str:
            if not addr or "@" not in addr:
                return "***"
            local, domain = addr.split("@", 1)
            return f"{local[:3]}***@{domain[:2]}***" if len(local) >= 3 else "***@***"

        if result.outcome in ("sent", "duplicate_ignored"):
            await create_audit_log(
                action=AuditAction.PASSWORD_TOKEN_GENERATED,
                client_id=client_id,
                actor_id=user_id,
                metadata={"email": email}
            )
            provider_message_id = (result.details or {}).get("provider_message_id") or getattr(result, "message_id", None)
            await create_audit_log(
                action=AuditAction.ACTIVATION_EMAIL_SENT,
                client_id=client_id,
                actor_id=user_id,
                metadata={
                    "provider": "postmark",
                    "template_key": "WELCOME_EMAIL",
                    "recipient_masked": _mask_email(email),
                    "message_id": result.message_id,
                    "provider_message_id": provider_message_id,
                }
            )
            logger.info(
                "ACTIVATION_EMAIL_SENT client_id=%s provider=postmark template=WELCOME_EMAIL recipient_masked=%s message_id=%s",
                client_id, _mask_email(email), result.message_id,
            )
            return True, "SENT", None
        if result.outcome == "blocked" and (result.block_reason or "").strip() == "BLOCKED_PROVIDER_NOT_CONFIGURED":
            err_msg = (result.error_message or result.block_reason or "POSTMARK_SERVER_TOKEN not set")[:500]
            logger.warning("Activation email not sent: Postmark not configured (BLOCKED_PROVIDER_NOT_CONFIGURED)")
            await create_audit_log(
                action=AuditAction.ACTIVATION_EMAIL_FAILED,
                client_id=client_id,
                metadata={"error_message": err_msg, "provider": "postmark", "provider_response": "not_configured"},
            )
            return False, "NOT_CONFIGURED", err_msg
        err = (result.error_message or result.block_reason or result.outcome or "unknown")[:500]
        await create_audit_log(
            action=AuditAction.ACTIVATION_EMAIL_FAILED,
            client_id=client_id,
            metadata={
                "error_message": err,
                "provider": "postmark",
                "provider_response_code": getattr(result, "status_code", None),
            },
        )
        logger.warning("ACTIVATION_EMAIL_FAILED client_id=%s error=%s provider_response_code=%s", client_id, err, getattr(result, "status_code", None))
        return False, "FAILED", err
    
    async def _fail_provisioning(self, client_id: str, reason: str):
        """Mark provisioning as failed."""
        db = database.get_db()
        now_utc = datetime.now(timezone.utc)
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "onboarding_status": OnboardingStatus.FAILED.value,
                    "provisioning_status": "FAILED",
                    "last_provisioning_error": (reason or "")[:1000],
                }
            }
        )
        
        await create_audit_log(
            action=AuditAction.PROVISIONING_FAILED,
            client_id=client_id,
            metadata={"reason": reason}
        )

provisioning_service = ProvisioningService()
