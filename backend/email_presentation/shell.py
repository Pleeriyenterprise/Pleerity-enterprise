"""Email shell authority — canonical customer layout wrapper."""

from __future__ import annotations

import html
from typing import Any, Dict, Optional

from email_templates.email_layout import build_customer_email_layout, merge_branding_kwargs
from email_presentation.brand import get_brand_profile
from email_presentation.copy import PREFERENCES_LINK_TEXT
from email_presentation.cta import render_cta_html
from email_presentation.greeting import resolve_greeting, strip_embedded_greetings


def render_customer_email(
    model: Optional[Dict[str, Any]],
    *,
    greeting: str,
    body_html: str,
    header_title: Optional[str] = None,
    ref_badge: str = "",
    cta_key: Optional[str] = None,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    why_received: Optional[str] = None,
    show_preferences_link: bool = False,
    preferences_url: Optional[str] = None,
    customer_reference: Optional[str] = None,
    strip_fragment_greetings: bool = True,
) -> str:
    """Render through governed canonical shell only."""
    brand = get_brand_profile(model)
    body = strip_embedded_greetings(body_html) if strip_fragment_greetings else (body_html or "")
    merged = merge_branding_kwargs(
        model,
        greeting=greeting,
        body_html=body,
        header_title=header_title or brand.product_name,
        ref_badge=ref_badge,
        cta_label=cta_label,
        cta_url=cta_url,
        why_received=why_received,
        show_preferences_link=show_preferences_link,
        preferences_url=preferences_url,
        company_name=brand.company_name,
        tagline=brand.tagline,
        support_email=brand.support_email,
        website_url=brand.website_url,
        security_note=brand.security_note,
        customer_reference=customer_reference,
        header_bg=brand.header_bg,
        link_color=brand.link_color,
    )
    # If caller passed cta_key without label, resolve from CTA authority
    if cta_key and not cta_label and cta_url:
        from email_presentation.cta import cta_label as resolve_cta_label

        merged["cta_label"] = resolve_cta_label(cta_key)
        merged["cta_url"] = cta_url
    return build_customer_email_layout(**merged)


def render_plain_text_as_html(body_text: str) -> str:
    esc = html.escape(body_text or "", quote=False)
    return f'<div style="white-space:pre-line;line-height:1.55;">{esc}</div>'


def render_lead_sequence_email(
    model: Optional[Dict[str, Any]],
    *,
    display_name: str,
    body_text: str,
    header_title: str,
    cta_url: str,
    cta_key: str = "continue",
    why_received: Optional[str] = None,
    show_preferences_link: bool = False,
    preferences_url: Optional[str] = None,
    tracking_open_url: Optional[str] = None,
) -> str:
    """Lead automation / nurture plain-text body via canonical shell."""
    from email_presentation.cta import cta_label

    body_html = render_plain_text_as_html(body_text)
    if tracking_open_url:
        body_html += (
            f'<img src="{html.escape(tracking_open_url, quote=True)}" width="1" height="1" alt="" '
            'style="display:block"/>'
        )
    if show_preferences_link and not preferences_url:
        from email_presentation.authority import EmailPresentationAuthority

        preferences_url = EmailPresentationAuthority.notification_preferences_url(model) or None
    return render_customer_email(
        model,
        greeting=resolve_greeting(display_name),
        body_html=body_html,
        header_title=header_title,
        cta_key=cta_key,
        cta_label=cta_label(cta_key),
        cta_url=cta_url,
        why_received=why_received,
        show_preferences_link=show_preferences_link,
        preferences_url=preferences_url,
        strip_fragment_greetings=True,
    )


def render_fragment_email(
    model: Optional[Dict[str, Any]],
    *,
    body_html: str,
    header_title: Optional[str] = None,
    client_name: Optional[str] = None,
    first_name: Optional[str] = None,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    why_received: Optional[str] = None,
    show_preferences_link: bool = False,
    preferences_url: Optional[str] = None,
    customer_reference: Optional[str] = None,
) -> str:
    """ENABLEMENT / admin-manual fragments — single shell greeting, no embedded Hi/Hello."""
    return render_customer_email(
        model,
        greeting=resolve_greeting(client_name=client_name, first_name=first_name, display_name=client_name),
        body_html=body_html,
        header_title=header_title,
        cta_label=cta_label,
        cta_url=cta_url,
        why_received=why_received,
        show_preferences_link=show_preferences_link,
        preferences_url=preferences_url,
        customer_reference=customer_reference,
        strip_fragment_greetings=True,
    )
