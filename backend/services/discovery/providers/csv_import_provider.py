"""
CSV discovery provider — Stage M.

Provider-neutral CSV ingest into discovery_prospects only.
No routes, UI, LeadService, import service, or notifications.
"""
from __future__ import annotations

import asyncio
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
from services.discovery.discovery_models import (
    DiscoveryBusinessType,
    DiscoveryLandlordType,
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
    DiscoveryRunStatus,
    DiscoverySourceType,
    ProspectLocation,
    RunAttestation,
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
PROVIDER_ID = DiscoveryProviderId.CSV

INLINE_PAYLOAD_KEYS = frozenset({"raw_payload", "raw_row", "csv_row", "html_payload"})

CANONICAL_CSV_COLUMNS = frozenset(
    {
        "email",
        "phone",
        "company_name",
        "website",
        "contact_name",
        "source_url",
        "business_type",
        "landlord_type",
        "city",
        "region",
        "postcode",
        "country",
        "tags",
        "notes",
        "marketing_consent",
        "lawful_basis",
        "consent_evidence",
        "provider_reference",
        "provider_confidence",
    }
)

IDENTITY_COLUMNS = frozenset({"email", "phone", "company_name", "website"})

# Documented safe header aliases — see DISCOVERY_PROVIDER_PROTOCOL.md §8
DOCUMENTED_HEADER_ALIASES: Dict[str, str] = {
    "company": "company_name",
    "organisation": "company_name",
    "organization": "company_name",
    "e_mail": "email",
    "e-mail": "email",
    "tel": "phone",
    "telephone": "phone",
    "mobile": "phone",
    "url": "website",
    "web": "website",
    "post_code": "postcode",
    "zip": "postcode",
}

RAW_PAYLOAD_ONLY_COLUMNS = frozenset({"tags", "notes", "consent_evidence"})

URL_PATTERN = re.compile(r"^https?://", re.I)
PROVIDER_REF_INVALID = re.compile(r"[\x00-\x1f\x7f]")

TRUTHY_VALUES = frozenset({"1", "true", "yes", "y", "on"})


class CsvImportProviderError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class CsvIngestResult:
    discovery_run_id: str
    provider: str
    total_rows: int
    accepted_count: int
    rejected_count: int
    duplicate_rows: int
    created_prospect_ids: List[str] = field(default_factory=list)
    errors: List[RowError] = field(default_factory=list)

    @property
    def accepted_rows(self) -> int:
        return self.accepted_count

    @property
    def rejected_rows(self) -> int:
        return self.rejected_count

    @property
    def rejected_row_errors(self) -> List[RowError]:
        return self.errors

    @property
    def run_id(self) -> str:
        return self.discovery_run_id


def _normalize_header(header: str) -> str:
    key = header.strip().lower().replace(" ", "_").replace("-", "_")
    return DOCUMENTED_HEADER_ALIASES.get(key, key)


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in TRUTHY_VALUES


def _parse_lawful_basis(value: Optional[str]) -> Optional[DiscoveryLawfulBasis]:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().lower()
    for basis in DiscoveryLawfulBasis:
        if basis.value == text:
            return basis
    return None


def _parse_business_type(value: Optional[str]) -> Optional[DiscoveryBusinessType]:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().lower()
    for bt in DiscoveryBusinessType:
        if bt.value == text:
            return bt
    return None


def _parse_landlord_type(value: Optional[str]) -> Optional[DiscoveryLandlordType]:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().lower()
    for lt in DiscoveryLandlordType:
        if lt.value == text:
            return lt
    return None


def _valid_source_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _validate_headers(headers: Sequence[str]) -> Tuple[List[str], List[str]]:
    """Return (canonical_headers, errors)."""
    errors: List[str] = []
    if not headers:
        return [], ["CSV must include a header row"]

    canonical: List[str] = []
    seen: Set[str] = set()
    for raw in headers:
        norm = _normalize_header(raw)
        if norm in seen:
            continue
        seen.add(norm)
        canonical.append(norm)

    if not any(col in canonical for col in IDENTITY_COLUMNS):
        errors.append(
            "CSV headers must include at least one identity column: "
            "email, phone, company_name, or website"
        )
    return canonical, errors


def _split_row_fields(
    row: Mapping[str, str],
    canonical_headers: Sequence[str],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Split mapped row into prospect-mapped fields and raw-payload-only extras."""
    mapped: Dict[str, str] = {}
    extras: Dict[str, str] = {}
    for key, value in row.items():
        norm_key = _normalize_header(key)
        if norm_key in CANONICAL_CSV_COLUMNS:
            if norm_key in RAW_PAYLOAD_ONLY_COLUMNS:
                if value and str(value).strip():
                    extras[norm_key] = str(value).strip()
            else:
                mapped[norm_key] = str(value).strip() if value is not None else ""
        else:
            if value and str(value).strip():
                extras[norm_key] = str(value).strip()
    for col in canonical_headers:
        if col not in mapped and col not in RAW_PAYLOAD_ONLY_COLUMNS:
            mapped.setdefault(col, "")
    return mapped, extras


class CSVImportProvider:
    """CSV provider adapter — discovery prospects only."""

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
        return False

    @property
    def supports_enrichment(self) -> bool:
        return False

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_async=False,
            supports_enrichment=False,
            supports_cost_tracking=False,
            supports_webhook=False,
            max_batch_size=2000,
            prohibited_capabilities=PROHIBITED_PROVIDER_CAPABILITIES,
        )

    def validate(self, raw_row: Dict[str, Any], context: IngestContext) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        for key in INLINE_PAYLOAD_KEYS:
            if key in raw_row and raw_row[key]:
                errors.append(f"inline field '{key}' is not permitted")

        mapped, _extras = _split_row_fields(
            {str(k): str(v) if v is not None else "" for k, v in raw_row.items()},
            CANONICAL_CSV_COLUMNS,
        )

        has_identity = any(mapped.get(c, "").strip() for c in IDENTITY_COLUMNS)
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

        attestation_errors = _validate_run_attestation(context)
        errors.extend(attestation_errors)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def map_to_canonical(
        self, raw_row: Dict[str, Any], context: IngestContext
    ) -> CanonicalProspect:
        mapped, _extras = _split_row_fields(
            {str(k): str(v) if v is not None else "" for k, v in raw_row.items()},
            CANONICAL_CSV_COLUMNS,
        )
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
        if any(location_parts.values()):
            provider_extensions = {"location": location_parts}
        else:
            provider_extensions = {}

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
            provider_reference=mapped.get("provider_reference") or None,
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

    def ingest(self, source: IngestSource, context: IngestContext) -> CsvIngestResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.ingest_async(source, context))
        raise CsvImportProviderError(
            "ASYNC_CONTEXT",
            "ingest() cannot run inside an active event loop; use ingest_async()",
        )

    async def ingest_async(
        self, source: IngestSource, context: IngestContext
    ) -> CsvIngestResult:
        return await self._ingest_impl(source, context)

    async def _ingest_impl(
        self, source: IngestSource, context: IngestContext
    ) -> CsvIngestResult:
        cap_errors = validate_provider_capabilities(self.capabilities())
        if cap_errors:
            raise CsvImportProviderError("CAPABILITY_VIOLATION", "; ".join(cap_errors))

        run_errors = await _validate_run_for_ingest(context)
        if run_errors:
            raise CsvImportProviderError("RUN_VALIDATION_FAILED", "; ".join(run_errors))

        rows, header_errors = _parse_csv_rows(source.payload)
        if header_errors:
            raise CsvImportProviderError("INVALID_HEADERS", "; ".join(header_errors))

        if len(rows) > self.capabilities().max_batch_size:
            raise CsvImportProviderError(
                "BATCH_TOO_LARGE",
                f"CSV exceeds max batch size {self.capabilities().max_batch_size}",
            )

        result = CsvIngestResult(
            discovery_run_id=context.discovery_run_id,
            provider=self.provider_id,
            total_rows=len(rows),
            accepted_count=0,
            rejected_count=0,
            duplicate_rows=0,
        )

        seen_idempotency: Set[str] = set()
        run = await DiscoveryRunService.get_run(context.discovery_run_id)
        campaign_id = context.discovery_campaign_id or (
            run.get("campaign_id") if run else None
        )

        for row_index, raw_row in enumerate(rows, start=1):
            validation = self.validate(raw_row, context)
            if not validation.valid:
                result.rejected_count += 1
                result.errors.append(
                    RowError(row_index=row_index, errors=list(validation.errors))
                )
                continue

            canonical = self.map_to_canonical(raw_row, context)
            mapped, extras = _split_row_fields(raw_row, CANONICAL_CSV_COLUMNS)
            hash_fields = _canonical_hash_fields(canonical, context, campaign_id=campaign_id)
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
                        errors=["duplicate row in batch (same idempotency key)"],
                    )
                )
                continue
            seen_idempotency.add(idem_key)

            payload_doc = {
                "canonical_row": mapped,
                "unknown_columns": extras,
                "original_row": dict(raw_row),
            }
            raw_payload_reference = self._payload_store.put(
                payload_doc,
                metadata={
                    "provider": self.provider_id,
                    "discovery_run_id": context.discovery_run_id,
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
                provider_ref = f"{self.provider_id}:row-{row_index}"

            request = CreateProspectRequest(
                discovery_run_id=context.discovery_run_id,
                campaign_id=campaign_id,
                discovery_job_id=context.discovery_job_id,
                provider=PROVIDER_ID,
                content_hash=content_hash,
                source_type=DiscoverySourceType.CSV,
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
                job_id=context.discovery_job_id,
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


def _parse_csv_rows(payload: Any) -> Tuple[List[Dict[str, str]], List[str]]:
    if payload is None:
        return [], ["CSV payload is required"]
    if isinstance(payload, bytes):
        text = payload.decode("utf-8-sig")
    else:
        text = str(payload)
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], ["CSV must include a header row"]

    canonical_headers, header_errors = _validate_headers(list(reader.fieldnames))
    if header_errors:
        return [], header_errors

    rows: List[Dict[str, str]] = []
    for raw in reader:
        row: Dict[str, str] = {}
        for key, value in raw.items():
            if key is None:
                continue
            norm = _normalize_header(key)
            row[norm] = value.strip() if value else ""
        rows.append(row)
    return rows, []


def _validate_run_attestation(context: IngestContext) -> List[str]:
    errors: List[str] = []
    if context.attestation is None:
        errors.append("run attestation is required for CSV ingest")
    elif not isinstance(context.attestation, RunAttestation):
        errors.append("run attestation must be a RunAttestation")
    return errors


async def _validate_run_for_ingest(context: IngestContext) -> List[str]:
    errors: List[str] = []
    errors.extend(_validate_run_attestation(context))

    run = await DiscoveryRunService.get_run(context.discovery_run_id)
    if not run:
        errors.append(f"discovery_run_id {context.discovery_run_id} not found")
        return errors

    if run.get("provider") != PROVIDER_ID.value:
        errors.append("discovery run provider must be csv")

    status = run.get("status", DiscoveryRunStatus.PROCESSING.value)
    if status != DiscoveryRunStatus.PROCESSING.value:
        errors.append(f"run status '{status}' does not allow ingest")

    if not run.get("is_ad_hoc") and not run.get("campaign_id") and not context.discovery_campaign_id:
        errors.append("campaign_id is required unless run is ad_hoc")

    if context.discovery_campaign_id and run.get("campaign_id"):
        if context.discovery_campaign_id != run.get("campaign_id"):
            errors.append("context campaign_id must match discovery run")

    if run.get("attestation") is None and context.attestation is None:
        errors.append("discovery run must include attestation")

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
