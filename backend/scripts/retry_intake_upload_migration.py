"""
Retry intake upload migration for a client (support script).

Use when provisioning succeeded later or migration needs to be re-run.
Runs migrate_intake_uploads_to_vault(client_id) and prints migrated/skipped counts.

Usage (from backend/):
  python -m scripts.retry_intake_upload_migration <client_id>
  python -m scripts.retry_intake_upload_migration --client-id <client_id>
"""

import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run(client_id: str) -> dict:
    from services.intake_upload_migration import migrate_intake_uploads_to_vault
    return await migrate_intake_uploads_to_vault(client_id)


def main():
    parser = argparse.ArgumentParser(description="Retry intake upload migration for a client")
    parser.add_argument("client_id", nargs="?", help="Client ID")
    parser.add_argument("--client-id", dest="client_id_flag", help="Client ID (alternative)")
    args = parser.parse_args()
    client_id = args.client_id or args.client_id_flag
    if not client_id:
        parser.error("Provide client_id as positional argument or --client-id")
        return 1
    client_id = client_id.strip()
    async def _():
        await database.connect()
        try:
            result = await run(client_id)
            print(f"Migrated: {result.get('migrated', 0)}")
            print(f"Skipped (already migrated): {result.get('skipped', 0)}")
            if result.get("errors"):
                print("Errors:")
                for e in result["errors"]:
                    print(f"  - {e}")
            return 0
        finally:
            await database.close()
    return asyncio.run(_())


if __name__ == "__main__":
    sys.exit(main())
