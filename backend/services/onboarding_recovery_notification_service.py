"""Customer-safe onboarding recovery emails (payment continuation, activation)."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TEMPLATE_KEY = "ADMIN_MANUAL"
_BRAND_PRIMARY = "#0B1D3A"
_BRAND_ACCENT = "#00B8A9"


def build_recovery_payment_email_html(*, checkout_url: str, customer_reference: str) -> str:
    ref_display = (customer_reference or "").strip()
    ref_block = ""
    if ref_display and ref_display != "N/A":
        ref_block = f"""
                    <p style="margin: 0 0 20px 0; font-size: 14px; color: #64748b;">Your Customer Reference</p>
                    <p style="margin: 0 0 24px 0;"><span style="background-color: {_BRAND_ACCENT}; color: white; padding: 6px 14px; border-radius: 6px; font-family: monospace; font-size: 14px; font-weight: 600;">{ref_display}</span></p>"""
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f1f5f9;">
    <div style="max-width: 560px; margin: 0 auto; padding: 24px 16px;">
        <div style="background-color: {_BRAND_PRIMARY}; padding: 24px; border-radius: 10px 10px 0 0; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 22px; font-weight: 600;">Compliance Vault Pro</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">Continue your onboarding</p>
        </div>
        <div style="background-color: #ffffff; padding: 28px 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 10px 10px;">
            <p style="margin: 0 0 16px 0; font-size: 16px; color: #334155;">You can continue setting up your Compliance Vault Pro account. Use the secure link below to complete your subscription payment.</p>
            {ref_block}
            <p style="margin: 0 0 20px 0;">
                <a href="{checkout_url}" style="display: inline-block; background-color: {_BRAND_ACCENT}; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600;">Continue to payment</a>
            </p>
            <p style="margin: 0; font-size: 12px; color: #94a3b8;">If the button does not work, copy this link into your browser:</p>
            <p style="margin: 4px 0 0 0; font-size: 12px; word-break: break-all;"><a href="{checkout_url}" style="color: {_BRAND_ACCENT};">{checkout_url}</a></p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;" />
            <p style="margin: 0; font-size: 13px; color: #64748b;">If you need help, contact our support team.</p>
        </div>
    </div>
</body>
</html>"""


async def send_recovery_payment_email(
    *,
    client_id: str,
    recipient: str,
    checkout_url: str,
    customer_reference: str,
    session_id: Optional[str],
) -> Dict[str, Any]:
    from services.notification_orchestrator import notification_orchestrator

    html = build_recovery_payment_email_html(
        checkout_url=checkout_url,
        customer_reference=customer_reference or "N/A",
    )
    idempotency_key = f"onboarding_recovery_payment_{client_id}_{session_id or uuid.uuid4()}"
    result = await notification_orchestrator.send(
        template_key=TEMPLATE_KEY,
        client_id=client_id,
        context={
            "recipient": recipient.strip(),
            "client_name": "there",
            "subject": "Continue your Compliance Vault Pro onboarding",
            "message": html,
            "customer_reference": customer_reference or "",
        },
        idempotency_key=idempotency_key,
        event_type="onboarding_recovery_payment_continuation",
    )
    sent = result.outcome in ("sent", "duplicate_ignored")
    return {
        "email_sent": sent,
        "outcome": result.outcome,
        "block_reason": result.block_reason,
        "message_id": getattr(result, "message_id", None),
    }


async def send_recovery_activation_email(
    *,
    client_id: str,
    recipient: str,
    setup_link: str,
    client_name: str,
) -> Dict[str, Any]:
    from services.notification_orchestrator import notification_orchestrator

    idempotency_key = f"onboarding_recovery_activation_{client_id}_{uuid.uuid4()}"
    result = await notification_orchestrator.send(
        template_key="WELCOME_EMAIL",
        client_id=client_id,
        context={
            "recipient": recipient.strip(),
            "setup_link": setup_link,
            "client_name": client_name or "Customer",
            "company_name": "Pleerity Enterprise Ltd",
            "tagline": "AI-Driven Solutions & Compliance",
        },
        idempotency_key=idempotency_key,
        event_type="onboarding_recovery_activation",
    )
    sent = result.outcome in ("sent", "duplicate_ignored")
    return {
        "email_sent": sent,
        "outcome": result.outcome,
        "block_reason": result.block_reason,
        "message_id": getattr(result, "message_id", None),
    }
