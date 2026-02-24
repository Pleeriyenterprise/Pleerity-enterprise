"""
Checklist lead nurture: 5-email sequence for source_platform COMPLIANCE_CHECKLIST.
Day 0 (immediate), Day 2, Day 4, Day 6, Day 9. Respects unsubscribe and conversion.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from database import database
from services.lead_models import LeadStatus, LeadAuditEvent
from services.lead_service import LeadService

logger = logging.getLogger(__name__)

LEADS_COLLECTION = "leads"
FRONTEND_BASE_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
UNSUBSCRIBE_URL = os.environ.get("UNSUBSCRIBE_URL", "http://localhost:3000/unsubscribe")
COMPANY_FOOTER = os.environ.get(
    "COMPANY_ADDRESS_FOOTER",
    "Compliance Vault Pro | pleerityenterprise.co.uk",
)
DISCLAIMER = (
    "This email is for information only and does not constitute legal advice. "
    "Requirements may vary by property type and local authority."
)

# Next email index (1–5) -> minimum days since created_at to send
NURTURE_DAYS = (0, 2, 4, 6, 9)  # email 1 at day 0, email 2 at day 2, etc.

NURTURE_TEMPLATES = [
    {
        "subject": "Your UK Landlord Compliance Checklist (2026)",
        "body": """Hello {name},

Here is your UK Landlord Compliance Master Checklist (2026 Edition).

This checklist provides a structured framework for tracking certificates, licences, and renewal deadlines across rental properties.

Important note: This document is informational and does not constitute legal advice.

If you manage multiple properties, you may find manual tracking becomes complex over time. Many landlords eventually move to structured digital tracking to centralise documents and expiry reminders.

[Explore Compliance Vault Pro]({base_url}/compliance-vault-pro)

No hard sell. Just positioning.

{disclaimer}

---
{unsubscribe_link}
{company_footer}
Reference: {lead_id}
""",
    },
    {
        "subject": "The most commonly missed landlord deadline",
        "body": """Hello {name},

Most missed compliance issues are simple expiry oversights—especially Gas Safety (CP12). An annual Gas Safety Record is typically required where gas appliances are present, and renewal dates are easy to lose track of when you have multiple properties.

Structured tracking reduces reliance on memory and helps you stay ahead of renewals.

[See how automated expiry tracking works]({base_url}/compliance-vault-pro)

{disclaimer}

---
{unsubscribe_link}
{company_footer}
Reference: {lead_id}
""",
    },
    {
        "subject": "How portfolio landlords reduce compliance stress",
        "body": """Hello {name},

When managing multiple properties, dates overlap, licences vary, and certificates expire at different intervals. Property-level visibility helps you see at a glance which properties need attention.

A structured dashboard gives you one place for documents, expiry dates, and reminders—so you spend less time chasing spreadsheets and more time on your portfolio.

[View dashboard overview]({base_url}/compliance-vault-pro)

{disclaimer}

---
{unsubscribe_link}
{company_footer}
Reference: {lead_id}
""",
    },
    {
        "subject": "What happens when compliance deadlines are missed?",
        "body": """Hello {name},

Consequences vary depending on the requirement and the authority. Proactive tracking reduces the likelihood of oversight—instead of reacting after a deadline, you can set reminders well in advance.

Automated systems send notifications before expiry so you can renew in good time.

[Start structured tracking]({base_url}/intake/start)

{disclaimer}

---
{unsubscribe_link}
{company_footer}
Reference: {lead_id}
""",
    },
    {
        "subject": "Ready to centralise your landlord compliance?",
        "body": """Hello {name},

If you've been using the checklist manually and it's working for you, that's great.

If you prefer automated reminders and centralised document storage, Compliance Vault Pro is designed for that—without urgency gimmicks.

[Start 14-day trial]({base_url}/intake/start)

{disclaimer}

---
{unsubscribe_link}
{company_footer}
Reference: {lead_id}
""",
    },
]


def _markdown_to_html(text: str) -> str:
    import re
    html = text
    html = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.*?)\*", r"<em>\1</em>", html)
    html = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', html)
    html = html.replace("\n\n", "</p><p>")
    html = html.replace("\n", "<br>")
    return f"""<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<div style="max-width: 600px; margin: 0 auto; padding: 20px;"><p>{html}</p></div>
