from postmarker.core import PostmarkClient
from database import database
from models import MessageLog, EmailTemplateAlias, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
import html as html_module
import os
import logging
from typing import Optional, Dict, Any, List

from email_templates.email_layout import build_customer_email_layout

logger = logging.getLogger(__name__)

# Email sender configuration
# Verified sender in Postmark
DEFAULT_SENDER = os.getenv("EMAIL_SENDER", "info@pleerityenterprise.co.uk")

# Base URL for client portal (notification preferences link). Use FRONTEND_URL or PORTAL_BASE_URL.
def _notification_preferences_url(model: Dict[str, Any]) -> str:
    base = (model.get("portal_base_url") or os.getenv("FRONTEND_URL") or os.getenv("PORTAL_BASE_URL") or "").strip().rstrip("/")
    if base:
        return base + "/settings/notifications"
    return ""

# Aliases that must not show "Manage notification preferences" (system_critical).
SYSTEM_CRITICAL_ALIASES = {
    EmailTemplateAlias.PASSWORD_SETUP,
    EmailTemplateAlias.PASSWORD_RESET,
    EmailTemplateAlias.PASSWORD_CHANGED_CONFIRMATION,
    EmailTemplateAlias.PORTAL_READY,
    EmailTemplateAlias.ADMIN_INVITE,
    EmailTemplateAlias.TENANT_INVITE,
    EmailTemplateAlias.ORDER_DELIVERED,
    EmailTemplateAlias.PAYMENT_RECEIVED,
    EmailTemplateAlias.PAYMENT_FAILED,
    EmailTemplateAlias.SUBSCRIPTION_CANCELED,
    EmailTemplateAlias.CLEARFORM_WELCOME,
    EmailTemplateAlias.INTERNAL_ALERT,
}

# Landlord onboarding sequence: aliases and content for 7-day emails (customer layout, reporting_notifications).
ONBOARDING_ALIASES = {
    EmailTemplateAlias.ONBOARDING_DAY0_WELCOME,
    EmailTemplateAlias.ONBOARDING_DAY1_SETUP_REMINDER,
    EmailTemplateAlias.ONBOARDING_DAY2_COMPLIANCE_EDUCATION,
    EmailTemplateAlias.ONBOARDING_DAY3_PRODUCT_VALUE,
    EmailTemplateAlias.ONBOARDING_DAY4_DOCUMENT_PACK_INTRO,
    EmailTemplateAlias.ONBOARDING_DAY5_RISK_AWARENESS,
    EmailTemplateAlias.ONBOARDING_DAY6_CASE_EXAMPLE,
    EmailTemplateAlias.ONBOARDING_DAY7_ACTIVATION_PUSH,
}

