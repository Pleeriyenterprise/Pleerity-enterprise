from postmarker.core import PostmarkClient
from database import database
from models import MessageLog, EmailTemplateAlias, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Email sender configuration
# Verified sender in Postmark
DEFAULT_SENDER = os.getenv("EMAIL_SENDER", "info@pleerityenterprise.co.uk")

class EmailService:
    def __init__(self):
        postmark_token = os.getenv("POSTMARK_SERVER_TOKEN")
        if not postmark_token:
            logger.warning("POSTMARK_SERVER_TOKEN not set - emails will be logged but not sent")
            self.client = None
        else:
            self.client = PostmarkClient(server_token=postmark_token)
            logger.info("Postmark email client initialized")
    
    async def send_email(
        self,
        recipient: str,
        template_alias: EmailTemplateAlias,
        template_model: Dict[str, Any],
        client_id: Optional[str] = None,
        subject: str = "Compliance Vault Pro"
    ) -> MessageLog:
        """Send an email using database template, Postmark template, or fallback to built-in."""
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
                # First try to get template from database
                db_template = await db.email_templates.find_one(
                    {"alias": template_alias.value, "is_active": True},
                    {"_id": 0}
                )
                
                if db_template:
                    # Use database template
                    html_body = db_template["html_body"]
                    text_body = db_template["text_body"]
                    email_subject = db_template["subject"]
                    
                    # Replace placeholders
                    for key, value in template_model.items():
                        placeholder = "{{" + key + "}}"
                        html_body = html_body.replace(placeholder, str(value))
                        text_body = text_body.replace(placeholder, str(value))
                        email_subject = email_subject.replace(placeholder, str(value))
                    
                    try:
                        response = self.client.emails.send(
                            From=DEFAULT_SENDER,
                            To=recipient,
                            Subject=email_subject,
                            HtmlBody=html_body,
                            TextBody=text_body,
                            TrackOpens=True,
                            TrackLinks="HtmlOnly",
                            Tag=template_alias.value
                        )
                        
                        message_log.postmark_message_id = response["MessageID"]
                        message_log.status = "sent"
                        message_log.sent_at = datetime.now(timezone.utc)
                        message_log.subject = email_subject
                        
                        logger.info(f"Database template email sent to {recipient}: {response['MessageID']}")
                    except Exception as send_error:
                        raise send_error
                else:
                    # Fallback to built-in HTML templates
                    html_body = self._build_html_body(template_alias, template_model)
                    text_body = self._build_text_body(template_alias, template_model)
                    
                    try:
                        response = self.client.emails.send(
                            From=DEFAULT_SENDER,
                            To=recipient,
                            Subject=subject,
                            HtmlBody=html_body,
                            TextBody=text_body,
                            TrackOpens=True,
                            TrackLinks="HtmlOnly",
                            Tag=template_alias.value
                        )
                        
                        message_log.postmark_message_id = response["MessageID"]
                        message_log.status = "sent"
                        message_log.sent_at = datetime.now(timezone.utc)
                        
                        logger.info(f"Built-in template email sent to {recipient}: {response['MessageID']}")
                    except Exception as send_error:
                        raise send_error
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
                "status": message_log.status,
                "postmark_id": message_log.postmark_message_id,
                "error": message_log.error_message
            }
        )
        
        return message_log
    
    def _build_html_body(self, template_alias: EmailTemplateAlias, model: Dict[str, Any]) -> str:
        """Build HTML email body based on template type."""
        if template_alias == EmailTemplateAlias.PASSWORD_SETUP:
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #1a2744;">Welcome to Compliance Vault Pro</h1>
                <p>Hello {model.get('client_name', 'there')},</p>
                <p>Your compliance portal account has been created. Please set your password to get started.</p>
                <p style="margin: 30px 0;">
                    <a href="{model.get('setup_link', '#')}" 
                       style="background-color: #14b8a6; color: white; padding: 12px 24px; 
                              text-decoration: none; border-radius: 6px; display: inline-block;">
                        Set Your Password
                    </a>
                </p>
                <p style="color: #666; font-size: 14px;">
                    This link will expire in 24 hours. If you didn't request this, please ignore this email.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                    {model.get('tagline', 'AI-Driven Solutions & Compliance')}
                </p>
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.PORTAL_READY:
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #1a2744;">Your Portal is Ready!</h1>
                <p>Hello {model.get('client_name', 'there')},</p>
                <p>Great news! Your Compliance Vault Pro portal is now ready to use.</p>
                <p style="margin: 30px 0;">
                    <a href="{model.get('portal_link', '#')}" 
                       style="background-color: #14b8a6; color: white; padding: 12px 24px; 
                              text-decoration: none; border-radius: 6px; display: inline-block;">
                        Access Your Portal
                    </a>
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                    {model.get('tagline', 'AI-Driven Solutions & Compliance')}
                </p>
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.COMPLIANCE_ALERT:
            # Compliance status change alert
            status_color = model.get('status_color', '#dc2626')
            new_status = model.get('new_status', 'RED')
            properties_html = ""
            for prop in model.get('affected_properties', []):
                properties_html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{prop.get('address', 'N/A')}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">
                        <span style="color: {prop.get('prev_color', '#22c55e')}; font-weight: bold;">{prop.get('previous_status', 'GREEN')}</span>
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">
                        <span style="color: {prop.get('new_color', '#dc2626')}; font-weight: bold;">{prop.get('new_status', 'RED')}</span>
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{prop.get('reason', 'Status changed')}</td>
                </tr>
                """
            
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: {status_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0;">⚠️ Compliance Alert</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Action may be required for your properties</p>
                </div>
                
                <div style="background-color: #f8fafc; padding: 20px; border-radius: 0 0 8px 8px; border: 1px solid #e2e8f0; border-top: none;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    <p>The compliance status of one or more of your properties has changed and may require your attention.</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden;">
                        <thead>
                            <tr style="background-color: #1a2744; color: white;">
                                <th style="padding: 12px; text-align: left;">Property</th>
                                <th style="padding: 12px; text-align: center;">Previous</th>
                                <th style="padding: 12px; text-align: center;">Current</th>
                                <th style="padding: 12px; text-align: left;">Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            {properties_html}
                        </tbody>
                    </table>
                    
                    <p style="margin: 20px 0;">
                        <a href="{model.get('portal_link', '#')}" 
                           style="background-color: #14b8a6; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            View Dashboard
                        </a>
                    </p>
                    
                    <p style="color: #64748b; font-size: 14px;">
                        <strong>What this means:</strong><br>
                        • <span style="color: #22c55e;">GREEN</span> = All requirements are compliant<br>
                        • <span style="color: #f59e0b;">AMBER</span> = Some requirements are expiring soon<br>
                        • <span style="color: #dc2626;">RED</span> = Immediate action required
                    </p>
                </div>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                    {model.get('tagline', 'AI-Driven Solutions & Compliance')}
                </p>
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.TENANT_INVITE:
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #1a2744;">Tenant Portal Invitation</h1>
                <p>Hello {model.get('tenant_name', 'there')},</p>
                <p>Your landlord has invited you to view the compliance status of your rental property.</p>
                <p>The tenant portal allows you to:</p>
                <ul style="color: #64748b;">
                    <li>View property compliance status (GREEN/AMBER/RED)</li>
                    <li>See certificate expiry dates</li>
                    <li>Track overall compliance health</li>
                </ul>
                <p style="margin: 30px 0;">
                    <a href="{model.get('setup_link', '#')}" 
                       style="background-color: #14b8a6; color: white; padding: 12px 24px; 
                              text-decoration: none; border-radius: 6px; display: inline-block;">
                        Set Up Your Access
                    </a>
                </p>
                <p style="color: #666; font-size: 14px;">
                    This link expires in 7 days. If you have questions, please contact your landlord.
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                    {model.get('tagline', 'AI-Driven Solutions & Compliance')}
                </p>
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.SCHEDULED_REPORT:
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #1a2744 0%, #2d3a5c 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">📊 Your {model.get('frequency', 'Weekly').title()} Compliance Report</h1>
                    <p style="margin: 10px 0 0; opacity: 0.9;">Generated on {model.get('generated_date', 'today')}</p>
                </div>
                <div style="border: 1px solid #eee; border-top: 0; padding: 20px; background: white;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    <p>Please find your scheduled <strong>{model.get('report_type', 'compliance')}</strong> report below.</p>
                    
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0; font-family: monospace; font-size: 12px; white-space: pre-wrap; overflow-x: auto;">
{model.get('report_content', 'Report data will appear here.')[:1500]}
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">
                        For the full report with all details, please log in to your dashboard 
                        and download the complete report from the Reports section.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="color: #999; font-size: 12px;">
                        This is an automated {model.get('frequency', 'weekly')} report. 
                        To change your report preferences, visit your dashboard settings.<br><br>
                        {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                        AI-Driven Solutions & Compliance
                    </p>
                </div>
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.ADMIN_INVITE:
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #1a2744 0%, #14b8a6 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">🛡️ Admin Invitation</h1>
                    <p style="margin: 10px 0 0; opacity: 0.9;">You've been invited to join as an administrator</p>
                </div>
                <div style="border: 1px solid #eee; border-top: 0; padding: 20px; background: white; border-radius: 0 0 8px 8px;">
                    <p>Hello {model.get('admin_name', 'there')},</p>
                    <p>You have been invited by <strong>{model.get('inviter_name', 'an administrator')}</strong> to join Compliance Vault Pro as an <strong>Administrator</strong>.</p>
                    
                    <p>As an admin, you will have access to:</p>
                    <ul style="color: #64748b;">
                        <li>Full system management dashboard</li>
                        <li>All client accounts and properties</li>
                        <li>Audit logs and compliance reports</li>
                        <li>System configuration and settings</li>
                    </ul>
                    
                    <p style="margin: 30px 0;">
                        <a href="{model.get('setup_link', '#')}" 
                           style="background-color: #14b8a6; color: white; padding: 14px 28px; 
                                  text-decoration: none; border-radius: 6px; display: inline-block;
                                  font-weight: bold;">
                            Set Up Your Admin Account
                        </a>
                    </p>
                    
                    <p style="color: #dc2626; font-size: 14px; font-weight: bold;">
                        ⏰ This invitation expires in 24 hours.
                    </p>
                    
                    <p style="color: #666; font-size: 14px;">
                        If you did not expect this invitation or have questions, please contact the system administrator.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="color: #999; font-size: 12px;">
                        {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                        AI-Driven Solutions & Compliance
                    </p>
                </div>
            </body>
            </html>
            """
        else:
            # Generic template
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #1a2744;">Compliance Vault Pro</h1>
                <p>Hello {model.get('client_name', 'there')},</p>
                <p>{model.get('message', 'You have a new notification from Compliance Vault Pro.')}</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                    {model.get('tagline', 'AI-Driven Solutions & Compliance')}
                </p>
            </body>
            </html>
            """
    
    def _build_text_body(self, template_alias: EmailTemplateAlias, model: Dict[str, Any]) -> str:
        """Build plain text email body based on template type."""
        if template_alias == EmailTemplateAlias.PASSWORD_SETUP:
            return f"""
