from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import database  # noqa: E402
from services.published_registry_client_truth_migration_service import evaluate_client_truth_migration  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Published registry client-truth migration (dry-run/apply).")
    p.add_argument("--client-id", default=None, help="Optional client_id scope")
    p.add_argument("--limit", type=int, default=20000, help="Maximum requirements to scan")
    p.add_argument("--apply", action="store_true", help="Persist updates. Default is dry-run.")
    p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Write full JSON report to this path (recommended; avoids huge console output).",
    )
    return p


async def _run(args: argparse.Namespace) -> int:
    await database.connect()
    try:
        db = database.get_db()
        out = await evaluate_client_truth_migration(
            db,
            client_id=(args.client_id or None),
            limit=max(100, int(args.limit or 20000)),
            apply=bool(args.apply),
        )
        text = json.dumps(out, indent=2, default=str)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(text, encoding="utf-8")
            print(json.dumps({k: out[k] for k in out if k != "rows"}, indent=2, default=str))
            print(f"Wrote full report ({len(out.get('rows') or [])} rows) to {args.output}")
        else:
            print(text)
        return 0
    finally:
        await database.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run(_parser().parse_args())))

