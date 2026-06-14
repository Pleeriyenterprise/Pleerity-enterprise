"""
JURISDICTION-COVERAGE-S1: publish LEAD_TESTING|SCOTLAND to production registry v4.

Exports staging entry, dry-run merge, v3 backup, apply, validate. No other keys changed.
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

REGISTRY_KEY = "LEAD_TESTING|SCOTLAND"
PLACEHOLDER = "Draft placeholder: replace with a concise client-facing reason"
OUT_DIR = ROOT / "docs" / "audit" / "jurisdiction_coverage_s1_lead_testing_scotland"
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
    changed = [k for k in prev_entries if k in merged and prev_entries[k] != merged[k]]
    added = sorted(set(merged) - set(prev_entries))
    removed = sorted(set(prev_entries) - set(merged))
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
        "projected_version": int((pub or {}).get("version") or 0) + 1,
        "action": "added" if REGISTRY_KEY not in prev_entries else "updated",
        "keys_added": added,
        "keys_removed": removed,
        "keys_changed_excluding_add": [k for k in changed if k not in added],
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
            "conditions": ent.get("conditions"),
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
    actor = {"portal_user_id": "jurisdiction_coverage_s1", "email": "system@local"}
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
                "last_activation_kind": "jurisdiction_coverage_s1",
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
        activation_kind="jurisdiction_coverage_s1",
        reverted_from_published_line_version=None,
    )
    return {"applied": True, "published_version": next_v, "entry_count": len(merged)}


async def _validate(prod_db) -> Dict[str, Any]:
    from database import database
    from services.catalog_compliance import get_property_compliance_detail
    from services.compliance_registry_publish_service import COLLECTION_PUBLISHED, SINGLETON_KEY
    from services.compliance_requirement_registry import build_requirement_plan_for_property
    from services.compliance_registry_publish_service import fetch_active_published_registry_entries
    from services.compliance_scoring_v2 import _applies_if, compute_property_score_v2
    from services.requirement_catalog import LEAD_TESTING, get_applicable_requirements
    from services.requirement_truth import enrich_requirements_for_client

    database.db = prod_db
    published = await fetch_active_published_registry_entries(prod_db)

    pub = await prod_db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0})
    entries = (pub or {}).get("entries") or {}
    entry = entries.get(REGISTRY_KEY) or {}

    v3_backup_files = sorted(OUT_DIR.glob("production_registry_v3_backup_*.json"))
    v3_backup = str(v3_backup_files[-1]) if v3_backup_files else None

    report: Dict[str, Any] = {
        "registry": {
            "version": (pub or {}).get("version"),
            "entry_count": len(entries),
            "key_present": REGISTRY_KEY in entries,
            "placeholder_count": _count_placeholders(entries),
            "last_activation_kind": (pub or {}).get("last_activation_kind"),
            "why_it_matters_short": (str(entry.get("why_it_matters_short") or ""))[:160],
        },
        "rollback": {
            "v3_backup_file": v3_backup,
            "history_line_version_to_revert": 3,
            "revert_command": "revert_active_published_to_line_version(prod_db, target_published_line_version=3, actor={...})",
            "expected_post_rollback": {
                "version": 5,
                "entry_count": 20,
                "LEAD_TESTING|SCOTLAND": "absent",
            },
        },
    }

    def _planner_case(name: str, prop: Dict[str, Any]) -> Dict[str, Any]:
        applicable = get_applicable_requirements(prop, None)
        plan = build_requirement_plan_for_property(prop, {}, published_registry_entries=published)
        plan_types = [p.requirement_type for p in plan]
        score = compute_property_score_v2(
            property_doc=prop,
            client_doc=None,
            requirements=[],
            documents=[],
            open_issues_count=0,
            overdue_work_orders_count=0,
            open_risks_count=0,
        )
        lt = next(
            (b for b in (score.get("requirement_breakdown") or []) if b.get("requirement_code") == "LEAD_TESTING"),
            {},
        )
        mock_req = {
            "requirement_type": "lead_testing",
            "requirement_code": "lead_testing",
            "status": "MISSING",
            "jurisdiction": prop.get("jurisdiction"),
        }
        from services.requirement_truth import enrich_requirement_dict as _enrich

        enriched_row = _enrich(
            mock_req,
            "MISSING",
            published_registry_entries=published,
            property_doc=prop,
            audience="client",
        )
        return {
            "case": name,
            "planner_emits": LEAD_TESTING in applicable,
            "plan_includes_lead_testing": "lead_testing" in plan_types,
            "scoring_applies_if": _applies_if("LEAD_TESTING", prop, None),
            "scoring_weight": lt.get("weight"),
            "scoring_applicable_points": lt.get("applicable_points"),
            "editorial_why_short": (enriched_row.get("why_it_matters_short") or "")[:160],
            "has_placeholder": PLACEHOLDER in str(enriched_row.get("why_it_matters_short") or ""),
        }

    report["synthetic_planner"] = {
        "scotland_age_70_tenancy": _planner_case(
            "scotland_age_70_tenancy",
            {"jurisdiction": "Scotland", "property_type": "flat", "tenancy_active": True, "building_age_years": 70},
        ),
        "scotland_age_40_tenancy": _planner_case(
            "scotland_age_40_tenancy",
            {"jurisdiction": "Scotland", "property_type": "flat", "tenancy_active": True, "building_age_years": 40},
        ),
        "england_age_70_tenancy": _planner_case(
            "england_age_70_tenancy",
            {"jurisdiction": "England", "property_type": "flat", "tenancy_active": True, "building_age_years": 70},
        ),
    }

    eng_prop = await prod_db.properties.find_one(
        {"client_id": ENGLAND_CLIENT, "property_id": ENGLAND_PROPERTY}, {"_id": 0}
    )
    if eng_prop:
        client = await prod_db.clients.find_one({"client_id": ENGLAND_CLIENT}, {"_id": 0})
        applicable = get_applicable_requirements(eng_prop, client)
        detail = await get_property_compliance_detail(ENGLAND_CLIENT, ENGLAND_PROPERTY)
        report["england_control"] = {
            "found": True,
            "planner_includes_lead_testing": LEAD_TESTING in applicable,
            "compliance_detail_ok": detail is not None,
            "matrix_codes": [m.get("requirement_code") for m in (detail or {}).get("matrix") or []],
        }
    else:
        report["england_control"] = {"found": False}

    scot_prop = await prod_db.properties.find_one(
        {
            "jurisdiction": {"$regex": "^Scotland$", "$options": "i"},
            "tenancy_active": True,
            "property_type": {"$nin": ["commercial", "COMMERCIAL"]},
        },
        {"_id": 0},
    )
    if scot_prop:
        report["production_scotland_reference"] = {
            "client_id": scot_prop.get("client_id"),
            "property_id": scot_prop.get("property_id"),
            "building_age_years": scot_prop.get("building_age_years"),
            "read_only": True,
            "note": "No property fields modified; planner/scoring checked against current doc only.",
            **_planner_case("production_scotland_existing", scot_prop),
        }

    sp = report["synthetic_planner"]
    report["gates"] = {
        "version_is_4": report["registry"].get("version") == 4,
        "entry_count_21": report["registry"].get("entry_count") == 21,
        "key_present": report["registry"].get("key_present") is True,
        "placeholder_zero": report["registry"].get("placeholder_count") == 0,
        "scotland_age_70_emits": sp["scotland_age_70_tenancy"]["planner_emits"] is True,
        "scotland_age_40_no_emit": sp["scotland_age_40_tenancy"]["planner_emits"] is False,
        "england_no_emit": sp["england_age_70_tenancy"]["planner_emits"] is False,
        "scoring_weight_8_when_applicable": sp["scotland_age_70_tenancy"]["scoring_weight"] == 8.0,
        "scoring_not_applicable_when_age_low": sp["scotland_age_40_tenancy"]["scoring_applies_if"] is False,
        "england_control_no_lead_testing": not (report.get("england_control") or {}).get(
            "planner_includes_lead_testing", True
        ),
    }
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

    AsyncIOMotorClient = __import__("motor.motor_asyncio", fromlist=["AsyncIOMotorClient"]).AsyncIOMotorClient
    mc = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=20000)
    stg_db = mc["pleerity_staging"]
    prod_db = mc["pleerity_production"]
    await stg_db.command("ping")
    await prod_db.command("ping")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.validate_only:
        validation = await _validate(prod_db)
        out = OUT_DIR / "production_validation_report.json"
        out.write_text(json.dumps(validation, indent=2, default=str), encoding="utf-8")
        print(json.dumps(validation, indent=2, default=str))
        mc.close()
        return 0 if all(validation.get("gates", {}).values()) else 3

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
    backup_path = OUT_DIR / f"production_registry_v3_backup_{_utc().replace(':', '').replace('-', '')}.json"
    backup_path.write_text(json.dumps(pub, indent=2, default=str), encoding="utf-8")

    apply_result = await _apply_publish(prod_db, staging_entry)
    apply_path = OUT_DIR / "production_apply_output.json"
    apply_path.write_text(
        json.dumps({"backup_v3": str(backup_path), **apply_result}, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(apply_result, indent=2))

    validation = await _validate(prod_db)
    val_path = OUT_DIR / "production_validation_report.json"
    val_path.write_text(json.dumps(validation, indent=2, default=str), encoding="utf-8")
    print(json.dumps(validation, indent=2, default=str))

    mc.close()
    return 0 if all(validation.get("gates", {}).values()) else 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
