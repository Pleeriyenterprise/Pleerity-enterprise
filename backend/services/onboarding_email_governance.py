"""
State-driven guards for Compliance Vault Pro client onboarding emails.

Milestones (persisted under clients.onboarding_milestones, ISO timestamps UTC):
  payment_confirmed_at       — Stripe checkout completed (subscription)
  payment_email_sent_at      — SUBSCRIPTION_CONFIRMED sent
  activation_link_ready_at   — Provisioning finished; password token exists (optional signal)
  activation_email_sent_at   — WELCOME_EMAIL / set-password invite sent
  password_set_at            — Client admin completed set-password
  first_login_completed_at   — First successful POST /auth/login for client portal user
  dashboard_ready_email_sent_at — DASHBOARD_READY sent (mirrors onboarding_dashboard_ready_email_sent_at)

Authoritative send paths:
  - Payment: stripe_webhook_service checkout.session.completed (SUBSCRIPTION_CONFIRMED)
  - Activation: provisioning_runner → provisioning_service._send_password_setup_link (WELBOARD_EMAIL)
  - Dashboard + 7-day queue: onboarding_lifecycle_service after password SET (and backup on first login)
  - Reminder: onboarding_lifecycle_service.process_activation_reminders (ACTIVATION_REMINDER)
  - Queue processor: onboarding_sequence_service (Day 0–7) only if password SET
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from models import AuditAction, PasswordStatus, UserRole
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


async def primary_client_admin_password_set(client_id: Optional[str]) -> bool:
    """True if this client has a client-admin portal user with password_status == SET."""
    if not client_id or client_id == "ADMIN_INVITE":
        return False
    db = database.get_db()
    pu = await db.portal_users.find_one(
        {"client_id": client_id, "role": UserRole.ROLE_CLIENT_ADMIN.value},
        {"password_status": 1},
    )
    return bool(pu and pu.get("password_status") == PasswordStatus.SET.value)


async def log_onboarding_email_blocked(
    *,
    template_key: str,
    client_id: Optional[str],
    reason: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    logger.info(
        "onboarding_email_blocked template_key=%s client_id=%s reason=%s extra=%s",
        template_key,
        client_id,
        reason,
        extra or {},
    )
    try:
        await create_audit_log(
            action=AuditAction.ONBOARDING_EMAIL_SEND_BLOCKED,
            client_id=client_id,
            metadata={"template_key": template_key, "reason": reason, **(extra or {})},
        )
    except Exception:
        pass


def milestone_set_payload(milestone_key: str, at: Optional[datetime] = None) -> Dict[str, Any]:
    """$set fields for one onboarding_milestones.* key (dot notation)."""
    at = at or datetime.now(timezone.utc)
    iso = at.isoformat()
    return {f"onboarding_milestones.{milestone_key}": iso}
