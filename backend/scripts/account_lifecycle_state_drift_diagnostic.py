#!/usr/bin/env python3
"""
Read-only drift diagnostic: compare stored lifecycle bands vs ILP-1 resolver output.

Does not mutate data. Safe for staging/local inspection.

Usage:
  python scripts/account_lifecycle_state_drift_diagnostic.py --fixture
  python scripts/account_lifecycle_state_drift_diagnostic.py --client-id <id>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Allow running from backend/ or repo root
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.account_lifecycle_state_resolver import (  # noqa: E402
    compare_resolution_with_existing_fields,
    resolve_account_lifecycle_state,
)


FIXTURES: List[Dict[str, Any]] = [
    {
        "label": "active_paid",
        "client": {"client_id": "fx-active", "client_lifecycle_status": "ACTIVE", "onboarding_status": "PROVISIONED"},
        "billing": {
            "client_id": "fx-active",
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "active",
            "canonical_entitlement_state": "ENABLED",
        },
    },
    {
        "label": "cancel_scheduled",
        "client": {"client_id": "fx-cap", "client_lifecycle_status": "ACTIVE"},
        "billing": {
            "client_id": "fx-cap",
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "cancel_at_period_end",
            "cancel_at_period_end": True,
            "current_period_end": "2026-08-01T00:00:00+00:00",
        },
    },
    {
        "label": "mirror_drift",
        "client": {
            "client_id": "fx-drift",
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "active",
            "canonical_entitlement_state": "ENABLED",
        },
        "billing": {
            "client_id": "fx-drift",
            "subscription_status": "CANCELED",
            "billing_lifecycle_state": "cancelled",
            "canonical_entitlement_state": "CANCELLED",
        },
    },
    {
        "label": "archived_with_stripe_active",
        "client": {"client_id": "fx-arch", "is_deleted": True, "client_lifecycle_status": "ARCHIVED"},
        "billing": {"client_id": "fx-arch", "subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
    },
]


def run_fixture_diagnostic() -> Dict[str, Any]:
    rows = []
    drift_count = 0
    for fx in FIXTURES:
        resolution = resolve_account_lifecycle_state(client=fx.get("client"), billing=fx.get("billing"))
        comparison = compare_resolution_with_existing_fields(resolution)
        if comparison.get("drift_flags"):
            drift_count += 1
        rows.append(
            {
                "fixture": fx["label"],
                "resolved": resolution.to_dict(),
                "comparison": comparison,
            }
        )
    return {
        "mode": "fixture",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture_count": len(FIXTURES),
        "drift_fixture_count": drift_count,
        "rows": rows,
    }


async def run_client_diagnostic(client_id: str) -> Dict[str, Any]:
    from database import database

    await database.connect()
    try:
        from services.account_lifecycle_state_resolver import resolve_for_client_id

        resolution = await resolve_for_client_id(database.db, client_id)
        comparison = compare_resolution_with_existing_fields(resolution)
        return {
            "mode": "client_id",
            "client_id": client_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "resolved": resolution.to_dict(),
            "comparison": comparison,
        }
    finally:
        await database.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description="Account lifecycle state drift diagnostic (read-only)")
    parser.add_argument("--fixture", action="store_true", help="Run built-in fixture comparison")
    parser.add_argument("--client-id", type=str, help="Resolve a single client from Mongo (read-only)")
    parser.add_argument("--json-out", type=str, help="Optional path to write JSON output")
    args = parser.parse_args()

    if args.fixture:
        report = run_fixture_diagnostic()
    elif args.client_id:
        report = asyncio.run(run_client_diagnostic(args.client_id))
    else:
        parser.print_help()
        return 1

    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
