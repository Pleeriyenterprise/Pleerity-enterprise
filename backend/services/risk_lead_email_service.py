"""
Risk Check lead 5-email nurture sequence.
Informational indicator only. Not legal advice.
"""
import html
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Step 1 = immediate; 2 = +2d, 3 = +4d, 4 = +6d, 5 = +10d
NURTURE_SUBJECTS = [
    "Your Compliance Risk Snapshot",
    "Most compliance gaps happen quietly",
    "What councils typically review",
    "Manual tracking vs structured monitoring",
    "Your monitoring gaps remain open",
]

_MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _format_assessment_timestamp_utc(dt: datetime) -> str:
    """English, audit-friendly timestamp (UTC), independent of server locale."""
    m = _MONTHS_EN[dt.month - 1]
    return f"{dt.day} {m} {dt.year}, {dt.hour:02d}:{dt.minute:02d} UTC"


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


def _operational_footer_html() -> str:
    from email_presentation.brand import get_brand_profile, support_footer_html

    brand = get_brand_profile()
    support = support_footer_html(brand.link_color)
    website_esc = html.escape(brand.website_url, quote=True)
    return (
        '<hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0 16px 0;">'
        '<div style="font-size:12px;color:#64748b;line-height:1.55;">'
        f"<strong>{html.escape(brand.company_name, quote=False)}</strong><br/>"
        f"{html.escape(brand.tagline, quote=False)}<br/><br/>"
        "<strong>Disclaimer:</strong> This communication is informational only and does not constitute legal advice.<br/><br/>"
        f"{support}<br/>"
        f'Website: <a href="{website_esc}" style="color:{brand.link_color};text-decoration:none;">'
        f"{html.escape(brand.website_url, quote=False)}</a><br/>"
        f'<span style="font-size:11px;color:#94a3b8;">{html.escape(brand.security_note, quote=False)}</span>'
        "</div>"
    )


def _cta_button_html(url: str) -> str:
    from email_presentation.cta import CTA_START_MONITORING, render_cta_html

    return render_cta_html(url, CTA_START_MONITORING)


def _cvp_operational_document_html(
    *,
    document_subtitle: str,
    body_inner: str,
    meta_line: Optional[str] = None,
) -> str:
    """
    Single operational HTML document: one branded header strip + one content panel.
    No nested dark sub-headers (avoids 'email inside an email' feel).
    """
    esc_sub = html.escape(document_subtitle, quote=False)
    meta_block = ""
    if meta_line:
        esc_meta = html.escape(meta_line, quote=False)
        meta_block = (
            f'<p style="margin:0 0 18px 0;font-size:12px;color:#64748b;line-height:1.5;">{esc_meta}</p>'
        )
    return f"""
<html>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;color:#0f172a;">
  <div style="max-width:680px;margin:0 auto;padding:24px 16px;">
    <div style="background:#0B1D3A;padding:18px 22px;border-radius:8px 8px 0 0;border-bottom:3px solid #14b8a6;">
      <p style="margin:0;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:#94a3b8;font-weight:600;">
        Compliance Vault Pro
      </p>
      <p style="margin:10px 0 0 0;font-size:17px;font-weight:600;color:#f8fafc;line-height:1.35;">{esc_sub}</p>
    </div>
    <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:none;padding:22px 22px 26px;border-radius:0 0 8px 8px;
                box-shadow:0 1px 3px rgba(15,23,42,0.06);">
      {meta_block}
      {body_inner}
      {_operational_footer_html()}
    </div>
  </div>
</body>
</html>
""".strip()


