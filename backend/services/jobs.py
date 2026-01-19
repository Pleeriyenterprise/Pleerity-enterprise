"""Background jobs for reminders and digests - Compliance Vault Pro"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta, timezone
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

# Status severity ranking (lower is better)
STATUS_SEVERITY = {
    "GREEN": 0,
    "AMBER": 1,
    "RED": 2
}

def get_status_color(status):
    """Get CSS color for compliance status."""
    return {
        "GREEN": "#22c55e",
        "AMBER": "#f59e0b",
        "RED": "#dc2626"
    }.get(status, "#64748b")

class JobScheduler:
    def __init__(self):
        self.mongo_url = os.environ['MONGO_URL']
        self.db_name = os.environ['DB_NAME']
        self.client = None
        self.db = None
    
    async def connect(self):
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client[self.db_name]
        logger.info("Job scheduler connected to MongoDB")
    
    async def close(self):
        if self.client:
            self.client.close()
    
    async def send_daily_reminders(self):
        """Send daily compliance reminders for expiring requirements."""
        logger.info("Running daily reminder job...")
        
        try:
            # Get all active clients
            clients = await self.db.clients.find(
                {"subscription_status": "ACTIVE"},
                {"_id": 0}
            ).to_list(1000)
            
            reminder_count = 0
            
            for client in clients:
                # Get requirements expiring in next 30 days
                thirty_days_from_now = datetime.now(timezone.utc) + timedelta(days=30)
                
                requirements = await self.db.requirements.find({
                    "client_id": client["client_id"],
                    "status": {"$in": ["PENDING", "EXPIRING_SOON"]}
                }, {"_id": 0}).to_list(100)
                
                expiring_requirements = []
                
                for req in requirements:
                    due_date = datetime.fromisoformat(req["due_date"]) if isinstance(req["due_date"], str) else req["due_date"]
                    days_until_due = (due_date - datetime.now(timezone.utc)).days
                    
                    if 0 <= days_until_due <= 30:
                        expiring_requirements.append({
                            "type": req["description"],
                            "due_date": due_date.strftime("%d %B %Y"),
                            "days_remaining": days_until_due,
                            "status": "URGENT" if days_until_due <= 7 else "WARNING"
                        })
                        
                        # Update requirement status
                        if days_until_due <= 30:
                            await self.db.requirements.update_one(
                                {"requirement_id": req["requirement_id"]},
                                {"$set": {"status": "EXPIRING_SOON"}}
                            )
                
                # Check for overdue
                overdue_requirements = []
                for req in requirements:
                    due_date = datetime.fromisoformat(req["due_date"]) if isinstance(req["due_date"], str) else req["due_date"]
                    if due_date < datetime.now(timezone.utc):
                        overdue_requirements.append({
                            "type": req["description"],
                            "due_date": due_date.strftime("%d %B %Y"),
                            "days_overdue": (datetime.now(timezone.utc) - due_date).days
                        })
                        
                        # Update requirement status
                        await self.db.requirements.update_one(
                            {"requirement_id": req["requirement_id"]},
                            {"$set": {"status": "OVERDUE"}}
                        )
                
                # Send reminder if there are expiring or overdue requirements
                if expiring_requirements or overdue_requirements:
                    await self._send_reminder_email(
                        client,
                        expiring_requirements,
                        overdue_requirements
                    )
                    reminder_count += 1
            
            logger.info(f"Daily reminder job complete. Sent {reminder_count} reminders.")
            return reminder_count
        
        except Exception as e:
            logger.error(f"Daily reminder job error: {e}")
            return 0
    
    async def send_monthly_digests(self):
        """Send monthly compliance digest to all active clients."""
        logger.info("Running monthly digest job...")
        
        try:
            # Get all active clients
            clients = await self.db.clients.find(
                {"subscription_status": "ACTIVE"},
                {"_id": 0}
            ).to_list(1000)
            
            digest_count = 0
            
            for client in clients:
                # Calculate digest period (last 30 days)
                period_end = datetime.now(timezone.utc)
                period_start = period_end - timedelta(days=30)
                
                # Get properties
                properties = await self.db.properties.find(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                ).to_list(100)
                
                # Get requirements summary
                requirements = await self.db.requirements.find(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                ).to_list(1000)
                
                compliant = sum(1 for r in requirements if r["status"] == "COMPLIANT")
                overdue = sum(1 for r in requirements if r["status"] == "OVERDUE")
                expiring = sum(1 for r in requirements if r["status"] == "EXPIRING_SOON")
                
                # Get recent documents uploaded
                recent_documents = await self.db.documents.find({
                    "client_id": client["client_id"],
                    "uploaded_at": {"$gte": period_start.isoformat()}
                }, {"_id": 0}).to_list(100)
                
                digest_content = {
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "properties_count": len(properties),
                    "total_requirements": len(requirements),
                    "compliant": compliant,
                    "overdue": overdue,
                    "expiring_soon": expiring,
                    "documents_uploaded": len(recent_documents)
                }
                
                # Send digest email
                await self._send_digest_email(client, digest_content)
                
                # Log digest
                digest_log = {
                    "digest_id": str(datetime.now(timezone.utc).timestamp()),
                    "client_id": client["client_id"],
                    "digest_period_start": period_start.isoformat(),
                    "digest_period_end": period_end.isoformat(),
                    "content": digest_content,
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                
                await self.db.digest_logs.insert_one(digest_log)
                digest_count += 1
            
            logger.info(f"Monthly digest job complete. Sent {digest_count} digests.")
            return digest_count
        
        except Exception as e:
            logger.error(f"Monthly digest job error: {e}")
            return 0
    
    async def _send_reminder_email(self, client, expiring, overdue):
        """Send reminder email using email service."""
        try:
            # Import here to avoid circular dependency
            from services.email_service import email_service
            from models import EmailTemplateAlias
            
            # In production, this would use a proper reminder template
            # For now, log the reminder
            logger.info(f"Sending reminder to {client['email']}: {len(expiring)} expiring, {len(overdue)} overdue")
            
            # Create audit log
            audit_log = {
                "audit_id": str(datetime.now(timezone.utc).timestamp()),
                "action": "REMINDER_SENT",
                "client_id": client["client_id"],
                "metadata": {
                    "expiring_count": len(expiring),
                    "overdue_count": len(overdue)
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.db.audit_logs.insert_one(audit_log)
        
        except Exception as e:
            logger.error(f"Failed to send reminder email: {e}")
    
    async def _send_digest_email(self, client, content):
        """Send monthly digest email."""
        try:
            # Import here to avoid circular dependency
            from services.email_service import email_service
            from models import EmailTemplateAlias
            
            # In production, this would use the monthly-digest template
            logger.info(f"Sending digest to {client['email']}: {content['total_requirements']} requirements")
            
            # Create audit log
            audit_log = {
                "audit_id": str(datetime.now(timezone.utc).timestamp()),
                "action": "DIGEST_SENT",
                "client_id": client["client_id"],
                "metadata": content,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.db.audit_logs.insert_one(audit_log)
        
        except Exception as e:
            logger.error(f"Failed to send digest email: {e}")

async def run_daily_job():
    """Run daily reminder job."""
    scheduler = JobScheduler()
    await scheduler.connect()
    await scheduler.send_daily_reminders()
    await scheduler.close()

async def run_monthly_job():
    """Run monthly digest job."""
    scheduler = JobScheduler()
    await scheduler.connect()
    await scheduler.send_monthly_digests()
    await scheduler.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "daily":
            asyncio.run(run_daily_job())
        elif sys.argv[1] == "monthly":
            asyncio.run(run_monthly_job())
        else:
            print("Usage: python jobs.py [daily|monthly]")
    else:
        print("Usage: python jobs.py [daily|monthly]")
