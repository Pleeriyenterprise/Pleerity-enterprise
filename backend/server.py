from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uuid
from contextlib import asynccontextmanager
from database import database
from routes import auth, intake, webhooks, client, admin, documents, assistant, profile, properties, rules, templates, calendar, sms, otp, reports, tenant, webhooks_config, billing, admin_billing, public, admin_orders, orders, client_orders, admin_notifications, admin_services, public_services, blog, admin_services_v2, public_services_v2, orchestration, intake_wizard, admin_intake_schema, admin_pending_payments, analytics, support, admin_canned_responses, knowledge_base, leads, consent, cms, enablement, reporting, team, prompts, document_packs, checkout_validation, marketing, admin_legal_content, talent_pool, partnerships, admin_modules, intake_uploads

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
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.mongodb import MongoDBJobStore

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

scheduler = AsyncIOScheduler(jobstores=jobstores)

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
    run_notification_failure_spike_monitor,
    run_notification_retry_worker,
    run_pending_payment_lifecycle,
)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Compliance Vault Pro API")
    await database.connect()

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
    
    # Configure scheduled jobs
    # Daily reminders at 9:00 AM UTC
    scheduler.add_job(
        run_daily_reminders,
        CronTrigger(hour=9, minute=0),
        id="daily_reminders",
        name="Daily Compliance Reminders",
        replace_existing=True
    )
    
    # Pending verification digest daily at 9:30 AM UTC (counts only, no PII)
    scheduler.add_job(
        run_pending_verification_digest,
        CronTrigger(hour=9, minute=30),
        id="pending_verification_digest",
        name="Pending Verification Digest",
        replace_existing=True
    )
    
    # Monthly digest on the 1st of each month at 10:00 AM UTC
    scheduler.add_job(
        run_monthly_digests,
        CronTrigger(day=1, hour=10, minute=0),
        id="monthly_digest",
        name="Monthly Compliance Digest",
        replace_existing=True
    )
    
    # Compliance status check - runs twice daily at 8:00 AM and 6:00 PM UTC
    # This detects status changes and sends email alerts when status degrades
    scheduler.add_job(
        run_compliance_status_check,
        CronTrigger(hour=8, minute=0),
        id="compliance_check_morning",
        name="Compliance Status Check (Morning)",
        replace_existing=True
    )
    
    scheduler.add_job(
        run_compliance_status_check,
        CronTrigger(hour=18, minute=0),
        id="compliance_check_evening",
        name="Compliance Status Check (Evening)",
        replace_existing=True
    )
    
    # Scheduled reports - runs every hour to check for due reports
    # Reports are sent based on their individual schedule (daily/weekly/monthly)
    scheduler.add_job(
        run_scheduled_reports,
        CronTrigger(minute=0),  # Every hour on the hour
        id="scheduled_reports",
        name="Process Scheduled Reports",
        replace_existing=True
    )
    
    # Daily compliance score snapshots at 2:00 AM UTC
    # Captures score history for trend analysis
    scheduler.add_job(
        run_compliance_score_snapshots,
        CronTrigger(hour=2, minute=0),
        id="compliance_score_snapshots",
        name="Daily Compliance Score Snapshots",
        replace_existing=True
    )
    
    # Expiry rollover: recalc score for properties with due_date in window (daily 00:10 UTC)
    scheduler.add_job(
        run_expiry_rollover_recalc,
        CronTrigger(hour=0, minute=10),
        id="expiry_rollover_recalc",
        name="Expiry Rollover Compliance Recalc",
        replace_existing=True
    )
    
    # Async compliance recalc worker - runs every 15 seconds (Option B)
    scheduler.add_job(
        run_compliance_recalc_worker,
        IntervalTrigger(seconds=15),
        id="compliance_recalc_worker",
        name="Compliance Recalc Worker",
        replace_existing=True
    )
    
    # Compliance recalc SLA monitor - every 5 minutes (stuck jobs + alerts)
    scheduler.add_job(
        run_compliance_recalc_sla_monitor,
        CronTrigger(minute="*/5"),
        id="compliance_recalc_sla_monitor",
        name="Compliance Recalc SLA Monitor",
        replace_existing=True
    )
    
    # Notification failure spike monitor - every 5 minutes
    scheduler.add_job(
        run_notification_failure_spike_monitor,
        CronTrigger(minute="*/5"),
        id="notification_failure_spike_monitor",
        name="Notification Failure Spike Monitor",
        replace_existing=True
    )
    
    # Notification retry worker (outbox) - every minute
    scheduler.add_job(
        run_notification_retry_worker,
        CronTrigger(minute="*"),
        id="notification_retry_worker",
        name="Notification Retry Worker",
        replace_existing=True
    )
    
    # Order delivery processing - runs every 5 minutes
    # Automatically delivers orders in FINALISING status
    scheduler.add_job(
        run_order_delivery_processing,
        CronTrigger(minute="*/5"),  # Every 5 minutes
        id="order_delivery_processing",
        name="Order Delivery Processing",
        replace_existing=True
    )
    
    # SLA monitoring - runs every 15 minutes
    # Sends warnings at 75% SLA, breach notifications at 100%
    scheduler.add_job(
        run_sla_monitoring,
        CronTrigger(minute="*/15"),  # Every 15 minutes
        id="sla_monitoring",
        name="SLA Monitoring",
        replace_existing=True
    )
    
    # Stuck order detection - runs every 30 minutes
    # Detects orders stuck in FINALISING without proper documents
    scheduler.add_job(
        run_stuck_order_detection,
        CronTrigger(minute="*/30"),  # Every 30 minutes
        id="stuck_order_detection",
        name="Stuck Order Detection",
        replace_existing=True
    )
    
    # Queued order processing - runs every 10 minutes
    # Processes queued orders through document generation
    scheduler.add_job(
        run_queued_order_processing,
        CronTrigger(minute="*/10"),  # Every 10 minutes
        id="queued_order_processing",
        name="Queued Order Processing",
        replace_existing=True
    )
    
    # Lead automation jobs
    # Abandoned intake detection - runs every 15 minutes
    scheduler.add_job(
        run_abandoned_intake_detection,
        CronTrigger(minute="*/15"),  # Every 15 minutes
        id="abandoned_intake_detection",
        name="Abandoned Intake Detection",
        replace_existing=True
    )
    
    # Lead follow-up processing - runs every 15 minutes
    scheduler.add_job(
        run_lead_followup_processing,
        CronTrigger(minute="*/15"),  # Every 15 minutes
        id="lead_followup_processing",
        name="Lead Follow-up Processing",
        replace_existing=True
    )
    
    # Pending payment lifecycle - daily at 3:00 AM UTC
    scheduler.add_job(
        run_pending_payment_lifecycle,
        CronTrigger(hour=3, minute=0),
        id="pending_payment_lifecycle",
        name="Pending Payment Lifecycle (abandoned/archived)",
        replace_existing=True
    )
    
    # Lead SLA breach check - runs every hour
    scheduler.add_job(
        run_lead_sla_check,
        CronTrigger(minute=0),  # Every hour on the hour
        id="lead_sla_check",
        name="Lead SLA Breach Check",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Background job scheduler started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Compliance Vault Pro API")
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
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(intake.router)
app.include_router(webhooks.router)
app.include_router(client.router)
app.include_router(admin.router)
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
app.include_router(admin_orders.router)
app.include_router(orders.router)
app.include_router(client_orders.router)
app.include_router(admin_notifications.router)
app.include_router(admin_services.router)
app.include_router(public_services.router)
app.include_router(blog.router)
app.include_router(admin_services_v2.router)
app.include_router(public_services_v2.router)
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
app.include_router(document_packs.router)  # Document Pack Orchestrator
app.include_router(checkout_validation.router)  # Checkout Validation
app.include_router(marketing.router)  # Marketing Website CMS
app.include_router(admin_legal_content.router)  # Legal Content Editor
app.include_router(talent_pool.router)  # Talent Pool
app.include_router(partnerships.router)  # Partnerships
app.include_router(admin_modules.router)  # Public endpoints
app.include_router(admin_modules.router_admin)  # Admin endpoints
app.include_router(intake_uploads.router)  # Intake document uploads

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
