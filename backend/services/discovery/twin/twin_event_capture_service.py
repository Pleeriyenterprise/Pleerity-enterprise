"""Persist raw Twin run events for inspection — Stage Y."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.discovery.discovery_models import PLATFORM_TENANT_ID
from services.discovery.twin.twin_connector_constants import (
    DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION,
    generate_twin_event_capture_id,
)
from services.discovery.twin.twin_run_event_extractor import (
    events_json_preview,
    summarize_events_for_capture,
)
from services.discovery.twin.twin_finished_event_analyzer import analyze_finished_output

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TwinEventCaptureService:
    @staticmethod
    async def find_latest_capture(
        *,
        twin_agent_id: str,
        twin_run_id: str,
    ) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        cursor = db[DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION].find(
            {"twin_agent_id": twin_agent_id, "twin_run_id": twin_run_id},
            {"_id": 0},
        ).sort("captured_at", -1).limit(1)
        docs = await cursor.to_list(length=1)
        return docs[0] if docs else None

    @staticmethod
    async def capture_run_events(
        *,
        receipt_id: str,
        twin_agent_id: str,
        twin_run_id: str,
        events: List[Dict[str, Any]],
        twin_run_status: Optional[Dict[str, Any]] = None,
        extraction_diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        diagnostics = extraction_diagnostics or summarize_events_for_capture(events)
        finished_analysis = analyze_finished_output(events)
        diagnostics["finished_event_analysis"] = {
            k: v for k, v in finished_analysis.items() if k != "sample_record_shape"
        }
        if finished_analysis.get("sample_record_shape"):
            diagnostics["finished_event_analysis"]["sample_record_keys"] = sorted(
                finished_analysis["sample_record_shape"].keys()
            )
        doc = {
            "capture_id": generate_twin_event_capture_id(),
            "receipt_id": receipt_id,
            "twin_agent_id": twin_agent_id,
            "twin_run_id": twin_run_id,
            "event_count": len(events),
            "events": events,
            "events_preview": events_json_preview(events),
            "event_diagnostics": diagnostics,
            "twin_run_status": twin_run_status,
            "tenant_id": PLATFORM_TENANT_ID,
            "captured_at": _iso_now(),
        }
        db = database.get_db()
        await db[DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION].insert_one(doc)
        logger.info(
            "Twin run events captured capture_id=%s run_id=%s event_count=%s top_keys=%s",
            doc["capture_id"],
            twin_run_id,
            len(events),
            diagnostics.get("top_level_event_keys"),
        )
        return {k: v for k, v in doc.items() if k != "_id"}

    @staticmethod
    async def get_capture(capture_id: str) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        return await db[DISCOVERY_TWIN_RUN_EVENT_CAPTURES_COLLECTION].find_one(
            {"capture_id": capture_id},
            {"_id": 0},
        )
