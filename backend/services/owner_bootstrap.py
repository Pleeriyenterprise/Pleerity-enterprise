"""
Idempotent OWNER bootstrap: create/find owner from env (Render/MongoDB Atlas).
- When BOOTSTRAP_OWNER_EMAIL and BOOTSTRAP_OWNER_PASSWORD are set: if a user with that email
  exists, do nothing (idempotent); otherwise create owner with hashed password (same as login).
- Optional: BOOTSTRAP_OWNER_NAME, BOOTSTRAP_OWNER_ROLE (default "owner").
- When only BOOTSTRAP_OWNER_EMAIL is set (e.g. BOOTSTRAP_ENABLED=true): ensure one OWNER
  (promote existing user or create with invite email).
Never logs or returns plaintext passwords.
"""
import os
import logging
import uuid
from datetime import datetime, timezone, timedelta
from database import database
from models import UserRole, UserStatus, PasswordStatus, AuditAction
from utils.audit import create_audit_log
from auth import hash_password, generate_secure_token, hash_token

logger = logging.getLogger(__name__)

BOOTSTRAP_OWNER_EMAIL_KEY = "BOOTSTRAP_OWNER_EMAIL"
BOOTSTRAP_OWNER_PASSWORD_KEY = "BOOTSTRAP_OWNER_PASSWORD"
BOOTSTRAP_OWNER_NAME_KEY = "BOOTSTRAP_OWNER_NAME"
BOOTSTRAP_OWNER_ROLE_KEY = "BOOTSTRAP_OWNER_ROLE"


def _role_from_env() -> str:
    raw = os.environ.get(BOOTSTRAP_OWNER_ROLE_KEY, "owner").strip().upper()
    if raw in ("OWNER", "ROLE_OWNER", ""):
        return UserRole.ROLE_OWNER.value
    if raw in ("ADMIN", "ROLE_ADMIN"):
        return UserRole.ROLE_ADMIN.value
    return UserRole.ROLE_OWNER.value


async def run_bootstrap_owner() -> dict:
    """
    Idempotent bootstrap. When both BOOTSTRAP_OWNER_EMAIL and BOOTSTRAP_OWNER_PASSWORD are set:
    create owner by email if not present (safe for Render). Otherwise ensure one OWNER (legacy).
    Returns dict with keys: action (str), portal_user_id (str|None), message (str).
    """
    email = os.environ.get(BOOTSTRAP_OWNER_EMAIL_KEY, "").strip()
    password = os.environ.get(BOOTSTRAP_OWNER_PASSWORD_KEY, "").strip()
    if not email:
        return {"action": "skipped", "portal_user_id": None, "message": "BOOTSTRAP_OWNER_EMAIL not set"}

    db = database.get_db()

    # Path 1: Email + password both set → idempotent create-by-email (Render-friendly)
    if email and password:
        existing = await db.portal_users.find_one(
            {"auth_email": email},
            {"_id": 0, "portal_user_id": 1, "auth_email": 1}
        )
        if existing:
            logger.info("Bootstrap owner: already exists (email=%s)", email)
            return {
                "action": "already_exists",
                "portal_user_id": existing["portal_user_id"],
                "message": "Owner already exists for this email",
            }
        name = os.environ.get(BOOTSTRAP_OWNER_NAME_KEY, "").strip() or None
        role_value = _role_from_env()
        portal_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        new_owner = {
            "portal_user_id": portal_user_id,
            "client_id": None,
            "auth_email": email,
            "password_hash": hash_password(password),
            "role": role_value,
            "status": UserStatus.ACTIVE.value,
            "password_status": PasswordStatus.SET.value,
            "must_set_password": False,
            "session_version": 0,
            "last_login": None,
            "created_at": now,
        }
        if name:
            new_owner["full_name"] = name
        await db.portal_users.insert_one(new_owner)
        await create_audit_log(
            action=AuditAction.OWNER_CREATED,
            actor_id=portal_user_id,
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={"auth_email": email, "method": "bootstrap_env"},
        )
        logger.info("Bootstrap owner: created (email=%s, role=%s)", email, role_value)
        return {
            "action": "created",
            "portal_user_id": portal_user_id,
            "message": "Owner created from env",
        }

    # Path 2: Only email set → ensure exactly one OWNER (legacy: promote or create + invite)
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
        new_owner["must_set_password"] = True

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
