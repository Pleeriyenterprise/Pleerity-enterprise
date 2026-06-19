"""
Discovery prospect store service — Stage G.

CRUD, validation, review status state machine, origin lineage, quality scoring.
No routes, import, duplicate engine, LeadService, or provider ingest.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from database import database
from services.discovery.discovery_audit_helpers import build_audit_event, prepare_audit_payload
from services.discovery.discovery_hashing import (
    normalize_provider_reference,
    validate_content_hash_hex,
    validate_origin_lineage,
    validate_origin_lineage_entry,
)
from services.discovery.discovery_payload_store import validate_raw_payload_reference
from services.discovery.discovery_quality_service import (
    DiscoveryQualityService,
    QualityInputs,
)
from services.discovery.discovery_models import (
    DISCOVERY_PROSPECTS_COLLECTION,
    PLATFORM_TENANT_ID,
    DiscoveryBusinessType,
    DiscoveryErasureStatus,
    DiscoveryLandlordType,
    DiscoveryLawfulBasis,
    DiscoveryProspectDocument,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
    DiscoverySourceType,
    OriginLineageEntry,
    ProspectLocation,
    compute_content_hash,
    generate_prospect_id,
    normalise_email,
)
from services.discovery.discovery_run_service import DiscoveryRunService

logger = logging.getLogger(__name__)

PROVIDER_REFERENCE_MAX_LEN = 256
INLINE_PAYLOAD_KEYS = frozenset({"raw_payload", "raw_row", "csv_row", "html_payload"})

# Review status state machine — frozen Stage G
ALLOWED_REVIEW_TRANSITIONS: Dict[
    DiscoveryReviewStatus, frozenset[DiscoveryReviewStatus]
] = {
    DiscoveryReviewStatus.DISCOVERED: frozenset({DiscoveryReviewStatus.NEEDS_REVIEW}),
    DiscoveryReviewStatus.NEEDS_REVIEW: frozenset(
        {
            DiscoveryReviewStatus.DUPLICATE_DETECTED,
            DiscoveryReviewStatus.APPROVED,
            DiscoveryReviewStatus.REJECTED,
        }
    ),
    DiscoveryReviewStatus.DUPLICATE_DETECTED: frozenset(
        {
            DiscoveryReviewStatus.NEEDS_REVIEW,
            DiscoveryReviewStatus.REJECTED,
            DiscoveryReviewStatus.APPROVED,  # requires override_reason
        }
    ),
    DiscoveryReviewStatus.APPROVED: frozenset({DiscoveryReviewStatus.ARCHIVED}),
    DiscoveryReviewStatus.REJECTED: frozenset({DiscoveryReviewStatus.ARCHIVED}),
    DiscoveryReviewStatus.IMPORTED: frozenset({DiscoveryReviewStatus.ARCHIVED}),
    DiscoveryReviewStatus.ARCHIVED: frozenset(),
}

TERMINAL_REVIEW_STATUSES = frozenset({DiscoveryReviewStatus.ARCHIVED})

class DiscoveryProspectError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class CreateProspectRequest(BaseModel):
    discovery_run_id: str
    provider: DiscoveryProviderId
    content_hash: str
    source_type: DiscoverySourceType
    lawful_basis: DiscoveryLawfulBasis
    campaign_id: Optional[str] = None
    discovery_job_id: Optional[str] = None
    provider_reference: Optional[str] = None
    provider_confidence: int = Field(default=50, ge=0, le=100)
    marketing_consent: bool = False
    review_status: DiscoveryReviewStatus = DiscoveryReviewStatus.DISCOVERED
    source_url: Optional[str] = None
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    location: Optional[ProspectLocation] = None
    business_type: DiscoveryBusinessType = DiscoveryBusinessType.UNKNOWN
    landlord_type: DiscoveryLandlordType = DiscoveryLandlordType.UNKNOWN
    raw_payload_reference: Optional[str] = None
    risk_flags: List[str] = Field(default_factory=list)
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)
    # Inline payloads forbidden — rejected in validate_prospect if present via extra dict


class UpdateProspectRequest(BaseModel):
    contact_name: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    location: Optional[ProspectLocation] = None
    business_type: Optional[DiscoveryBusinessType] = None
    landlord_type: Optional[DiscoveryLandlordType] = None
    source_url: Optional[str] = None
    provider_confidence: Optional[int] = Field(default=None, ge=0, le=100)
    raw_payload_reference: Optional[str] = None
    risk_flags: Optional[List[str]] = None


class DiscoveryProspectService:
    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def validate_content_hash(content_hash: str) -> List[str]:
        return validate_content_hash_hex(content_hash)

    @staticmethod
    def validate_provider_reference(
        provider: DiscoveryProviderId | str,
        provider_reference: Optional[str],
        *,
        content_hash: Optional[str] = None,
    ) -> List[str]:
        errors: List[str] = []
        provider_id = provider.value if isinstance(provider, DiscoveryProviderId) else provider
        if not provider_reference or not str(provider_reference).strip():
            if not content_hash:
                errors.append("provider_reference or content_hash is required")
            return errors
        ref = str(provider_reference).strip()
        if ":" in ref:
            prefix = ref.split(":", 1)[0].strip().lower()
            if prefix != str(provider_id).strip().lower():
                errors.append(
                    f"provider_reference namespace '{prefix}' does not match provider '{provider_id}'"
                )
        normalized = normalize_provider_reference(provider_id, provider_reference)
        if len(normalized) > PROVIDER_REFERENCE_MAX_LEN:
            errors.append("provider_reference exceeds maximum length")
        if "\n" in normalized or "\r" in normalized:
            errors.append("provider_reference must not contain newlines")
        if ":" in normalized:
            prefix = normalized.split(":", 1)[0]
            if prefix != str(provider_id).strip().lower():
                errors.append(
                    f"provider_reference namespace '{prefix}' does not match provider '{provider_id}'"
                )
        return errors

    @staticmethod
    def validate_raw_payload_reference(reference: Optional[str]) -> List[str]:
        return validate_raw_payload_reference(reference)

    @staticmethod
    async def validate_prospect(
        request: CreateProspectRequest,
        *,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        errors: List[str] = []
        if extra_fields:
            for key in INLINE_PAYLOAD_KEYS:
                if key in extra_fields and extra_fields[key] is not None:
                    errors.append(f"inline field '{key}' is not permitted; use raw_payload_reference")

        if request.lawful_basis == DiscoveryLawfulBasis.UNKNOWN:
            errors.append("lawful_basis cannot be unknown")
        if request.tenant_id != PLATFORM_TENANT_ID:
            errors.append(f"tenant_id must be {PLATFORM_TENANT_ID} in Phase 1")

        errors.extend(DiscoveryProspectService.validate_content_hash(request.content_hash))
        errors.extend(
            DiscoveryProspectService.validate_provider_reference(
                request.provider,
                request.provider_reference,
                content_hash=request.content_hash,
            )
        )
        errors.extend(
            DiscoveryProspectService.validate_raw_payload_reference(
                request.raw_payload_reference
            )
        )

        has_identity = any(
            v and str(v).strip()
            for v in (
                request.email,
                request.phone,
                request.company_name,
                request.website,
            )
        )
        if not has_identity:
            errors.append(
                "at least one of email, phone, company_name, or website is required"
            )

        run = await DiscoveryRunService.get_run(request.discovery_run_id)
        if not run:
            errors.append(f"discovery_run_id {request.discovery_run_id} not found")
        else:
            if run.get("provider") != request.provider.value:
                errors.append("provider must match discovery run provider")
            run_campaign = run.get("campaign_id")
            if request.campaign_id and run_campaign and request.campaign_id != run_campaign:
                errors.append("campaign_id must match linked discovery run")
            if not request.campaign_id and not run.get("is_ad_hoc") and not run_campaign:
                errors.append(
                    "campaign_id required unless discovery run is documented ad-hoc"
                )

        if request.marketing_consent and request.lawful_basis != DiscoveryLawfulBasis.CONSENT:
            errors.append(
                "marketing_consent=true requires lawful_basis=consent"
            )

        if request.review_status not in (
            DiscoveryReviewStatus.DISCOVERED,
            DiscoveryReviewStatus.NEEDS_REVIEW,
        ):
            errors.append(
                "review_status on create must be discovered or needs_review"
            )

        return errors

    @staticmethod
    def compute_platform_quality_score(
        *,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company_name: Optional[str] = None,
        website: Optional[str] = None,
        source_url: Optional[str] = None,
        provider_reference: Optional[str] = None,
        business_type: DiscoveryBusinessType = DiscoveryBusinessType.UNKNOWN,
        landlord_type: DiscoveryLandlordType = DiscoveryLandlordType.UNKNOWN,
        location: Optional[ProspectLocation] = None,
        lawful_basis: DiscoveryLawfulBasis = DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        marketing_consent: bool = False,
        marketing_consent_explicit: bool = False,
        provider_confidence: int = 0,
        risk_flags: Optional[List[str]] = None,
        origin_lineage: Optional[List[OriginLineageEntry]] = None,
    ) -> int:
        """Delegates to DiscoveryQualityService — platform-owned deterministic score."""
        inputs = QualityInputs(
            email=email,
            phone=phone,
            company_name=company_name,
            website=website,
            source_url=source_url,
            provider_reference=provider_reference,
            business_type=business_type,
            landlord_type=landlord_type,
            location=location,
            lawful_basis=lawful_basis,
            marketing_consent=marketing_consent,
            marketing_consent_explicit=marketing_consent_explicit,
            provider_confidence=provider_confidence,
            risk_flags=list(risk_flags or []),
            origin_lineage=list(origin_lineage or []),
        )
        return DiscoveryQualityService.compute_platform_quality_score(inputs)

    @staticmethod
    def derive_review_priority(
        platform_quality_score: int,
        risk_flags: Optional[List[str]] = None,
        *,
        lawful_basis: Optional[DiscoveryLawfulBasis] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company_name: Optional[str] = None,
        website: Optional[str] = None,
    ) -> int:
        """Delegates to DiscoveryQualityService.calculate_review_priority."""
        return DiscoveryQualityService.calculate_review_priority(
            platform_quality_score,
            risk_flags=risk_flags,
            lawful_basis=lawful_basis,
            email=email,
            phone=phone,
            company_name=company_name,
            website=website,
        )

    @staticmethod
    def append_origin_lineage(
        existing: List[OriginLineageEntry],
        *,
        provider: str,
        provider_reference: Optional[str],
        discovery_run_id: str,
        campaign_id: Optional[str],
        source_url: Optional[str],
        content_hash: str,
        discovered_at: Optional[datetime] = None,
        discovery_job_id: Optional[str] = None,
    ) -> List[OriginLineageEntry]:
        """Append-only lineage — never overwrites prior entries."""
        now = discovered_at or datetime.now(timezone.utc)
        entry = OriginLineageEntry(
            provider=provider,
            provider_reference=provider_reference,
            discovery_run_id=discovery_run_id,
            discovery_job_id=discovery_job_id,
            campaign_id=campaign_id,
            source_url=source_url,
            content_hash=content_hash,
            discovered_at=now,
            ingested_at=now,
        )
        entry_errors = validate_origin_lineage_entry(entry)
        if entry_errors:
            raise DiscoveryProspectError(
                "INVALID_LINEAGE",
                "; ".join(entry_errors),
            )
        combined = list(existing) + [entry]
        lineage_errors = validate_origin_lineage(combined, previous=existing or None)
        if lineage_errors:
            raise DiscoveryProspectError(
                "INVALID_LINEAGE",
                "; ".join(lineage_errors),
            )
        return combined

    @staticmethod
    def _assert_not_terminal(prospect: Dict[str, Any]) -> None:
        status = prospect.get("review_status")
        if status in {s.value for s in TERMINAL_REVIEW_STATUSES}:
            raise DiscoveryProspectError(
                "TERMINAL_STATUS",
                f"Prospect in terminal review_status={status}",
            )
        if prospect.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
            raise DiscoveryProspectError(
                "ERASED",
                "Prospect is erased — no further mutations",
            )

    @staticmethod
    def _validate_review_transition(
        current: DiscoveryReviewStatus,
        new: DiscoveryReviewStatus,
        *,
        override_reason: Optional[str] = None,
    ) -> None:
        if new == DiscoveryReviewStatus.IMPORTED:
            raise DiscoveryProspectError(
                "IMPORT_RESERVED",
                "imported status is not reachable in Stage G",
            )
        allowed = ALLOWED_REVIEW_TRANSITIONS.get(current, frozenset())
        if new not in allowed:
            raise DiscoveryProspectError(
                "INVALID_STATUS_TRANSITION",
                f"Cannot transition review_status from {current.value} to {new.value}",
            )
        if (
            current == DiscoveryReviewStatus.DUPLICATE_DETECTED
            and new == DiscoveryReviewStatus.APPROVED
            and not (override_reason and str(override_reason).strip())
        ):
            raise DiscoveryProspectError(
                "OVERRIDE_REQUIRED",
                "duplicate_detected → approved requires override_reason",
            )

    @staticmethod
    def _prepare_audit_event_for_prospect(
        event_type: str,
        prospect: Dict[str, Any],
        *,
        actor_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build audit event dict — does not persist."""
        event = build_audit_event(
            event_type=event_type,
            prospect_id=prospect.get("prospect_id"),
            run_id=prospect.get("discovery_run_id"),
            campaign_id=prospect.get("campaign_id"),
            job_id=prospect.get("discovery_job_id"),
            provider=prospect.get("provider"),
            actor_id=actor_id,
            details=prepare_audit_payload(details),
        )
        return event.model_dump(mode="json")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @staticmethod
    async def create_prospect(
        request: CreateProspectRequest,
        *,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Create prospect record. Returns (prospect_doc, prepared_audit_event).
        Does not write audit logs.
        """
        errors = await DiscoveryProspectService.validate_prospect(
            request, extra_fields=extra_fields
        )
        if errors:
            raise DiscoveryProspectError("VALIDATION_FAILED", "; ".join(errors))

        run = await DiscoveryRunService.get_run(request.discovery_run_id)
        campaign_id = request.campaign_id or (run.get("campaign_id") if run else None)

        # Idempotency: same provider + run + content_hash
        db = database.get_db()
        existing = await db[DISCOVERY_PROSPECTS_COLLECTION].find_one(
            {
                "discovery_run_id": request.discovery_run_id,
                "provider": request.provider.value,
                "content_hash": request.content_hash.strip().lower(),
            },
            {"_id": 0},
        )
        if existing:
            raise DiscoveryProspectError(
                "DUPLICATE_CONTENT_HASH",
                "Prospect with same content_hash already exists for this run",
            )

        now = datetime.now(timezone.utc)
        lineage = DiscoveryProspectService.append_origin_lineage(
            [],
            provider=request.provider.value,
            provider_reference=request.provider_reference,
            discovery_run_id=request.discovery_run_id,
            campaign_id=campaign_id,
            source_url=request.source_url,
            content_hash=request.content_hash.strip().lower(),
            discovered_at=now,
            discovery_job_id=request.discovery_job_id,
        )
        quality_inputs = QualityInputs(
            email=request.email,
            phone=request.phone,
            company_name=request.company_name,
            website=request.website,
            source_url=request.source_url,
            provider_reference=request.provider_reference,
            business_type=request.business_type,
            landlord_type=request.landlord_type,
            location=request.location,
            lawful_basis=request.lawful_basis,
            marketing_consent=request.marketing_consent,
            provider_confidence=request.provider_confidence,
            risk_flags=list(request.risk_flags),
            origin_lineage=lineage,
        )
        platform_score = DiscoveryQualityService.compute_platform_quality_score(quality_inputs)
        review_priority = DiscoveryQualityService.calculate_review_priority(
            platform_score,
            inputs=quality_inputs,
        )

        doc = DiscoveryProspectDocument(
            prospect_id=generate_prospect_id(),
            campaign_id=campaign_id,
            discovery_run_id=request.discovery_run_id,
            discovery_job_id=request.discovery_job_id,
            provider=request.provider,
            provider_reference=request.provider_reference,
            content_hash=request.content_hash.strip().lower(),
            provider_confidence=request.provider_confidence,
            platform_quality_score=platform_score,
            review_priority=review_priority,
            origin_lineage=lineage,
            source_url=request.source_url,
            source_type=request.source_type,
            company_name=request.company_name,
            contact_name=request.contact_name,
            email=normalise_email(request.email) if request.email else None,
            phone=request.phone,
            website=request.website,
            location=request.location,
            business_type=request.business_type,
            landlord_type=request.landlord_type,
            lawful_basis=request.lawful_basis,
            marketing_consent=request.marketing_consent,
            review_status=request.review_status,
            raw_payload_reference=request.raw_payload_reference,
            risk_flags=request.risk_flags,
            tenant_id=request.tenant_id,
            created_at=now,
            updated_at=now,
        )
        payload = doc.model_dump(mode="json")
        await db[DISCOVERY_PROSPECTS_COLLECTION].insert_one(payload)

        audit_event = DiscoveryProspectService._prepare_audit_event_for_prospect(
            "PROSPECT_DISCOVERED",
            payload,
            details={"review_status": doc.review_status.value},
        )
        logger.info("Discovery prospect created prospect_id=%s", doc.prospect_id)
        return {k: v for k, v in payload.items() if k != "_id"}, audit_event

    @staticmethod
    async def get_prospect(prospect_id: str) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        return await db[DISCOVERY_PROSPECTS_COLLECTION].find_one(
            {"prospect_id": prospect_id},
            {"_id": 0},
        )

    @staticmethod
    async def list_prospects(
        *,
        discovery_run_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        review_status: Optional[DiscoveryReviewStatus] = None,
        provider: Optional[DiscoveryProviderId] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        db = database.get_db()
        query: Dict[str, Any] = {"tenant_id": PLATFORM_TENANT_ID}
        if discovery_run_id:
            query["discovery_run_id"] = discovery_run_id
        if campaign_id:
            query["campaign_id"] = campaign_id
        if review_status is not None:
            query["review_status"] = review_status.value
        if provider is not None:
            query["provider"] = provider.value
        cursor = (
            db[DISCOVERY_PROSPECTS_COLLECTION]
            .find(query, {"_id": 0})
            .sort([("review_priority", -1), ("created_at", -1)])
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    @staticmethod
    async def update_prospect(
        prospect_id: str,
        request: UpdateProspectRequest,
        *,
        actor_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        existing = await DiscoveryProspectService.get_prospect(prospect_id)
        if not existing:
            raise DiscoveryProspectError("PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found")
        DiscoveryProspectService._assert_not_terminal(existing)

        updates: Dict[str, Any] = {}
        data = request.model_dump(exclude_unset=True)
        if "raw_payload_reference" in data:
            ref_errors = DiscoveryProspectService.validate_raw_payload_reference(
                data["raw_payload_reference"]
            )
            if ref_errors:
                raise DiscoveryProspectError("VALIDATION_FAILED", "; ".join(ref_errors))

        for key, value in data.items():
            if value is not None:
                updates[key] = value
        if "email" in updates and updates["email"]:
            updates["email"] = normalise_email(updates["email"])

        if not updates:
            return existing, {}

        # Recompute scores if relevant fields changed
        merged = {**existing, **updates}
        quality_inputs = DiscoveryQualityService.quality_inputs_from_mapping(merged)
        platform_score = DiscoveryQualityService.compute_platform_quality_score(quality_inputs)
        updates["platform_quality_score"] = platform_score
        updates["review_priority"] = DiscoveryQualityService.calculate_review_priority(
            platform_score,
            inputs=quality_inputs,
        )
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {"$set": updates},
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None
        audit_event = DiscoveryProspectService._prepare_audit_event_for_prospect(
            "PROSPECT_UPDATED",
            updated,
            actor_id=actor_id,
            details={"fields": list(updates.keys())},
        )
        return updated, audit_event

    @staticmethod
    async def update_review_status(
        prospect_id: str,
        new_status: DiscoveryReviewStatus,
        *,
        actor_id: Optional[str] = None,
        override_reason: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        existing = await DiscoveryProspectService.get_prospect(prospect_id)
        if not existing:
            raise DiscoveryProspectError("PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found")
        DiscoveryProspectService._assert_not_terminal(existing)

        current = DiscoveryReviewStatus(
            existing.get("review_status", DiscoveryReviewStatus.DISCOVERED.value)
        )
        DiscoveryProspectService._validate_review_transition(
            current, new_status, override_reason=override_reason
        )

        updates: Dict[str, Any] = {
            "review_status": new_status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if override_reason:
            updates["duplicate_override_reason"] = override_reason.strip()

        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {"$set": updates},
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None
        event_type = (
            "PROSPECT_ARCHIVED"
            if new_status == DiscoveryReviewStatus.ARCHIVED
            else "PROSPECT_APPROVED"
            if new_status == DiscoveryReviewStatus.APPROVED
            else "PROSPECT_REJECTED"
            if new_status == DiscoveryReviewStatus.REJECTED
            else "PROSPECT_UPDATED"
        )
        audit_event = DiscoveryProspectService._prepare_audit_event_for_prospect(
            event_type,
            updated,
            actor_id=actor_id,
            details={"from": current.value, "to": new_status.value},
        )
        return updated, audit_event

    @staticmethod
    async def archive_prospect(
        prospect_id: str,
        *,
        actor_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return await DiscoveryProspectService.update_review_status(
            prospect_id,
            DiscoveryReviewStatus.ARCHIVED,
            actor_id=actor_id,
        )

    @staticmethod
    async def mark_imported(
        prospect_id: str,
        imported_lead_id: str,
        *,
        imported_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Set prospect to imported after successful CRM lead creation.
        Only DiscoveryImportService should call this path.
        """
        existing = await DiscoveryProspectService.get_prospect(prospect_id)
        if not existing:
            raise DiscoveryProspectError(
                "PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found"
            )
        if existing.get("imported_lead_id"):
            return existing
        if existing.get("review_status") != DiscoveryReviewStatus.APPROVED.value:
            raise DiscoveryProspectError(
                "INVALID_STATUS",
                "import completion requires review_status=approved",
            )
        now = imported_at or datetime.now(timezone.utc)
        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {
                "$set": {
                    "review_status": DiscoveryReviewStatus.IMPORTED.value,
                    "imported_lead_id": imported_lead_id,
                    "imported_timestamp": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            },
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None
        return updated

    @staticmethod
    async def mark_erasure_requested(
        prospect_id: str,
        *,
        actor_id: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        existing = await DiscoveryProspectService.get_prospect(prospect_id)
        if not existing:
            raise DiscoveryProspectError("PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found")
        if existing.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
            raise DiscoveryProspectError("ERASED", "Prospect already erased")

        now = datetime.now(timezone.utc)
        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {"$set": {"erasure_requested_at": now.isoformat(), "updated_at": now.isoformat()}},
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None
        audit_event = DiscoveryProspectService._prepare_audit_event_for_prospect(
            "PROSPECT_ERASURE_REQUESTED",
            updated,
            actor_id=actor_id,
            details={"reason_code": reason_code},
        )
        return updated, audit_event

    @staticmethod
    async def mark_erased(
        prospect_id: str,
        *,
        actor_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        existing = await DiscoveryProspectService.get_prospect(prospect_id)
        if not existing:
            raise DiscoveryProspectError("PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found")
        if existing.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
            raise DiscoveryProspectError("ERASED", "Prospect already erased")

        now = datetime.now(timezone.utc)
        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {
                "$set": {
                    "erasure_status": DiscoveryErasureStatus.ERASED.value,
                    "email": None,
                    "phone": None,
                    "contact_name": "[ERASED]",
                    "company_name": "[ERASED]",
                    "website": None,
                    "raw_payload_reference": None,
                    "updated_at": now.isoformat(),
                }
            },
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None
        audit_event = DiscoveryProspectService._prepare_audit_event_for_prospect(
            "PROSPECT_ERASED",
            updated,
            actor_id=actor_id,
        )
        return updated, audit_event

    @staticmethod
    def verify_content_hash_matches_fields(
        content_hash: str,
        fields: Dict[str, Any],
    ) -> bool:
        """Verify content_hash matches canonical field set (idempotency aid)."""
        expected = compute_content_hash(fields)
        return expected == content_hash.strip().lower()
