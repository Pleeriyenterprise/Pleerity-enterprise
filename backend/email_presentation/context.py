"""Presentation context enrichment — colours and names before render (no send logic)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from email_presentation.greeting import resolve_greeting, strip_embedded_greetings
from email_presentation.status_colors import enrich_affected_properties


def enrich_presentation_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Enrich notification render context for governed presentation.
    Safe to call from orchestrator render path only — does not change routing or scheduling.
    """
    ctx = dict(context or {})
    if ctx.get("affected_properties"):
        ctx["affected_properties"] = enrich_affected_properties(ctx["affected_properties"])
    # Unified greeting token for templates that read it
    if "presentation_greeting" not in ctx:
        ctx["presentation_greeting"] = resolve_greeting(
            display_name=ctx.get("client_name") or ctx.get("full_name"),
            first_name=ctx.get("first_name"),
            client_name=ctx.get("client_name"),
        )
    if ctx.get("message") and not _is_full_html_document(str(ctx.get("message"))):
        ctx["message"] = strip_embedded_greetings(str(ctx["message"]))
    return ctx


def _is_full_html_document(message: str) -> bool:
    low = (message or "").lstrip().lower()
    return low.startswith("<html") or low.startswith("<!doctype")
