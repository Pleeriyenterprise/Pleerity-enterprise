"""MongoDB indexes for Twin webhook connector collections — Stage Y."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from services.discovery.twin.twin_connector_constants import (
    DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION,
    DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION,
)

logger = logging.getLogger(__name__)

IndexSpec = Tuple[str, Any, Dict[str, Any]]

TWIN_CONNECTOR_INDEX_INVENTORY: List[IndexSpec] = [
    (DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION, "receipt_id", {"unique": True}),
    (
        DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION,
        [("twin_agent_id", 1), ("twin_run_id", 1), ("event", 1)],
        {"unique": True, "name": "idx_twin_webhook_receipt_run_event"},
    ),
    (DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION, "status", {}),
    (DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION, "created_at", {}),
    (DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION, "capture_id", {"unique": True}),
    (
        DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION,
        [("twin_agent_id", 1), ("twin_run_id", 1)],
        {"name": "idx_twin_event_capture_run"},
    ),
    (DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION, "receipt_id", {}),
    (DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION, "captured_at", {}),
]


async def ensure_twin_connector_indexes(db) -> None:
    for collection_name, keys, kwargs in TWIN_CONNECTOR_INDEX_INVENTORY:
        try:
            await db[collection_name].create_index(keys, **kwargs)
        except Exception as exc:
            logger.warning(
                "Twin connector index note collection=%s keys=%s: %s",
                collection_name,
                keys,
                exc,
            )
    logger.info(
        "Twin connector MongoDB indexes created/verified (%d specs)",
        len(TWIN_CONNECTOR_INDEX_INVENTORY),
    )
