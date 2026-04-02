from postmarker.core import PostmarkClient
from database import database
from models import MessageLog, EmailTemplateAlias, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
import html as html_module
import os
import re
import logging
from typing import Optional, Dict, Any, List

from email_templates.email_layout import build_customer_email_layout, merge_branding_kwargs
from utils.branding import CUSTOMER_SUPPORT_FOOTER_PLAIN, SUPPORT_EMAIL
from presentation.label_service import (
    compliance_requirement_status_label,
    document_type_label,
    requirement_label,
)

logger = logging.getLogger(__name__)


def _strip_html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:5000] if len(text) > 5000 else text


def _customer_email_html(model: Dict[str, Any], **kwargs: Any) -> str:
    """Apply ``_email_branding`` from notification context, then explicit kwargs."""
    merged = merge_branding_kwargs(model, **kwargs)
    greeting = merged.pop("greeting")
    body_html = merged.pop("body_html")
    return build_customer_email_layout(greeting, body_html, **merged)


def _format_greeting(client_name: Optional[str]) -> str:
    """Avoid empty 'Hi ,' — use first name or neutral 'Hello,'."""
    name = (client_name or "").strip()
    if not name or name.lower() in ("valued customer", "there", "customer"):
        return "Hello,"
    first = name.split()[0]
    return f"Hello {first},"


def _email_app_base() -> str:
    from utils.app_urls import get_app_base_url

    return get_app_base_url(for_email_links=True).rstrip("/")


# Email sender configuration
# Verified sender in Postmark
DEFAULT_SENDER = os.getenv("EMAIL_SENDER", "info@pleerityenterprise.co.uk")


def _notification_preferences_url(model: Dict[str, Any]) -> str:
    base = (model.get("portal_base_url") or _email_app_base()).strip().rstrip("/")
    if base:
        return base + "/settings/notifications"
    return ""

