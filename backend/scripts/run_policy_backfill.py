"""
PR4 policy backfill/reconciliation runner (tenant-scoped, resumable, idempotent).

Examples:
  python -m scripts.run_policy_backfill --client-id CLIENT_A
  python -m scripts.run_policy_backfill --client-id CLIENT_A --batch-size 150 --max-writes-per-sec 30
  python -m scripts.run_policy_backfill --tenant-list CLIENT_A CLIENT_B --tenant-concurrency-limit 2
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
    from services.compliance_policy_backfill_service import (
        discover_tenant_ids,
        get_tenant_policy_convergence_status,
        run_policy_backfill_for_tenants,
    )

    await database.connect()
    try:
        db = database.get_db()
        if args.status_only and args.client_id:
            return await get_tenant_policy_convergence_status(db, client_id=args.client_id)
        discovered = await discover_tenant_ids(
            db,
            client_id=args.client_id,
            all_tenants=bool(args.all_tenants),
            limit=max(1, int(args.limit)),
            resume_from=args.resume_from,
            include_test_tenants=bool(args.include_test_tenants),
            dry_run=bool(args.dry_run),
        )
        tenant_ids = discovered.get("tenant_ids") or []
        if not tenant_ids:
            return {"tenant_results": {}, "discovery": discovered, "message": "No tenants discovered"}
        out = await run_policy_backfill_for_tenants(
            db,
            tenant_ids=tenant_ids,
            tenant_concurrency_limit=max(1, int(args.tenant_concurrency_limit)),
            batch_size=max(1, int(args.batch_size)),
            max_retries=max(0, int(args.max_retries)),
            backoff_seconds=max(0.01, float(args.backoff_seconds)),
            max_writes_per_sec=max(0.1, float(args.max_writes_per_sec)),
            force=bool(args.force),
            dry_run=bool(args.dry_run),
            max_tenants=max(1, int(args.limit)),
        )
        out["discovery"] = discovered
        return out
    finally:
        await database.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Run tenant-scoped policy requirement backfill + gap reconciliation.")
    ap.add_argument("--client-id", type=str, default=None, help="Single tenant ID.")
    ap.add_argument("--all-tenants", action="store_true", help="Discover active tenants from authoritative clients source.")
    ap.add_argument("--include-test-tenants", action="store_true", help="Include test-like tenants in discovery.")
    ap.add_argument("--resume-from", type=str, default=None, help="Discover tenants with client_id > resume-from.")
    ap.add_argument("--limit", type=int, default=100, help="Max tenants per run (bounded all-tenant scan).")
    ap.add_argument("--dry-run", action="store_true", help="Discovery+status only; do not write backfill/reconcile.")
    ap.add_argument("--force", action="store_true", help="Do not skip converged tenants.")
    ap.add_argument("--status-only", action="store_true", help="Return convergence status for --client-id only.")
    ap.add_argument("--tenant-concurrency-limit", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--backoff-seconds", type=float, default=0.25)
    ap.add_argument("--max-writes-per-sec", type=float, default=50.0)
    args = ap.parse_args()
    try:
        result = asyncio.run(_run(args))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        sys.exit(2)
    print(json.dumps(result, indent=2, default=str))
    failed = 0
    for tr in (result.get("tenant_results") or {}).values():
        if tr.get("mode") == "executed":
            failed += int((tr.get("requirement_backfill") or {}).get("failed") or 0)
            failed += int((tr.get("gap_reconciliation") or {}).get("failed") or 0)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
