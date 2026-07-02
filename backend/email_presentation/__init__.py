"""
Email Presentation Authority — single governed presentation layer for customer emails.

Presentation only: branding, greeting, colours, CTA, footer, shell layout.
Does not own notification lifecycle, routing, or business logic.
"""

from email_presentation.authority import EmailPresentationAuthority
from email_presentation.context import enrich_presentation_context
from email_presentation.greeting import resolve_greeting
from email_presentation.registry import (
    AUTHORITY_VERSION,
    get_registry_entry,
    iter_registry_entries,
)
from email_presentation.status_colors import color_for_rag, enrich_affected_properties

__all__ = [
    "AUTHORITY_VERSION",
    "EmailPresentationAuthority",
    "color_for_rag",
    "enrich_affected_properties",
    "enrich_presentation_context",
    "get_registry_entry",
    "iter_registry_entries",
    "resolve_greeting",
]