# Content per onboarding template: body (HTML), cta_label, cta_url_suffix (appended to portal base), why_received, header_title.
def _get_onboarding_content(template_alias: EmailTemplateAlias) -> Dict[str, Any]:
    base = {
        "header_title": "Compliance Vault Pro",
        "why_received": "you have signed up for Compliance Vault Pro and we send occasional onboarding tips to help you get the most from your account.",
    }
    content = {
        EmailTemplateAlias.ONBOARDING_DAY0_WELCOME: {
            **base,
            "body": "<p>Welcome to Compliance Vault Pro. Your portal is ready—the next step is to add your first property so we can help you track certificates and stay compliant.</p>",
            "cta_label": "Add your first property",
            "cta_url_suffix": "/properties",
        },
        EmailTemplateAlias.ONBOARDING_DAY1_SETUP_REMINDER: {
            **base,
            "body": "<p>Just a quick reminder to complete your setup. Pleerity can monitor key compliance items for your properties, including:</p><ul><li>Gas Safety (CP12)</li><li>EICR</li><li>EPC</li><li>Fire alarm inspections</li><li>Legionella assessments</li></ul><p>You can mark any requirement as not applicable if it doesn't apply to your property.</p>",
            "cta_label": "Continue setup",
            "cta_url_suffix": "/properties",
        },
        EmailTemplateAlias.ONBOARDING_DAY2_COMPLIANCE_EDUCATION: {
            **base,
            "body": "<p>We track the core compliance requirements that landlords typically need—certificates, renewals, and expiry dates. If something isn't relevant to a property, you can mark it as not applicable.</p>",
            "cta_label": "Track these automatically in Pleerity",
            "cta_url_suffix": "/properties",
        },
        EmailTemplateAlias.ONBOARDING_DAY3_PRODUCT_VALUE: {
            **base,
            "body": "<p>Pleerity's automation helps you stay on top of compliance: certificate monitoring, automated reminders, a compliance score per property, and secure document storage—all in one place.</p>",
            "cta_label": "View your compliance dashboard",
            "cta_url_suffix": "/dashboard",
        },
        EmailTemplateAlias.ONBOARDING_DAY4_DOCUMENT_PACK_INTRO: {
            **base,
            "body": "<p>Landlord document packs can help you with tenancy agreements, inventory forms, compliance declarations, and other common paperwork—all drafted to save you time.</p>",
            "cta_label": "View landlord document packs",
            "cta_url_suffix": "/services",
        },
        EmailTemplateAlias.ONBOARDING_DAY5_RISK_AWARENESS: {
            **base,
            "body": "<p>Missing or expired compliance certificates can lead to legal penalties, insurance issues, and tenant disputes. Enabling compliance alerts helps you renew in good time.</p>",
            "cta_label": "Enable compliance alerts",
            "cta_url_suffix": "/settings/notifications",
        },
        EmailTemplateAlias.ONBOARDING_DAY6_CASE_EXAMPLE: {
            **base,
            "body": "<p>One landlord nearly missed a Gas Safety renewal. Pleerity detected the upcoming expiry and sent a reminder 10 days early—so they renewed in time with no stress.</p>",
            "cta_label": "Start monitoring your property",
            "cta_url_suffix": "/properties",
        },
        EmailTemplateAlias.ONBOARDING_DAY7_ACTIVATION_PUSH: {
            **base,
            "body": "<p>Quick recap: certificate tracking, automated reminders, compliance score, and secure document storage are all ready when you activate monitoring for your properties.</p>",
            "cta_label": "Activate monitoring",
            "cta_url_suffix": "/properties",
        },
    }
    return content.get(template_alias, base)

