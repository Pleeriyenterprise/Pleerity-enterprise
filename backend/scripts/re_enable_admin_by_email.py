"""
Re-enable Admin by Email (recovery script)

Use when the last active admin was deactivated and no one can log in to the admin portal.
Sets status back to ACTIVE for a portal_user with role admin and the given email.

Usage (from backend/):
  python -m scripts.re_enable_admin_by_email admin@example.com
  python -m scripts.re_enable_admin_by_email --email admin@example.com
"""

import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
from models import UserRole, UserStatus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def re_enable_admin(email: str) -> bool:
    """
    Find admin by auth_email (case-insensitive), set status to ACTIVE.
    Returns True if updated, False if not found or already active.
    """
    db = database.get_db()
    email_lower = email.strip().lower()
    if not email_lower:
        logger.error("Email is required")
        return False

    admin = await db.portal_users.find_one(
        {"auth_email": email_lower, "role": UserRole.ROLE_ADMIN.value},
        {"_id": 0, "portal_user_id": 1, "auth_email": 1, "status": 1}
    )
    if not admin:
        logger.warning("No admin user found with email: %s", email)
        return False
    if admin.get("status") == UserStatus.ACTIVE.value:
        logger.info("Admin %s is already ACTIVE; no change.", email_lower)
        return True

    await db.portal_users.update_one(
        {"portal_user_id": admin["portal_user_id"]},
        {"$set": {"status": UserStatus.ACTIVE.value}}
    )
    logger.info("Re-enabled admin: %s (portal_user_id=%s)", email_lower, admin["portal_user_id"])
    return True


def main():
    parser = argparse.ArgumentParser(description="Re-enable a disabled admin by email")
    parser.add_argument("email", nargs="?", help="Admin email (auth_email)")
    parser.add_argument("--email", dest="email_flag", help="Admin email (alternative)")
    args = parser.parse_args()
    email = args.email or args.email_flag
    if not email:
        parser.error("Provide email as positional argument or --email")
        return 1
    ok = asyncio.run(re_enable_admin(email))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
