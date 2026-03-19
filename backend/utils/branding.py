"""
Pleerity branding constants for backend (PDF, email, reports).
Single source for company name, website, support email. Logo path optional for PDF header.
"""
COMPANY_NAME = "Pleerity Enterprise Ltd"
PRODUCT_NAME = "Compliance Vault Pro"
TAGLINE = "AI-Driven Solutions & Compliance"
SUPPORT_EMAIL = "info@pleerityenterprise.co.uk"

# Canonical customer-facing support line (order, payment, onboarding, support templates)
CUSTOMER_SUPPORT_FOOTER_PLAIN = (
    "If you have any questions, simply reply to this email or contact our support team at "
    f"{SUPPORT_EMAIL}"
)


def format_customer_support_footer_html(link_color: str = "#00B8A9") -> str:
    """HTML snippet: full sentence with mailto on support address only."""
    import html as html_module

    esc = html_module.escape(SUPPORT_EMAIL)
    return (
        "If you have any questions, simply reply to this email or contact our support team at "
        f'<a href="mailto:{esc}" style="color: {link_color}; text-decoration: none;">{esc}</a>'
    )


def get_branding_website_url() -> str:
    """Public site URL for PDF/email footers (same origin as SPA)."""
    from utils.app_urls import get_app_base_url

    return get_app_base_url(for_email_links=True)


# Backward compat for imports expecting a constant (resolved at use sites should prefer get_branding_website_url).
WEBSITE_URL = "https://pleerityenterprise.co.uk"

# Brand colors (hex) for PDFs and emails
PRIMARY_HEX = "#0B1D3A"
SECONDARY_HEX = "#00B8A9"

# Optional: path or URL to logo image for PDF header (None = text-only header)
BRAND_LOGO_PATH = None
