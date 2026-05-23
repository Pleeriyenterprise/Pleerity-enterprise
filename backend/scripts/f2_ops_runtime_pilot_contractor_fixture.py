"""
F2 ops-runtime bounded staging fixture — assignable maintenance contractor for Wales HMO pilot.

Governance / verification only. Does not bypass quote gates or lifecycle checks.

  python -m scripts.f2_ops_runtime_pilot_contractor_fixture --client-id CID --property-id PID
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import database  # noqa: E402
from services.contractor_service import (  # noqa: E402
    EXECUTION_CAPABILITY_MAINTENANCE,
    PORTAL_ACCESS_ENABLED,
    SOURCE_CLIENT_SUPPLIED_PERSONAL,
    contractor_is_assignable,
    contractor_location_matches_property,
    contractor_passes_work_order_execution_gate,
    contractor_service_regions_allow_jurisdiction,
    contractor_trade_matches_category,
    list_assignable_contractors_for_work_order,
    normalize_email_for_lookup,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
FIXTURE_MARKER = "F2_ops_runtime_pilot_contractor_v1"
FIXTURE_EMAIL = "f2-ops-heating-wales@yopmail.com"
FIXTURE_CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="F2 ops runtime pilot contractor fixture")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def _fixture_doc(*, client_id: str, property_postcode: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    email_norm = normalize_email_for_lookup(FIXTURE_EMAIL)
    return {
        "contractor_id": FIXTURE_CONTRACTOR_ID,
        "client_id": client_id,
        "linked_client_id": client_id,
        "name": "F2 Ops Verify Heating",
        "company_name": "F2 Ops Verify Heating Ltd",
        "contact_name": "F2 Ops Verify Heating",
        "trade_types": ["heating", "plumbing", "general"],
        "vetted": True,
        "email": FIXTURE_EMAIL,
        "email_normalized": email_norm,
        "phone": "+440000000001",
        "areas_served": [property_postcode, "W8", "London"],
        "coverage_area": [property_postcode, "W8", "London"],
        "region": property_postcode or "W8",
        "registration_postcode": property_postcode or "W8",
        "service_regions": ["Wales", "England", "Scotland", "Northern Ireland"],
        "source_type": SOURCE_CLIENT_SUPPLIED_PERSONAL,
        "status": "active",
        "portal_access_status": PORTAL_ACCESS_ENABLED,
        "vetting_status": "approved",
        "available_for_assignment": True,
        "execution_capabilities": EXECUTION_CAPABILITY_MAINTENANCE,
        "declared_execution_capabilities": EXECUTION_CAPABILITY_MAINTENANCE,
        "supported_requirement_codes": [],
        "credentials": [],
        "property_scope": [],
        "notes": FIXTURE_MARKER,
        "updated_at": now,
    }


async def _ensure_fixture(args: argparse.Namespace) -> Dict[str, Any]:
    await database.connect()
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": args.property_id, "client_id": args.client_id},
        {"_id": 0, "postcode": 1, "jurisdiction": 1},
    )
    if not prop:
        raise RuntimeError(f"property not found: {args.property_id}")
    postcode = (prop.get("postcode") or "W8").strip()
    doc = _fixture_doc(client_id=args.client_id, property_postcode=postcode)
    existing = await db.contractors.find_one({"contractor_id": FIXTURE_CONTRACTOR_ID}, {"_id": 0, "created_at": 1})
    if existing and existing.get("created_at"):
        doc["created_at"] = existing["created_at"]
    else:
        doc["created_at"] = doc["updated_at"]
    if args.dry_run:
        return {"dry_run": True, "contractor_id": FIXTURE_CONTRACTOR_ID, "postcode": postcode}
    await db.contractors.update_one(
        {"contractor_id": FIXTURE_CONTRACTOR_ID},
        {"$set": doc},
        upsert=True,
    )
    # Verify assignability against a synthetic maintenance WO shape for the pilot property.
    sample_wo = {
        "client_id": args.client_id,
        "property_id": args.property_id,
        "category": "heating",
        "work_order_kind": "MAINTENANCE",
        "jurisdiction": prop.get("jurisdiction") or "Wales",
    }
    ok_assign, reason = contractor_is_assignable(doc)
    checks = {
        "assignable": ok_assign,
        "assignable_reason": reason,
        "trade_heating": contractor_trade_matches_category(doc, "heating"),
        "location": contractor_location_matches_property(doc, postcode),
        "execution_gate": contractor_passes_work_order_execution_gate(doc, sample_wo),
        "service_region": contractor_service_regions_allow_jurisdiction(doc, sample_wo["jurisdiction"]),
    }
    if not all(checks[k] for k in ("assignable", "trade_heating", "location", "execution_gate", "service_region")):
        raise RuntimeError(f"fixture contractor failed readiness checks: {checks}")
    return {
        "contractor_id": FIXTURE_CONTRACTOR_ID,
        "email": FIXTURE_EMAIL,
        "marker": FIXTURE_MARKER,
        "property_postcode": postcode,
        "checks": checks,
    }


async def _verify_on_open_wo(client_id: str, property_id: str) -> Dict[str, Any]:
    db = database.get_db()
    wo = await db.work_orders.find_one(
        {
            "client_id": client_id,
            "property_id": property_id,
            "status": {"$nin": ["COMPLETED", "CANCELLED", "VERIFIED", "CLOSED"]},
            "work_order_kind": {"$ne": "COMPLIANCE"},
        },
        {"_id": 0, "work_order_id": 1},
        sort=[("created_at", -1)],
    )
    if not wo:
        return {"assignable_on_open_wo": None}
    result = await list_assignable_contractors_for_work_order(client_id, wo["work_order_id"], limit=5)
    return {
        "assignable_on_open_wo": result.get("total", 0) > 0,
        "work_order_id": wo["work_order_id"],
        "eligible": result.get("total"),
        "diagnostics": result.get("filter_diagnostics"),
    }


async def main() -> None:
    args = _parse_args()
    out = await _ensure_fixture(args)
    verify = await _verify_on_open_wo(args.client_id, args.property_id)
    out["verify"] = verify
    print(out)


if __name__ == "__main__":
    asyncio.run(main())
