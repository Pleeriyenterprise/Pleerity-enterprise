"""
Idempotent OWNER bootstrap: ensure exactly one OWNER exists.
- If an OWNER already exists, do nothing.
- If a user exists with auth_email == BOOTSTRAP_OWNER_EMAIL, promote to OWNER (audit OWNER_PROMOTED_FROM_ADMIN, session_version++).
- Otherwise create OWNER from env (BOOTSTRAP_OWNER_EMAIL; BOOTSTRAP_OWNER_PASSWORD optional, one-time use).
Never logs or returns plaintext passwords.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from database import database
from models import UserRole, UserStatus, PasswordStatus, AuditAction
from utils.audit import create_audit_log
from auth import hash_password, generate_secure_token, hash_token

logger = logging.getLogger(__name__)

# Env keys (no defaults for email - must be explicit)
BOOTSTRAP_OWNER_EMAIL_KEY = "BOOTSTRAP_OWNER_EMAIL"
BOOTSTRAP_OWNER_PASSWORD_KEY = "BOOTSTRAP_OWNER_PASSWORD"


async def run_bootstrap_owner() -> dict:
    """
    Idempotent bootstrap: ensure one OWNER. Uses BOOTSTRAP_OWNER_EMAIL from env.
    Returns dict with keys: action (str), portal_user_id (str|None), message (str).
    """
    email = os.environ.get(BOOTSTRAP_OWNER_EMAIL_KEY, "").strip()
    if not email:
        return {"action": "skipped", "portal_user_id": None, "message": "BOOTSTRAP_OWNER_EMAIL not set"}

    db = database.get_db()

    # 1) If any OWNER already exists, do nothing (idempotent)
    existing_owner = await db.portal_users.find_one(
        {"role": UserRole.ROLE_OWNER.value},
        {"_id": 0, "portal_user_id": 1, "auth_email": 1}
    )
    if existing_owner:
        return {
            "action": "already_exists",
            "portal_user_id": existing_owner["portal_user_id"],
            "message": "OWNER already exists",
        }

    # 2) User with this email already exists? Promote to OWNER.
    existing_user = await db.portal_users.find_one(
        {"auth_email": email},
        {"_id": 0}
    )
    if existing_user:
        portal_user_id = existing_user["portal_user_id"]
        await db.portal_users.update_one(
            {"portal_user_id": portal_user_id},
            {
                "$set": {
                    "role": UserRole.ROLE_OWNER.value,
                    "status": UserStatus.ACTIVE.value,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "$inc": {"session_version": 1},
            }
        )
        await create_audit_log(
            action=AuditAction.OWNER_PROMOTED_FROM_ADMIN,
            actor_id=portal_user_id,
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={"auth_email": email, "previous_role": existing_user.get("role")},
        )
        logger.info("Owner promoted from existing user for email (id=%s)", portal_user_id)
        return {
            "action": "promoted",
            "portal_user_id": portal_user_id,
            "message": "Existing user promoted to OWNER",
        }

    # 3) Create new OWNER
    import uuid
    portal_user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    bootstrap_password = os.environ.get(BOOTSTRAP_OWNER_PASSWORD_KEY, "").strip()

    new_owner = {
        "portal_user_id": portal_user_id,
        "client_id": None,
        "auth_email": email,
        "password_hash": None,
        "role": UserRole.ROLE_OWNER.value,
        "status": UserStatus.INVITED.value,
        "password_status": PasswordStatus.NOT_SET.value,
        "must_set_password": True,
        "session_version": 0,
        "last_login": None,
        "created_at": now,
    }

    if bootstrap_password:
        new_owner["password_hash"] = hash_password(bootstrap_password)
        new_owner["status"] = UserStatus.ACTIVE.value
        new_owner["password_status"] = PasswordStatus.SET.value
        new_owner["must_set_password"] = True  # Require rotation after first login (handled by client/flow)

    await db.portal_users.insert_one(new_owner)
    await create_audit_log(
        action=AuditAction.OWNER_CREATED,
        actor_id=portal_user_id,
        resource_type="portal_user",
        resource_id=portal_user_id,
        metadata={"auth_email": email, "method": "password_set" if bootstrap_password else "invite"},
    )
    logger.info("Owner created (id=%s)", portal_user_id)

    if not bootstrap_password:
        # Send password setup email
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        token_doc = {
            "token_hash": token_hash,
            "portal_user_id": portal_user_id,
            "client_id": "ADMIN_INVITE",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            "used_at": None,
            "revoked_at": None,
            "created_by": "BOOTSTRAP",
            "send_count": 1,
            "created_at": now,
        }
        await db.password_tokens.insert_one(token_doc)
        frontend_url = os.getenv("FRONTEND_URL", "")
        setup_link = f"{frontend_url}/set-password?token={raw_token}" if frontend_url else ""
        try:
            from services.email_service import email_service
            await email_service.send_admin_invite_email(
                recipient=email,
                admin_name=email.split("@")[0],
                inviter_name="System",
                setup_link=setup_link,
            )
        except Exception as e:
            logger.warning("Bootstrap owner: could not send invite email: %s", e)

    return {
        "action": "created",
        "portal_user_id": portal_user_id,
        "message": "OWNER created" + (" (password set from env)" if bootstrap_password else " (invite email sent)"),
    }
