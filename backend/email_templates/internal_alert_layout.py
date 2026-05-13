"""
Internal alert email layout. Used for operational alerts to admins (sla_watchdog, etc.).
Do not use the customer layout (email_layout) for these emails.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Dict


HEADER_BG = "#0B1D3A"
PRIMARY_COLOR = "#00B8A9"


def _severity_style_label(severity_label: str) -> str:
    sl = (severity_label or "").strip().upper()
    if sl == "CRITICAL":
        return "color: #dc2626;"
    if sl == "ACTION_REQUIRED":
        return "color: #ea580c;"
    if sl == "WARNING":
        return "color: #ca8a04;"
    return "color: #64748b;"


def _severity_style_stored(severity: str) -> str:
    if severity == "P0":
        return "color: #dc2626;"
    if severity == "P1":
        return "color: #ea580c;"
    return "color: #ca8a04;"


def _structured_internal_alert_html(model: Dict[str, Any]) -> str:
    """Phase 2 layout: operator summary first, technical block collapsed."""
    severity_label = model.get("severity_label") or "WARNING"
    stored = model.get("severity", "P2")
    title = html.escape(str(model.get("presentation_title") or model.get("title") or "Internal alert"))
    operational_summary = html.escape(str(model.get("operational_summary") or "").strip())
    business_impact = str(model.get("business_impact") or "").strip()
    comp = html.escape(str(model.get("affected_component") or model.get("component") or "").strip())
    scope = html.escape(str(model.get("affected_scope") or "").strip())
    action = html.escape(
        str(model.get("recommended_actions") or model.get("suggested_action") or "").strip()
    )
    cust = model.get("customer_impact")
    cust_s = str(cust).strip() if cust else ""
    resolution = str(model.get("resolution_link") or model.get("incident_link") or "").strip()
    observability = str(model.get("dashboard_link") or "").strip()
    automation = ""
    rl = model.get("resolution_links")
    if isinstance(rl, dict):
        automation = str(rl.get("automation_centre") or "").strip()
    technical = str(model.get("technical_details") or "").strip()
    technical_esc = html.escape(technical)
    ts_raw = model.get("timestamp")
    if ts_raw is None:
        ts_plain = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    elif isinstance(ts_raw, datetime):
        ts_plain = (
            ts_raw.strftime("%Y-%m-%d %H:%M:%S UTC")
            if ts_raw.tzinfo
            else ts_raw.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )
    else:
        ts_plain = str(ts_raw)
    ts = html.escape(ts_plain)
    subj_label = html.escape(str(severity_label).replace("_", " "))

    bio_block = ""
    if business_impact and business_impact.strip() != (model.get("operational_summary") or "").strip():
        bio_block = f'<p style="margin: 0 0 12px 0;"><strong>Operational impact:</strong> {html.escape(business_impact)}</p>'

    cust_block = ""
    if cust_s:
        cust_block = f'<p style="margin: 0 0 12px 0;"><strong>Customer impact:</strong> {html.escape(cust_s)}</p>'

    urg = str(model.get("operator_urgency_note") or "").strip()
    urg_block = ""
    if urg:
        urg_block = f'<p style="margin: 0 0 12px 0;"><strong>Urgency and response:</strong> {html.escape(urg)}</p>'

    ign = str(model.get("if_ignored_guidance") or "").strip()
    ign_block = ""
    if ign:
        ign_block = f'<p style="margin: 0 0 12px 0;"><strong>If left unresolved:</strong> {html.escape(ign)}</p>'

    affected_block = ""
    if comp or scope:
        bits = []
        if comp:
            bits.append(f"<strong>Component:</strong> {comp}")
        if scope:
            bits.append(f"<strong>Scope:</strong> {scope}")
        affected_block = f'<p style="margin: 0 0 12px 0;">{" &nbsp;|&nbsp; ".join(bits)}</p>'

    links_html = ""
    if resolution:
        links_html += f'<p style="margin: 12px 0 4px 0;"><a href="{html.escape(resolution, quote=True)}" style="color: {PRIMARY_COLOR}; font-weight: 600;">Open incident →</a></p>'
    if observability and observability != resolution:
        links_html += f'<p style="margin: 4px 0 4px 0;"><a href="{html.escape(observability, quote=True)}" style="color: {PRIMARY_COLOR};">Observability dashboard →</a></p>'
    if automation and automation not in (resolution, observability):
        links_html += f'<p style="margin: 4px 0 0 0;"><a href="{html.escape(automation, quote=True)}" style="color: {PRIMARY_COLOR};">Automation Control Centre →</a></p>'

    tech_details = ""
    if technical:
        tech_details = f"""
            <details style="margin-top: 16px; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;">
                <summary style="cursor: pointer; font-weight: 600; color: #475569;">Technical details</summary>
                <pre style="white-space: pre-wrap; font-size: 11px; color: #334155; margin: 10px 0 0 0;">{technical_esc}</pre>
            </details>
        """

    label_style = _severity_style_label(str(severity_label))

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: {HEADER_BG}; padding: 20px; border-radius: 8px 8px 0 0;">
            <h1 style="color: {PRIMARY_COLOR}; margin: 0;">Compliance Vault Pro – Monitoring</h1>
            <p style="color: #94a3b8; margin: 8px 0 0 0; font-size: 14px;">Internal operational alert</p>
        </div>
        <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
            <p style="margin: 0 0 4px 0;">
                <span style="font-weight: bold; {label_style}">{subj_label}</span>
                <span style="color: #94a3b8; font-size: 12px; margin-left: 8px;">(reference: {html.escape(stored)})</span>
            </p>
            <h2 style="margin: 8px 0 12px 0; font-size: 18px; color: #0f172a;">{title}</h2>
            <p style="margin: 0 0 12px 0; font-size: 13px; color: #64748b;">{ts}</p>
            <p style="margin: 0 0 12px 0; line-height: 1.5;">{operational_summary or html.escape(str(model.get("description") or ""))}</p>
            {bio_block}
            {cust_block}
            {urg_block}
            {ign_block}
            {affected_block}
            <p style="margin: 0 0 12px 0;"><strong>Recommended actions:</strong></p>
            <p style="margin: 0 0 12px 0; line-height: 1.55; white-space: pre-wrap; color: #334155;">{action or "Review linked admin views and resolve when safe."}</p>
            {links_html}
            {tech_details}
        </div>
        <p style="font-size: 12px; color: #94a3b8; margin-top: 16px;">This is an automated operational alert. Do not reply to this email.</p>
    </body>
    </html>
    """


