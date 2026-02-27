from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None
    
    async def connect(self):
        try:
            mongo_url = os.environ['MONGO_URL']
            self.client = AsyncIOMotorClient(mongo_url)
            self.db = self.client[os.environ['DB_NAME']]
            # Verify connection
            await self.db.command("ping")
            logger.info(f"Connected to MongoDB: {os.environ['DB_NAME']}")
            
            # Create indexes for efficient search and lookups
            await self._create_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    def get_db(self):
        return self.db
    
    async def _create_indexes(self):
        """Create MongoDB indexes for efficient queries."""
        try:
            # Client indexes - CRN (customer_reference) is critical for search
            # Use sparse=True to allow multiple null values
            try:
                await self.db.clients.create_index("customer_reference", unique=True, sparse=True)
            except Exception:
                pass  # Index may already exist with different options
            
            try:
                await self.db.clients.create_index("email", unique=True)
            except Exception:
                pass
            
            await self.db.clients.create_index("client_id", unique=True)
            await self.db.clients.create_index("full_name")  # For name search
            await self.db.clients.create_index("billing_plan")  # Plan filter (admin clients list)
            await self.db.clients.create_index("subscription_status")  # Status filter (admin clients list)

            # Property indexes - for postcode search
            await self.db.properties.create_index("postcode")
            await self.db.properties.create_index("client_id")
            await self.db.properties.create_index("property_id", unique=True)
            await self.db.properties.create_index("compliance_status")
            
            # Documents - pending verification admin list (status + uploaded_at; client_id filter)
            await self.db.documents.create_index([("status", 1), ("uploaded_at", 1)])
            await self.db.documents.create_index([("client_id", 1), ("status", 1), ("uploaded_at", 1)])
            
            # Portal user indexes
            try:
                await self.db.portal_users.create_index("auth_email", unique=True)
            except Exception:
                pass
            
            await self.db.portal_users.create_index("client_id")
            await self.db.portal_users.create_index("portal_user_id", unique=True)
            
            # Audit log indexes - for timeline queries and email-delivery
            await self.db.audit_logs.create_index([("client_id", 1), ("timestamp", -1)])
            await self.db.audit_logs.create_index([("action", 1), ("timestamp", -1)])
            await self.db.audit_logs.create_index("timestamp")
            await self.db.audit_logs.create_index("action")
            
            # Message log indexes - for email-delivery admin view and orchestrator
            await self.db.message_logs.create_index([("created_at", -1)])
            await self.db.message_logs.create_index([("status", 1), ("created_at", -1)])
            await self.db.message_logs.create_index([("channel", 1), ("created_at", -1)])
            await self.db.message_logs.create_index([("template_alias", 1), ("created_at", -1)])
            await self.db.message_logs.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.message_logs.create_index([("template_key", 1), ("created_at", -1)])
            await self.db.message_logs.create_index("provider_message_id", sparse=True)
            try:
                await self.db.message_logs.create_index("idempotency_key", unique=True, sparse=True)
            except Exception:
                pass
            # Notification templates (template_key -> gating + email alias)
            await self.db.notification_templates.create_index("template_key", unique=True)
            # Notification retry queue (outbox pattern)
            await self.db.notification_retry_queue.create_index([("status", 1), ("next_run_at", 1)])
            await self.db.notification_retry_queue.create_index("message_id")
            await self._seed_notification_templates()
            # Compliance score history indexes - for trend queries
            await self.db.compliance_score_history.create_index([("client_id", 1), ("date_key", -1)])
            try:
                await self.db.compliance_score_history.create_index(
                    [("client_id", 1), ("date_key", 1)], 
                    unique=True
                )
            except Exception:
                pass  # Index may already exist
            # Property-level score history (event-driven)
            await self.db.property_compliance_score_history.create_index([("property_id", 1), ("created_at", -1)])
            await self.db.property_compliance_score_history.create_index([("client_id", 1), ("created_at", -1)])
            # Async compliance recalc queue (Option B)
            try:
                await self.db.compliance_recalc_queue.create_index(
                    [("property_id", 1), ("correlation_id", 1)],
                    unique=True
                )
            except Exception:
                pass
            await self.db.compliance_recalc_queue.create_index([("status", 1), ("next_run_at", 1)])
            await self.db.compliance_recalc_queue.create_index([("property_id", 1), ("status", 1)])
            # Compliance recalc SLA alerts (dedupe by property + alert type)
            try:
                await self.db.compliance_sla_alerts.create_index(
                    [("property_id", 1), ("alert_type", 1)],
                    unique=True
                )
            except Exception:
                pass
            await self.db.compliance_sla_alerts.create_index([("active", 1), ("last_detected_at", -1)])
            await self.db.compliance_sla_alerts.create_index([("severity", 1)])

            # Submissions: contact, talent, partnership (list/dedupe/audit)
            await self.db.contact_submissions.create_index("submission_id", unique=True)
            await self.db.contact_submissions.create_index([("email_normalized", 1), ("created_at", -1)])
            await self.db.contact_submissions.create_index([("dedupe_key", 1), ("created_at", -1)])
            await self.db.contact_submissions.create_index("created_at")
            await self.db.contact_submissions.create_index("status")
            await self.db.talent_pool.create_index("submission_id", unique=True)
            await self.db.talent_pool.create_index([("email_normalized", 1), ("created_at", -1)])
            await self.db.talent_pool.create_index([("dedupe_key", 1), ("created_at", -1)])
            await self.db.talent_pool.create_index("created_at")
            await self.db.talent_pool.create_index("status")
            await self.db.partnership_enquiries.create_index("enquiry_id", unique=True)
            await self.db.partnership_enquiries.create_index([("email_normalized", 1), ("created_at", -1)])
            await self.db.partnership_enquiries.create_index([("dedupe_key", 1), ("created_at", -1)])
            await self.db.partnership_enquiries.create_index("created_at")
            await self.db.partnership_enquiries.create_index("status")
            # Risk check leads (conversion demo; no client/provisioning)
            await self.db.risk_leads.create_index("lead_id", unique=True)
            await self.db.risk_leads.create_index("created_at")
            await self.db.risk_leads.create_index("email")
            await self.db.risk_leads.create_index("risk_band")
            await self.db.risk_leads.create_index("status")
            # Tenant portal: messages and certificate requests (landlord notification flow)
            await self.db.tenant_messages.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.tenant_messages.create_index("message_id", unique=True)
            await self.db.tenant_requests.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.tenant_requests.create_index("request_id", unique=True)
            await self.db.tenant_requests.create_index([("client_id", 1), ("status", 1)])

            # OTP codes - one active per (phone_hash, purpose); no raw phone stored
            try:
                await self.db.otp_codes.create_index(
                    [("phone_hash", 1), ("purpose", 1)],
                    unique=True,
                )
            except Exception:
                pass
            await self.db.otp_codes.create_index("expires_at")
            # Step-up tokens - one-time use; validate by token_hash + user_id
            await self.db.step_up_tokens.create_index("token_hash")
            await self.db.step_up_tokens.create_index([("user_id", 1), ("expires_at", 1)])

            # Intake uploads - for migration and list by session
            await self.db.intake_uploads.create_index("intake_session_id")
            await self.db.intake_uploads.create_index([("intake_session_id", 1), ("status", 1)])
            # Stripe webhook idempotency - duplicate event_id must not process twice
            try:
                await self.db.stripe_events.create_index("event_id", unique=True)
            except Exception:
                pass
            # Normalized payments (Revenue Analytics) - idempotency and date queries
            if hasattr(self.db, "payments"):
                try:
                    await self.db.payments.create_index("stripe_event_id", unique=True, sparse=True)
                except Exception:
                    pass
                await self.db.payments.create_index("created_at")
                await self.db.payments.create_index([("client_id", 1), ("created_at", -1)])
                await self.db.payments.create_index("stripe_charge_id", sparse=True)
                await self.db.payments.create_index("stripe_invoice_id", sparse=True)
            # MRR snapshots for NRR (Executive Overview)
            if hasattr(self.db, "mrr_snapshots"):
                try:
                    await self.db.mrr_snapshots.create_index("period", unique=True)
                except Exception:
                    pass
            # Provisioning jobs - idempotency by checkout_session_id
            await self.db.provisioning_jobs.create_index("job_id", unique=True)
            try:
                await self.db.provisioning_jobs.create_index("checkout_session_id", unique=True)
            except Exception:
                pass
            await self.db.provisioning_jobs.create_index("client_id")
            await self.db.provisioning_jobs.create_index("status")
            # Analytics events - conversion funnel and operational metrics (passive logging)
            await self.db.analytics_events.create_index([("event", 1), ("ts", -1)])
            await self.db.analytics_events.create_index([("client_id", 1), ("ts", -1)])
            await self.db.analytics_events.create_index([("lead_id", 1), ("ts", -1)])
            await self.db.analytics_events.create_index("ts")
            try:
                await self.db.analytics_events.create_index("idempotency_key", unique=True, sparse=True)
            except Exception:
                pass
            # Requirements catalog (data-driven compliance definitions)
            await self.db.requirements_catalog.create_index("code", unique=True)
            await self.db.requirements_catalog.create_index("category")
            await self.db.requirements_catalog.create_index("criticality")
            # Requirements (instance state) - ensure efficient lookups
            await self.db.requirements.create_index([("client_id", 1), ("property_id", 1)])
            await self.db.requirements.create_index([("property_id", 1), ("requirement_type", 1)])
            # Assistant chat (Compliance Vault Assistant)
            await self.db.assistant_conversations.create_index([("client_id", 1), ("last_activity_at", -1)])
            await self.db.assistant_conversations.create_index("conversation_id", unique=True)
            await self.db.assistant_messages.create_index([("conversation_id", 1), ("created_at", 1)])
            await self.db.assistant_messages.create_index([("client_id", 1), ("created_at", -1)])
            await self._seed_requirements_catalog()
            logger.info("MongoDB indexes created/verified")
        except Exception as e:
            # Indexes may already exist, log but don't fail
            logger.warning(f"Index creation note: {e}")

    async def _seed_requirements_catalog(self):
        """Seed requirements_catalog for data-driven compliance (idempotent by code)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        items = [
            {"code": "gas_safety", "title": "Gas Safety (CP12)", "description": "Annual gas safety inspection", "category": "SAFETY", "criticality": "HIGH", "weight": 18, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": {"all": [{"field": "has_gas_supply", "op": "==", "value": True}]}, "default_actions": [], "help_text": "Required for properties with gas.", "updated_at": now},
            {"code": "eicr", "title": "EICR", "description": "Electrical Installation Condition Report", "category": "ELECTRICAL", "criticality": "HIGH", "weight": 16, "expiry_type": "EXPIRING", "validity_days": 1825, "expiring_windows_days": 60, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Typically every 5 years.", "updated_at": now},
            {"code": "epc", "title": "EPC", "description": "Energy Performance Certificate", "category": "ENERGY", "criticality": "HIGH", "weight": 8, "expiry_type": "EXPIRING", "validity_days": 3650, "expiring_windows_days": 90, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Minimum E for rental.", "updated_at": now},
            {"code": "smoke_alarms", "title": "Smoke Alarms", "description": "Smoke alarms required", "category": "FIRE", "criticality": "HIGH", "weight": 8, "expiry_type": "NON_EXPIRING", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Smoke alarms on each storey.", "updated_at": now},
            {"code": "co_alarms", "title": "CO Alarms", "description": "Carbon monoxide alarms where solid fuel", "category": "FIRE", "criticality": "HIGH", "weight": 6, "expiry_type": "NON_EXPIRING", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Where applicable.", "updated_at": now},
            {"code": "deposit_pi", "title": "Deposit Protection", "description": "Deposit in approved scheme", "category": "TENANCY", "criticality": "HIGH", "weight": 10, "expiry_type": "EVENT_BASED", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Prescribed information to tenant.", "updated_at": now},
            {"code": "right_to_rent", "title": "Right to Rent", "description": "Right to rent checks", "category": "TENANCY", "criticality": "HIGH", "weight": 7, "expiry_type": "EVENT_BASED", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Check and retain copies.", "updated_at": now},
            {"code": "how_to_rent", "title": "How to Rent", "description": "How to Rent guide to tenant", "category": "TENANCY", "criticality": "MED", "weight": 5, "expiry_type": "EVENT_BASED", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Latest version.", "updated_at": now},
            {"code": "tenancy_agreement", "title": "Tenancy Agreement", "description": "Written tenancy agreement", "category": "TENANCY", "criticality": "MED", "weight": 6, "expiry_type": "EVENT_BASED", "validity_days": None, "expiring_windows_days": None, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Signed agreement.", "updated_at": now},
            {"code": "hmo_license", "title": "HMO Licence", "description": "HMO licence where required", "category": "REGULATORY", "criticality": "HIGH", "weight": 18, "expiry_type": "EXPIRING", "validity_days": 1825, "expiring_windows_days": 90, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": {"any": [{"field": "is_hmo", "op": "==", "value": True}, {"field": "licence_required", "op": "==", "value": "YES"}]}, "default_actions": [], "help_text": "Mandatory for licensable HMO.", "updated_at": now},
            {"code": "fire_risk_assessment", "title": "Fire Risk Assessment", "description": "Fire risk assessment (HMO)", "category": "FIRE", "criticality": "HIGH", "weight": 6, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": {"field": "is_hmo", "op": "==", "value": True}, "default_actions": [], "help_text": "Required for HMO.", "updated_at": now},
            {"code": "legionella", "title": "Legionella Risk Assessment", "description": "Legionella risk assessment", "category": "HEALTH", "criticality": "LOW", "weight": 4, "expiry_type": "EXPIRING", "validity_days": 730, "expiring_windows_days": 60, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Water system risk.", "updated_at": now},
            {"code": "portable_appliance_test", "title": "Portable Appliance Testing (PAT)", "description": "Portable Appliance Testing (PAT)", "category": "ELECTRICAL", "criticality": "MED", "weight": 5, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "PAT certificate where applicable.", "updated_at": now},
            {"code": "fire_alarm", "title": "Fire Alarm Inspection", "description": "Fire Alarm Inspection", "category": "FIRE", "criticality": "HIGH", "weight": 8, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Annual fire alarm inspection.", "updated_at": now},
        ]
        for item in items:
            await self.db.requirements_catalog.update_one(
                {"code": item["code"]},
                {"$set": item},
                upsert=True,
            )
        logger.info("Requirements catalog seeded/updated")

    async def _seed_notification_templates(self):
        """Seed notification_templates for orchestrator (idempotent upsert by template_key)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        templates = [
            {
                "template_key": "WELCOME_EMAIL",
                "channel": "EMAIL",
                "email_template_alias": "password-setup",
                "sms_body": None,
                "requires_provisioned": True,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "PASSWORD_RESET",
                "channel": "EMAIL",
                "email_template_alias": "password-reset",
                "sms_body": None,
                "requires_provisioned": True,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "COMPLIANCE_EXPIRY_REMINDER",
                "channel": "EMAIL",
                "email_template_alias": "reminder",
                "sms_body": None,
                "requires_provisioned": True,
                "requires_active_subscription": True,
                "requires_entitlement_enabled": True,
                "plan_required_feature_key": None,
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "SUBSCRIPTION_CONFIRMED",
                "channel": "EMAIL",
                "email_template_alias": "payment-receipt",
                "sms_body": None,
                "requires_provisioned": False,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "PAYMENT_FAILED",
                "channel": "EMAIL",
                "email_template_alias": "payment-failed",
                "sms_body": None,
                "requires_provisioned": False,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "is_active": True,
                "updated_at": now,
            },
            {"template_key": "SUBSCRIPTION_CANCELED", "channel": "EMAIL", "email_template_alias": "subscription-canceled", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "MONTHLY_DIGEST", "channel": "EMAIL", "email_template_alias": "monthly-digest", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "COMPLIANCE_EXPIRY_REMINDER_SMS", "channel": "SMS", "email_template_alias": None, "sms_body": "Pleerity: {{count}} compliance item(s) need attention. View: {{portal_link}}", "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": "sms_reminders", "is_active": True, "updated_at": now},
            {"template_key": "PENDING_VERIFICATION_DIGEST", "channel": "EMAIL", "email_template_alias": "pending-verification-digest", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "COMPLIANCE_ALERT", "channel": "EMAIL", "email_template_alias": "compliance-alert", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "RENEWAL_REMINDER", "channel": "EMAIL", "email_template_alias": "renewal-reminder", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "SCHEDULED_REPORT", "channel": "EMAIL", "email_template_alias": "scheduled-report", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "ADMIN_MANUAL", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "ADMIN_MANUAL_SMS", "channel": "SMS", "email_template_alias": None, "sms_body": "{{body}}", "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "ADMIN_INVITE", "channel": "EMAIL", "email_template_alias": "admin-invite", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "ORDER_DELIVERED", "channel": "EMAIL", "email_template_alias": "order-delivered", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "ORDER_NOTIFICATION", "channel": "EMAIL", "email_template_alias": "compliance-alert", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "AI_EXTRACTION_APPLIED", "channel": "EMAIL", "email_template_alias": "ai-extraction-applied", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "TENANT_INVITE", "channel": "EMAIL", "email_template_alias": "tenant-invite", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": "tenant_portal", "is_active": True, "updated_at": now},
            {"template_key": "CUSTOM_NOTIFICATION", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "SUPPORT_TICKET_CONFIRMATION", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "SUPPORT_INTERNAL_NOTIFICATION", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "LEAD_MANUAL_MESSAGE", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "LEAD_FOLLOWUP", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "LEAD_SLA_BREACH_ADMIN", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "LEAD_HIGH_INTENT_ADMIN", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "COMPLIANCE_SLA_ALERT", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "CLEARFORM_WELCOME", "channel": "EMAIL", "email_template_alias": "clearform-welcome", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "PARTNERSHIP_ACK", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "ENABLEMENT_DELIVERY", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "OTP_CODE_SMS", "channel": "SMS", "email_template_alias": None, "sms_body": "{{body}}", "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "OPS_ALERT_NOTIFICATION_SPIKE", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "PROVISIONING_FAILED_ADMIN", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "STRIPE_WEBHOOK_FAILURE_ADMIN", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
        ]
        for t in templates:
            await self.db.notification_templates.update_one(
                {"template_key": t["template_key"]},
                {"$set": t},
                upsert=True,
            )
        logger.info("Notification templates seeded/updated")

# Global database instance
database = Database()

@asynccontextmanager
async def get_db_context():
    """Context manager for standalone scripts to access the database.
    
    Usage in scripts:
        async with get_db_context() as db:
            # db is now connected and ready to use
            await db.clients.find_one(...)
    """
    client = None
    try:
        mongo_url = os.environ['MONGO_URL']
        db_name = os.environ['DB_NAME']
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        # Verify connection
        await db.command("ping")
        logger.info(f"Script connected to MongoDB: {db_name}")
        yield db
    finally:
        if client:
            client.close()
            logger.info("Script MongoDB connection closed")
