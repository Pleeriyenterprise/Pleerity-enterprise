"""
Read-only diagnostic for portfolio risk override outputs (PR5 readiness).

Prints legacy_override_output, policy_override_output (after persistent latch),
effective_override_output, PR5 feature-flag state, fallback fields, canonical reason codes,
gap reconciliation checkpoint snapshot, and optional active latch document.

Examples:
  python -m scripts.diagnose_portfolio_risk_override --client-id CLIENT_A
  python -m scripts.diagnose_portfolio_risk_override --all-tenants --limit 25
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def _tenant_snapshot(db: Any, *, client_id: str) -> Dict[str, Any]:
    from services.compliance_gap_sync import aggregate_gap_counts_for_client
    from services.compliance_score import (
        build_portfolio_override_outputs,
        get_persisted_portfolio_headline_for_summary,
    )
    from services.portfolio_override_policy_health import get_tenant_policy_runtime_health
    from services.portfolio_override_inputs import build_portfolio_legacy_property_breakdown_for_override
    from services.portfolio_risk_override_flag import is_feature_policy_backed_portfolio_override_enabled
    from services.portfolio_risk_override_latch import load_critical_escalation_latch

    headline = await get_persisted_portfolio_headline_for_summary(client_id, skip_lazy_backfill=True)
    properties = headline.get("properties") or []
    gap_engine_unavailable = False
    try:
        gap_engine = await aggregate_gap_counts_for_client(db, client_id)
    except Exception:
        gap_engine_unavailable = True
        gap_engine = {
            "by_kind": {},
            "by_severity": {},
            "total_open": 0,
            "policy": {
                "critical_mandatory_breach_count": 0,
                "high_risk_gap_count": 0,
                "attention_only_gap_count": 0,
                "unknown_or_stale_signal_count": 0,
                "policy_fields_present_count": 0,
                "policy_coverage_percent": 0.0,
                "top_reason_codes": {},
                "policy_versions": {},
                "total_open": 0,
            },
        }
    property_breakdown = await build_portfolio_legacy_property_breakdown_for_override(
        db,
        client_id=client_id,
        properties=properties,
    )
    overrides = await build_portfolio_override_outputs(
        db=db,
        client_id=client_id,
        base_portfolio_risk_state=headline.get("risk_level"),
        properties=properties,
        property_breakdown=property_breakdown,
        gap_engine=gap_engine,
        policy_aggregate_unavailable=gap_engine_unavailable,
    )
    try:
        runtime_health = await get_tenant_policy_runtime_health(db, client_id=client_id)
    except Exception:
        runtime_health = {}
    latch = await load_critical_escalation_latch(db, client_id=client_id)
    eff = overrides["effective_override_output"]
    try:
        from services.hiua_operational_uncertainty import hiua_tenant_operational_summary

        hiua = await hiua_tenant_operational_summary(db, client_id, max_gaps_scan=500, max_detail=20)
    except Exception:
        hiua = {
            "hiua_active": False,
            "hiua_open_gap_count": 0,
            "hiua_reason_codes": [],
            "hiua_gap_details": [],
            "hiua_command_centre_message": None,
            "hiua_command_centre_tooltip": None,
            "hiua_command_centre_filter_label": None,
            "hiua_digest_line": None,
            "hiua_report_framing_notice": None,
        }
    return {
        "client_id": client_id,
        "feature_policy_backed_portfolio_override_enabled": is_feature_policy_backed_portfolio_override_enabled(
            client_id
        ),
        "gap_engine_unavailable": gap_engine_unavailable,
        "runtime_health": runtime_health,
        "critical_escalation_latch_active": latch,
        "legacy_override_output": overrides["legacy_override_output"],
        "policy_override_output": overrides["policy_override_output"],
        "effective_override_output": overrides["effective_override_output"],
        "fallback_applied": eff.get("fallback_applied"),
        "fallback_reason_codes": eff.get("fallback_reason_codes"),
        "override_output_source": eff.get("override_output_source"),
        "hiua_operational_uncertainty": hiua,
    }


async def _run(args: argparse.Namespace) -> Dict[str, Any]:
    from database import database
    from services.compliance_policy_backfill_service import discover_tenant_ids

    await database.connect()
    try:
        db = database.get_db()
        if args.client_id:
            tenant_ids: List[str] = [args.client_id.strip()]
        else:
            discovered = await discover_tenant_ids(
                db,
                client_id=None,
                all_tenants=True,
                limit=max(1, int(args.limit)),
                resume_from=args.resume_from,
                include_test_tenants=bool(args.include_test_tenants),
                dry_run=True,
            )
            tenant_ids = list(discovered.get("tenant_ids") or [])
        out: Dict[str, Any] = {"tenants": {}}
        for cid in tenant_ids:
            out["tenants"][cid] = await _tenant_snapshot(db, client_id=cid)
        out["tenant_order"] = tenant_ids
        return out
    finally:
        await database.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only portfolio risk override diagnostic (tenant-scoped).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--client-id", type=str, default=None, help="Single tenant (client_id).")
    g.add_argument("--all-tenants", action="store_true", help="Bounded scan of tenants (uses --limit).")
    ap.add_argument("--limit", type=int, default=50, help="Max tenants when using --all-tenants.")
    ap.add_argument("--resume-from", type=str, default=None, help="Discover tenants with client_id > this value.")
    ap.add_argument("--include-test-tenants", action="store_true", help="Include test-like tenants in discovery.")
    args = ap.parse_args()
    try:
        payload = asyncio.run(_run(args))
        print(json.dumps(payload, indent=2, default=str))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
