"""
Scheduled operational evidence maintenance — bounded backfill + retention tiering.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from services.operational_evidence.backfill_service import run_operational_evidence_backfill
from services.operational_evidence.retention_service import apply_warm_retention_tier

logger = logging.getLogger(__name__)


async def run_operational_evidence_maintenance(
    *,
    backfill_days: int = 1,
    backfill_limit_per_source: int = 200,
    retention_batch_limit: int = 2000,
) -> Dict[str, Any]:
    backfill = await run_operational_evidence_backfill(
        days=backfill_days,
        limit_per_source=backfill_limit_per_source,
    )
    retention = await apply_warm_retention_tier(batch_limit=retention_batch_limit)
    emitted = backfill.get("totals", {}).get("emitted", 0)
    modified = retention.get("modified", 0)
    return {
        "message": (
            f"Operational evidence maintenance: backfill emitted {emitted}, "
            f"retention warm-tier modified {modified}"
        ),
        "count": emitted + modified,
        "backfill": backfill,
        "retention": retention,
    }
