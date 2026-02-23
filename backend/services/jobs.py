"""Background jobs for reminders and digests - Compliance Vault Pro"""
import asyncio
import json
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta, timezone
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from utils.expiry_utils import get_effective_expiry_date, get_computed_status, is_included_for_calendar

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
        """Send daily compliance reminders for expiring requirements.
        Respects user notification preferences.
        
        IMPORTANT: Only runs for clients with ENABLED entitlement.
        Clients with LIMITED or DISABLED entitlement do not receive reminders.
        """
        logger.info("Running daily reminder job...")
        
        try:
            # Get all active clients with ENABLED entitlement
            # Per spec: no background jobs when entitlement is DISABLED
            clients = await self.db.clients.find(
                {
                    "subscription_status": "ACTIVE",
                    "entitlement_status": {"$in": ["ENABLED", None]}  # None for legacy compatibility
                },
                {"_id": 0}
            ).to_list(1000)
            
            reminder_count = 0
            
            for client in clients:
                # Check notification preferences
                prefs = await self.db.notification_preferences.find_one(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                )
                
                # Default to enabled if no preferences set
                reminders_enabled = prefs.get("expiry_reminders", True) if prefs else True
                reminder_days = prefs.get("reminder_days_before", 30) if prefs else 30
                daily_reminder_enabled = prefs.get("daily_reminder_enabled", True) if prefs else True
                
                if not reminders_enabled:
                    logger.info(f"Skipping reminders for {client['email']} - disabled in preferences")
                    continue
                if not daily_reminder_enabled:
                    logger.info(f"Skipping reminders for {client['email']} - daily reminder disabled in preferences")
                    continue
                if self._is_in_quiet_hours(prefs):
                    logger.info(f"Skipping reminders for {client['email']} - within quiet hours")
                    continue
                
                # Get all requirements for client; use effective expiry (confirmed else extracted else due_date); exclude NOT_REQUIRED
                requirements = await self.db.requirements.find(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                ).to_list(500)

                expiring_requirements = []
                overdue_requirements = []
                reminder_refs = []  # For message_logs: client_id on log; refs list here
                properties_status_changed = set()
                now_utc = datetime.now(timezone.utc)

                for req in requirements:
                    if not is_included_for_calendar(req):
                        continue
                    due_date = get_effective_expiry_date(req)
                    if due_date is None:
                        continue
                    days_until_due = (due_date - now_utc).days

                    if days_until_due < 0:
                        overdue_requirements.append({
                            "type": req.get("description", req.get("requirement_type", "Certificate")),
                            "due_date": due_date.strftime("%d %B %Y"),
                            "days_overdue": -days_until_due
                        })
                        reminder_refs.append({
                            "property_id": req.get("property_id"),
                            "requirement_type": req.get("requirement_type", ""),
                            "due_date": due_date.strftime("%Y-%m-%d"),
                        })
                        await self.db.requirements.update_one(
                            {"requirement_id": req["requirement_id"]},
                            {"$set": {"status": "OVERDUE"}}
                        )
                        properties_status_changed.add(req.get("property_id"))
                    elif 0 <= days_until_due <= reminder_days:
                        expiring_requirements.append({
                            "type": req.get("description", req.get("requirement_type", "Certificate")),
                            "due_date": due_date.strftime("%d %B %Y"),
                            "days_remaining": days_until_due,
                            "status": "URGENT" if days_until_due <= 7 else "WARNING"
                        })
                        reminder_refs.append({
                            "property_id": req.get("property_id"),
                            "requirement_type": req.get("requirement_type", ""),
                            "due_date": due_date.strftime("%Y-%m-%d"),
                        })
                        await self.db.requirements.update_one(
                            {"requirement_id": req["requirement_id"]},
                            {"$set": {"status": "EXPIRING_SOON"}}
                        )
                        properties_status_changed.add(req.get("property_id"))
                
                # Enqueue compliance recalc for properties whose requirement status changed
                if properties_status_changed:
                    from services.compliance_recalc_queue import enqueue_compliance_recalc
                    from services.compliance_recalc_queue import TRIGGER_EXPIRY_JOB, ACTOR_SYSTEM
                    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    for property_id in properties_status_changed:
                        if not property_id:
                            continue
                        await enqueue_compliance_recalc(
                            property_id=property_id,
                            client_id=client["client_id"],
                            trigger_reason=TRIGGER_EXPIRY_JOB,
                            actor_type=ACTOR_SYSTEM,
                            actor_id=None,
                            correlation_id=f"REMINDER_JOB:{property_id}:{date_str}",
                        )
                
                # Send reminder if there are expiring or overdue requirements
                if expiring_requirements or overdue_requirements:
                    reminder_recipients = await self._resolve_reminder_recipients(client)
                    for recipient_email in reminder_recipients:
                        await self._send_reminder_email(
                            client,
                            expiring_requirements,
                            overdue_requirements,
                            recipient_email=recipient_email,
                            reminder_refs=reminder_refs,
                        )
                    if reminder_recipients:
                        reminder_count += 1
                    # Professional only: runtime plan gating before SMS (survives downgrade/cancel)
                    from services.plan_registry import plan_registry
                    sms_allowed, _sms_err, _sms_details = await plan_registry.enforce_feature(
                        client["client_id"], "sms_reminders"
                    )
                    if sms_allowed:
                        # Only send SMS for urgent (overdue) when sms_urgent_alerts_only is True
                        sms_urgent_only = prefs.get("sms_urgent_alerts_only", True) if prefs else True
                        if sms_urgent_only and not overdue_requirements:
                            logger.info("Skipping SMS reminder for client %s - sms_urgent_alerts_only and no overdue items", client["client_id"])
                        else:
                            sms_recipients = await self._resolve_reminder_sms_recipients(client, prefs)
                            for recipient_phone in sms_recipients:
                                await self._maybe_send_reminder_sms(
                                    client,
                                    prefs,
                                    expiring_requirements,
                                    overdue_requirements,
                                    recipient_phone=recipient_phone,
                                    reminder_refs=reminder_refs,
                                )
                    else:
                        logger.info(
                            "Skipping SMS reminder for client %s - plan/subscription does not allow sms_reminders",
                            client["client_id"],
                        )
            
            logger.info(f"Daily reminder job complete. Sent {reminder_count} reminders.")
            return reminder_count
        
        except Exception as e:
            logger.error(f"Daily reminder job error: {e}")
            return 0
    
    async def send_monthly_digests(self):
        """Send monthly compliance digest to all active clients.
        Respects user notification preferences.
        
        IMPORTANT: Only runs for clients with ENABLED entitlement.
        Clients with LIMITED or DISABLED entitlement do not receive digests.
        """
        logger.info("Running monthly digest job...")
        
        try:
            # Get all active clients with ENABLED entitlement
            # Per spec: no background jobs when entitlement is DISABLED
            clients = await self.db.clients.find(
                {
                    "subscription_status": "ACTIVE",
                    "entitlement_status": {"$in": ["ENABLED", None]}  # None for legacy compatibility
                },
                {"_id": 0}
            ).to_list(1000)
            
            digest_count = 0
            
            for client in clients:
                # Check notification preferences
                prefs = await self.db.notification_preferences.find_one(
                    {"client_id": client["client_id"]},
                    {"_id": 0}
                )
                
                # Default to enabled if no preferences set
                monthly_digest_enabled = prefs.get("monthly_digest", True) if prefs else True
                
                if not monthly_digest_enabled:
                    logger.info(f"Skipping monthly digest for {client['email']} - disabled in preferences")
                    continue
                if self._is_in_quiet_hours(prefs):
                    logger.info(f"Skipping monthly digest for {client['email']} - within quiet hours")
                    continue
                
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
                # Section flags from preferences (default True for backward compatibility)
                digest_content["include_compliance_summary"] = prefs.get("digest_compliance_summary", True) if prefs else True
                digest_content["include_action_items"] = prefs.get("digest_action_items", True) if prefs else True
                digest_content["include_upcoming_expiries"] = prefs.get("digest_upcoming_expiries", True) if prefs else True
                digest_content["include_property_breakdown"] = prefs.get("digest_property_breakdown", True) if prefs else True
                digest_content["include_recent_documents"] = prefs.get("digest_recent_documents", True) if prefs else True
                digest_content["include_recommendations"] = prefs.get("digest_recommendations", True) if prefs else True
                digest_content["include_audit_summary"] = prefs.get("digest_audit_summary", False) if prefs else False
                
                # Send digest email (skip and audit if no recipient)
                sent = await self._send_digest_email(client, digest_content)
                if not sent:
                    continue
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
    
    async def _resolve_reminder_recipients(self, client) -> list:
        """
        Resolve reminder email recipients from client + properties.
        Uses property send_reminders_to (LANDLORD / AGENT / BOTH) and agent_email.
        Returns list of distinct email addresses to send the daily reminder to.
        """
        client_email = (client.get("email") or client.get("contact_email") or "").strip()
        properties = await self.db.properties.find(
            {"client_id": client["client_id"]},
            {"_id": 0, "send_reminders_to": 1, "agent_email": 1}
        ).to_list(500)
        send_to_landlord = False
        agent_emails = set()
        for prop in properties:
            to_whom = (prop.get("send_reminders_to") or "LANDLORD").upper()
            if to_whom in ("LANDLORD", "BOTH"):
                send_to_landlord = True
            if to_whom in ("AGENT", "BOTH"):
                ae = (prop.get("agent_email") or "").strip()
                if ae:
                    agent_emails.add(ae)
        recipients = []
        if send_to_landlord and client_email:
            recipients.append(client_email)
        for ae in agent_emails:
            if ae and ae not in recipients:
                recipients.append(ae)
        if not recipients and client_email:
            recipients = [client_email]
        return recipients

    async def _resolve_reminder_sms_recipients(self, client, prefs) -> list:
        """
        Resolve SMS reminder recipients: client phone + agent phones when send_reminders_to is AGENT/BOTH.
        Returns list of phone numbers (only if SMS is enabled in prefs for client; agent phones included by property setting).
        """
        phones = []
        client_phone = (prefs.get("sms_phone_number") if prefs else None) or client.get("sms_phone_number") or ""
        client_phone = (client_phone or "").strip()
        if prefs and prefs.get("sms_enabled") and client_phone:
            phones.append(client_phone)
        properties = await self.db.properties.find(
            {"client_id": client["client_id"]},
            {"_id": 0, "send_reminders_to": 1, "agent_phone": 1}
        ).to_list(500)
        for prop in properties:
            to_whom = (prop.get("send_reminders_to") or "LANDLORD").upper()
            if to_whom in ("AGENT", "BOTH"):
                ap = (prop.get("agent_phone") or "").strip()
                if ap and ap not in phones:
                    phones.append(ap)
        return phones

    async def _send_reminder_email(self, client, expiring, overdue, recipient_email=None, reminder_refs=None):
        """Send reminder email via NotificationOrchestrator. If recipient_email is set, send to that address (agent); otherwise to client email. Writes message_log with event_type REMINDER and reminder_refs in metadata."""
        try:
            from services.notification_orchestrator import notification_orchestrator
            from services.webhook_service import fire_reminder_sent
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            to_addr = (recipient_email or client.get("email") or client.get("contact_email") or "").strip()
            if not to_addr:
                return
            key_suffix = to_addr.replace("@", "_at_") if recipient_email else "client"
            idempotency_key = f"{client['client_id']}_COMPLIANCE_EXPIRY_REMINDER_{date_key}_{key_suffix}"
            portal_link = os.environ.get("FRONTEND_URL", "https://app.pleerity.co.uk") + "/app/dashboard"
            context = {
                "client_name": client.get("full_name", "Valued Customer"),
                "expiring_count": len(expiring),
                "overdue_count": len(overdue),
                "portal_link": portal_link,
            }
            if recipient_email:
                context["recipient"] = recipient_email
            if reminder_refs is not None:
                context["reminder_refs"] = json.dumps(reminder_refs)
            await notification_orchestrator.send(
                template_key="COMPLIANCE_EXPIRY_REMINDER",
                client_id=client["client_id"],
                context=context,
                idempotency_key=idempotency_key,
                event_type="REMINDER",
            )
            logger.info(f"Sending reminder to {to_addr}: {len(expiring)} expiring, {len(overdue)} overdue")
            try:
                await fire_reminder_sent(client_id=client["client_id"], recipient=to_addr, expiring_count=len(expiring), overdue_count=len(overdue))
            except Exception as webhook_err:
                logger.error(f"Webhook error for reminder: {webhook_err}")
            audit_log = {
                "audit_id": str(datetime.now(timezone.utc).timestamp()),
                "action": "REMINDER_SENT",
                "client_id": client["client_id"],
                "metadata": {"expiring_count": len(expiring), "overdue_count": len(overdue), "recipient": to_addr},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.db.audit_logs.insert_one(audit_log)
        except Exception as e:
            logger.error(f"Failed to send reminder email: {e}")

    async def _maybe_send_reminder_sms(self, client, prefs, expiring, overdue, recipient_phone=None, reminder_refs=None):
        """Send SMS reminder via NotificationOrchestrator (plan-gated, 24h throttle inside orchestrator). Writes message_log with event_type REMINDER and reminder_refs in metadata."""
        try:
            from services.notification_orchestrator import notification_orchestrator
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            key_suffix = (recipient_phone or "").replace("+", "").replace(" ", "")[:20] if recipient_phone else "client"
            idempotency_key = f"{client['client_id']}_COMPLIANCE_EXPIRY_REMINDER_SMS_{date_key}_{key_suffix}"
            portal_link = os.environ.get("PORTAL_BASE_URL", "https://app.pleerity.co.uk") + "/app/dashboard"
            total = len(expiring) + len(overdue)
            context = {"count": total, "portal_link": portal_link}
            if recipient_phone:
                context["recipient"] = recipient_phone
            if reminder_refs is not None:
                context["reminder_refs"] = json.dumps(reminder_refs)
            await notification_orchestrator.send(
                template_key="COMPLIANCE_EXPIRY_REMINDER_SMS",
                client_id=client["client_id"],
                context=context,
                idempotency_key=idempotency_key,
                event_type="REMINDER",
            )
        except Exception as e:
            logger.warning("SMS reminder error for client %s (non-fatal): %s", client.get("client_id"), e)
    
    async def _send_digest_email(self, client, content):
        """Send monthly digest email via NotificationOrchestrator. Returns True if sent, False if skipped."""
        try:
            from services.notification_orchestrator import notification_orchestrator
            from services.webhook_service import fire_digest_sent
            from utils.audit import create_audit_log
            from models import AuditAction

            recipient = (client.get("email") or client.get("contact_email") or "").strip()
            if not recipient:
                await create_audit_log(
                    action=AuditAction.EMAIL_SKIPPED_NO_RECIPIENT,
                    client_id=client["client_id"],
                    metadata={
                        "template_key": "MONTHLY_DIGEST",
                        "properties_count": content.get("properties_count", 0),
                        "total_requirements": content.get("total_requirements", 0),
                        "compliant": content.get("compliant", 0),
                        "overdue": content.get("overdue", 0),
                        "expiring_soon": content.get("expiring_soon", 0),
                        "documents_uploaded": content.get("documents_uploaded", 0),
                    },
                )
                logger.info(f"Digest skipped for client {client['client_id']}: no email or contact_email")
                return False

            period_end = (content.get("period_end") or "").replace("T", " ")[:10]
            idempotency_key = f"{client['client_id']}_MONTHLY_DIGEST_{period_end}"
            template_model = {
                "period_start": content.get("period_start", ""),
                "period_end": content.get("period_end", ""),
                "properties_count": content.get("properties_count", 0),
                "total_requirements": content.get("total_requirements", 0),
                "compliant": content.get("compliant", 0),
                "overdue": content.get("overdue", 0),
                "expiring_soon": content.get("expiring_soon", 0),
                "documents_uploaded": content.get("documents_uploaded", 0),
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance",
                "subject": "Monthly Compliance Digest",
            }
            for key in ("include_compliance_summary", "include_action_items", "include_upcoming_expiries",
                       "include_property_breakdown", "include_recent_documents", "include_recommendations", "include_audit_summary"):
                if key in content:
                    template_model[key] = content[key]
            from services.notification_orchestrator import notification_orchestrator
            result = await notification_orchestrator.send(
                template_key="MONTHLY_DIGEST",
                client_id=client["client_id"],
                context=template_model,
                idempotency_key=idempotency_key,
                event_type="monthly_digest",
            )
            if result.outcome not in ("sent", "duplicate_ignored"):
                return False
            logger.info(f"Digest sent to {recipient}: {content.get('total_requirements', 0)} requirements")
            try:
                await fire_digest_sent(
                    client_id=client["client_id"],
                    digest_type="monthly",
                    recipients=[recipient],
                    properties_count=content.get("properties_count", 0),
                    requirements_summary={
                        "total": content.get("total_requirements", 0),
                        "compliant": content.get("compliant", 0),
                        "overdue": content.get("overdue", 0),
                        "expiring_soon": content.get("expiring_soon", 0),
                    },
                )
            except Exception as webhook_err:
                logger.error(f"Webhook error for digest: {webhook_err}")
            return True
        except Exception as e:
            logger.error(f"Failed to send digest email: {e}")
            return False
    
    async def send_pending_verification_digest(self):
        """Send daily summary of documents with status UPLOADED (counts only, no PII) to OWNER/ADMIN via orchestrator."""
        logger.info("Running pending verification digest job...")
        try:
            from services.notification_orchestrator import notification_orchestrator
            from models import AuditAction, UserRole, UserStatus
            from utils.audit import create_audit_log

            count_pending = await self.db.documents.count_documents({"status": "UPLOADED"})
            cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            count_older_24h = await self.db.documents.count_documents({
                "status": "UPLOADED",
                "uploaded_at": {"$lte": cutoff_24h}
            })
            admins = await self.db.portal_users.find(
                {
                    "role": {"$in": [UserRole.ROLE_OWNER.value, UserRole.ROLE_ADMIN.value]},
                    "status": UserStatus.ACTIVE.value,
                },
                {"_id": 0, "auth_email": 1}
            ).to_list(100)

            recipient_emails = [a["auth_email"] for a in admins if a.get("auth_email")]
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sent = 0
            for email in recipient_emails:
                try:
                    result = await notification_orchestrator.send(
                        template_key="PENDING_VERIFICATION_DIGEST",
                        client_id=None,
                        context={
                            "recipient": email,
                            "count_pending": count_pending,
                            "count_older_24h": count_older_24h,
                            "company_name": "Pleerity Enterprise Ltd",
                            "tagline": "AI-Driven Solutions & Compliance",
                            "subject": "Pending verification digest",
                        },
                        idempotency_key=f"PENDING_VERIFICATION_DIGEST_{date_key}_{email}",
                        event_type="pending_verification_digest",
                    )
                    if result.outcome in ("sent", "duplicate_ignored"):
                        sent += 1
                except Exception as e:
                    logger.warning(f"Pending verification digest send failed to {email}: {e}")

            await create_audit_log(
                action=AuditAction.PENDING_VERIFICATION_DIGEST_SENT,
                actor_id="system",
                metadata={
                    "recipient_count": sent,
                    "count_pending": count_pending,
                    "count_older_24h": count_older_24h,
                },
            )
            logger.info(f"Pending verification digest sent to {sent} recipients (count_pending={count_pending}, count_older_24h={count_older_24h})")
            return sent
        except Exception as e:
            logger.error(f"Pending verification digest job error: {e}")
            return 0

    async def check_compliance_status_changes(self):
        """Check for compliance status changes and send alerts.
        
        This job:
        1. Evaluates current compliance status for all properties
        2. Compares with stored previous status
        3. Sends email alerts when status degrades (GREEN→AMBER, AMBER→RED, GREEN→RED)
        4. Fires webhooks for status changes
        5. Updates the stored status
        6. Respects user notification preferences
        """
        logger.info("Running compliance status change check...")
        
        try:
            from services.webhook_service import fire_compliance_status_changed
            
            # Get all active clients with ENABLED entitlement
            # Per spec: no background jobs when entitlement is DISABLED
            clients = await self.db.clients.find(
                {
                    "subscription_status": "ACTIVE",
                    "entitlement_status": {"$in": ["ENABLED", None]}  # None for legacy compatibility
                },
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
                
                if self._is_in_quiet_hours(prefs):
                    logger.info(f"Skipping compliance alert for {client['email']} - within quiet hours")
                    status_alerts_enabled = False  # skip send for this client
                
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
                    
                    # Check if status has changed at all
                    if new_status != old_status:
                        # Determine reason for change
                        reason = self._get_status_change_reason(requirements, new_status)
                        property_address = f"{prop.get('address_line_1', 'Unknown')}, {prop.get('city', '')}"
                        
                        # Fire webhook for ANY status change (not just degradation)
                        try:
                            await fire_compliance_status_changed(
                                client_id=client["client_id"],
                                property_id=prop["property_id"],
                                property_address=property_address,
                                old_status=old_status,
                                new_status=new_status,
                                reason=reason
                            )
                        except Exception as webhook_err:
                            logger.error(f"Webhook error for property {prop['property_id']}: {webhook_err}")
                        
                        # Check if status has degraded since last notification
                        old_severity = STATUS_SEVERITY.get(previous_notified_status, 0)
                        new_severity = STATUS_SEVERITY.get(new_status, 0)
                        
                        # Only add to email alert on degradation (getting worse)
                        if new_severity > old_severity:
                            properties_with_changes.append({
                                "property_id": prop["property_id"],
                                "address": property_address,
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
                        else:
                            # Status changed but not degraded - just update the status
                            await self.db.properties.update_one(
                                {"property_id": prop["property_id"]},
                                {"$set": {
                                    "compliance_status": new_status,
                                    "status_changed_at": datetime.now(timezone.utc).isoformat()
                                }}
                            )
                
                # Send email alert via orchestrator if there are properties with degraded status
                if properties_with_changes and status_alerts_enabled:
                    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
                    from services.notification_orchestrator import notification_orchestrator
                    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    ids_hash = "_".join(sorted(p.get("property_id", "") for p in properties_with_changes))[:32]
                    idempotency_key = f"{client['client_id']}_COMPLIANCE_ALERT_{date_key}_{ids_hash}"
                    await notification_orchestrator.send(
                        template_key="COMPLIANCE_ALERT",
                        client_id=client["client_id"],
                        context={
                            "client_name": client.get("full_name", "Valued Customer"),
                            "affected_properties": properties_with_changes,
                            "portal_link": f"{frontend_url}/app/dashboard",
                        },
                        idempotency_key=idempotency_key,
                        event_type="compliance_status_changed",
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
                elif not status_alerts_enabled and properties_with_changes:
                    logger.info(f"Skipping email alert for {client['email']} - disabled in preferences (webhooks still fired)")
            
            logger.info(f"Compliance status check complete. Sent {alert_count} email alerts.")
            return alert_count
        
        except Exception as e:
            logger.error(f"Compliance status check error: {e}")
            return 0
    
    def _is_in_quiet_hours(self, prefs) -> bool:
        """True if quiet hours are enabled and current UTC time is within the window (e.g. 22:00-08:00)."""
        if not prefs or not prefs.get("quiet_hours_enabled"):
            return False
        try:
            start_str = (prefs.get("quiet_hours_start") or "22:00").strip()
            end_str = (prefs.get("quiet_hours_end") or "08:00").strip()
            start_parts = start_str.split(":")
            end_parts = end_str.split(":")
            start_min = int(start_parts[0]) * 60 + (int(start_parts[1]) if len(start_parts) > 1 else 0)
            end_min = int(end_parts[0]) * 60 + (int(end_parts[1]) if len(end_parts) > 1 else 0)
            now = datetime.now(timezone.utc)
            now_min = now.hour * 60 + now.minute
            # Window crosses midnight (e.g. 22:00-08:00): in window if now_min >= start_min or now_min < end_min
            if start_min > end_min:
                return now_min >= start_min or now_min < end_min
            return start_min <= now_min < end_min
        except (ValueError, IndexError, TypeError):
            return False
    
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

    async def send_renewal_reminders(self):
        """Send renewal reminders 7 days before subscription renewal.
        
        IMPORTANT: Only runs for clients with ENABLED entitlement.
        Per spec: no background jobs when entitlement is DISABLED.
        """
        logger.info("Running renewal reminder job...")
        
        try:
            from services.plan_registry import plan_registry
            
            now = datetime.now(timezone.utc)
            reminder_window = now + timedelta(days=7)
            
            # Get billing records with renewals in the next 7 days
            billings = await self.db.client_billing.find(
                {
                    "subscription_status": {"$in": ["ACTIVE", "TRIALING"]},
                    "entitlement_status": "ENABLED",
                    "current_period_end": {
                        "$gte": now,
                        "$lte": reminder_window
                    },
                    "cancel_at_period_end": {"$ne": True},  # Don't remind if already canceling
                    "renewal_reminder_sent": {"$ne": True}  # Don't send duplicate reminders
                },
                {"_id": 0}
            ).to_list(500)
            
            reminder_count = 0
            
            for billing in billings:
                try:
                    client_id = billing.get("client_id")
                    
                    # Get client info
                    client = await self.db.clients.find_one(
                        {"client_id": client_id},
                        {"_id": 0, "contact_email": 1, "contact_name": 1}
                    )
                    
                    if not client or not client.get("contact_email"):
                        continue
                    
                    # Check notification preferences
                    prefs = await self.db.notification_preferences.find_one(
                        {"client_id": client_id},
                        {"_id": 0}
                    )
                    
                    # Default to enabled if no preferences set
                    renewal_reminders_enabled = prefs.get("renewal_reminders", True) if prefs else True
                    
                    if not renewal_reminders_enabled:
                        logger.info(f"Skipping renewal reminder for {client_id} - disabled in preferences")
                        continue
                    
                    # Get plan info
                    plan_code = billing.get("current_plan_code", "PLAN_1_SOLO")
                    plan_def = plan_registry.get_plan_by_code_string(plan_code)
                    
                    renewal_date = billing.get("current_period_end")
                    if isinstance(renewal_date, datetime):
                        renewal_date_str = renewal_date.strftime("%B %d, %Y")
                    else:
                        renewal_date_str = str(renewal_date)[:10] if renewal_date else "soon"
                    
                    amount = f"£{plan_def.get('monthly_price', 0):.2f}"
                    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
                    
                    # Send renewal reminder via orchestrator
                    period_end = billing.get("current_period_end")
                    period_str = period_end.strftime("%Y-%m-%d") if isinstance(period_end, datetime) else str(period_end or "")[:10]
                    idempotency_key = f"{client_id}_RENEWAL_REMINDER_{period_str}"
                    from services.notification_orchestrator import notification_orchestrator
                    await notification_orchestrator.send(
                        template_key="RENEWAL_REMINDER",
                        client_id=client_id,
                        context={
                            "client_name": client.get("contact_name", "Valued Customer"),
                            "plan_name": plan_def.get("name", plan_code) if plan_def else plan_code,
                            "renewal_date": renewal_date_str,
                            "amount": amount,
                            "billing_portal_link": f"{frontend_url}/app/billing",
                        },
                        idempotency_key=idempotency_key,
                        event_type="renewal_reminder",
                    )
                    # Mark reminder as sent to prevent duplicates
                    await self.db.client_billing.update_one(
                        {"client_id": client_id},
                        {"$set": {"renewal_reminder_sent": True}}
                    )
                    
                    reminder_count += 1
                    logger.info(f"Renewal reminder sent to {client.get('contact_email')}")
                    
                except Exception as e:
                    logger.error(f"Failed to send renewal reminder for client {billing.get('client_id')}: {e}")
            
            logger.info(f"Renewal reminder job complete. Sent {reminder_count} reminders.")
            return reminder_count
            
        except Exception as e:
            logger.error(f"Renewal reminder job error: {e}")
            return 0

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


async def run_renewal_reminders():
    """Run subscription renewal reminder job."""
    scheduler = JobScheduler()
    await scheduler.connect()
    count = await scheduler.send_renewal_reminders()
    await scheduler.close()
    return count


async def run_scheduled_reports():
    """Run scheduled report generation and email delivery."""
    scheduler = JobScheduler()
    await scheduler.connect()
    count = await scheduler.send_scheduled_reports()
    await scheduler.close()
    return count


class ScheduledReportJob:
    """Handles scheduled report generation and email delivery."""
    
    def __init__(self, db):
        self.db = db
    
    async def process_scheduled_reports(self):
        """Process all due scheduled reports and send them via email.
        
        IMPORTANT: Only runs for clients with ENABLED entitlement.
        Per spec: no background jobs when entitlement is DISABLED.
        """
        from services.reporting_service import reporting_service

        logger.info("Processing scheduled reports...")
        
        now = datetime.now(timezone.utc)
        reports_sent = 0
        
        try:
            # Find all active schedules that are due
            schedules = await self.db.report_schedules.find(
                {
                    "is_active": True,
                    "$or": [
                        {"next_scheduled": {"$lte": now.isoformat()}},
                        {"next_scheduled": None}
                    ]
                },
                {"_id": 0}
            ).to_list(100)
            
            for schedule in schedules:
                try:
                    # Get client info
                    client = await self.db.clients.find_one(
                        {"client_id": schedule["client_id"]},
                        {"_id": 0}
                    )
                    
                    # Skip if client not active or entitlement not ENABLED
                    if not client:
                        continue
                    if client.get("subscription_status") != "ACTIVE":
                        continue
                    if client.get("entitlement_status") not in ["ENABLED", None]:
                        logger.info(f"Skipping scheduled report for {schedule['client_id']} - entitlement is {client.get('entitlement_status')}")
                        continue
                    
                    # Runtime plan gating: scheduled_reports must be allowed (survives downgrade/cancel)
                    from services.plan_registry import plan_registry
                    allowed, error_msg, error_details = await plan_registry.enforce_feature(
                        schedule["client_id"], "scheduled_reports"
                    )
                    if not allowed:
                        logger.info(
                            "Skipping scheduled report for client %s - plan/subscription does not allow scheduled_reports: %s",
                            schedule["client_id"],
                            error_msg,
                        )
                        from utils.audit import create_audit_log
                        from models import AuditAction
                        await create_audit_log(
                            action=AuditAction.ADMIN_ACTION,
                            actor_role="SYSTEM",
                            client_id=schedule["client_id"],
                            metadata={
                                "action_type": "SCHEDULED_REPORT_BLOCKED_PLAN",
                                "schedule_id": schedule.get("schedule_id"),
                                "reason": error_msg,
                                "error_code": (error_details or {}).get("error_code"),
                            },
                        )
                        # MessageLog for visibility in notification health
                        try:
                            await self.db.message_logs.insert_one({
                                "message_id": str(__import__("uuid").uuid4()),
                                "client_id": schedule["client_id"],
                                "recipient": None,
                                "template_key": "SCHEDULED_REPORT",
                                "channel": "EMAIL",
                                "status": "BLOCKED_PLAN",
                                "attempt_count": 1,
                                "error_message": error_msg,
                                "metadata": {"event_type": "scheduled_report", "block_reason": "BLOCKED_PLAN"},
                                "created_at": datetime.now(timezone.utc),
                            })
                        except Exception:
                            pass
                        continue
                    
                    # Generate report
                    report_type = schedule.get("report_type", "compliance_summary")
                    
                    if report_type == "compliance_summary":
                        report_data = await reporting_service.generate_compliance_summary_report(
                            client_id=schedule["client_id"],
                            format="csv",
                            include_details=schedule.get("include_details", True)
                        )
                    elif report_type == "requirements":
                        report_data = await reporting_service.generate_requirements_report(
                            client_id=schedule["client_id"],
                            format="csv"
                        )
                    else:
                        logger.warning(f"Unknown report type: {report_type}")
                        continue
                    
                    # Prepare email
                    recipients = schedule.get("recipients", [client.get("email")])
                    frequency = schedule.get("frequency", "weekly")
                    
                    subject = f"Your {frequency.title()} Compliance Report - {now.strftime('%d %b %Y')}"
                    
                    # Send to each recipient via orchestrator
                    date_key = now.strftime("%Y-%m-%d")
                    for recipient in recipients:
                        try:
                            idempotency_key = f"{schedule.get('schedule_id', schedule['client_id'])}_SCHEDULED_REPORT_{date_key}_{recipient}"
                            from services.notification_orchestrator import notification_orchestrator
                            result = await notification_orchestrator.send(
                                template_key="SCHEDULED_REPORT",
                                client_id=schedule["client_id"],
                                context={
                                    "recipient": recipient,
                                    "client_name": client.get("full_name", "there"),
                                    "report_type": report_type.replace("_", " ").title(),
                                    "frequency": frequency,
                                    "generated_date": now.strftime("%d %B %Y"),
                                    "report_content": report_data.get("content", "")[:2000],
                                    "company_name": client.get("company_name", "Your Company"),
                                    "subject": subject,
                                },
                                idempotency_key=idempotency_key,
                                event_type="scheduled_report",
                            )
                            if result.outcome in ("sent", "duplicate_ignored"):
                                reports_sent += 1
                        except Exception as e:
                            logger.error(f"Failed to send report to {recipient}: {e}")
                    
                    # Calculate next scheduled time
                    next_scheduled = self._calculate_next_schedule(frequency, now)
                    
                    # Update schedule record
                    await self.db.report_schedules.update_one(
                        {"schedule_id": schedule["schedule_id"]},
                        {"$set": {
                            "last_sent": now.isoformat(),
                            "next_scheduled": next_scheduled.isoformat()
                        }}
                    )
                    
                    logger.info(f"Sent {report_type} report for client {schedule['client_id']}")
                    
                except Exception as e:
                    logger.error(f"Error processing schedule {schedule.get('schedule_id')}: {e}")
            
            logger.info(f"Scheduled reports job complete: {reports_sent} reports sent")
            return reports_sent
            
        except Exception as e:
            logger.error(f"Scheduled reports job failed: {e}")
            return 0
    
    def _calculate_next_schedule(self, frequency, from_time):
        """Calculate the next scheduled time based on frequency."""
        if frequency == "daily":
            return from_time + timedelta(days=1)
        elif frequency == "weekly":
            return from_time + timedelta(weeks=1)
        elif frequency == "monthly":
            # Add roughly 30 days
            return from_time + timedelta(days=30)
        else:
            return from_time + timedelta(weeks=1)


# Add to JobScheduler class
JobScheduler.send_scheduled_reports = lambda self: ScheduledReportJob(self.db).process_scheduled_reports()


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
