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
from email_templates.unified.scheduled_report_digest import (
    build_scheduled_report_digest_html,
    build_scheduled_report_digest_text,
)
from utils.branding import CUSTOMER_SUPPORT_FOOTER_PLAIN, SUPPORT_EMAIL
from presentation.label_service import (
    compliance_requirement_status_label,
    document_type_label,
    requirement_label,
)
from services.scoring_semantics_v1 import headline_score_display_for_export

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


def _format_currency_amount_for_email(amount: Any, currency: Optional[str]) -> str:
    """Human-facing amount for quote / invoice lines in email (HTML and text)."""
    code = (currency or "GBP").strip().upper()
    sym = "£" if code == "GBP" else "€" if code == "EUR" else "$" if code == "USD" else f"{code} "
    try:
        n = float(amount)
    except (TypeError, ValueError):
        return f"{sym}—"
    return f"{sym}{n:.2f}"


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


def _safe_reminder_semantic_line(group_key: str, semantic_line: str) -> str:
    line = str(semantic_line or "").strip()
    low = line.lower()
    forbidden_fragments = (
        "blocking compliance",
        "externally verified",
        "legally validated",
        "verified",
        "certified",
        "operationally safe",
        "remediated",
        "remediation complete",
        "upload complete",
        "document-complete",
        "document complete",
        "upload-only complete",
    )
    if any(f in low for f in forbidden_fragments):
        if group_key == "declaration_reminders":
            return "Declaration details need review and update"
        if group_key == "assessment_reminders":
            return "Assessment review due and follow-up actions require attention"
        if group_key == "condition_reminders":
            return "Property condition issues require review"
        if group_key == "certificate_reminders":
            return "Evidence renewal is due"
        return "Compliance action required"
    return line


def _build_grouped_reminder_sections_html(model: Dict[str, Any]) -> str:
    heading_map = [
        ("certificate_reminders", "Certificates & Expiring Evidence"),
        ("declaration_reminders", "Declarations & Tenancy Records"),
        ("assessment_reminders", "Assessments & Reviews"),
        ("condition_reminders", "Property Conditions & Remediation"),
        ("other_reminders", "Other Compliance Actions"),
    ]
    blocks: List[str] = []
    for key, heading in heading_map:
        rows = model.get(key) if isinstance(model.get(key), list) else []
        if not rows:
            continue
        items = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get("type") or row.get("detail_type") or "Compliance item").strip() or "Compliance item"
            semantic = _safe_reminder_semantic_line(key, str(row.get("semantic_line") or "").strip())
            label_h = html_module.escape(label)
            semantic_h = html_module.escape(semantic) if semantic else ""
            if semantic_h:
                items.append(f"<li><strong>{label_h}</strong> — {semantic_h}</li>")
            else:
                items.append(f"<li><strong>{label_h}</strong></li>")
        if not items:
            continue
        blocks.append(
            f"<h4 style=\"margin: 16px 0 8px; color: #0B1D3A;\">{html_module.escape(heading)}</h4><ul style=\"margin: 0 0 10px 18px; color: #334155;\">{''.join(items)}</ul>"
        )
    return "".join(blocks)