def build_compliance_risk_snapshot_email_html(
    *,
    greeting_name: str,
    score: Optional[int],
    activation_url: str,
    generated_at: Optional[datetime] = None,
) -> Tuple[str, str]:
    """
    Build subject + full HTML for the Compliance Risk Snapshot (risk check + nurture step 1).
    ``greeting_name`` is used after 'Hello' (e.g. first name or full name).
    ``score`` may be None when the source value is missing or non-numeric (no risk band is shown).
    """
    subject = "Your Compliance Risk Snapshot"
    gen = generated_at or datetime.now(timezone.utc)
    meta = f"Assessment generated: {_format_assessment_timestamp_utc(gen)}"
    risk_badge = ""
    if score is not None:
        risk_level = _risk_level_label(score)
        if risk_level:
            esc_rl = html.escape(risk_level, quote=False)
            risk_badge = (
                f'<p style="margin:10px 0 0 0;">'
                f'<span style="display:inline-block;background:#0f172a;color:#f8fafc;font-size:12px;'
                f'font-weight:600;padding:5px 12px;border-radius:4px;letter-spacing:0.02em;">{esc_rl}</span></p>'
            )
    from email_presentation.greeting import resolve_greeting

    greet_line = resolve_greeting(display_name=greeting_name, first_name=greeting_name)
    esc_greet_display = html.escape(greet_line, quote=False)
    if score is not None:
        score_line = f'<p style="margin:0;font-size:32px;font-weight:700;color:#0f172a;line-height:1.15;">{int(score)}%</p>'
        score_caption = '<p style="margin:4px 0 0 0;font-size:13px;color:#475569;">Compliance score (indicative)</p>'
        meaning_para = (
            "<p style=\"margin:0 0 18px 0;font-size:14px;line-height:1.6;color:#334155;\">"
            "This score indicates how resilient your current compliance monitoring posture appears based on your risk check responses. "
            "It highlights where renewals and evidence tracking may need stronger controls."
            "</p>"
        )
    else:
        score_line = (
            '<p style="margin:0;font-size:28px;font-weight:700;color:#0f172a;line-height:1.15;">—</p>'
        )
        score_caption = (
            '<p style="margin:4px 0 0 0;font-size:13px;color:#475569;">'
            "Compliance score unavailable (responses did not yield a numeric score)."
            "</p>"
        )
        meaning_para = (
            "<p style=\"margin:0 0 18px 0;font-size:14px;line-height:1.6;color:#334155;\">"
            "Structured monitoring can still help centralise renewals, evidence, and follow-up even when a numeric snapshot is not available."
            "</p>"
        )
    inner = f"""
<p style="margin:0 0 16px 0;font-size:15px;line-height:1.55;">{esc_greet_display}</p>
<p style="margin:0 0 22px 0;font-size:13px;color:#475569;line-height:1.55;">
  This snapshot is based on the information currently available from your risk check responses.
</p>
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #14b8a6;padding:16px 18px;margin:0 0 22px 0;border-radius:0 6px 6px 0;">
  <p style="margin:0 0 8px 0;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.06em;font-weight:600;">
    Assessment outcome
  </p>
  {score_line}
  {score_caption}
  {risk_badge}
</div>
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:15px;margin:0 0 8px 0;font-weight:600;">1) What this means</h2>
{meaning_para}
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:15px;margin:0 0 8px 0;font-weight:600;">2) Recommended actions</h2>
<ul style="margin:0 0 18px 18px;padding:0;font-size:14px;line-height:1.55;color:#334155;">
  <li>Centralise certificates and evidence into one monitored workflow.</li>
  <li>Enable automated expiry reminders and follow-up tasks.</li>
  <li>Prioritise properties with higher risk exposure indicators.</li>
</ul>
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:15px;margin:0 0 8px 0;font-weight:600;">3) Next step</h2>
<p style="margin:0 0 18px 0;">{_cta_button_html(activation_url)}</p>
<h2 style="font-family:Montserrat,Inter,sans-serif;color:#0f172a;font-size:15px;margin:0 0 8px 0;font-weight:600;">4) Trust &amp; scope</h2>
<p style="margin:0;font-size:13px;color:#475569;line-height:1.55;">
  This report is informational only and does not constitute legal advice.
</p>
""".strip()
    doc = _cvp_operational_document_html(
        document_subtitle="Compliance Risk Snapshot",
        body_inner=inner,
        meta_line=meta,
    )
    return subject, doc


def _activate_url(lead: dict, activation_token: Optional[str] = None) -> str:
    """
    Build absolute URL for 'Activate Monitoring' CTA.
    Uses app origin (get_public_app_url) so /intake/start is on the portal app; optional lead_token for prefill.
    """
    from utils.app_urls import get_app_base_url

    base = get_app_base_url(for_email_links=True).rstrip("/")
    url = f"{base}/intake/start"
    if activation_token and (activation_token or "").strip():
        url = f"{url}?lead_token={(activation_token or '').strip()}"
    return url


