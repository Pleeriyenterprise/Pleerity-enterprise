from database import database
from models import (
    Client, PortalUser, Property, Requirement, OnboardingStatus,
    UserRole, UserStatus, PasswordStatus, ComplianceStatus, RequirementStatus,
    AuditAction, SubscriptionStatus
)
from utils.audit import create_audit_log
from services.client_lifecycle_service import persist_operational_client_lifecycle_if_needed
from auth import generate_secure_token, hash_token
from datetime import datetime, timedelta, timezone
import os
import logging
from typing import List, Dict, Optional, Any, Set

from services.compliance_rules_registry import (
    governed_requirement_rule_covers_property,
    portfolio_jurisdiction_label,
    scoring_jurisdiction_for_property,
)
from services.requirement_action_resolver import infer_action_type
from services.compliance_requirement_engine import resolve_engine_payload_from_code
from services.requirement_materialization_service import materialize_requirements_for_property

logger = logging.getLogger(__name__)

REQUIREMENT_GENERATION_SOURCE_DB_RULE = "requirement_rules"

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
            from services.compliance_recalc_queue import TRIGGER_PROVISIONING, ACTOR_SYSTEM
            from services.compliance_recalc_lifecycle_transition import (
                enqueue_governed_compliance_recalc as enqueue_compliance_recalc,
            )
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
            await persist_operational_client_lifecycle_if_needed(db, client_id)
            await create_audit_log(
                action=AuditAction.PROVISIONING_COMPLETE,
                client_id=client_id,
                metadata={"portal_user_id": user_id}
            )
            try:
                from services.lead_automation_service import record_client_event, evaluate_client_automation_rules, EVENT_PROVISIONING_COMPLETED
                await record_client_event(
                    client_id=client_id,
                    event_type=EVENT_PROVISIONING_COMPLETED,
                    source="provisioning.provision_client_portal_core",
                    metadata={"portal_user_id": user_id},
                )
                await evaluate_client_automation_rules(client_id, EVENT_PROVISIONING_COMPLETED)
            except Exception as flow_err:
                logger.warning("Provisioning automation event skipped client_id=%s: %s", client_id, flow_err)
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
                from services.onboarding_email_governance import milestone_set_payload

                set_fields["activation_email_sent_at"] = now_act
                set_fields.update(milestone_set_payload("activation_email_sent_at", now_act))
                set_fields.update(milestone_set_payload("activation_link_ready_at", now_act))
                logger.info(
                    "onboarding_activation_email_sent client_id=%s template=WELCOME_EMAIL source=provision_client_portal",
                    client_id,
                )
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

        Dual path (audit):
        - **Registry (primary):** ``materialize_requirements_for_property`` persists the full plan from
          ``build_requirement_plan_for_property`` (core cadence from ``iter_core_rules`` + catalog-driven
          keys + HMO / communal / selective-licensing expansion). ``requirement_generation_source`` =
          ``catalog_registry``.
        - **Mongo rules (supplemental):** Active ``requirement_rules`` documents are applied only for
          ``rule_type`` values whose lowercase slug is **not** already in the registry plan's
          ``requirement_type`` set for this property (avoids duplicate rows when both exist).
          Those rows use ``requirement_generation_source`` = ``requirement_rules``.
        - If ``requirement_rules`` is empty (typical), the DB-rule arm is a no-op and everything is
          registry-backed. Custom admin-defined rule types remain DB-only until added to the code registry.
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

        client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
        portfolio_label = portfolio_jurisdiction_label(property_doc, client_doc)
        scoring_jurisdiction = scoring_jurisdiction_for_property(property_doc, client_doc)
        
        mat = await materialize_requirements_for_property(
            client_id, property_id, reconcile_obsolete=True
        )
        planned_lower: Set[str] = {str(t).lower() for t in (mat.get("planned_types") or [])}

        db_rules = await db.requirement_rules.find(
            {"is_active": True},
            {"_id": 0}
        ).to_list(100)
        if db_rules:
            await self._apply_db_rules(
                db_rules,
                client_id,
                property_id,
                property_type,
                property_doc,
                client_doc,
                planned_registry_types=planned_lower,
            )
        
        await create_audit_log(
            action=AuditAction.REQUIREMENTS_GENERATED,
            client_id=client_id,
            resource_type="property",
            resource_id=property_id,
            metadata={
                "property_type": property_type,
                "is_hmo": is_hmo,
                "has_gas_supply": property_doc.get("has_gas_supply"),
                "building_age_years": property_doc.get("building_age_years"),
                "local_authority": (property_doc.get("local_authority") or ""),
                "portfolio_jurisdiction": portfolio_label,
                "scoring_jurisdiction": scoring_jurisdiction,
            }
        )
    
    async def _apply_db_rules(
        self,
        rules: List[Dict],
        client_id: str,
        property_id: str,
        property_type: str,
        property_doc: Dict[str, Any],
        client_doc: Optional[Dict[str, Any]],
        *,
        planned_registry_types: Optional[Set[str]] = None,
    ):
        """Apply database rules to generate requirements."""
        portfolio = portfolio_jurisdiction_label(property_doc, client_doc)

        for rule in rules:
            if not governed_requirement_rule_covers_property(
                rule, property_type, property_doc, client_doc
            ):
                continue

            rc = (rule.get("rule_type") or "").strip().lower()
            if planned_registry_types and rc in planned_registry_types:
                continue
            # Legacy DB rule slug ``occupation_contract`` must not duplicate catalog ``wales_occupation_contract``.
            if rc == "occupation_contract" and planned_registry_types and "wales_occupation_contract" in planned_registry_types:
                continue
            eng = resolve_engine_payload_from_code(rc) if rc else {}
            cls_override = (rule.get("compliance_requirement_class") or "").strip().upper() or None
            cls_eff = cls_override or eng.get("compliance_requirement_class")
            csv = rule.get("client_surface_visible")
            if csv is None:
                csv = eng.get("client_surface_visible")
            meta = None
            if rule.get("governed_version_id"):
                meta = {"governed_version_id": rule.get("governed_version_id")}
            tracked = None
            if cls_eff:
                tracked = cls_eff in ("DOCUMENT", "JOB")
            await self._create_requirement_if_not_exists(
                client_id,
                property_id,
                rule["rule_type"],
                rule["name"],
                rule["frequency_days"],
                warning_days=rule.get("warning_days", 30),
                jurisdiction_label=portfolio,
                requirement_code=rc,
                compliance_requirement_class=cls_eff,
                is_tracked=tracked,
                client_surface_visible=csv,
                registry_metadata=meta,
                governed_sync=bool(rule.get("governed")),
            )
    
    async def _create_requirement_if_not_exists(
        self,
        client_id: str,
        property_id: str,
        requirement_type: str,
        description: str,
        frequency_days: int,
        warning_days: int = 30,
        *,
        jurisdiction_label: Optional[str] = None,
        requirement_code: Optional[str] = None,
        compliance_requirement_class: Optional[str] = None,
        is_tracked: Optional[bool] = None,
        client_surface_visible: Optional[bool] = None,
        requires_document: Optional[bool] = None,
        requires_job: Optional[bool] = None,
        registry_metadata: Optional[Dict[str, Any]] = None,
        governed_sync: bool = False,
    ):
        """Create a requirement if it doesn't already exist (idempotent)."""
        db = database.get_db()
        
        existing = await db.requirements.find_one({
            "client_id": client_id,
            "property_id": property_id,
            "requirement_type": requirement_type
        })
        
        cls_eff = (compliance_requirement_class or "").strip().upper() or None
        rd = requires_document
        rj = requires_job
        if rd is None and cls_eff == "DOCUMENT":
            rd = True
        if rj is None and cls_eff == "JOB":
            rj = True
        csv = client_surface_visible
        if csv is None and cls_eff:
            csv = cls_eff != "SYSTEM"
        if is_tracked is None and cls_eff:
            is_tracked = cls_eff in ("DOCUMENT", "JOB")

        if existing:
            patch: Dict[str, Any] = {}
            meta_in = registry_metadata if isinstance(registry_metadata, dict) else {}
            prev_meta = existing.get("registry_metadata") or {}
            governed_reconciled = bool(prev_meta.get("governed_reconciled"))

            if governed_sync and governed_reconciled:
                patch["applicability"] = "REQUIRED"
                patch["status"] = RequirementStatus.PENDING.value
                patch["not_required_reason"] = None
                patch["is_tracked"] = is_tracked if is_tracked is not None else cls_eff in ("DOCUMENT", "JOB")
                patch["client_surface_visible"] = csv if csv is not None else existing.get("client_surface_visible")
                patch["requires_document"] = rd if rd is not None else existing.get("requires_document")
                patch["requires_job"] = rj if rj is not None else existing.get("requires_job")
                patch["description"] = description
                patch["frequency_days"] = frequency_days
                patch["warning_days"] = warning_days
                if compliance_requirement_class:
                    patch["compliance_requirement_class"] = compliance_requirement_class
                merged = {**prev_meta, **meta_in}
                merged.pop("governed_reconciled", None)
                merged.pop("governed_reconciled_at", None)
                patch["registry_metadata"] = merged
            elif governed_sync:
                if jurisdiction_label:
                    patch["jurisdiction"] = jurisdiction_label
                rc = (requirement_code or requirement_type or "").strip().lower()
                if rc:
                    patch["requirement_code"] = rc
                if compliance_requirement_class:
                    patch["compliance_requirement_class"] = compliance_requirement_class
                if is_tracked is not None:
                    patch["is_tracked"] = is_tracked
                if csv is not None:
                    patch["client_surface_visible"] = csv
                if rd is not None:
                    patch["requires_document"] = rd
                if rj is not None:
                    patch["requires_job"] = rj
                patch["description"] = description
                patch["frequency_days"] = frequency_days
                patch["warning_days"] = warning_days
                patch["registry_metadata"] = {**prev_meta, **meta_in}
            else:
                if jurisdiction_label and not existing.get("jurisdiction"):
                    patch["jurisdiction"] = jurisdiction_label
                rc = (requirement_code or requirement_type or "").strip().lower()
                if rc and not existing.get("requirement_code"):
                    patch["requirement_code"] = rc
                if compliance_requirement_class and not existing.get("compliance_requirement_class"):
                    patch["compliance_requirement_class"] = compliance_requirement_class
                if is_tracked is not None and existing.get("is_tracked") is None:
                    patch["is_tracked"] = is_tracked
                if existing.get("client_surface_visible") is None and csv is not None:
                    patch["client_surface_visible"] = csv
                if existing.get("requires_document") is None and rd is not None:
                    patch["requires_document"] = rd
                if existing.get("requires_job") is None and rj is not None:
                    patch["requires_job"] = rj
                if meta_in:
                    merged = {**prev_meta, **meta_in}
                    patch["registry_metadata"] = merged
            if not existing.get("requirement_generation_source"):
                patch["requirement_generation_source"] = REQUIREMENT_GENERATION_SOURCE_DB_RULE
            if patch:
                patch["action_type"] = infer_action_type({**existing, **patch})
                patch["updated_at"] = datetime.now(timezone.utc).isoformat()
                await db.requirements.update_one(
                    {"requirement_id": existing["requirement_id"]},
                    {"$set": patch},
                )
            return
        
        rc_final = (requirement_code or requirement_type or "").strip().lower()
        requirement = Requirement(
            client_id=client_id,
            property_id=property_id,
            requirement_type=requirement_type,
            requirement_code=rc_final or None,
            jurisdiction=jurisdiction_label,
            description=description,
            frequency_days=frequency_days,
            due_date=datetime.now(timezone.utc) + timedelta(days=warning_days),
            status=RequirementStatus.PENDING,
            compliance_requirement_class=compliance_requirement_class,
            is_tracked=is_tracked if is_tracked is not None else True,
            client_surface_visible=csv if csv is not None else True,
            requires_document=rd,
            requires_job=rj,
            requirement_generation_source=REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            registry_metadata=registry_metadata,
        )
        
        doc = requirement.model_dump()
        for key in ["due_date", "created_at", "updated_at"]:
            if doc.get(key):
                doc[key] = doc[key].isoformat()
        doc["date_source"] = "SYSTEM_ESTIMATED"
        doc["evidence_state"] = "MISSING"
        doc["confidence_state"] = "ESTIMATED"
        if registry_metadata:
            doc["registry_metadata"] = registry_metadata

        doc["action_type"] = infer_action_type(doc)

        await db.requirements.insert_one(doc)
    
    async def _update_property_compliance(self, property_id: str):
        """Compute deterministic compliance status based on requirements."""
        db = database.get_db()
        
        requirements = await db.requirements.find(
            {"property_id": property_id},
            {"_id": 0}
        ).to_list(100)
        
        # Deterministic compliance logic: OVERDUE → RED; EXPIRING_SOON or PENDING (missing evidence) → AMBER; else GREEN
        red_count = sum(1 for r in requirements if r["status"] == RequirementStatus.OVERDUE.value)
        amber_count = sum(1 for r in requirements if r["status"] == RequirementStatus.EXPIRING_SOON.value)
        pending_count = sum(1 for r in requirements if r["status"] == RequirementStatus.PENDING.value)

        if red_count > 0:
            status = ComplianceStatus.RED
        elif amber_count > 0 or pending_count > 0:
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
                "subject": "Welcome to Compliance Vault Pro — set your password",
                "customer_reference": crn,
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
            try:
                from services.analytics_service import log_event
                await log_event("activation_email_sent", {"client_id": client_id})
            except Exception:
                pass
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
            try:
                from services.analytics_service import log_event
                await log_event("email_failed", {"client_id": client_id, "error_code": "NOT_CONFIGURED", "metadata": {"template_key": "WELCOME_EMAIL", "error": err_msg}})
            except Exception:
                pass
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
        try:
            from services.analytics_service import log_event
            await log_event("email_failed", {"client_id": client_id, "error_code": "FAILED", "metadata": {"template_key": "WELCOME_EMAIL", "error": err}})
        except Exception:
            pass
        logger.warning("ACTIVATION_EMAIL_FAILED client_id=%s error=%s provider_response_code=%s", client_id, err, getattr(result, "status_code", None))
        return False, "FAILED", err

    async def send_activation_reminder_email(
        self,
        client_id: str,
        user_id: str,
        email: str,
        name: str,
        *,
        idempotency_key: str,
    ) -> tuple[bool, str, Optional[str]]:
        """
        Second-chance activation email (reminder). Generates a new token; same mechanics as welcome/activation.
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
            send_count=1,
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
            logger.error("Activation reminder not sent: %s", e)
            return False, "FAILED", str(e)[:500]
        setup_link = f"{base_url.rstrip('/')}/set-password?token={raw_token}"

        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "customer_reference": 1})
        crn = (client or {}).get("customer_reference") or ""
        support_email = os.getenv("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk") or "info@pleerityenterprise.co.uk"

        from services.notification_orchestrator import notification_orchestrator

        result = await notification_orchestrator.send(
            template_key="ACTIVATION_REMINDER",
            client_id=client_id,
            context={
                "setup_link": setup_link,
                "client_name": name,
                "customer_reference": crn,
                "support_email": support_email,
                "subject": "Complete your setup — Compliance Vault Pro reminder",
            },
            idempotency_key=idempotency_key,
            event_type="activation_reminder",
        )
        if result.outcome in ("sent", "duplicate_ignored"):
            return True, "SENT", None
        if result.outcome == "blocked" and (result.block_reason or "").strip() == "BLOCKED_PROVIDER_NOT_CONFIGURED":
            err_msg = (result.error_message or result.block_reason or "POSTMARK_SERVER_TOKEN not set")[:500]
            return False, "NOT_CONFIGURED", err_msg
        err = (result.error_message or result.block_reason or result.outcome or "unknown")[:500]
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
        await persist_operational_client_lifecycle_if_needed(db, client_id)

        await create_audit_log(
            action=AuditAction.PROVISIONING_FAILED,
            client_id=client_id,
            metadata={"reason": reason}
        )

provisioning_service = ProvisioningService()
