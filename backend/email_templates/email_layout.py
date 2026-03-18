"""
Shared customer email layout. All customer-facing emails must use this layout.
Internal/staff notifications must NOT use this module.
"""
from typing import Optional


# Brand constants
COMPANY_NAME = "Pleerity Enterprise Ltd"
TAGLINE = "AI-Driven Solutions & Compliance"
SUPPORT_EMAIL = "info@pleerityenterprise.co.uk"
SECURITY_NOTE = "For security, Pleerity will never ask for your password by email."
PREFERENCES_LINK_TEXT = "Manage notification preferences"

# Primary teal used across Pleerity UI
PRIMARY_COLOR = "#00B8A9"
HEADER_BG = "#0B1D3A"


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
                <div style="background-color: {HEADER_BG}; padding: 20px; border-radius: 8px 8px 0 0;">
                    <h1 style="color: {PRIMARY_COLOR}; margin: 0; font-size: 22px;">{header_text}</h1>
                    <p style="color: #94a3b8; margin: 8px 0 0 0; font-size: 14px;">{tagline}</p>
                    {ref_badge}
                </div>"""

    cta_block = ""
    if cta_label and cta_url:
        cta_block = f"""
                    <p style="margin: 24px 0;">
                        <a href="{cta_url}"
                           style="background-color: {PRIMARY_COLOR}; color: white; padding: 12px 24px;
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
                        <a href="{preferences_url}" style="color: {PRIMARY_COLOR}; text-decoration: none;">{PREFERENCES_LINK_TEXT}</a>
                    </p>"""
    elif show_preferences_link and not preferences_url:
        prefs_link = f"""
                    <p style="margin-top: 16px; font-size: 13px; color: #64748b;">{PREFERENCES_LINK_TEXT} in your account settings.</p>"""

    ref_line = ""
    if customer_reference:
        ref_line = f"<br><strong>Your reference:</strong> {customer_reference}"

    footer_block = f"""
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 28px 0 16px 0;">
                <div style="background-color: #f8fafc; padding: 16px; border-radius: 6px; margin-bottom: 12px;">
                    <p style="color: #64748b; font-size: 13px; margin: 0 0 8px 0;">
                        {company_name}<br>{tagline}{ref_line}
                    </p>
                    <p style="color: #64748b; font-size: 12px; margin: 8px 0 0 0;">
                        Support: <a href="mailto:{support_email}" style="color: {PRIMARY_COLOR};">{support_email}</a><br>
                        Website: <a href="{website_url}" style="color: {PRIMARY_COLOR};">{website_url}</a>
                    </p>
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