def _body_step1(lead: dict, activation_token: Optional[str] = None) -> str:
    first_name = (lead.get("first_name") or lead.get("name") or "").strip()
    raw = lead.get("computed_score", 0)
    score: Optional[int] = None
    try:
        score = int(float(raw))
    except (TypeError, ValueError):
        score = None
    url = _activate_url(lead, activation_token)
    _subject, doc = build_compliance_risk_snapshot_email_html(
        greeting_name=first_name,
        score=score,
        activation_url=url,
        generated_at=datetime.now(timezone.utc),
    )
    return doc


def _body_step2(lead: dict) -> str:
    url = _activate_url(lead)
    gen = datetime.now(timezone.utc)
    meta = f"Issued: {_format_assessment_timestamp_utc(gen)}"
    inner = f"""
<p style="margin:0 0 14px 0;font-size:14px;line-height:1.6;color:#334155;">Many compliance failures happen when records exist but deadlines are not visible in time.</p>
<ul style="margin:0 0 16px 18px;padding:0;font-size:14px;line-height:1.55;color:#334155;">
  <li>Missed certificate renewals</li>
  <li>Manual reminder drift</li>
  <li>No portfolio-wide audit trail</li>
</ul>
<p style="margin:0 0 18px 0;">{_cta_button_html(url)}</p>
<p style="margin:0;font-size:13px;color:#475569;">Informational only, not legal advice.</p>
""".strip()
    return _cvp_operational_document_html(
        document_subtitle="Compliance monitoring — insight",
        body_inner=inner,
        meta_line=meta,
    )


def _body_step3(lead: dict) -> str:
    url = _activate_url(lead)
    gen = datetime.now(timezone.utc)
    meta = f"Issued: {_format_assessment_timestamp_utc(gen)}"
    inner = f"""
<p style="margin:0 0 12px 0;font-size:14px;line-height:1.6;color:#334155;">Councils commonly review Gas Safety, EICR, HMO licensing evidence, and renewal history.</p>
<p style="margin:0 0 16px 0;font-size:14px;line-height:1.6;color:#334155;">Structured monitoring reduces friction by keeping evidence and due dates in one auditable place.</p>
<p style="margin:0 0 18px 0;">{_cta_button_html(url)}</p>
<p style="margin:0;font-size:13px;color:#475569;">Informational only, not legal advice.</p>
""".strip()
    return _cvp_operational_document_html(
        document_subtitle="Inspection readiness",
        body_inner=inner,
        meta_line=meta,
    )


def _body_step4(lead: dict) -> str:
    url = _activate_url(lead)
    gen = datetime.now(timezone.utc)
    meta = f"Issued: {_format_assessment_timestamp_utc(gen)}"
    inner = f"""
<p style="margin:0 0 12px 0;font-size:14px;line-height:1.6;color:#334155;"><strong>Manual:</strong> calendar reminders, spreadsheets, fragmented folders.</p>
<p style="margin:0 0 16px 0;font-size:14px;line-height:1.6;color:#334155;"><strong>Structured:</strong> automated alerts, portfolio visibility, central evidence vault.</p>
<p style="margin:0 0 18px 0;">{_cta_button_html(url)}</p>
<p style="margin:0;font-size:13px;color:#475569;">Informational only, not legal advice.</p>
""".strip()
    return _cvp_operational_document_html(
        document_subtitle="Manual vs structured monitoring",
        body_inner=inner,
        meta_line=meta,
    )


def _body_step5(lead: dict) -> str:
    url = _activate_url(lead)
    gen = datetime.now(timezone.utc)
    meta = f"Issued: {_format_assessment_timestamp_utc(gen)}"
    inner = f"""
<p style="margin:0 0 12px 0;font-size:14px;line-height:1.6;color:#334155;">Unresolved monitoring gaps can increase renewal risk over time.</p>
<p style="margin:0 0 16px 0;font-size:14px;line-height:1.6;color:#334155;">Continuous oversight supports clearer evidence, alerts, and renewal control.</p>
<p style="margin:0 0 18px 0;">{_cta_button_html(url)}</p>
<p style="margin:0;font-size:13px;color:#475569;">Informational only, not legal advice.</p>
""".strip()
    return _cvp_operational_document_html(
        document_subtitle="Monitoring gaps — final reminder",
        body_inner=inner,
        meta_line=meta,
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
