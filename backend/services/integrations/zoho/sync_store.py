"""Sync run persistence, dead-letter queue, external keys, and queue claims."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from database import database
from services.integrations.zoho.types import (
    ZOHO_EXTERNAL_KEYS_COLLECTION,
    ZOHO_QUEUE_LEASE_SECONDS,
    ZOHO_SYNC_DEAD_LETTER_COLLECTION,
    ZOHO_SYNC_QUEUE_COLLECTION,
    ZOHO_SYNC_RUNS_COLLECTION,
    SyncDirection,
    SyncStatus,
)
from services.integrations.zoho.version import sync_run_versions

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def generate_sync_id() -> str:
    return f"ZSYNC-{uuid.uuid4().hex[:12].upper()}"


def generate_queue_worker_id() -> str:
    return f"WQ-{uuid.uuid4().hex[:12].upper()}"


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
        result_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        db = database.get_db()
        update: Dict[str, Any] = {
            "status": status.value,
            "message": message,
            "external_id": external_id,
            "error": error,
            "updated_at": _now_iso(),
            "completed_at": _now_iso(),
        }
        if result_summary is not None:
            update["result_summary"] = result_summary
        await db[ZOHO_SYNC_RUNS_COLLECTION].update_one(
            {"sync_id": sync_id},
            {"$set": update},
        )

    async def find_successful_analytics_period_export(
        self, period_start: str, period_end: str
    ) -> Optional[Dict[str, Any]]:
        """Return prior successful analytics export for the same reporting window, if any."""
        db = database.get_db()
        return await db[ZOHO_SYNC_RUNS_COLLECTION].find_one(
            {
                "integration": "analytics",
                "operation": "export_aggregates",
                "status": SyncStatus.SUCCESS.value,
                "result_summary.period_start": period_start,
                "result_summary.period_end": period_end,
            },
            {"_id": 0, "sync_id": 1, "completed_at": 1, "result_summary": 1},
            sort=[("completed_at", -1)],
        )

    async def mark_dead_letter_resolved(self, dead_letter_id: str) -> None:
        db = database.get_db()
        await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].update_one(
            {"dead_letter_id": dead_letter_id},
            {"$set": {"resolved": True, "updated_at": _now_iso()}},
        )

    async def increment_dead_letter_replay(self, dead_letter_id: str) -> None:
        db = database.get_db()
        await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].update_one(
            {"dead_letter_id": dead_letter_id},
            {"$inc": {"replay_count": 1}, "$set": {"updated_at": _now_iso()}},
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
                "claim_id": None,
                "claimed_at": None,
                "lease_expires_at": None,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        return queue_id

    async def fetch_pending_queue(self, integration: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Read-only listing of pending rows (observability). Prefer claim_pending_queue for workers."""
        db = database.get_db()
        filt: Dict[str, Any] = {"status": "pending"}
        if integration:
            filt["integration"] = integration
        return await db[ZOHO_SYNC_QUEUE_COLLECTION].find(filt, {"_id": 0}).sort("created_at", 1).to_list(limit)

    async def claim_pending_queue(
        self,
        integration: Optional[str] = None,
        limit: int = 50,
        *,
        worker_id: Optional[str] = None,
        lease_seconds: int = ZOHO_QUEUE_LEASE_SECONDS,
    ) -> List[Dict[str, Any]]:
        """
        Atomically claim up to ``limit`` queue items: pending|expired-processing → processing.
        Two workers cannot claim the same item.
        """
        db = database.get_db()
        claimer = worker_id or generate_queue_worker_id()
        now = _now()
        now_iso = now.isoformat()
        lease_iso = (now + timedelta(seconds=max(30, int(lease_seconds)))).isoformat()
        claimed: List[Dict[str, Any]] = []

        for _ in range(max(1, int(limit))):
            status_clause: Dict[str, Any] = {
                "$or": [
                    {"status": "pending"},
                    {
                        "status": "processing",
                        "lease_expires_at": {"$lte": now_iso},
                    },
                ]
            }
            filt: Dict[str, Any] = status_clause
            if integration:
                filt = {"$and": [{"integration": integration}, status_clause]}

            doc = await db[ZOHO_SYNC_QUEUE_COLLECTION].find_one_and_update(
                filt,
                {
                    "$set": {
                        "status": "processing",
                        "claim_id": claimer,
                        "claimed_at": now_iso,
                        "lease_expires_at": lease_iso,
                        "updated_at": now_iso,
                    }
                },
                sort=[("created_at", 1)],
                return_document=ReturnDocument.AFTER,
            )
            if not doc:
                break
            doc.pop("_id", None)
            claimed.append(doc)
        return claimed

    async def mark_queue_done(self, queue_id: str) -> None:
        db = database.get_db()
        await db[ZOHO_SYNC_QUEUE_COLLECTION].update_one(
            {"queue_id": queue_id},
            {
                "$set": {
                    "status": "completed",
                    "claim_id": None,
                    "claimed_at": None,
                    "lease_expires_at": None,
                    "updated_at": _now_iso(),
                }
            },
        )

    async def mark_queue_failed(self, queue_id: str, error: str) -> None:
        db = database.get_db()
        await db[ZOHO_SYNC_QUEUE_COLLECTION].update_one(
            {"queue_id": queue_id},
            {
                "$set": {
                    "status": "failed",
                    "error": error,
                    "claim_id": None,
                    "claimed_at": None,
                    "lease_expires_at": None,
                    "updated_at": _now_iso(),
                },
                "$inc": {"attempts": 1},
            },
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

    async def get_external_key(
        self, integration: str, pleerity_id: str, resource_type: str = "lead"
    ) -> Optional[str]:
        db = database.get_db()
        doc = await db[ZOHO_EXTERNAL_KEYS_COLLECTION].find_one(
            {"integration": integration, "pleerity_id": pleerity_id, "resource_type": resource_type},
            {"_id": 0},
        )
        return doc.get("zoho_id") if doc else None

    async def get_pleerity_id_for_zoho(
        self, integration: str, zoho_id: str, resource_type: str = "lead"
    ) -> Optional[str]:
        db = database.get_db()
        doc = await db[ZOHO_EXTERNAL_KEYS_COLLECTION].find_one(
            {"integration": integration, "zoho_id": zoho_id, "resource_type": resource_type},
            {"_id": 0, "pleerity_id": 1},
        )
        return doc.get("pleerity_id") if doc else None

    async def store_external_key(
        self, integration: str, pleerity_id: str, zoho_id: str, resource_type: str = "lead"
    ) -> str:
        """
        Bind pleerity_id → zoho_id with first-writer-wins semantics.

        Returns the authoritative Zoho ID after binding (may differ if a concurrent
        writer already won). Re-reads on DuplicateKeyError.
        """
        db = database.get_db()
        existing = await self.get_external_key(integration, pleerity_id, resource_type)
        if existing:
            # Immutable after first bind — keep the winner.
            return str(existing)

        other = await self.get_pleerity_id_for_zoho(integration, zoho_id, resource_type)
        if other and other != pleerity_id:
            # Zoho record already bound to a different Pleerity lead — do not steal.
            raise ValueError(
                f"external_key_zoho_id_conflict:zoho={zoho_id}:owner={other}:attempt={pleerity_id}"
            )

        doc = {
            "integration": integration,
            "pleerity_id": pleerity_id,
            "zoho_id": zoho_id,
            "resource_type": resource_type,
            "updated_at": _now_iso(),
            "created_at": _now_iso(),
        }
        try:
            await db[ZOHO_EXTERNAL_KEYS_COLLECTION].insert_one(doc)
            return str(zoho_id)
        except DuplicateKeyError:
            winner = await self.get_external_key(integration, pleerity_id, resource_type)
            if winner:
                return str(winner)
            # Lost on zoho_id uniqueness — another lead owns this CRM id.
            owner = await self.get_pleerity_id_for_zoho(integration, zoho_id, resource_type)
            raise ValueError(
                f"external_key_duplicate_race:zoho={zoho_id}:owner={owner}:attempt={pleerity_id}"
            )

    async def ensure_indexes(self) -> Dict[str, Any]:
        """Create unique indexes for external keys and supporting queue indexes."""
        db = database.get_db()
        results: Dict[str, Any] = {}
        try:
            await db[ZOHO_EXTERNAL_KEYS_COLLECTION].create_index(
                [("integration", 1), ("pleerity_id", 1), ("resource_type", 1)],
                unique=True,
                name="ux_zoho_ext_integration_pleerity_resource",
            )
            results["pleerity_binding"] = "ok"
        except Exception as exc:
            logger.warning("zoho_external_keys pleerity unique index: %s", exc)
            results["pleerity_binding"] = f"error:{exc}"
        try:
            await db[ZOHO_EXTERNAL_KEYS_COLLECTION].create_index(
                [("integration", 1), ("zoho_id", 1), ("resource_type", 1)],
                unique=True,
                name="ux_zoho_ext_integration_zoho_resource",
            )
            results["zoho_binding"] = "ok"
        except Exception as exc:
            logger.warning("zoho_external_keys zoho unique index: %s", exc)
            results["zoho_binding"] = f"error:{exc}"
        try:
            await db[ZOHO_SYNC_QUEUE_COLLECTION].create_index(
                [("status", 1), ("integration", 1), ("created_at", 1)],
                name="ix_zoho_queue_status_integration_created",
            )
            await db[ZOHO_SYNC_QUEUE_COLLECTION].create_index(
                [("status", 1), ("lease_expires_at", 1)],
                name="ix_zoho_queue_status_lease",
            )
            results["queue"] = "ok"
        except Exception as exc:
            logger.warning("zoho_sync_queue indexes: %s", exc)
            results["queue"] = f"error:{exc}"
        return results


zoho_sync_store = ZohoSyncStore()