# Quarantine: all outbound sends must go through NotificationOrchestrator (STEP 6).
# This module is only used for template rendering (_build_html_body, _build_text_body) by the orchestrator.
def _raise_send_deprecated():
    raise RuntimeError(
        "Direct email send is deprecated. Use services.notification_orchestrator.notification_orchestrator.send() "
        "with the appropriate template_key. All outbound email/SMS must go through the orchestrator."
    )


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
        """DEPRECATED: Use notification_orchestrator.send(). Kept for reference only."""
        _raise_send_deprecated()
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

    def _build_scheduled_report_table(self, report_rows: List[Dict[str, Any]]) -> str:
        """Build HTML table for scheduled requirements report with status styling."""
        status_styles = {
            "COMPLIANT": "background-color: #dcfce7; color: #166534; font-weight: 600;",
            "OVERDUE": "background-color: #fee2e2; color: #b91c1c; font-weight: 600;",
            "PENDING": "background-color: #fef3c7; color: #b45309; font-weight: 600;",
            "EXPIRING_SOON": "background-color: #fef3c7; color: #b45309; font-weight: 600;",
        }
        columns = [
            ("property_address", "Property"),
            ("requirement_type", "Type"),
            ("description", "Description"),
            ("status", "Status"),
            ("due_date", "Due date"),
            ("frequency_days", "Freq."),
            ("documents_count", "Docs"),
            ("latest_document", "Latest doc"),
            ("latest_doc_status", "Doc status"),
        ]
        thead = "".join(
            f'<th style="padding: 10px 8px; text-align: left; border-bottom: 2px solid #e2e8f0; background: #f1f5f9;">{label}</th>'
            for _key, label in columns
        )
        rows_html = []
        for row in report_rows:
            cells = []
            for key, _label in columns:
                val = row.get(key, "")
                if isinstance(val, (int, float)):
                    val = str(val)
                else:
                    val = str(val) if val is not None else ""
                escaped = html_module.escape(val)
                if key == "status":
                    style = status_styles.get(str(val).upper(), "")
                    cells.append(
                        f'<td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><span style="display: inline-block; padding: 2px 8px; border-radius: 4px; {style}">{escaped}</span></td>'
                    )
                else:
                    cells.append(f'<td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{escaped}</td>')
            rows_html.append("<tr>" + "".join(cells) + "</tr>")
        return f"""
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
            <thead><tr>{thead}</tr></thead>
            <tbody>{"".join(rows_html)}</tbody>
        </table>"""

    def _build_html_body(self, template_alias: EmailTemplateAlias, model: Dict[str, Any]) -> str:
        """Build HTML email body based on template type."""
        footer = self._build_email_footer(model)
        
        if template_alias == EmailTemplateAlias.PASSWORD_SETUP:
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{customer_ref}</span></p>' if customer_ref else ""
            greeting = f"Hello {model.get('client_name', 'there')},"
            body = "<p>Your compliance portal account has been created. Please set your password to get started.</p><p style=\"color: #666; font-size: 14px;\">This link will expire in 24 hours. If you didn't request this, please ignore this email.</p>"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Welcome to Compliance Vault Pro",
                ref_badge=ref_badge,
                cta_label="Set Your Password",
                cta_url=model.get('setup_link', '#'),
                why_received="you have a new compliance portal account and need to set your password.",
                show_preferences_link=False,
                customer_reference=customer_ref or None,
            )
        elif template_alias == EmailTemplateAlias.PASSWORD_RESET:
            greeting = f"Hello {model.get('client_name', 'there')},"
            body = "<p>You requested a password reset for your Compliance Vault Pro account. Use the link below to set a new password.</p><p style=\"color: #666; font-size: 14px;\">This link will expire in 1 hour. If you didn't request this, please ignore this email or contact support.</p>"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Reset your password",
                cta_label="Set new password",
                cta_url=model.get('setup_link', '#'),
                why_received="you requested a password reset.",
                show_preferences_link=False,
                customer_reference=model.get('customer_reference'),
            )
        elif template_alias == EmailTemplateAlias.PASSWORD_CHANGED_CONFIRMATION:
            greeting = f"Hello {model.get('client_name', 'there')},"
            body = "<p>Your password was changed successfully. If you did not make this change, please contact support immediately.</p>"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Password changed",
                cta_label="View your dashboard",
                cta_url=model.get('portal_link', '#'),
                why_received="you recently updated your account password.",
                show_preferences_link=False,
                customer_reference=model.get('customer_reference'),
                preferences_url=_notification_preferences_url(model) or None,
            )
        elif template_alias == EmailTemplateAlias.PORTAL_READY:
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{customer_ref}</span></p>' if customer_ref else ""
            greeting = f"Hello {model.get('client_name', 'there')},"
            body = "<p>Great news! Your Compliance Vault Pro portal is now ready to use.</p>"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Your Portal is Ready!",
                ref_badge=ref_badge,
                cta_label="Access Your Portal",
                cta_url=model.get('portal_link', '#'),
                why_received="your compliance portal has been provisioned and is ready to use.",
                show_preferences_link=False,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=customer_ref or None,
            )
        elif template_alias == EmailTemplateAlias.COMPLIANCE_ALERT:
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-left: 10px;">{customer_ref}</span>' if customer_ref else ""
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
            body = f"""
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
                    <p style="color: #64748b; font-size: 14px;">
                        <strong>What this means:</strong><br>
                        • <span style="color: #22c55e;">GREEN</span> = All requirements are compliant<br>
                        • <span style="color: #f59e0b;">AMBER</span> = Some requirements are expiring soon<br>
                        • <span style="color: #dc2626;">RED</span> = Immediate action required
                    </p>"""
            greeting = f"Hello {model.get('client_name', 'there')},"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="⚠️ Compliance Alert",
                ref_badge=ref_badge,
                cta_label="View Dashboard",
                cta_url=model.get('portal_link', '#'),
                why_received="compliance monitoring is enabled for your account and a property status changed.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=customer_ref or None,
            )
        elif template_alias == EmailTemplateAlias.REMINDER:
            req_name = model.get("requirement_name", "Certificate")
            prop_addr = model.get("property_address", "Your property")
            due_date = model.get("due_date", "")
            days_overdue = model.get("days_overdue")
            days_remaining = model.get("days_remaining", 0)
            if days_overdue is not None and days_overdue >= 0:
                urgency_line = f"<p><strong>This requirement is {'overdue' if days_overdue == 0 else f'{days_overdue} days overdue'}.</strong></p>"
            else:
                urgency_line = f"<p><strong>{days_remaining}</strong> days remaining to complete this requirement.</p>"
            body = f"<p>This is a reminder that <strong>{req_name}</strong> for your property at <strong>{prop_addr}</strong> is due on <strong>{due_date}</strong>.</p>{urgency_line}"
            greeting = f"Hello {model.get('client_name', 'Valued Customer')},"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Compliance Action Required",
                cta_label="View in Portal",
                cta_url=model.get('portal_link', '#'),
                why_received="compliance monitoring and expiry reminders are enabled for your account.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=model.get('customer_reference'),
            )
        elif template_alias == EmailTemplateAlias.TENANT_INVITE:
            body = "<p>Your landlord has invited you to view the compliance status of your rental property.</p><p>The tenant portal allows you to:</p><ul style=\"color: #64748b;\"><li>View property compliance status (GREEN/AMBER/RED)</li><li>See certificate expiry dates</li><li>Track overall compliance health</li></ul><p style=\"color: #666; font-size: 14px;\">This link expires in 7 days. If you have questions, please contact your landlord.</p>"
            if model.get('login_url'):
                body += f'<p style="color: #666; font-size: 14px; margin-top: 16px;">After you\'ve set your password, you can log in anytime at: <a href="{model.get("login_url", "#")}" style="color: #00B8A9;">{model.get("login_url", "")}</a></p>'
            greeting = f"Hello {model.get('tenant_name', 'there')},"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Tenant Portal Invitation",
                cta_label="Set Up Your Access",
                cta_url=model.get('setup_link', '#'),
                why_received="your landlord invited you to access the tenant portal.",
                show_preferences_link=False,
                customer_reference=model.get('customer_reference'),
            )
        elif template_alias == EmailTemplateAlias.SCHEDULED_REPORT:
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-left: 10px;">{customer_ref}</span>' if customer_ref else ""
            report_rows: List[Dict[str, Any]] = model.get('report_rows') or []
            total_requirements = model.get('total_requirements', 0) or len(report_rows)
            if report_rows:
                report_table_html = self._build_scheduled_report_table(report_rows)
                report_body = f"""
                    <p style="margin: 0 0 12px 0;"><strong>Report:</strong> {html_module.escape(str(model.get('report_type', 'Requirements Report')))}</p>
                    <p style="margin: 0 0 16px 0;"><strong>Total requirements:</strong> {total_requirements}</p>
                    <div style="overflow-x: auto; margin: 16px 0; border: 1px solid #e2e8f0; border-radius: 6px;">
                        {report_table_html}
                    </div>"""
            else:
                raw_content = (model.get('report_content') or 'Report data will appear here.')[:1500]
                report_body = f"""
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0; font-family: monospace; font-size: 12px; white-space: pre-wrap; overflow-x: auto;">{html_module.escape(raw_content)}</div>"""
            body = f"<p>Please find your scheduled <strong>{model.get('report_type', 'compliance')}</strong> report below.</p>{report_body}<p style=\"color: #666; font-size: 14px; margin-top: 20px;\">For the full report with all details, please log in to your dashboard and download the complete report from the Reports section.</p>"
            greeting = f"Hello {model.get('client_name', 'there')},"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title=f"Your {model.get('frequency', 'Weekly').title()} Compliance Report",
                ref_badge=ref_badge,
                cta_label="View your dashboard",
                cta_url=model.get('portal_link', '#'),
                why_received="you have scheduled compliance reports enabled for your account.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=customer_ref or None,
            )
        elif template_alias == EmailTemplateAlias.ADMIN_INVITE:
            body = "<p>You have been invited by <strong>" + (model.get('inviter_name') or 'an administrator') + "</strong> to join Compliance Vault Pro as an <strong>Administrator</strong>.</p><p>As an admin, you will have access to:</p><ul style=\"color: #64748b;\"><li>Full system management dashboard</li><li>All client accounts and properties</li><li>Audit logs and compliance reports</li><li>System configuration and settings</li></ul><p style=\"color: #dc2626; font-size: 14px; font-weight: bold;\">⏰ This invitation expires in 24 hours.</p><p style=\"color: #666; font-size: 14px;\">If you did not expect this invitation or have questions, please contact the system administrator.</p>"
            greeting = f"Hello {model.get('admin_name', 'there')},"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Admin Invitation",
                cta_label="Set Up Your Admin Account",
                cta_url=model.get('setup_link', '#'),
                why_received="you were invited by an administrator to join as an admin.",
                show_preferences_link=False,
                customer_reference=model.get('customer_reference'),
            )
        elif template_alias == EmailTemplateAlias.AI_EXTRACTION_APPLIED:
            customer_ref = model.get('customer_reference', '')
            ref_badge = f'<span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-left: 10px;">{customer_ref}</span>' if customer_ref else ""
            status_color = model.get('status_color', '#22c55e')
            status_icon = "✅" if model.get('requirement_status') == 'COMPLIANT' else "⚠️" if model.get('requirement_status') == 'EXPIRING_SOON' else "❌"
            body = f"""
                    <p>Good news! Our AI has successfully extracted and saved certificate details from your uploaded document.</p>
                    <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h3 style="margin: 0 0 15px 0; color: #166534;">📋 Certificate Details Saved</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 8px 0; color: #64748b; width: 140px;">Property:</td><td style="padding: 8px 0; font-weight: bold;">{model.get('property_address', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; color: #64748b;">Document Type:</td><td style="padding: 8px 0; font-weight: bold;">{model.get('document_type', 'Certificate')}</td></tr>
                            <tr><td style="padding: 8px 0; color: #64748b;">Certificate No:</td><td style="padding: 8px 0; font-weight: bold; font-family: monospace;">{model.get('certificate_number', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; color: #64748b;">Expiry Date:</td><td style="padding: 8px 0; font-weight: bold;">{model.get('expiry_date', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; color: #64748b;">Compliance Status:</td><td style="padding: 8px 0;"><span style="background-color: {status_color}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;">{status_icon} {model.get('requirement_status', 'UPDATED')}</span></td></tr>
                        </table>
                    </div>
                    <p style="color: #64748b; font-size: 14px;"><strong>What happens next?</strong><br>• Your compliance dashboard has been updated automatically<br>• You'll receive reminders before this certificate expires<br>• You can review or edit these details in your portal</p>"""
            greeting = f"Hello {model.get('client_name', 'there')},"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="AI Document Analysis Complete",
                ref_badge=ref_badge,
                cta_label="View in Dashboard",
                cta_url=model.get('portal_link', '#'),
                why_received="compliance monitoring is enabled and our AI processed your uploaded document.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=customer_ref or None,
            )
        elif template_alias == EmailTemplateAlias.ORDER_DELIVERED:
            documents = model.get('documents', [])
            docs_html = ""
            if documents:
                docs_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
                for doc in documents:
                    doc_name = doc if isinstance(doc, str) else doc.get('name', 'Document')
                    docs_html += f"<li style='margin: 5px 0;'>{doc_name}</li>"
                docs_html += "</ul>"
            body = f"<p>Your <strong>{model.get('service_name', 'order')}</strong> is complete and your documents are ready for download!</p><div style=\"background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 20px; margin: 20px 0;\"><p style=\"margin: 0 0 10px 0; font-weight: bold; color: #166534;\">Included Documents:</p>{docs_html}</div><p style=\"color: #64748b; font-size: 14px;\">Your documents are also available in your <a href=\"{model.get('portal_link', '#')}\" style=\"color: #00B8A9;\">portal dashboard</a>.</p>"
            greeting = f"Hello {model.get('client_name', 'there')},"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Your Documents Are Ready",
                cta_label="Download Documents",
                cta_url=model.get('download_link', '#'),
                why_received="you purchased a document pack and your order is ready.",
                show_preferences_link=False,
                customer_reference=model.get('customer_reference'),
            )
        elif template_alias == EmailTemplateAlias.PENDING_VERIFICATION_DIGEST:
            # Internal staff digest – do not use customer layout
            footer = self._build_email_footer(model)
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
            include_summary = model.get("include_compliance_summary", True)
            include_actions = model.get("include_action_items", True)
            include_expiries = model.get("include_upcoming_expiries", True)
            include_docs = model.get("include_recent_documents", True)
            items = []
            if include_summary:
                items.extend([
                    f"<li><strong>Properties:</strong> {model.get('properties_count', 0)}</li>",
                    f"<li><strong>Total requirements:</strong> {model.get('total_requirements', 0)}</li>",
                    f"<li><strong>Compliant:</strong> {model.get('compliant', 0)}</li>",
                ])
            if include_actions:
                items.append(f"<li><strong>Overdue:</strong> {model.get('overdue', 0)}</li>")
            if include_expiries:
                items.append(f"<li><strong>Expiring soon:</strong> {model.get('expiring_soon', 0)}</li>")
            if include_docs:
                items.append(f"<li><strong>Documents uploaded (period):</strong> {model.get('documents_uploaded', 0)}</li>")
            if not items:
                items = ["<li>No sections enabled in your digest preferences.</li>"]
            list_html = "\n                        ".join(items)
            data_as_of = (model.get("data_as_of") or model.get("period_end") or "").replace("T", " ")[:19]
            body = f"<p>Summary for the period (counts only):</p><ul>{list_html}</ul><p>Period: {model.get('period_start', '')} to {model.get('period_end', '')}</p><p style=\"color: #64748b; font-size: 12px; margin-top: 16px;\">Data as of {data_as_of}. This summary is for information only and does not constitute legal advice.</p>"
            greeting = f"Hello {model.get('client_name', 'there')},"
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title="Monthly compliance digest",
                cta_label="View your dashboard",
                cta_url=model.get('portal_link', '#'),
                why_received="you have reporting notifications enabled for your account.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=model.get('customer_reference'),
            )
        elif template_alias == EmailTemplateAlias.CLEARFORM_WELCOME:
            # Use the dedicated ClearForm method (customer-facing but custom layout)
            return self._build_clearform_welcome_html(model)
        elif template_alias == EmailTemplateAlias.ADMIN_MANUAL:
            # Internal/staff template – do not use customer layout. Accept "message" or "body" for content.
            body_content = model.get("message") or model.get("body") or "You have a new notification from Compliance Vault Pro."
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
                    <p>{body_content}</p>
                </div>
                {footer}
            </body>
            </html>
            """
        elif template_alias == EmailTemplateAlias.INTERNAL_ALERT:
            from email_templates.internal_alert_layout import build_internal_alert_html
            return build_internal_alert_html(model)
        elif template_alias in ONBOARDING_ALIASES:
            portal_base = (model.get("portal_base_url") or model.get("portal_link") or os.getenv("FRONTEND_URL") or os.getenv("PORTAL_BASE_URL") or "").strip().rstrip("/")
            c = _get_onboarding_content(template_alias)
            cta_url = (portal_base + c.get("cta_url_suffix", "/dashboard")) if portal_base else "#"
            greeting = f"Hello {model.get('client_name', 'there')},"
            ref_badge = ""
            if model.get("customer_reference"):
                ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{model["customer_reference"]}</span></p>'
            return build_customer_email_layout(
                greeting=greeting,
                body_html=c.get("body", ""),
                header_title=c.get("header_title", "Compliance Vault Pro"),
                ref_badge=ref_badge,
                cta_label=c.get("cta_label"),
                cta_url=cta_url,
                why_received=c.get("why_received", "you have an account with Pleerity."),
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=model.get("customer_reference"),
            )
        else:
            # Generic customer-facing (e.g. payment-receipt, payment-failed, renewal-reminder, subscription-canceled)
            customer_ref = model.get('customer_reference', '')
            ref_line = f"<p>Your Reference: <strong>{customer_ref}</strong></p>" if customer_ref else ""
            body = f"{ref_line}<p>{model.get('message', 'You have a new notification from Pleerity.')}</p>"
            greeting = f"Hello {model.get('client_name', 'there')},"
            show_prefs = template_alias not in SYSTEM_CRITICAL_ALIASES
            return build_customer_email_layout(
                greeting=greeting,
                body_html=body,
                header_title=model.get('subject', 'Pleerity'),
                cta_label=model.get('cta_label'),
                cta_url=model.get('cta_url'),
                why_received=model.get('why_received', "you have an active account with Pleerity."),
                show_preferences_link=show_prefs,
                preferences_url=_notification_preferences_url(model) if show_prefs else None,
                customer_reference=customer_ref or None,
            )
    
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
        elif template_alias == EmailTemplateAlias.PASSWORD_RESET:
            return f"""