</body></html>"""


def _render_nurture_body(lead: Dict[str, Any], template_index: int) -> str:
    template = NURTURE_TEMPLATES[template_index]
    name = lead.get("name") or (lead.get("email") or "").split("@")[0] or "there"
    unsubscribe_link = f'<a href="{UNSUBSCRIBE_URL}?lead={lead[\"lead_id\"]}">Unsubscribe from marketing emails</a>'
    return template["body"].format(
        name=name,
        base_url=FRONTEND_BASE_URL,
        disclaimer=DISCLAIMER,
        unsubscribe_link=unsubscribe_link,
        company_footer=COMPANY_FOOTER,
        lead_id=lead["lead_id"],
    )


async def send_nurture_email(
    lead: Dict[str, Any],
    template_index: int,
) -> tuple[bool, Optional[str]]:
    """Send nurture email (1-based index 1–5). Returns (success, error_message)."""
    if not lead.get("email"):
        return False, "No email address"
    if template_index < 0 or template_index >= len(NURTURE_TEMPLATES):
        return False, "Invalid template index"
    subject = NURTURE_TEMPLATES[template_index]["subject"]
    body_html = _markdown_to_html(_render_nurture_body(lead, template_index))
    try:
        from services.notification_orchestrator import notification_orchestrator
        now = datetime.now(timezone.utc)
        date_key = now.strftime("%Y-%m-%d")
        idempotency_key = f"{lead['lead_id']}_CHECKLIST_NURTURE_{template_index + 1}_{date_key}"
        result = await notification_orchestrator.send(
            template_key="LEAD_FOLLOWUP",
            client_id=None,
            context={
                "recipient": lead["email"],
                "subject": subject,
                "message": body_html,
            },
            idempotency_key=idempotency_key,
            event_type=f"checklist_nurture_{template_index + 1}",
        )
        if result.outcome in ("sent", "duplicate_ignored"):
            logger.info(
                "Checklist nurture email %s sent to %s (lead %s)",
                template_index + 1,
                lead.get("email"),
                lead.get("lead_id"),
            )
            return True, None
        return False, result.error_message or result.block_reason or result.outcome
    except Exception as e:
        logger.exception("Failed to send checklist nurture email: %s", e)
        return False, str(e)


async def should_skip_nurture(lead: Dict[str, Any]) -> bool:
    """True if we must not send any more nurture emails."""
    if lead.get("status") in (
        LeadStatus.CONVERTED.value,
        LeadStatus.LOST.value,
        LeadStatus.MERGED.value,
        LeadStatus.UNSUBSCRIBED.value,
    ):
        return True
    if not lead.get("marketing_consent"):
        return True
    if lead.get("followup_status") == "OPTED_OUT":
        return True
    if lead.get("merged_into_lead_id"):
        return True
    return False


async def send_checklist_delivery_email_and_update_lead(lead: Dict[str, Any]) -> bool:
    """
    Send Email 1 (checklist delivery) and set nurture_stage=1, last_nurture_sent_at.
    Call after create_lead for COMPLIANCE_CHECKLIST when marketing_consent and not duplicate.
    """
    if await should_skip_nurture(lead):
        return False
    success, err = await send_nurture_email(lead, 0)
    if not success:
        return False
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db[LEADS_COLLECTION].update_one(
        {"lead_id": lead["lead_id"]},
        {"$set": {"nurture_stage": 1, "last_nurture_sent_at": now, "updated_at": now}},
    )
    await LeadService.log_audit(
        event=LeadAuditEvent.FOLLOWUP_EMAIL_SENT,
        lead_id=lead["lead_id"],
        actor_id="system",
        actor_type="automation",
        details={
            "type": "checklist_nurture",
            "nurture_stage": 1,
            "email": lead.get("email"),
        },
    )
    return True


async def process_checklist_nurture_queue() -> int:
    """
    Daily job: find COMPLIANCE_CHECKLIST leads due for next nurture email (2–5).
    Sends at most one email per lead per run; increments nurture_stage and sets last_nurture_sent_at.
    Returns count of emails sent.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    sent = 0
    for next_stage in range(1, 5):  # next_stage 1 = send email 2, etc.
        required_days = NURTURE_DAYS[next_stage]
        cutoff = (now - timedelta(days=required_days)).isoformat()
        due = await db[LEADS_COLLECTION].find(
            {
                "source_platform": "COMPLIANCE_CHECKLIST",
                "marketing_consent": True,
                "followup_status": {"$ne": "OPTED_OUT"},
                "status": {"$nin": [LeadStatus.CONVERTED.value, LeadStatus.LOST.value, LeadStatus.MERGED.value]},
                "nurture_stage": next_stage,
                "created_at": {"$lte": cutoff},
            },
            {"_id": 0},
        ).to_list(length=200)
        for lead in due:
            if await should_skip_nurture(lead):
                continue
            success, _ = await send_nurture_email(lead, next_stage)
            if success:
                now_iso = datetime.now(timezone.utc).isoformat()
                await db[LEADS_COLLECTION].update_one(
                    {"lead_id": lead["lead_id"]},
                    {
                        "$set": {
                            "nurture_stage": next_stage + 1,
                            "last_nurture_sent_at": now_iso,
                            "updated_at": now_iso,
                        }
                    },
                )
                await LeadService.log_audit(
                    event=LeadAuditEvent.FOLLOWUP_EMAIL_SENT,
                    lead_id=lead["lead_id"],
                    actor_id="system",
                    actor_type="automation",
                    details={
                        "type": "checklist_nurture",
                        "nurture_stage": next_stage + 1,
                        "email": lead.get("email"),
                    },
                )
                sent += 1
    if sent:
        logger.info("Checklist nurture queue: %s email(s) sent", sent)
    return sent