# Aliases that must not show "Manage notification preferences" (system_critical).
SYSTEM_CRITICAL_ALIASES = {
    EmailTemplateAlias.PASSWORD_SETUP,
    EmailTemplateAlias.PASSWORD_RESET,
    EmailTemplateAlias.PASSWORD_CHANGED_CONFIRMATION,
    EmailTemplateAlias.PORTAL_READY,
    EmailTemplateAlias.ACTIVATION_REMINDER,
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
            "body": "<p>Now that you’re signed in, add your first property so Compliance Vault Pro can track certificates, renewals, and your compliance score.</p>",
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

    def _build_monthly_digest_action_body_html(self, model: Dict[str, Any]) -> str:
        """Mobile-first action layer: summary, deltas, urgent items, steps — no wide data tables."""
        m = model
        label = html_module.escape(str(m.get("reporting_month_label") or "this period"))
        acct = html_module.escape(str(m.get("account_name") or m.get("client_name") or "Your account"))
        crn = m.get("customer_reference")
        crn_line = (
            f'<p style="margin:6px 0 0 0;color:#334155;font-size:14px;"><strong>CRN:</strong> {html_module.escape(str(crn))}</p>'
            if crn
            else ""
        )
        gen = html_module.escape(str(m.get("generated_at_display") or m.get("data_as_of") or ""))
        props = int(m.get("properties_count") or 0)
        scope_note_html = ""
        dsn = m.get("digest_score_scope_note")
        if dsn:
            scope_note_html = (
                '<p style="margin:12px 0;padding:10px 12px;background:#eff6ff;border-left:4px solid #2563eb;'
                'font-size:13px;color:#1e3a5f;line-height:1.5;">'
                f"{html_module.escape(str(dsn))}"
                "</p>"
            )
        score = int(m.get("compliance_score") or 0)
        risk = html_module.escape(str(m.get("risk_level") or "—"))
        total = int(m.get("total_requirements") or 0)
        valid = int(m.get("valid_count") or m.get("compliant") or 0)
        exp = int(m.get("expiring_soon") or 0)
        ovd = int(m.get("overdue") or 0)
        miss = int(m.get("missing_evidence_count") or 0)

        def metric_card(title: str, value: str) -> str:
            return (
                f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin:0 0 10px 0;">'
                f'<div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;">{title}</div>'
                f'<div style="font-size:20px;font-weight:700;color:#0f172a;margin-top:4px;">{value}</div></div>'
            )

        top_prop_html = ""
        tpr = m.get("digest_email_top_properties_at_risk") or []
        if tpr and m.get("include_property_breakdown", True):
            parts = [
                '<p style="font-weight:600;color:#0f172a;margin:20px 0 8px 0;">'
                "Properties needing the most attention</p>",
                '<ul style="margin:0;padding-left:20px;color:#334155;font-size:14px;line-height:1.55;">',
            ]
            for row in tpr:
                nm = html_module.escape(str(row.get("name") or "Property"))
                rk = html_module.escape(str(row.get("risk_level") or "—"))
                sc = row.get("score")
                sc_s = html_module.escape(str(sc)) if sc is not None else "—"
                ovd = int(row.get("overdue_count") or 0)
                miss = int(row.get("missing_evidence_count") or 0)
                bits = [f"Score {sc_s}", rk]
                if ovd:
                    bits.append(f"{ovd} overdue")
                if miss:
                    bits.append(f"{miss} missing evidence")
                parts.append(f"<li><strong>{nm}</strong> — {html_module.escape(' · '.join(bits))}</li>")
            parts.append("</ul>")
            top_prop_html = "".join(parts)

        cards = ""
        if m.get("include_compliance_summary", True):
            cards += metric_card("Compliance score", html_module.escape(str(score)))
            cards += metric_card("Risk level", risk)
            cards += metric_card("Tracked requirements", html_module.escape(str(total)))
            cards += metric_card("Valid", html_module.escape(str(valid)))
            cards += metric_card("Expiring soon", html_module.escape(str(exp)))
            cards += metric_card("Overdue", html_module.escape(str(ovd)))
            cards += metric_card("Missing evidence", html_module.escape(str(miss)))

        d = m.get("deltas") or {}
        delta_block = ""
        if d.get("has_prior_snapshot"):
            delta_block = '<p style="font-weight:600;color:#0f172a;margin:20px 0 8px 0;">What changed since your last report</p><ul style="margin:0;padding-left:20px;color:#334155;font-size:15px;line-height:1.5;">'
            sd = d.get("score_delta")
            if sd is not None:
                try:
                    sdi = int(sd)
                    delta_block += f"<li>Compliance score moved by {sdi:+d} point(s).</li>"
                except (TypeError, ValueError):
                    delta_block += f"<li>Compliance score movement recorded.</li>"
            if d.get("newly_overdue_labels"):
                for x in d["newly_overdue_labels"][:5]:
                    delta_block += f"<li>Newly overdue: {html_module.escape(str(x))}</li>"
            if d.get("resolved_improved_labels"):
                for x in d["resolved_improved_labels"][:5]:
                    delta_block += f"<li>Resolved or improved: {html_module.escape(str(x))}</li>"
            if d.get("newly_expiring_labels"):
                for x in d["newly_expiring_labels"][:4]:
                    delta_block += f"<li>Newly expiring soon: {html_module.escape(str(x))}</li>"
            docd = d.get("documents_uploaded_delta_vs_prev_period")
            if docd is not None:
                try:
                    delta_block += f"<li>Document uploads vs your prior reporting period: {int(docd):+d}.</li>"
                except (TypeError, ValueError):
                    delta_block += f"<li>Document upload activity changed vs your prior reporting period.</li>"
            elif m.get("include_recent_documents", True):
                delta_block += f"<li>Documents uploaded this reporting period: {int(m.get('documents_uploaded_period') or 0)}.</li>"
            nmd = d.get("newly_missing_evidence_delta")
            if nmd is not None:
                try:
                    nmdi = int(nmd)
                    if nmdi != 0:
                        delta_block += f"<li>Missing evidence count vs last report: {nmdi:+d}.</li>"
                except (TypeError, ValueError):
                    pass
            delta_block += "</ul>"
        else:
            delta_block = (
                '<p style="background:#eff6ff;border-left:4px solid #3b82f6;padding:12px 14px;color:#1e3a5f;font-size:14px;line-height:1.5;">'
                "This is your first monthly compliance summary on record. Next month we will compare changes against this report."
                "</p>"
            )

        urgent_block = ""
        if m.get("include_action_items", True):
            items = m.get("urgent_items") or []
            if items:
                urgent_block = '<p style="font-weight:600;color:#b91c1c;margin:20px 0 8px 0;">Immediate attention</p><ul style="margin:0;padding-left:0;list-style:none;">'
                for it in items[:5]:
                    url = html_module.escape(str(it.get("url") or m.get("primary_cta_url") or m.get("portal_link") or "#"))
                    line = html_module.escape(str(it.get("line") or it.get("title") or "Action item"))
                    urgent_block += (
                        f'<li style="margin:0 0 12px 0;"><a href="{url}" style="display:block;padding:12px 14px;'
                        f'background:#fef2f2;border:1px solid #fecaca;border-radius:8px;color:#991b1b;text-decoration:none;'
                        f'font-size:15px;font-weight:600;">{line}</a></li>'
                    )
                urgent_block += "</ul>"

        steps = ""
        if m.get("include_recommendations", True):
            steps = '<p style="font-weight:600;color:#0f172a;margin:20px 0 8px 0;">Recommended next steps</p><ol style="margin:0;padding-left:20px;color:#334155;font-size:15px;line-height:1.55;">'
            if miss > 0:
                steps += "<li>Upload missing documents and request verification where required.</li>"
            if ovd > 0:
                steps += "<li>Clear overdue renewals or book a compliance job from the command centre.</li>"
            steps += "<li>Review your dashboard and calendar for upcoming expiries.</li>"
            steps += "</ol>"

        pdf_note = ""
        if m.get("digest_pdf_attached"):
            pdf_note = (
                '<p style="margin:16px 0;font-size:14px;color:#334155;">'
                "A detailed <strong>PDF audit report</strong> is attached for your records, lenders, or advisers."
                "</p>"
            )

        trunc_note = ""
        if m.get("digest_truncated") and m.get("digest_truncation_display_lines"):
            lines_esc = " ".join(
                html_module.escape(str(x)) for x in (m.get("digest_truncation_display_lines") or [])
            )
            trunc_note = (
                '<p style="margin:16px 0;padding:12px 14px;background:#fffbeb;border-left:4px solid #d97706;'
                'font-size:13px;color:#78350f;line-height:1.5;">'
                "<strong>Data scope notice.</strong> "
                f"{lines_esc}"
                "</p>"
            )

        support = html_module.escape(str(m.get("support_email") or SUPPORT_EMAIL or "support@pleerityenterprise.co.uk"))
        disclaimer = (
            "<p style='font-size:12px;color:#64748b;margin-top:20px;line-height:1.5;'>"
            "Figures are generated from tracked requirements, evidence states, and dates recorded in Compliance Vault Pro. "
            f"Support: <a href='mailto:{support}' style='color:#00B8A9;'>{support}</a>. "
            "This email is operational and informational — not legal advice."
            "</p>"
        )

        return f"""
<p style="margin:0 0 8px 0;color:#64748b;font-size:13px;">Monthly Compliance Summary — {label}</p>
<p style="margin:0 0 4px 0;font-size:16px;color:#0f172a;"><strong>{acct}</strong></p>
{crn_line}
<p style="margin:8px 0 0 0;color:#64748b;font-size:13px;">Properties in scope: <strong>{props}</strong> · Generated: {gen}</p>
{scope_note_html}
<div style="height:16px;"></div>
{cards}
{top_prop_html}
{delta_block}
{urgent_block}
{steps}
{pdf_note}
{trunc_note}
{disclaimer}
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
                    raw_s = str(val)
                else:
                    raw_s = str(val) if val is not None else ""
                if key == "requirement_type":
                    code = (row.get("requirement_code") or row.get("requirement_type") or raw_s or "").strip()
                    display = requirement_label(code) if code else ""
                elif key in ("status", "latest_doc_status"):
                    display = compliance_requirement_status_label(raw_s) if raw_s.strip() else ""
                else:
                    display = raw_s
                escaped = html_module.escape(display)
                if key == "status":
                    style = status_styles.get(raw_s.upper(), "")
                    cells.append(
                        f'<td style="padding: 8px; border-bottom: 1px solid #e2e8f0;"><span style="display: inline-block; padding: 2px 8px; border-radius: 4px; {style}">{escaped}</span></td>'
                    )
                elif key == "latest_doc_status":
                    cells.append(f'<td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{escaped}</td>')
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
            greeting = _format_greeting(model.get("client_name"))
            link_h = int(model.get("link_expiry_hours") or 24)
            expiry_phrase = f"{link_h} hour{'s' if link_h != 1 else ''}"
            body = (
                "<p>Your Compliance Vault Pro account is ready for activation. Set your password to secure your portal — you’ll need this before you can sign in.</p>"
                f'<p style="color: #666; font-size: 14px;">This link will expire in {expiry_phrase}. If you didn’t expect this email, you can ignore it.</p>'
            )
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body,
                header_title="Welcome — set your password",
                ref_badge=ref_badge,
                cta_label="Set Your Password",
                cta_url=model.get('setup_link', '#'),
                why_received="you have a new compliance portal account and need to set your password.",
                show_preferences_link=False,
                customer_reference=customer_ref or None,
            )
        elif template_alias == EmailTemplateAlias.ACTIVATION_REMINDER:
            customer_ref = model.get("customer_reference", "") or ""
            ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{customer_ref}</span></p>' if customer_ref else ""
            greeting = _format_greeting(model.get("client_name"))
            link_h = int(model.get("link_expiry_hours") or 24)
            expiry_phrase = f"{link_h} hour{'s' if link_h != 1 else ''}"
            body = (
                "<p>We noticed you haven’t finished activating your Compliance Vault Pro account yet.</p>"
                "<p>Setting your password takes a minute and unlocks your compliance dashboard, property tracking, and document vault.</p>"
                f'<p style="color: #666; font-size: 14px;">This link will expire in {expiry_phrase}.</p>'
            )
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body,
                header_title="Complete your setup",
                ref_badge=ref_badge,
                cta_label="Set your password",
                cta_url=model.get("setup_link", "#"),
                why_received="you started a Compliance Vault Pro subscription but haven’t activated your account yet.",
                show_preferences_link=False,
                customer_reference=customer_ref or None,
            )
        elif template_alias == EmailTemplateAlias.PASSWORD_RESET:
            greeting = _format_greeting(model.get("client_name"))
            expiry_txt = (model.get("link_expiry_text") or "1 hour").strip()
            body = (
                "<p>You requested a password reset for your Compliance Vault Pro account. Use the link below to set a new password.</p>"
                f'<p style="color: #666; font-size: 14px;">This link will expire in {html_module.escape(expiry_txt)}. If you didn\'t request this, please ignore this email or contact support.</p>'
            )
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body,
                header_title="Reset your password",
                cta_label="Set new password",
                cta_url=model.get('setup_link', '#'),
                why_received="you requested a password reset.",
                show_preferences_link=False,
                customer_reference=model.get('customer_reference'),
            )
        elif template_alias == EmailTemplateAlias.PAYMENT_RECEIPT:
            greeting = _format_greeting(model.get("client_name"))
            plan = html_module.escape(str(model.get("plan_name") or "Compliance Vault Pro"))
            amount = html_module.escape(str(model.get("amount_display") or ""))
            pdate = html_module.escape(str(model.get("payment_date_display") or ""))
            ref = html_module.escape(str(model.get("reference_display") or ""))
            next_steps = model.get("next_steps_html") or (
                "<ol style=\"margin: 16px 0; padding-left: 20px; color: #334155;\">"
                "<li>We’ll email you shortly with a link to <strong>set your password</strong>.</li>"
                "<li>After activation, sign in to your dashboard to add properties and track compliance.</li>"
                "<li>If you have any questions, simply reply to this email or contact our support team at "
                f"<a href=\"mailto:{html_module.escape(SUPPORT_EMAIL)}\" style=\"color: #00B8A9;\">"
                f"{html_module.escape(SUPPORT_EMAIL)}</a>.</li></ol>"
            )
            body = f"""
            <p>Thank you — your payment for <strong>{plan}</strong> was received successfully.</p>
            <table style="width: 100%; max-width: 480px; border-collapse: collapse; margin: 20px 0; font-size: 14px;">
              <tr><td style="padding: 8px 0; color: #64748b;">Amount</td><td style="padding: 8px 0; text-align: right;"><strong>{amount}</strong></td></tr>
              <tr><td style="padding: 8px 0; color: #64748b;">Date</td><td style="padding: 8px 0; text-align: right;">{pdate}</td></tr>
              <tr><td style="padding: 8px 0; color: #64748b;">Reference</td><td style="padding: 8px 0; text-align: right; font-family: monospace; font-size: 12px;">{ref}</td></tr>
            </table>
            <p style="color: #0B1D3A; font-weight: 600;">What happens next</p>
            {next_steps}
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body,
                header_title="Payment received",
                cta_label=model.get("receipt_cta_label"),
                cta_url=model.get("receipt_cta_url"),
                why_received="you completed checkout for Compliance Vault Pro.",
                show_preferences_link=False,
                customer_reference=model.get("customer_reference") or None,
            )
        elif template_alias == EmailTemplateAlias.PASSWORD_CHANGED_CONFIRMATION:
            greeting = _format_greeting(model.get("client_name"))
            body = "<p>Your password was changed successfully. If you did not make this change, please contact support immediately.</p>"
            return _customer_email_html(
                model,
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
            greeting = _format_greeting(model.get("client_name"))
            body = (
                "<p>Your password is set — you now have full access to your <strong>Compliance Vault Pro</strong> dashboard.</p>"
                "<p style=\"color: #0B1D3A; font-weight: 600; margin-top: 20px;\">Suggested first steps</p>"
                "<ul style=\"margin: 12px 0; padding-left: 20px; color: #334155; line-height: 1.6;\">"
                "<li>Review <strong>your properties</strong> and add any missing addresses.</li>"
                "<li>Check your <strong>compliance status</strong> and upcoming renewals.</li>"
                "<li><strong>Upload certificates</strong> so expiry tracking and reminders work for you.</li>"
                "</ul>"
            )
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body,
                header_title="Your dashboard is ready",
                ref_badge=ref_badge,
                cta_label="Go to your dashboard",
                cta_url=model.get('portal_link', '#'),
                why_received="you successfully activated your Compliance Vault Pro account.",
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
            return _customer_email_html(
                model,
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
            rc = (model.get("requirement_code") or model.get("requirement_type") or "").strip()
            req_name = requirement_label(rc) if rc else (model.get("requirement_name") or "Certificate")
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
            return _customer_email_html(
                model,
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
            return _customer_email_html(
                model,
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
            return _customer_email_html(
                model,
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
            return _customer_email_html(
                model,
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
            doc_type_disp = html_module.escape(document_type_label(model.get('document_type')))
            status_disp = html_module.escape(compliance_requirement_status_label(model.get('requirement_status')))
            body = f"""
                    <p>Good news! Our AI has successfully extracted and saved certificate details from your uploaded document.</p>
                    <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h3 style="margin: 0 0 15px 0; color: #166534;">📋 Certificate Details Saved</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr><td style="padding: 8px 0; color: #64748b; width: 140px;">Property:</td><td style="padding: 8px 0; font-weight: bold;">{model.get('property_address', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; color: #64748b;">Document Type:</td><td style="padding: 8px 0; font-weight: bold;">{doc_type_disp}</td></tr>
                            <tr><td style="padding: 8px 0; color: #64748b;">Certificate No:</td><td style="padding: 8px 0; font-weight: bold; font-family: monospace;">{model.get('certificate_number', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; color: #64748b;">Expiry Date:</td><td style="padding: 8px 0; font-weight: bold;">{model.get('expiry_date', 'N/A')}</td></tr>
                            <tr><td style="padding: 8px 0; color: #64748b;">Compliance Status:</td><td style="padding: 8px 0;"><span style="background-color: {status_color}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold;">{status_icon} {status_disp}</span></td></tr>
                        </table>
                    </div>
                    <p style="color: #64748b; font-size: 14px;"><strong>What happens next?</strong><br>• Your compliance dashboard has been updated automatically<br>• You'll receive reminders before this certificate expires<br>• You can review or edit these details in your portal</p>"""
            greeting = f"Hello {model.get('client_name', 'there')},"
            return _customer_email_html(
                model,
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
            return _customer_email_html(
                model,
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
            body_inner = self._build_monthly_digest_action_body_html(model)
            extra_cc = ""
            if model.get("include_audit_summary") and model.get("command_centre_digest_included"):
                u = int(model.get("command_centre_urgent_open") or 0)
                up = int(model.get("command_centre_upcoming_open") or 0)
                ip = int(model.get("command_centre_in_progress_open") or 0)
                sn = int(model.get("command_centre_snoozed") or 0)
                extra_cc = (
                    "<p style=\"font-weight:600;margin:20px 0 8px 0;\">Today inbox snapshot</p>"
                    "<ul style=\"margin:0;padding-left:20px;color:#334155;font-size:14px;\">"
                    f"<li>Urgent: {u}</li><li>Upcoming: {up}</li><li>In progress: {ip}</li><li>Snoozed: {sn}</li></ul>"
                )
                act_lines = model.get("command_centre_recent_activity_lines") or []
                if act_lines:
                    lis = "".join(f"<li>{html_module.escape(str(line))}</li>" for line in act_lines)
                    extra_cc += f"<p style=\"font-weight:600;margin:16px 0 6px 0;\">Recent inbox activity</p><ul style=\"margin:0;padding-left:20px;font-size:14px;\">{lis}</ul>"
            period_html = ""
            if model.get("include_audit_summary") and model.get("digest_period_activity_included"):
                plines = model.get("digest_period_activity_lines") or []
                if plines:
                    plis = "".join(f"<li>{html_module.escape(str(line))}</li>" for line in plines)
                    period_html = f"<p style=\"font-weight:600;margin:20px 0 8px 0;\">Operational activity (period)</p><ul style=\"margin:0;padding-left:20px;font-size:14px;\">{plis}</ul>"
                else:
                    period_html = "<p style=\"color:#64748b;font-size:14px;\">No qualifying operational activity lines for this window.</p>"
            body = body_inner + extra_cc + period_html
            greeting = _format_greeting(model.get("client_name"))
            header = html_module.escape(
                str(model.get("email_header_title") or model.get("subject") or "Monthly Compliance Summary")
            )
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body,
                header_title=header,
                cta_label=str(model.get("primary_cta_label") or "Review & Fix Compliance Now"),
                cta_url=model.get("primary_cta_url") or model.get("portal_link") or "#",
                why_received="you have monthly compliance reporting enabled for your account.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=model.get("customer_reference"),
            )
        elif template_alias == EmailTemplateAlias.CLEARFORM_WELCOME:
            # Use the dedicated ClearForm method (customer-facing but custom layout)
            return self._build_clearform_welcome_html(model)
        elif template_alias == EmailTemplateAlias.CLIENT_OPERATIONAL_NOTICE:
            body_html = model.get("message") or model.get("body") or "<p></p>"
            header_title = (model.get("email_header_title") or model.get("subject") or "Service notice").strip()[:200]
            show_prefs = model.get("show_notification_preferences_link")
            if show_prefs is None:
                show_prefs = True
            ref_badge = ""
            if model.get("customer_reference"):
                ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{html_module.escape(str(model["customer_reference"]))}</span></p>'
            return _customer_email_html(
                model,
                greeting=_format_greeting(model.get("client_name")),
                body_html=body_html,
                header_title=header_title,
                ref_badge=ref_badge,
                cta_label="Open your dashboard",
                cta_url=model.get("portal_link") or "#",
                why_received=model.get(
                    "why_received",
                    "we need to share an operational or account-related update with you.",
                ),
                show_preferences_link=show_prefs,
                preferences_url=_notification_preferences_url(model) if show_prefs else None,
                customer_reference=model.get("customer_reference"),
            )
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
            portal_base = (model.get("portal_base_url") or model.get("portal_link") or _email_app_base()).strip().rstrip("/")
            c = _get_onboarding_content(template_alias)
            cta_url = (portal_base + c.get("cta_url_suffix", "/dashboard")) if portal_base else "#"
            greeting = _format_greeting(model.get("client_name"))
            ref_badge = ""
            if model.get("customer_reference"):
                ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{model["customer_reference"]}</span></p>'
            return _customer_email_html(
                model,
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
            return _customer_email_html(
                model,
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
        eb = model.get("_email_branding") if isinstance(model.get("_email_branding"), dict) else {}
        co = eb.get("company_name") or model.get("company_name", "Pleerity Enterprise Ltd")
        tag = eb.get("tagline") or model.get("tagline", "AI-Driven Solutions & Compliance")
        se = eb.get("support_email") or SUPPORT_EMAIL
        support_plain = (
            CUSTOMER_SUPPORT_FOOTER_PLAIN
            if se == SUPPORT_EMAIL
            else f"If you have any questions, contact us at {se}"
        )

        return f"""
--
{co}
{tag}{ref_line}

{support_plain}
        """

    def _build_text_body(self, template_alias: EmailTemplateAlias, model: Dict[str, Any]) -> str:
        """Build plain text email body based on template type."""
        footer = self._build_text_footer(model)
        customer_ref = model.get('customer_reference', '')
        ref_line = f"\nYour Reference: {customer_ref}" if customer_ref else ""
        
        if template_alias == EmailTemplateAlias.PASSWORD_SETUP:
            link_h = int(model.get("link_expiry_hours") or 24)
            expiry_phrase = f"{link_h} hour{'s' if link_h != 1 else ''}"
            return f"""
Welcome — set your password
{ref_line}

{_format_greeting(model.get('client_name'))}

Your Compliance Vault Pro account is ready for activation. Set your password to secure your portal.

Set your password: {model.get('setup_link', '#')}

This link will expire in {expiry_phrase}.
{footer}
            """
        elif template_alias == EmailTemplateAlias.ACTIVATION_REMINDER:
            link_h = int(model.get("link_expiry_hours") or 24)
            expiry_phrase = f"{link_h} hour{'s' if link_h != 1 else ''}"
            return f"""
Complete your setup
{ref_line}

{_format_greeting(model.get('client_name'))}

We noticed you haven't finished activating your Compliance Vault Pro account. Set your password to unlock your dashboard.

Set your password: {model.get('setup_link', '#')}

This link will expire in {expiry_phrase}.
{footer}
            """
        elif template_alias == EmailTemplateAlias.PAYMENT_RECEIPT:
            return f"""
Payment received — Compliance Vault Pro
{ref_line}

{_format_greeting(model.get('client_name'))}

Thank you. Your payment was received.

Plan: {model.get('plan_name', '')}
Amount: {model.get('amount_display', '')}
Date: {model.get('payment_date_display', '')}
Reference: {model.get('reference_display', '')}

What happens next:
1. You'll receive a separate email to set your password.
2. After activation, sign in to manage properties and compliance.

{footer}
            """
        elif template_alias == EmailTemplateAlias.PASSWORD_RESET:
            expiry_txt = (model.get("link_expiry_text") or "1 hour").strip()
            return f"""
Reset your password

{_format_greeting(model.get('client_name'))}

You requested a password reset for your Compliance Vault Pro account. Use the link below to set a new password.

Set new password: {model.get('setup_link', '#')}

This link will expire in {expiry_txt}. If you didn't request this, please ignore this email or contact support.
{footer}
            """
        elif template_alias == EmailTemplateAlias.PASSWORD_CHANGED_CONFIRMATION:
            return f"""
Password changed

{_format_greeting(model.get('client_name'))}

Your password was changed successfully. If you did not make this change, please contact support immediately.

View your dashboard: {model.get('portal_link', '#')}
{footer}
            """
        elif template_alias == EmailTemplateAlias.PORTAL_READY:
            return f"""
Your dashboard is ready
{ref_line}

{_format_greeting(model.get('client_name'))}

Your password is set — you now have full access to Compliance Vault Pro.

Suggested first steps:
- Review your properties and add any missing addresses.
- Check compliance status and upcoming renewals.
- Upload certificates for expiry tracking.

Go to your dashboard: {model.get('portal_link', '#')}
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
            rc = (model.get("requirement_code") or model.get("requirement_type") or "").strip()
            req_name = requirement_label(rc) if rc else (model.get("requirement_name") or "Certificate")
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
            doc_plain = document_type_label(model.get('document_type'))
            status_plain = compliance_requirement_status_label(model.get('requirement_status'))
            return f"""
🤖 AI DOCUMENT ANALYSIS COMPLETE
{ref_line}

Hello {model.get('client_name', 'there')},

Good news! Our AI has successfully extracted and saved certificate details from your uploaded document.

📋 CERTIFICATE DETAILS SAVED
----------------------------
Property:         {model.get('property_address', 'N/A')}
Document Type:    {doc_plain}
Certificate No:   {model.get('certificate_number', 'N/A')}
Expiry Date:      {model.get('expiry_date', 'N/A')}
Status:           {status_icon} {status_plain}

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
            label = model.get("reporting_month_label") or ""
            lines = [
                f"MONTHLY COMPLIANCE SUMMARY — {label}",
                "",
                f"Account: {model.get('account_name') or model.get('client_name', '')}",
            ]
            if model.get("customer_reference"):
                lines.append(f"CRN: {model.get('customer_reference')}")
            lines.extend(
                [
                    f"Properties: {model.get('properties_count', 0)}",
                    f"Compliance score: {model.get('compliance_score', 0)}",
                    f"Risk: {model.get('risk_level', '')}",
                    f"Requirements: {model.get('total_requirements', 0)} (valid {model.get('valid_count', model.get('compliant', 0))}, "
                    f"expiring soon {model.get('expiring_soon', 0)}, overdue {model.get('overdue', 0)}, "
                    f"missing evidence {model.get('missing_evidence_count', 0)})",
                    "",
                ]
            )
            d = model.get("deltas") or {}
            if d.get("has_prior_snapshot"):
                lines.append("Changes since your last report:")
                if d.get("score_delta") is not None:
                    lines.append(f"- Score delta: {d.get('score_delta')}")
                for x in (d.get("newly_overdue_labels") or [])[:4]:
                    lines.append(f"- Newly overdue: {x}")
                for x in (d.get("resolved_improved_labels") or [])[:4]:
                    lines.append(f"- Resolved/improved: {x}")
                docd = d.get("documents_uploaded_delta_vs_prev_period")
                if docd is not None:
                    lines.append(f"- Document uploads vs prior period: {docd}")
            else:
                lines.append("First monthly summary on record; comparison starts next month.")
            lines.append("")
            for it in (model.get("urgent_items") or [])[:5]:
                lines.append(f"* {it.get('line') or it.get('title')} — {it.get('url')}")
            lines.append("")
            lines.append(f"Open command centre: {model.get('primary_cta_url') or model.get('portal_link', '')}")
            if model.get("digest_pdf_attached"):
                lines.append("PDF audit report attached.")
            lines.append("")
            lines.append(
                "Generated from tracked requirements and evidence in Compliance Vault Pro. Not legal advice."
            )
            return "\n".join(lines) + footer
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
        elif template_alias == EmailTemplateAlias.CLIENT_OPERATIONAL_NOTICE:
            subj = (model.get("subject") or "Service notice").strip()
            plain = (model.get("text_message") or "").strip() or _strip_html_to_text(str(model.get("message") or ""))
            lines = [
                subj,
                "",
                _format_greeting(model.get("client_name")),
                "",
                plain,
                "",
                f"Dashboard: {model.get('portal_link', '#')}",
            ]
            if model.get("customer_reference"):
                lines.insert(2, f"Reference: {model['customer_reference']}")
            return "\n".join(lines) + "\n" + footer
        elif template_alias in ONBOARDING_ALIASES:
            c = _get_onboarding_content(template_alias)
            body_html = c.get("body", "")
            body_text = body_html.replace("</p>", "\n").replace("<p>", "").replace("<ul>", "\n").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "\n")
            body_text = html_module.unescape(body_text.strip())
            portal_base = (model.get("portal_base_url") or model.get("portal_link") or _email_app_base()).strip().rstrip("/")
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
            dashboard_link = f"{_email_app_base()}/clearform/dashboard"
        
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
