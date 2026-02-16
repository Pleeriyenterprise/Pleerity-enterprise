"""
Support Email Service - delegates to NotificationOrchestrator.

Sends transactional emails for support tickets:
- Customer ticket confirmation (SUPPORT_TICKET_CONFIRMATION)
- Internal support team notification (SUPPORT_INTERNAL_NOTIFICATION)
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://pleerity.com")


async def send_ticket_confirmation_email(
    ticket_id: str,
    customer_email: str,
    subject: str,
    description: str,
    category: str,
    priority: str
) -> bool:
    """Send ticket confirmation email to customer via NotificationOrchestrator."""
    try:
        from services.notification_orchestrator import notification_orchestrator
        message = (
            f"Thank you for contacting Pleerity Support. We've received your request and will respond within 24 hours.<br><br>"
            f"<strong>Ticket Reference:</strong> {ticket_id}<br>"
            f"<strong>Subject:</strong> {subject}<br>"
            f"<strong>Category:</strong> {category.replace('_', ' ').title()}<br>"
            f"<strong>Priority:</strong> {priority.title()}<br><br>"
            f"Your message: {description[:500]}{'...' if len(description) > 500 else ''}"
        )
        result = await notification_orchestrator.send(
            template_key="SUPPORT_TICKET_CONFIRMATION",
            client_id=None,
            context={
                "recipient": customer_email,
                "subject": f"Support Ticket {ticket_id} - We've received your request",
                "message": message,
            },
            idempotency_key=f"{ticket_id}_SUPPORT_TICKET_CONFIRMATION",
            event_type="support_ticket_created",
        )
        if result.outcome in ("sent", "duplicate_ignored"):
            logger.info(f"Ticket confirmation email sent to {customer_email} for {ticket_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to send ticket confirmation email: {e}")
        return False


async def send_internal_ticket_notification(
    ticket_id: str,
    customer_email: Optional[str],
    customer_crn: Optional[str],
    subject: str,
    description: str,
    category: str,
    priority: str,
    service_area: str,
    transcript: Optional[str] = None
) -> bool:
    """Send internal notification to support team via NotificationOrchestrator."""
    try:
        from services.notification_orchestrator import notification_orchestrator
        priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}.get(priority, "⚪")
        message = (
            f"<p><strong>Ticket:</strong> {ticket_id} | {priority_emoji} {priority.upper()}</p>"
            f"<p><strong>Customer:</strong> {customer_email or 'Not provided'} | <strong>CRN:</strong> {customer_crn or 'Not provided'}</p>"
            f"<p><strong>Category:</strong> {category.replace('_', ' ').title()} | <strong>Service Area:</strong> {service_area.replace('_', ' ').title()}</p>"
            f"<p><strong>Subject:</strong> {subject}</p>"
            f"<p>{description}</p>"
        )
        if transcript:
            message += f"<p><strong>Transcript:</strong></p><pre>{transcript[:2000]}</pre>"
        message += f"<p><a href=\"{FRONTEND_URL}/admin/support\">View in Admin Dashboard</a></p>"
        result = await notification_orchestrator.send(
            template_key="SUPPORT_INTERNAL_NOTIFICATION",
            client_id=None,
            context={
                "recipient": SUPPORT_EMAIL,
                "subject": f"{priority_emoji} [{priority.upper()}] New Ticket: {subject[:50]}{'...' if len(subject) > 50 else ''} - {ticket_id}",
                "message": message,
            },
            idempotency_key=f"{ticket_id}_SUPPORT_INTERNAL_NOTIFICATION",
            event_type="support_internal_notification",
        )
        if result.outcome in ("sent", "duplicate_ignored"):
            logger.info(f"Internal notification sent to {SUPPORT_EMAIL} for {ticket_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to send internal notification: {e}")
        return False
