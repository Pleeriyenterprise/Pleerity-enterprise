"""
Structured HTML for admin-manual (EmailTemplateAlias.ADMIN_MANUAL) when
`admin_manual_structured` is true and summary fields are present.

Does not change template_key or routing; EmailService selects this vs legacy.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Tuple

HEADER_BG = "#0B1D3A"
PRIMARY = "#00B8A9"


def _pairs_from_secondary(model: Dict[str, Any]) -> List[Tuple[str, str]]:
    raw = model.get("admin_manual_secondary_links")
    if not isinstance(raw, list):
        return []
    out: List[Tuple[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            url = str(item.get("url") or "").strip()
            if label and url:
                out.append((label, url))
    return out


def build_admin_manual_structured_html(
    model: Dict[str, Any],
    *,
    footer_html: str = "",
    customer_reference_html: str = "",
) -> str:
    summary = html.escape(str(model.get("admin_manual_summary") or "").strip())
    impact = str(model.get("admin_manual_impact") or "").strip()
    actions = str(model.get("admin_manual_actions") or "").strip()
    res_url = str(model.get("admin_manual_resolution_url") or "").strip()
    res_label = html.escape(
        str(model.get("admin_manual_resolution_label") or "Open admin view").strip()
    )
    debug = str(model.get("admin_manual_debug") or "").strip()
    greeting = html.escape(str(model.get("client_name") or "there").strip())
    header_title = html.escape(str(model.get("admin_manual_header_title") or "Staff notification").strip())

    impact_html = ""
    if impact:
        impact_html = (
            f'<h2 style="font-size: 15px; color: #0f172a; margin: 20px 0 8px 0;">Operational impact</h2>'
            f'<p style="margin: 0; line-height: 1.55; color: #334155;">{html.escape(impact)}</p>'
        )
    actions_html = ""
    if actions:
        actions_html = (
            f'<h2 style="font-size: 15px; color: #0f172a; margin: 20px 0 8px 0;">Recommended actions</h2>'
            f'<p style="margin: 0; line-height: 1.55; color: #334155;">{html.escape(actions)}</p>'
        )

    cta_block = ""
    if res_url:
        cta_block = f"""
            <p style="margin: 20px 0 0 0;">
                <a href="{html.escape(res_url, quote=True)}" style="display: inline-block; background-color: {PRIMARY}; color: #0b1d3a; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: 600;">{res_label}</a>
            </p>
        """
    secondary = _pairs_from_secondary(model)
    sec_html = ""
    if secondary:
        links = []
        for lab, url in secondary:
            links.append(
                f'<li style="margin: 4px 0;"><a href="{html.escape(url, quote=True)}" style="color: {PRIMARY};">{html.escape(lab)}</a></li>'
            )
        sec_html = f'<ul style="margin: 12px 0 0 18px; padding: 0;">{"".join(links)}</ul>'

    debug_html = ""
    if debug:
        debug_esc = html.escape(debug)
        debug_html = f"""
            <details style="margin-top: 22px; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;">
                <summary style="cursor: pointer; font-weight: 600; color: #475569;">Technical / debug details</summary>
                <pre style="white-space: pre-wrap; font-size: 11px; color: #334155; margin: 12px 0 0 0;">{debug_esc}</pre>
            </details>
        """

    summary_block = (
        f'<p style="margin: 0; line-height: 1.55; color: #1e293b; font-size: 15px;">{summary}</p>'
        if summary
        else '<p style="margin: 0; color: #64748b;">See details below.</p>'
    )

    return f"""
    <html>
    <body style="font-family: Arial, Helvetica, sans-serif; max-width: 640px; margin: 0 auto; padding: 20px; background: #f8fafc;">
        <div style="background-color: {HEADER_BG}; padding: 18px 20px; border-radius: 8px 8px 0 0;">
            <p style="color: #94a3b8; margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em;">Operational</p>
            <h1 style="color: {PRIMARY}; margin: 6px 0 0 0; font-size: 20px;">{header_title}</h1>
        </div>
        <div style="padding: 22px 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; background: #ffffff;">
            {customer_reference_html}
            <p style="margin: 0 0 16px 0; color: #475569;">Hello {greeting},</p>
            <h2 style="font-size: 15px; color: #0f172a; margin: 0 0 8px 0;">Summary</h2>
            {summary_block}
            {impact_html}
            {actions_html}
            {cta_block}
            {sec_html}
            {debug_html}
        </div>
        {footer_html}
        <p style="font-size: 11px; color: #94a3b8; margin-top: 16px;">Automated staff notification. Do not forward to clients unless appropriate.</p>
    </body>
    </html>
    """


def build_admin_manual_structured_plain_text(model: Dict[str, Any], *, footer: str) -> str:
    """Plain-text body mirroring structured sections."""
    lines: List[str] = [
        str(model.get("admin_manual_header_title") or "Staff notification"),
        "",
        f"Hello {model.get('client_name', 'there').strip() or 'there'},",
        "",
        "Summary",
        str(model.get("admin_manual_summary") or "").strip() or "(see debug section)",
    ]
    imp = str(model.get("admin_manual_impact") or "").strip()
    if imp:
        lines.extend(["", "Operational impact", imp])
    act = str(model.get("admin_manual_actions") or "").strip()
    if act:
        lines.extend(["", "Recommended actions", act])
    url = str(model.get("admin_manual_resolution_url") or "").strip()
    if url:
        lab = str(model.get("admin_manual_resolution_label") or "Open admin view").strip()
        lines.extend(["", lab, url])
    for lab, u in _pairs_from_secondary(model):
        lines.extend(["", lab, u])
    dbg = str(model.get("admin_manual_debug") or "").strip()
    if dbg:
        lines.extend(["", "--- Technical / debug ---", dbg])
    lines.append(footer)
    return "\n".join(lines)
