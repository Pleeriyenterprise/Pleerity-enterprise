"""
Seed service catalogue and prompt templates from seed_data_v1.json.

Loads backend/seed/seed_data_v1.json, upserts services into service_catalogue_v2,
and inserts prompt templates as version 1 DRAFT (or ACTIVE if SEED_ACTIVATE=true).
Idempotent: skips inserting a prompt if one already exists for (service_code, doc_type).

Usage:
  python -m scripts.seed_services_and_prompts
  SEED_ACTIVATE=true python -m scripts.seed_services_and_prompts  # Activate prompts
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import database

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
SEED_FILE = SEED_DIR / "seed_data_v1.json"
TEMPLATE_ID_PREFIX = "PTMPL"


def _generate_template_id() -> str:
    """Generate unique template_id with PTMPL prefix."""
    import hashlib
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    r = os.urandom(4).hex().upper()
    return f"{TEMPLATE_ID_PREFIX}-{ts}-{r}"


def _minimal_service_doc(svc: dict, now: datetime) -> dict:
    """Build minimal service_catalogue_v2 document for upsert."""
    return {
        "service_code": svc["service_code"],
        "service_name": svc["service_name"],
        "description": svc.get("description", ""),
        "long_description": None,
        "icon": None,
        "category": svc.get("category", "ai_automation"),
        "tags": svc.get("tags", []),
        "website_preview": None,
        "learn_more_slug": None,
        "pricing_model": "one_time",
        "base_price": svc.get("base_price", 0),
        "price_currency": "gbp",
        "vat_rate": 0.20,
        "pricing_variants": svc.get("pricing_variants", []),
        "fast_track_available": False,
        "fast_track_price": 2000,
        "fast_track_hours": 24,
        "printed_copy_available": False,
        "printed_copy_price": 2500,
        "delivery_type": "digital",
        "standard_turnaround_hours": 72,
        "delivery_format": "digital",
        "workflow_name": svc.get("workflow_name", "order_workflow_v2"),
        "product_type": "one_time",
        "documents_generated": svc.get("documents_generated", []),
        "pack_tier": svc.get("pack_tier"),
        "includes_lower_tiers": False,
        "parent_pack_code": None,
        "intake_fields": svc.get("intake_fields", []),
        "generation_mode": "GPT_FULL",
        "master_prompt_id": None,
        "gpt_sections": [],
        "review_required": True,
        "requires_cvp_subscription": False,
        "is_cvp_feature": False,
        "allowed_plans": [],
        "active": True,
        "display_order": svc.get("display_order", 99),
        "created_at": now,
        "updated_at": now,
        "created_by": "seed_script",
        "updated_by": "seed_script",
        "deleted_at": None,
    }


def _prompt_doc(entry: dict, template_id: str, output_schema: dict, now: datetime, activate: bool) -> dict:
    """Build prompt_templates document."""
    status = "ACTIVE" if activate else "DRAFT"
    doc = {
        "template_id": template_id,
        "service_code": entry["service_code"],
        "doc_type": entry["doc_type"],
        "name": entry["name"],
        "description": entry.get("description"),
        "version": 1,
        "status": status,
        "system_prompt": entry["system_prompt"],
        "user_prompt_template": entry["user_prompt_template"],
        "output_schema": output_schema,
        "temperature": 0.3,
        "max_tokens": 4000,
        "tags": entry.get("tags", []),
        "last_test_status": None,
        "last_test_at": None,
        "test_count": 0,
        "created_at": now,
        "created_by": "seed_script",
        "updated_at": None,
        "updated_by": None,
        "activated_at": now if activate else None,
        "activated_by": "seed_script" if activate else None,
        "deprecated_at": None,
        "deprecated_by": None,
        "deleted_at": None,
    }
    return doc


async def run():
    if not SEED_FILE.exists():
        print(f"Seed file not found: {SEED_FILE}")
        sys.exit(1)

    with open(SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    services = data.get("services", [])
    prompts = data.get("prompts", [])
    default_schema = data.get("default_output_schema", {
        "schema_version": "1.0",
        "root_type": "object",
        "strict_validation": True,
        "fields": [
            {"field_name": "content", "field_type": "string", "description": "Main content", "required": True},
            {"field_name": "summary", "field_type": "string", "description": "Brief summary", "required": False},
        ],
    })

    await database.connect()
    db = database.get_db()
    now = datetime.now(timezone.utc)
    seed_activate = os.environ.get("SEED_ACTIVATE", "").strip().lower() in ("1", "true", "yes")

    print("Seed data version:", data.get("version", "1.0"))
    print("SEED_ACTIVATE:", seed_activate)
    print()

    # --- Services: upsert by service_code (insert new; only touch updated_at if exists) ---
    for svc in services:
        existing = await db.service_catalogue_v2.find_one({"service_code": svc["service_code"]})
        if existing:
            await db.service_catalogue_v2.update_one(
                {"service_code": svc["service_code"]},
                {"$set": {"updated_at": now, "updated_by": "seed_script"}},
            )
            print(f"  Service exists:   {svc['service_code']}")
        else:
            doc = _minimal_service_doc(svc, now)
            await db.service_catalogue_v2.insert_one(doc)
            print(f"  Service inserted: {svc['service_code']}")

    # --- Prompts: insert only if no existing (service_code, doc_type) ---
    existing_pairs = set()
    cursor = db.prompt_templates.find({}, {"service_code": 1, "doc_type": 1})
    async for d in cursor:
        existing_pairs.add((d["service_code"], d["doc_type"]))

    inserted = 0
    for entry in prompts:
        key = (entry["service_code"], entry["doc_type"])
        if key in existing_pairs:
            print(f"  Prompt skipped (exists): {entry['service_code']} / {entry['doc_type']}")
            continue
        template_id = _generate_template_id()
        doc = _prompt_doc(entry, template_id, default_schema, now, seed_activate)
        await db.prompt_templates.insert_one(doc)
        existing_pairs.add(key)
        inserted += 1
        print(f"  Prompt inserted: {template_id}  {entry['service_code']} / {entry['doc_type']}  status={doc['status']}")

    print()
    print(f"Done. Services: {len(services)} processed. Prompts: {inserted} inserted.")
    await database.close()


if __name__ == "__main__":
    asyncio.run(run())
