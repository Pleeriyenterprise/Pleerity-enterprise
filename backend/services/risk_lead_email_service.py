"""
Risk Check lead 5-email nurture sequence.
Informational indicator only. Not legal advice.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Step 1 = immediate; 2 = +2d, 3 = +4d, 4 = +6d, 5 = +10d
NURTURE_SUBJECTS = [
    "Your Compliance Risk Snapshot",
    "Most compliance gaps happen quietly",
    "What councils typically review",
    "Manual tracking vs structured monitoring",
    "Your monitoring gaps remain open",
]


def _risk_level_label(score_val: object) -> Optional[str]:
    """Enterprise risk-level labels for customer-facing emails."""
    try:
        score = int(float(score_val))
    except (TypeError, ValueError):
        return None
    if score >= 90:
        return "Low Risk"
    if score >= 70:
        return "Moderate Risk"
    if score >= 50:
        return "Elevated Risk"
    return "High Risk"


def _brand_footer_html() -> str:
    return (
        "<p style=\"margin:16px 0 0 0; font-size:12px; color:#64748b;\">"
        "<strong>Pleerity Enterprise Ltd</strong><br/>"
        "AI-Driven Solutions & Compliance<br/>"
        "Support: info@pleerityenterprise.co.uk | https://pleerity.com<br/>"
        "Security note: Never share account credentials or payment details over email."
        "</p>"
    )


def _cta_button_html(url: str) -> str:
    return (
        f"<a href=\"{url}\" "
        "style=\"display:inline-block;background:#0f766e;color:#ffffff;text-decoration:none;"
        "padding:12px 18px;border-radius:8px;font-weight:600;\">"
        "Activate Compliance Monitoring</a>"
    )


def _email_shell(title: str, body: str) -> str:
    return f"""
<html>
<body style="margin:0;padding:0;background:#f8fafc;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;color:#0f172a;">
  <div style="max-width:680px;margin:0 auto;padding:24px;">
    <div style="background:#0f172a;color:#ffffff;padding:16px 20px;border-radius:10px 10px 0 0;">
      <h1 style="margin:0;font-family:Montserrat,Inter,sans-serif;font-size:20px;color:#14b8a6;">{title}</h1>
    </div>
    <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:none;padding:20px;border-radius:0 0 10px 10px;">
      {body}
      {_brand_footer_html()}
    </div>
  </div>
</body>
</html>
""".strip()


def _activate_url(lead: dict, activation_token: Optional[str] = None) -> str:
    """
    Build absolute URL for 'Activate Monitoring' CTA.
    Uses app origin (get_public_app_url) so /intake/start is on the portal app; optional lead_token for prefill.
    """
    from utils.app_urls import get_app_base_url

    base = get_app_base_url(for_email_links=True).rstrip("/")
    url = f"{base}/intake/start"
    if activation_token and (activation_token or "").strip():
        url = f"{url}?lead_token={(activation_token or "").strip()}"
    return url


def _body_step1(lead: dict, activation_token: Optional[str] = None) -> str:
    first_name = lead.get("first_name") or "there"
    score = lead.get("computed_score", 0)
    risk_level = _risk_level_label(score)
    url = _activate_url(lead, activation_token)
    risk_row = f"<li><strong>Risk Level:</strong> {risk_level}</li>" if risk_level else ""
    body = f"""
<p style="margin:0 0 12px 0;">Hello {first_name},</p>
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">1) Result</h2>
<ul style="margin:0 0 14px 18px;padding:0;">
  <li><strong>Compliance Score:</strong> {score}%</li>
  {risk_row}
</ul>
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">2) Meaning</h2>
<p style="margin:0 0 14px 0;">Your score reflects the monitoring posture indicated by your responses. It highlights where renewals and evidence tracking may need stronger controls.</p>
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">3) Recommended Actions</h2>
<ul style="margin:0 0 14px 18px;padding:0;">
  <li>Centralise certificate and evidence records in one monitored system.</li>
  <li>Set automated reminders for upcoming expiry milestones.</li>
  <li>Review high-risk properties first and close renewal gaps.</li>
