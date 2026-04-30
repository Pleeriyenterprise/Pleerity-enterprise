"""
Idempotent backfill for document Evidence Review V2 fields.

Run from backend directory:
  python -m scripts.backfill_evidence_review_v2
  python -m scripts.backfill_evidence_review_v2 --apply
  python -m scripts.backfill_evidence_review_v2 --apply --force

Safety:
- Always prints dry-run summary first.
- Default mode does not overwrite existing evidence_review_state + assurance_tier.
- --force explicitly overwrites mapped fields.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _print_summary(label: str, res: dict) -> None:
    print(f"--- {label} ---")
    print(f"dry_run={res.get('dry_run')} force={res.get('force')} limit={res.get('limit')}")
    print(f"scanned={res.get('scanned')} planned_updates={res.get('planned_updates')} updated={res.get('updated')}")
    for k, v in sorted((res.get("counts_by_legacy_status") or {}).items(), key=lambda x: (-x[1], x[0])):
        print(f"legacy_status[{k}]={v}")
    for k, v in sorted((res.get("counts_by_mapped_state") or {}).items(), key=lambda x: (-x[1], x[0])):
        print(f"mapped_state[{k}]={v}")


async def run(*, apply: bool, force: bool, limit: int) -> None:
    from database import database
    from services.evidence_review_backfill import scan_evidence_review_backfill

    await database.connect()
    db = database.get_db()
    try:
        dry = await scan_evidence_review_backfill(db, limit=limit, force=force, dry_run=True)
        _print_summary("backfill_evidence_review_v2 dry-run", dry)
        if apply:
            applied = await scan_evidence_review_backfill(db, limit=limit, force=force, dry_run=False)
            _print_summary("backfill_evidence_review_v2 apply", applied)
    finally:
        await database.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Apply writes after dry-run summary")
    ap.add_argument("--force", action="store_true", help="Overwrite mapped V2 fields explicitly")
    ap.add_argument("--limit", type=int, default=500, help="Max docs to scan per run (default 500)")
    args = ap.parse_args()
    asyncio.run(run(apply=bool(args.apply), force=bool(args.force), limit=int(args.limit)))


if __name__ == "__main__":
    main()

