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
    DEFAULT_DAY_NURTURE_SEQUENCE,
)
from services.lead_service import LeadService

logger = logging.getLogger(__name__)

# Postmark configuration
POSTMARK_SERVER_TOKEN = os.environ.get("POSTMARK_SERVER_TOKEN")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
UNSUBSCRIBE_URL = os.environ.get("UNSUBSCRIBE_URL", "http://localhost:3000/unsubscribe")


def _lead_app_base() -> str:
    from utils.app_urls import get_app_base_url

    return get_app_base_url(for_email_links=True).rstrip("/")


def _lead_api_base() -> str:
    from utils.app_urls import get_api_base_url

    return get_api_base_url().rstrip("/")


def _risk_level_label(score_val: object) -> Optional[str]:
    try:
        score = int(float(score_val))
    except (TypeError, ValueError):
        return None
    if score >= 90:
        return "Low Risk"
    if score >= 70:
        return "Moderate Risk"
    if score >= 50:
        return "Elevated Risk"
    return "High Risk"


def _risk_email_footer_html() -> str:
    return (
        "<p style=\"margin:16px 0 0 0; font-size:12px; color:#64748b;\">"
        "<strong>Pleerity Enterprise Ltd</strong><br/>"
        "AI-Driven Solutions & Compliance<br/>"
        "Support: info@pleerityenterprise.co.uk | https://pleerity.com<br/>"
        "Security note: Never share account credentials or payment details over email."
        "</p>"
    )


def _build_transactional_risk_check_html(lead: Dict[str, Any], activation_url: str) -> tuple[str, str]:
    name = lead.get("name") or lead.get("email", "").split("@")[0] or "there"
    raw_score = lead.get("risk_score")
    try:
        risk_score = int(raw_score) if raw_score is not None else 0
    except (TypeError, ValueError):
        risk_score = 0
    risk_level = _risk_level_label(risk_score)
    risk_row = f"<li><strong>Risk Level:</strong> {risk_level}</li>" if risk_level else ""
    subject = "Your Compliance Risk Snapshot"
    body = f"""
<html>
<body style="margin:0;padding:0;background:#f8fafc;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;color:#0f172a;">
  <div style="max-width:680px;margin:0 auto;padding:24px;">
    <div style="background:#0f172a;color:#ffffff;padding:16px 20px;border-radius:10px 10px 0 0;">
      <h1 style="margin:0;font-family:Montserrat,Inter,sans-serif;font-size:20px;color:#14b8a6;">Compliance Risk Snapshot</h1>
    </div>
    <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:none;padding:20px;border-radius:0 0 10px 10px;">
      <p style="margin:0 0 12px 0;">Hello {name},</p>
      <h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">1) Result</h2>
      <ul style="margin:0 0 14px 18px;padding:0;">
        <li><strong>Compliance Score:</strong> {risk_score}%</li>
        {risk_row}
      </ul>
      <h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">2) Meaning</h2>
      <p style="margin:0 0 14px 0;">This score indicates how resilient your current compliance monitoring posture appears based on your risk check responses.</p>
      <h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">3) Recommended Actions</h2>
      <ul style="margin:0 0 14px 18px;padding:0;">
        <li>Centralise certificates and evidence into one monitored workflow.</li>
        <li>Enable automated expiry reminders and follow-up tasks.</li>
        <li>Prioritise properties with higher risk exposure indicators.</li>
      </ul>
      <h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">4) Next Step</h2>
      <p style="margin:0 0 16px 0;">
        <a href="{activation_url}" style="display:inline-block;background:#0f766e;color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:8px;font-weight:600;">Activate Compliance Monitoring</a>
      </p>
      <h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">5) Trust & Disclaimer</h2>
      <p style="margin:0;">This report is informational only and does not constitute legal advice.</p>
      {_risk_email_footer_html()}
    </div>
  </div>
</body>
</html>
""".strip()
    return subject, body

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

[Complete your setup now]({track_cta_url})

