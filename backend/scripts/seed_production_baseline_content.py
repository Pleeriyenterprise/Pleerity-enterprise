"""
Seed system-owned baseline content for production (or any environment).

Safe by default: --dry-run prints planned actions without writing.

  cd backend
  python -m scripts.seed_production_baseline_content --dry-run
  python -m scripts.seed_production_baseline_content --apply --i-approve-production-write

Only touches: legal_content, kb_articles, kb_categories, compliance registry drafts/published.
Does not copy staging customer data.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from database import database
from services.production_baseline_content_seed import run_production_baseline_seed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Production baseline content seed (system-owned only)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned create/update/skip actions without writing (default if --apply omitted)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply baseline seed to the connected database",
    )
    parser.add_argument(
        "--i-approve-production-write",
        action="store_true",
        help="Required with --apply when DB_NAME=pleerity_production",
    )
    parser.add_argument(
        "--force-legal",
        action="store_true",
        help="Overwrite legal pages even when custom CMS content exists (use with care)",
    )
    parser.add_argument(
        "--force-registry",
        action="store_true",
        help="Overwrite existing registry drafts from baseline bundle",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    dry_run = not args.apply or args.dry_run
    db_name = (os.environ.get("DB_NAME") or "").strip()

    if args.apply and not dry_run:
        if db_name == "pleerity_production" and not args.i_approve_production_write:
            print(
                "ERROR: DB_NAME=pleerity_production requires --i-approve-production-write for --apply."
            )
            return 2
        if not (os.environ.get("MONGO_URL") or "").strip():
            print("ERROR: MONGO_URL is not set.")
            return 2

    print(f"Target DB_NAME={db_name or '(unset)'} mode={'dry-run' if dry_run else 'apply'}")

    async def _run() -> dict:
        await database.connect()
        db = database.get_db()
        if db is None:
            raise RuntimeError("Database not connected")
        return await run_production_baseline_seed(
            db,
            dry_run=dry_run,
            force_legal=args.force_legal,
            force_registry=args.force_registry,
        )

    result = asyncio.run(_run())
    print(json.dumps(result, indent=2, default=str))

    if dry_run:
        counts = result.get("counts") or {}
        print(
            f"\nSummary: create={counts.get('create', 0)} update={counts.get('update', 0)} "
            f"seed={counts.get('seed', 0)} skip={counts.get('skip', 0)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
