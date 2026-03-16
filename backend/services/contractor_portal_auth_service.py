"""
Contractor portal authentication: accounts and password.
Contractors log in via /api/auth/contractor-login; password set via contractor-set-password token.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid
import logging
from auth import hash_password, verify_password
from database import database

logger = logging.getLogger(__name__)

STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"


async def get_account_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get contractor portal account by email (normalized lowercase)."""
    if not email or not str(email).strip():
        return None
    db = database.get_db()
    email_norm = str(email).strip().lower()
    doc = await db.contractor_portal_accounts.find_one({"email": email_norm})
    if doc:
        doc.pop("_id", None)
    return doc


async def get_account_by_contractor_id(contractor_id: str) -> Optional[Dict[str, Any]]:
    """Get contractor portal account by contractor_id."""
    if not contractor_id:
        return None
    db = database.get_db()
    doc = await db.contractor_portal_accounts.find_one({"contractor_id": contractor_id})
    if doc:
        doc.pop("_id", None)
    return doc


async def create_account(contractor_id: str, email: str, password: str) -> Dict[str, Any]:
    """Create a contractor portal account. Email must be unique. Fails if contractor_id or email already has account."""
    db = database.get_db()
    existing = await get_account_by_email(email)
    if existing:
        raise ValueError("An account with this email already exists")
    existing_c = await get_account_by_contractor_id(contractor_id)
    if existing_c:
        raise ValueError("This contractor already has a portal account")
    now = datetime.now(timezone.utc).isoformat()
    email_norm = str(email).strip().lower()
    doc = {
        "contractor_id": contractor_id,
        "email": email_norm,
        "password_hash": hash_password(password),
        "status": STATUS_ACTIVE,
        "created_at": now,
        "updated_at": now,
    }
    await db.contractor_portal_accounts.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


async def set_password(contractor_id: str, password: str) -> bool:
    """Set or update password for contractor portal account."""
    db = database.get_db()
    result = await db.contractor_portal_accounts.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"password_hash": hash_password(password), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return result.modified_count > 0 or result.matched_count > 0


async def verify_contractor_password(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify email/password and return account (without password_hash) if valid. Returns None if invalid."""
    acc = await get_account_by_email(email)
    if not acc:
        return None
    if acc.get("status") != STATUS_ACTIVE:
        return None
    db = database.get_db()
    doc = await db.contractor_portal_accounts.find_one({"email": acc["email"]}, {"password_hash": 1, "contractor_id": 1, "email": 1, "status": 1})
    if not doc or not doc.get("password_hash"):
        return None
    if not verify_password(password, doc["password_hash"]):
        return None
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc
