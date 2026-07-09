"""Sync run persistence, dead-letter queue, and replay."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.integrations.zoho.types import (
    ZOHO_EXTERNAL_KEYS_COLLECTION,
    ZOHO_SYNC_DEAD_LETTER_COLLECTION,
    ZOHO_SYNC_QUEUE_COLLECTION,
    ZOHO_SYNC_RUNS_COLLECTION,
    SyncDirection,
    SyncStatus,
)
from services.integrations.zoho.version import sync_run_versions


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_sync_id() -> str:
    return f"ZSYNC-{uuid.uuid4().hex[:12].upper()}"


class ZohoSyncStore:
    async def create_run(
        self,
        *,
        integration: str,
        operation: str,
        direction: SyncDirection,
        payload_summary: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        sync_id = generate_sync_id()
        db = database.get_db()
        doc = {
            "sync_id": sync_id,
            "integration": integration,
            "operation": operation,
            "direction": direction.value,
            "status": SyncStatus.PENDING.value,
            "attempt": 0,
            "max_attempts": 3,
            "correlation_id": correlation_id,
            "payload_summary": payload_summary or {},
            "versions": sync_run_versions(integration),
            "error": None,
            "external_id": None,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "completed_at": None,
        }
        await db[ZOHO_SYNC_RUNS_COLLECTION].insert_one(doc)
        return sync_id

    async def mark_running(self, sync_id: str) -> None:
        db = database.get_db()
        await db[ZOHO_SYNC_RUNS_COLLECTION].update_one(
            {"sync_id": sync_id},
            {"$set": {"status": SyncStatus.RUNNING.value, "updated_at": _now_iso()}, "$inc": {"attempt": 1}},
        )

    async def complete_run(
        self,
        sync_id: str,
        *,
        status: SyncStatus,
        message: str = "",
        external_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        db = database.get_db()
        await db[ZOHO_SYNC_RUNS_COLLECTION].update_one(
            {"sync_id": sync_id},
            {
                "$set": {
                    "status": status.value,
                    "message": message,
                    "external_id": external_id,
                    "error": error,
                    "updated_at": _now_iso(),
                    "completed_at": _now_iso(),
                }
            },
        )

    async def add_dead_letter(
        self,
        *,
        sync_id: str,
        integration: str,
        operation: str,
        payload: Dict[str, Any],
        error: str,
    ) -> str:
        db = database.get_db()
        dl_id = f"ZDL-{uuid.uuid4().hex[:12].upper()}"
        await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].insert_one(
            {
                "dead_letter_id": dl_id,
                "sync_id": sync_id,
                "integration": integration,
                "operation": operation,
                "payload": payload,
                "error": error,
                "replay_count": 0,
                "resolved": False,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        await self.complete_run(sync_id, status=SyncStatus.DEAD_LETTER, error=error)
        return dl_id

    async def enqueue(self, integration: str, operation: str, payload: Dict[str, Any]) -> str:
        db = database.get_db()
        queue_id = f"ZQ-{uuid.uuid4().hex[:12].upper()}"
        await db[ZOHO_SYNC_QUEUE_COLLECTION].insert_one(
            {
                "queue_id": queue_id,
                "integration": integration,
                "operation": operation,
                "payload": payload,
                "status": "pending",
                "attempts": 0,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        return queue_id

    async def fetch_pending_queue(self, integration: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        db = database.get_db()
        filt: Dict[str, Any] = {"status": "pending"}
        if integration:
            filt["integration"] = integration
        return await db[ZOHO_SYNC_QUEUE_COLLECTION].find(filt, {"_id": 0}).sort("created_at", 1).to_list(limit)

    async def mark_queue_done(self, queue_id: str) -> None:
        db = database.get_db()
        await db[ZOHO_SYNC_QUEUE_COLLECTION].update_one(
            {"queue_id": queue_id},
            {"$set": {"status": "completed", "updated_at": _now_iso()}},
        )

    async def mark_queue_failed(self, queue_id: str, error: str) -> None:
        db = database.get_db()
        await db[ZOHO_SYNC_QUEUE_COLLECTION].update_one(
            {"queue_id": queue_id},
            {"$set": {"status": "failed", "error": error, "updated_at": _now_iso()}, "$inc": {"attempts": 1}},
        )

    async def get_dead_letter(self, dead_letter_id: str) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        return await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].find_one(
            {"dead_letter_id": dead_letter_id}, {"_id": 0}
        )

    async def list_recent_runs(self, integration: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        db = database.get_db()
        filt: Dict[str, Any] = {}
        if integration:
            filt["integration"] = integration
        return await db[ZOHO_SYNC_RUNS_COLLECTION].find(filt, {"_id": 0}).sort("created_at", -1).to_list(limit)

    async def store_external_key(
        self, integration: str, pleerity_id: str, zoho_id: str, resource_type: str = "lead"
    ) -> None:
        db = database.get_db()
        await db[ZOHO_EXTERNAL_KEYS_COLLECTION].update_one(
            {"integration": integration, "pleerity_id": pleerity_id, "resource_type": resource_type},
            {
                "$set": {
                    "integration": integration,
                    "pleerity_id": pleerity_id,
                    "zoho_id": zoho_id,
                    "resource_type": resource_type,
                    "updated_at": _now_iso(),
                }
            },
            upsert=True,
        )

    async def get_external_key(self, integration: str, pleerity_id: str, resource_type: str = "lead") -> Optional[str]:
        db = database.get_db()
        doc = await db[ZOHO_EXTERNAL_KEYS_COLLECTION].find_one(
            {"integration": integration, "pleerity_id": pleerity_id, "resource_type": resource_type},
            {"_id": 0},
        )
        return doc.get("zoho_id") if doc else None


zoho_sync_store = ZohoSyncStore()
