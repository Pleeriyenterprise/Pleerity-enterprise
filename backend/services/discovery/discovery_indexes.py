"""
MongoDB index definitions for Discovery Foundation collections.

Stage B: index registration only — no query/workflow logic.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from services.discovery.discovery_models import (
    DISCOVERY_AUDIT_LOGS_COLLECTION,
    DISCOVERY_CAMPAIGNS_COLLECTION,
    DISCOVERY_JOBS_COLLECTION,
    DISCOVERY_METRICS_COLLECTION,
    DISCOVERY_PROSPECTS_COLLECTION,
    DISCOVERY_RUNS_COLLECTION,
    PROVIDER_MAPPING_PROFILES_COLLECTION,
)

logger = logging.getLogger(__name__)

# (collection, keys, kwargs) — inventory for tests and ops
IndexSpec = Tuple[str, Any, Dict[str, Any]]

DISCOVERY_INDEX_INVENTORY: List[IndexSpec] = [
    # discovery_campaigns
    (DISCOVERY_CAMPAIGNS_COLLECTION, "campaign_id", {"unique": True}),
    (DISCOVERY_CAMPAIGNS_COLLECTION, "status", {}),
    (DISCOVERY_CAMPAIGNS_COLLECTION, "owner_id", {}),
    (DISCOVERY_CAMPAIGNS_COLLECTION, [("tenant_id", 1), ("created_at", -1)], {}),
    # discovery_runs — campaign reporting + provider
    (DISCOVERY_RUNS_COLLECTION, "discovery_run_id", {"unique": True}),
    (DISCOVERY_RUNS_COLLECTION, "campaign_id", {}),
    (DISCOVERY_RUNS_COLLECTION, "provider", {}),
    (DISCOVERY_RUNS_COLLECTION, [("provider", 1), ("status", 1)], {}),
    (DISCOVERY_RUNS_COLLECTION, "created_at", {}),
    (DISCOVERY_RUNS_COLLECTION, [("tenant_id", 1), ("created_at", -1)], {}),
    # discovery_jobs (stub)
    (DISCOVERY_JOBS_COLLECTION, "job_id", {"unique": True}),
    (DISCOVERY_JOBS_COLLECTION, "run_id", {}),
    (DISCOVERY_JOBS_COLLECTION, [("provider", 1), ("status", 1)], {}),
    # discovery_prospects — cross-run dedupe
    (DISCOVERY_PROSPECTS_COLLECTION, "prospect_id", {"unique": True}),
    (DISCOVERY_PROSPECTS_COLLECTION, "email", {"sparse": True}),
    (DISCOVERY_PROSPECTS_COLLECTION, "phone", {"sparse": True}),
    (DISCOVERY_PROSPECTS_COLLECTION, "email_hash", {"sparse": True}),
    (DISCOVERY_PROSPECTS_COLLECTION, "phone_hash", {"sparse": True}),
    (DISCOVERY_PROSPECTS_COLLECTION, "content_hash", {}),
    (DISCOVERY_PROSPECTS_COLLECTION, "provider_reference", {"sparse": True}),
    (
        DISCOVERY_PROSPECTS_COLLECTION,
        [("provider", 1), ("provider_reference", 1), ("discovery_run_id", 1)],
        {"unique": True, "sparse": True, "name": "idx_discovery_prospect_provider_ref_run"},
    ),
    (
        DISCOVERY_PROSPECTS_COLLECTION,
        [("tenant_id", 1), ("content_hash", 1), ("discovery_run_id", 1)],
        {"name": "idx_discovery_prospect_content_hash_run"},
    ),
    # Review queue
    (DISCOVERY_PROSPECTS_COLLECTION, [("review_status", 1), ("created_at", -1)], {}),
    (DISCOVERY_PROSPECTS_COLLECTION, [("duplicate_status", 1), ("created_at", -1)], {}),
    (DISCOVERY_PROSPECTS_COLLECTION, [("review_status", 1), ("duplicate_status", 1)], {}),
    (DISCOVERY_PROSPECTS_COLLECTION, "review_priority", {}),
    # Import traceability
    (DISCOVERY_PROSPECTS_COLLECTION, "discovery_run_id", {}),
    (DISCOVERY_PROSPECTS_COLLECTION, "campaign_id", {}),
    (DISCOVERY_PROSPECTS_COLLECTION, "merged_into_prospect_id", {"sparse": True}),
    (DISCOVERY_PROSPECTS_COLLECTION, "imported_lead_id", {"sparse": True}),
    (DISCOVERY_PROSPECTS_COLLECTION, [("tenant_id", 1), ("email_hash", 1)], {"sparse": True}),
    (DISCOVERY_PROSPECTS_COLLECTION, [("tenant_id", 1), ("phone_hash", 1)], {"sparse": True}),
    # discovery_audit_logs — immutable append-only
    (DISCOVERY_AUDIT_LOGS_COLLECTION, "audit_id", {"unique": True}),
    (DISCOVERY_AUDIT_LOGS_COLLECTION, [("prospect_id", 1), ("created_at", -1)], {}),
    (DISCOVERY_AUDIT_LOGS_COLLECTION, [("run_id", 1), ("created_at", -1)], {}),
    (DISCOVERY_AUDIT_LOGS_COLLECTION, [("campaign_id", 1), ("created_at", -1)], {}),
    (DISCOVERY_AUDIT_LOGS_COLLECTION, "created_at", {}),
    (DISCOVERY_AUDIT_LOGS_COLLECTION, [("event_type", 1), ("created_at", -1)], {}),
    # discovery_metrics — campaign reporting
    (
        DISCOVERY_METRICS_COLLECTION,
        [("metric_date", 1), ("provider", 1), ("campaign_id", 1)],
        {"unique": True, "name": "idx_discovery_metrics_date_provider_campaign"},
    ),
    (DISCOVERY_METRICS_COLLECTION, "campaign_id", {}),
    (DISCOVERY_METRICS_COLLECTION, "provider", {}),
    # provider_mapping_profiles (reserved)
    (PROVIDER_MAPPING_PROFILES_COLLECTION, "profile_id", {"unique": True}),
    (PROVIDER_MAPPING_PROFILES_COLLECTION, [("provider", 1), ("tenant_id", 1)], {}),
]


async def ensure_discovery_indexes(db) -> None:
    """Register all discovery indexes. Safe to call on startup."""
    for collection_name, keys, kwargs in DISCOVERY_INDEX_INVENTORY:
        try:
            await db[collection_name].create_index(keys, **kwargs)
        except Exception as exc:
            logger.warning(
                "Discovery index note collection=%s keys=%s: %s",
                collection_name,
                keys,
                exc,
            )
    logger.info("Discovery MongoDB indexes created/verified (%d specs)", len(DISCOVERY_INDEX_INVENTORY))
    from services.discovery.twin.twin_connector_indexes import ensure_twin_connector_indexes

    await ensure_twin_connector_indexes(db)
