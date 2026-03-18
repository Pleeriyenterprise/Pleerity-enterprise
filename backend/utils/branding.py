"""
Pleerity branding constants for backend (PDF, email, reports).
Single source for company name, website, support email. Logo path optional for PDF header.
"""
COMPANY_NAME = "Pleerity Enterprise Ltd"
PRODUCT_NAME = "Compliance Vault Pro"
TAGLINE = "AI-Driven Solutions & Compliance"
SUPPORT_EMAIL = "info@pleerityenterprise.co.uk"


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