Reset your password

Hello {model.get('client_name', 'there')},

You requested a password reset for your Compliance Vault Pro account. Use the link below to set a new password.

Set new password: {model.get('setup_link', '#')}

This link will expire in 1 hour. If you didn't request this, please ignore this email or contact support.
{footer}
            """
        elif template_alias == EmailTemplateAlias.PASSWORD_CHANGED_CONFIRMATION:
            return f"""
Password changed

Hello {model.get('client_name', 'there')},

Your password was changed successfully. If you did not make this change, please contact support immediately.

View your dashboard: {model.get('portal_link', '#')}
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
        elif template_alias == EmailTemplateAlias.REMINDER:
            req_name = model.get("requirement_name", "Certificate")
            prop_addr = model.get("property_address", "Your property")
            due_date = model.get("due_date", "")
            days_overdue = model.get("days_overdue")
            days_remaining = model.get("days_remaining", 0)
            if days_overdue is not None and days_overdue >= 0:
                urgency_line = f"This requirement is {'overdue' if days_overdue == 0 else f'{days_overdue} days overdue'}."
            else:
                urgency_line = f"{days_remaining} days remaining to complete this requirement."
            return f"""
Compliance Action Required
=========================
{ref_line}

Hello {model.get('client_name', 'Valued Customer')},

This is a reminder that {req_name} for your property at {prop_addr} is due on {due_date}.

{urgency_line}

View in Portal: {model.get('portal_link', '#')}
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
        elif template_alias == EmailTemplateAlias.SCHEDULED_REPORT:
            total = model.get('total_requirements', 0)
            report_type = model.get('report_type', 'compliance')
            return f"""
