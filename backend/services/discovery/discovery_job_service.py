"""
Discovery job stub service — Stage C.

Record CRUD only. No execution, polling, webhooks, or scheduling.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from services.discovery.discovery_models import (
    DISCOVERY_JOBS_COLLECTION,
    PLATFORM_TENANT_ID,
    DiscoveryJobDocument,
    DiscoveryJobStatus,
    DiscoveryProviderId,
    generate_discovery_job_id,
)

logger = logging.getLogger(__name__)


class DiscoveryJobError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class DiscoveryJobService:
    @staticmethod
    async def create_job_record(
        *,
        run_id: str,
        provider: DiscoveryProviderId,
        supports_async: bool = False,
        status: DiscoveryJobStatus = DiscoveryJobStatus.PENDING,
        tenant_id: str = PLATFORM_TENANT_ID,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        doc = DiscoveryJobDocument(
            job_id=generate_discovery_job_id(),
            run_id=run_id,
            provider=provider,
            status=status,
            supports_async=supports_async,
            tenant_id=tenant_id,
            created_at=now,
            completed_at=now if status == DiscoveryJobStatus.COMPLETED else None,
        )
        payload = doc.model_dump(mode="json")
        db = database.get_db()
        await db[DISCOVERY_JOBS_COLLECTION].insert_one(payload)
        logger.info("Discovery job record created job_id=%s run_id=%s", doc.job_id, run_id)
        return {k: v for k, v in payload.items() if k != "_id"}

    @staticmethod
    async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        return await db[DISCOVERY_JOBS_COLLECTION].find_one(
            {"job_id": job_id},
            {"_id": 0},
        )

    @staticmethod
    async def update_job_status(
        job_id: str,
        new_status: DiscoveryJobStatus,
        *,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        existing = await DiscoveryJobService.get_job(job_id)
        if not existing:
            raise DiscoveryJobError("JOB_NOT_FOUND", f"Job {job_id} not found")

        now = datetime.now(timezone.utc)
        update_fields: Dict[str, Any] = {"status": new_status.value}
        if new_status in (DiscoveryJobStatus.COMPLETED, DiscoveryJobStatus.FAILED):
            update_fields["completed_at"] = now.isoformat()
        if error_message is not None:
            update_fields["error_message"] = error_message

        db = database.get_db()
        await db[DISCOVERY_JOBS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": update_fields},
        )
        updated = await DiscoveryJobService.get_job(job_id)
        assert updated is not None
        return updated
