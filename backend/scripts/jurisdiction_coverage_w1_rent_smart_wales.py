"""
JURISDICTION-COVERAGE-W1: publish RENT_SMART_WALES_REGISTRATION|WALES to production registry v3.

Exports staging entry, dry-run merge, v2 backup, apply, validate. No other keys changed.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

REGISTRY_KEY = "RENT_SMART_WALES_REGISTRATION|WALES"
PLACEHOLDER = "Draft placeholder: replace with a concise client-facing reason"
OUT_DIR = ROOT / "docs" / "audit" / "jurisdiction_coverage_w1_rent_smart_wales"

# OPS-verified Wales stack (staging reference; validate on production if present)
WALES_CLIENT = "6bcc43c0-16f4-46a5-adf4-26693a0919d0"
WALES_PROPERTY = "2e9c2f5f-d746-4199-b361-0f383ca2e478"
ENGLAND_CLIENT = "a169ee0c-3fd4-42d4-a2a6-8144bc833716"
ENGLAND_PROPERTY = "817a44d1-309f-44ab-98e1-46b5fa51d895"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _count_placeholders(entries: Dict[str, Any]) -> int:
    from services.compliance_registry_admin_service import REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER

    n = 0
    for e in (entries or {}).values():
        if not isinstance(e, dict):
            continue
        short = str(e.get("why_it_matters_short") or e.get("why_it_matters") or "")
        if PLACEHOLDER in short or short == REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER:
            n += 1
    return n


async def _export_staging_entry(stg_db) -> Dict[str, Any]:
    doc = await stg_db["compliance_requirement_registry_published"].find_one(
        {"singleton_key": "active_registry"}, {"_id": 0}
    )
    entries = (doc or {}).get("entries") or {}
    entry = entries.get(REGISTRY_KEY)
    if not isinstance(entry, dict):
        raise RuntimeError(f"Staging missing registry key {REGISTRY_KEY}")
    export = {
        "exported_at": _utc(),
        "staging_published_version": (doc or {}).get("version"),
        "registry_key": REGISTRY_KEY,
        "entry": copy.deepcopy(entry),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "staging_entry_export.json"
    path.write_text(json.dumps(export, indent=2, default=str), encoding="utf-8")
    return export


async def _dry_run_merge(prod_db, staging_entry: Dict[str, Any]) -> Dict[str, Any]:
    from services.compliance_registry_admin_service import validate_registry_draft

    pub = await prod_db["compliance_requirement_registry_published"].find_one(
        {"singleton_key": "active_registry"}, {"_id": 0}
    )
    prev_entries = copy.deepcopy((pub or {}).get("entries") or {})
    merged = copy.deepcopy(prev_entries)
    merged[REGISTRY_KEY] = copy.deepcopy(staging_entry)
    errs: Dict[str, Any] = {}
    ent = merged[REGISTRY_KEY]
    doc = json.loads(json.dumps(ent))
    v_errs = validate_registry_draft(doc)
    if v_errs:
        errs[REGISTRY_KEY] = v_errs
    return {
        "dry_run": True,
        "previous_version": (pub or {}).get("version"),
        "previous_entry_count": len(prev_entries),
        "merged_entry_count": len(merged),
        "action": "added" if REGISTRY_KEY not in prev_entries else "updated",
        "validation_errors": errs,
        "merged_key_preview": {
            "canonical_code": ent.get("canonical_code"),
            "scope_key": ent.get("scope_key"),
            "why_it_matters_short": (str(ent.get("why_it_matters_short") or ""))[:120],
            "primary_action_mode": (
                (ent.get("action_behaviour") or {}).get("primary_action_mode")
                if isinstance(ent.get("action_behaviour"), dict)
                else None
            ),
        },
    }


async def _apply_publish(prod_db, staging_entry: Dict[str, Any]) -> Dict[str, Any]:
    from services.compliance_registry_publish_service import (
        COLLECTION_PUBLISHED,
        SINGLETON_KEY,
        append_published_history_record,
    )

    pub = await prod_db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0})
    prev_entries = copy.deepcopy((pub or {}).get("entries") or {})
    merged = copy.deepcopy(prev_entries)
    merged[REGISTRY_KEY] = copy.deepcopy(staging_entry)
    next_v = int((pub or {}).get("version") or 0) + 1
    now = _utc()
    actor = {"portal_user_id": "jurisdiction_coverage_w1", "email": "system@local"}
    await prod_db[COLLECTION_PUBLISHED].update_one(
        {"singleton_key": SINGLETON_KEY},
        {
            "$set": {
                "singleton_key": SINGLETON_KEY,
                "version": next_v,
                "entries": merged,
                "updated_at": now,
                "last_queue_id": None,
                "last_published_by": actor,
                "last_activation_kind": "jurisdiction_coverage_w1",
                "reverted_from_published_line_version": None,
            }
        },
        upsert=True,
    )
    await append_published_history_record(
        prod_db,
        published_line_version=next_v,
        entries=merged,
        recorded_at=now,
        last_queue_id=None,
        activated_by=actor,
        activation_kind="jurisdiction_coverage_w1",
        reverted_from_published_line_version=None,
    )
    return {"applied": True, "published_version": next_v, "entry_count": len(merged)}


async def _validate(prod_db) -> Dict[str, Any]:
    from database import database
    from services.catalog_compliance import get_property_compliance_detail
    from services.compliance_registry_publish_service import COLLECTION_PUBLISHED, SINGLETON_KEY
    from services.requirement_catalog import RENT_SMART_WALES, get_applicable_requirements
    from services.requirement_truth import enrich_requirements_for_client

    database.db = prod_db

    pub = await prod_db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0})
    entries = (pub or {}).get("entries") or {}
    entry = entries.get(REGISTRY_KEY) or {}

    report: Dict[str, Any] = {
        "registry": {
            "version": (pub or {}).get("version"),
            "entry_count": len(entries),
            "key_present": REGISTRY_KEY in entries,
            "placeholder_count": _count_placeholders(entries),
            "last_activation_kind": (pub or {}).get("last_activation_kind"),
            "why_it_matters_short": (str(entry.get("why_it_matters_short") or ""))[:160],
        }
    }

    async def _prop_checks(client_id: str, property_id: str, label: str) -> Dict[str, Any]:
        prop = await prod_db.properties.find_one(
            {"client_id": client_id, "property_id": property_id}, {"_id": 0}
        )
        client = await prod_db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not prop:
            return {"label": label, "found": False}
        applicable = get_applicable_requirements(prop, client)
        out: Dict[str, Any] = {
            "label": label,
            "found": True,
            "jurisdiction": prop.get("jurisdiction"),
            "tenancy_active": prop.get("tenancy_active"),
            "planner_includes_rent_smart_wales": RENT_SMART_WALES in applicable,
            "applicable_keys": applicable,
        }
        reqs = await prod_db.requirements.find(
            {"client_id": client_id, "property_id": property_id}, {"_id": 0}
        ).to_list(200)
        rsw = [
            r
            for r in reqs
            if str(r.get("requirement_type") or r.get("requirement_code") or "").lower()
            in ("rent_smart_wales", "rent_smart_wales_registration")
        ]
        out["materialised_row_count"] = len(rsw)
        if rsw:
            enriched, _ = await enrich_requirements_for_client(prod_db, client_id, rsw[:1])
            row = enriched[0] if enriched else {}
            out["editorial_why_short"] = (str(row.get("why_it_matters_short") or ""))[:160]
            out["has_placeholder"] = PLACEHOLDER in str(row.get("why_it_matters_short") or "")
        detail = await get_property_compliance_detail(client_id, property_id)
        out["compliance_detail_ok"] = detail is not None
        out["matrix_codes"] = [
            m.get("requirement_code") for m in ((detail or {}).get("matrix") or [])
        ]
        out["kpis"] = (detail or {}).get("kpis")
        return out

    report["wales_property"] = await _prop_checks(WALES_CLIENT, WALES_PROPERTY, "wales_ops_reference")
    report["england_property"] = await _prop_checks(ENGLAND_CLIENT, ENGLAND_PROPERTY, "england_pilot_control")

    # Find any Wales tenancy_active property on production if OPS reference missing
    wales_prop = await prod_db.properties.find_one(
        {
            "jurisdiction": {"$regex": "^Wales$", "$options": "i"},
            "tenancy_active": True,
        },
        {"_id": 0, "client_id": 1, "property_id": 1, "jurisdiction": 1},
    )
    if wales_prop and wales_prop.get("property_id") != WALES_PROPERTY:
        report["wales_fallback"] = await _prop_checks(
            wales_prop["client_id"], wales_prop["property_id"], "wales_production_fallback"
        )

    report["gates"] = {
        "version_is_3": report["registry"].get("version") == 3,
        "key_present": report["registry"].get("key_present") is True,
        "placeholder_zero": report["registry"].get("placeholder_count") == 0,
        "england_no_rent_smart_planner": not report["england_property"].get(
            "planner_includes_rent_smart_wales", True
        ),
        "england_compliance_detail_ok": report["england_property"].get("compliance_detail_ok") is True,
    }
    wales_ref = report.get("wales_property") or {}
    if wales_ref.get("found"):
        report["gates"]["wales_planner_emits_when_tenancy_active"] = wales_ref.get(
            "planner_includes_rent_smart_wales"
        ) is True
        if wales_ref.get("materialised_row_count", 0) > 0:
            report["gates"]["wales_editorial_no_placeholder"] = not wales_ref.get("has_placeholder", True)
    return report


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    if not uri:
        print(json.dumps({"error": "MONGO_URI not set"}))
        return 1

    client = AsyncIOMotorClient = __import__("motor.motor_asyncio", fromlist=["AsyncIOMotorClient"]).AsyncIOMotorClient
    mc = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=20000)
    stg_db = mc["pleerity_staging"]
    prod_db = mc["pleerity_production"]
    await stg_db.command("ping")
    await prod_db.command("ping")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.validate_only:
        validation = await _validate(prod_db)
        out = OUT_DIR / "validation_report.json"
        out.write_text(json.dumps(validation, indent=2, default=str), encoding="utf-8")
        print(json.dumps(validation, indent=2, default=str))
        mc.close()
        return 0

    export = await _export_staging_entry(stg_db)
    staging_entry = export["entry"]

    dry = await _dry_run_merge(prod_db, staging_entry)
    dry_path = OUT_DIR / "production_dry_run.json"
    dry_path.write_text(json.dumps(dry, indent=2, default=str), encoding="utf-8")
    print(json.dumps(dry, indent=2, default=str))

    if dry.get("validation_errors"):
        mc.close()
        return 2

    if args.dry_run and not args.apply:
        mc.close()
        return 0

    if not args.apply:
        mc.close()
        return 0

    pub = await prod_db["compliance_requirement_registry_published"].find_one(
        {"singleton_key": "active_registry"}, {"_id": 0}
    )
    backup_path = OUT_DIR / f"production_registry_v2_backup_{_utc().replace(':', '').replace('-', '')}.json"
    backup_path.write_text(json.dumps(pub, indent=2, default=str), encoding="utf-8")

    apply_result = await _apply_publish(prod_db, staging_entry)
    apply_path = OUT_DIR / "production_apply_output.json"
    apply_path.write_text(
        json.dumps(
            {"backup_v2": str(backup_path), **apply_result},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(json.dumps(apply_result, indent=2))

    validation = await _validate(prod_db)
    val_path = OUT_DIR / "validation_report.json"
    val_path.write_text(json.dumps(validation, indent=2, default=str), encoding="utf-8")
    print(json.dumps(validation, indent=2, default=str))

    mc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
