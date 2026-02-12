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
            message_log.provider_error_type = type(e).__name__
            message_log.provider_error_code = getattr(e, "code", None) or getattr(e, "error_code", None)
            if message_log.provider_error_code is not None:
                message_log.provider_error_code = str(message_log.provider_error_code)
            logger.error(f"Failed to send email to {recipient}: {e}")
        
        # Store message log (template_alias, client_id already set; provider fields for failures)
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
                "template": template_alias.value,
                "status": message_log.status,
                "postmark_id": message_log.postmark_message_id,
                "error": message_log.error_message,
                "provider_error_type": message_log.provider_error_type,
                "provider_error_code": message_log.provider_error_code,
            }
        )
        
        return message_log
    
    def _build_email_footer(self, model: Dict[str, Any]) -> str:
        """Build consistent email footer with CRN and company branding."""
        customer_ref = model.get('customer_reference', '')
        ref_line = f"<br><strong>Your Reference:</strong> {customer_ref}" if customer_ref else ""
        
        return f"""
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <div style="background-color: #f8fafc; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                    <p style="color: #64748b; font-size: 13px; margin: 0;">
                        {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                        {model.get('tagline', 'AI-Driven Solutions & Compliance')}{ref_line}
                    </p>
                </div>
        """

    def _build_html_body(self, template_alias: EmailTemplateAlias, model: Dict[str, Any]) -> str:
        """Build HTML email body based on template type."""
        footer = self._build_email_footer(model)
        
        if template_alias == EmailTemplateAlias.PASSWORD_SETUP:
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{customer_ref}</span></p>' if customer_ref else ""
            
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0B1D3A; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: #00B8A9; margin: 0;">Welcome to Compliance Vault Pro</h1>
                    {ref_badge}
                </div>
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    <p>Your compliance portal account has been created. Please set your password to get started.</p>
                    <p style="margin: 30px 0;">
                        <a href="{model.get('setup_link', '#')}" 
                           style="background-color: #00B8A9; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            Set Your Password
                        </a>
                    </p>
                    <p style="color: #666; font-size: 14px;">
                        This link will expire in 24 hours. If you didn't request this, please ignore this email.
                    </p>
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.PORTAL_READY:
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{customer_ref}</span></p>' if customer_ref else ""
            
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0B1D3A; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: #00B8A9; margin: 0;">Your Portal is Ready!</h1>
                    {ref_badge}
                </div>
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    <p>Great news! Your Compliance Vault Pro portal is now ready to use.</p>
                    <p style="margin: 30px 0;">
                        <a href="{model.get('portal_link', '#')}" 
                           style="background-color: #00B8A9; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            Access Your Portal
                        </a>
                    </p>
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.COMPLIANCE_ALERT:
            # Compliance status change alert
            footer = self._build_email_footer(model)
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-left: 10px;">{customer_ref}</span>' if customer_ref else ""
            
            status_color = model.get('status_color', '#dc2626')
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
                    <h1 style="margin: 0; display: inline-block;">⚠️ Compliance Alert</h1>{ref_badge}
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Action may be required for your properties</p>
                </div>
                
                <div style="background-color: #f8fafc; padding: 20px; border-radius: 0 0 8px 8px; border: 1px solid #e2e8f0; border-top: none;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    <p>The compliance status of one or more of your properties has changed and may require your attention.</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden;">
                        <thead>
                            <tr style="background-color: #0B1D3A; color: white;">
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
                           style="background-color: #00B8A9; color: white; padding: 12px 24px; 
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
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.TENANT_INVITE:
            footer = self._build_email_footer(model)
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0B1D3A; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: #00B8A9; margin: 0;">Tenant Portal Invitation</h1>
                </div>
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
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
                           style="background-color: #00B8A9; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            Set Up Your Access
                        </a>
                    </p>
                    <p style="color: #666; font-size: 14px;">
                        This link expires in 7 days. If you have questions, please contact your landlord.
                    </p>
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.SCHEDULED_REPORT:
            footer = self._build_email_footer(model)
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-left: 10px;">{customer_ref}</span>' if customer_ref else ""
            
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #0B1D3A 0%, #1a3a5c 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px; display: inline-block;">📊 Your {model.get('frequency', 'Weekly').title()} Compliance Report</h1>{ref_badge}
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
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.ADMIN_INVITE:
            footer = self._build_email_footer(model)
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #0B1D3A 0%, #00B8A9 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
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
                           style="background-color: #00B8A9; color: white; padding: 14px 28px; 
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
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.AI_EXTRACTION_APPLIED:
            # AI extraction applied notification
            footer = self._build_email_footer(model)
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-left: 10px;">{customer_ref}</span>' if customer_ref else ""
            
            status_color = model.get('status_color', '#22c55e')
            status_icon = "✅" if model.get('requirement_status') == 'COMPLIANT' else "⚠️" if model.get('requirement_status') == 'EXPIRING_SOON' else "❌"
            
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0B1D3A; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: #00B8A9; margin: 0; display: inline-block;">🤖 AI Document Analysis Complete</h1>
                    {ref_badge}
                </div>
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    <p>Good news! Our AI has successfully extracted and saved certificate details from your uploaded document.</p>
                    
                    <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h3 style="margin: 0 0 15px 0; color: #166534;">📋 Certificate Details Saved</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #64748b; width: 140px;">Property:</td>
                                <td style="padding: 8px 0; font-weight: bold;">{model.get('property_address', 'N/A')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b;">Document Type:</td>
                                <td style="padding: 8px 0; font-weight: bold;">{model.get('document_type', 'Certificate')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b;">Certificate No:</td>
                                <td style="padding: 8px 0; font-weight: bold; font-family: monospace;">{model.get('certificate_number', 'N/A')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b;">Expiry Date:</td>
                                <td style="padding: 8px 0; font-weight: bold;">{model.get('expiry_date', 'N/A')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #64748b;">Compliance Status:</td>
                                <td style="padding: 8px 0;">
                                    <span style="background-color: {status_color}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;">
                                        {status_icon} {model.get('requirement_status', 'UPDATED')}
                                    </span>
                                </td>
                            </tr>
                        </table>
                    </div>
                    
                    <p style="color: #64748b; font-size: 14px;">
                        <strong>What happens next?</strong><br>
                        • Your compliance dashboard has been updated automatically<br>
                        • You'll receive reminders before this certificate expires<br>
                        • You can review or edit these details in your portal
                    </p>
                    
                    <p style="margin: 25px 0;">
                        <a href="{model.get('portal_link', '#')}" 
                           style="background-color: #00B8A9; color: white; padding: 12px 24px; 
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            View in Dashboard
                        </a>
                    </p>
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.ORDER_DELIVERED:
            # Order documents delivered notification
            footer = self._build_email_footer(model)
            
            # Build documents list
            documents = model.get('documents', [])
            docs_html = ""
            if documents:
                docs_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
                for doc in documents:
                    doc_name = doc if isinstance(doc, str) else doc.get('name', 'Document')
                    docs_html += f"<li style='margin: 5px 0;'>{doc_name}</li>"
                docs_html += "</ul>"
            
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0B1D3A; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: #00B8A9; margin: 0;">📦 Your Documents Are Ready</h1>
                    <p style="color: #94a3b8; margin: 10px 0 0 0;">Order {model.get('order_reference', '')}</p>
                </div>
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    <p>Your <strong>{model.get('service_name', 'order')}</strong> is complete and your documents are ready for download!</p>
                    
                    <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 20px; margin: 20px 0;">
                        <p style="margin: 0 0 10px 0; font-weight: bold; color: #166534;">Included Documents:</p>
                        {docs_html}
                    </div>
                    
                    <p style="margin: 25px 0; text-align: center;">
                        <a href="{model.get('download_link', '#')}" 
                           style="background-color: #00B8A9; color: white; padding: 14px 28px; 
                                  text-decoration: none; border-radius: 6px; display: inline-block;
                                  font-weight: bold; font-size: 16px;">
                            Download Documents
                        </a>
                    </p>
                    
                    <p style="color: #64748b; font-size: 14px; text-align: center;">
                        Your documents are also available in your <a href="{model.get('portal_link', '#')}" style="color: #00B8A9;">portal dashboard</a>.
                    </p>
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.PENDING_VERIFICATION_DIGEST:
            count_pending = model.get("count_pending", 0)
            count_older_24h = model.get("count_older_24h", 0)
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0B1D3A; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: #00B8A9; margin: 0;">Pending verification digest</h1>
                </div>
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>Summary of documents awaiting admin verification (counts only):</p>
                    <ul>
                        <li><strong>Total UPLOADED:</strong> {count_pending}</li>
                        <li><strong>Older than 24 hours:</strong> {count_older_24h}</li>
                    </ul>
                    <p>Review the admin dashboard pending-verification list to process these documents.</p>
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.MONTHLY_DIGEST:
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0B1D3A; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: #00B8A9; margin: 0;">Monthly compliance digest</h1>
                </div>
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>Summary for the period (counts only):</p>
                    <ul>
                        <li><strong>Properties:</strong> {model.get('properties_count', 0)}</li>
                        <li><strong>Total requirements:</strong> {model.get('total_requirements', 0)}</li>
                        <li><strong>Compliant:</strong> {model.get('compliant', 0)}</li>
                        <li><strong>Overdue:</strong> {model.get('overdue', 0)}</li>
                        <li><strong>Expiring soon:</strong> {model.get('expiring_soon', 0)}</li>
                        <li><strong>Documents uploaded (period):</strong> {model.get('documents_uploaded', 0)}</li>
                    </ul>
                    <p>Period: {model.get('period_start', '')} to {model.get('period_end', '')}</p>
                </div>
                {self._build_email_footer(model)}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.CLEARFORM_WELCOME:
            # Use the dedicated ClearForm method
            return self._build_clearform_welcome_html(model)
        else:
            # Generic template
            footer = self._build_email_footer(model)
            customer_ref = model.get('customer_reference', '')
            ref_line = f"<p>Your Reference: <strong>{customer_ref}</strong></p>" if customer_ref else ""
            
            return f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #0B1D3A; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: #00B8A9; margin: 0;">Compliance Vault Pro</h1>
                </div>
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>Hello {model.get('client_name', 'there')},</p>
                    {ref_line}
                    <p>{model.get('message', 'You have a new notification from Compliance Vault Pro.')}</p>
                </div>
                {footer}
            </body>
            </html>
            """
    
    def _build_text_footer(self, model: Dict[str, Any]) -> str:
        """Build consistent plain text footer with CRN."""
        customer_ref = model.get('customer_reference', '')
        ref_line = f"\nYour Reference: {customer_ref}" if customer_ref else ""
        
        return f"""
--
{model.get('company_name', 'Pleerity Enterprise Ltd')}
{model.get('tagline', 'AI-Driven Solutions & Compliance')}{ref_line}
        """

    def _build_text_body(self, template_alias: EmailTemplateAlias, model: Dict[str, Any]) -> str:
        """Build plain text email body based on template type."""
        footer = self._build_text_footer(model)
        customer_ref = model.get('customer_reference', '')
        ref_line = f"\nYour Reference: {customer_ref}" if customer_ref else ""
        
        if template_alias == EmailTemplateAlias.PASSWORD_SETUP:
            return f"""
Welcome to Compliance Vault Pro
{ref_line}

Hello {model.get('client_name', 'there')},

Your compliance portal account has been created. Please set your password to get started.

Set your password here: {model.get('setup_link', '#')}

This link will expire in 24 hours. If you didn't request this, please ignore this email.
{footer}
            """
        elif template_alias == EmailTemplateAlias.PORTAL_READY:
            return f"""
Your Portal is Ready!
{ref_line}

Hello {model.get('client_name', 'there')},

Great news! Your Compliance Vault Pro portal is now ready to use.

Access your portal here: {model.get('portal_link', '#')}
{footer}
            """
        elif template_alias == EmailTemplateAlias.COMPLIANCE_ALERT:
            properties_text = ""
            for prop in model.get('affected_properties', []):
                properties_text += f"- {prop.get('address', 'N/A')}: {prop.get('previous_status', 'GREEN')} → {prop.get('new_status', 'RED')} ({prop.get('reason', 'Status changed')})\n"
            
            return f"""
⚠️ COMPLIANCE ALERT - Action Required
{ref_line}

Hello {model.get('client_name', 'there')},

The compliance status of one or more of your properties has changed and may require your attention.

AFFECTED PROPERTIES:
{properties_text}

View your dashboard: {model.get('portal_link', '#')}

WHAT THIS MEANS:
• GREEN = All requirements are compliant
• AMBER = Some requirements are expiring soon  
• RED = Immediate action required
{footer}
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
{footer}
            """
        elif template_alias == EmailTemplateAlias.AI_EXTRACTION_APPLIED:
            status_icon = "✅" if model.get('requirement_status') == 'COMPLIANT' else "⚠️" if model.get('requirement_status') == 'EXPIRING_SOON' else "❌"
            return f"""
🤖 AI DOCUMENT ANALYSIS COMPLETE
{ref_line}

Hello {model.get('client_name', 'there')},

Good news! Our AI has successfully extracted and saved certificate details from your uploaded document.

📋 CERTIFICATE DETAILS SAVED
----------------------------
Property:         {model.get('property_address', 'N/A')}
Document Type:    {model.get('document_type', 'Certificate')}
Certificate No:   {model.get('certificate_number', 'N/A')}
Expiry Date:      {model.get('expiry_date', 'N/A')}
Status:           {status_icon} {model.get('requirement_status', 'UPDATED')}

WHAT HAPPENS NEXT:
• Your compliance dashboard has been updated automatically
• You'll receive reminders before this certificate expires
• You can review or edit these details in your portal

View in Dashboard: {model.get('portal_link', '#')}
{footer}
            """
        elif template_alias == EmailTemplateAlias.ORDER_DELIVERED:
            # Build documents list for text
            documents = model.get('documents', [])
            docs_text = ""
            for doc in documents:
                doc_name = doc if isinstance(doc, str) else doc.get('name', 'Document')
                docs_text += f"  • {doc_name}\n"
            
            return f"""
📦 YOUR DOCUMENTS ARE READY
===========================
Order Reference: {model.get('order_reference', '')}

Hello {model.get('client_name', 'there')},

Your {model.get('service_name', 'order')} is complete and your documents are ready!

INCLUDED DOCUMENTS:
-------------------
{docs_text}

Download your documents here:
{model.get('download_link', '#')}

Your documents are also available in your portal dashboard:
{model.get('portal_link', '#')}

Need help? Contact us at info@pleerityenterprise.co.uk
{footer}
            """
        elif template_alias == EmailTemplateAlias.PENDING_VERIFICATION_DIGEST:
            count_pending = model.get("count_pending", 0)
            count_older_24h = model.get("count_older_24h", 0)
            return f"""
PENDING VERIFICATION DIGEST
==========================

Summary of documents awaiting admin verification (counts only):

- Total UPLOADED: {count_pending}
- Older than 24 hours: {count_older_24h}

Review the admin dashboard pending-verification list to process these documents.
{footer}
            """
        elif template_alias == EmailTemplateAlias.MONTHLY_DIGEST:
            return f"""
MONTHLY COMPLIANCE DIGEST
========================

Summary for the period (counts only):

- Properties: {model.get('properties_count', 0)}
- Total requirements: {model.get('total_requirements', 0)}
- Compliant: {model.get('compliant', 0)}
- Overdue: {model.get('overdue', 0)}
- Expiring soon: {model.get('expiring_soon', 0)}
- Documents uploaded (period): {model.get('documents_uploaded', 0)}

Period: {model.get('period_start', '')} to {model.get('period_end', '')}
{footer}
            """
        elif template_alias == EmailTemplateAlias.CLEARFORM_WELCOME:
            return f"""
WELCOME TO CLEARFORM BY PLEERITY
================================

Hello {model.get('full_name', 'there')},

Welcome to ClearForm. Your account is ready, and we've added some starter credits 
to help you get going.

ClearForm helps you create professional paperwork without stress or mistakes. 
Just tell us what you need in plain English, and we'll generate a properly 
formatted document for you.

YOUR CREDIT BALANCE: {model.get('credit_balance', 5)} credits

Each document costs 1 credit. You can always add more credits later if you need them.

Create Your First Document: {model.get('dashboard_link', '#')}

---
Important: ClearForm is an assistive tool to help you draft documents. 
Always review the output and seek professional advice for legal matters.

--
{model.get('company_name', 'Pleerity Enterprise Ltd')}
{model.get('tagline', 'AI-Driven Solutions & Compliance')}
            """
        else:
            return f"""
Compliance Vault Pro
{ref_line}

Hello {model.get('client_name', 'there')},

{model.get('message', 'You have a new notification from Compliance Vault Pro.')}
{footer}

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
    ) -> MessageLog:
        """Send password setup email. Returns MessageLog so callers can check status."""
        return await self.send_email(
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
    
    async def send_admin_invite_email(
        self,
        recipient: str,
        admin_name: str,
        inviter_name: str,
        setup_link: str
    ):
        """Send admin invitation email."""
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.ADMIN_INVITE,
            template_model={
                "admin_name": admin_name,
                "inviter_name": inviter_name,
                "setup_link": setup_link,
                "company_name": "Pleerity Enterprise Ltd"
            },
            client_id=None,  # Admin invites are not client-specific
            subject="🛡️ You've Been Invited to Join Compliance Vault Pro as an Admin"
        )
    
    async def send_ai_extraction_email(
        self,
        recipient: str,
        client_name: str,
        client_id: str,
        customer_reference: str,
        property_address: str,
        document_type: str,
        certificate_number: str,
        expiry_date: str,
        requirement_status: str,
        portal_link: str
    ):
        """Send AI extraction applied notification email.
        
        Called after a user reviews and applies AI-extracted certificate data.
        """
        # Determine status color for email styling
        status_colors = {
            'COMPLIANT': '#22c55e',
            'EXPIRING_SOON': '#f59e0b',
            'OVERDUE': '#dc2626'
        }
        status_color = status_colors.get(requirement_status, '#64748b')
        
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.AI_EXTRACTION_APPLIED,
            template_model={
                "client_name": client_name,
                "customer_reference": customer_reference,
                "property_address": property_address,
                "document_type": document_type,
                "certificate_number": certificate_number,
                "expiry_date": expiry_date,
                "requirement_status": requirement_status,
                "status_color": status_color,
                "portal_link": portal_link,
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance"
            },
            client_id=client_id,
            subject="🤖 AI Document Analysis Complete - Certificate Details Saved"
        )

    # =========================================================================
    # Subscription Lifecycle Emails
    # =========================================================================
    
    async def send_payment_received_email(
        self,
        recipient: str,
        client_name: str,
        client_id: str,
        plan_name: str,
        amount: str,
        portal_link: str
    ):
        """
        Send payment received / provisioning started email.
        
        Sent after checkout.session.completed webhook.
        Confirms payment and informs about provisioning.
        """
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.PAYMENT_RECEIVED,
            template_model={
                "client_name": client_name,
                "plan_name": plan_name,
                "amount": amount,
                "portal_link": portal_link,
                "company_name": "Pleerity Enterprise Ltd",
                "support_email": "info@pleerityenterprise.co.uk"
            },
            client_id=client_id,
            subject="✅ Payment Received - Compliance Vault Pro"
        )
        
        logger.info(f"Payment received email sent to {recipient} for client {client_id}")
    
    async def send_payment_failed_email(
        self,
        recipient: str,
        client_name: str,
        client_id: str,
        billing_portal_link: str,
        retry_date: Optional[str] = None
    ):
        """
        Send payment failed notification.
        
        Sent after invoice.payment_failed webhook.
        Includes link to update payment method.
        No scare language per specification.
        """
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.PAYMENT_FAILED,
            template_model={
                "client_name": client_name,
                "billing_portal_link": billing_portal_link,
                "retry_date": retry_date or "soon",
                "company_name": "Pleerity Enterprise Ltd",
                "support_email": "info@pleerityenterprise.co.uk"
            },
            client_id=client_id,
            subject="⚠️ Payment Update Required - Compliance Vault Pro"
        )
        
        logger.info(f"Payment failed email sent to {recipient} for client {client_id}")
    
    async def send_renewal_reminder_email(
        self,
        recipient: str,
        client_name: str,
        client_id: str,
        plan_name: str,
        renewal_date: str,
        amount: str,
        billing_portal_link: str
    ):
        """
        Send upcoming renewal reminder (7 days before renewal).
        
        Sent by scheduled job when current_period_end is within 7 days.
        """
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.RENEWAL_REMINDER,
            template_model={
                "client_name": client_name,
                "plan_name": plan_name,
                "renewal_date": renewal_date,
                "amount": amount,
                "billing_portal_link": billing_portal_link,
                "company_name": "Pleerity Enterprise Ltd",
                "support_email": "info@pleerityenterprise.co.uk"
            },
            client_id=client_id,
            subject="📅 Subscription Renewal Reminder - Compliance Vault Pro"
        )
        
        logger.info(f"Renewal reminder email sent to {recipient} for client {client_id}")
    
    async def send_subscription_canceled_email(
        self,
        recipient: str,
        client_name: str,
        client_id: str,
        access_end_date: str,
        billing_portal_link: str
    ):
        """
        Send subscription cancellation confirmation.
        
        Sent after customer.subscription.deleted webhook
        or when cancel_at_period_end is set.
        """
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.SUBSCRIPTION_CANCELED,
            template_model={
                "client_name": client_name,
                "access_end_date": access_end_date,
                "billing_portal_link": billing_portal_link,
                "company_name": "Pleerity Enterprise Ltd",
                "support_email": "info@pleerityenterprise.co.uk"
            },
            client_id=client_id,
            subject="Subscription Update - Compliance Vault Pro"
        )
        
        logger.info(f"Subscription canceled email sent to {recipient} for client {client_id}")
    
    # ================================================================================
    # CLEARFORM EMAIL METHODS
    # ================================================================================
    
    async def send_clearform_welcome_email(
        self,
        recipient: str,
        full_name: str,
        user_id: str,
        credit_balance: int = 5,
        dashboard_link: str = None
    ):
        """
        Send ClearForm welcome email after account creation.
        
        Brand: ClearForm by Pleerity
        Tone: Calm, reassuring, plain English
        """
        if dashboard_link is None:
            frontend_url = os.getenv("FRONTEND_URL", "https://pleerityenterprise.co.uk")
            dashboard_link = f"{frontend_url}/clearform/dashboard"
        
        await self.send_email(
            recipient=recipient,
            template_alias=EmailTemplateAlias.CLEARFORM_WELCOME,
            template_model={
                "full_name": full_name,
                "credit_balance": credit_balance,
                "dashboard_link": dashboard_link,
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance"
            },
            client_id=None,  # ClearForm uses user_id, not client_id
            subject="Welcome to ClearForm by Pleerity"
        )
        
        logger.info(f"ClearForm welcome email sent to {recipient} for user {user_id}")
    
    def _build_clearform_welcome_html(self, model: dict) -> str:
        """Build ClearForm welcome email HTML."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f8fafc;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background-color: #0B1D3A; padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="color: #00B8A9; margin: 0; font-size: 24px; font-weight: 700;">
                ClearForm <span style="color: #ffffff; font-weight: 400;">by Pleerity</span>
            </h1>
            <p style="color: #94a3b8; margin: 10px 0 0 0; font-size: 14px;">
                Professional paperwork, without the stress
            </p>
        </div>
        
        <!-- Main Content -->
        <div style="background-color: #ffffff; padding: 30px; border: 1px solid #e2e8f0; border-top: none;">
            <p style="color: #1e293b; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                Hello {model.get('full_name', 'there')},
            </p>
            
            <p style="color: #475569; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                Welcome to ClearForm. Your account is ready, and we've added some starter credits to help you get going.
            </p>
            
            <p style="color: #475569; font-size: 15px; line-height: 1.6; margin: 0 0 25px 0;">
                ClearForm helps you create professional paperwork without stress or mistakes. Just tell us what you need in plain English, and we'll generate a properly formatted document for you.
            </p>
            
            <!-- Credit Balance Box -->
            <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 25px;">
                <p style="color: #166534; font-size: 14px; margin: 0 0 5px 0; text-transform: uppercase; letter-spacing: 0.5px;">
                    Your Credit Balance
                </p>
                <p style="color: #15803d; font-size: 36px; font-weight: 700; margin: 0;">
                    {model.get('credit_balance', 5)} credits
                </p>
            </div>
            
            <!-- CTA Button -->
            <div style="text-align: center; margin: 30px 0;">
                <a href="{model.get('dashboard_link', '#')}" 
                   style="display: inline-block; background-color: #10b981; color: #ffffff; 
                          padding: 14px 32px; text-decoration: none; border-radius: 8px; 
                          font-weight: 600; font-size: 15px;">
                    Create Your First Document
                </a>
            </div>
            
            <p style="color: #64748b; font-size: 14px; line-height: 1.6; margin: 25px 0 0 0;">
                Each document costs 1 credit. You can always add more credits later if you need them.
            </p>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f8fafc; padding: 20px 30px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin: 0 0 10px 0; text-align: center;">
                <strong style="color: #64748b;">Important:</strong> ClearForm is an assistive tool to help you draft documents. 
                Always review the output and seek professional advice for legal matters.
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 15px 0;">
            <p style="color: #94a3b8; font-size: 12px; margin: 0; text-align: center;">
                {model.get('company_name', 'Pleerity Enterprise Ltd')}<br>
                {model.get('tagline', 'AI-Driven Solutions & Compliance')}
            </p>
        </div>
    </div>
</body>
</html>
        """

email_service = EmailService()
