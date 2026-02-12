"""
Idempotent seed: ensure OWNER (from BOOTSTRAP_OWNER_EMAIL) and optional test ADMIN.
No hard-coded OWNER email; use BOOTSTRAP_OWNER_EMAIL. Test ADMIN for local/testing only.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
from pathlib import Path
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv(Path(__file__).resolve().parent / ".env")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test ADMIN (for local/dev); override with SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD
SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@pleerity.com")
SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "Admin123!")


async def seed_database():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print("Seeding database (idempotent)...")

    # 1) OWNER: use bootstrap if BOOTSTRAP_OWNER_EMAIL set (no hard-coded email)
    if os.environ.get("BOOTSTRAP_OWNER_EMAIL", "").strip():
        from database import database
        database.db = db
        from services.owner_bootstrap import run_bootstrap_owner
        result = await run_bootstrap_owner()
        print(f"  OWNER: {result.get('action')} - {result.get('message')}")
    else:
        # Ensure at least one OWNER exists for tests (create from SEED_OWNER_EMAIL if set)
        seed_owner_email = os.environ.get("SEED_OWNER_EMAIL", "").strip()
        if seed_owner_email:
            existing_owner = await db.portal_users.find_one({"role": "ROLE_OWNER"})
            if not existing_owner:
                import uuid
                pid = str(uuid.uuid4())
                await db.portal_users.insert_one({
                    "portal_user_id": pid,
                    "client_id": None,
                    "auth_email": seed_owner_email,
                    "password_hash": pwd_context.hash(os.environ.get("SEED_OWNER_PASSWORD", "Owner123!")),
                    "role": "ROLE_OWNER",
                    "status": "ACTIVE",
                    "password_status": "SET",
                    "must_set_password": False,
                    "session_version": 0,
                    "last_login": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  OWNER created (SEED_OWNER_EMAIL): {seed_owner_email}")
        else:
            print("  OWNER: skipped (set BOOTSTRAP_OWNER_EMAIL or SEED_OWNER_EMAIL to create)")

    # 2) Test ADMIN (idempotent)
    admin_exists = await db.portal_users.find_one({"auth_email": SEED_ADMIN_EMAIL})
    if not admin_exists:
        await db.portal_users.insert_one({
            "portal_user_id": "admin-001",
            "client_id": None,
            "auth_email": SEED_ADMIN_EMAIL,
            "password_hash": pwd_context.hash(SEED_ADMIN_PASSWORD),
            "role": "ROLE_ADMIN",
            "status": "ACTIVE",
            "password_status": "SET",
            "must_set_password": False,
            "session_version": 0,
            "last_login": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"  ADMIN created: {SEED_ADMIN_EMAIL}")
    else:
        print(f"  ADMIN already exists: {SEED_ADMIN_EMAIL}")

    print("Seed complete.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_database())
