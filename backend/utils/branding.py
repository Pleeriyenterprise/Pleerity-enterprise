"""
Pleerity branding constants for backend (PDF, email, reports).
Single source for company name, website, support email. Logo path optional for PDF header.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

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

# Optional: explicit absolute path to logo PNG for PDF header (overrides default file discovery)
BRAND_LOGO_PATH: Optional[str] = None


def get_branding_logo_path() -> Optional[str]:
    """
    Resolve logo file for PDF/email use. Safe no-op when missing.

    Order: ``PLEERITY_PDF_LOGO_PATH`` env → ``BRAND_LOGO_PATH`` constant →
    ``backend/static/branding/logo.png`` if present.
    """
    env = (os.environ.get("PLEERITY_PDF_LOGO_PATH") or "").strip()
    if env and os.path.isfile(env):
        return env
    if BRAND_LOGO_PATH and os.path.isfile(BRAND_LOGO_PATH):
        return BRAND_LOGO_PATH
    default_png = Path(__file__).resolve().parent.parent / "static" / "branding" / "logo.png"
    if default_png.is_file():
        return str(default_png)
    return None
