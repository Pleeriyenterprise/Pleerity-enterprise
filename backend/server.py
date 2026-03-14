from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uuid
from contextlib import asynccontextmanager
from database import database
from routes import auth, intake, onboarding, portal, webhooks, client, admin, documents, assistant, profile, properties, rules, templates, calendar, sms, otp, reports, tenant, webhooks_config, billing, admin_billing, public, admin_orders, orders, client_orders, admin_notifications, admin_services, public_services, blog, admin_services_v2, public_services_v2, services_public, orchestration, intake_wizard, admin_intake_schema, admin_pending_payments, analytics, support, admin_canned_responses, knowledge_base, leads, consent, cms, enablement, reporting, team, prompts, document_packs, checkout_validation, marketing, admin_legal_content, talent_pool, partnerships, admin_modules, admin_submissions, intake_uploads, portfolio, risk_check, admin_risk_leads
from routes import observability, ops_compliance, contractors, maintenance, client_maintenance, client_approvals, predictive_data, admin_document_templates, public_orders

# ClearForm - Separate Product Routes
from clearform.routes import auth as clearform_auth
from clearform.routes import credits as clearform_credits
from clearform.routes import documents as clearform_documents
from clearform.routes import subscriptions as clearform_subscriptions
from clearform.routes import webhooks as clearform_webhooks
from clearform.routes.document_types import router as clearform_document_types_router
from clearform.routes.document_types import templates_router as clearform_templates_router
from clearform.routes.workspaces import workspaces_router as clearform_workspaces_router
from clearform.routes.workspaces import profiles_router as clearform_profiles_router
from clearform.routes.organizations import router as clearform_organizations_router
from clearform.routes.audit import router as clearform_audit_router
from clearform.routes.admin import router as clearform_admin_router

import os
import logging
import asyncio
from datetime import timezone as dt_timezone
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.mongodb import MongoDBJobStore

# All cron schedules are intended to be UTC; enforce explicitly so server locale cannot change them
SCHEDULER_TIMEZONE = dt_timezone.utc

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize scheduler with MongoDB job store for persistence
# Jobs will survive server restarts
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'compliance_vault_pro')

jobstores = {
    'default': MongoDBJobStore(
        database=db_name,
        collection='scheduled_jobs',
        client=None  # Will use mongo_url
    )
}

# Configure job store with MongoDB URL
try:
    from pymongo import MongoClient
    mongo_client = MongoClient(mongo_url)
    jobstores['default'] = MongoDBJobStore(
        database=db_name,
        collection='scheduled_jobs',
        client=mongo_client
    )
    logger.info(f"MongoDB job store configured: {db_name}.scheduled_jobs")
except Exception as e:
    logger.warning(f"Failed to configure MongoDB job store, using memory store: {e}")
    jobstores = {}

# Safe defaults for cloud reliability: avoid startup misfires and overlapping runs
JOB_DEFAULTS = {
    "coalesce": True,
    "max_instances": 1,
    "misfire_grace_time": 300,
}
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    timezone=SCHEDULER_TIMEZONE,
    job_defaults=JOB_DEFAULTS,
)