def _build_grouped_reminder_sections_text(model: Dict[str, Any]) -> str:
    heading_map = [
        ("certificate_reminders", "Certificates & Expiring Evidence"),
        ("declaration_reminders", "Declarations & Tenancy Records"),
        ("assessment_reminders", "Assessments & Reviews"),
        ("condition_reminders", "Property Conditions & Remediation"),
        ("other_reminders", "Other Compliance Actions"),
    ]
    out: List[str] = []
    for key, heading in heading_map:
        rows = model.get(key) if isinstance(model.get(key), list) else []
        if not rows:
            continue
        out.append(f"{heading}:")
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get("type") or row.get("detail_type") or "Compliance item").strip() or "Compliance item"
            semantic = _safe_reminder_semantic_line(key, str(row.get("semantic_line") or "").strip())
            out.append(f"- {label}" + (f" — {semantic}" if semantic else ""))
        out.append("")
    return "\n".join(out).strip()

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
    EmailTemplateAlias.CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED,
    EmailTemplateAlias.CONTRACTOR_QUOTE_APPROVED,
    EmailTemplateAlias.CONTRACTOR_VISIT_CONFIRMED,
    EmailTemplateAlias.CONTRACTOR_PROOF_REQUIRED,
    EmailTemplateAlias.CONTRACTOR_INVOICE_READY,
    EmailTemplateAlias.CLIENT_PROOF_UPLOADED,
    EmailTemplateAlias.CLIENT_INVOICE_REVIEW_REQUIRED,
    EmailTemplateAlias.CLIENT_QUOTE_REVIEW_REQUIRED,
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
        jur_note_html = ""
        djn = m.get("digest_jurisdiction_framing")
        if djn:
            jur_note_html = (
                '<p style="margin:12px 0;padding:10px 12px;background:#f1f5f9;border-left:4px solid #0f172a;'
                'font-size:13px;color:#0f172a;line-height:1.5;">'
                f"<strong>Jurisdiction context:</strong> {html_module.escape(str(djn))}"
                "</p>"
            )
        jur_fb_html = ""
        djfb = m.get("digest_jurisdiction_fallback_disclaimer")
        if djfb:
            jur_fb_html = (
                '<p style="margin:12px 0;padding:10px 12px;background:#fffbeb;border-left:4px solid #d97706;'
                'font-size:13px;color:#78350f;line-height:1.5;">'
                f"<strong>Default jurisdiction notice:</strong> {html_module.escape(str(djfb))}"
                "</p>"
            )
        hiua_html = ""
        dhl = m.get("digest_hiua_line")
        dhfn = m.get("digest_hiua_report_framing_notice")
        if dhl or dhfn:
            inner_hiua = ""
            if dhl:
                inner_hiua += (
                    '<p style="margin:12px 0 0 0;padding:10px 12px;background:#f5f3ff;border-left:4px solid #6d28d9;'
                    'font-size:13px;color:#4c1d95;line-height:1.55;">'
                    f"<strong>Operational follow-up (applicability):</strong> {html_module.escape(str(dhl))}"
                    "</p>"
                )
            if dhfn:
                inner_hiua += (
                    '<p style="margin:8px 0 0 0;padding:8px 12px 10px 12px;background:#faf5ff;border-left:4px solid #a78bfa;'
                    'font-size:12px;color:#5b21b6;line-height:1.5;">'
                    f"{html_module.escape(str(dhfn))}"
                    "</p>"
                )
            hiua_html = f'<div style="margin:4px 0 8px 0;">{inner_hiua}</div>'
        score_display = html_module.escape(
            str(m.get("compliance_score_display") or headline_score_display_for_export(m.get("compliance_score"), m.get("score_status")))
        )
        score_status = m.get("score_status")
        score_status_esc = html_module.escape(str(score_status)) if score_status else ""
        last_calc = m.get("last_calculated_at")
        last_calc_esc = html_module.escape(str(last_calc)) if last_calc else ""
        risk = html_module.escape(str(m.get("risk_level") or "—"))
        total = int(m.get("total_requirements") or 0)
        valid = int(m.get("valid_count") or m.get("compliant") or 0)
        exp = int(m.get("expiring_soon") or 0)
        ovd = int(m.get("overdue") or 0)
        miss = int(m.get("missing_evidence_count") or 0)

        tpr = m.get("digest_email_top_properties_at_risk") or []
        gen_raw = str(m.get("generated_at_display") or m.get("data_as_of") or "").strip()
        snapshot_framing = (m.get("digest_snapshot_framing_line") or "").strip()
        if not snapshot_framing and gen_raw:
            snapshot_framing = f"Snapshot as of {gen_raw}"
        show_score_snapshot_banner = m.get("include_compliance_summary", True) or (
            bool(tpr) and m.get("include_property_breakdown", True)
        )
        snapshot_html = ""
        if snapshot_framing and show_score_snapshot_banner:
            snapshot_html = (
                '<p style="margin:0 0 12px 0;padding:8px 12px;background:#f1f5f9;border-radius:8px;'
                'font-size:13px;color:#334155;line-height:1.45;">'
                f"{html_module.escape(snapshot_framing)}"
                "</p>"
            )

        def metric_card(title: str, value: str) -> str:
            return (
                f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin:0 0 10px 0;">'
                f'<div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.04em;">{title}</div>'
                f'<div style="font-size:20px;font-weight:700;color:#0f172a;margin-top:4px;">{value}</div></div>'
            )

        top_prop_html = ""
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
                sc_s = html_module.escape(
                    str(headline_score_display_for_export(sc, row.get("score_status")))
                )
                ovd = int(row.get("overdue_count") or 0)
                miss = int(row.get("missing_evidence_count") or 0)
                bits = [f"Headline score {sc_s}", rk]
                if ovd:
                    bits.append(f"{ovd} overdue")
                if miss:
                    bits.append(f"{miss} missing evidence")
                parts.append(f"<li><strong>{nm}</strong> — {html_module.escape(' · '.join(bits))}</li>")
            parts.append("</ul>")
            top_prop_html = "".join(parts)

        cards = ""
        if m.get("include_compliance_summary", True):
            cards += metric_card("Compliance score (headline)", score_display)
            ssm_raw = (m.get("score_status_message") or "").strip()
            if score_status_esc or last_calc_esc or ssm_raw:
                meta_bits: List[str] = []
                if score_status_esc:
                    meta_bits.append(f"Status: {score_status_esc}")
                if last_calc_esc:
                    meta_bits.append(f"Last calculated: {last_calc_esc}")
                if ssm_raw:
                    meta_bits.append(html_module.escape(ssm_raw))
                cards += metric_card("Score semantics", " · ".join(meta_bits))
            cov = m.get("score_coverage")
            if isinstance(cov, dict) and int(cov.get("properties_missing_score") or 0) > 0:
                cards += metric_card(
                    "Score coverage",
                    html_module.escape(
                        f"{int(cov.get('properties_with_score') or 0)} of {int(cov.get('properties_total') or 0)} properties with stored scores; "
                        f"{int(cov.get('properties_missing_score') or 0)} without."
                    ),
                )
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
{jur_note_html}
{jur_fb_html}
{hiua_html}
{snapshot_html}
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
            is_renewal = model.get("receipt_kind") == "subscription_renewal"
            extra_rows = ""
            ps = model.get("payment_status_display")
            if ps:
                pse = html_module.escape(str(ps))
                extra_rows += f'<tr><td style="padding: 8px 0; color: #64748b;">Payment status</td><td style="padding: 8px 0; text-align: right;"><strong>{pse}</strong></td></tr>'
            sid = model.get("stripe_invoice_id_display")
            if sid:
                extra_rows += f'<tr><td style="padding: 8px 0; color: #64748b;">Stripe invoice</td><td style="padding: 8px 0; text-align: right; font-family: monospace; font-size: 12px;">{html_module.escape(str(sid))}</td></tr>'
            snum = model.get("stripe_invoice_number_display")
            if snum:
                extra_rows += f'<tr><td style="padding: 8px 0; color: #64748b;">Invoice number</td><td style="padding: 8px 0; text-align: right; font-family: monospace; font-size: 12px;">{html_module.escape(str(snum))}</td></tr>'
            bp = model.get("billing_period_display")
            if bp:
                extra_rows += f'<tr><td style="padding: 8px 0; color: #64748b;">Billing period</td><td style="padding: 8px 0; text-align: right;">{html_module.escape(str(bp))}</td></tr>'
            nrd = model.get("next_renewal_display")
            if nrd:
                extra_rows += f'<tr><td style="padding: 8px 0; color: #64748b;">Next billing date</td><td style="padding: 8px 0; text-align: right;">{html_module.escape(str(nrd))}</td></tr>'
            host = model.get("hosted_invoice_url")
            if host:
                he = html_module.escape(str(host))
                extra_rows += (
                    '<tr><td style="padding: 8px 0; color: #64748b;">Official invoice</td>'
                    f'<td style="padding: 8px 0; text-align: right;"><a href="{he}" style="color: #00B8A9;">View on Stripe</a></td></tr>'
                )
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
            <table style="width: 100%; max-width: 520px; border-collapse: collapse; margin: 20px 0; font-size: 14px;">
              <tr><td style="padding: 8px 0; color: #64748b;">Amount</td><td style="padding: 8px 0; text-align: right;"><strong>{amount}</strong></td></tr>
              <tr><td style="padding: 8px 0; color: #64748b;">Date</td><td style="padding: 8px 0; text-align: right;">{pdate}</td></tr>
              <tr><td style="padding: 8px 0; color: #64748b;">Reference</td><td style="padding: 8px 0; text-align: right; font-family: monospace; font-size: 12px;">{ref}</td></tr>
              {extra_rows}
            </table>
            <p style="color: #0B1D3A; font-weight: 600;">What happens next</p>
            {next_steps}
            """
            why = (
                "your subscription renewed or was adjusted and Stripe recorded a successful invoice payment."
                if is_renewal
                else "you completed checkout for Compliance Vault Pro."
            )
            header_title = (
                str(model.get("header_title") or "").strip()
                or ("Subscription renewed" if is_renewal else "Payment received")
            )
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body,
                header_title=header_title,
                cta_label=model.get("receipt_cta_label"),
                cta_url=model.get("receipt_cta_url"),
                why_received=why,
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
            grouped_sections_html = _build_grouped_reminder_sections_html(model)
            grouped_block = f"{grouped_sections_html}" if grouped_sections_html else ""
            body = (
                f"<p>This is a reminder that <strong>{req_name}</strong> for your property at <strong>{prop_addr}</strong> is due on <strong>{due_date}</strong>.</p>"
                f"{urgency_line}"
                f"{grouped_block}"
            )
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
            customer_ref = str(model.get("customer_reference") or "").strip()
            ref_badge = (
                f'<span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-left: 10px;">{html_module.escape(customer_ref)}</span>'
                if customer_ref
                else ""
            )
            inner_body, header_title = build_scheduled_report_digest_html(model)
            greeting = _format_greeting(model.get("client_name"))
            portal = str(model.get("portal_link") or "").strip().rstrip("/") or ""
            if not portal or portal == "#":
                portal = f"{_email_app_base()}/today"
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=inner_body,
                header_title=header_title,
                ref_badge=ref_badge,
                cta_label="Open your portal",
                cta_url=portal,
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
        elif template_alias == EmailTemplateAlias.CLIENT_QUOTE_REVIEW_REQUIRED:
            esc = html_module.escape
            greeting = _format_greeting(model.get("client_name"))
            prop = esc(str(model.get("property_address") or "See portal"))
            job_title = esc(str(model.get("job_title") or "Work order"))
            contractor = esc(str(model.get("contractor_name") or "Contractor"))
            woid = esc(str(model.get("work_order_id") or ""))
            amount_disp = esc(_format_currency_amount_for_email(model.get("quoted_price"), model.get("price_currency")))
            notes_raw = (str(model.get("quote_notes") or "")).strip()
            notes_block = ""
            if notes_raw:
                notes_block = (
                    f'<p style="margin: 12px 0 0 0;"><strong>Notes:</strong> {esc(notes_raw)}</p>'
                )
            job_link = str(model.get("client_job_link") or model.get("secure_client_job_link") or "#").strip()
            ref_badge = ""
            if model.get("customer_reference"):
                ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{html_module.escape(str(model["customer_reference"]))}</span></p>'
            body_inner = f"""
            <p>A quote has been submitted for your job.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Job details</h2>
            <p style="margin: 0; line-height: 1.6;">
              <strong>Property:</strong> {prop}<br />
              <strong>Job:</strong> {job_title}<br />
              <strong>Contractor:</strong> {contractor}<br />
              <strong>Work order ID:</strong> {woid}
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Quote summary</h2>
            <p style="margin: 0;"><strong>Amount:</strong> {amount_disp}</p>
            {notes_block}
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">▶ Next step: Review and approve</h2>
            <p>Work will not begin until you approve the quote in the platform.</p>
            <p style="margin: 12px 0 8px 0;"><strong>Review the quote:</strong></p>
            <p style="margin: 0;"><a href="{job_link}" style="color: #00B8A9; word-break: break-all;">{esc(job_link)}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">What happens next</h2>
            <ul style="margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;">
              <li><strong>Approve</strong> — the contractor can proceed with the job</li>
              <li><strong>Reject</strong> — the contractor can submit a revised quote for you to review again</li>
            </ul>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Important</h2>
            <ul style="margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;">
              <li>Do not ask the contractor to start billable work until you have approved the quote here</li>
            </ul>
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body_inner,
                header_title="Quote submitted — your review needed",
                ref_badge=ref_badge,
                cta_label="Review quote",
                cta_url=job_link or "#",
                why_received="a contractor submitted a quote for a job linked to your account.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=model.get("customer_reference"),
            )
        elif template_alias == EmailTemplateAlias.CLIENT_PROOF_UPLOADED:
            esc = html_module.escape
            greeting = _format_greeting(model.get("client_name"))
            prop = esc(str(model.get("property_address") or "See portal"))
            job_title = esc(str(model.get("job_title") or "Work order"))
            contractor = esc(str(model.get("contractor_name") or "Contractor"))
            woid = esc(str(model.get("work_order_id") or ""))
            job_link = str(
                model.get("client_job_link") or model.get("secure_client_job_link") or model.get("portal_link") or "#"
            ).strip()
            hint = str(model.get("compliance_outcome_hint") or "").strip()
            hint_block = ""
            if hint:
                hint_block = (
                    f'<p style="margin: 16px 0 0 0; line-height: 1.6; color: #64748b; font-size: 14px;">{esc(hint)}</p>'
                )
            compl_extra = ""
            if model.get("is_compliance"):
                compl_extra = (
                    '<p style="margin: 16px 0 0 0; line-height: 1.6; color: #334155;">'
                    "You can review the evidence now; compliance validation may still be in progress."
                    "</p>"
                )
            ref_badge = ""
            if model.get("customer_reference"):
                ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{html_module.escape(str(model["customer_reference"]))}</span></p>'
            body_inner = f"""
            <p>Evidence has been uploaded for your job.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Job details</h2>
            <p style="margin: 0; line-height: 1.6;">
              <strong>Property:</strong> {prop}<br />
              <strong>Job:</strong> {job_title}<br />
              <strong>Contractor:</strong> {contractor}<br />
              <strong>Work order ID:</strong> {woid}
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">▶ Next step: Review evidence</h2>
            <p style="margin: 0; line-height: 1.6;">You can now review the uploaded evidence in your portal.</p>
            <p style="margin: 12px 0 8px 0;"><strong>Access your job:</strong></p>
            <p style="margin: 0;"><a href="{job_link}" style="color: #00B8A9; word-break: break-all;">{esc(job_link)}</a></p>
            {compl_extra}
            {hint_block}
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body_inner,
                header_title="New evidence on your job",
                ref_badge=ref_badge,
                cta_label="Review evidence",
                cta_url=job_link or "#",
                why_received="a contractor uploaded evidence for a job linked to your account.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=model.get("customer_reference"),
            )
        elif template_alias == EmailTemplateAlias.CLIENT_INVOICE_REVIEW_REQUIRED:
            esc = html_module.escape
            greeting = _format_greeting(model.get("client_name"))
            prop = esc(str(model.get("property_address") or "See portal"))
            job_title = esc(str(model.get("job_title") or "Work order"))
            contractor = esc(str(model.get("contractor_name") or "Contractor"))
            woid = esc(str(model.get("work_order_id") or ""))
            iid = esc(str(model.get("invoice_id") or ""))
            inv_no_raw = str(model.get("invoice_number") or "").strip()
            inv_no_line = ""
            if inv_no_raw:
                inv_no_line = f'<p style="margin: 6px 0 0 0;"><strong>Invoice reference:</strong> {esc(inv_no_raw)}</p>'
            amount_disp = esc(_format_currency_amount_for_email(model.get("invoice_amount"), model.get("price_currency")))
            review_link = str(
                model.get("invoice_review_link")
                or model.get("secure_client_job_link")
                or model.get("portal_link")
                or model.get("client_job_link")
                or "#"
            ).strip()
            job_link = str(model.get("client_job_link") or "#").strip()
            has_quote = bool(model.get("has_agreed_price"))
            agreed_line = ""
            if has_quote:
                agreed_line = (
                    "<li>This invoice is expected to align with the agreed quote for this job—please confirm it looks right before you approve.</li>"
                )
            ref_badge = ""
            if model.get("customer_reference"):
                ref_badge = f'<p style="margin-top: 10px;"><span style="background-color: #00B8A9; color: white; padding: 4px 12px; border-radius: 4px; font-family: monospace; font-size: 13px;">{html_module.escape(str(model["customer_reference"]))}</span></p>'
            body_inner = f"""
            <p>An invoice has been submitted for your review.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Job details</h2>
            <p style="margin: 0; line-height: 1.6;">
              <strong>Property:</strong> {prop}<br />
              <strong>Job:</strong> {job_title}<br />
              <strong>Contractor:</strong> {contractor}<br />
              <strong>Work order ID:</strong> {woid}
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Invoice summary</h2>
            <p style="margin: 0;"><strong>Amount:</strong> {amount_disp}</p>
            <p style="margin: 6px 0 0 0;"><strong>Invoice ID:</strong> {iid}</p>
            {inv_no_line}
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">▶ Next step: Review invoice</h2>
            <p style="margin: 0; line-height: 1.6;">Please review and approve or reject the invoice in your portal.</p>
            <p style="margin: 12px 0 8px 0;"><strong>Open Approvals:</strong></p>
            <p style="margin: 0;"><a href="{review_link}" style="color: #00B8A9; word-break: break-all;">{esc(review_link)}</a></p>
            <p style="margin: 12px 0 0 0; font-size: 14px; color: #64748b;">Related job: <a href="{job_link}" style="color: #00B8A9;">{esc(job_link)}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Important</h2>
            <ul style="margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;">
              {agreed_line}
              <li>Review the amount and description before you approve.</li>
              <li>You can approve, reject, or request more information from Approvals.</li>
            </ul>
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body_inner,
                header_title="Invoice ready for review",
                ref_badge=ref_badge,
                cta_label="Review invoice",
                cta_url=review_link or "#",
                why_received="a contractor submitted an invoice linked to your account for approval.",
                show_preferences_link=True,
                preferences_url=_notification_preferences_url(model) or None,
                customer_reference=model.get("customer_reference"),
            )
        elif template_alias == EmailTemplateAlias.CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED:
            esc = html_module.escape
            contractor_key = model.get("contractor_name")
            greeting = _format_greeting(str(contractor_key).strip() if contractor_key else None)
            prop = esc(str(model.get("property_address") or "See portal"))
            job_title = esc(str(model.get("job_title") or "Work order"))
            woid = esc(str(model.get("work_order_id") or ""))
            job_kind = esc(str(model.get("job_kind") or "MAINTENANCE"))
            juris = (str(model.get("jurisdiction") or "")).strip()
            juris_block = (
                f'<p style="margin: 8px 0 0 0;"><strong>Jurisdiction:</strong> {esc(juris)}</p>' if juris else ""
            )
            due_raw = (str(model.get("due_date") or "")).strip()
            sla_raw = (str(model.get("sla_summary") or "")).strip()
            due_block = ""
            if due_raw:
                due_block = f'<p style="margin: 8px 0 0 0;"><strong>Due:</strong> {esc(due_raw)}</p>'
            elif sla_raw:
                due_block = f'<p style="margin: 8px 0 0 0;">{esc(sla_raw)}</p>'
            secure = str(model.get("secure_job_link") or "#").strip()
            is_compl = bool(model.get("is_compliance"))
            compliance_li = ""
            if is_compl:
                compliance_li = (
                    "<li>Completion requires a certificate or proof uploaded in the platform.</li>"
                )
            body_inner = f"""
            <p>You've been assigned a new job.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Job details</h2>
            <p style="margin: 0; line-height: 1.6;">
              <strong>Property:</strong> {prop}<br />
              <strong>Job:</strong> {job_title}<br />
              <strong>Work order ID:</strong> {woid}<br />
              <strong>Job type:</strong> {job_kind}
            </p>
            {juris_block}
            {due_block}
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">▶ Next step: Submit your quote</h2>
            <p>Before any work can begin, please provide your price for this job.</p>
            <p style="margin: 12px 0 8px 0;"><strong>Access the job securely</strong> using the button below (same link for reference):</p>
            <p style="margin: 0;"><a href="{secure}" style="color: #00B8A9; word-break: break-all;">{esc(secure)}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">What happens next</h2>
            <ul style="margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;">
              <li>You submit your quote</li>
              <li>The client reviews and approves</li>
              <li>Once approved, you can schedule and carry out the work</li>
            </ul>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Important</h2>
            <ul style="margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;">
              <li>Work cannot begin until your quote is approved</li>
              <li>Your invoice must match the approved price</li>
              {compliance_li}
            </ul>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Payment</h2>
            <p style="margin: 0; line-height: 1.6;">The client pays you directly.<br />
            Pleerity Enterprise manages job tracking and invoice approval.</p>
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body_inner,
                header_title="New job — submit your quote",
                cta_label="View job and submit quote",
                cta_url=secure or "#",
                why_received="you have been assigned a work order and the client requires an approved quote before work can begin.",
                show_preferences_link=False,
                customer_reference=None,
            )
        elif template_alias == EmailTemplateAlias.CONTRACTOR_QUOTE_APPROVED:
            esc = html_module.escape
            greeting = _format_greeting(str(model.get("contractor_name") or "").strip() or None)
            prop = esc(str(model.get("property_address") or "See portal"))
            job_title = esc(str(model.get("job_title") or "Work order"))
            price_disp = esc(
                _format_currency_amount_for_email(model.get("approved_price"), model.get("price_currency"))
            )
            secure = str(model.get("secure_job_link") or "#").strip()
            next_action = esc(str(model.get("next_action") or "Schedule and carry out the agreed work."))
            is_compl = bool(model.get("is_compliance"))
            compliance_li = ""
            if is_compl:
                compliance_li = (
                    "<li>A valid certificate or proof must be uploaded in the platform to complete the job.</li>"
                )
            body_inner = f"""
            <p>Your quote has been approved.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Job details</h2>
            <p style="margin: 0; line-height: 1.6;">
              <strong>Property:</strong> {prop}<br />
              <strong>Job:</strong> {job_title}
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Approved price</h2>
            <p style="margin: 0; font-size: 18px; font-weight: 600; color: #0B1D3A;">{price_disp}</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">▶ Next step: Proceed with the job</h2>
            <p>You can now schedule and carry out the work.</p>
            <p style="margin: 12px 0 8px 0; line-height: 1.6;">{next_action}</p>
            <p style="margin: 12px 0 8px 0;"><strong>Access the job securely</strong> using the button below (link for reference):</p>
            <p style="margin: 0;"><a href="{secure}" style="color: #00B8A9; word-break: break-all;">{esc(secure)}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Important</h2>
            <ul style="margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;">
              {compliance_li}
              <li>Your invoice must match the approved price.</li>
            </ul>
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body_inner,
                header_title="Your quote was approved",
                cta_label="Open job",
                cta_url=secure or "#",
                why_received="the client approved your quote for a job assigned to you.",
                show_preferences_link=False,
                customer_reference=None,
            )
        elif template_alias == EmailTemplateAlias.CONTRACTOR_VISIT_CONFIRMED:
            esc = html_module.escape
            greeting = _format_greeting(str(model.get("contractor_name") or "").strip() or None)
            prop = esc(str(model.get("property_address") or "See portal"))
            job_title = esc(str(model.get("job_title") or "Work order"))
            wid = esc(str(model.get("work_order_id") or ""))
            sched_date = esc(str(model.get("scheduled_date") or ""))
            sched_time = esc(str(model.get("scheduled_time") or ""))
            tz_disp = esc(str(model.get("timezone") or "UTC"))
            secure = str(model.get("secure_job_link") or "#").strip()
            kind_note = ""
            if model.get("is_compliance"):
                kind_note = (
                    '<p style="margin: 0 0 0 0; line-height: 1.6; color: #64748b; font-size: 14px;">'
                    "This is a compliance visit—please upload the required certificate or proof when the work is complete."
                    "</p>"
                )
            body_inner = f"""
            <p>Your visit has been confirmed.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Job details</h2>
            <p style="margin: 0; line-height: 1.6;">
              <strong>Property:</strong> {prop}<br />
              <strong>Job:</strong> {job_title}<br />
              <strong>Work order:</strong> {wid}
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Scheduled time</h2>
            <p style="margin: 0; line-height: 1.6; font-size: 16px;">
              <strong>{sched_date} at {sched_time}</strong> ({tz_disp})
            </p>
            {kind_note}
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <p style="margin: 0; line-height: 1.6;">Open the job for full details and next actions.</p>
            <p style="margin: 12px 0 0 0; line-height: 1.6;">Please attend as scheduled and update the job status when appropriate.</p>
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body_inner,
                header_title="Your visit is confirmed",
                cta_label="View job",
                cta_url=secure or "#",
                why_received="a visit time for a job assigned to you was confirmed.",
                show_preferences_link=False,
                customer_reference=None,
            )
        elif template_alias == EmailTemplateAlias.CONTRACTOR_PROOF_REQUIRED:
            esc = html_module.escape
            greeting = _format_greeting(str(model.get("contractor_name") or "").strip() or None)
            prop = esc(str(model.get("property_address") or "See portal"))
            job_title = esc(str(model.get("job_title") or "Work order"))
            wid = esc(str(model.get("work_order_id") or ""))
            hint = esc(str(model.get("proof_type_hint") or "completion proof"))
            secure = str(model.get("secure_job_link") or "#").strip()
            is_compl = bool(model.get("is_compliance"))
            if is_compl:
                important_ul = (
                    "<ul style=\"margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;\">"
                    "<li>The job cannot be completed or verified without valid proof.</li>"
                    "<li>A certificate (or required compliance document) must be uploaded for validation.</li>"
                    "</ul>"
                )
            else:
                important_ul = (
                    "<ul style=\"margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;\">"
                    "<li>The job cannot be completed or verified without valid proof.</li>"
                    "<li>Please upload relevant evidence (photos, report, or invoice documentation) as appropriate.</li>"
                    "</ul>"
                )
            body_inner = f"""
            <p>This job requires completion proof before it can be finalised.</p>
            <p style="margin: 12px 0 0 0; line-height: 1.6;">Upload the required evidence to continue. We are looking for: <strong>{hint}</strong>.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Job details</h2>
            <p style="margin: 0; line-height: 1.6;">
              <strong>Property:</strong> {prop}<br />
              <strong>Job:</strong> {job_title}<br />
              <strong>Work order:</strong> {wid}
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">▶ Next step: Upload proof</h2>
            <p style="margin: 0; line-height: 1.6;">Please upload the required evidence in the job.</p>
            <p style="margin: 12px 0 8px 0;"><strong>Access the job securely:</strong></p>
            <p style="margin: 0;"><a href="{secure}" style="color: #00B8A9; word-break: break-all;">{esc(secure)}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Important</h2>
            {important_ul}
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body_inner,
                header_title="Completion proof required",
                cta_label="Upload proof",
                cta_url=secure or "#",
                why_received="your job is in a stage where completion evidence must be uploaded before it can be finalised.",
                show_preferences_link=False,
                customer_reference=None,
            )
        elif template_alias == EmailTemplateAlias.CONTRACTOR_INVOICE_READY:
            esc = html_module.escape
            greeting = _format_greeting(str(model.get("contractor_name") or "").strip() or None)
            prop = esc(str(model.get("property_address") or "See portal"))
            job_title = esc(str(model.get("job_title") or "Work order"))
            wid = esc(str(model.get("work_order_id") or ""))
            ap = model.get("approved_price")
            ap_line = str(model.get("approved_price_display") or "").strip()
            if ap_line:
                price_disp = esc(ap_line)
            elif ap is not None:
                price_disp = esc(_format_currency_amount_for_email(ap, model.get("price_currency")))
            else:
                price_disp = esc("As agreed with your client (see job details)")
            secure = str(model.get("secure_job_link") or "#").strip()
            body_inner = f"""
            <p>This job is now ready for invoicing.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Job details</h2>
            <p style="margin: 0; line-height: 1.6;">
              <strong>Property:</strong> {prop}<br />
              <strong>Job:</strong> {job_title}<br />
              <strong>Work order:</strong> {wid}
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Approved price</h2>
            <p style="margin: 0; font-size: 18px; font-weight: 600; color: #0B1D3A;">{price_disp}</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">▶ Next step: Submit your invoice</h2>
            <p style="margin: 0; line-height: 1.6;">Submit your invoice using the approved amount.</p>
            <p style="margin: 12px 0 8px 0;"><strong>Access the job securely:</strong></p>
            <p style="margin: 0;"><a href="{secure}" style="color: #00B8A9; word-break: break-all;">{esc(secure)}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <h2 style="color: #0B1D3A; font-size: 16px; margin: 0 0 12px 0;">Important</h2>
            <ul style="margin: 8px 0; padding-left: 20px; color: #334155; line-height: 1.6;">
              <li>Your invoice must match the approved price (or the agreed scope for this job).</li>
              <li>The official invoice number is generated by Pleerity when you submit.</li>
              <li>You may include your own reference on the invoice if the form allows it.</li>
            </ul>
            """
            return _customer_email_html(
                model,
                greeting=greeting,
                body_html=body_inner,
                header_title="Ready for invoicing",
                cta_label="Submit invoice",
                cta_url=secure or "#",
                why_received="your assigned job is now eligible for you to submit an invoice in the platform.",
                show_preferences_link=False,
                customer_reference=None,
            )
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
            footer = self._build_email_footer(model)
            customer_ref = model.get("customer_reference", "")
            ref_line = f"<p>Your Reference: <strong>{customer_ref}</strong></p>" if customer_ref else ""
            if model.get("admin_manual_structured") and str(model.get("admin_manual_summary") or "").strip():
                from email_templates.admin_manual_structured_layout import build_admin_manual_structured_html

                inner = build_admin_manual_structured_html(
                    model,
                    footer_html="",
                    customer_reference_html=ref_line or "",
                )
                return inner.replace("</body>", f"{footer}</body>", 1)
            # Legacy: single block (message or body).
            body_content = model.get("message") or model.get("body") or "You have a new notification from Compliance Vault Pro."
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
            is_ren = model.get("receipt_kind") == "subscription_renewal"
            extra_lines = ""
            if model.get("payment_status_display"):
                extra_lines += f"Payment status: {model.get('payment_status_display')}\n"
            if model.get("stripe_invoice_id_display"):
                extra_lines += f"Stripe invoice: {model.get('stripe_invoice_id_display')}\n"
            if model.get("stripe_invoice_number_display"):
                extra_lines += f"Invoice number: {model.get('stripe_invoice_number_display')}\n"
            if model.get("billing_period_display"):
                extra_lines += f"Billing period: {model.get('billing_period_display')}\n"
            if model.get("next_renewal_display"):
                extra_lines += f"Next billing date: {model.get('next_renewal_display')}\n"
            if model.get("hosted_invoice_url"):
                extra_lines += f"Hosted invoice: {model.get('hosted_invoice_url')}\n"
            title = "Subscription renewed" if is_ren else "Payment received"
            next_default = (
                "Your subscription remains active. See Billing in the portal for receipts and payment methods.\n"
                if is_ren
                else "1. You'll receive a separate email to set your password.\n2. After activation, sign in to manage properties and compliance.\n"
            )
            next_block = model.get("next_steps_text") or next_default
            return f"""
{title} — Compliance Vault Pro
{ref_line}

{_format_greeting(model.get('client_name'))}

Thank you. Your payment was received.

Plan: {model.get('plan_name', '')}
Amount: {model.get('amount_display', '')}
Date: {model.get('payment_date_display', '')}
Reference: {model.get('reference_display', '')}
{extra_lines}
What happens next:
{next_block}
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
            grouped_sections_text = _build_grouped_reminder_sections_text(model)
            grouped_block = f"\n\n{grouped_sections_text}" if grouped_sections_text else ""
            return f"""
