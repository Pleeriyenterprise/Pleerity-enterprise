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

# Task-style category string -> service_catalogue_v2 category (enum value)
CATEGORY_STRING_TO_ENUM = {
    "automation services": "ai_automation",
    "market research": "market_research",
    "compliance services": "compliance",
    "document packs": "document_pack",
}


def _normalize_service(svc: dict) -> dict:
    """
    Accept both task-style and legacy seed service shapes; return a single
    internal shape for _minimal_service_doc.
    Task shape: name, description_preview, base_price_gbp, currency, requires_review,
                document_types[], is_active, seo_slug, category (display string).
    Legacy shape: service_name, description, workflow_name, display_order, category (enum).
    """
    name = svc.get("name") or svc.get("service_name") or ""
    desc = svc.get("description_preview") or svc.get("description") or ""
    cat_raw = (svc.get("category") or "ai_automation").strip().lower()
    category = CATEGORY_STRING_TO_ENUM.get(cat_raw) or (
        cat_raw if cat_raw in ("ai_automation", "market_research", "compliance", "document_pack") else "ai_automation"
    )
    # base_price: task sends base_price_gbp (e.g. 79); we store pence (7900)
    base_price_gbp = svc.get("base_price_gbp")
    if base_price_gbp is not None:
        base_price = int(round(float(base_price_gbp) * 100))
    else:
        base_price = svc.get("base_price", 0)
    review_required = svc.get("requires_review", svc.get("review_required", True))
    if isinstance(review_required, str):
        review_required = review_required.strip().lower() in ("1", "true", "yes")
    document_types = svc.get("document_types") or []
    # Build documents_generated: list of { template_code, template_name, ... } for catalogue
    documents_generated = svc.get("documents_generated")
    if document_types and not documents_generated:
        documents_generated = [
            {
                "template_code": dt,
                "template_name": dt.replace("_", " ").title(),
                "format": "docx",
                "generation_order": i,
                "gpt_sections": [],
                "is_optional": False,
            }
            for i, dt in enumerate(document_types)
        ]
    elif not documents_generated:
        documents_generated = []
    is_active = svc.get("is_active", True)
    if isinstance(is_active, str):
        is_active = is_active.strip().lower() in ("1", "true", "yes")
    seo_slug = svc.get("seo_slug") or ""
    workflow_name = svc.get("workflow_name", "order_workflow_v2")
    display_order = svc.get("display_order", 99)
    return {
        "service_code": svc["service_code"],
        "service_name": name,
        "description": desc,
        "category": category,
        "base_price": base_price,
        "review_required": review_required,
        "documents_generated": documents_generated,
        "learn_more_slug": seo_slug or None,
        "active": is_active,
        "workflow_name": workflow_name,
        "display_order": display_order,
        "tags": svc.get("tags", []),
        "pack_tier": svc.get("pack_tier"),
        "intake_fields": svc.get("intake_fields", []),
        "pricing_variants": svc.get("pricing_variants", []),
    }


def _generate_template_id() -> str:
    """Generate unique template_id with PTMPL prefix."""
    import hashlib
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    r = os.urandom(4).hex().upper()
    return f"{TEMPLATE_ID_PREFIX}-{ts}-{r}"


def _minimal_service_doc(svc: dict, now: datetime) -> dict:
    """Build minimal service_catalogue_v2 document for upsert. Accepts task or legacy shape via _normalize_service."""
    n = _normalize_service(svc)
    return {
        "service_code": n["service_code"],
        "service_name": n["service_name"],
        "description": n["description"],
        "long_description": None,
        "icon": None,
        "category": n["category"],
        "tags": n["tags"],
        "website_preview": None,
        "learn_more_slug": n["learn_more_slug"],
        "pricing_model": "one_time",
        "base_price": n["base_price"],
        "price_currency": "gbp",
        "vat_rate": 0.20,
        "pricing_variants": n["pricing_variants"],
        "fast_track_available": False,
        "fast_track_price": 2000,
        "fast_track_hours": 24,
        "printed_copy_available": False,
        "printed_copy_price": 2500,
        "delivery_type": "digital",
        "standard_turnaround_hours": 72,
        "delivery_format": "digital",
        "workflow_name": n["workflow_name"],
        "product_type": "one_time",
        "documents_generated": n["documents_generated"],
        "pack_tier": n["pack_tier"],
        "includes_lower_tiers": False,
        "parent_pack_code": None,
        "intake_fields": n["intake_fields"],
        "generation_mode": "GPT_FULL",
        "master_prompt_id": None,
        "gpt_sections": [],
        "review_required": n["review_required"],
        "requires_cvp_subscription": False,
        "is_cvp_feature": False,
        "allowed_plans": [],
        "active": n["active"],
        "display_order": n["display_order"],
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
        schema = entry.get("output_schema") or default_schema
        doc = _prompt_doc(entry, template_id, schema, now, seed_activate)
        await db.prompt_templates.insert_one(doc)
        existing_pairs.add(key)
        inserted += 1
        print(f"  Prompt inserted: {template_id}  {entry['service_code']} / {entry['doc_type']}  status={doc['status']}")

    print()
    print(f"Done. Services: {len(services)} processed. Prompts: {inserted} inserted.")
    await database.close()


if __name__ == "__main__":
    asyncio.run(run())
