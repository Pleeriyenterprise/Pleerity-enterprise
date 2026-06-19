"""
Discovery campaign service — Stage C.

Safe CRUD for discovery_campaigns only. No outreach, leads, or provider ingest.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from database import database
from services.discovery.discovery_models import (
    DISCOVERY_CAMPAIGNS_COLLECTION,
    PLATFORM_TENANT_ID,
    DiscoveryCampaignDocument,
    DiscoveryCampaignStatus,
    DiscoveryLawfulBasis,
    TargetIcp,
    generate_campaign_id,
)

logger = logging.getLogger(__name__)

ALLOWED_CAMPAIGN_STATUS_TRANSITIONS: Dict[DiscoveryCampaignStatus, frozenset[DiscoveryCampaignStatus]] = {
    DiscoveryCampaignStatus.DRAFT: frozenset(
        {DiscoveryCampaignStatus.ACTIVE, DiscoveryCampaignStatus.ARCHIVED}
    ),
    DiscoveryCampaignStatus.ACTIVE: frozenset(
        {
            DiscoveryCampaignStatus.PAUSED,
            DiscoveryCampaignStatus.COMPLETED,
            DiscoveryCampaignStatus.ARCHIVED,
        }
    ),
    DiscoveryCampaignStatus.PAUSED: frozenset(
        {DiscoveryCampaignStatus.ACTIVE, DiscoveryCampaignStatus.ARCHIVED}
    ),
    DiscoveryCampaignStatus.COMPLETED: frozenset({DiscoveryCampaignStatus.ARCHIVED}),
    DiscoveryCampaignStatus.ARCHIVED: frozenset(),
}


class DiscoveryCampaignError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class CreateCampaignRequest(BaseModel):
    name: str
    purpose: str
    target_icp: TargetIcp
    owner_id: str
    owner_email: Optional[str] = None
    budget_reference: Optional[str] = None
    budget_amount: Optional[float] = None
    lawful_basis: DiscoveryLawfulBasis = DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B
    lawful_basis_declaration_id: Optional[str] = None
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)


class DiscoveryCampaignService:
    @staticmethod
    def validate_campaign(
        request: CreateCampaignRequest | DiscoveryCampaignDocument,
    ) -> List[str]:
        errors: List[str] = []
        name = getattr(request, "name", None)
        purpose = getattr(request, "purpose", None)
        owner_id = getattr(request, "owner_id", None)
        target_icp = getattr(request, "target_icp", None)
        lawful_basis = getattr(request, "lawful_basis", None)
        lia_id = getattr(request, "lawful_basis_declaration_id", None)

        if not name or not str(name).strip():
            errors.append("name is required")
        if not purpose or not str(purpose).strip():
            errors.append("purpose is required")
        if not owner_id or not str(owner_id).strip():
            errors.append("owner_id is required")
        if target_icp is None:
            errors.append("target_icp is required")
        if lawful_basis == DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B and not lia_id:
            errors.append(
                "lawful_basis_declaration_id is required when lawful_basis is legitimate_interest_b2b"
            )
        if lawful_basis == DiscoveryLawfulBasis.UNKNOWN:
            errors.append("lawful_basis cannot be unknown for campaigns")
        return errors

    @staticmethod
    async def create_campaign(request: CreateCampaignRequest) -> Dict[str, Any]:
        errors = DiscoveryCampaignService.validate_campaign(request)
        if errors:
            raise DiscoveryCampaignError("VALIDATION_FAILED", "; ".join(errors))

        now = datetime.now(timezone.utc)
        doc = DiscoveryCampaignDocument(
            campaign_id=generate_campaign_id(),
            name=request.name.strip(),
            purpose=request.purpose.strip(),
            target_icp=request.target_icp,
            owner_id=request.owner_id.strip(),
            owner_email=request.owner_email,
            budget_reference=request.budget_reference,
            budget_amount=request.budget_amount,
            lawful_basis=request.lawful_basis,
            lawful_basis_declaration_id=request.lawful_basis_declaration_id,
            status=DiscoveryCampaignStatus.DRAFT,
            tenant_id=request.tenant_id,
            created_at=now,
            updated_at=now,
        )
        payload = doc.model_dump(mode="json")
        db = database.get_db()
        await db[DISCOVERY_CAMPAIGNS_COLLECTION].insert_one(payload)
        logger.info("Discovery campaign created campaign_id=%s", doc.campaign_id)
        return {k: v for k, v in payload.items() if k != "_id"}

    @staticmethod
    async def get_campaign(campaign_id: str) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        doc = await db[DISCOVERY_CAMPAIGNS_COLLECTION].find_one(
            {"campaign_id": campaign_id},
            {"_id": 0},
        )
        return doc

    @staticmethod
    async def list_campaigns(
        *,
        status: Optional[DiscoveryCampaignStatus] = None,
        owner_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        db = database.get_db()
        query: Dict[str, Any] = {"tenant_id": PLATFORM_TENANT_ID}
        if status is not None:
            query["status"] = status.value
        if owner_id:
            query["owner_id"] = owner_id
        cursor = (
            db[DISCOVERY_CAMPAIGNS_COLLECTION]
            .find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    @staticmethod
    def _validate_status_transition(
        current: DiscoveryCampaignStatus,
        new: DiscoveryCampaignStatus,
    ) -> None:
        allowed = ALLOWED_CAMPAIGN_STATUS_TRANSITIONS.get(current, frozenset())
        if new not in allowed:
            raise DiscoveryCampaignError(
                "INVALID_STATUS_TRANSITION",
                f"Cannot transition campaign from {current.value} to {new.value}",
            )

    @staticmethod
    async def update_campaign_status(
        campaign_id: str,
        new_status: DiscoveryCampaignStatus,
    ) -> Dict[str, Any]:
        existing = await DiscoveryCampaignService.get_campaign(campaign_id)
        if not existing:
            raise DiscoveryCampaignError("CAMPAIGN_NOT_FOUND", f"Campaign {campaign_id} not found")

        current = DiscoveryCampaignStatus(existing.get("status", DiscoveryCampaignStatus.DRAFT.value))
        DiscoveryCampaignService._validate_status_transition(current, new_status)

        now = datetime.now(timezone.utc)
        db = database.get_db()
        await db[DISCOVERY_CAMPAIGNS_COLLECTION].update_one(
            {"campaign_id": campaign_id},
            {"$set": {"status": new_status.value, "updated_at": now.isoformat()}},
        )
        updated = await DiscoveryCampaignService.get_campaign(campaign_id)
        assert updated is not None
        return updated
