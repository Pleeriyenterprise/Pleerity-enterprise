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


def rag_status_chip_html(status: str, *, bold: bool = True) -> str:
    key = (status or "").strip().upper()
    color = color_for_rag(key)
    weight = "font-weight: bold;" if bold else ""
    label = key or "—"
    return f'<span style="color: {color}; {weight}">{label}</span>'


def rag_legend_html() -> str:
    return (
        '<p style="color: #64748b; font-size: 14px;">'
        "<strong>How to read this:</strong><br>"
        f'• <span style="color: {RAG_GREEN_HEX};">GREEN</span> = Dashboard indicator: tracked requirements '
        "for this property appear satisfied on the last calculation (not a legal guarantee).<br>"
        f'• <span style="color: {RAG_AMBER_HEX};">AMBER</span> = Some tracked requirements are due soon '
        "or need review in the portal<br>"
        f'• <span style="color: {RAG_RED_HEX};">RED</span> = One or more tracked requirements need attention '
        "— review details in the portal"
        "</p>"
    )
