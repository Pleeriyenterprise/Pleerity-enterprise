from postmarker.core import PostmarkClient
from database import database
from models import MessageLog, EmailTemplateAlias, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        postmark_token = os.getenv("POSTMARK_SERVER_TOKEN")
        if not postmark_token:
            logger.warning("POSTMARK_SERVER_TOKEN not set - emails will be logged but not sent")
            self.client = None
        else:
            self.client = PostmarkClient(server_token=postmark_token)
    
    async def send_email(
        self,
        recipient: str,
        template_alias: EmailTemplateAlias,
        template_model: Dict[str, Any],
        client_id: Optional[str] = None,
        subject: str = "Compliance Vault Pro"
    ) -> MessageLog:
        """Send an email using Postmark template."""
        db = database.get_db()
        
        # Create message log
        message_log = MessageLog(
            client_id=client_id,
            recipient=recipient,
            template_alias=template_alias,
            subject=subject,
            status="queued"
        )
        
        try:
            if self.client:
                # Send via Postmark
                response = self.client.emails.send_with_template(
                    From="noreply@compliancevaultpro.com",
                    To=recipient,
                    TemplateAlias=template_alias.value,
                    TemplateModel=template_model,
                    TrackOpens=True,
                    TrackLinks="HtmlOnly",
                    Tag=template_alias.value
                )
                
                message_log.postmark_message_id = response["MessageID"]
                message_log.status = "sent"
                message_log.sent_at = datetime.now(timezone.utc)
                
                logger.info(f"Email sent to {recipient}: {response['MessageID']}")
            else:
                # Dev mode - just log
                message_log.status = "sent"
                message_log.sent_at = datetime.now(timezone.utc)
                logger.info(f"[DEV MODE] Email logged (not sent) to {recipient}")
        
        except Exception as e:
            message_log.status = "failed"
            message_log.error_message = str(e)
            logger.error(f"Failed to send email to {recipient}: {e}")
        
        # Store message log
        doc = message_log.model_dump()
        for key in ["created_at", "sent_at", "delivered_at", "opened_at", "bounced_at"]:
            if doc.get(key) and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()
        
        await db.message_logs.insert_one(doc)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.EMAIL_SENT if message_log.status == "sent" else AuditAction.EMAIL_FAILED,
            client_id=client_id,
            metadata={
                "recipient": recipient,
                "template": template_alias.value,
                "status": message_log.status
            }
        )
        
        return message_log
    
    async def send_password_setup_email(
        self,
        recipient: str,
        client_name: str,
        setup_link: str,
        client_id: str
    ):
        """Send password setup email."""
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.PASSWORD_SETUP,
            template_model={
                "client_name": client_name,
                "setup_link": setup_link,
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance"
            },
            client_id=client_id,
            subject="Set Up Your Compliance Vault Pro Account"
        )
    
    async def send_portal_ready_email(
        self,
        recipient: str,
        client_name: str,
        portal_link: str,
        client_id: str
    ):
        """Send portal ready notification."""
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.PORTAL_READY,
            template_model={
                "client_name": client_name,
                "portal_link": portal_link,
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance"
            },
            client_id=client_id,
            subject="Your Compliance Vault Pro Portal is Ready"
        )

email_service = EmailService()