Welcome to Compliance Vault Pro

Hello {model.get('client_name', 'there')},

Your compliance portal account has been created. Please set your password to get started.

Set your password here: {model.get('setup_link', '#')}

This link will expire in 24 hours. If you didn't request this, please ignore this email.

--
{model.get('company_name', 'Pleerity Enterprise Ltd')}
{model.get('tagline', 'AI-Driven Solutions & Compliance')}
            """
        elif template_alias == EmailTemplateAlias.PORTAL_READY:
            return f"""
Your Portal is Ready!

Hello {model.get('client_name', 'there')},

Great news! Your Compliance Vault Pro portal is now ready to use.

Access your portal here: {model.get('portal_link', '#')}

--
{model.get('company_name', 'Pleerity Enterprise Ltd')}
{model.get('tagline', 'AI-Driven Solutions & Compliance')}
            """
        elif template_alias == EmailTemplateAlias.COMPLIANCE_ALERT:
            properties_text = ""
            for prop in model.get('affected_properties', []):
                properties_text += f"- {prop.get('address', 'N/A')}: {prop.get('previous_status', 'GREEN')} → {prop.get('new_status', 'RED')} ({prop.get('reason', 'Status changed')})\n"
            
            return f"""
⚠️ COMPLIANCE ALERT - Action Required

