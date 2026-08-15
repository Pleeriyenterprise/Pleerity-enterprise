"""Customer-safe commercial entitlement continuity emails (Phase 2C)."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TEMPLATE_KEY = "ADMIN_MANUAL"
_BRAND_PRIMARY = "#0B1D3A"
_BRAND_ACCENT = "#00B8A9"


def build_commercial_continuity_email_html(
    *,
    body_line: str,
    effective_access_reason: str,
    expiry_label: Optional[str] = None,
) -> str:
    expiry_block = ""
    if expiry_label and expiry_label != "—":
        expiry_block = f'<p style="margin: 16px 0 0 0; font-size: 14px; color: #64748b;">This arrangement is in place until <strong>{expiry_label}</strong>.</p>'
    reason = (effective_access_reason or "").strip()
    reason_block = ""
    if reason:
        reason_block = f'<p style="margin: 12px 0 0 0; font-size: 14px; color: #475569;">{reason}</p>'
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f1f5f9;">
    <div style="max-width: 560px; margin: 0 auto; padding: 24px 16px;">
        <div style="background-color: {_BRAND_PRIMARY}; padding: 24px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 22px; font-weight: 600;">Compliance Vault Pro</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">Account update</p>
        </div>
        <div style="background-color: #ffffff; padding: 28px 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 10px 10px;">
            <p style="margin: 0; font-size: 16px; color: #334155;">{body_line}</p>
            {reason_block}
            {expiry_block}
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;" />
            <p style="margin: 0; font-size: 13px; color: #64748b;">Your compliance records and evidence remain available in your account unless we tell you otherwise. If you need help, contact our support team.</p>
        </div>
    </div>
</body>
</html>"""


def _expiry_label(expiry_at: Optional[str]) -> Optional[str]:
    if not expiry_at:
        return None
    raw = str(expiry_at).strip()
    if not raw:
        return None
    return raw[:10] if len(raw) >= 10 else raw


async def send_commercial_continuity_email(
    *,
    client_id: str,
    recipient: str,
    action: str,
    impact_preview: Dict[str, Any],
    effective_access_reason: str,
    expiry_at: Optional[str] = None,
    governance_id: Optional[str] = None,
) -> Dict[str, Any]:
    from services.commercial_entitlement_execution_service import (
        ACTION_GRANT_GRACE,
        ACTION_RESTRICT,
        ACTION_RETENTION_EXTENSION,
        ACTION_SPONSORED_ACCESS,
        ACTION_SUSPEND_BILLING,
        ACTION_WAIVE_ONBOARDING,
    )
    from services.notification_orchestrator import notification_orchestrator

    body_line = (impact_preview.get("customer_impact") or "").strip()
    if not body_line:
        body_line = "Your account has been updated. Our team is here if you have questions."

    subject = "An update about your Compliance Vault Pro account"
    if action == ACTION_SUSPEND_BILLING:
        subject = (
            impact_preview.get("notification_subject")
            or "Billing temporarily paused on your account"
        )
    elif action in (ACTION_GRANT_GRACE, ACTION_RETENTION_EXTENSION):
        subject = "Your access has been extended"
    elif action == ACTION_SPONSORED_ACCESS:
        subject = "Your sponsored access arrangement"
    elif action == ACTION_WAIVE_ONBOARDING:
        subject = "Onboarding fee update for your account"
    elif action == ACTION_RESTRICT:
        subject = "Temporary limits on your account"

    html = build_commercial_continuity_email_html(
        body_line=body_line,
        effective_access_reason=effective_access_reason,
        expiry_label=_expiry_label(expiry_at),
    )
    idempotency_key = (
        f"commercial_entitlement_{client_id}_{governance_id}_{action}"
        if governance_id
        else f"commercial_entitlement_{client_id}_{action}_{uuid.uuid4()}"
    )
    result = await notification_orchestrator.send(
        template_key=TEMPLATE_KEY,
        client_id=client_id,
        context={
            "recipient": recipient.strip(),
            "client_name": "there",
            "subject": subject,
            "message": html,
        },
        idempotency_key=idempotency_key,
        event_type="commercial_entitlement_continuity",
    )
    sent = result.outcome in ("sent", "duplicate_ignored")
    return {
        "email_sent": sent,
        "outcome": result.outcome,
        "block_reason": result.block_reason,
    }
