"""Status colour authority — GREEN / AMBER / RED dashboard indicator colours."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from email_presentation.constants import (
    RAG_AMBER_HEX,
    RAG_GREEN_HEX,
    RAG_NEUTRAL_HEX,
    RAG_RED_HEX,
)

_RAG_MAP = {
    "GREEN": RAG_GREEN_HEX,
    "AMBER": RAG_AMBER_HEX,
    "RED": RAG_RED_HEX,
}

# Customer-facing labels for the same dashboard indicators. Do not expose RAG.
_CUSTOMER_STATUS_LABELS = {
    "GREEN": "In order",
    "AMBER": "Needs review",
    "RED": "Needs attention",
}


def color_for_rag(status: Optional[str], *, default: Optional[str] = None) -> str:
    key = (status or "").strip().upper()
    if key in _RAG_MAP:
        return _RAG_MAP[key]
    return default if default is not None else RAG_NEUTRAL_HEX


def enrich_property_status_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Inject governed prev_color/new_color; never default AMBER to RED."""
    out = dict(row)
    prev = (out.get("previous_status") or out.get("old_status") or "").strip().upper()
    new = (out.get("new_status") or out.get("current_status") or "").strip().upper()
    out["prev_color"] = color_for_rag(prev)
    out["new_color"] = color_for_rag(new)
    return out


def enrich_affected_properties(properties: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not properties:
        return []
    return [enrich_property_status_row(p) for p in properties]


def customer_facing_status_label(status: Optional[str]) -> str:
    """Plain-language label for a property dashboard indicator. Scoring is unchanged."""
    key = (status or "").strip().upper()
    return _CUSTOMER_STATUS_LABELS.get(key, "Updated")


def rag_status_chip_html(status: str, *, bold: bool = True) -> str:
    key = (status or "").strip().upper()
    color = color_for_rag(key)
    weight = "font-weight: bold;" if bold else ""
    label = customer_facing_status_label(key)
    return f'<span style="color: {color}; {weight}">{label}</span>'


def customer_facing_compliance_alert_subject(affected_properties: Optional[List[Dict[str, Any]]]) -> str:
    """Inbox subject for COMPLIANCE_ALERT — no RAG / colour-code jargon."""
    rank = {"GREEN": 0, "AMBER": 1, "RED": 2}
    worst = ""
    worst_n = -1
    for row in affected_properties or []:
        st = str(row.get("new_status") or "").strip().upper()
        n = rank.get(st, -1)
        if n > worst_n:
            worst_n = n
            worst = st
    if worst == "RED":
        return "A property needs attention"
    if worst == "AMBER":
        return "A property needs review"
    return "Compliance status update"


def rag_legend_html() -> str:
    return (
        '<p style="color: #64748b; font-size: 14px;">'
        "<strong>How to read this:</strong><br>"
        f'• <span style="color: {RAG_GREEN_HEX};">In order</span> — tracked requirements '
        "for this property appear satisfied on the last check (not a legal guarantee).<br>"
        f'• <span style="color: {RAG_AMBER_HEX};">Needs review</span> — some tracked items are due soon '
        "or need a look in the portal.<br>"
        f'• <span style="color: {RAG_RED_HEX};">Needs attention</span> — one or more tracked items need action. '
        "Review details in the portal."
        "</p>"
    )