# Import job runners from shared module (used by scheduler and admin run-now)
from job_runner import (
    run_daily_reminders,
    run_pending_verification_digest,
    run_monthly_digests,
    run_compliance_status_check,
    run_scheduled_reports,
    run_compliance_score_snapshots,
    run_compliance_recalc_worker,
    run_compliance_recalc_sla_monitor,
    run_expiry_rollover_recalc,
    run_order_delivery_processing,
    run_sla_monitoring,
    run_stuck_order_detection,
    run_queued_order_processing,
    run_abandoned_intake_detection,
    run_lead_followup_processing,
    run_lead_sla_check,
    run_checklist_nurture_processing,
    run_onboarding_sequence_processing,
    run_risk_lead_nurture_processing,
    run_notification_failure_spike_monitor,
    run_notification_retry_worker,
    run_pending_payment_lifecycle,
)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Compliance Vault Pro API")
    if os.environ.get("PYTEST_RUNNING") == "1":
        logger.info("PYTEST_RUNNING=1: skipping database, scheduler, and heavy startup")
        yield
        return
    await database.connect()

    # Production safety: require non-default JWT_SECRET when ENV is production
    _env = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    if _env in ("production", "prod"):
        try:
            from auth import require_non_default_jwt_secret
            require_non_default_jwt_secret()
        except RuntimeError as e:
            logger.critical("Startup aborted: %s", e)
            raise

    # Alerting: warn if admin incident emails are not configured (ops visibility)
    _alert_emails = (os.environ.get("ADMIN_ALERT_EMAILS") or os.environ.get("OPS_ALERT_EMAIL") or "").strip()
    if not _alert_emails:
        logger.warning(
            "ADMIN_ALERT_EMAILS and OPS_ALERT_EMAIL are not set. Admin incident alerts will not be sent. "
            "Set one of these environment variables for production."
        )

    # Stripe config: log mode (test/live) from key prefix and which price IDs are in use (no secret keys)
    try:
        stripe_key = (os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY") or "").strip()
        if not stripe_key:
            logger.error("STRIPE_API_KEY / STRIPE_SECRET_KEY is not set. Intake checkout and billing will fail.")
            stripe_mode = "unknown"
        else:
            stripe_mode = "test" if stripe_key.startswith("sk_test_") else "live"
            logger.info("STRIPE_MODE = %s (from Stripe key prefix)", stripe_mode)
            if stripe_mode == "test" and "CVP_PROD" in os.environ.get("ENV", "").upper():
                logger.warning("STRIPE_API_KEY looks like test key but ENV suggests production. Verify key.")
        from services.plan_registry import plan_registry, PlanCode, get_stripe_price_mappings, StripeModeMismatchError
        try:
            config = get_stripe_price_mappings()
            for plan in PlanCode:
                prices = config["mappings"].get(plan.value, {})
                sub_id = prices.get("subscription_price_id")
                onb_id = prices.get("onboarding_price_id")
                logger.info(
                    "Stripe price IDs plan=%s subscription_price_id=%s onboarding_price_id=%s",
                    plan.value, sub_id or "(missing)", onb_id or "(none)"
                )
        except StripeModeMismatchError as e:
            logger.error("Stripe mode mismatch: %s. Set STRIPE_TEST_PRICE_* or STRIPE_LIVE_PRICE_* env vars for current key mode.", e)
    except Exception as e:
        logger.warning("Stripe config check failed: %s", e)

    # Public frontend URL for activation/email links (safe log, no secrets)
    try:
        from utils.public_app_url import get_public_app_url
        _app_url = get_public_app_url(for_email_links=False)
        logger.info("PUBLIC_APP_URL configured: %s", _app_url)
    except Exception as e:
        logger.warning("PUBLIC_APP_URL not configured: %s", e)

    # Idempotent OWNER bootstrap: when BOOTSTRAP_ENABLED=true OR when email+password env are set (Render)
    bootstrap_enabled = os.environ.get("BOOTSTRAP_ENABLED", "").strip().lower() == "true"
    bootstrap_email = (os.environ.get("BOOTSTRAP_OWNER_EMAIL") or "").strip()
    bootstrap_password = (os.environ.get("BOOTSTRAP_OWNER_PASSWORD") or "").strip()
    if bootstrap_enabled or (bootstrap_email and bootstrap_password):
        try:
            from services.owner_bootstrap import run_bootstrap_owner
            result = await run_bootstrap_owner()
            logger.info("Bootstrap owner: %s - %s", result.get("action"), result.get("message"))
        except Exception as e:
            logger.warning("Bootstrap owner failed: %s", e)
    
    # Create consent indexes
    try:
        from services.consent_service import ensure_consent_indexes
        await ensure_consent_indexes()
        logger.info("Consent indexes created")
    except Exception as e:
        logger.error(f"Failed to create consent indexes: {e}")
    
    # Create CMS indexes
    try:
        db = database.get_db()
        await db.cms_pages.create_index("page_id", unique=True)
        await db.cms_pages.create_index("slug", unique=True)
        await db.cms_pages.create_index("status")
        await db.cms_revisions.create_index("revision_id", unique=True)
        await db.cms_revisions.create_index([("page_id", 1), ("version", -1)])
        await db.cms_media.create_index("media_id", unique=True)
        await db.cms_media.create_index("media_type")
        await db.cms_media.create_index([("file_name", "text"), ("alt_text", "text")])
        logger.info("CMS indexes created")
    except Exception as e:
        logger.error(f"Failed to create CMS indexes: {e}")
    
    # Create Enablement Engine indexes and seed templates
    try:
        from services.enablement_templates import ensure_enablement_indexes, seed_enablement_templates
        await ensure_enablement_indexes()
        await seed_enablement_templates()
        logger.info("Enablement engine initialized")
    except Exception as e:
        logger.error(f"Failed to initialize enablement engine: {e}")
    
    # Seed service catalogue
    try:
        from services.service_catalogue import seed_service_catalogue
        await seed_service_catalogue()
        logger.info("Service catalogue seeded successfully")
    except Exception as e:
        logger.error(f"Failed to seed service catalogue: {e}")
    
    # Seed service catalogue V2 (authoritative)
    try:
        from services.service_definitions_v2 import seed_service_catalogue_v2
        result = await seed_service_catalogue_v2()
        logger.info(f"Service catalogue V2 seeded: {result['created']} created, {result['skipped']} skipped")
    except Exception as e:
        logger.error(f"Failed to seed service catalogue V2: {e}")
    
    # Seed CMS pages (hub, category, service pages) so /services/* category pages show services. Idempotent.
    try:
        from scripts.seed_cms_pages import seed_cms_pages
        await seed_cms_pages()
        logger.info("CMS pages (services hub, categories, service pages) seeded")
    except Exception as e:
        logger.warning("CMS pages seed failed (category pages may show 'No services available'): %s", e)
    
    # Create Prompt Manager indexes
    try:
        db = database.get_db()
        await db.prompt_templates.create_index("template_id", unique=True)
        await db.prompt_templates.create_index([("service_code", 1), ("doc_type", 1), ("status", 1)])
        await db.prompt_templates.create_index([("service_code", 1), ("doc_type", 1), ("version", -1)])
        await db.prompt_templates.create_index("status")
        await db.prompt_templates.create_index("tags")
        await db.prompt_test_results.create_index("test_id", unique=True)
        await db.prompt_test_results.create_index([("template_id", 1), ("executed_at", -1)])
        await db.prompt_audit_log.create_index("audit_id", unique=True)
        await db.prompt_audit_log.create_index([("template_id", 1), ("performed_at", -1)])
        await db.prompt_audit_log.create_index("performed_at")
        # Prompt execution metrics indexes for analytics
        await db.prompt_execution_metrics.create_index([("template_id", 1), ("executed_at", -1)])
        await db.prompt_execution_metrics.create_index([("service_code", 1), ("executed_at", -1)])
        await db.prompt_execution_metrics.create_index("executed_at")
        logger.info("Prompt Manager indexes created")
    except Exception as e:
        logger.error(f"Failed to create Prompt Manager indexes: {e}")
    
    # Create Document Pack Orchestrator indexes
    try:
        db = database.get_db()
        await db.document_pack_items.create_index("item_id", unique=True)
        await db.document_pack_items.create_index([("order_id", 1), ("canonical_index", 1)])
        await db.document_pack_items.create_index("order_id")
        await db.document_pack_items.create_index("status")
        await db.document_pack_items.create_index("doc_type")
        await db.document_pack_items.create_index("doc_key")
        logger.info("Document Pack Orchestrator indexes created")
    except Exception as e:
        logger.error(f"Failed to create Document Pack Orchestrator indexes: {e}")
    
    # Document templates (server-side .docx per service_code/doc_type)
    try:
        db = database.get_db()
        await db.document_templates.create_index("template_id", unique=True)
        await db.document_templates.create_index([("service_code", 1), ("doc_type", 1)], unique=True)
        await db.document_templates.create_index("service_code")
        logger.info("Document templates indexes created")
    except Exception as e:
        logger.error("Document templates indexes: %s", e)
    
    # Create ClearForm indexes
    try:
        db = database.get_db()
        # Users
        await db.clearform_users.create_index("user_id", unique=True)
        await db.clearform_users.create_index("email", unique=True)
        await db.clearform_users.create_index("stripe_customer_id", sparse=True)
        # Documents
        await db.clearform_documents.create_index("document_id", unique=True)
        await db.clearform_documents.create_index([("user_id", 1), ("created_at", -1)])
        await db.clearform_documents.create_index("status")
        await db.clearform_documents.create_index("document_type")
        # Credit transactions
        await db.clearform_credit_transactions.create_index("transaction_id", unique=True)
        await db.clearform_credit_transactions.create_index([("user_id", 1), ("created_at", -1)])
        await db.clearform_credit_transactions.create_index("transaction_type")
        # Credit expiry
        await db.clearform_credit_expiry.create_index("expiry_id", unique=True)
        await db.clearform_credit_expiry.create_index([("user_id", 1), ("expires_at", 1)])
        await db.clearform_credit_expiry.create_index("expired")
        # Subscriptions
        await db.clearform_subscriptions.create_index("subscription_id", unique=True)
        await db.clearform_subscriptions.create_index("user_id")
        await db.clearform_subscriptions.create_index("stripe_subscription_id", sparse=True)
        # Top-ups
        await db.clearform_credit_topups.create_index("topup_id", unique=True)
        await db.clearform_credit_topups.create_index("stripe_checkout_session_id", sparse=True)
        # Document types (admin-configurable)
        await db.clearform_document_types.create_index("type_id", unique=True)
        await db.clearform_document_types.create_index("code", unique=True)
        await db.clearform_document_types.create_index("category")
        await db.clearform_document_types.create_index("is_active")
        # Document categories
        await db.clearform_document_categories.create_index("category_id", unique=True)
        await db.clearform_document_categories.create_index("code", unique=True)
        # User templates
        await db.clearform_templates.create_index("template_id", unique=True)
        await db.clearform_templates.create_index([("user_id", 1), ("document_type_code", 1)])
        await db.clearform_templates.create_index("workspace_id", sparse=True)
        # Workspaces
        await db.clearform_workspaces.create_index("workspace_id", unique=True)
        await db.clearform_workspaces.create_index("owner_id")
        # Smart profiles
        await db.clearform_profiles.create_index("profile_id", unique=True)
        await db.clearform_profiles.create_index([("user_id", 1), ("profile_type", 1)])
        # Organizations
        await db.clearform_organizations.create_index("org_id", unique=True)
        await db.clearform_organizations.create_index("slug", unique=True)
        await db.clearform_organizations.create_index("owner_id")
        # Organization members
        await db.clearform_org_members.create_index("member_id", unique=True)
        await db.clearform_org_members.create_index([("org_id", 1), ("user_id", 1)], unique=True)
        await db.clearform_org_members.create_index("user_id")
        # Organization invitations
        await db.clearform_org_invitations.create_index("invitation_id", unique=True)
        await db.clearform_org_invitations.create_index([("org_id", 1), ("email", 1), ("status", 1)])
        # Audit logs
        await db.clearform_audit_logs.create_index("log_id", unique=True)
        await db.clearform_audit_logs.create_index([("user_id", 1), ("created_at", -1)])
        await db.clearform_audit_logs.create_index([("org_id", 1), ("created_at", -1)])
        await db.clearform_audit_logs.create_index("action")
        await db.clearform_audit_logs.create_index("created_at")
        # Compliance packs
        await db.clearform_compliance_packs.create_index("pack_id", unique=True)
        await db.clearform_compliance_packs.create_index("code", unique=True)
        logger.info("ClearForm indexes created")
        
        # Initialize default document types
        from clearform.services.document_type_service import document_type_service
        await document_type_service.initialize_defaults()
        logger.info("ClearForm document types initialized")
    except Exception as e:
        logger.error(f"Failed to create ClearForm indexes: {e}")
    
    # Configure scheduled jobs – bind scheduler to running event loop so async jobs execute
    try:
        _loop = asyncio.get_running_loop()
        scheduler._eventloop = _loop
        logger.info("Scheduler bound to running event loop (jobs will run automatically)")
    except RuntimeError as e:
        logger.warning("No running event loop for scheduler: %s. Jobs may not run automatically.", e)
    # Daily reminders at 9:00 AM UTC
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=9, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="daily_reminders",
        name="Daily Compliance Reminders",
        replace_existing=True,
        args=["daily_reminders"],
        kwargs={"run_type": "schedule"},
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    
    # Pending verification digest daily at 9:30 AM UTC (counts only, no PII)
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=9, minute=30, timezone=SCHEDULER_TIMEZONE),
        id="pending_verification_digest",
        name="Pending Verification Digest",
        replace_existing=True,
        args=["pending_verification_digest"],
        kwargs={"run_type": "schedule"},
    )
    
    # Monthly digest on the 1st of each month at 10:00 AM UTC
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(day=1, hour=10, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="monthly_digest",
        name="Monthly Compliance Digest",
        replace_existing=True,
        args=["monthly_digest"],
        kwargs={"run_type": "schedule"},
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    
    # Compliance status check - runs twice daily at 8:00 AM and 6:00 PM UTC
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=8, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="compliance_check_morning",
        name="Compliance Status Check (Morning)",
        replace_existing=True,
        args=["compliance_check_morning"],
        kwargs={"run_type": "schedule"},
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=18, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="compliance_check_evening",
        name="Compliance Status Check (Evening)",
        replace_existing=True,
        args=["compliance_check_evening"],
        kwargs={"run_type": "schedule"},
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    
    # Scheduled reports - runs every hour
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute=0, timezone=SCHEDULER_TIMEZONE),
        id="scheduled_reports",
        name="Process Scheduled Reports",
        replace_existing=True,
        args=["scheduled_reports"],
        kwargs={"run_type": "schedule"},
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    
    # Daily compliance score snapshots at 2:00 AM UTC
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=2, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="compliance_score_snapshots",
        name="Daily Compliance Score Snapshots",
        replace_existing=True,
        args=["compliance_score_snapshots"],
        kwargs={"run_type": "schedule"},
    )
    
    # Expiry rollover - daily 00:10 UTC
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=0, minute=10, timezone=SCHEDULER_TIMEZONE),
        id="expiry_rollover_recalc",
        name="Expiry Rollover Compliance Recalc",
        replace_existing=True,
        args=["expiry_rollover_recalc"],
        kwargs={"run_type": "schedule"},
    )
    
    # Async compliance recalc worker - every 15 seconds
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        IntervalTrigger(seconds=15, timezone=SCHEDULER_TIMEZONE),
        id="compliance_recalc_worker",
        name="Compliance Recalc Worker",
        replace_existing=True,
        args=["compliance_recalc_worker"],
        kwargs={"run_type": "schedule"},
    )
    
    # Compliance recalc SLA monitor - every 5 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/5", timezone=SCHEDULER_TIMEZONE),
        id="compliance_recalc_sla_monitor",
        name="Compliance Recalc SLA Monitor",
        replace_existing=True,
        args=["compliance_recalc_sla_monitor"],
        kwargs={"run_type": "schedule"},
    )
    
    # Notification failure spike monitor - every 5 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/5", timezone=SCHEDULER_TIMEZONE),
        id="notification_failure_spike_monitor",
        name="Notification Failure Spike Monitor",
        replace_existing=True,
        args=["notification_failure_spike_monitor"],
        kwargs={"run_type": "schedule"},
    )
    
    # Scheduler heartbeat - every 2 minutes (for system health "scheduler alive" visibility)
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        IntervalTrigger(minutes=2, timezone=SCHEDULER_TIMEZONE),
        id="scheduler_heartbeat",
        name="Scheduler Heartbeat",
        replace_existing=True,
        args=["scheduler_heartbeat"],
        kwargs={"run_type": "schedule"},
    )
    # Delivery reconciliation - every 15 min (enrich reminder/digest runs with delivered/bounced from message_logs)
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/15", timezone=SCHEDULER_TIMEZONE),
        id="delivery_reconciliation",
        name="Delivery Reconciliation",
        replace_existing=True,
        args=["delivery_reconciliation"],
        kwargs={"run_type": "schedule"},
    )
    # SLA watchdog (job run SLA) - every 10 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/10", timezone=SCHEDULER_TIMEZONE),
        id="sla_watchdog",
        name="SLA Watchdog (job run monitoring)",
        replace_existing=True,
        args=["sla_watchdog"],
        kwargs={"run_type": "schedule"},
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    
    # Notification retry worker - every minute
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*", timezone=SCHEDULER_TIMEZONE),
        id="notification_retry_worker",
        name="Notification Retry Worker",
        replace_existing=True,
        args=["notification_retry_worker"],
        kwargs={"run_type": "schedule"},
    )
    
    # Order delivery processing - every 5 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/5", timezone=SCHEDULER_TIMEZONE),
        id="order_delivery_processing",
        name="Order Delivery Processing",
        replace_existing=True,
        args=["order_delivery_processing"],
        kwargs={"run_type": "schedule"},
    )
    
    # SLA monitoring - every 15 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/15", timezone=SCHEDULER_TIMEZONE),
        id="sla_monitoring",
        name="SLA Monitoring",
        replace_existing=True,
        args=["sla_monitoring"],
        kwargs={"run_type": "schedule"},
    )
    
    # Stuck order detection - every 30 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/30", timezone=SCHEDULER_TIMEZONE),
        id="stuck_order_detection",
        name="Stuck Order Detection",
        replace_existing=True,
        args=["stuck_order_detection"],
        kwargs={"run_type": "schedule"},
    )
    
    # Queued order processing - every 10 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/10", timezone=SCHEDULER_TIMEZONE),
        id="queued_order_processing",
        name="Queued Order Processing",
        replace_existing=True,
        args=["queued_order_processing"],
        kwargs={"run_type": "schedule"},
    )
    
    # Abandoned intake detection - every 15 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/15", timezone=SCHEDULER_TIMEZONE),
        id="abandoned_intake_detection",
        name="Abandoned Intake Detection",
        replace_existing=True,
        args=["abandoned_intake_detection"],
        kwargs={"run_type": "schedule"},
    )
    
    # Lead follow-up processing - every 15 minutes
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute="*/15", timezone=SCHEDULER_TIMEZONE),
        id="lead_followup_processing",
        name="Lead Follow-up Processing",
        replace_existing=True,
        args=["lead_followup_processing"],
        kwargs={"run_type": "schedule"},
    )
    
    # Pending payment lifecycle - daily 3:00 AM UTC
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=3, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="pending_payment_lifecycle",
        name="Pending Payment Lifecycle (abandoned/archived)",
        replace_existing=True,
        args=["pending_payment_lifecycle"],
        kwargs={"run_type": "schedule"},
    )
    
    # Lead SLA breach check - every hour
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute=0, timezone=SCHEDULER_TIMEZONE),
        id="lead_sla_check",
        name="Lead SLA Breach Check",
        replace_existing=True,
        args=["lead_sla_check"],
        kwargs={"run_type": "schedule"},
    )
    
    # Checklist nurture - daily 9:00 AM UTC
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=9, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="checklist_nurture_processing",
        name="Checklist Nurture (compliance checklist leads)",
        replace_existing=True,
        args=["checklist_nurture_processing"],
        kwargs={"run_type": "schedule"},
    )
    # Risk-check lead nurture (steps 2–5 at day 2, 4, 6, 10) - daily at 9:15 AM UTC
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=9, minute=15, timezone=SCHEDULER_TIMEZONE),
        id="risk_lead_nurture_processing",
        name="Risk Lead Nurture (risk-check conversion leads)",
        replace_existing=True,
        args=["risk_lead_nurture_processing"],
        kwargs={"run_type": "schedule"},
    )
    # Landlord onboarding sequence (7-day emails) - every hour
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute=30, timezone=SCHEDULER_TIMEZONE),
        id="onboarding_sequence_processing",
        name="Onboarding Sequence (landlord 7-day emails)",
        replace_existing=True,
        args=["onboarding_sequence_processing"],
        kwargs={"run_type": "schedule"},
    )
    # Predictive maintenance insights - daily 4:00 AM UTC (warms insights for clients with PREDICTIVE_MAINTENANCE)
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=4, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="predictive_insights_job",
        name="Predictive Maintenance Insights (precompute)",
        replace_existing=True,
        args=["predictive_insights_job"],
        kwargs={"run_type": "schedule"},
    )
    # Risk signals - daily 4:30 AM UTC (generates stored risk signals for clients with PREDICTIVE_MAINTENANCE)
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(hour=4, minute=30, timezone=SCHEDULER_TIMEZONE),
        id="risk_signals_job",
        name="Risk Signals (generate)",
        replace_existing=True,
        args=["risk_signals_job"],
        kwargs={"run_type": "schedule"},
    )
    # Work order SLA breach / at-risk - every hour
    scheduler.add_job(
        "job_runner:run_scheduled_job",
        CronTrigger(minute=0, timezone=SCHEDULER_TIMEZONE),
        id="work_order_sla_breach_job",
        name="Work Order SLA Breach & At-Risk",
        replace_existing=True,
        args=["work_order_sla_breach_job"],
        kwargs={"run_type": "schedule"},
    )

    scheduler_started = False
    try:
        scheduler.start(paused=True)
        scheduler_started = True
        jobs = scheduler.get_jobs()
        job_ids = [getattr(j, "id", None) for j in jobs]
        logger.info(
            "Scheduler started (paused). All jobs registered: %s job(s). Job ids: %s",
            len(jobs),
            job_ids,
        )
        next_runs = [getattr(j, "next_run_time", None) for j in jobs[:5]]
        next_runs_fmt = [t.isoformat() if t else None for t in next_runs]
        logger.info("Scheduler next runs (first 5): %s", next_runs_fmt)
        # At DEBUG: log every job's next_run_time to verify cron/interval schedules
        for j in jobs:
            nrt = getattr(j, "next_run_time", None)
            logger.debug(
                "Scheduler job: id=%s name=%s next_run_time=%s",
                getattr(j, "id", None),
                getattr(j, "name", None),
                nrt.isoformat() if nrt else None,
            )
        # Startup reconciliation: catch-up missed critical jobs within recovery window, or create incident if overdue
        try:
            from services.startup_reconciliation import run_startup_reconciliation
            await run_startup_reconciliation()
        except Exception as recon_err:
            logger.exception("Startup reconciliation failed (scheduler still paused): %s", recon_err)
        scheduler.resume()
        logger.info("Scheduler resumed; jobs will execute at scheduled times.")
    except Exception as e:
        logger.exception("Background job scheduler failed to start: %s. API will run without scheduled jobs.", e)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Compliance Vault Pro API")
    if scheduler_started:
        scheduler.shutdown(wait=False)
        logger.info("Background job scheduler stopped")
    await database.close()

