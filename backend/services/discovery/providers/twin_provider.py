"""
Twin discovery provider — Stage W.

Twin export/webhook ingest into discovery_prospects only.
No LeadService, DiscoveryImportService, outreach, nurture, or CRM writes.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

from services.discovery.discovery_audit_service import DiscoveryAuditService
from services.discovery.discovery_duplicate_service import (
    DiscoveryDuplicateService,
    DuplicateClassification,
)
from services.discovery.discovery_hashing import (
    build_discovery_idempotency_key,
    compute_content_hash,
    normalize_provider_reference,
)
from services.discovery.discovery_job_service import DiscoveryJobService
from services.discovery.discovery_models import (
    DiscoveryBusinessType,
    DiscoveryJobStatus,
    DiscoveryLandlordType,
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
    DiscoveryRunStatus,
    DiscoverySourceType,
    ProspectLocation,
)
from services.discovery.discovery_payload_store import (
    InMemoryRawPayloadStore,
    RawPayloadStore,
)
from services.discovery.discovery_prospect_service import (
    CreateProspectRequest,
    DiscoveryProspectError,
    DiscoveryProspectService,
)
from services.discovery.discovery_run_service import DiscoveryRunService
from services.discovery.providers.discovery_provider_protocol import (
    PROHIBITED_PROVIDER_CAPABILITIES,
    CanonicalProspect,
    IngestContext,
    IngestSource,
    ProviderCapabilities,
    RowError,
    ValidationResult,
    build_idempotency_key,
    validate_provider_capabilities,
)

ADAPTER_VERSION = "1.0.0"
PROVIDER_ID = DiscoveryProviderId.TWIN

INLINE_PAYLOAD_KEYS = frozenset({"raw_payload", "raw_row", "csv_row", "html_payload"})

IDENTITY_FIELDS = frozenset({"email", "phone", "company_name", "website"})

# Canonical Discovery fields Twin may populate (Architecture + Stage W mapping rules)
TWIN_CANONICAL_FIELDS = frozenset(
    {
        "email",
        "phone",
        "company_name",
        "website",
        "source_url",
        "contact_name",
        "business_type",
        "landlord_type",
        "provider_reference",
        "provider_confidence",
        "marketing_consent",
        "lawful_basis",
        "city",
        "region",
        "postcode",
        "country",
    }
)

# Twin export aliases → canonical field names
TWIN_FIELD_ALIASES: Dict[str, str] = {
    "twin_id": "provider_reference",
    "external_id": "provider_reference",
    "company": "company_name",
    "organisation": "company_name",
    "organization": "company_name",
    "contact": "contact_name",
    "full_name": "contact_name",
    "name": "contact_name",
    "url": "website",
    "web": "website",
    "linkedin_url": "source_url",
    "profile_url": "source_url",
    "confidence": "provider_confidence",
    "confidence_score": "provider_confidence",
    "score": "provider_confidence",
    "post_code": "postcode",
    "zip": "postcode",
}

# Twin-specific fields — raw payload only, never on DiscoveryProspectDocument
TWIN_RAW_PAYLOAD_FIELDS = frozenset(
    {
        "workflow_id",
        "workflow_name",
        "twin_campaign_id",
        "twin_sequence_id",
        "enrichment_data",
        "enrichment_tags",
        "twin_metadata",
        "export_batch_id",
        "export_id",
    }
)

URL_PATTERN = re.compile(r"^https?://", re.I)
PROVIDER_REF_INVALID = re.compile(r"[\x00-\x1f\x7f]")
TRUTHY_VALUES = frozenset({"1", "true", "yes", "y", "on"})


class TwinProviderError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class TwinIngestResult:
    discovery_run_id: str
    provider: str
    total_rows: int
    accepted_count: int
    rejected_count: int
    duplicate_rows: int
    discovery_job_id: Optional[str] = None
    created_prospect_ids: List[str] = field(default_factory=list)
    errors: List[RowError] = field(default_factory=list)

    @property
    def accepted_rows(self) -> int:
        return self.accepted_count

    @property
    def rejected_rows(self) -> int:
        return self.rejected_count


def _normalize_twin_key(key: str) -> str:
    norm = str(key).strip().lower().replace(" ", "_").replace("-", "_")
    return TWIN_FIELD_ALIASES.get(norm, norm)


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None or str(value).strip() == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUTHY_VALUES


def _parse_lawful_basis(value: Any) -> Optional[DiscoveryLawfulBasis]:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().lower()
    for basis in DiscoveryLawfulBasis:
        if basis.value == text:
            return basis
    return None


def _parse_business_type(value: Any) -> Optional[DiscoveryBusinessType]:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().lower()
    for bt in DiscoveryBusinessType:
        if bt.value == text:
            return bt
    return None


def _parse_landlord_type(value: Any) -> Optional[DiscoveryLandlordType]:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().lower()
    for lt in DiscoveryLandlordType:
        if lt.value == text:
            return lt
    return None


def _valid_source_url(url: str) -> bool:
    parsed = urlparse(str(url).strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _coerce_row(raw: Mapping[str, Any]) -> Dict[str, str]:
    row: Dict[str, str] = {}
    for key, value in raw.items():
        if key is None:
            continue
        norm = _normalize_twin_key(str(key))
        if value is None:
            row[norm] = ""
        elif isinstance(value, (dict, list)):
            row[norm] = ""  # nested Twin data stays in original_row payload
        else:
            row[norm] = str(value).strip()
    return row


def _split_twin_fields(
    row: Mapping[str, str],
) -> Tuple[Dict[str, str], Dict[str, Any], Dict[str, Any]]:
    """Return (mapped canonical strings, raw-only extras, original snapshot)."""
    mapped: Dict[str, str] = {}
    extras: Dict[str, Any] = {}
    original: Dict[str, Any] = dict(row)

    for key, value in row.items():
        if key in TWIN_CANONICAL_FIELDS:
            mapped[key] = value
        elif key in TWIN_RAW_PAYLOAD_FIELDS or key not in TWIN_CANONICAL_FIELDS:
            if value:
                extras[key] = value

    for field_name in TWIN_CANONICAL_FIELDS:
        mapped.setdefault(field_name, "")

    return mapped, extras, original


def _parse_twin_records(payload: Any) -> Tuple[List[Dict[str, str]], List[str]]:
    errors: List[str] = []
    if payload is None:
        return [], ["Twin ingest payload is required"]

    records_raw: List[Any]
    if isinstance(payload, list):
        records_raw = payload
    elif isinstance(payload, dict):
        records_raw = payload.get("records") or payload.get("prospects") or []
        if not isinstance(records_raw, list):
            return [], ["Twin payload.records must be a list"]
    else:
        return [], ["Twin payload must be a list or object with records[]"]

    if not records_raw:
        return [], ["Twin export contains no records"]

    rows: List[Dict[str, str]] = []
    for item in records_raw:
        if not isinstance(item, dict):
            errors.append("each Twin record must be an object")
            continue
        rows.append(_coerce_row(item))

    if errors:
        return [], errors
    return rows, []


class TwinProvider:
    """Twin provider adapter — discovery prospects only (Stage W)."""

    def __init__(self, payload_store: Optional[RawPayloadStore] = None) -> None:
        self._payload_store = payload_store or InMemoryRawPayloadStore()

    @property
    def provider_id(self) -> str:
        return PROVIDER_ID.value

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    @property
    def supports_async(self) -> bool:
        return True

    @property
    def supports_enrichment(self) -> bool:
        return False

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_async=True,
            supports_enrichment=False,
            supports_cost_tracking=True,
            supports_webhook=True,
            max_batch_size=50000,
            prohibited_capabilities=PROHIBITED_PROVIDER_CAPABILITIES,
        )

    def validate(self, raw_row: Dict[str, Any], context: IngestContext) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        for key in INLINE_PAYLOAD_KEYS:
            if key in raw_row and raw_row[key]:
                errors.append(f"inline field '{key}' is not permitted")

        row = _coerce_row(raw_row)
        mapped, _extras, _original = _split_twin_fields(row)

        has_identity = any(mapped.get(c, "").strip() for c in IDENTITY_FIELDS)
        if not has_identity:
            errors.append(
                "at least one of email, phone, company_name, or website is required"
            )

        row_basis = _parse_lawful_basis(mapped.get("lawful_basis"))
        effective_basis = row_basis or context.lawful_basis
        if effective_basis is None or effective_basis == DiscoveryLawfulBasis.UNKNOWN:
            errors.append("lawful_basis is required and must not be unknown")

        marketing_consent = _parse_bool(mapped.get("marketing_consent"), default=False)
        if marketing_consent and effective_basis != DiscoveryLawfulBasis.CONSENT:
            errors.append("marketing_consent=true requires lawful_basis=consent")

        if mapped.get("source_url") and not _valid_source_url(mapped["source_url"]):
            errors.append("source_url is malformed; must be http(s) URL")

        if mapped.get("business_type"):
            if _parse_business_type(mapped["business_type"]) is None:
                errors.append(f"invalid business_type '{mapped['business_type']}'")

        if mapped.get("landlord_type"):
            if _parse_landlord_type(mapped["landlord_type"]) is None:
                errors.append(f"invalid landlord_type '{mapped['landlord_type']}'")

        provider_ref = mapped.get("provider_reference") or None
        if provider_ref:
            if PROVIDER_REF_INVALID.search(provider_ref):
                errors.append("provider_reference contains invalid characters")
            ref_errors = DiscoveryProspectService.validate_provider_reference(
                PROVIDER_ID,
                provider_ref,
            )
            errors.extend(ref_errors)

        if mapped.get("provider_confidence"):
            try:
                conf = int(str(mapped["provider_confidence"]).strip())
                if conf < 0 or conf > 100:
                    errors.append("provider_confidence must be between 0 and 100")
            except ValueError:
                errors.append("provider_confidence must be an integer")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def map_to_canonical(
        self, raw_row: Dict[str, Any], context: IngestContext
    ) -> CanonicalProspect:
        row = _coerce_row(raw_row)
        mapped, _extras, _original = _split_twin_fields(row)
        row_basis = _parse_lawful_basis(mapped.get("lawful_basis"))
        effective_basis = row_basis or context.lawful_basis

        business_type = _parse_business_type(mapped.get("business_type"))
        landlord_type = _parse_landlord_type(mapped.get("landlord_type"))

        provider_confidence = 50
        if mapped.get("provider_confidence"):
            provider_confidence = int(str(mapped["provider_confidence"]).strip())

        location_parts = {
            "city": mapped.get("city") or None,
            "region": mapped.get("region") or None,
            "postcode": mapped.get("postcode") or None,
            "country": mapped.get("country") or None,
        }
        provider_extensions: Dict[str, Any] = {}
        if any(location_parts.values()):
            provider_extensions["location"] = location_parts

        provider_reference = mapped.get("provider_reference") or None
        if provider_reference and not provider_reference.startswith("twin:"):
            provider_reference = f"twin:{provider_reference.lstrip(':')}"

        return CanonicalProspect(
            company_name=mapped.get("company_name") or None,
            contact_name=mapped.get("contact_name") or None,
            email=mapped.get("email") or None,
            phone=mapped.get("phone") or None,
            website=mapped.get("website") or None,
            source_url=mapped.get("source_url") or None,
            business_type=business_type.value if business_type else None,
            landlord_type=landlord_type.value if landlord_type else None,
            provider_confidence=provider_confidence,
            marketing_consent=_parse_bool(mapped.get("marketing_consent"), default=False),
            lawful_basis=effective_basis,
            provider_reference=provider_reference,
            provider_extensions=provider_extensions,
        )

    def idempotency_key(
        self, canonical: CanonicalProspect, context: IngestContext
    ) -> str:
        hash_fields = _canonical_hash_fields(canonical, context)
        content_hash = compute_content_hash(hash_fields)
        return build_idempotency_key(
            self.provider_id,
            canonical.provider_reference,
            content_hash,
        )

    def ingest(self, source: IngestSource, context: IngestContext) -> TwinIngestResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.ingest_async(source, context))
        raise TwinProviderError(
            "ASYNC_CONTEXT",
            "ingest() cannot run inside an active event loop; use ingest_async()",
        )

    async def ingest_async(
        self, source: IngestSource, context: IngestContext
    ) -> TwinIngestResult:
        return await self._ingest_impl(source, context)

    async def _ingest_impl(
        self, source: IngestSource, context: IngestContext
    ) -> TwinIngestResult:
        cap_errors = validate_provider_capabilities(self.capabilities())
        if cap_errors:
            raise TwinProviderError("CAPABILITY_VIOLATION", "; ".join(cap_errors))

        run_errors = await _validate_run_for_ingest(context)
        if run_errors:
            raise TwinProviderError("RUN_VALIDATION_FAILED", "; ".join(run_errors))

        rows, parse_errors = _parse_twin_records(source.payload)
        if parse_errors:
            raise TwinProviderError("INVALID_PAYLOAD", "; ".join(parse_errors))

        if len(rows) > self.capabilities().max_batch_size:
            raise TwinProviderError(
                "BATCH_TOO_LARGE",
                f"Twin export exceeds max batch size {self.capabilities().max_batch_size}",
            )

        job = await DiscoveryJobService.create_job_record(
            run_id=context.discovery_run_id,
            provider=PROVIDER_ID,
            supports_async=True,
            status=DiscoveryJobStatus.RUNNING,
        )
        job_id = job["job_id"]

        result = TwinIngestResult(
            discovery_run_id=context.discovery_run_id,
            provider=self.provider_id,
            total_rows=len(rows),
            accepted_count=0,
            rejected_count=0,
            duplicate_rows=0,
            discovery_job_id=job_id,
        )

        seen_idempotency: Set[str] = set()
        run = await DiscoveryRunService.get_run(context.discovery_run_id)
        campaign_id = context.discovery_campaign_id or (
            run.get("campaign_id") if run else None
        )

        try:
            for row_index, raw_row in enumerate(rows, start=1):
                validation = self.validate(raw_row, context)
                if not validation.valid:
                    result.rejected_count += 1
                    result.errors.append(
                        RowError(row_index=row_index, errors=list(validation.errors))
                    )
                    continue

                canonical = self.map_to_canonical(raw_row, context)
                mapped, extras, original = _split_twin_fields(_coerce_row(raw_row))
                hash_fields = _canonical_hash_fields(
                    canonical, context, campaign_id=campaign_id
                )
                content_hash = compute_content_hash(hash_fields)
                idem_key = build_discovery_idempotency_key(
                    self.provider_id,
                    canonical.provider_reference,
                    content_hash,
                )

                if idem_key in seen_idempotency:
                    result.rejected_count += 1
                    result.errors.append(
                        RowError(
                            row_index=row_index,
                            errors=["duplicate record in batch (same idempotency key)"],
                        )
                    )
                    continue
                seen_idempotency.add(idem_key)

                payload_doc = {
                    "canonical_row": mapped,
                    "twin_extras": extras,
                    "original_record": original,
                }
                raw_payload_reference = self._payload_store.put(
                    payload_doc,
                    metadata={
                        "provider": self.provider_id,
                        "discovery_run_id": context.discovery_run_id,
                        "discovery_job_id": job_id,
                        "content_hash": content_hash,
                    },
                )

                location = None
                loc_data = canonical.provider_extensions.get("location")
                if loc_data:
                    location = ProspectLocation(**loc_data)

                business_type = DiscoveryBusinessType.UNKNOWN
                if canonical.business_type:
                    business_type = DiscoveryBusinessType(canonical.business_type)
                landlord_type = DiscoveryLandlordType.UNKNOWN
                if canonical.landlord_type:
                    landlord_type = DiscoveryLandlordType(canonical.landlord_type)

                provider_ref = normalize_provider_reference(
                    self.provider_id,
                    canonical.provider_reference,
                )
                if provider_ref.endswith(":-") and not canonical.provider_reference:
                    provider_ref = f"{self.provider_id}:record-{row_index}"

                request = CreateProspectRequest(
                    discovery_run_id=context.discovery_run_id,
                    campaign_id=campaign_id,
                    discovery_job_id=job_id,
                    provider=PROVIDER_ID,
                    content_hash=content_hash,
                    source_type=DiscoverySourceType.API,
                    lawful_basis=canonical.lawful_basis or context.lawful_basis,
                    provider_reference=provider_ref,
                    provider_confidence=canonical.provider_confidence,
                    marketing_consent=canonical.marketing_consent,
                    review_status=DiscoveryReviewStatus.NEEDS_REVIEW,
                    source_url=canonical.source_url,
                    company_name=canonical.company_name,
                    contact_name=canonical.contact_name,
                    email=canonical.email,
                    phone=canonical.phone,
                    website=canonical.website,
                    location=location,
                    business_type=business_type,
                    landlord_type=landlord_type,
                    raw_payload_reference=raw_payload_reference,
                    tenant_id=context.tenant_id,
                )

                try:
                    prospect, _prepared = await DiscoveryProspectService.create_prospect(
                        request
                    )
                except DiscoveryProspectError as exc:
                    if exc.code == "DUPLICATE_CONTENT_HASH":
                        continue
                    result.rejected_count += 1
                    result.errors.append(
                        RowError(row_index=row_index, errors=[exc.message])
                    )
                    continue

                await DiscoveryAuditService.create_audit_event(
                    event_type="PROSPECT_DISCOVERED",
                    prospect_id=prospect["prospect_id"],
                    run_id=context.discovery_run_id,
                    campaign_id=campaign_id,
                    job_id=job_id,
                    provider=self.provider_id,
                    actor_id=context.actor_id,
                    actor_email=context.actor_email,
                    content_hash=content_hash,
                    details={"review_status": prospect.get("review_status")},
                )

                dup_result = await _apply_duplicate_precheck(
                    prospect,
                    actor_id=context.actor_id,
                )
                if dup_result is not None:
                    result.duplicate_rows += 1

                result.accepted_count += 1
                result.created_prospect_ids.append(prospect["prospect_id"])

            await DiscoveryJobService.update_job_status(
                job_id,
                DiscoveryJobStatus.COMPLETED,
            )
        except Exception:
            await DiscoveryJobService.update_job_status(
                job_id,
                DiscoveryJobStatus.FAILED,
                error_message="Twin ingest failed",
            )
            raise

        return result


def _canonical_hash_fields(
    canonical: CanonicalProspect,
    context: IngestContext,
    *,
    campaign_id: Optional[str] = None,
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "provider": PROVIDER_ID.value,
        "provider_reference": canonical.provider_reference,
        "source_url": canonical.source_url,
        "company_name": canonical.company_name,
        "contact_name": canonical.contact_name,
        "email": canonical.email,
        "phone": canonical.phone,
        "website": canonical.website,
        "business_type": canonical.business_type,
        "landlord_type": canonical.landlord_type,
        "campaign_id": campaign_id or context.discovery_campaign_id,
        "discovery_run_id": context.discovery_run_id,
    }
    loc = canonical.provider_extensions.get("location")
    if loc:
        fields["location"] = loc
    return fields


async def _validate_run_for_ingest(context: IngestContext) -> List[str]:
    errors: List[str] = []

    run = await DiscoveryRunService.get_run(context.discovery_run_id)
    if not run:
        errors.append(f"discovery_run_id {context.discovery_run_id} not found")
        return errors

    if run.get("provider") != PROVIDER_ID.value:
        errors.append("discovery run provider must be twin")

    status = run.get("status", DiscoveryRunStatus.PROCESSING.value)
    if status != DiscoveryRunStatus.PROCESSING.value:
        errors.append(f"run status '{status}' does not allow ingest")

    if not run.get("is_ad_hoc") and not run.get("campaign_id") and not context.discovery_campaign_id:
        errors.append("campaign_id is required unless run is ad_hoc")

    if context.discovery_campaign_id and run.get("campaign_id"):
        if context.discovery_campaign_id != run.get("campaign_id"):
            errors.append("context campaign_id must match discovery run")

    return errors


async def _apply_duplicate_precheck(
    prospect: Dict[str, Any],
    *,
    actor_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    candidates = await DiscoveryDuplicateService.find_duplicate_candidates(
        prospect, exclude_prospect_id=prospect.get("prospect_id")
    )
    classification = DiscoveryDuplicateService.classify_duplicate(prospect, candidates)
    if classification.classification == DuplicateClassification.NONE:
        return None

    await DiscoveryDuplicateService.apply_duplicate_status(
        prospect["prospect_id"],
        classification,
        actor_id=actor_id,
    )
    snapshot = DiscoveryAuditService.freeze_duplicate_evidence_snapshot(
        classification.to_dict()
    )
    await DiscoveryAuditService.create_audit_event(
        event_type="DUPLICATE_DETECTED",
        prospect_id=prospect["prospect_id"],
        run_id=prospect.get("discovery_run_id"),
        campaign_id=prospect.get("campaign_id"),
        provider=prospect.get("provider"),
        actor_id=actor_id,
        duplicate_evidence_snapshot=snapshot,
        content_hash=prospect.get("content_hash"),
        details={"review_status": prospect.get("review_status")},
    )
    return classification.to_dict()
