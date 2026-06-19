"""
Discovery run service — Stage C.

Safe CRUD for discovery_runs only. No prospect ingest, provider calls, or LeadService.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from database import database
from services.discovery.discovery_campaign_service import DiscoveryCampaignService
from services.discovery.discovery_models import (
    DISCOVERY_RUNS_COLLECTION,
    PLATFORM_TENANT_ID,
    DiscoveryCampaignStatus,
    DiscoveryProviderId,
    DiscoveryRunDocument,
    DiscoveryRunStatus,
    RunAttestation,
    generate_discovery_run_id,
)
from services.discovery.discovery_provider_registry import (
    DiscoveryProviderRegistryError,
    default_provider_registry,
)

logger = logging.getLogger(__name__)

ALLOWED_RUN_STATUS_TRANSITIONS: Dict[DiscoveryRunStatus, frozenset[DiscoveryRunStatus]] = {
    DiscoveryRunStatus.PROCESSING: frozenset(
        {DiscoveryRunStatus.COMPLETED, DiscoveryRunStatus.FAILED, DiscoveryRunStatus.PARTIAL}
    ),
    DiscoveryRunStatus.COMPLETED: frozenset(),
    DiscoveryRunStatus.FAILED: frozenset(),
    DiscoveryRunStatus.PARTIAL: frozenset({DiscoveryRunStatus.COMPLETED}),
}


class DiscoveryRunError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class CreateRunRequest(BaseModel):
    provider: DiscoveryProviderId
    uploaded_by: str
    uploaded_by_email: Optional[str] = None
    campaign_id: Optional[str] = None
    is_ad_hoc: bool = False
    file_name: Optional[str] = None
    attestation: Optional[RunAttestation] = None
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)


class DiscoveryRunService:
    @staticmethod
    async def validate_run(
        request: CreateRunRequest,
        *,
        registry=default_provider_registry,
    ) -> List[str]:
        errors: List[str] = []
        if not request.uploaded_by or not str(request.uploaded_by).strip():
            errors.append("uploaded_by is required")

        if request.campaign_id is None and not request.is_ad_hoc:
            errors.append(
                "campaign_id is required unless is_ad_hoc=True (documented ad-hoc/manual run)"
            )
        if request.is_ad_hoc and request.campaign_id is not None:
            errors.append("is_ad_hoc runs must not set campaign_id")

        try:
            entry = registry.get(request.provider)
            if entry.phase > 1 and not registry.is_enabled(request.provider):
                errors.append(
                    f"Provider '{request.provider.value}' is reserved and disabled"
                )
            elif request.provider not in DiscoveryProviderId.phase1_active() and entry.phase <= 1:
                errors.append(f"provider {request.provider.value} is not Phase 1 active")
        except DiscoveryProviderRegistryError as exc:
            errors.append(exc.message)

        if request.campaign_id and not any(
            "disabled" in e.lower() for e in errors
        ):
            campaign = await DiscoveryCampaignService.get_campaign(request.campaign_id)
            if not campaign:
                errors.append(f"campaign_id {request.campaign_id} not found")
            elif campaign.get("status") == DiscoveryCampaignStatus.ARCHIVED.value:
                errors.append("cannot attach run to archived campaign")

        if request.provider == DiscoveryProviderId.CSV and request.attestation is None:
            errors.append("attestation is required for csv provider runs")

        return errors

    @staticmethod
    async def create_run(
        request: CreateRunRequest,
        *,
        registry=default_provider_registry,
    ) -> Dict[str, Any]:
        errors = await DiscoveryRunService.validate_run(request, registry=registry)
        if errors:
            raise DiscoveryRunError("VALIDATION_FAILED", "; ".join(errors))

        registry.assert_provider_allowed_for_metadata(request.provider)

        now = datetime.now(timezone.utc)
        doc = DiscoveryRunDocument(
            discovery_run_id=generate_discovery_run_id(),
            campaign_id=request.campaign_id,
            is_ad_hoc=request.is_ad_hoc,
            provider=request.provider,
            status=DiscoveryRunStatus.PROCESSING,
            uploaded_by=request.uploaded_by.strip(),
            uploaded_by_email=request.uploaded_by_email,
            file_name=request.file_name,
            attestation=request.attestation,
            tenant_id=request.tenant_id,
            created_at=now,
            updated_at=now,
        )
        payload = doc.model_dump(mode="json")
        db = database.get_db()
        await db[DISCOVERY_RUNS_COLLECTION].insert_one(payload)
        logger.info(
            "Discovery run created discovery_run_id=%s provider=%s",
            doc.discovery_run_id,
            doc.provider.value,
        )
        return {k: v for k, v in payload.items() if k != "_id"}

    @staticmethod
    async def get_run(discovery_run_id: str) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        return await db[DISCOVERY_RUNS_COLLECTION].find_one(
            {"discovery_run_id": discovery_run_id},
            {"_id": 0},
        )

    @staticmethod
    async def list_runs(
        *,
        campaign_id: Optional[str] = None,
        provider: Optional[DiscoveryProviderId] = None,
        status: Optional[DiscoveryRunStatus] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        db = database.get_db()
        query: Dict[str, Any] = {"tenant_id": PLATFORM_TENANT_ID}
        if campaign_id:
            query["campaign_id"] = campaign_id
        if provider is not None:
            query["provider"] = provider.value
        if status is not None:
            query["status"] = status.value
        cursor = (
            db[DISCOVERY_RUNS_COLLECTION]
            .find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    @staticmethod
    def _validate_status_transition(
        current: DiscoveryRunStatus,
        new: DiscoveryRunStatus,
    ) -> None:
        allowed = ALLOWED_RUN_STATUS_TRANSITIONS.get(current, frozenset())
        if new not in allowed:
            raise DiscoveryRunError(
                "INVALID_STATUS_TRANSITION",
                f"Cannot transition run from {current.value} to {new.value}",
            )

    @staticmethod
    async def update_run_status(
        discovery_run_id: str,
        new_status: DiscoveryRunStatus,
    ) -> Dict[str, Any]:
        existing = await DiscoveryRunService.get_run(discovery_run_id)
        if not existing:
            raise DiscoveryRunError("RUN_NOT_FOUND", f"Run {discovery_run_id} not found")

        current = DiscoveryRunStatus(existing.get("status", DiscoveryRunStatus.PROCESSING.value))
        DiscoveryRunService._validate_status_transition(current, new_status)

        now = datetime.now(timezone.utc)
        update_fields: Dict[str, Any] = {
            "status": new_status.value,
            "updated_at": now.isoformat(),
        }
        if new_status in (
            DiscoveryRunStatus.COMPLETED,
            DiscoveryRunStatus.FAILED,
            DiscoveryRunStatus.PARTIAL,
        ):
            update_fields["completed_at"] = now.isoformat()

        db = database.get_db()
        await db[DISCOVERY_RUNS_COLLECTION].update_one(
            {"discovery_run_id": discovery_run_id},
            {"$set": update_fields},
        )
        updated = await DiscoveryRunService.get_run(discovery_run_id)
        assert updated is not None
        return updated

    @staticmethod
    async def attach_run_to_campaign(
        discovery_run_id: str,
        campaign_id: str,
    ) -> Dict[str, Any]:
        run = await DiscoveryRunService.get_run(discovery_run_id)
        if not run:
            raise DiscoveryRunError("RUN_NOT_FOUND", f"Run {discovery_run_id} not found")
        if run.get("is_ad_hoc"):
            raise DiscoveryRunError(
                "AD_HOC_RUN",
                "Cannot attach ad-hoc run to campaign; create a new run with campaign_id",
            )
        if run.get("campaign_id"):
            raise DiscoveryRunError(
                "CAMPAIGN_ALREADY_SET",
                "Run already has campaign_id",
            )

        campaign = await DiscoveryCampaignService.get_campaign(campaign_id)
        if not campaign:
            raise DiscoveryRunError("CAMPAIGN_NOT_FOUND", f"Campaign {campaign_id} not found")
        if campaign.get("status") == DiscoveryCampaignStatus.ARCHIVED.value:
            raise DiscoveryRunError("CAMPAIGN_ARCHIVED", "Cannot attach to archived campaign")

        now = datetime.now(timezone.utc)
        db = database.get_db()
        await db[DISCOVERY_RUNS_COLLECTION].update_one(
            {"discovery_run_id": discovery_run_id},
            {"$set": {"campaign_id": campaign_id, "updated_at": now.isoformat()}},
        )
        updated = await DiscoveryRunService.get_run(discovery_run_id)
        assert updated is not None
        return updated
