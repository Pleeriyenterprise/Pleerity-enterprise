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
    
    async def check_compliance_status_changes(self):
        """Check for compliance status changes and send alerts.
        
        This job:
        1. Evaluates current compliance status for all properties
        2. Compares with stored previous status
        3. Sends email alerts when status degrades (GREEN→AMBER, AMBER→RED, GREEN→RED)
        4. Updates the stored status
        5. Respects user notification preferences
        """
        logger.info("Running compliance status change check...")
        
        try:
            from services.email_service import email_service
            
            # Get all active clients
            clients = await self.db.clients.find(
                {"subscription_status": "ACTIVE"},
                {"_id": 0}
            ).to_list(1000)
            
            alert_count = 0
            
            for client in clients:
                # Check notification preferences
                prefs = await self.db.notification_preferences.find_one(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                )
                
                # Default to enabled if no preferences set
                status_alerts_enabled = prefs.get("status_change_alerts", True) if prefs else True
                
                if not status_alerts_enabled:
                    logger.info(f"Skipping compliance alerts for {client['email']} - disabled in preferences")
                    continue
                
                # Get all properties for this client
                properties = await self.db.properties.find(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                ).to_list(100)
                
                properties_with_changes = []
                
                for prop in properties:
                    # Get requirements for this property
                    requirements = await self.db.requirements.find(
                        {"property_id": prop["property_id"]},
                        {"_id": 0}
                    ).to_list(100)
                    
                    # Calculate current compliance status based on requirements
                    new_status = self._calculate_property_compliance(requirements)
                    old_status = prop.get("compliance_status", "GREEN")
                    previous_notified_status = prop.get("last_notified_status", old_status)
                    
                    # Check if status has degraded since last notification
                    old_severity = STATUS_SEVERITY.get(previous_notified_status, 0)
                    new_severity = STATUS_SEVERITY.get(new_status, 0)
                    
                    # Only alert on degradation (getting worse)
                    if new_severity > old_severity:
                        # Determine reason for change
                        reason = self._get_status_change_reason(requirements, new_status)
                        
                        properties_with_changes.append({
                            "property_id": prop["property_id"],
                            "address": f"{prop.get('address_line_1', 'Unknown')}, {prop.get('city', '')}",
                            "previous_status": previous_notified_status,
                            "new_status": new_status,
                            "reason": reason
                        })
                        
                        # Update property with new status and last notified status
                        await self.db.properties.update_one(
                            {"property_id": prop["property_id"]},
                            {"$set": {
                                "compliance_status": new_status,
                                "last_notified_status": new_status,
                                "status_changed_at": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                    elif new_status != old_status:
                        # Status changed but not degraded - just update the status
                        await self.db.properties.update_one(
                            {"property_id": prop["property_id"]},
                            {"$set": {
                                "compliance_status": new_status,
                                "status_changed_at": datetime.now(timezone.utc).isoformat()
                            }}
                        )
                
                # Send alert if there are properties with degraded status
                if properties_with_changes:
                    frontend_url = os.getenv("FRONTEND_URL", "https://property-vault-10.preview.emergentagent.com")
                    
                    await email_service.send_compliance_alert_email(
                        recipient=client["email"],
                        client_name=client["full_name"],
                        affected_properties=properties_with_changes,
                        portal_link=f"{frontend_url}/app/dashboard",
                        client_id=client["client_id"]
                    )
                    
                    # Audit log
                    audit_log = {
                        "audit_id": str(datetime.now(timezone.utc).timestamp()),
                        "action": "COMPLIANCE_ALERT_SENT",
                        "client_id": client["client_id"],
                        "metadata": {
                            "properties_affected": len(properties_with_changes),
                            "changes": properties_with_changes
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    await self.db.audit_logs.insert_one(audit_log)
                    
                    alert_count += 1
                    logger.info(f"Sent compliance alert to {client['email']} for {len(properties_with_changes)} properties")
            
            logger.info(f"Compliance status check complete. Sent {alert_count} alerts.")
            return alert_count
        
        except Exception as e:
            logger.error(f"Compliance status check error: {e}")
            return 0
    
    def _calculate_property_compliance(self, requirements):
        """Calculate overall compliance status for a property based on its requirements."""
        if not requirements:
            return "GREEN"  # No requirements = compliant
        
        now = datetime.now(timezone.utc)
        has_overdue = False
        has_expiring_soon = False
        
        for req in requirements:
            status = req.get("status", "PENDING")
            
            if status in ["OVERDUE", "EXPIRED"]:
                has_overdue = True
            elif status == "EXPIRING_SOON":
                has_expiring_soon = True
            elif status == "PENDING":
                # Check due date
                due_date_str = req.get("due_date")
                if due_date_str:
                    try:
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')) if isinstance(due_date_str, str) else due_date_str
                        days_until_due = (due_date - now).days
                        
                        if days_until_due < 0:
                            has_overdue = True
                        elif days_until_due <= 30:
                            has_expiring_soon = True
                    except Exception:
                        pass
        
        if has_overdue:
            return "RED"
        elif has_expiring_soon:
            return "AMBER"
        else:
            return "GREEN"
    
    def _get_status_change_reason(self, requirements, new_status):
        """Generate a human-readable reason for the status change."""
        if new_status == "RED":
            overdue_types = []
            for req in requirements:
                if req.get("status") in ["OVERDUE", "EXPIRED"]:
                    overdue_types.append(req.get("description", req.get("requirement_type", "Certificate")))
            
            if overdue_types:
                return f"Overdue: {', '.join(overdue_types[:2])}" + ("..." if len(overdue_types) > 2 else "")
            return "Requirements overdue"
        
        elif new_status == "AMBER":
            expiring_types = []
            for req in requirements:
                if req.get("status") == "EXPIRING_SOON":
                    expiring_types.append(req.get("description", req.get("requirement_type", "Certificate")))
            
            if expiring_types:
                return f"Expiring soon: {', '.join(expiring_types[:2])}" + ("..." if len(expiring_types) > 2 else "")
            return "Requirements expiring soon"
        
        return "Status updated"

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

async def run_compliance_check():
    """Run compliance status change check."""
    scheduler = JobScheduler()
    await scheduler.connect()
    count = await scheduler.check_compliance_status_changes()
    await scheduler.close()
    return count

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "daily":
            asyncio.run(run_daily_job())
        elif sys.argv[1] == "monthly":
            asyncio.run(run_monthly_job())
        elif sys.argv[1] == "compliance":
            asyncio.run(run_compliance_check())
        else:
            print("Usage: python jobs.py [daily|monthly|compliance]")
    else:
        print("Usage: python jobs.py [daily|monthly|compliance]")
