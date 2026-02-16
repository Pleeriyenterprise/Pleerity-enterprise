"""
Lead Follow-Up Automation Service

Handles:
- Time-based email follow-up sequences
- Consent-aware sending
- Stop condition detection
- Email template rendering
- Postmark integration
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from database import database
from services.lead_models import (
    LeadStatus,
    FollowUpStatus,
    LeadAuditEvent,
    FOLLOWUP_SEQUENCE,
    ABANDONED_INTAKE_SEQUENCE,
)
from services.lead_service import LeadService

logger = logging.getLogger(__name__)

# Postmark configuration
POSTMARK_SERVER_TOKEN = os.environ.get("POSTMARK_SERVER_TOKEN")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
UNSUBSCRIBE_URL = os.environ.get("UNSUBSCRIBE_URL", "http://localhost:3000/unsubscribe")
FRONTEND_BASE_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")

LEADS_COLLECTION = "leads"


class LeadFollowUpService:
    """Service for automated lead follow-up emails."""
    
    # Email templates
    TEMPLATES = {
        # Default follow-up sequence
        "lead_followup_1h": {
            "subject": "Following up on your enquiry",
            "body": """
Hi {name},

Thank you for reaching out to Pleerity. We received your enquiry about {service_interest} and wanted to follow up.

{message_context}

Our team is ready to help you get started. If you have any questions, simply reply to this email or call us at +44 7440 645017.

