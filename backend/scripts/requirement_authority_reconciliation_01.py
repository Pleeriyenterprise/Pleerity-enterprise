#!/usr/bin/env python3
"""
REQUIREMENT-RECONCILIATION-AUTHORITY-01 runner.

Usage:
  python scripts/requirement_authority_reconciliation_01.py --dry-run
  python scripts/requirement_authority_reconciliation_01.py --client-id <uuid>
  python scripts/requirement_authority_reconciliation_01.py --execute --client-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
OUT_DIR = BACKEND / "docs/audit/requirement_reconciliation_authority_01"
sys.path.insert(0, str(BACKEND))

load_dotenv(BACKEND / ".env")
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]


async def _run(args: argparse.Namespace) -> int:
    from database import database
    from services.requirement_authority_reconciliation_service import (
        reconcile_requirement_authority_duplicates,
    )

    await database.connect()
    dry_run = not args.execute
    result = await reconcile_requirement_authority_duplicates(
        client_id=args.client_id,
        dry_run=dry_run,
        reconciled_by=args.reconciled_by,
        limit=args.limit,
    )

    idem = None
    if args.idempotency_check and not dry_run:
        second = await reconcile_requirement_authority_duplicates(
            client_id=args.client_id,
            dry_run=False,
            reconciled_by=args.reconciled_by,
            limit=args.limit,
        )
        idem = {
            "second_run_archived": second.get("records_archived"),
            "second_run_to_archive": second.get("records_to_archive"),
            "pass": second.get("records_archived") == 0 and second.get("records_to_archive") == 0,
        }
        result["idempotency_verification"] = idem

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = "dry_run" if dry_run else "execute"
    json_path = OUT_DIR / f"REQUIREMENT_RECONCILIATION_{suffix}_{tag}.json"
    json_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    latest_json = OUT_DIR / "REQUIREMENT_RECONCILIATION.json"
    latest_md = OUT_DIR / "REQUIREMENT_RECONCILIATION_REPORT.md"
    latest_json.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    lines = [
        "# REQUIREMENT-RECONCILIATION-AUTHORITY-01",
        "",
        f"**Mode:** {'dry-run' if dry_run else 'execute'}",
        f"**Duration:** {result.get('duration_ms')} ms",
        f"**Duplicate families found:** {result.get('duplicate_families_found')}",
        f"**Records to archive:** {result.get('records_to_archive')}",
        f"**Records archived:** {result.get('records_archived')}",
        "",
        "## Metrics before",
        "",
        "```json",
        json.dumps(result.get("metrics_before"), indent=2),
        "```",
        "",
        "## Metrics after",
        "",
        "```json",
        json.dumps(result.get("metrics_after"), indent=2),
        "```",
        "",
    ]
    if idem:
        lines.extend(
            [
                "## Idempotency verification",
                "",
                f"**Pass:** {idem.get('pass')}",
                "",
                "```json",
                json.dumps(idem, indent=2),
                "```",
                "",
            ]
        )
    lines.append(f"Evidence: `{json_path.name}`")
    latest_md.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"ok": True, "dry_run": dry_run, "result": result, "evidence": str(latest_json)}, indent=2))
    if idem and not idem.get("pass"):
        return 1
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", default=True, help="Analyze only (default)")
    p.add_argument("--execute", action="store_true", help="Apply supersede archives")
    p.add_argument("--client-id", default=None, help="Limit to one client")
    p.add_argument("--limit", type=int, default=None, help="Max requirement rows scanned")
    p.add_argument(
        "--reconciled-by",
        default="system:requirement_authority_reconciliation_01",
        help="Actor id stored on archived rows and audit logs",
    )
    p.add_argument(
        "--idempotency-check",
        action="store_true",
        help="After execute, run reconciliation a second time and require 0 changes",
    )
    args = p.parse_args()
    if args.execute:
        args.dry_run = False
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
