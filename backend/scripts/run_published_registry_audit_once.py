"""One-off read-only audit for published registry client-truth migration (no --apply)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import database  # noqa: E402
from services.published_registry_client_truth_migration_service import (  # noqa: E402
    evaluate_client_truth_migration,
)


async def _main() -> int:
    await database.connect()
    try:
        db = database.get_db()
        client_id = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else None
        limit = int(sys.argv[2]) if len(sys.argv) > 2 and str(sys.argv[2]).strip().isdigit() else 50000
        r = await evaluate_client_truth_migration(db, client_id=client_id, limit=limit, apply=False)
        summary = {k: v for k, v in r.items() if k != "rows"}
        out_dir = Path(__file__).resolve().parent
        (out_dir / "audit_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        (out_dir / "audit_ghost_visible.json").write_text(
            json.dumps(r.get("ghost_currently_visible_rows", []), indent=2, default=str),
            encoding="utf-8",
        )
        (out_dir / "audit_rows.json").write_text(json.dumps(r.get("rows", []), default=str), encoding="utf-8")
        print(json.dumps({"written": ["audit_summary.json", "audit_ghost_visible.json", "audit_rows.json"]}, indent=2))
        return 0
    finally:
        await database.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
