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


def _activate_url(lead: dict, activation_token: Optional[str] = None) -> str:
    """
    Build absolute URL for 'Activate Monitoring' CTA.
    Uses app origin (get_public_app_url) so /intake/start is on the portal app; optional lead_token for prefill.
    """
    try:
        from utils.public_app_url import get_public_app_url
        base = get_public_app_url(for_email_links=True).rstrip("/")
    except ValueError:
        base = (os.environ.get("FRONTEND_URL") or os.environ.get("FRONTEND_PUBLIC_URL") or "").strip().rstrip("/") or "http://localhost:3000"
    url = f"{base}/intake/start"
    if activation_token and (activation_token or "").strip():
        url = f"{url}?lead_token={(activation_token or "").strip()}"
    return url


def _body_step1(lead: dict, activation_token: Optional[str] = None) -> str:
    first_name = lead.get("first_name") or "there"
    score = lead.get("computed_score", 0)
    risk_band = lead.get("risk_band", "MODERATE")
    url = _activate_url(lead, activation_token)
    return f"""
<p>Hello {first_name},</p>
<p>Thank you for completing the Pleerity Compliance Risk Check.</p>
<p>Based on your responses, your monitoring posture was assessed as:</p>
<p><strong>Compliance Score:</strong> {score}%<br/>
<strong>Risk Level:</strong> {risk_band}</p>
<p>This score reflects structured weighting of safety indicators and monitoring structure.</p>
<p>If certificates are tracked manually, renewal gaps can occur without warning.</p>
<p>Continuous monitoring centralises expiry tracking across your portfolio and reduces missed renewals.</p>
<p><a href="{url}">Activate Monitoring</a></p>
<p>This assessment is an informational indicator only and not legal advice.</p>
<p>Regards,<br/>Pleerity Compliance Vault Pro</p>
""".strip()


def _body_step2(lead: dict) -> str:
    url = _activate_url(lead)
    return f"""
<p>Many landlords assume they are compliant because documents exist.</p>
<p>The risk often arises from:</p>
<ul>
<li>Expired certificates not noticed</li>
<li>Manual reminders missed</li>
<li>No centralised audit trail</li>
</ul>
<p>Monitoring is not about paperwork. It is about visibility.</p>
<p>When renewals are tracked automatically, risk reduces structurally.</p>
<p>You can activate monitoring here:</p>
<p><a href="{url}">Activate Monitoring</a></p>
<p>This assessment is an informational indicator only and not legal advice.</p>
<p>Regards,<br/>Pleerity Compliance Vault Pro</p>
""".strip()


def _body_step3(lead: dict) -> str:
    url = _activate_url(lead)
    return f"""
<p>During inspections or audits, councils commonly review:</p>
<ul>
<li>Gas Safety documentation</li>
<li>Electrical condition reports</li>
<li>HMO licence evidence</li>
<li>Renewal history</li>
</ul>
<p>Disorganised records increase friction.</p>
<p>Structured monitoring provides a documented trail of renewal tracking and evidence storage.</p>
<p>Activate monitoring when ready:</p>
<p><a href="{url}">Activate Monitoring</a></p>
<p>This assessment is an informational indicator only and not legal advice.</p>
<p>Regards,<br/>Pleerity Compliance Vault Pro</p>
""".strip()


def _body_step4(lead: dict) -> str:
    url = _activate_url(lead)
    return f"""
<p>Manual tracking relies on memory. Structured monitoring relies on system alerts.</p>
<p><strong>Manual:</strong></p>
<ul><li>Calendar reminders</li><li>Spreadsheets</li><li>Email folders</li></ul>
<p><strong>Monitoring:</strong></p>
<ul><li>Automated expiry alerts</li><li>Portfolio-level visibility</li><li>Centralised vault</li><li>Risk dashboard</li></ul>
<p>Your current structure suggests monitoring could improve consistency.</p>
<p><a href="{url}">Activate Monitoring</a></p>
<p>This assessment is an informational indicator only and not legal advice.</p>
<p>Regards,<br/>Pleerity Compliance Vault Pro</p>
""".strip()


def _body_step5(lead: dict) -> str:
    url = _activate_url(lead)
    return f"""
<p>Your compliance snapshot identified monitoring gaps.</p>
<p>Unresolved monitoring structures can increase renewal vulnerability over time.</p>
<p>If you would like structured oversight across your portfolio:</p>
<p><a href="{url}">Activate Continuous Monitoring</a></p>
<p>Cancel anytime.</p>
<p>This assessment is an informational indicator only and not legal advice.</p>
<p>Regards,<br/>Pleerity Compliance Vault Pro</p>
""".strip()


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
