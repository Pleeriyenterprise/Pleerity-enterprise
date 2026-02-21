"""
Resend portal password setup link by client email (support script).

Finds the client by email, then revokes existing unused tokens, creates a new
token, and sends the password setup email. No rate limit (script is admin-run).

Usage (from backend/):
  python -m scripts.resend_portal_invite --email client@example.com
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
from models import PasswordToken
from utils.audit import create_audit_log
from models import AuditAction
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def resend_invite(email: str) -> bool:
    """
    Find client by email (case-insensitive), then resend password setup link.
    Returns True if email was sent, False if client/portal user not found.
    """
    db = database.get_db()
    email_lower = email.strip().lower()
    if not email_lower:
        logger.error("Email is required")
        return False

    client = await db.clients.find_one(
        {"email": email_lower},
        {"_id": 0, "client_id": 1, "email": 1, "full_name": 1}
    )
    if not client:
        logger.warning("No client found with email: %s", email)
        return False

    client_id = client["client_id"]
    portal_user = await db.portal_users.find_one(
        {"client_id": client_id},
        {"_id": 0, "portal_user_id": 1}
    )
    if not portal_user:
        logger.warning("No portal user found for client_id=%s", client_id)
        return False

    from auth import generate_secure_token, hash_token

    # Revoke old tokens
    await db.password_tokens.update_many(
        {"portal_user_id": portal_user["portal_user_id"], "used_at": None, "revoked_at": None},
        {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Generate new token
    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)
    password_token = PasswordToken(
        token_hash=token_hash,
        portal_user_id=portal_user["portal_user_id"],
        client_id=client_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        created_by="SCRIPT",
        send_count=1
    )
    doc = password_token.model_dump()
    for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
        if doc.get(key) and isinstance(doc[key], datetime):
            doc[key] = doc[key].isoformat()
    await db.password_tokens.insert_one(doc)

    from services.notification_orchestrator import notification_orchestrator
    from utils.public_app_url import get_frontend_base_url
    base_url = get_frontend_base_url()
    setup_link = f"{base_url}/set-password?token={raw_token}"
    idempotency_key = f"{client_id}_WELCOME_EMAIL_script_{raw_token[:16]}"
    await notification_orchestrator.send(
        template_key="WELCOME_EMAIL",
        client_id=client_id,
        context={
            "setup_link": setup_link,
            "client_name": client.get("full_name", "Valued Customer"),
            "company_name": "Pleerity Enterprise Ltd",
            "tagline": "AI-Driven Solutions & Compliance",
        },
        idempotency_key=idempotency_key,
        event_type="script_resend_invite",
    )

    await create_audit_log(
        action=AuditAction.PORTAL_INVITE_RESENT,
        client_id=client_id,
        metadata={"source": "script", "email": email_lower}
    )
    logger.info("Password setup link resent to %s (client_id=%s)", email_lower, client_id)
    return True


def main():
    parser = argparse.ArgumentParser(description="Resend portal password setup link by client email")
    parser.add_argument("--email", required=True, help="Client email")
    args = parser.parse_args()

    async def _():
        await database.connect()
        try:
            return await resend_invite(args.email)
        finally:
            await database.close()

    ok = asyncio.run(_())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
