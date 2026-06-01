#!/usr/bin/env python3
"""Staging verification harness for Phase 2C commercial entitlement governance."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT_DIR = ROOT / "docs" / "audit" / "phase2c_commercial_entitlement_governance_01"


async def run_scenarios(client_id: str, *, dry_run: bool = True) -> dict:
    from services.commercial_entitlement_service import build_commercial_entitlement_assessment
    from services.commercial_entitlement_stripe_convergence_service import (
        prevent_duplicate_subscription_risk,
        reconcile_entitlement_billing_state,
    )
    from services.commercial_entitlement_service import detect_entitlement_drift

    assessment = await build_commercial_entitlement_assessment(client_id)
    drift = await detect_entitlement_drift(client_id)
    recon = await reconcile_entitlement_billing_state(client_id)
    dup = await prevent_duplicate_subscription_risk(client_id)

    scenarios = {
        "A_grace_extension": {"executable": "grant_grace_period" in (assessment.get("executable_actions") or [])},
        "B_billing_suspension": {"executable": "suspend_billing" in (assessment.get("executable_actions") or [])},
        "C_sponsored_access": {"executable": "grant_sponsored_access" in (assessment.get("executable_actions") or [])},
        "D_grace_expiry": {"job": "commercial_entitlement_expiry", "note": "Run job after granting short grace"},
        "E_retention_continuity": {"executable": "retention_extension" in (assessment.get("executable_actions") or [])},
        "F_duplicate_subscription_prevention": dup,
    }
    return {
        "client_id": client_id,
        "dry_run": dry_run,
        "assessment": assessment,
        "drift": drift,
        "reconciliation": recon,
        "scenarios": scenarios,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def write_audit_bundle(payload: dict) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "root_cause.json": {"programme": "PHASE-2C", "note": "Fragmented pilot waivers → governed commercial_entitlement_governance"},
        "entitlement_runtime.json": payload.get("assessment"),
        "stripe_convergence_runtime.json": payload.get("reconciliation"),
        "continuity_runtime.json": (payload.get("assessment") or {}).get("continuity"),
        "audit_runtime.json": {"scenarios": payload.get("scenarios")},
        "browser_runtime.json": {"status": "pending", "note": "Capture admin Commercial Controls + customer copy in staging UI"},
        "regression_runtime.json": {"pytest": "backend/tests/test_commercial_entitlement_governance.py"},
        "classifications.json": {
            "classification": "IMPLEMENTED_PENDING_OPERATIONAL_VERIFICATION",
            "requires_browser_proof": True,
        },
    }
    for name, content in files.items():
        (AUDIT_DIR / name).write_text(json.dumps(content, indent=2), encoding="utf-8")
    report = AUDIT_DIR / "REPORT.md"
    report.write_text(
        """# Phase 2C — Commercial Entitlement Governance

## Status
**IMPLEMENTED_PENDING_OPERATIONAL_VERIFICATION** — backend + admin UI wired; browser/staging proof required for `VERIFIED_OPERATIONALLY`.

## Governance principles
- Commercial governance state ≠ canonical access band (`derive_customer_access_state` only bridge)
- Platform authoritative in v1; Stripe lightweight reconciliation
- One active governance row per client
- Commercial ≠ compliance destruction (`access_policy`)
- Sponsored access requires expiry/review + sponsor reference
- Mandatory admin impact preview before execute

## Verification
Run `python scripts/staging_commercial_entitlement_verify.py --client-id <id>` against staging Mongo.
Complete browser scenarios A–F on `/admin/clients/{id}` → Billing tab → Commercial Controls.
""",
        encoding="utf-8",
    )
    watchlist = AUDIT_DIR / "watchlist.md"
    watchlist.write_text(
        """# Watchlist — Phase 2C

- Schedule `commercial_entitlement_expiry` job in production scheduler if not auto-registered.
- Replace fragmented pilot waiver buttons with Commercial Controls when ops-ready.
- Upgrade Stripe convergence beyond lightweight v1 when billing programme authorizes.
- Browser proof: grace, suspend, sponsor, expiry, retention, duplicate subscription advisory.
""",
        encoding="utf-8",
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--write-audit", action="store_true")
    args = parser.parse_args()
    from database import database

    await database.connect()
    try:
        payload = await run_scenarios(args.client_id)
        print(json.dumps(payload, indent=2, default=str))
        if args.write_audit:
            write_audit_bundle(payload)
            print(f"Audit bundle written to {AUDIT_DIR}")
    finally:
        await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
