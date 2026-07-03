#!/usr/bin/env python3
"""Read-only runtime contract drift diagnostic (ILP-2)."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.account_lifecycle_runtime_contract import (  # noqa: E402
    build_runtime_contract,
    compare_runtime_with_legacy,
    runtime_contract_to_dict,
)
from services.account_lifecycle_state_resolver import (  # noqa: E402
    compare_resolution_with_existing_fields,
    resolve_account_lifecycle_state,
)

FIXTURES: List[Dict[str, Any]] = [
    {
        "label": "active_paid",
        "client": {"client_id": "fx-active", "billing_plan": "PLAN_2_PORTFOLIO", "client_lifecycle_status": "ACTIVE"},
        "billing": {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active", "canonical_entitlement_state": "ENABLED"},
    },
    {
        "label": "cancelled_recovery",
        "client": {"client_id": "fx-cancel", "billing_plan": "PLAN_1_SOLO"},
        "billing": {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled", "canonical_entitlement_state": "CANCELLED"},
    },
    {
        "label": "grace_period",
        "client": {"client_id": "fx-grace", "billing_plan": "PLAN_3_PRO"},
        "billing": {
            "subscription_status": "PAST_DUE",
            "billing_lifecycle_state": "grace_period",
            "grace_period_ends_at": "2026-07-01T00:00:00+00:00",
        },
    },
    {
        "label": "archived_stripe_active",
        "client": {"client_id": "fx-arch", "is_deleted": True, "client_lifecycle_status": "ARCHIVED"},
        "billing": {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
    },
]


def run_fixture_diagnostic() -> Dict[str, Any]:
    rows = []
    for fx in FIXTURES:
        resolution = resolve_account_lifecycle_state(client=fx.get("client"), billing=fx.get("billing"))
        contract = build_runtime_contract(client=fx.get("client"), billing=fx.get("billing"), include_audit=True)
        legacy = compare_runtime_with_legacy(contract)
        resolver_cmp = compare_resolution_with_existing_fields(resolution)
        rows.append(
            {
                "fixture": fx["label"],
                "resolver": resolution.to_dict(),
                "runtime": runtime_contract_to_dict(contract),
                "legacy_comparison": legacy,
                "resolver_comparison": resolver_cmp,
            }
        )
    return {
        "mode": "fixture",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture_count": len(FIXTURES),
        "rows": rows,
    }


async def run_client_diagnostic(client_id: str) -> Dict[str, Any]:
    from database import database
    from services.account_lifecycle_runtime_contract import resolve_runtime_contract_for_client

    await database.connect()
    try:
        contract = await resolve_runtime_contract_for_client(database.get_db(), client_id, include_audit=True)
        return {
            "mode": "client_id",
            "client_id": client_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "runtime": runtime_contract_to_dict(contract),
            "legacy_comparison": compare_runtime_with_legacy(contract),
        }
    finally:
        await database.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description="Lifecycle runtime contract drift diagnostic (read-only)")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--client-id", type=str)
    parser.add_argument("--json-out", type=str)
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
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
