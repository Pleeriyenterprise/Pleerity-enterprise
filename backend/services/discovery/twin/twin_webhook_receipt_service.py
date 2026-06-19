"""Persist Twin webhook receipts for idempotency — Stage Y."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from services.discovery.discovery_models import PLATFORM_TENANT_ID
from services.discovery.twin.twin_connector_constants import (
    DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION,
    generate_twin_webhook_receipt_id,
)

logger = logging.getLogger(__name__)


class TwinWebhookReceiptError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TwinWebhookReceiptService:
    @staticmethod
    async def find_receipt(
        *,
        twin_agent_id: str,
        twin_run_id: str,
        event: str,
    ) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        return await db[DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION].find_one(
            {
                "twin_agent_id": twin_agent_id,
                "twin_run_id": twin_run_id,
                "event": event,
            },
            {"_id": 0},
        )

    @staticmethod
    async def create_receipt(
        *,
        twin_agent_id: str,
        twin_run_id: str,
        event: str,
        webhook_timestamp: str,
        webhook_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        existing = await TwinWebhookReceiptService.find_receipt(
            twin_agent_id=twin_agent_id,
            twin_run_id=twin_run_id,
            event=event,
        )
        if existing:
            return existing

        doc = {
            "receipt_id": generate_twin_webhook_receipt_id(),
            "twin_agent_id": twin_agent_id,
            "twin_run_id": twin_run_id,
            "event": event,
            "webhook_timestamp": webhook_timestamp,
            "status": "received",
            "capture_id": None,
            "discovery_run_id": None,
            "ingest_summary": None,
            "error_code": None,
            "error_message": None,
            "webhook_payload": webhook_payload,
            "tenant_id": PLATFORM_TENANT_ID,
            "created_at": _iso_now(),
            "updated_at": _iso_now(),
        }
        db = database.get_db()
        try:
            await db[DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION].insert_one(doc)
        except Exception as exc:
            if "duplicate key" in str(exc).lower() or "E11000" in str(exc):
                found = await TwinWebhookReceiptService.find_receipt(
                    twin_agent_id=twin_agent_id,
                    twin_run_id=twin_run_id,
                    event=event,
                )
                if found:
                    return found
            raise TwinWebhookReceiptError("RECEIPT_INSERT_FAILED", str(exc)) from exc
        logger.info(
            "Twin webhook receipt created receipt_id=%s run_id=%s event=%s",
            doc["receipt_id"],
            twin_run_id,
            event,
        )
        return {k: v for k, v in doc.items() if k != "_id"}

    @staticmethod
    async def update_receipt(
        receipt_id: str,
        *,
        status: str,
        capture_id: Optional[str] = None,
        discovery_run_id: Optional[str] = None,
        ingest_summary: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        update: Dict[str, Any] = {"status": status, "updated_at": _iso_now()}
        if capture_id is not None:
            update["capture_id"] = capture_id
        if discovery_run_id is not None:
            update["discovery_run_id"] = discovery_run_id
        if ingest_summary is not None:
            update["ingest_summary"] = ingest_summary
        if error_code is not None:
            update["error_code"] = error_code
        if error_message is not None:
            update["error_message"] = error_message

        db = database.get_db()
        await db[DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION].update_one(
            {"receipt_id": receipt_id},
            {"$set": update},
        )
        doc = await db[DISCOVERY_TWIN_WEBHOOK_RECEIPTS_COLLECTION].find_one(
            {"receipt_id": receipt_id},
            {"_id": 0},
        )
        if not doc:
            raise TwinWebhookReceiptError("RECEIPT_NOT_FOUND", f"Receipt {receipt_id} not found")
        return doc