Hello {model.get('client_name', 'there')},

The compliance status of one or more of your properties has changed and may require your attention.

AFFECTED PROPERTIES:
{properties_text}

View your dashboard: {model.get('portal_link', '#')}

WHAT THIS MEANS:
• GREEN = All requirements are compliant
• AMBER = Some requirements are expiring soon  
• RED = Immediate action required

--
{model.get('company_name', 'Pleerity Enterprise Ltd')}
{model.get('tagline', 'AI-Driven Solutions & Compliance')}
            """
        elif template_alias == EmailTemplateAlias.ADMIN_INVITE:
            return f"""
🛡️ ADMIN INVITATION - Compliance Vault Pro

Hello {model.get('admin_name', 'there')},

You have been invited by {model.get('inviter_name', 'an administrator')} to join Compliance Vault Pro as an Administrator.

As an admin, you will have access to:
• Full system management dashboard
• All client accounts and properties
• Audit logs and compliance reports
• System configuration and settings

Set up your admin account here: {model.get('setup_link', '#')}

⏰ This invitation expires in 24 hours.

If you did not expect this invitation, please contact the system administrator.

--
{model.get('company_name', 'Pleerity Enterprise Ltd')}
AI-Driven Solutions & Compliance
            """
        else:
            return f"""
Compliance Vault Pro

