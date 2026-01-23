"""
Support Email Service - Postmark Integration

Sends transactional emails for support tickets:
- Customer ticket confirmation
- Internal support team notification
"""
import os
import logging
from typing import Optional, Dict, Any
from postmarker.core import PostmarkClient

logger = logging.getLogger(__name__)

# Get configuration from environment
POSTMARK_TOKEN = os.environ.get("POSTMARK_SERVER_TOKEN")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "info@pleerityenterprise.co.uk")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://pleerity.com")


def get_postmark_client() -> Optional[PostmarkClient]:
    """Get Postmark client if configured."""
    if not POSTMARK_TOKEN:
        logger.warning("POSTMARK_SERVER_TOKEN not configured")
        return None
    return PostmarkClient(server_token=POSTMARK_TOKEN)


async def send_ticket_confirmation_email(
    ticket_id: str,
    customer_email: str,
    subject: str,
    description: str,
    category: str,
    priority: str
) -> bool:
    """
    Send ticket confirmation email to customer.
    """
    client = get_postmark_client()
    if not client:
        logger.info(f"[MOCK EMAIL] Ticket confirmation to {customer_email} for {ticket_id}")
        return False
    
    try:
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #0d9488 0%, #14b8a6 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .ticket-box {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0; }}
        .ticket-id {{ font-family: monospace; font-size: 18px; color: #0d9488; font-weight: bold; }}
        .label {{ color: #6b7280; font-size: 12px; text-transform: uppercase; margin-bottom: 4px; }}
        .value {{ font-size: 14px; margin-bottom: 16px; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
        .button {{ display: inline-block; background: #0d9488; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">Support Ticket Received</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">We've got your message</p>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p>Thank you for contacting Pleerity Support. We've received your request and will respond within 24 hours.</p>
            
            <div class="ticket-box">
                <div class="label">Ticket Reference</div>
                <div class="ticket-id">{ticket_id}</div>
                
                <div style="margin-top: 20px;">
                    <div class="label">Subject</div>
                    <div class="value">{subject}</div>
                    
                    <div class="label">Category</div>
                    <div class="value">{category.replace('_', ' ').title()}</div>
                    
                    <div class="label">Priority</div>
                    <div class="value">{priority.title()}</div>
                    
                    <div class="label">Your Message</div>
                    <div class="value">{description[:500]}{'...' if len(description) > 500 else ''}</div>
                </div>
            </div>
            
            <p>You can reply to this email to add more information to your ticket.</p>
            
            <center>
                <a href="{FRONTEND_URL}/app/orders" class="button">View Your Account</a>
            </center>
        </div>
        <div class="footer">
            <p>This is an automated message from Pleerity Enterprise Ltd.</p>
            <p>For support, contact <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
            <p>© 2026 Pleerity Enterprise Ltd. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
        
        text_body = f"""
Support Ticket Received - {ticket_id}

Hello,

Thank you for contacting Pleerity Support. We've received your request and will respond within 24 hours.

TICKET DETAILS:
Reference: {ticket_id}
Subject: {subject}
Category: {category.replace('_', ' ').title()}
Priority: {priority.title()}

Your Message:
{description}

---
This is an automated message from Pleerity Enterprise Ltd.
For support, contact {SUPPORT_EMAIL}
"""
        
        client.emails.send(
            From=f"Pleerity Support <{EMAIL_SENDER}>",
            To=customer_email,
            Subject=f"Support Ticket {ticket_id} - We've received your request",
            HtmlBody=html_body,
            TextBody=text_body,
            Tag="support-ticket-confirmation"
        )
        
        logger.info(f"Ticket confirmation email sent to {customer_email} for {ticket_id}")
        return True
        
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
    """
    Send internal notification to support team about new ticket.
    """
    client = get_postmark_client()
    if not client:
        logger.info(f"[MOCK EMAIL] Internal notification to {SUPPORT_EMAIL} for {ticket_id}")
        return False
    
    try:
        priority_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "urgent": "🔴"
        }.get(priority, "⚪")
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #1e293b; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .priority-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
        .priority-low {{ background: #dcfce7; color: #166534; }}
        .priority-medium {{ background: #fef9c3; color: #854d0e; }}
        .priority-high {{ background: #ffedd5; color: #c2410c; }}
        .priority-urgent {{ background: #fee2e2; color: #dc2626; }}
        .content {{ background: #f8fafc; padding: 20px; }}
        .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }}
        .info-box {{ background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; }}
        .label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .value {{ font-size: 14px; font-weight: 500; margin-top: 4px; }}
        .description {{ background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0; }}
        .transcript {{ background: #f1f5f9; border-radius: 6px; padding: 15px; margin: 20px 0; font-family: monospace; font-size: 12px; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }}
        .footer {{ padding: 15px; text-align: center; color: #64748b; font-size: 12px; }}
        .button {{ display: inline-block; background: #0d9488; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">🎫 New Support Ticket</h2>
            <p style="margin: 5px 0 0 0; opacity: 0.8; font-size: 14px;">{ticket_id}</p>
        </div>
        <div class="content">
            <div style="margin-bottom: 15px;">
                <span class="priority-badge priority-{priority}">{priority_emoji} {priority.upper()}</span>
            </div>
            
            <div class="info-grid">
                <div class="info-box">
                    <div class="label">Customer Email</div>
                    <div class="value">{customer_email or 'Not provided'}</div>
                </div>
                <div class="info-box">
                    <div class="label">CRN</div>
                    <div class="value">{customer_crn or 'Not provided'}</div>
                </div>
                <div class="info-box">
                    <div class="label">Category</div>
                    <div class="value">{category.replace('_', ' ').title()}</div>
                </div>
                <div class="info-box">
                    <div class="label">Service Area</div>
                    <div class="value">{service_area.replace('_', ' ').title()}</div>
                </div>
            </div>
            
            <div class="description">
                <div class="label">Subject</div>
                <h3 style="margin: 5px 0 15px 0;">{subject}</h3>
                <div class="label">Description</div>
                <p style="margin: 5px 0;">{description}</p>
            </div>
            
            {'<div class="transcript"><div class="label">Conversation Transcript</div><br/>' + transcript + '</div>' if transcript else ''}
            
            <center>
                <a href="{FRONTEND_URL}/admin/support" class="button">View in Admin Dashboard</a>
            </center>
        </div>
        <div class="footer">
            <p>Pleerity Enterprise Support System</p>
        </div>
    </div>
</body>
</html>
"""
        
        text_body = f"""
NEW SUPPORT TICKET - {ticket_id}
{'='*50}

Priority: {priority_emoji} {priority.upper()}
Category: {category.replace('_', ' ').title()}
Service Area: {service_area.replace('_', ' ').title()}

Customer Email: {customer_email or 'Not provided'}
Customer CRN: {customer_crn or 'Not provided'}

SUBJECT: {subject}

DESCRIPTION:
{description}

{'CONVERSATION TRANSCRIPT:' + chr(10) + transcript if transcript else ''}

---
View in Admin Dashboard: {FRONTEND_URL}/admin/support
"""
        
        client.emails.send(
            From=f"Pleerity Support System <{EMAIL_SENDER}>",
            To=SUPPORT_EMAIL,
            Subject=f"{priority_emoji} [{priority.upper()}] New Ticket: {subject[:50]}{'...' if len(subject) > 50 else ''} - {ticket_id}",
            HtmlBody=html_body,
            TextBody=text_body,
            Tag="support-internal-notification"
        )
        
        logger.info(f"Internal notification sent to {SUPPORT_EMAIL} for {ticket_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send internal notification: {e}")
        return False