**Quick links:**
- [View our services]({base_url}/services)
- [Book a consultation]({base_url}/contact)
- [Get started]({base_url}/intake)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "lead_followup_24h": {
            "subject": "Still deciding? Here's what you need to know",
            "body": """
Hi {name},

We noticed you were interested in {service_interest} but haven't completed your setup yet.

**Here's what you'll get:**
✅ Automated compliance tracking
✅ Professional document generation
✅ 24/7 support access
✅ Simple, transparent pricing

Most landlords complete their setup in under 5 minutes. Ready to get started?

[Complete your setup now]({base_url}/intake)

If you have questions or need help, just reply to this email.

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "lead_followup_72h": {
            "subject": "Final reminder: We're here to help",
            "body": """
Hi {name},

This is our final follow-up about your {service_interest} enquiry.

We understand choosing the right compliance solution is an important decision. If you're still evaluating your options, here are some resources that might help:

📋 [Compare our plans]({base_url}/pricing)
💬 [Chat with our team]({base_url}/) (available 24/7)
📞 [Book a call]({base_url}/contact)

If you've already found a solution or are no longer interested, no worries—we won't send any more follow-ups.

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        
        # Abandoned intake sequence
        "abandoned_intake_1h": {
            "subject": "You started setting up Compliance Vault Pro — need help?",
            "body": """
Hi {name},

We noticed you started setting up Compliance Vault Pro but didn't complete the process.

{intake_context}

**Need help?** Our team is here to assist:
- Reply to this email with any questions
- Chat with us anytime at [pleerity.com]({base_url})
- Call us at +44 7440 645017

[Continue your setup →]({base_url}/intake?resume={draft_id})

Your progress has been saved—just pick up where you left off.

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "abandoned_intake_24h": {
            "subject": "Most landlords finish setup in under 5 minutes",
            "body": """
Hi {name},

Quick reminder: your Compliance Vault Pro setup is almost complete!

**What happens when you finish:**
✅ Instant access to your compliance dashboard
✅ Automated certificate and document tracking
✅ Professional document generation
✅ Peace of mind for your properties

[Complete your setup now →]({base_url}/intake?resume={draft_id})

Questions? Just reply to this email.

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "abandoned_intake_72h": {
            "subject": "Still deciding? Here's what you get with your plan",
            "body": """
Hi {name},

This is our final reminder about your Compliance Vault Pro setup.

{plan_details}

**Why landlords choose Pleerity:**
- ⏰ Save hours on compliance admin
- 📋 Never miss a certificate expiry
- 🏠 Professional tenant document packs
- 💬 24/7 support access

Ready to simplify your compliance?

[Complete your setup →]({base_url}/intake?resume={draft_id})

If you've decided not to proceed, no problem—we won't send further reminders.

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        
        # Acknowledgement email (transactional, not marketing)
        "lead_acknowledgement": {
            "subject": "We've received your enquiry — Reference: {lead_id}",
            "body": """
Hi {name},

Thank you for contacting Pleerity. We've received your enquiry and a member of our team will be in touch shortly.

**Your reference number:** {lead_id}

In the meantime, you can:
- [Browse our services]({base_url}/services)
- [Check our Knowledge Base]({base_url}/support/knowledge-base)
- [Start a chat]({base_url}) (24/7 support)

Best regards,
The Pleerity Team

---
This is an automated confirmation. Your enquiry reference is {lead_id}.
""",
        },
    }
    
    @staticmethod
    def render_template(
        template_id: str,
        lead: Dict[str, Any],
        draft: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """Render email template with lead data."""
        template = LeadFollowUpService.TEMPLATES.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Build context
        name = lead.get("name") or lead.get("email", "").split("@")[0] or "there"
        service_interest = lead.get("service_interest", "our services").replace("_", " ").title()
        
        # Message context
        message_context = ""
        if lead.get("message_summary"):
            message_context = f"\n> \"{lead['message_summary']}\"\n"
        
        # Intake context for abandoned intakes
        intake_context = ""
        plan_details = ""
        draft_id = lead.get("intake_draft_id", "")
        
        if draft:
            plan = draft.get("intake_payload", {}).get("selected_plan", "")
            properties = len(draft.get("intake_payload", {}).get("properties", []))
            intake_context = f"You selected the **{plan}** plan with **{properties}** properties."
            plan_details = f"**Your selected plan:** {plan}\n**Properties:** {properties}"
        
        # Unsubscribe link
        unsubscribe_link = f"[Unsubscribe from marketing emails]({UNSUBSCRIBE_URL}?lead={lead['lead_id']})"
        
        # Render (base_url for links)
        context = {
            "name": name,
            "service_interest": service_interest,
            "message_context": message_context,
            "intake_context": intake_context,
            "plan_details": plan_details,
            "draft_id": draft_id,
            "lead_id": lead["lead_id"],
            "unsubscribe_link": unsubscribe_link,
            "base_url": FRONTEND_BASE_URL,
        }
        
        subject = template["subject"].format(**context)
        body = template["body"].format(**context)
        
        return subject, body
    
    @staticmethod
    async def send_followup_email(
        lead: Dict[str, Any],
        template_id: str,
        subject: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Send follow-up email via Postmark.
        Returns (success, error_message).
        """
        if not lead.get("email"):
            return False, "No email address"
        
        try:
            from services.notification_orchestrator import notification_orchestrator
            db = database.get_db()
            draft = None
            if lead.get("intake_draft_id"):
                draft = await db["intake_drafts"].find_one(
                    {"draft_id": lead["intake_draft_id"]},
                    {"_id": 0}
                )
            subject, body = LeadFollowUpService.render_template(
                template_id=template_id,
                lead=lead,
                draft=draft,
            )
            html_body = LeadFollowUpService.markdown_to_html(body)
            from datetime import datetime, timezone
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            idempotency_key = f"{lead['lead_id']}_LEAD_FOLLOWUP_{template_id}_{date_key}"
            result = await notification_orchestrator.send(
                template_key="LEAD_FOLLOWUP",
                client_id=None,
                context={"recipient": lead["email"], "subject": subject, "message": html_body},
                idempotency_key=idempotency_key,
                event_type=f"lead_followup_{template_id}",
            )
            if result.outcome in ("sent", "duplicate_ignored"):
                logger.info(f"Follow-up email sent to {lead['email']} for lead {lead['lead_id']}")
                return True, None
            return False, result.error_message or result.block_reason or result.outcome
        except Exception as e:
            logger.error(f"Failed to send follow-up email: {e}")
            return False, str(e)
    
    @staticmethod
    def markdown_to_html(text: str) -> str:
        """Simple markdown to HTML conversion."""
        import re
        
        html = text
        
        # Bold
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        
        # Italic
        html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
        
        # Links
        html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html)
        
        # Line breaks
        html = html.replace('\n\n', '</p><p>')
        html = html.replace('\n', '<br>')
        
        # Checkmarks and emojis (keep as-is)
        
        # Wrap in basic HTML
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <p>{html}</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    async def process_followup_queue():
        """
        Process follow-up queue.
        Called by scheduled job every 15 minutes.
        
        CONSENT ENFORCEMENT:
        - Checks both lead.marketing_consent AND cookie consent state
        - Only proceeds if both allow marketing outreach
        """
        db = database.get_db()
        now = datetime.now(timezone.utc)
        
        # Import consent service for server-side consent check
        from services.consent_service import ConsentService
        
        # Find leads due for follow-up
        due_leads = await db[LEADS_COLLECTION].find({
            "followup_status": FollowUpStatus.IN_PROGRESS.value,
            "marketing_consent": True,
            "next_followup_at": {"$lte": now.isoformat()},
            "status": {"$nin": [
                LeadStatus.CONVERTED.value,
                LeadStatus.LOST.value,
                LeadStatus.MERGED.value,
            ]},
        }, {"_id": 0}).to_list(length=100)
        
        logger.info(f"Processing {len(due_leads)} leads for follow-up")
        
        for lead in due_leads:
            # Additional consent check via cookie consent system
            session_id = lead.get("session_id") or lead.get("source_metadata", {}).get("session_id")
            
            if session_id:
                # Check server-side cookie consent
                is_eligible = await ConsentService.is_outreach_eligible(session_id=session_id)
                if not is_eligible:
                    logger.info(f"Skipping follow-up for lead {lead.get('lead_id')}: cookie consent not granted")
                    # Update lead to stop follow-up
                    await db[LEADS_COLLECTION].update_one(
                        {"lead_id": lead["lead_id"]},
                        {"$set": {
                            "followup_status": FollowUpStatus.STOPPED.value,
                            "followup_stop_reason": "cookie_consent_withdrawn",
                        }}
                    )
                    continue
            
            await LeadFollowUpService.send_next_followup(lead)
    
    @staticmethod
    async def send_next_followup(lead: Dict[str, Any]):
        """Send next follow-up email for a lead."""
        db = database.get_db()
        
        # Check stop conditions
        if await LeadFollowUpService.should_stop_followup(lead):
            await LeadService.update_followup_status(
                lead["lead_id"],
                FollowUpStatus.STOPPED,
            )
            await LeadService.log_audit(
                event=LeadAuditEvent.FOLLOWUP_STOPPED,
                lead_id=lead["lead_id"],
                actor_id="system",
                actor_type="automation",
                details={"reason": "Stop condition met"},
            )
            return
        
        # Get sequence based on source
        sequence = (
            ABANDONED_INTAKE_SEQUENCE
            if lead.get("followup_sequence") == "abandoned_intake"
            else FOLLOWUP_SEQUENCE
        )
        
        current_step = lead.get("followup_step", 0)
        next_step = current_step + 1
        
        # Check if sequence complete
        if next_step > len(sequence):
            await LeadService.update_followup_status(
                lead["lead_id"],
                FollowUpStatus.COMPLETED,
            )
            return
        
        # Get step details
        step_config = sequence[next_step - 1]
        template_id = step_config["template_id"]
        subject = step_config["subject"]
        
        # Send email
        success, error = await LeadFollowUpService.send_followup_email(
            lead=lead,
            template_id=template_id,
            subject=subject,
        )
        
        # Log result
        if success:
            await LeadService.log_audit(
                event=LeadAuditEvent.FOLLOWUP_EMAIL_SENT,
                lead_id=lead["lead_id"],
                actor_id="system",
                actor_type="automation",
                details={
                    "step": next_step,
                    "template_id": template_id,
                    "email": lead.get("email"),
                },
            )
            
            # Update lead with next follow-up time
            next_delay = sequence[next_step]["delay_hours"] if next_step < len(sequence) else None
            
            update_data = {
                "followup_step": next_step,
                "last_followup_at": datetime.now(timezone.utc).isoformat(),
            }
            
            if next_delay:
                update_data["next_followup_at"] = (
                    datetime.now(timezone.utc) + timedelta(hours=next_delay)
                ).isoformat()
            else:
                update_data["followup_status"] = FollowUpStatus.COMPLETED.value
            
            await db[LEADS_COLLECTION].update_one(
                {"lead_id": lead["lead_id"]},
                {"$set": update_data}
            )
        else:
            await LeadService.log_audit(
                event=LeadAuditEvent.FOLLOWUP_EMAIL_FAILED,
                lead_id=lead["lead_id"],
                actor_id="system",
                actor_type="automation",
                details={
                    "step": next_step,
                    "template_id": template_id,
                    "error": error,
                },
            )
    
    @staticmethod
    async def should_stop_followup(lead: Dict[str, Any]) -> bool:
        """Check if follow-up should be stopped."""
        # Stop conditions
        if lead.get("status") in [
            LeadStatus.CONVERTED.value,
            LeadStatus.LOST.value,
            LeadStatus.MERGED.value,
            LeadStatus.UNSUBSCRIBED.value,
        ]:
            return True
        
        if not lead.get("marketing_consent"):
            return True
        
        if lead.get("merged_into_lead_id"):
            return True
        
        return False
    
    @staticmethod
    async def send_acknowledgement(lead: Dict[str, Any]) -> bool:
        """
        Send acknowledgement email (transactional, not marketing).
        This is sent regardless of marketing consent.
        """
        success, error = await LeadFollowUpService.send_followup_email(
            lead=lead,
            template_id="lead_acknowledgement",
            subject=f"We've received your enquiry — Reference: {lead['lead_id']}",
        )
        
        if success:
            await LeadService.log_audit(
                event=LeadAuditEvent.FOLLOWUP_EMAIL_SENT,
                lead_id=lead["lead_id"],
                actor_id="system",
                actor_type="automation",
                details={
                    "type": "acknowledgement",
                    "email": lead.get("email"),
                },
            )
        
        return success
    
    @staticmethod
    async def start_followup_sequence(lead_id: str):
        """Start follow-up sequence for a lead (if consent given)."""
        db = database.get_db()
        lead = await LeadService.get_lead(lead_id)
        
        if not lead:
            return
        
        # Only start if marketing consent given
        if not lead.get("marketing_consent"):
            logger.info(f"Skipping follow-up for {lead_id}: no marketing consent")
            return
        
        # Calculate first follow-up time
        first_followup = datetime.now(timezone.utc) + timedelta(hours=1)
        
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {
                "$set": {
                    "followup_status": FollowUpStatus.IN_PROGRESS.value,
                    "next_followup_at": first_followup.isoformat(),
                }
            }
        )
        
        logger.info(f"Started follow-up sequence for lead {lead_id}")


class LeadSLAService:
    """Service for SLA tracking and breach detection."""
    
    @staticmethod
    async def check_sla_breaches(sla_hours: int = 24):
        """
        Check for SLA breaches.
        Default: 24 hours (simple mode).
        TODO: Implement business hours mode.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=sla_hours)).isoformat()
        
        # Find leads that:
        # 1. Are NEW and not contacted
        # 2. Created before cutoff
        # 3. Not already marked as SLA breach
        breached_leads = await db[LEADS_COLLECTION].find({
            "stage": "NEW",
            "status": "ACTIVE",
            "sla_breach": False,
            "created_at": {"$lt": cutoff},
            "last_contacted_at": None,
        }, {"_id": 0}).to_list(length=100)
        
        for lead in breached_leads:
            await db[LEADS_COLLECTION].update_one(
                {"lead_id": lead["lead_id"]},
                {
                    "$set": {
                        "sla_breach": True,
                        "sla_breach_at": now.isoformat(),
                    }
                }
            )
            
            await LeadService.log_audit(
                event=LeadAuditEvent.SLA_BREACH,
                lead_id=lead["lead_id"],
                actor_id="system",
                actor_type="automation",
                details={
                    "sla_hours": sla_hours,
                    "created_at": lead["created_at"],
                },
            )
            
            # Send SLA breach notification to admins
            await LeadSLAService.notify_sla_breach(lead)
        
        if breached_leads:
            logger.warning(f"SLA breach detected for {len(breached_leads)} leads")
        
        return len(breached_leads)
    
    @staticmethod
    async def notify_sla_breach(lead: Dict[str, Any]):
        """Send SLA breach notification to admins."""
        import os
        
        POSTMARK_SERVER_TOKEN = os.environ.get("POSTMARK_SERVER_TOKEN")
        ADMIN_NOTIFICATION_EMAILS = os.environ.get(
            "ADMIN_NOTIFICATION_EMAILS", 
            "admin@pleerity.com"
        ).split(",")
        SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
        _base = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        ADMIN_DASHBOARD_URL = os.environ.get("ADMIN_DASHBOARD_URL", f"{_base}/admin/leads")
        
        try:
            from services.notification_orchestrator import notification_orchestrator
            from datetime import datetime, timezone
            lead_id = lead.get("lead_id")
            name = lead.get("name") or "Unknown"
            email = lead.get("email") or "No email"
            created_at = lead.get("created_at", "Unknown")
            subject = f"⚠️ SLA BREACH: Lead {lead_id} not contacted within 24 hours"
            message = (
                f"<p>This lead has not been contacted within the required 24-hour SLA window.</p>"
                f"<p><strong>Lead ID:</strong> {lead_id}<br><strong>Name:</strong> {name}<br>"
                f"<strong>Email:</strong> {email}<br><strong>Created:</strong> {created_at}</p>"
                f"<p><a href=\"{ADMIN_DASHBOARD_URL}\">Contact Lead Now →</a></p>"
            )
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for admin_email in ADMIN_NOTIFICATION_EMAILS:
                admin_email = admin_email.strip()
                if admin_email:
                    try:
                        idempotency_key = f"{lead_id}_LEAD_SLA_BREACH_ADMIN_{date_key}_{admin_email}"
                        result = await notification_orchestrator.send(
                            template_key="LEAD_SLA_BREACH_ADMIN",
                            client_id=None,
                            context={"recipient": admin_email, "subject": subject, "message": message},
                            idempotency_key=idempotency_key,
                            event_type="lead_sla_breach",
                        )
                        if result.outcome in ("sent", "duplicate_ignored"):
                            logger.info(f"SLA breach notification sent to {admin_email} for lead {lead_id}")
                    except Exception as e:
                        logger.error(f"Failed to send SLA breach notification: {e}")
        except Exception as e:
            logger.error(f"Failed to send SLA breach notification: {e}")