If you have questions or need help, just reply to this email.

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        # Type-specific first step (nurture by lead type)
        "lead_followup_doc_1h": {
            "subject": "Following up on your document pack enquiry",
            "body": """
Hi {name},

Thank you for your interest in our document packs. We offer tenancy agreements, inventories, notices, and more—all legally compliant and ready to use.

If you'd like a quote or have questions, reply to this email or call us at +44 7440 645017.

**Quick links:**
- [View document packs]({base_url}/services/document-packs)
- [Order now]({base_url}/order/intake)
- [Contact us]({base_url}/contact)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "lead_followup_auto_1h": {
            "subject": "Following up on your AI automation enquiry",
            "body": """
Hi {name},

Thank you for your interest in our AI workflow automation. We help property managers and landlords automate document processing, reminders, and reporting.

If you'd like to discuss your workflow or see a demo, reply to this email or call us at +44 7440 645017.

**Quick links:**
- [AI & Automation services]({base_url}/services/ai-workflow-automation)
- [Book a consultation]({base_url}/booking)
- [Contact us]({base_url}/contact)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "lead_followup_mr_1h": {
            "subject": "Following up on your market research enquiry",
            "body": """
Hi {name},

Thank you for your interest in our market research service. We provide area analysis, rental yield reports, and investment insights to support your decisions.

If you'd like a sample or a quote, reply to this email or call us at +44 7440 645017.

**Quick links:**
- [Market research]({base_url}/services/market-research)
- [Book a consultation]({base_url}/booking)
- [Contact us]({base_url}/contact)

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
📞 [Book a call]({track_booking_url})

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
        # Nurture step 1 templates by type (document_pack, automation, market_research) are above
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
        # Default day-based nurture sequence (day0–day15)
        "nurture_day0_welcome": {
            "subject": "Welcome to Pleerity",
            "body": """
Hi {name},

Thanks for your interest in Pleerity. We help landlords stay on top of compliance—certificates, renewals, and document packs—without the spreadsheets.

If you have any questions, reply to this email or visit our [Knowledge Base]({base_url}/support/knowledge-base).

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "nurture_day2_compliance_education": {
            "subject": "Quick guide to landlord compliance",
            "body": """
Hi {name},

A quick overview: key areas landlords often need to track include Gas Safety (CP12), EICR, EPC, and—where applicable—HMO licensing. Renewal dates can slip when you have multiple properties.

[Explore compliance overview]({base_url}/services)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "nurture_day4_compliance_mistakes": {
            "subject": "The most commonly missed landlord deadline",
            "body": """
Hi {name},

Gas Safety (CP12) renewals are one of the most commonly missed—annual checks are required where gas appliances are present. Structured tracking helps you stay ahead of renewals.

[See how automated tracking works]({base_url}/compliance-vault-pro)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "nurture_day6_automation_benefits": {
            "subject": "How portfolio landlords reduce compliance stress",
            "body": """
Hi {name},

When you manage multiple properties, dates overlap and certificates expire at different times. A single dashboard for documents and expiry reminders can save time and reduce oversights.

[View dashboard overview]({base_url}/compliance-vault-pro)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "nurture_day8_document_pack": {
            "subject": "Introducing our document packs",
            "body": """
Hi {name},

We offer tenancy agreements, inventories, notices, and more—all designed for UK landlords and legally compliant. You can order individual packs or bundle with a compliance plan.

[View document packs]({base_url}/services/document-packs)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "nurture_day12_case_example": {
            "subject": "How other landlords stay on top of compliance",
            "body": """
Hi {name},

Many landlords use reminders and centralised document storage so nothing falls through the cracks. Proactive tracking means renewing in good time instead of reacting after a deadline.

[Get started]({base_url}/intake/start)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        "nurture_day15_conversion_cta": {
            "subject": "Ready to centralise your compliance?",
            "body": """
Hi {name},

If you'd like automated reminders and one place for your compliance documents, we're here to help. No hard sell—just a simple way to stay on top of renewals.

[Get started]({base_url}/intake/start) | [Book a call]({base_url}/contact)

Best regards,
The Pleerity Team

---
Reference: {lead_id}
{unsubscribe_link}
""",
        },
        # Transactional: compliance risk check completed (central lead)
        "lead_transactional_risk_check_completed": {
            "subject": "Your Compliance Risk Snapshot",
            "body": """
Hi {name},

Thank you for completing the Pleerity Compliance Risk Check.

1) Result
- Compliance Score: {risk_score}%

2) Meaning
Your score indicates your current compliance monitoring posture based on your risk check responses.

3) Recommended Actions
- Centralise evidence and certification records
- Enable automated expiry tracking
- Prioritise higher-risk properties first

4) Next Step
[Activate Compliance Monitoring]({activation_url})

5) Trust & Disclaimer
Informational only. Not legal advice.

