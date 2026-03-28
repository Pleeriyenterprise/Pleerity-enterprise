"""
Shared customer email layout. All customer-facing emails must use this layout.
Internal/staff notifications must NOT use this module.

Branding: pass ``**merge_branding_kwargs(model, ...)`` so orchestrator-injected
``_email_branding`` is applied; explicit keyword arguments override branding.
"""
from typing import Any, Dict, Optional

from utils.branding import SUPPORT_EMAIL, format_customer_support_footer_html

# Brand constants (Pleerity defaults)
COMPANY_NAME = "Pleerity Enterprise Ltd"
TAGLINE = "AI-Driven Solutions & Compliance"
SECURITY_NOTE = "For security, Pleerity will never ask for your password by email."
PREFERENCES_LINK_TEXT = "Manage notification preferences"

# Primary teal used across Pleerity UI
PRIMARY_COLOR = "#00B8A9"
HEADER_BG = "#0B1D3A"


def merge_branding_kwargs(model: Optional[Dict[str, Any]], **explicit: Any) -> Dict[str, Any]:
    """Merge orchestrator ``_email_branding`` into explicit layout kwargs (explicit wins)."""
    base: Dict[str, Any] = {}
    if model and isinstance(model.get("_email_branding"), dict):
        base = dict(model["_email_branding"])
    base.update(explicit)
    return base


def build_customer_email_layout(
    greeting: str,
    body_html: str,
    *,
    header_title: Optional[str] = None,
    ref_badge: str = "",
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    why_received: Optional[str] = None,
    show_preferences_link: bool = False,
    preferences_url: Optional[str] = None,
    company_name: str = COMPANY_NAME,
    tagline: str = TAGLINE,
    support_email: str = SUPPORT_EMAIL,
    website_url: Optional[str] = None,
    security_note: str = SECURITY_NOTE,
    customer_reference: Optional[str] = None,
    header_bg: str = HEADER_BG,
    link_color: str = PRIMARY_COLOR,
    support_footer_html: Optional[str] = None,
    powered_by_html: str = "",
    header_logo_html: str = "",
) -> str:
    """
    Build full HTML for a customer-facing email with standard header, body, CTA,
    transparency block, notification preferences link, and footer.
    """
    if website_url is None:
        from utils.branding import get_branding_website_url

        website_url = get_branding_website_url()
    header_text = header_title or "Pleerity"
    header_block = f"""
                <div style="background-color: {header_bg}; padding: 20px; border-radius: 8px 8px 0 0;">
                    {header_logo_html}
                    <h1 style="color: {link_color}; margin: 0; font-size: 22px;">{header_text}</h1>
                    <p style="color: #94a3b8; margin: 8px 0 0 0; font-size: 14px;">{tagline}</p>
                    {ref_badge}
                </div>"""

    cta_block = ""
    if cta_label and cta_url:
        cta_block = f"""
                    <p style="margin: 24px 0;">
                        <a href="{cta_url}"
                           style="background-color: {link_color}; color: white; padding: 12px 24px;
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            {cta_label}
                        </a>
                    </p>"""

    why_block = ""
    if why_received:
        why_block = f"""
                    <div style="margin-top: 24px; padding: 12px 16px; background-color: #f8fafc; border-radius: 6px; border-left: 4px solid #e2e8f0;">
                        <p style="color: #64748b; font-size: 13px; margin: 0;">
                            <strong>Why you received this email:</strong> {why_received}
                        </p>
                    </div>"""

    prefs_link = ""
    if show_preferences_link and preferences_url:
        prefs_link = f"""
                    <p style="margin-top: 16px; font-size: 13px;">
                        <a href="{preferences_url}" style="color: {link_color}; text-decoration: none;">{PREFERENCES_LINK_TEXT}</a>
                    </p>"""
    elif show_preferences_link and not preferences_url:
        prefs_link = f"""
                    <p style="margin-top: 16px; font-size: 13px; color: #64748b;">{PREFERENCES_LINK_TEXT} in your account settings.</p>"""

    ref_line = ""
    if customer_reference:
        ref_line = f"<br><strong>Your reference:</strong> {customer_reference}"

    support_block = (
        support_footer_html
        if support_footer_html is not None
        else format_customer_support_footer_html(link_color)
    )
    footer_block = f"""
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 28px 0 16px 0;">
                <div style="background-color: #f8fafc; padding: 16px; border-radius: 6px; margin-bottom: 12px;">
                    <p style="color: #64748b; font-size: 13px; margin: 0 0 8px 0;">
                        {company_name}<br>{tagline}{ref_line}
                    </p>
                    <p style="color: #64748b; font-size: 12px; margin: 8px 0 0 0;">
                        {support_block}<br><br>
                        Website: <a href="{website_url}" style="color: {link_color};">{website_url}</a>
                    </p>
                    {powered_by_html}
                    <p style="color: #94a3b8; font-size: 11px; margin: 12px 0 0 0;">{security_note}</p>
                </div>"""

    html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                {header_block}
                <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                    <p>{greeting}</p>
                    {body_html}
                    {cta_block}
                    {why_block}
                    {prefs_link}
                </div>
                {footer_block}
            </body>
            </html>
            """
    return html