</ul>
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">4) Next Step</h2>
<p style="margin:0 0 16px 0;">{_cta_button_html(url)}</p>
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:16px;margin:0 0 8px 0;">5) Trust & Disclaimer</h2>
<p style="margin:0;">This report is informational only and does not constitute legal advice.</p>
""".strip()
    return _email_shell("Compliance Risk Snapshot", body)


def _body_step2(lead: dict) -> str:
    url = _activate_url(lead)
    return _email_shell(
        "Compliance Monitoring Insights",
        f"<p style=\"margin:0 0 12px 0;\">Many compliance failures happen when records exist but deadlines are not visible in time.</p>"
        "<ul style=\"margin:0 0 14px 18px;padding:0;\"><li>Missed certificate renewals</li><li>Manual reminder drift</li><li>No portfolio-wide audit trail</li></ul>"
        f"<p style=\"margin:0 0 14px 0;\">{_cta_button_html(url)}</p>"
        "<p style=\"margin:0;\">Informational only, not legal advice.</p>",
    )


def _body_step3(lead: dict) -> str:
    url = _activate_url(lead)
    return _email_shell(
        "Inspection Readiness",
        "<p style=\"margin:0 0 12px 0;\">Councils commonly review Gas Safety, EICR, HMO licensing evidence, and renewal history.</p>"
        "<p style=\"margin:0 0 12px 0;\">Structured monitoring reduces friction by keeping evidence and due dates in one auditable place.</p>"
        f"<p style=\"margin:0 0 14px 0;\">{_cta_button_html(url)}</p>"
        "<p style=\"margin:0;\">Informational only, not legal advice.</p>",
    )


def _body_step4(lead: dict) -> str:
    url = _activate_url(lead)
    return _email_shell(
        "Manual vs Structured Monitoring",
        "<p style=\"margin:0 0 12px 0;\"><strong>Manual:</strong> calendar reminders, spreadsheets, fragmented folders.</p>"
        "<p style=\"margin:0 0 12px 0;\"><strong>Structured:</strong> automated alerts, portfolio visibility, central evidence vault.</p>"
        f"<p style=\"margin:0 0 14px 0;\">{_cta_button_html(url)}</p>"
        "<p style=\"margin:0;\">Informational only, not legal advice.</p>",
    )


def _body_step5(lead: dict) -> str:
    url = _activate_url(lead)
    return _email_shell(
        "Final Reminder: Monitoring Gaps",
        "<p style=\"margin:0 0 12px 0;\">Unresolved monitoring gaps can increase renewal risk over time.</p>"
        "<p style=\"margin:0 0 12px 0;\">Activate continuous oversight for clearer evidence, alerts, and renewal control.</p>"
        f"<p style=\"margin:0 0 14px 0;\">{_cta_button_html(url)}</p>"
        "<p style=\"margin:0;\">Informational only, not legal advice.</p>",
    )


def _body_step1_builder(lead: dict, activation_token: Optional[str] = None) -> str:
    return _body_step1(lead, activation_token)


async def send_risk_lead_email(lead: dict, step: int, activation_token: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """
    Send nurture email for step (1-based, 1–5). Returns (success, error_message).
    Uses notification orchestrator with LEAD_FOLLOWUP.
    When step==1, pass activation_token so the Activate Monitoring link includes lead_token for intake prefill.
    """
    if step < 1 or step > 5:
        return False, "step must be 1–5"
    email = lead.get("email")
    if not email:
        return False, "no email"
    lead_id = lead.get("lead_id", "")
    subject = NURTURE_SUBJECTS[step - 1]
    if step == 1:
        body_html = _body_step1_builder(lead, activation_token)
    else:
        body_html = [_body_step2, _body_step3, _body_step4, _body_step5][step - 2](lead)
    try:
        from services.notification_orchestrator import notification_orchestrator
        now = datetime.now(timezone.utc)
        idempotency_key = f"risk_nurture_{lead_id}_step{step}_{now.strftime('%Y-%m-%d')}"
        result = await notification_orchestrator.send(
            template_key="LEAD_FOLLOWUP",
            client_id=None,
            context={
                "recipient": email,
                "subject": subject,
                "message": body_html,
            },
            idempotency_key=idempotency_key,
            event_type=f"risk_lead_nurture_step_{step}",
        )
        if result.outcome in ("sent", "duplicate_ignored"):
            return True, None
        return False, result.error_message or result.block_reason or result.outcome
    except Exception as e:
        logger.warning("Risk lead email step %s not sent: %s", step, e)
        return False, str(e)