Regards,
Pleerity Enterprise Ltd
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
        
        # CTA tracking URLs (record nurture_cta_clicked then redirect)
        from urllib.parse import quote

        _ab = _lead_app_base()
        _intake = quote(f"{_ab}/intake/start", safe="")
        _booking = quote(f"{_ab}/booking", safe="")
        track_cta_url = f"{_ab}/track/lead-activity?lead_id={lead['lead_id']}&activity_type=nurture_cta_clicked&redirect_url={_intake}"
        track_booking_url = f"{_ab}/track/lead-activity?lead_id={lead['lead_id']}&activity_type=consultation_request&redirect_url={_booking}"
        
        # Risk check transactional context (optional)
        risk_score = lead.get("risk_score")
        risk_band = lead.get("risk_band") or "—"
        activation_url = lead.get("activation_url") or f"{_ab}/intake/start"
        if risk_score is not None:
            risk_score = int(risk_score)
        else:
            risk_score = 0

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
            "base_url": _ab,
            "track_cta_url": track_cta_url,
            "track_booking_url": track_booking_url,
            "risk_score": risk_score,
            "risk_band": risk_band,
            "activation_url": activation_url,
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
            # Email open tracking: 1x1 pixel loads GET /api/leads/track-open?lead_id=...
            track_open_url = f"{_lead_api_base()}/api/leads/track-open?lead_id={lead['lead_id']}"
            html_body += f'<img src="{track_open_url}" width="1" height="1" alt="" style="display:block" />'
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
        
        # Get sequence based on followup_sequence (nurture by type)
        seq_key = lead.get("followup_sequence") or "default"
        if seq_key == "abandoned_intake":
            sequence = ABANDONED_INTAKE_SEQUENCE
        elif seq_key == "document_pack":
            sequence = [
                {"step": 1, "delay_hours": 1, "template_id": "lead_followup_doc_1h", "subject": "Following up on your document pack enquiry"},
                {"step": 2, "delay_hours": 24, "template_id": "lead_followup_24h", "subject": "Still deciding? Here's what you need to know"},
                {"step": 3, "delay_hours": 72, "template_id": "lead_followup_72h", "subject": "Final reminder: We're here to help"},
            ]
        elif seq_key == "automation":
            sequence = [
                {"step": 1, "delay_hours": 1, "template_id": "lead_followup_auto_1h", "subject": "Following up on your AI automation enquiry"},
                {"step": 2, "delay_hours": 24, "template_id": "lead_followup_24h", "subject": "Still deciding? Here's what you need to know"},
                {"step": 3, "delay_hours": 72, "template_id": "lead_followup_72h", "subject": "Final reminder: We're here to help"},
            ]
        elif seq_key == "market_research":
            sequence = [
                {"step": 1, "delay_hours": 1, "template_id": "lead_followup_mr_1h", "subject": "Following up on your market research enquiry"},
                {"step": 2, "delay_hours": 24, "template_id": "lead_followup_24h", "subject": "Still deciding? Here's what you need to know"},
                {"step": 3, "delay_hours": 72, "template_id": "lead_followup_72h", "subject": "Final reminder: We're here to help"},
            ]
        else:
            # default: day-based 7-step nurture (day0 welcome → day15 conversion CTA)
            sequence = DEFAULT_DAY_NURTURE_SEQUENCE
        
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
            
            # Update lead with next follow-up time (support delay_hours or delay_days)
            update_data = {
                "followup_step": next_step,
                "last_followup_at": datetime.now(timezone.utc).isoformat(),
            }
            if next_step < len(sequence):
                next_cfg = sequence[next_step]
                if "delay_days" in next_cfg:
                    # Day-based: next_followup_at = lead created_at + delay_days
                    created_at_raw = lead.get("created_at")
                    if isinstance(created_at_raw, str):
                        try:
                            created_dt = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                        except Exception:
                            created_dt = datetime.now(timezone.utc)
                    elif hasattr(created_at_raw, "isoformat"):
                        created_dt = created_at_raw
                    else:
                        created_dt = datetime.now(timezone.utc)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    next_at = created_dt + timedelta(days=next_cfg["delay_days"])
                    update_data["next_followup_at"] = next_at.isoformat()
                else:
                    next_delay_hours = next_cfg.get("delay_hours", 0)
                    update_data["next_followup_at"] = (
                        datetime.now(timezone.utc) + timedelta(hours=next_delay_hours)
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
    async def send_risk_check_completed_transactional(
        lead: Dict[str, Any],
        activation_url: str,
    ) -> bool:
        """
        Send transactional email after compliance risk check (central lead).
        Uses template lead_transactional_risk_check_completed and template_key LEAD_TRANSACTIONAL_RISK_CHECK_COMPLETED.
        Call from risk_check after syncing to central leads; do not also send from risk_lead_email_service.
        """
        if not lead.get("email"):
            return False
        try:
            lead = dict(lead)
            subject, html_body = _build_transactional_risk_check_html(lead, activation_url)
            from services.notification_orchestrator import notification_orchestrator
            from datetime import datetime, timezone
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            idempotency_key = f"{lead['lead_id']}_LEAD_TRANSACTIONAL_RISK_CHECK_{date_key}"
            result = await notification_orchestrator.send(
                template_key="LEAD_TRANSACTIONAL_RISK_CHECK_COMPLETED",
                client_id=None,
                context={"recipient": lead["email"], "subject": subject, "message": html_body},
                idempotency_key=idempotency_key,
                event_type="lead_transactional_risk_check_completed",
            )
            if result.outcome in ("sent", "duplicate_ignored"):
                await LeadService.log_audit(
                    event=LeadAuditEvent.FOLLOWUP_EMAIL_SENT,
                    lead_id=lead["lead_id"],
                    actor_id="system",
                    actor_type="automation",
                    details={"type": "risk_check_completed", "email": lead.get("email")},
                )
                return True
            return False
        except Exception as e:
            logger.error("Failed to send risk check completed email: %s", e)
            return False

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

        # Default and compliance sequences are day-based (day 0 = welcome immediately); others use 1h first delay
        seq_key = lead.get("followup_sequence") or "default"
        if seq_key in ("default", "compliance"):
            first_followup = datetime.now(timezone.utc)  # due immediately for step 1 (day 0)
        else:
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

        ADMIN_NOTIFICATION_EMAILS = os.environ.get(
            "ADMIN_NOTIFICATION_EMAILS",
            "admin@pleerity.com",
        ).split(",")
        _base = _lead_app_base()
        ADMIN_DASHBOARD_URL = os.environ.get("ADMIN_DASHBOARD_URL", f"{_base}/admin/leads")
        
        try:
            from services.notification_orchestrator import notification_orchestrator
            from datetime import datetime, timezone
            lead_id = lead.get("lead_id")
            name = lead.get("name") or "Unknown"
            email = lead.get("email") or "No email"
            created_at = lead.get("created_at", "Unknown")
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            from services.operational_alert_presentation import enrich_lead_sla_breach_admin_context

            for admin_email in ADMIN_NOTIFICATION_EMAILS:
                admin_email = admin_email.strip()
                if admin_email:
                    try:
                        idempotency_key = f"{lead_id}_LEAD_SLA_BREACH_ADMIN_{date_key}_{admin_email}"
                        ctx = enrich_lead_sla_breach_admin_context(
                            recipient=admin_email,
                            lead_id=str(lead_id),
                            name=str(name),
                            email=str(email),
                            created_at=str(created_at),
                            admin_dashboard_url=ADMIN_DASHBOARD_URL,
                        )
                        result = await notification_orchestrator.send(
                            template_key="LEAD_SLA_BREACH_ADMIN",
                            client_id=None,
                            context=ctx,
                            idempotency_key=idempotency_key,
                            event_type="lead_sla_breach",
                        )
                        if result.outcome in ("sent", "duplicate_ignored"):
                            logger.info(f"SLA breach notification sent to {admin_email} for lead {lead_id}")
                    except Exception as e:
                        logger.error(f"Failed to send SLA breach notification: {e}")
        except Exception as e:
            logger.error(f"Failed to send SLA breach notification: {e}")
