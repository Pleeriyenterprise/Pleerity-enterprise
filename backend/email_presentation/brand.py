"""Branding authority — company, colours, support, website (no hardcoded production domains)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from utils.branding import (
    COMPANY_NAME,
    PRODUCT_NAME,
    SUPPORT_EMAIL,
    TAGLINE,
    format_customer_support_footer_html,
    get_branding_website_url,
)
from utils.app_urls import get_app_base_url

from email_presentation.constants import (
    BRAND_PROFILE,
    RAG_AMBER_HEX,
    RAG_GREEN_HEX,
    RAG_RED_HEX,
)


@dataclass(frozen=True)
class BrandProfile:
    company_name: str
    product_name: str
    tagline: str
    support_email: str
    website_url: str
    app_base_url: str
    primary_color: str
    header_bg: str
    accent_color: str
    button_bg: str
    link_color: str
    security_note: str
    brand_profile_id: str = BRAND_PROFILE


def get_brand_profile(model: Optional[Dict[str, Any]] = None) -> BrandProfile:
    """Resolve governed brand tokens; explicit ``_email_branding`` overrides defaults."""
    eb = {}
    if model and isinstance(model.get("_email_branding"), dict):
        eb = model["_email_branding"]
    website = (eb.get("website_url") or get_branding_website_url()).strip()
    app_base = get_app_base_url(for_email_links=True).rstrip("/")
    primary = eb.get("link_color") or eb.get("primary_color") or "#00B8A9"
    header_bg = eb.get("header_bg") or "#0B1D3A"
    return BrandProfile(
        company_name=eb.get("company_name") or COMPANY_NAME,
        product_name=PRODUCT_NAME,
        tagline=eb.get("tagline") or TAGLINE,
        support_email=eb.get("support_email") or SUPPORT_EMAIL,
        website_url=website,
        app_base_url=app_base,
        primary_color=primary,
        header_bg=header_bg,
        accent_color=primary,
        button_bg=primary,
        link_color=primary,
        security_note=eb.get("security_note")
        or "For security, Pleerity will never ask for your password by email.",
    )


def support_footer_html(link_color: Optional[str] = None) -> str:
    return format_customer_support_footer_html(link_color or "#00B8A9")


def rag_legend_swatches() -> Dict[str, str]:
    return {"GREEN": RAG_GREEN_HEX, "AMBER": RAG_AMBER_HEX, "RED": RAG_RED_HEX}
