"""
Internal alert email layout. Used for operational alerts to admins (sla_watchdog, etc.).
Do not use the customer layout (email_layout) for these emails.
"""
from typing import Dict, Any
from datetime import datetime, timezone

# Reuse brand header colours for consistency with ADMIN_MANUAL
HEADER_BG = "#0B1D3A"
PRIMARY_COLOR = "#00B8A9"


def build_internal_alert_html(model: Dict[str, Any]) -> str:
    """
    Build HTML for an internal alert email from a context dict.
    Expected keys (all optional except severity/title): severity, title, component,
    last_successful_run, last_run_at, degraded_run, expected_interval, current_status,
    possible_impact, suggested_action, dashboard_link, timestamp.
    """
    severity = model.get("severity", "P2")
    title = model.get("title", "Internal alert")
    component = model.get("component", "")
    last_run = model.get("last_successful_run")
    expected_interval = model.get("expected_interval")
    current_status = model.get("current_status")
    possible_impact = model.get("possible_impact")
    suggested_action = model.get("suggested_action")
    dashboard_link = model.get("dashboard_link")
    ts = model.get("timestamp")
    if ts is None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    elif isinstance(ts, datetime):
        ts = ts.strftime("%Y-%m-%d %H:%M:%S UTC") if ts.tzinfo else (ts.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    description = model.get("description", "")

    severity_style = "color: #dc2626;" if severity == "P0" else ("color: #ea580c;" if severity == "P1" else "color: #ca8a04;")
    sections = []
    if description:
        sections.append(f'<p style="margin: 0 0 12px 0;">{description}</p>')
    if component:
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Component:</strong> {component}</p>')
    if degraded and last_run_any is not None and str(last_run_any).strip():
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Last run (degraded outcome):</strong> {last_run_any}</p>')
    if last_run_success is not None and str(last_run_success).strip():
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Last successful run:</strong> {last_run_success}</p>')
    elif not degraded and last_run_any is not None and str(last_run_any).strip():
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Last successful run:</strong> {last_run_any}</p>')
    if expected_interval is not None and str(expected_interval).strip():
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Expected interval:</strong> {expected_interval}</p>')
    if current_status is not None and str(current_status).strip():
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Current status:</strong> {current_status}</p>')
    if possible_impact is not None and str(possible_impact).strip():
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Possible impact:</strong> {possible_impact}</p>')
    if suggested_action is not None and str(suggested_action).strip():
        sections.append(f'<p style="margin: 0 0 8px 0;"><strong>Suggested action:</strong> {suggested_action}</p>')
    body_inner = "\n                    ".join(sections) if sections else "<p>No additional details.</p>"

    dashboard_block = ""
    if dashboard_link and str(dashboard_link).strip():
        dashboard_block = f'<p style="margin: 16px 0 0 0;"><a href="{dashboard_link}" style="color: {PRIMARY_COLOR};">View in Observability →</a></p>'

    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: {HEADER_BG}; padding: 20px; border-radius: 8px 8px 0 0;">
            <h1 style="color: {PRIMARY_COLOR}; margin: 0;">Compliance Vault Pro – Monitoring</h1>
            <p style="color: #94a3b8; margin: 8px 0 0 0; font-size: 14px;">Internal alert</p>
        </div>
        <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
            <p style="margin: 0 0 8px 0;"><span style="font-weight: bold; {severity_style}">[{severity}]</span> {title}</p>
            <p style="margin: 0 0 12px 0; font-size: 13px; color: #64748b;">{ts}</p>
            {body_inner}
            {dashboard_block}
        </div>
        <p style="font-size: 12px; color: #94a3b8; margin-top: 16px;">This is an automated operational alert. Do not reply to this email.</p>
    </body>
    </html>
    """
