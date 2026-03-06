"""
Ensure MongoDB indexes for the four services collections.

Run from backend root: python -m scripts.ensure_services_indexes
Or: python scripts/ensure_services_indexes.py (with PYTHONPATH=.)

Idempotency: Orders use source_draft_id (unique) and pricing.stripe_checkout_session_id
(unique, sparse) so the same Stripe event/session cannot create duplicate orders.

Indexes created:
- service_catalogue_v2: service_code, category, active, created_at, soft delete
- intake_drafts: draft_id, draft_ref, service_code, status, created_at
- orders: order_ref, source_draft_id, service_code, status, created_at, stripe session id
- prompt_templates: template_id, service_code+doc_type+status/version, soft delete
- generation_runs: run_id, order_id, status, created_at
- document_pack_items: item_id, order_id, status, doc_type, doc_key
- generated_documents: document_id, order_id, version, created_at
- document_pack_definitions: doc_key, pack_tier, soft delete
- pack_bundles: bundle_id, order_id, bundle_version
- workflow_events: event_id, order_id, created_at
- deliveries: delivery_id, order_id, status, created_at
- audit_logs: client_id, action, timestamp, resource_type+resource_id
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Allow running as script or module
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def ensure_indexes():
    from database import database

    await database.connect()
    db = database.get_db()

    # --- service_catalogue_v2 ---
    await db.service_catalogue_v2.create_index("service_code", unique=True)
    await db.service_catalogue_v2.create_index("category")
    await db.service_catalogue_v2.create_index([("active", 1), ("display_order", 1)])
    await db.service_catalogue_v2.create_index("created_at")
    await db.service_catalogue_v2.create_index("deleted_at", sparse=True)
    logger.info("service_catalogue_v2 indexes OK")

    # --- intake_drafts ---
    await db.intake_drafts.create_index("draft_id", unique=True)
    await db.intake_drafts.create_index("draft_ref", unique=True)
    await db.intake_drafts.create_index("service_code")
    await db.intake_drafts.create_index("status")
    await db.intake_drafts.create_index([("status", 1), ("created_at", -1)])
    await db.intake_drafts.create_index("created_at")
    await db.intake_drafts.create_index("deleted_at", sparse=True)
    logger.info("intake_drafts indexes OK")

    # --- orders (idempotency + queries) ---
    try:
        await db.orders.create_index("pricing.stripe_checkout_session_id", unique=True, sparse=True)
    except Exception:
        pass
    await db.orders.create_index("source_draft_id", unique=True)
    await db.orders.create_index("order_ref", unique=True)
    await db.orders.create_index([("service_code", 1), ("created_at", -1)])
    await db.orders.create_index([("status", 1), ("created_at", -1)])
    await db.orders.create_index("created_at")
    logger.info("orders indexes OK")

    # --- prompt_templates ---
    await db.prompt_templates.create_index("template_id", unique=True)
    await db.prompt_templates.create_index([("service_code", 1), ("doc_type", 1), ("status", 1)])
    await db.prompt_templates.create_index([("service_code", 1), ("doc_type", 1), ("version", -1)])
    await db.prompt_templates.create_index("status")
    await db.prompt_templates.create_index("deleted_at", sparse=True)
    logger.info("prompt_templates indexes OK")

    # --- generation_runs ---
    await db.generation_runs.create_index("run_id", unique=True)
    await db.generation_runs.create_index([("order_id", 1), ("created_at", -1)])
    await db.generation_runs.create_index([("status", 1), ("created_at", -1)])
    await db.generation_runs.create_index("created_at")
    logger.info("generation_runs indexes OK")

    # --- document_pack_items ---
    await db.document_pack_items.create_index("item_id", unique=True)
    await db.document_pack_items.create_index([("order_id", 1), ("canonical_index", 1)])
    await db.document_pack_items.create_index("order_id")
    await db.document_pack_items.create_index("status")
    await db.document_pack_items.create_index("doc_type")
    await db.document_pack_items.create_index("doc_key")
    logger.info("document_pack_items indexes OK")

    # --- generated_documents ---
    await db.generated_documents.create_index("document_id", unique=True)
    await db.generated_documents.create_index([("order_id", 1), ("version", 1)])
    await db.generated_documents.create_index([("order_id", 1), ("created_at", -1)])
    await db.generated_documents.create_index("created_at")
    logger.info("generated_documents indexes OK")

    # --- document_pack_definitions ---
    await db.document_pack_definitions.create_index("doc_key", unique=True)
    await db.document_pack_definitions.create_index("pack_tier")
    await db.document_pack_definitions.create_index([("pack_tier", 1), ("canonical_index", 1)])
    await db.document_pack_definitions.create_index("deleted_at", sparse=True)
    logger.info("document_pack_definitions indexes OK")

    # --- pack_bundles ---
    await db.pack_bundles.create_index("bundle_id", unique=True)
    await db.pack_bundles.create_index([("order_id", 1), ("bundle_version", -1)])
    await db.pack_bundles.create_index("order_id")
    logger.info("pack_bundles indexes OK")

    # --- workflow_events ---
    await db.workflow_events.create_index("event_id", unique=True)
    await db.workflow_events.create_index([("order_id", 1), ("created_at", -1)])
    await db.workflow_events.create_index("created_at")
    logger.info("workflow_events indexes OK")

    # --- deliveries ---
    await db.deliveries.create_index("delivery_id", unique=True)
    await db.deliveries.create_index([("order_id", 1), ("created_at", -1)])
    await db.deliveries.create_index([("status", 1), ("created_at", -1)])
    await db.deliveries.create_index("created_at")
    await db.deliveries.create_index("postmark_message_id", sparse=True)
    await db.deliveries.create_index("provider_message_id", sparse=True)
    logger.info("deliveries indexes OK")

    # --- audit_logs (shared with CVP; every admin action) ---
    await db.audit_logs.create_index([("client_id", 1), ("timestamp", -1)])
    await db.audit_logs.create_index([("action", 1), ("timestamp", -1)])
    await db.audit_logs.create_index("timestamp")
    await db.audit_logs.create_index("action")
    await db.audit_logs.create_index([("resource_type", 1), ("resource_id", 1)])
    logger.info("audit_logs indexes OK")

    await database.close()
    logger.info("All services indexes ensured.")


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if not os.environ.get("MONGO_URL"):
        logger.error("MONGO_URL not set")
        sys.exit(1)
    asyncio.run(ensure_indexes())


if __name__ == "__main__":
    main()
