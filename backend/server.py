from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from database import database
from routes import auth, intake, webhooks, client, admin, documents, assistant, profile, properties, rules, templates, calendar, sms, reports, tenant, webhooks_config
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
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

async def run_daily_reminders():
    """Scheduled job: Send daily compliance reminders."""
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        count = await job_scheduler.send_daily_reminders()
        await job_scheduler.close()
        logger.info(f"Daily reminders job completed: {count} reminders sent")
    except Exception as e:
        logger.error(f"Daily reminders job failed: {e}")

async def run_monthly_digests():
    """Scheduled job: Send monthly compliance digests."""
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        count = await job_scheduler.send_monthly_digests()
        await job_scheduler.close()
        logger.info(f"Monthly digest job completed: {count} digests sent")
    except Exception as e:
        logger.error(f"Monthly digest job failed: {e}")

async def run_compliance_status_check():
    """Scheduled job: Check for compliance status changes and send alerts."""
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        count = await job_scheduler.check_compliance_status_changes()
        await job_scheduler.close()
        logger.info(f"Compliance status check completed: {count} alerts sent")
    except Exception as e:
        logger.error(f"Compliance status check failed: {e}")


async def run_scheduled_reports():
    """Scheduled job: Process and send scheduled reports."""
    try:
        from services.jobs import run_scheduled_reports as process_reports
        count = await process_reports()
        logger.info(f"Scheduled reports job completed: {count} reports sent")
    except Exception as e:
        logger.error(f"Scheduled reports job failed: {e}")


async def run_compliance_score_snapshots():
    """Scheduled job: Capture daily compliance score snapshots for all clients."""
    try:
        from services.compliance_trending import capture_all_client_snapshots
        result = await capture_all_client_snapshots()
        logger.info(f"Compliance score snapshots completed: {result['success_count']}/{result['total_clients']} clients")
    except Exception as e:
        logger.error(f"Compliance score snapshots job failed: {e}")

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Compliance Vault Pro API")
    await database.connect()
    
    # Configure scheduled jobs
    # Daily reminders at 9:00 AM UTC
    scheduler.add_job(
        run_daily_reminders,
        CronTrigger(hour=9, minute=0),
        id="daily_reminders",
        name="Daily Compliance Reminders",
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
app.include_router(reports.router)
app.include_router(tenant.router)
app.include_router(webhooks_config.router)

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