def build_internal_alert_html(model: Dict[str, Any]) -> str:
    """
    Build HTML for an internal alert email from a context dict.
    When `severity_label` and `operational_summary` are present (sla_watchdog path), use structured layout.
    Otherwise legacy layout (minimal keys).
    """
    if model.get("severity_label"):
        return _structured_internal_alert_html(model)

    severity = model.get("severity", "P2")
    title = html.escape(str(model.get("title", "Internal alert")))
    component = html.escape(str(model.get("component", "")))
    last_successful_run = model.get("last_successful_run")
    last_run_at = model.get("last_run_at")
    degraded = bool(model.get("degraded_run"))
    expected_interval = model.get("expected_interval")
    current_status = model.get("current_status")
    possible_impact = model.get("possible_impact")
    suggested_action = model.get("suggested_action")
    dashboard_link = model.get("dashboard_link")
    ts = model.get("timestamp")
    if ts is None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    elif isinstance(ts, datetime):
        ts = (
            ts.strftime("%Y-%m-%d %H:%M:%S UTC")
            if ts.tzinfo
            else ts.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )
    else:
        ts = str(ts)
    description = model.get("description") or model.get("message") or ""
    desc_esc = html.escape(str(description)) if description else ""

    severity_style = _severity_style_stored(str(severity))
    sections = []
    if desc_esc:
        sections.append(f'<p style="margin: 0 0 12px 0;">{desc_esc}</p>')
    if component:
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Component:</strong> {component}</p>')
    if degraded and last_run_at is not None and str(last_run_at).strip():
        sections.append(
            f'<p style="margin: 0 0 8px 0;"><strong>Last run (degraded outcome):</strong> {html.escape(str(last_run_at))}</p>'
        )
    if last_successful_run is not None and str(last_successful_run).strip():
        sections.append(
            f'<p style="margin: 0 0 8px 0;"><strong>Last successful run:</strong> {html.escape(str(last_successful_run))}</p>'
        )
    elif not degraded and last_run_at is not None and str(last_run_at).strip():
        sections.append(
            f'<p style="margin: 0 0 8px 0;"><strong>Last successful run:</strong> {html.escape(str(last_run_at))}</p>'
        )
    if expected_interval is not None and str(expected_interval).strip():
        sections.append(
            f'<p style="margin: 0 0 8px 0;"><strong>Expected interval:</strong> {html.escape(str(expected_interval))}</p>'
        )
    if current_status is not None and str(current_status).strip():
        sections.append(
            f'<p style="margin: 0 0 8px 0;"><strong>Current status:</strong> {html.escape(str(current_status))}</p>'
        )
    if possible_impact is not None and str(possible_impact).strip():
        sections.append(
            f'<p style="margin: 0 0 8px 0;"><strong>Possible impact:</strong> {html.escape(str(possible_impact))}</p>'
        )
    if suggested_action is not None and str(suggested_action).strip():
        sections.append(
            f'<p style="margin: 0 0 8px 0;"><strong>Suggested action:</strong> {html.escape(str(suggested_action))}</p>'
        )
    body_inner = "\n                    ".join(sections) if sections else "<p>No additional details.</p>"

    dashboard_block = ""
    if dashboard_link and str(dashboard_link).strip():
        dashboard_block = f'<p style="margin: 16px 0 0 0;"><a href="{html.escape(str(dashboard_link), quote=True)}" style="color: {PRIMARY_COLOR};">View in Observability →</a></p>'

    sev_esc = html.escape(str(severity))
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: {HEADER_BG}; padding: 20px; border-radius: 8px 8px 0 0;">
            <h1 style="color: {PRIMARY_COLOR}; margin: 0;">Compliance Vault Pro – Monitoring</h1>
            <p style="color: #94a3b8; margin: 8px 0 0 0; font-size: 14px;">Internal alert</p>
        </div>
        <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
            <p style="margin: 0 0 8px 0;"><span style="font-weight: bold; {severity_style}">[{sev_esc}]</span> {title}</p>
            <p style="margin: 0 0 12px 0; font-size: 13px; color: #64748b;">{html.escape(str(ts))}</p>
            {body_inner}
            {dashboard_block}
        </div>
        <p style="font-size: 12px; color: #94a3b8; margin-top: 16px;">This is an automated operational alert. Do not reply to this email.</p>
    </body>
    </html>
    """
