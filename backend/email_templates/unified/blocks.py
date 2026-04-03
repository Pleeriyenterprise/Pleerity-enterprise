"""
Reusable, table-safe HTML fragments for customer emails.

Use inline styles only; avoid flex/grid that Outlook drops.
"""
from __future__ import annotations

import html as html_module
from typing import Any, Dict, Iterable, List, Optional, Tuple

PRIMARY_TEAL = "#00B8A9"
MUTED = "#64748b"
BORDER = "#e2e8f0"


def esc(s: Any) -> str:
    return html_module.escape(str(s) if s is not None else "")


def section_title_html(title: str) -> str:
    t = esc(title).upper()
    return (
        f'<p style="margin:24px 0 8px 0;font-size:12px;letter-spacing:0.06em;color:{PRIMARY_TEAL};'
        f'font-weight:700;">{t}</p>'
    )


def intro_paragraph_html(text: str) -> str:
    return f'<p style="margin:0 0 16px 0;color:#334155;font-size:15px;line-height:1.55;">{esc(text)}</p>'


def info_panel_html(title: str, body_html: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;border-collapse:collapse;">'
        f'<tr><td style="padding:14px 16px;background:#f8fafc;border:1px solid {BORDER};border-radius:6px;">'
        f'<p style="margin:0 0 8px 0;font-size:13px;font-weight:600;color:#0f172a;">{esc(title)}</p>'
        f'<div style="font-size:14px;color:#334155;line-height:1.5;">{body_html}</div>'
        f"</td></tr></table>"
    )


def key_value_table_html(rows: List[Tuple[str, str]], *, numeric_emphasis: bool = False) -> str:
    """rows: (label, value) — both plain text, will be escaped."""
    trs = []
    for label, value in rows:
        v = esc(value)
        if numeric_emphasis and label.lower().startswith("total"):
            v = f'<span style="font-size:18px;font-weight:700;color:#0f172a;">{v}</span>'
        trs.append(
            f'<tr>'
            f'<td style="padding:10px 8px;border-bottom:1px solid {BORDER};color:{MUTED};font-size:14px;width:45%;">{esc(label)}</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid {BORDER};color:#0f172a;font-size:14px;text-align:right;">{v}</td>'
            f"</tr>"
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin:12px 0;border:1px solid {BORDER};border-radius:6px;overflow:hidden;">'
        + "".join(trs)
        + "</table>"
    )


def bullet_list_html(items: Iterable[str]) -> str:
    lis = "".join(f'<li style="margin:6px 0;color:#334155;font-size:14px;line-height:1.45;">{esc(x)}</li>' for x in items)
    return f'<ul style="margin:8px 0 16px 0;padding-left:20px;">{lis}</ul>'


def reference_highlight_block_html(label: str, value: str) -> str:
    """Prominent reference (CRN, invoice ref) — Pleerity accent, not third-party styling."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:16px 0;">'
        '<tr><td style="background:#ecfdf5;border:2px solid #6ee7b7;border-radius:6px;padding:12px 18px;">'
        f'<p style="margin:0 0 4px 0;font-size:12px;color:#065f46;font-weight:600;">{esc(label)}</p>'
        f'<p style="margin:0;font-size:20px;font-weight:700;color:#0f172a;letter-spacing:0.02em;font-family:Consolas,monospace;">{esc(value)}</p>'
        "</td></tr></table>"
    )


def status_badge_row_html(label: str, status_upper: str) -> str:
    st = (status_upper or "").upper()
    colors = {
        "GREEN": ("#dcfce7", "#166534"),
        "AMBER": ("#fef3c7", "#b45309"),
        "RED": ("#fee2e2", "#b91c1c"),
        "OVERDUE": ("#fee2e2", "#b91c1c"),
        "EXPIRING_SOON": ("#fef3c7", "#b45309"),
        "COMPLIANT": ("#dcfce7", "#166534"),
        "PENDING": ("#e2e8f0", "#475569"),
    }
    bg, fg = colors.get(st, ("#f1f5f9", "#334155"))
    badge = f'<span style="display:inline-block;padding:4px 10px;border-radius:4px;background:{bg};color:{fg};font-size:13px;font-weight:600;">{esc(st)}</span>'
    return (
        f'<p style="margin:12px 0;font-size:14px;color:#334155;"><strong>{esc(label)}</strong> {badge}</p>'
    )
