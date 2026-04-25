"""
Persist compliance_gaps for all active requirements (idempotent convergence).

Run from the backend directory with MONGO_URL / DB_NAME set (same as the app):

  python -m scripts.backfill_compliance_gaps --dry-run
  python -m scripts.backfill_compliance_gaps
  python -m scripts.backfill_compliance_gaps --client-id CLIENT_A
  python -m scripts.backfill_compliance_gaps --property-id PROP_1 --client-id CLIENT_A

Large tenants: cap per-row lifecycle audit noise with a single batch summary instead:

  python -m scripts.backfill_compliance_gaps --suppress-lifecycle-audit --emit-batch-summary-audit

Pre-apply composition (same scope as backfill; default = net-new rows only, i.e. matches gaps_opened):

  python -m scripts.backfill_compliance_gaps --inspect-proposed
  python -m scripts.backfill_compliance_gaps --inspect-proposed --client-id CLIENT_A
  python -m scripts.backfill_compliance_gaps --inspect-all-inferred --client-id CLIENT_A

Exit code 1 if any sync/upsert/resolve/bridge errors were recorded (see ``errors`` / ``error_count``).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def _run(args: argparse.Namespace) -> dict:
    from database import database
    from services.compliance_gap_backfill import inspect_proposed_gap_composition, run_compliance_gaps_backfill

    await database.connect()
    try:
        db = database.get_db()
        if bool(args.inspect_proposed) or bool(args.inspect_all_inferred):
            return await inspect_proposed_gap_composition(
                db,
                client_id=args.client_id,
                property_id=args.property_id,
                batch_size=max(1, int(args.batch_size)),
                limit=args.limit,
                net_new_only=not bool(args.inspect_all_inferred),
            )
        return await run_compliance_gaps_backfill(
            db,
            client_id=args.client_id,
            property_id=args.property_id,
            dry_run=bool(args.dry_run),
            audit_lifecycle=not bool(args.suppress_lifecycle_audit),
            run_operational_bridge=not bool(args.skip_operational_bridge),
            batch_size=max(1, int(args.batch_size)),
            limit=args.limit,
            emit_batch_summary_audit=bool(args.emit_batch_summary_audit),
        )
    finally:
        await database.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill persisted compliance_gaps from gap engine inference.")
    ap.add_argument("--dry-run", action="store_true", help="Compute summary only; no writes.")
    ap.add_argument("--client-id", type=str, default=None, help="Restrict to one client_id.")
    ap.add_argument("--property-id", type=str, default=None, help="Restrict to one property_id (use with client scope).")
    ap.add_argument("--batch-size", type=int, default=250, help="Mongo page size per fetch.")
    ap.add_argument("--limit", type=int, default=None, help="Max requirement rows to read from DB (testing / partial run).")
    ap.add_argument(
        "--suppress-lifecycle-audit",
        action="store_true",
        help="Do not emit COMPLIANCE_GAP_OPENED / COMPLIANCE_GAP_RESOLVED per row (still persists gaps).",
    )
    ap.add_argument(
        "--emit-batch-summary-audit",
        action="store_true",
        help="With --suppress-lifecycle-audit and a full run, emit one COMPLIANCE_GAP_BACKFILL_COMPLETED audit.",
    )
    ap.add_argument(
        "--skip-operational-bridge",
        action="store_true",
        help="Skip maintenance issue bridge during sync (gaps collection only).",
    )
    ap.add_argument(
        "--inspect-proposed",
        action="store_true",
        help="Print JSON distribution for net-new proposed gaps (not already open); no writes.",
    )
    ap.add_argument(
        "--inspect-all-inferred",
        action="store_true",
        help="Like --inspect-proposed but count every inferred gap row (ignore persisted open keys).",
    )
    args = ap.parse_args()
    if args.property_id and not args.client_id:
        print("error: --property-id should be used together with --client-id for a safe index scope", file=sys.stderr)
        sys.exit(2)
    if args.emit_batch_summary_audit and not args.suppress_lifecycle_audit:
        print("error: --emit-batch-summary-audit requires --suppress-lifecycle-audit", file=sys.stderr)
        sys.exit(2)
    if args.inspect_proposed and args.inspect_all_inferred:
        print("error: use only one of --inspect-proposed or --inspect-all-inferred", file=sys.stderr)
        sys.exit(2)
    if (args.inspect_proposed or args.inspect_all_inferred) and (
        args.dry_run or args.suppress_lifecycle_audit or args.emit_batch_summary_audit or args.skip_operational_bridge
    ):
        print("error: inspection mode does not combine with backfill write/audit flags", file=sys.stderr)
        sys.exit(2)
    result = asyncio.run(_run(args))
    result["error_count"] = len(result.get("errors") or [])
    print(json.dumps(result, indent=2, default=str))
    if result["error_count"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
