"""EmailPresentationAuthority facade."""

from __future__ import annotations

from typing import Any, Dict, Optional

from email_presentation.brand import BrandProfile, get_brand_profile
from email_presentation.constants import AUTHORITY_VERSION
from email_presentation.context import enrich_presentation_context
from email_presentation.cta import cta_label, render_cta_html
from email_presentation.greeting import resolve_greeting, strip_embedded_greetings
from email_presentation.shell import (
    render_customer_email,
    render_fragment_email,
    render_lead_sequence_email,
)
from email_presentation.status_colors import (
    color_for_rag,
    enrich_affected_properties,
    rag_legend_html,
    rag_status_chip_html,
)


class EmailPresentationAuthority:
    """Single entry point for governed email presentation."""

    version = AUTHORITY_VERSION

    enrich_context = staticmethod(enrich_presentation_context)
    resolve_greeting = staticmethod(resolve_greeting)
    strip_embedded_greetings = staticmethod(strip_embedded_greetings)
    get_brand = staticmethod(get_brand_profile)
    color_for_rag = staticmethod(color_for_rag)
    enrich_affected_properties = staticmethod(enrich_affected_properties)
    rag_status_chip_html = staticmethod(rag_status_chip_html)
    rag_legend_html = staticmethod(rag_legend_html)
    cta_label = staticmethod(cta_label)
    render_cta_html = staticmethod(render_cta_html)
    render_customer_email = staticmethod(render_customer_email)
    render_fragment_email = staticmethod(render_fragment_email)
    render_lead_sequence_email = staticmethod(render_lead_sequence_email)

    @staticmethod
    def notification_preferences_url(model: Optional[Dict[str, Any]] = None) -> str:
        brand = get_brand_profile(model)
        base = brand.app_base_url
        return f"{base}/settings/notifications" if base else ""