Compliance Action Required
=========================
{ref_line}

Hello {model.get('client_name', 'Valued Customer')},

This is a reminder that {req_name} for your property at {prop_addr} is due on {due_date}.

{urgency_line}
{grouped_block}

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
            digest = build_scheduled_report_digest_text(model)
            return f"""{_format_greeting(model.get('client_name'))}

{digest}{footer}
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
                ]
            )
            snap_txt = (model.get("digest_snapshot_framing_line") or "").strip()
            if not snap_txt:
                _gr = str(model.get("generated_at_display") or model.get("data_as_of") or "").strip()
                if _gr:
                    snap_txt = f"Snapshot as of {_gr}"
            if snap_txt:
                lines.append(snap_txt)
                lines.append("")
            lines.extend(
                [
                    f"Compliance score (headline): {model.get('compliance_score_display') or headline_score_display_for_export(model.get('compliance_score'), model.get('score_status'))}",
                    f"Score status: {model.get('score_status') or '—'}",
                    f"Last calculated (headline): {model.get('last_calculated_at') or model.get('portfolio_last_calculated_at') or '—'}",
                ]
            )
            ssm_plain = (model.get("score_status_message") or "").strip()
            if ssm_plain:
                lines.append(f"Headline note: {ssm_plain}")
            lines.extend(
                [
                    f"Risk: {model.get('risk_level', '')}",
                    f"Requirements: {model.get('total_requirements', 0)} (valid {model.get('valid_count', model.get('compliant', 0))}, "
                    f"expiring soon {model.get('expiring_soon', 0)}, overdue {model.get('overdue', 0)}, "
                    f"missing evidence {model.get('missing_evidence_count', 0)})",
                    "",
                ]
            )
            dhl_txt = model.get("digest_hiua_line")
            dhfn_txt = model.get("digest_hiua_report_framing_notice")
            if dhl_txt or dhfn_txt:
                lines.append("OPERATIONAL FOLLOW-UP (APPLICABILITY — NOT A CONFIRMED BREACH FLAG)")
                if dhl_txt:
                    lines.append(str(dhl_txt))
                if dhfn_txt:
                    lines.append(str(dhfn_txt))
                lines.append("")
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
            if model.get("severity_label"):
                sl = str(model.get("severity_label", "")).replace("_", " ")
                title = model.get("presentation_title") or model.get("title", "Internal alert")
                lines = [f"[{sl}] {title}", ""]
                osum = (model.get("operational_summary") or "").strip()
                if osum:
                    lines.append(osum)
                bio = str(model.get("business_impact") or "").strip()
                if bio and bio != osum:
                    lines.extend(["", "Operational impact: " + bio])
                cust = str(model.get("customer_impact") or "").strip()
                if cust:
                    lines.extend(["", "Customer impact: " + cust])
                comp = str(model.get("affected_component") or model.get("component") or "").strip()
                scope = str(model.get("affected_scope") or "").strip()
                if comp or scope:
                    lines.append("")
                    if comp:
                        lines.append("Component: " + comp)
                    if scope:
                        lines.append("Scope: " + scope)
                action = (model.get("recommended_actions") or model.get("suggested_action") or "").strip()
                if action:
                    lines.extend(["", "Recommended actions: " + action])
                res = str(model.get("resolution_link") or model.get("incident_link") or "").strip()
                obs = str(model.get("dashboard_link") or "").strip()
                if res:
                    lines.extend(["", "Open incident: " + res])
                if obs and obs != res:
                    lines.extend(["", "Observability: " + obs])
                tech = str(model.get("technical_details") or "").strip()
                if tech:
                    lines.extend(["", "--- Technical details ---", tech])
                ts = model.get("timestamp", "")
                if ts:
                    lines.extend(["", str(ts)])
                ref = str(model.get("severity", "")).strip()
                if ref:
                    lines.extend(["", f"(Stored severity reference: {ref})"])
                return "\n".join(lines) + "\n" + footer
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
        elif template_alias == EmailTemplateAlias.CLIENT_QUOTE_REVIEW_REQUIRED:
            greet = _format_greeting(model.get("client_name"))
            amt = _format_currency_amount_for_email(model.get("quoted_price"), model.get("price_currency"))
            notes_raw = (str(model.get("quote_notes") or "")).strip()
            link = str(model.get("client_job_link") or model.get("secure_client_job_link") or "#")
            lines = [
                greet,
                "",
                "A quote has been submitted for your job.",
                "",
                "Job details",
                f"Property: {model.get('property_address') or 'See portal'}",
                f"Job: {model.get('job_title') or 'Work order'}",
                f"Contractor: {model.get('contractor_name') or 'Contractor'}",
                f"Work order ID: {model.get('work_order_id') or ''}",
                "",
                "Quote summary",
                f"Amount: {amt}",
            ]
            if notes_raw:
                lines.append(f"Notes: {notes_raw}")
            lines.extend(
                [
                    "",
                    "Next step: Review and approve",
                    "",
                    "Work will not begin until you approve the quote in the platform.",
                    "",
                    "Review the quote:",
                    link,
                    "",
                    "What happens next",
                    "- Approve — the contractor can proceed with the job",
                    "- Reject — the contractor can submit a revised quote for you to review again",
                    "",
                    "Important",
                    "- Do not ask the contractor to start billable work until you have approved the quote in the portal.",
                ]
            )
            return "\n".join(lines) + footer
        elif template_alias == EmailTemplateAlias.CLIENT_PROOF_UPLOADED:
            greet = _format_greeting(model.get("client_name"))
            link = str(
                model.get("client_job_link") or model.get("secure_client_job_link") or model.get("portal_link") or "#"
            )
            hint = str(model.get("compliance_outcome_hint") or "").strip()
            lines = [
                greet,
                "",
                "Evidence has been uploaded for your job.",
                "",
                "Job details",
                f"Property: {model.get('property_address') or 'See portal'}",
                f"Job: {model.get('job_title') or 'Work order'}",
                f"Contractor: {model.get('contractor_name') or 'Contractor'}",
                f"Work order ID: {model.get('work_order_id') or ''}",
                "",
                "Next step: Review evidence",
                "",
                "You can now review the uploaded evidence in your portal.",
                "",
                "Access your job:",
                link,
            ]
            if model.get("is_compliance"):
                lines.extend(
                    [
                        "",
                        "You can review the evidence now; compliance validation may still be in progress.",
                    ]
                )
            if hint:
                lines.extend(["", hint])
            return "\n".join(lines) + footer
        elif template_alias == EmailTemplateAlias.CLIENT_INVOICE_REVIEW_REQUIRED:
            greet = _format_greeting(model.get("client_name"))
            amt = _format_currency_amount_for_email(model.get("invoice_amount"), model.get("price_currency"))
            review_link = str(
                model.get("invoice_review_link")
                or model.get("secure_client_job_link")
                or model.get("portal_link")
                or model.get("client_job_link")
                or "#"
            )
            job_link = str(model.get("client_job_link") or "#")
            inv_no = str(model.get("invoice_number") or "").strip()
            lines = [
                greet,
                "",
                "An invoice has been submitted for your review.",
                "",
                "Job details",
                f"Property: {model.get('property_address') or 'See portal'}",
                f"Job: {model.get('job_title') or 'Work order'}",
                f"Contractor: {model.get('contractor_name') or 'Contractor'}",
                f"Work order ID: {model.get('work_order_id') or ''}",
                "",
                "Invoice summary",
                f"Amount: {amt}",
                f"Invoice ID: {model.get('invoice_id') or ''}",
            ]
            if inv_no:
                lines.append(f"Invoice reference: {inv_no}")
            lines.extend(
                [
                    "",
                    "Next step: Review invoice",
                    "",
                    "Please review and approve or reject the invoice in your portal.",
                    "",
                    "Open Approvals:",
                    review_link,
                    "",
                    f"Related job: {job_link}",
                    "",
                    "Important",
                ]
            )
            if model.get("has_agreed_price"):
                lines.append(
                    "- This invoice is expected to align with the agreed quote for this job—please confirm it looks right before you approve."
                )
            lines.extend(
                [
                    "- Review the amount and description before you approve.",
                    "- You can approve, reject, or request more information from Approvals.",
                ]
            )
            return "\n".join(lines) + footer
        elif template_alias == EmailTemplateAlias.CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED:
            ck = model.get("contractor_name")
            greet = _format_greeting(str(ck).strip() if ck else None)
            lines = [
                greet,
                "",
                "You've been assigned a new job.",
                "",
                "Job details",
                f"Property: {model.get('property_address') or 'See portal'}",
                f"Job: {model.get('job_title') or 'Work order'}",
                f"Work order ID: {model.get('work_order_id') or ''}",
                f"Job type: {model.get('job_kind') or 'MAINTENANCE'}",
            ]
            if (str(model.get("jurisdiction") or "")).strip():
                lines.append(f"Jurisdiction: {model.get('jurisdiction')}")
            if (str(model.get("due_date") or "")).strip():
                lines.append(f"Due: {model.get('due_date')}")
            elif (str(model.get("sla_summary") or "")).strip():
                lines.append(str(model.get("sla_summary")))
            lines.extend(
                [
                    "",
                    "Next step: Submit your quote",
                    "",
                    "Before any work can begin, please provide your price for this job.",
                    "",
                    "Access the job securely:",
                    str(model.get("secure_job_link") or "#"),
                    "",
                    "What happens next",
                    "- You submit your quote",
                    "- The client reviews and approves",
                    "- Once approved, you can schedule and carry out the work",
                    "",
                    "Important",
                    "- Work cannot begin until your quote is approved",
                    "- Your invoice must match the approved price",
                ]
            )
            if model.get("is_compliance"):
                lines.append("- Completion requires a certificate or proof uploaded in the platform.")
            lines.extend(
                [
                    "",
                    "Payment",
                    "The client pays you directly.",
                    "Pleerity Enterprise manages job tracking and invoice approval.",
                ]
            )
            return "\n".join(lines) + footer
        elif template_alias == EmailTemplateAlias.CONTRACTOR_QUOTE_APPROVED:
            greet = _format_greeting(str(model.get("contractor_name") or "").strip() or None)
            amt = _format_currency_amount_for_email(model.get("approved_price"), model.get("price_currency"))
            link = str(model.get("secure_job_link") or "#")
            lines = [
                greet,
                "",
                "Your quote has been approved.",
                "",
                "Job details",
                f"Property: {model.get('property_address') or 'See portal'}",
                f"Job: {model.get('job_title') or 'Work order'}",
                "",
                "Approved price",
                amt,
                "",
                "Next step: Proceed with the job",
                "",
                "You can now schedule and carry out the work.",
                str(model.get("next_action") or "Schedule and carry out the agreed work."),
                "",
                "Access the job securely:",
                link,
                "",
                "Important",
            ]
            if model.get("is_compliance"):
                lines.append("- A valid certificate or proof must be uploaded in the platform to complete the job.")
            lines.append("- Your invoice must match the approved price.")
            return "\n".join(lines) + footer
        elif template_alias == EmailTemplateAlias.CONTRACTOR_VISIT_CONFIRMED:
            greet = _format_greeting(str(model.get("contractor_name") or "").strip() or None)
            tz_disp = str(model.get("timezone") or "UTC")
            link = str(model.get("secure_job_link") or "#")
            lines = [
                greet,
                "",
                "Your visit has been confirmed.",
                "",
                "Job details",
                f"Property: {model.get('property_address') or 'See portal'}",
                f"Job: {model.get('job_title') or 'Work order'}",
                f"Work order: {model.get('work_order_id') or ''}",
                "",
                "Scheduled time",
                f"{model.get('scheduled_date') or ''} at {model.get('scheduled_time') or ''} ({tz_disp})",
                "",
            ]
            if model.get("is_compliance"):
                lines.append(
                    "This is a compliance visit—upload the required certificate or proof when the work is complete."
                )
                lines.append("")
            lines.extend(
                [
                    "Open the job for full details and next actions:",
                    link,
                    "",
                    "Please attend as scheduled and update the job status when appropriate.",
                ]
            )
            return "\n".join(lines) + footer
        elif template_alias == EmailTemplateAlias.CONTRACTOR_PROOF_REQUIRED:
            greet = _format_greeting(str(model.get("contractor_name") or "").strip() or None)
            link = str(model.get("secure_job_link") or "#")
            hint = str(model.get("proof_type_hint") or "completion proof")
            lines = [
                greet,
                "",
                "This job requires completion proof before it can be finalised.",
                "",
                "Upload the required evidence to continue.",
                f"We are looking for: {hint}",
                "",
                "Job details",
                f"Property: {model.get('property_address') or 'See portal'}",
                f"Job: {model.get('job_title') or 'Work order'}",
                f"Work order: {model.get('work_order_id') or ''}",
                "",
                "Next step: Upload proof",
                "",
                "Access the job securely:",
                link,
                "",
                "Important",
                "- The job cannot be completed or verified without valid proof.",
            ]
            if model.get("is_compliance"):
                lines.append("- A certificate (or required compliance document) must be uploaded for validation.")
            else:
                lines.append("- Please upload relevant evidence (photos, report, or invoice documentation) as appropriate.")
            return "\n".join(lines) + footer
        elif template_alias == EmailTemplateAlias.CONTRACTOR_INVOICE_READY:
            greet = _format_greeting(str(model.get("contractor_name") or "").strip() or None)
            link = str(model.get("secure_job_link") or "#")
            ap = model.get("approved_price")
            ap_line = str(model.get("approved_price_display") or "").strip()
            if ap_line:
                price_line = ap_line
            elif ap is not None:
                price_line = _format_currency_amount_for_email(ap, model.get("price_currency"))
            else:
                price_line = "As agreed with your client (see job details)"
            lines = [
                greet,
                "",
                "This job is now ready for invoicing.",
                "",
                "Job details",
                f"Property: {model.get('property_address') or 'See portal'}",
                f"Job: {model.get('job_title') or 'Work order'}",
                f"Work order: {model.get('work_order_id') or ''}",
                "",
                "Approved price",
                price_line,
                "",
                "Next step: Submit your invoice",
                "",
                "Submit your invoice using the approved amount.",
                "",
                "Access the job securely:",
                link,
                "",
                "Important",
                "- Your invoice must match the approved price (or the agreed scope for this job).",
                "- The official invoice number is generated by Pleerity when you submit.",
                "- You may include your own reference on the invoice if the form allows it.",
            ]
            return "\n".join(lines) + footer
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
        elif template_alias == EmailTemplateAlias.ADMIN_MANUAL:
            if model.get("admin_manual_structured") and str(model.get("admin_manual_summary") or "").strip():
                from email_templates.admin_manual_structured_layout import build_admin_manual_structured_plain_text

                return build_admin_manual_structured_plain_text(model, footer=footer)
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
