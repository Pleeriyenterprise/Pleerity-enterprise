"""
Operational backfill: initialize applicability_provenance + flat mirror fields.

Scans requirements in stable order by ``_id`` ascending so ``--limit`` batches are
repeatable across dry-run and real runs.

Does NOT run on application deploy. Run explicitly after PR1 review:

  cd backend
  python -m scripts.backfill_applicability_provenance --dry-run
  python -m scripts.backfill_applicability_provenance
  python -m scripts.backfill_applicability_provenance --client-id <UUID> --limit 1000

Requires MONGO_URL, DB_NAME (same as main app).

Skips rows with operator_override_active (nested or flat) to avoid clobbering
future operator governance.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def _async_main() -> None:
    parser = argparse.ArgumentParser(description="Backfill applicability provenance (manual / idempotent)")
    parser.add_argument("--dry-run", action="store_true", help="Count actions without writing")
    parser.add_argument("--client-id", default=None, help="Restrict to one tenant")
    parser.add_argument("--limit", type=int, default=None, help="Max requirement documents to examine")
    parser.add_argument(
        "--force-refresh-from-legacy",
        action="store_true",
        help="When pipeline in DB diverges from legacy applicability_state, refresh from legacy",
    )
    args = parser.parse_args()

    from database import database
    from services.applicability_provenance_backfill import run_applicability_provenance_backfill

    await database.connect()
    try:
        db = database.get_db()
        stats = await run_applicability_provenance_backfill(
            db,
            client_id=args.client_id,
            limit=args.limit,
            dry_run=args.dry_run,
            force_refresh_from_legacy=args.force_refresh_from_legacy,
        )
        print(stats)
    finally:
        await database.close()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
