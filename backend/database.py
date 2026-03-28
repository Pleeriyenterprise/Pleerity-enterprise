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

            # Evidence pack jobs (client exports)
            try:
                await self.db.compliance_evidence_pack_jobs.create_index(
                    [("client_id", 1), ("created_at", -1)]
                )
            except Exception:
                pass
            # Product analytics (first-party funnel events)
            try:
                await self.db.product_analytics_events.create_index(
                    [("client_id", 1), ("created_at", -1)]
                )
                await self.db.product_analytics_events.create_index(
                    [("event", 1), ("created_at", -1)]
                )
            except Exception:
                pass
            # Client read API keys (integrations; secret stored as hash only)
            try:
                await self.db.client_read_api_keys.create_index("token_hash", unique=True)
                await self.db.client_read_api_keys.create_index(
                    [("client_id", 1), ("revoked_at", 1)]
                )
            except Exception:
                pass
            
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
            # Reminder item-level state + evaluation audit (truth-checked suppression/cooldown)
            try:
                await self.db.reminder_item_state.create_index(
                    [("client_id", 1), ("property_id", 1), ("requirement_code", 1), ("target_ref", 1), ("reminder_type", 1)],
                    unique=True,
                )
            except Exception:
                pass
            await self.db.reminder_item_state.create_index([("client_id", 1), ("reminder_type", 1), ("updated_at", -1)])
            await self.db.reminder_item_state.create_index([("suppression_reason", 1), ("updated_at", -1)])
            await self.db.reminder_evaluation_log.create_index([("created_at", -1)])
            await self.db.reminder_evaluation_log.create_index([("reminder_type", 1), ("decision", 1), ("created_at", -1)])
            await self.db.reminder_evaluation_log.create_index([("client_id", 1), ("property_id", 1), ("created_at", -1)])
            # Notification templates (template_key -> gating + email alias)
            await self.db.notification_templates.create_index("template_key", unique=True)
            # Notification retry queue (outbox pattern)
            await self.db.notification_retry_queue.create_index([("status", 1), ("next_run_at", 1)])
            await self.db.notification_retry_queue.create_index("message_id")
            # Onboarding email sequence queue (per-client, send_at)
            await self.db.onboarding_email_queue.create_index([("status", 1), ("send_at", 1)])
            await self.db.onboarding_email_queue.create_index([("client_id", 1), ("event_id", 1)], unique=True)
            await self._seed_notification_templates()
            await self._seed_communication_collections()
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
            # Property daily score snapshots (score trend 90-day chart per property)
            await self.db.property_score_daily.create_index([("client_id", 1), ("property_id", 1), ("date", 1)], unique=True)
            await self.db.property_score_daily.create_index([("client_id", 1), ("date", -1)])
            await self.db.property_score_daily.create_index([("property_id", 1), ("date", -1)])
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
            # Risk signal regeneration queue (debounced; one PENDING row per property)
            try:
                await self.db.risk_signal_regen_queue.create_index([("status", 1), ("next_run_at", 1)])
            except Exception:
                pass
            try:
                await self.db.risk_signal_regen_queue.create_index(
                    [("property_id", 1)],
                    unique=True,
                    partialFilterExpression={"status": "PENDING"},
                    name="risk_regen_one_pending_per_property",
                )
            except Exception:
                pass
            try:
                await self.db.operational_issue_suggestions.create_index(
                    [("client_id", 1), ("property_id", 1), ("status", 1)]
                )
                await self.db.operational_issue_suggestions.create_index(
                    [("property_id", 1), ("operational_root_key", 1), ("status", 1)]
                )
            except Exception:
                pass
            try:
                await self.db.operational_automation_suppress_audit.create_index("created_at")
            except Exception:
                pass
            try:
                await self.db.maintenance_issues.create_index(
                    [("property_id", 1), ("operational_root_key", 1), ("status", 1)],
                    sparse=True,
                )
            except Exception:
                pass
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
            # Score events - audit-grade log for score trend and "What Changed" (client dashboard)
            await self.db.score_events.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.score_events.create_index([("client_id", 1), ("event_type", 1), ("created_at", -1)])
            # Action -> Outcome activity log (client timeline + admin visibility)
            await self.db.compliance_activity_log.create_index([("client_id", 1), ("property_id", 1), ("created_at", -1)])
            await self.db.compliance_activity_log.create_index([("client_id", 1), ("created_at", -1)])
            try:
                await self.db.compliance_activity_log.create_index("dedupe_key", unique=True)
            except Exception:
                pass
            # Score ledger - enterprise statement-of-account for score changes (before/after, drivers, trigger)
            await self.db.score_ledger_events.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.score_ledger_events.create_index([("client_id", 1), ("property_id", 1), ("created_at", -1)])
            await self.db.score_ledger_events.create_index([("client_id", 1), ("trigger_type", 1), ("created_at", -1)])
            # Job runs - observability: every automation execution (for SLA watchdog and admin dashboard)
            await self.db.job_runs.create_index([("job_name", 1), ("created_at", -1)])
            await self.db.job_runs.create_index([("job_name", 1), ("started_at", -1)])
            await self.db.job_runs.create_index([("status", 1), ("created_at", -1)])
            await self.db.job_runs.create_index("created_at")
            # Incidents - system-wide P0/P1/P2 with ack/resolve workflow
            await self.db.incidents.create_index([("status", 1), ("created_at", -1)])
            await self.db.incidents.create_index([("severity", 1), ("status", 1)])
            await self.db.incidents.create_index("created_at")
            # Security monitoring collections (events, incidents, auto-response locks/blocks)
            await self.db.security_incidents.create_index([("status", 1), ("timestamp", -1)])
            await self.db.security_incidents.create_index([("severity", 1), ("status", 1)])
            await self.db.security_incidents.create_index([("type", 1), ("timestamp", -1)])
            await self.db.security_incidents.create_index("incident_key", unique=True)
            await self.db.security_events.create_index("event_id", unique=True)
            await self.db.security_events.create_index([("event_type", 1), ("timestamp", -1)])
            await self.db.security_events.create_index([("ip", 1), ("timestamp", -1)])
            await self.db.security_events.create_index([("user_id", 1), ("timestamp", -1)])
            await self.db.security_locks.create_index([("lock_type", 1), ("principal", 1)], unique=True)
            await self.db.security_locks.create_index("expires_at")
            await self.db.security_blocks.create_index("ip", unique=True)
            await self.db.security_blocks.create_index("expires_at")
            # Admin login MFA challenges (email OTP fallback for staff login hardening)
            await self.db.admin_login_challenges.create_index("challenge_id", unique=True)
            await self.db.admin_login_challenges.create_index([("portal_user_id", 1), ("created_at", -1)])
            await self.db.admin_login_challenges.create_index("expires_at")
            # Operations & Compliance: module feature flags per client
            await self.db.client_feature_flags.create_index([("client_id", 1), ("flag_key", 1)], unique=True)
            await self.db.client_feature_flags.create_index("client_id")
            # CVP subscription checkout PDF receipts (portal billing)
            try:
                await self.db.stripe_checkout_invoices.create_index([("client_id", 1), ("created_at", -1)])
                await self.db.stripe_checkout_invoices.create_index([("client_id", 1), ("invoice_number", 1)])
            except Exception:
                pass
            # Provisioning status per property/module (compliance, maintenance)
            await self.db.provisioning_status.create_index([("client_id", 1), ("property_id", 1), ("module_name", 1)], unique=True)
            await self.db.provisioning_status.create_index([("client_id", 1), ("module_name", 1)])
            # Contractors (Ops: client-scoped or system-wide)
            await self.db.contractors.create_index("contractor_id", unique=True)
            await self.db.contractors.create_index("client_id")
            await self.db.contractors.create_index([("vetted", 1), ("client_id", 1)])
            await self.db.contractors.create_index("source_type")
            await self.db.contractors.create_index("status")
            await self.db.contractors.create_index("portal_access_status")
            await self.db.contractors.create_index([("portal_access_status", 1), ("updated_at", -1)])
            try:
                await self.db.contractors.create_index("email_normalized", sparse=True)
            except Exception:
                pass
            # Contractor ratings (landlord/client rates contractor after job)
            await self.db.contractor_ratings.create_index("rating_id", unique=True)
            await self.db.contractor_ratings.create_index("contractor_id")
            await self.db.contractor_ratings.create_index([("contractor_id", 1), ("created_at", -1)])
            await self.db.contractor_ratings.create_index("work_order_id", sparse=True)
            # Contractor performance (updated on work order completion)
            await self.db.contractor_performance.create_index([("contractor_id", 1), ("client_id", 1)], unique=True)
            await self.db.contractor_performance.create_index("contractor_id")
            # Work orders (maintenance workflows: tenant/client report → assign contractor → SLA)
            await self.db.work_orders.create_index("work_order_id", unique=True)
            await self.db.work_orders.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.work_orders.create_index([("client_id", 1), ("status", 1)])
            await self.db.work_orders.create_index([("property_id", 1), ("created_at", -1)])
            await self.db.work_orders.create_index("contractor_id", sparse=True)
            try:
                await self.db.work_orders.create_index("work_order_kind", sparse=True)
            except Exception:
                pass
            try:
                await self.db.work_orders.create_index(
                    [("client_id", 1), ("work_order_kind", 1), ("requirement_code", 1)],
                    sparse=True,
                )
            except Exception:
                pass
            await self.db.work_orders.create_index("issue_id", sparse=True)
            await self.db.work_orders.create_index("asset_id", sparse=True)
            try:
                await self.db.work_orders.create_index(
                    [("property_id", 1), ("operational_root_key", 1), ("status", 1)],
                    sparse=True,
                )
            except Exception:
                pass
            try:
                await self.db.work_orders.create_index(
                    [
                        ("assignment_routing_state", 1),
                        ("client_confirmation_deadline_at", 1),
                    ],
                    sparse=True,
                )
            except Exception:
                pass
            # Contractor assignments (history when work order is assigned; current assignment remains on work_order)
            await self.db.contractor_assignments.create_index([("work_order_id", 1), ("assigned_at", -1)])
            await self.db.contractor_assignments.create_index("work_order_id")
            await self.db.contractor_assignments.create_index("contractor_id")
            # Contractor job access tokens (secure link per work order assignment; no login required)
            await self.db.contractor_job_tokens.create_index("token_hash", unique=True)
            await self.db.contractor_job_tokens.create_index([("work_order_id", 1), ("contractor_id", 1)])
            await self.db.contractor_job_tokens.create_index("expires_at")
            await self.db.contractor_job_tokens.create_index("revoked_at")
            # Maintenance issues (issue → triage → work order flow)
            await self.db.maintenance_issues.create_index("issue_id", unique=True)
            await self.db.maintenance_issues.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.maintenance_issues.create_index([("client_id", 1), ("status", 1)])
            await self.db.maintenance_issues.create_index([("property_id", 1), ("created_at", -1)])
            # Property assets + maintenance events (predictive maintenance)
            await self.db.property_assets.create_index([("property_id", 1), ("asset_id", 1)], unique=True)
            await self.db.property_assets.create_index("property_id")
            await self.db.property_assets.create_index([("property_id", 1), ("asset_type", 1)])
            await self.db.maintenance_events.create_index("event_id", unique=True)
            await self.db.maintenance_events.create_index([("property_id", 1), ("occurred_at", -1)])
            await self.db.maintenance_events.create_index([("client_id", 1), ("occurred_at", -1)])
            # Asset events (per-asset history: issue_created, repair_completed, document_linked, etc.)
            await self.db.asset_events.create_index([("asset_id", 1), ("timestamp", -1)])
            await self.db.asset_events.create_index([("property_id", 1), ("timestamp", -1)])
            await self.db.asset_events.create_index([("client_id", 1), ("related_issue_id", 1)], sparse=True)
            await self.db.asset_events.create_index("event_id", unique=True)
            # Predictive insights cache (scheduled job writes; API can read when fresh)
            await self.db.predictive_insights_cache.create_index("client_id", unique=True)
            await self.db.predictive_insights_cache.create_index("updated_at")
            # Risk signals (stored, explainable risk intelligence per property)
            await self.db.risk_signals.create_index("signal_id", unique=True)
            await self.db.risk_signals.create_index([("client_id", 1), ("property_id", 1), ("status", 1)])
            await self.db.risk_signals.create_index([("client_id", 1), ("generated_at", -1)])
            await self.db.risk_signals.create_index([("property_id", 1), ("status", 1)])
            await self.db.risk_signals.create_index([("property_id", 1), ("signal_category", 1)])
            # Invoices & invoice approvals (Operations → Approvals; gated by INVOICING)
            await self.db.invoices.create_index("invoice_id", unique=True)
            await self.db.invoices.create_index([("client_id", 1), ("status", 1)])
            await self.db.invoices.create_index([("client_id", 1), ("submitted_at", -1)])
            await self.db.invoices.create_index("work_order_id", sparse=True)
            await self.db.invoices.create_index("contractor_id", sparse=True)
            await self.db.invoices.create_index("property_id")
            await self.db.invoice_approvals.create_index("approval_id", unique=True)
            await self.db.invoice_approvals.create_index("invoice_id")
            await self.db.invoice_approvals.create_index([("invoice_id", 1), ("created_at", -1)])
            # Orders (intake → payment → workflow): idempotency by Stripe session
            try:
                await self.db.orders.create_index("pricing.stripe_checkout_session_id", unique=True, sparse=True)
            except Exception:
                pass
            await self.db.orders.create_index("source_draft_id", unique=True)
            await self.db.orders.create_index([("status", 1), ("created_at", -1)])
            await self.db.orders.create_index("order_ref", unique=True)

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
            # Central leads (unified lead engine)
            await self.db.leads.create_index("lead_id", unique=True)
            await self.db.leads.create_index("email")
            await self.db.leads.create_index("created_at")
            await self.db.leads.create_index("last_activity_at")
            await self.db.leads.create_index([("status", 1), ("stage", 1)])
            await self.db.leads.create_index("source_platform")
            await self.db.leads.create_index("lead_score")
            await self.db.leads.create_index("converted_at")
            await self.db.leads.create_index("conversion_source")
            await self.db.lead_audit_logs.create_index("lead_id")
            await self.db.lead_audit_logs.create_index("created_at")
            # Lead events timeline (event-driven conversion automation)
            try:
                await self.db.lead_events.create_index("event_key", unique=True)
            except Exception:
                pass
            await self.db.lead_events.create_index([("lead_id", 1), ("occurred_at", -1)])
            await self.db.lead_events.create_index([("client_id", 1), ("occurred_at", -1)])
            await self.db.lead_events.create_index([("subject_type", 1), ("subject_key", 1), ("occurred_at", -1)])
            await self.db.lead_events.create_index([("event_type", 1), ("occurred_at", -1)])
            # Configurable automation rules
            try:
                await self.db.lead_automation_rules.create_index("rule_key", unique=True)
            except Exception:
                pass
            await self.db.lead_automation_rules.create_index([("enabled", 1), ("event_type", 1)])
            # Canonical sequence state and send history
            try:
                await self.db.lead_sequence_state.create_index("state_id", unique=True)
            except Exception:
                pass
            await self.db.lead_sequence_state.create_index([("status", 1), ("next_run_at", 1)])
            await self.db.lead_sequence_state.create_index([("lead_id", 1), ("updated_at", -1)])
            await self.db.lead_sequence_state.create_index([("client_id", 1), ("updated_at", -1)])
            await self.db.lead_sequence_state.create_index([("subject_type", 1), ("subject_key", 1), ("updated_at", -1)])
            await self.db.lead_sequence_sends.create_index([("lead_id", 1), ("created_at", -1)])
            await self.db.lead_sequence_sends.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.lead_sequence_sends.create_index([("state_id", 1), ("step", 1)])
            try:
                await self.db.lead_sequence_sends.create_index("send_id", unique=True)
            except Exception:
                pass
            # Tenant portal: messages and certificate requests (landlord notification flow)
            await self.db.tenant_messages.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.tenant_messages.create_index("message_id", unique=True)
            await self.db.tenant_requests.create_index([("client_id", 1), ("created_at", -1)])
            await self.db.tenant_requests.create_index("request_id", unique=True)
            await self.db.tenant_requests.create_index([("client_id", 1), ("status", 1)])
            # Contractor portal accounts (contractor_id + email login)
            await self.db.contractor_portal_accounts.create_index("email", unique=True)
            await self.db.contractor_portal_accounts.create_index("contractor_id", unique=True)
            await self.db.contractor_portal_accounts.create_index("status")
            await self.db.password_tokens.create_index([("purpose", 1), ("metadata.contractor_id", 1), ("expires_at", -1)])

            # OTP codes - one active per (phone_hash, purpose); no raw phone stored.
            # Drop legacy unique index (phone_e164, purpose) if present; it causes DuplicateKeyError
            # when upserting by phone_hash only (doc has no phone_e164, so multiple docs look like duplicate null).
            try:
                async for idx in self.db.otp_codes.list_indexes():
                    if idx.get("name") == "phone_e164_1_purpose_1":
                        await self.db.otp_codes.drop_index("phone_e164_1_purpose_1")
                        break
            except Exception:
                pass
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
            # Security monitoring (structured events, incidents, auto-response state)
            await self.db.security_events.create_index([("timestamp", -1)])
            await self.db.security_events.create_index([("event_type", 1), ("timestamp", -1)])
            await self.db.security_events.create_index([("ip", 1), ("timestamp", -1)])
            try:
                await self.db.security_incidents.create_index("incident_key", unique=True)
            except Exception:
                pass
            await self.db.security_incidents.create_index([("status", 1), ("timestamp", -1)])
            await self.db.security_locks.create_index([("expires_at", 1)])
            await self.db.security_blocks.create_index([("expires_at", 1)])
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
            await self.db.requirements.create_index([("client_id", 1), ("status", 1)])
            await self.db.requirements.create_index([("property_id", 1), ("requirement_type", 1)])
            await self.db.automation_status.create_index("client_id", unique=True)
            # Assistant chat (Compliance Vault Assistant)
            await self.db.assistant_conversations.create_index([("client_id", 1), ("last_activity_at", -1)])
            await self.db.assistant_conversations.create_index("conversation_id", unique=True)
            await self.db.assistant_messages.create_index([("conversation_id", 1), ("created_at", 1)])
            await self.db.assistant_messages.create_index([("client_id", 1), ("created_at", -1)])
            # Help Assistant feedback (doc-grounded assistant)
            await self.db.assistant_feedback.create_index([("user_id", 1), ("created_at", -1)])
            await self.db.assistant_feedback.create_index("scope")
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
            {"code": "fire_detection", "title": "Fire Detection Systems", "description": "Fire detection / alarm system inspection (canonical)", "category": "FIRE", "criticality": "HIGH", "weight": 8, "expiry_type": "EXPIRING", "validity_days": 365, "expiring_windows_days": 30, "evidence_required": True, "evidence_types": [], "evidence_tags": [], "applies_to": None, "default_actions": [], "help_text": "Aligned with contractor capability routing (fire_detection).", "updated_at": now},
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
                "email_category": "system_critical",
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
                "email_category": "system_critical",
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
                "email_category": "compliance_notifications",
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
                "email_category": "system_critical",
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "DASHBOARD_READY",
                "channel": "EMAIL",
                "email_template_alias": "portal-ready",
                "sms_body": None,
                "requires_provisioned": True,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "email_category": "system_critical",
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "ACTIVATION_REMINDER",
                "channel": "EMAIL",
                "email_template_alias": "activation-reminder",
                "sms_body": None,
                "requires_provisioned": True,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "email_category": "system_critical",
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
                "email_category": "system_critical",
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "AUTH_ACCOUNT_LOCKED",
                "channel": "EMAIL",
                "email_template_alias": "admin-manual",
                "sms_body": None,
                "requires_provisioned": False,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "email_category": "system_critical",
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "AUTH_LOGIN_RECOVERED",
                "channel": "EMAIL",
                "email_template_alias": "admin-manual",
                "sms_body": None,
                "requires_provisioned": False,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "email_category": "system_critical",
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "AUTH_ADMIN_MFA_CODE",
                "channel": "EMAIL",
                "email_template_alias": "admin-manual",
                "sms_body": None,
                "requires_provisioned": False,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "email_category": "system_critical",
                "is_active": True,
                "updated_at": now,
            },
            {"template_key": "SUBSCRIPTION_CANCELED", "channel": "EMAIL", "email_template_alias": "subscription-canceled", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "MONTHLY_DIGEST", "channel": "EMAIL", "email_template_alias": "monthly-digest", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "COMPLIANCE_EXPIRY_REMINDER_SMS", "channel": "SMS", "email_template_alias": None, "sms_body": "Pleerity: {{count}} compliance item(s) need attention. View: {{portal_link}}", "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": "sms_reminders", "is_active": True, "updated_at": now},
            {"template_key": "PENDING_VERIFICATION_DIGEST", "channel": "EMAIL", "email_template_alias": "pending-verification-digest", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "COMPLIANCE_ALERT", "channel": "EMAIL", "email_template_alias": "compliance-alert", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "compliance_notifications", "is_active": True, "updated_at": now},
            {"template_key": "RENEWAL_REMINDER", "channel": "EMAIL", "email_template_alias": "renewal-reminder", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "SUBSCRIPTION_RENEWAL_REMINDER_7D", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "SUBSCRIPTION_RENEWAL_REMINDER_3D", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "SUBSCRIPTION_GRACE_REMINDER", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "SUBSCRIPTION_RENEWAL_PAID", "channel": "EMAIL", "email_template_alias": "payment-receipt", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "SCHEDULED_REPORT", "channel": "EMAIL", "email_template_alias": "scheduled-report", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ADMIN_MANUAL", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "INTERNAL_ALERT", "channel": "EMAIL", "email_template_alias": "internal-alert", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            # Landlord onboarding sequence (7-day behaviour-aware; category reporting_notifications)
            {"template_key": "ONBOARDING_DAY0_WELCOME", "channel": "EMAIL", "email_template_alias": "onboarding-day0-welcome", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ONBOARDING_DAY1_SETUP_REMINDER", "channel": "EMAIL", "email_template_alias": "onboarding-day1-setup-reminder", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ONBOARDING_DAY2_COMPLIANCE_EDUCATION", "channel": "EMAIL", "email_template_alias": "onboarding-day2-compliance-education", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ONBOARDING_DAY3_PRODUCT_VALUE", "channel": "EMAIL", "email_template_alias": "onboarding-day3-product-value", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ONBOARDING_DAY4_DOCUMENT_PACK_INTRO", "channel": "EMAIL", "email_template_alias": "onboarding-day4-document-pack-intro", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ONBOARDING_DAY5_RISK_AWARENESS", "channel": "EMAIL", "email_template_alias": "onboarding-day5-risk-awareness", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ONBOARDING_DAY6_CASE_EXAMPLE", "channel": "EMAIL", "email_template_alias": "onboarding-day6-case-example", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ONBOARDING_DAY7_ACTIVATION_PUSH", "channel": "EMAIL", "email_template_alias": "onboarding-day7-activation-push", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "reporting_notifications", "is_active": True, "updated_at": now},
            {"template_key": "ADMIN_MANUAL_SMS", "channel": "SMS", "email_template_alias": None, "sms_body": "{{body}}", "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "ADMIN_INVITE", "channel": "EMAIL", "email_template_alias": "admin-invite", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "ORDER_DELIVERED", "channel": "EMAIL", "email_template_alias": "order-delivered", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "ORDER_NOTIFICATION", "channel": "EMAIL", "email_template_alias": "compliance-alert", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "compliance_notifications", "is_active": True, "updated_at": now},
            # Intake / one-off service order receipt (guest or CVP); not gated on subscription
            {"template_key": "ORDER_CONFIRMATION", "channel": "EMAIL", "email_template_alias": "order-intake-confirmation", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "ORDER_INFO_REQUEST", "channel": "EMAIL", "email_template_alias": "order-intake-confirmation", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "ORDER_DOCUMENTS_READY", "channel": "EMAIL", "email_template_alias": "order-intake-confirmation", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "AI_EXTRACTION_APPLIED", "channel": "EMAIL", "email_template_alias": "ai-extraction-applied", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "compliance_notifications", "is_active": True, "updated_at": now},
            {"template_key": "TENANT_INVITE", "channel": "EMAIL", "email_template_alias": "tenant-invite", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": "tenant_portal", "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "CUSTOM_NOTIFICATION", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "SUPPORT_TICKET_CONFIRMATION", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "SUPPORT_INTERNAL_NOTIFICATION", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "LEAD_MANUAL_MESSAGE", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "LEAD_FOLLOWUP", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "lead_nurture", "is_active": True, "updated_at": now},
            {"template_key": "LEAD_TRANSACTIONAL_RISK_CHECK_COMPLETED", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "lead_nurture", "is_active": True, "updated_at": now},
            {"template_key": "LEAD_SLA_BREACH_ADMIN", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "LEAD_HIGH_INTENT_ADMIN", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "COMPLIANCE_SLA_ALERT", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "CLEARFORM_WELCOME", "channel": "EMAIL", "email_template_alias": "clearform-welcome", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "PARTNERSHIP_ACK", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "ENABLEMENT_DELIVERY", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "OTP_CODE_SMS", "channel": "SMS", "email_template_alias": None, "sms_body": "{{body}}", "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "is_active": True, "updated_at": now},
            {"template_key": "OPS_ALERT_NOTIFICATION_SPIKE", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "PROVISIONING_FAILED_ADMIN", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "STRIPE_WEBHOOK_FAILURE_ADMIN", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "CONTRACTOR_ASSIGNED", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            # Lifecycle registry: missing events (template ready; triggers wired when implemented)
            {"template_key": "PASSWORD_CHANGED_CONFIRMATION", "channel": "EMAIL", "email_template_alias": "password-changed-confirmation", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "INVOICE_AVAILABLE", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "system_critical", "is_active": True, "updated_at": now},
            {"template_key": "SUPPORT_TICKET_UPDATED", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "SUPPORT_TICKET_RESOLVED", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": False, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "internal", "is_active": True, "updated_at": now},
            {"template_key": "FEATURE_ANNOUNCEMENT", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "marketing_notifications", "is_active": True, "updated_at": now},
            {"template_key": "PRODUCT_UPDATE", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": False, "requires_entitlement_enabled": False, "plan_required_feature_key": None, "email_category": "marketing_notifications", "is_active": True, "updated_at": now},
            {"template_key": "COMPLIANCE_SCORE_UPDATE", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "compliance_notifications", "is_active": True, "updated_at": now},
            {"template_key": "DOCUMENT_MISSING_ALERT", "channel": "EMAIL", "email_template_alias": "admin-manual", "sms_body": None, "requires_provisioned": True, "requires_active_subscription": True, "requires_entitlement_enabled": True, "plan_required_feature_key": None, "email_category": "compliance_notifications", "is_active": True, "updated_at": now},
        ]
        for t in templates:
            await self.db.notification_templates.update_one(
                {"template_key": t["template_key"]},
                {"$set": t},
                upsert=True,
            )
        logger.info("Notification templates seeded/updated")

    async def _seed_communication_collections(self):
        """Indexes + notification rows + default admin communication templates (idempotent)."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        try:
            await self.db.communication_messages.create_index("communication_id", unique=True)
            await self.db.communication_messages.create_index([("created_at", -1)])
            await self.db.communication_messages.create_index([("message_type", 1), ("created_at", -1)])
            await self.db.communication_messages.create_index([("sent_by_portal_user_id", 1), ("created_at", -1)])
            await self.db.communication_messages.create_index([("status", 1), ("created_at", -1)])
            await self.db.communication_messages.create_index([("status", 1), ("scheduled_at", 1)])
            await self.db.communication_deliveries.create_index("delivery_id", unique=True)
            await self.db.communication_deliveries.create_index([("communication_id", 1), ("client_id", 1)])
            await self.db.communication_templates.create_index("template_id", unique=True)
            await self.db.system_banners.create_index("banner_id", unique=True)
            await self.db.system_banners.create_index([("active", 1), ("start_at", -1)])
            await self.db.system_banner_dismissals.create_index(
                [("portal_user_id", 1), ("banner_id", 1)], unique=True
            )
        except Exception as e:
            logger.warning("communication collections index create: %s", e)

        admin_comm_templates = [
            {
                "template_key": "ADMIN_CLIENT_COMMUNICATION_CRITICAL",
                "channel": "EMAIL",
                "email_template_alias": "client-operational-notice",
                "sms_body": None,
                "requires_provisioned": False,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "email_category": "system_critical",
                "is_active": True,
                "updated_at": now,
            },
            {
                "template_key": "ADMIN_CLIENT_COMMUNICATION_ANNOUNCEMENT",
                "channel": "EMAIL",
                "email_template_alias": "client-operational-notice",
                "sms_body": None,
                "requires_provisioned": False,
                "requires_active_subscription": False,
                "requires_entitlement_enabled": False,
                "plan_required_feature_key": None,
                "email_category": "system_announcements",
                "is_active": True,
                "updated_at": now,
            },
        ]
        for t in admin_comm_templates:
            await self.db.notification_templates.update_one(
                {"template_key": t["template_key"]},
                {"$set": t},
                upsert=True,
            )

        support = os.getenv("EMAIL_REPLY_TO") or os.getenv("SUPPORT_EMAIL") or "support@pleerityenterprise.co.uk"
        defaults = [
            {
                "template_id": "TPL-SERVICE-DISRUPTION",
                "name": "Service disruption notice",
                "description": "Client-facing notice when impact is confirmed.",
                "default_message_type": "INCIDENT",
                "subject_template": "Service disruption — {{incident_title}}",
                "body_template": "<p>Hello,</p><p>We are experiencing a service disruption affecting Compliance Vault Pro. {{incident_title}}</p><p>Our team is working to restore normal service. We will update you as we learn more.</p><p>If you need urgent help, contact us at {{support_email}}.</p>",
                "in_app_title_template": "Service disruption",
                "in_app_body_template": "We are investigating a service issue. Details have been emailed to you.",
                "banner_text_template": "Service disruption — we are working on a fix.",
                "is_system_seed": True,
                "updated_at": now,
            },
            {
                "template_id": "TPL-INVESTIGATING",
                "name": "We are investigating an issue",
                "description": "Early incident comms before root cause is known.",
                "default_message_type": "INCIDENT",
                "subject_template": "We are investigating an issue",
                "body_template": "<p>Hello,</p><p>We have detected an issue that may affect your access to Compliance Vault Pro. Our engineering team is investigating.</p><p>You do not need to take any action right now. We will email you again when we have more information.</p><p>Questions: {{support_email}}</p>",
                "in_app_title_template": "Issue under investigation",
                "in_app_body_template": "We are investigating a potential service issue. Check your email for details.",
                "banner_text_template": "We are investigating a service issue — updates to follow.",
                "is_system_seed": True,
                "updated_at": now,
            },
            {
                "template_id": "TPL-ISSUE-RESOLVED",
                "name": "Issue resolved",
                "description": "Resolution notice after an incident.",
                "default_message_type": "SERVICE_UPDATE",
                "subject_template": "Resolved: {{incident_title}}",
                "body_template": "<p>Hello,</p><p>The issue we reported earlier (<strong>{{incident_title}}</strong>) is now resolved. Service should be operating normally.</p><p>If you still see problems, please reply to this email or contact {{support_email}}.</p>",
                "in_app_title_template": "Issue resolved",
                "in_app_body_template": "The reported service issue is resolved.",
                "banner_text_template": "",
                "is_system_seed": True,
                "updated_at": now,
            },
            {
                "template_id": "TPL-PLANNED-MAINTENANCE",
                "name": "Planned maintenance",
                "description": "Scheduled maintenance window.",
                "default_message_type": "MAINTENANCE_NOTICE",
                "subject_template": "Planned maintenance — {{incident_title}}",
                "body_template": "<p>Hello,</p><p>We will perform planned maintenance: <strong>{{incident_title}}</strong>.</p><p>During the window you may experience brief interruptions. We aim to complete work as quickly as possible.</p><p>Contact: {{support_email}}</p>",
                "in_app_title_template": "Planned maintenance",
                "in_app_body_template": "Scheduled maintenance may briefly affect the portal. See email for times and scope.",
                "banner_text_template": "Planned maintenance in progress — short interruptions possible.",
                "is_system_seed": True,
                "updated_at": now,
            },
            {
                "template_id": "TPL-ACCOUNT-SUPPORT",
                "name": "Account-specific support message",
                "description": "Direct message regarding a single client account.",
                "default_message_type": "DIRECT_SUPPORT_MESSAGE",
                "subject_template": "Regarding your account ({{customer_reference}})",
                "body_template": "<p>Hello {{client_name}},</p><p>We are writing regarding your Compliance Vault Pro account.</p><p>[Describe the situation and any actions required.]</p><p>If anything is unclear, reply to this email or contact {{support_email}}.</p>",
                "in_app_title_template": "Account update",
                "in_app_body_template": "We sent you an important account message by email.",
                "banner_text_template": "",
                "is_system_seed": True,
                "updated_at": now,
            },
        ]
        for doc in defaults:
            doc.setdefault(
                "variables_hint",
                ["client_name", "plan_name", "incident_title", "support_email", "portal_link", "customer_reference"],
            )
            doc["support_email_placeholder"] = support
            insert_doc = {**doc, "created_at": now, "updated_at": now}
            await self.db.communication_templates.update_one(
                {"template_id": doc["template_id"]},
                {"$setOnInsert": insert_doc},
                upsert=True,
            )
        logger.info("Communication collections / templates seeded")

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