# Create FastAPI app
app = FastAPI(
    title="Compliance Vault Pro API",
    description="AI-Driven Solutions & Compliance - Pleerity Enterprise Ltd",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
# Required production origins (custom domains + Vercel + local dev). When CORS_ORIGINS is set,
# these are merged in so all are allowed; when CORS_ORIGINS is '*' or unset, use this list for safety.
_CORS_REQUIRED_ORIGINS = [
    "https://pleerityenterprise.co.uk",
    "https://www.pleerityenterprise.co.uk",
    "https://pleerity-enterprise.vercel.app",
    "http://localhost:3000",
]
_cors_env = (os.environ.get("CORS_ORIGINS") or "").strip()
if _cors_env and _cors_env != "*":
    _origins_from_env = [o.strip() for o in _cors_env.split(",") if o.strip()]
    _cors_origins = list(dict.fromkeys(_origins_from_env + _CORS_REQUIRED_ORIGINS))
else:
    _cors_origins = _CORS_REQUIRED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Correlation ID for tracing (set or forward X-Correlation-Id on every request/response)
from middleware import CorrelationIdMiddleware
app.add_middleware(CorrelationIdMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(intake.router)
app.include_router(onboarding.router)
app.include_router(portal.router)
app.include_router(webhooks.router)
app.include_router(client.router)
app.include_router(portfolio.router)
app.include_router(admin.router)
app.include_router(observability.router)
app.include_router(documents.router)
app.include_router(assistant.router)
app.include_router(profile.router)
app.include_router(properties.router)
app.include_router(rules.router)
app.include_router(templates.router)
app.include_router(calendar.router)
app.include_router(sms.router)
app.include_router(otp.router)
app.include_router(reports.router)
app.include_router(tenant.router)
app.include_router(webhooks_config.router)
app.include_router(billing.router)
app.include_router(admin_billing.router)
app.include_router(public.router)
app.include_router(public_orders.router)
app.include_router(admin_orders.router)
app.include_router(orders.router)
app.include_router(client_orders.router)
app.include_router(admin_notifications.router)
app.include_router(admin_services.router)  # Canonical /api/admin/services (task paths)
app.include_router(public_services.router)
app.include_router(blog.router)
app.include_router(admin_services_v2.router, prefix="/api/admin/services/v2")  # V2 at /v2 only
app.include_router(public_services_v2.router)
app.include_router(services_public.router)
app.include_router(orchestration.router)
app.include_router(intake_wizard.router)
app.include_router(admin_intake_schema.router)
app.include_router(admin_pending_payments.router)
app.include_router(analytics.router)
app.include_router(support.public_router)
app.include_router(support.client_router)
app.include_router(support.admin_router)
app.include_router(admin_canned_responses.router)
app.include_router(knowledge_base.public_router)
app.include_router(knowledge_base.admin_router)
app.include_router(knowledge_base.client_help_router)
app.include_router(leads.public_router)
app.include_router(leads.admin_router)
app.include_router(consent.public_router)
app.include_router(consent.admin_router)
app.include_router(cms.router)  # Admin CMS routes
app.include_router(cms.public_router)  # Public CMS page rendering
app.include_router(enablement.router)  # Customer Enablement Automation Engine
app.include_router(reporting.router)  # Full Reporting System - Export & Scheduling
app.include_router(reporting.public_router)  # Public Report Sharing
app.include_router(team.router)  # Team Permissions & Role Management
app.include_router(prompts.router)  # Enterprise Prompt Manager
app.include_router(admin_document_templates.router)  # Server-side DOCX templates (per service/doc_type)
app.include_router(document_packs.router)  # Document Pack Orchestrator
app.include_router(checkout_validation.router)  # Checkout Validation
app.include_router(marketing.router)  # Marketing Website CMS
app.include_router(admin_legal_content.router)  # Legal Content Editor
app.include_router(talent_pool.router)  # Talent Pool
app.include_router(partnerships.router)  # Partnerships
app.include_router(admin_modules.router)  # Public endpoints
app.include_router(admin_modules.router_admin)  # Admin endpoints
app.include_router(admin_submissions.router)  # Unified submissions list/get/patch/notes/export
app.include_router(intake_uploads.router)  # Intake document uploads
app.include_router(risk_check.router)  # Compliance Risk Check (standalone demo, no client/provisioning)
app.include_router(admin_risk_leads.router)  # Admin: risk leads list, export, resend report
app.include_router(observability.router)  # Admin: job-runs, incidents, score-events (observability)
app.include_router(ops_compliance.router)  # Admin: Operations & Compliance (feature flags, plan usage)
app.include_router(contractors.router)  # Admin: Contractors (Ops Contractor Network)
app.include_router(maintenance.router)  # Admin: Work orders (Ops Maintenance)
app.include_router(client_maintenance.router)  # Client: Maintenance work orders (gated by MAINTENANCE_WORKFLOWS)
app.include_router(client_approvals.router)  # Client: Invoice approvals (gated by INVOICING)
app.include_router(predictive_data.router)  # Admin: Property assets & maintenance events (data for predictive)

# ============================================================================
# ClearForm Routes - Separate Product (Isolated)
# ============================================================================
app.include_router(clearform_auth.router)  # ClearForm Auth
app.include_router(clearform_credits.router)  # ClearForm Credits
app.include_router(clearform_documents.router)  # ClearForm Documents
app.include_router(clearform_subscriptions.router)  # ClearForm Subscriptions
app.include_router(clearform_webhooks.router)  # ClearForm Stripe Webhooks
app.include_router(clearform_document_types_router)  # ClearForm Document Types (Admin-configurable)
app.include_router(clearform_templates_router)  # ClearForm User Templates
app.include_router(clearform_workspaces_router)  # ClearForm Workspaces
app.include_router(clearform_profiles_router)  # ClearForm Smart Profiles
app.include_router(clearform_organizations_router)  # ClearForm Organizations (Institutional)
app.include_router(clearform_audit_router)  # ClearForm Audit Logs
app.include_router(clearform_admin_router)  # ClearForm Admin Panel

# Root path (/) — so health checks and GET / don't get 404
@app.get("/")
@app.head("/")
async def root_path():
    return {
        "service": "Compliance Vault Pro",
        "api": "/api",
        "health": "/api/health",
        "docs": "/docs",
        "status": "operational",
    }

# Root endpoint
@app.get("/api")
async def root():
    return {
        "service": "Compliance Vault Pro",
        "owner": "Pleerity Enterprise Ltd",
        "tagline": "AI-Driven Solutions & Compliance",
        "version": "1.0.0",
        "status": "operational"
    }

# Health check
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development")
    }


# Version/build stamp for deployment verification (commit SHA set by CI/CD, e.g. GIT_COMMIT_SHA)
@app.get("/api/version")
async def version_info():
    return {
        "commit_sha": os.getenv("GIT_COMMIT_SHA", os.getenv("BUILD_SHA", "unknown")),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }

# Validation error handler: log request_id + full errors (loc path) for intake submit debugging
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = str(uuid.uuid4())
    errors = exc.errors()
    path = getattr(request, "url", None) and getattr(request.url, "path", "") or ""
    if "intake" in path and "submit" in path:
        logger.warning(
            "Intake validation failed request_id=%s path=%s errors=%s",
            request_id,
            path,
            [(e.get("loc"), e.get("msg"), e.get("type")) for e in errors],
        )
    return JSONResponse(
        status_code=422,
        content={"detail": errors, "request_id": request_id},
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8001,
        reload=os.getenv("ENVIRONMENT") == "development"
    )