Hello {model.get('client_name', 'there')},

{model.get('message', 'You have a new notification from Compliance Vault Pro.')}

--
{model.get('company_name', 'Pleerity Enterprise Ltd')}
{model.get('tagline', 'AI-Driven Solutions & Compliance')}
            """
    
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
    
    async def send_compliance_alert_email(
        self,
        recipient: str,
        client_name: str,
        affected_properties: list,
        portal_link: str,
        client_id: str
    ):
        """Send compliance status change alert."""
        # Determine the most severe status for the subject line
        has_red = any(p.get('new_status') == 'RED' for p in affected_properties)
        has_amber = any(p.get('new_status') == 'AMBER' for p in affected_properties)
        
        if has_red:
            subject = "🔴 Urgent: Compliance Status Changed to RED"
            status_color = "#dc2626"
        elif has_amber:
            subject = "🟡 Attention: Compliance Status Changed to AMBER"
            status_color = "#f59e0b"
        else:
            subject = "Compliance Status Update"
            status_color = "#64748b"
        
        # Add color info to properties
        for prop in affected_properties:
            prop['prev_color'] = {'GREEN': '#22c55e', 'AMBER': '#f59e0b', 'RED': '#dc2626'}.get(prop.get('previous_status'), '#64748b')
            prop['new_color'] = {'GREEN': '#22c55e', 'AMBER': '#f59e0b', 'RED': '#dc2626'}.get(prop.get('new_status'), '#64748b')
        
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.COMPLIANCE_ALERT,
            template_model={
                "client_name": client_name,
                "affected_properties": affected_properties,
                "portal_link": portal_link,
                "status_color": status_color,
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance"
            },
            client_id=client_id,
            subject=subject
        )

email_service = EmailService()
