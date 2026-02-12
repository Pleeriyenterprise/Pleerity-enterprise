"""
Idempotent OWNER bootstrap script.
Uses BOOTSTRAP_OWNER_EMAIL (required) and optionally BOOTSTRAP_OWNER_PASSWORD from env.
If a user already exists with that email, promotes to OWNER. Otherwise creates OWNER.
Never outputs plaintext passwords.

Usage (from backend/):
  python -m scripts.bootstrap_owner
"""
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def main():
    from database import database
    from services.owner_bootstrap import run_bootstrap_owner

    await database.connect()
    try:
        result = await run_bootstrap_owner()
        print(f"Bootstrap: {result['action']} - {result['message']}")
        if result.get("portal_user_id"):
            print(f"  portal_user_id: {result['portal_user_id']}")
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