Your {model.get('frequency', 'Weekly').title()} Compliance Report
=========================================
{ref_line}

Hello {model.get('client_name', 'there')},

Please find your scheduled {report_type} report summary below.

Report: {report_type}
Generated: {model.get('generated_date', 'today')}
Total requirements: {total}

For the full report with all details, please log in to your dashboard and download the complete report from the Reports section.
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
            include_summary = model.get("include_compliance_summary", True)
            include_actions = model.get("include_action_items", True)
            include_expiries = model.get("include_upcoming_expiries", True)
            include_docs = model.get("include_recent_documents", True)
            lines = []
            if include_summary:
                lines.extend([
                    f"- Properties: {model.get('properties_count', 0)}",
                    f"- Total requirements: {model.get('total_requirements', 0)}",
                    f"- Compliant: {model.get('compliant', 0)}",
                ])
            if include_actions:
                lines.append(f"- Overdue: {model.get('overdue', 0)}")
            if include_expiries:
                lines.append(f"- Expiring soon: {model.get('expiring_soon', 0)}")
            if include_docs:
                lines.append(f"- Documents uploaded (period): {model.get('documents_uploaded', 0)}")
            if not lines:
                lines = ["- No sections enabled in your digest preferences."]
            body_lines = "\n".join(lines)
            data_as_of = (model.get("data_as_of") or model.get("period_end") or "").replace("T", " ")[:19]
            return f"""
MONTHLY COMPLIANCE DIGEST
========================

Summary for the period (counts only):

{body_lines}

Period: {model.get('period_start', '')} to {model.get('period_end', '')}

Data as of {data_as_of}. This summary is for information only and does not constitute legal advice.
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
        elif template_alias == EmailTemplateAlias.INTERNAL_ALERT:
            severity = model.get("severity", "P2")
            title = model.get("title", "Internal alert")
            desc = model.get("description", "")
            action = model.get("suggested_action", "")
            link = model.get("dashboard_link", "")
            ts = model.get("timestamp", "")
            lines = [f"[{severity}] {title}", ""]
            if desc:
                lines.append(desc)
            if action:
                lines.extend(["", "Suggested action: " + action])
            if link:
                lines.extend(["", "View: " + link])
            if ts:
                lines.extend(["", str(ts)])
            return "\n".join(lines) + "\n" + footer
        elif template_alias in ONBOARDING_ALIASES:
            c = _get_onboarding_content(template_alias)
            body_html = c.get("body", "")
            body_text = body_html.replace("</p>", "\n").replace("<p>", "").replace("<ul>", "\n").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "\n")
            body_text = html_module.unescape(body_text.strip())
            portal_base = (model.get("portal_base_url") or model.get("portal_link") or os.getenv("FRONTEND_URL") or os.getenv("PORTAL_BASE_URL") or "").strip().rstrip("/")
            cta_suffix = c.get("cta_url_suffix", "/dashboard")
            cta_url = (portal_base + cta_suffix) if portal_base else "#"
            lines = [
                c.get("header_title", "Compliance Vault Pro"),
                ref_line,
                "",
                f"Hello {model.get('client_name', 'there')},",
                "",
                body_text,
                "",
                f"{c.get('cta_label', 'Continue')}: {cta_url}",
                "",
                "Why you received this: " + c.get("why_received", "you have an account with Pleerity."),
            ]
            return "\n".join(lines) + "\n" + footer
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='WELCOME_EMAIL')."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send() with appropriate template_key."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='COMPLIANCE_ALERT')."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='ADMIN_INVITE')."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='AI_EXTRACTION_APPLIED')."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='SUBSCRIPTION_CONFIRMED')."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='PAYMENT_FAILED')."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='RENEWAL_REMINDER')."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='SUBSCRIPTION_CANCELED')."""
        _raise_send_deprecated()
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
        """DEPRECATED: Use notification_orchestrator.send(template_key='CLEARFORM_WELCOME')."""
        _raise_send_deprecated()
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
