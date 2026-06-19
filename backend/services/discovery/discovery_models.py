"""
Discovery Foundation data models — Stage B.

Schema authority: docs/DISCOVERY_FOUNDATION_ARCHITECTURE.md
Tenant: single-tenant platform; tenant_id reserved on all collections (default PLATFORM_TENANT_ID).
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Platform tenant invariant (Option A — reserved field, explicit default)
# ---------------------------------------------------------------------------
PLATFORM_TENANT_ID = "pleerity"
"""
Phase 1 operates as a single platform admin tenant.
All discovery records MUST set tenant_id to PLATFORM_TENANT_ID until multi-tenant SaaS is approved.
"""

# ---------------------------------------------------------------------------
# Collection names
# ---------------------------------------------------------------------------
DISCOVERY_CAMPAIGNS_COLLECTION = "discovery_campaigns"
DISCOVERY_RUNS_COLLECTION = "discovery_runs"
DISCOVERY_JOBS_COLLECTION = "discovery_jobs"
DISCOVERY_PROSPECTS_COLLECTION = "discovery_prospects"
DISCOVERY_AUDIT_LOGS_COLLECTION = "discovery_audit_logs"
DISCOVERY_METRICS_COLLECTION = "discovery_metrics"
DISCOVERY_SUPPRESSION_RECORDS_COLLECTION = "discovery_suppression_records"
PROVIDER_MAPPING_PROFILES_COLLECTION = "provider_mapping_profiles"  # reserved Phase 2

DISCOVERY_SOURCE_METADATA_SCHEMA_VERSION = "1.0.0"

# Fields included in canonical content_hash (ordered, normalised)
CONTENT_HASH_FIELDS = (
    "company_name",
    "contact_name",
    "email",
    "phone",
    "website",
    "business_type",
    "landlord_type",
    "source_url",
)


# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------
def _ts_hex_id(prefix: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{ts}-{uuid.uuid4().hex[:6].upper()}"


def generate_campaign_id() -> str:
    return _ts_hex_id("DCAMP")


def generate_discovery_run_id() -> str:
    return _ts_hex_id("DRUN")


def generate_discovery_job_id() -> str:
    return _ts_hex_id("DJOB")


def generate_prospect_id() -> str:
    return _ts_hex_id("PROSP")


def generate_discovery_audit_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Normalisation helpers (validation only — no persistence side effects)
# ---------------------------------------------------------------------------
def normalise_email(email: Optional[str]) -> Optional[str]:
    if not email or not str(email).strip():
        return None
    return str(email).strip().lower()


def normalise_phone(phone: Optional[str]) -> Optional[str]:
    if not phone or not str(phone).strip():
        return None
    digits = re.sub(r"\D", "", str(phone))
    return digits or None


def email_hash(email: Optional[str]) -> Optional[str]:
    norm = normalise_email(email)
    if not norm:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def phone_hash(phone: Optional[str]) -> Optional[str]:
    norm = normalise_phone(phone)
    if not norm:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def compute_content_hash(fields: Dict[str, Any]) -> str:
    """Deterministic SHA-256 over canonical prospect identity fields."""
    from services.discovery.discovery_hashing import compute_canonical_content_hash

    return compute_canonical_content_hash(fields)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class DiscoveryProviderId(str, Enum):
    """Registered provider identifiers. Phase 1 active: csv, manual only."""
    CSV = "csv"
    MANUAL = "manual"
    APOLLO = "apollo"
    CLAY = "clay"
    TWIN = "twin"
    INTERNAL_CRAWLER = "internal_crawler"

    @classmethod
    def phase1_active(cls) -> frozenset["DiscoveryProviderId"]:
        return frozenset({cls.CSV, cls.MANUAL})


class DiscoveryCampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class DiscoveryRunStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DiscoveryJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DiscoverySourceType(str, Enum):
    CSV = "csv"
    MANUAL = "manual"
    API = "api"  # reserved Phase 2
    CRAWLER = "crawler"  # reserved Phase 2


class DiscoveryBusinessType(str, Enum):
    LANDLORD = "landlord"
    LETTING_AGENCY = "letting_agency"
    PROPERTY_MANAGER = "property_manager"
    HMO_OPERATOR = "hmo_operator"
    COMPLIANCE_PROVIDER = "compliance_provider"
    UNKNOWN = "unknown"


class DiscoveryLandlordType(str, Enum):
    SINGLE_PROPERTY = "single_property"
    PORTFOLIO = "portfolio"
    HMO = "hmo"
    UNKNOWN = "unknown"


class DiscoveryLawfulBasis(str, Enum):
    LEGITIMATE_INTEREST_B2B = "legitimate_interest_b2b"
    CONSENT = "consent"
    UNKNOWN = "unknown"


class DiscoveryReviewStatus(str, Enum):
    DISCOVERED = "discovered"
    NEEDS_REVIEW = "needs_review"
    DUPLICATE_DETECTED = "duplicate_detected"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPORTED = "imported"
    ARCHIVED = "archived"


class DiscoveryDuplicateStatus(str, Enum):
    NONE = "none"
    POSSIBLE = "possible"
    CONFIRMED = "confirmed"


class DiscoveryErasureStatus(str, Enum):
    ACTIVE = "active"
    ERASED = "erased"
    SUPPRESSED = "suppressed"


class DiscoveryCostUnitType(str, Enum):
    ROWS = "rows"
    CREDITS = "credits"
    MINUTES = "minutes"


# ---------------------------------------------------------------------------
# Audit event taxonomy — FROZEN (Stage B)
# ---------------------------------------------------------------------------
class DiscoveryAuditEventCore(str, Enum):
    """Phase 1 core prospect lifecycle events."""
    PROSPECT_DISCOVERED = "PROSPECT_DISCOVERED"
    PROSPECT_UPDATED = "PROSPECT_UPDATED"
    PROSPECT_REVIEWED = "PROSPECT_REVIEWED"
    PROSPECT_APPROVED = "PROSPECT_APPROVED"
    PROSPECT_REJECTED = "PROSPECT_REJECTED"
    PROSPECT_IMPORTED = "PROSPECT_IMPORTED"
    PROSPECT_ARCHIVED = "PROSPECT_ARCHIVED"
    PROSPECT_ERASURE_REQUESTED = "PROSPECT_ERASURE_REQUESTED"
    PROSPECT_ERASED = "PROSPECT_ERASED"


class DiscoveryAuditEventPhase2Reserved(str, Enum):
    """Reserved — do not emit until Phase 2 provider integration."""
    PROVIDER_JOB_CREATED = "PROVIDER_JOB_CREATED"
    PROVIDER_JOB_COMPLETED = "PROVIDER_JOB_COMPLETED"
    PROVIDER_JOB_FAILED = "PROVIDER_JOB_FAILED"
    PROVIDER_ENRICHMENT_STARTED = "PROVIDER_ENRICHMENT_STARTED"
    PROVIDER_ENRICHMENT_COMPLETED = "PROVIDER_ENRICHMENT_COMPLETED"
    PROVIDER_ENRICHMENT_FAILED = "PROVIDER_ENRICHMENT_FAILED"


class DiscoveryAuditEventFrozenExtended(str, Enum):
    """Frozen operational events — reserved for Stages E+; taxonomy locked at Stage B."""
    RUN_CREATED = "RUN_CREATED"
    RUN_ATTESTED = "RUN_ATTESTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    JOB_CREATED = "JOB_CREATED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    DUPLICATE_DETECTED = "DUPLICATE_DETECTED"
    DUPLICATE_OVERRIDDEN = "DUPLICATE_OVERRIDDEN"
    IMPORT_REQUESTED = "IMPORT_REQUESTED"
    IMPORT_VALIDATED = "IMPORT_VALIDATED"
    IMPORT_BLOCKED = "IMPORT_BLOCKED"
    IMPORT_FAILED = "IMPORT_FAILED"
    SUPPRESSION_MATCH = "SUPPRESSION_MATCH"
    LIA_VALIDATION_FAILED = "LIA_VALIDATION_FAILED"
    CONSENT_VALIDATION_FAILED = "CONSENT_VALIDATION_FAILED"
    RAW_PAYLOAD_DELETED = "RAW_PAYLOAD_DELETED"
    LEGAL_HOLD_SET = "LEGAL_HOLD_SET"
    LEGAL_HOLD_RELEASED = "LEGAL_HOLD_RELEASED"
    ERASURE_REQUESTED = "ERASURE_REQUESTED"
    ERASURE_EXECUTED = "ERASURE_EXECUTED"
    LEGAL_HOLD_APPLIED = "LEGAL_HOLD_APPLIED"
    RETENTION_EXPIRY_REACHED = "RETENTION_EXPIRY_REACHED"
    PURGE_ELIGIBLE = "PURGE_ELIGIBLE"
    PURGE_BLOCKED = "PURGE_BLOCKED"
    LEAD_DISCOVERY_PROVENANCE_ERASED = "LEAD_DISCOVERY_PROVENANCE_ERASED"
    PROVIDER_JOB_STARTED = "PROVIDER_JOB_STARTED"
    PROVIDER_JOB_PROGRESS = "PROVIDER_JOB_PROGRESS"
    ENRICHMENT_REQUESTED = "ENRICHMENT_REQUESTED"
    ENRICHMENT_COMPLETED = "ENRICHMENT_COMPLETED"
    CRAWL_SESSION_STARTED = "CRAWL_SESSION_STARTED"
    CRAWL_PAGE_FETCHED = "CRAWL_PAGE_FETCHED"
    CRAWL_SESSION_COMPLETED = "CRAWL_SESSION_COMPLETED"


FROZEN_AUDIT_EVENT_VALUES = frozenset(
    e.value
    for enum_cls in (
        DiscoveryAuditEventCore,
        DiscoveryAuditEventPhase2Reserved,
        DiscoveryAuditEventFrozenExtended,
    )
    for e in enum_cls
)


def is_frozen_audit_event(event_type: str) -> bool:
    return event_type in FROZEN_AUDIT_EVENT_VALUES


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------
class TargetIcp(BaseModel):
    business_types: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    portfolio_min: Optional[int] = None
    portfolio_max: Optional[int] = None
    notes: Optional[str] = None


class OriginLineageEntry(BaseModel):
    """Schema-stable provenance entry — append-only via prospect service."""
    provider: str
    provider_reference: Optional[str] = None
    discovery_run_id: Optional[str] = None
    discovery_job_id: Optional[str] = None
    campaign_id: Optional[str] = None
    source_url: Optional[str] = None
    content_hash: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    discovered_at: Optional[datetime] = None
    ingested_at: datetime

    @model_validator(mode="after")
    def _default_discovered_at(self) -> "OriginLineageEntry":
        if self.discovered_at is None:
            self.discovered_at = self.ingested_at
        return self


class ProspectLocation(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None


class RunAttestation(BaseModel):
    lawful_basis_declared: DiscoveryLawfulBasis
    lawful_basis_declaration_id: Optional[str] = None
    data_source_description: str
    consent_not_assumed: bool = True
    attested_by_id: str
    attested_by_email: str
    attested_at: datetime


class RunCostAttribution(BaseModel):
    """Reserved cost fields — CSV defaults to zero."""
    estimated_cost: Optional[float] = 0.0
    cost_currency: str = "GBP"
    cost_units: Optional[float] = 0.0
    cost_unit_type: DiscoveryCostUnitType = DiscoveryCostUnitType.ROWS
    provider_billing_ref: Optional[str] = None


class QualitySnapshot(BaseModel):
    platform_quality_score: int = Field(ge=0, le=100)
    provider_confidence: int = Field(ge=0, le=100)
    completeness_score: Optional[int] = Field(default=None, ge=0, le=100)
    validity_score: Optional[int] = Field(default=None, ge=0, le=100)
    risk_flags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Collection document models
# ---------------------------------------------------------------------------
class DiscoveryCampaignDocument(BaseModel):
    campaign_id: str
    name: str
    purpose: str
    target_icp: TargetIcp
    owner_id: str
    owner_email: Optional[str] = None
    budget_reference: Optional[str] = None
    budget_amount: Optional[float] = None
    budget_currency: str = "GBP"
    status: DiscoveryCampaignStatus = DiscoveryCampaignStatus.DRAFT
    lawful_basis: DiscoveryLawfulBasis = DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B
    lawful_basis_declaration_id: Optional[str] = None
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)
    created_at: datetime
    updated_at: datetime


class DiscoveryRunDocument(BaseModel):
    discovery_run_id: str
    campaign_id: Optional[str] = None
    """Nullable only when is_ad_hoc=True (documented ad-hoc/manual runs)."""
    is_ad_hoc: bool = False
    provider: DiscoveryProviderId
    status: DiscoveryRunStatus = DiscoveryRunStatus.PROCESSING
    uploaded_by: str
    uploaded_by_email: Optional[str] = None
    file_name: Optional[str] = None
    row_count: Optional[int] = None
    attestation: Optional[RunAttestation] = None
    cost: RunCostAttribution = Field(default_factory=RunCostAttribution)
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)
    created_at: datetime
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DiscoveryJobDocument(BaseModel):
    """Stub schema — no execution logic in Stage B."""
    job_id: str
    run_id: str
    provider: DiscoveryProviderId
    status: DiscoveryJobStatus = DiscoveryJobStatus.PENDING
    supports_async: bool = False
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class DiscoveryProspectDocument(BaseModel):
    prospect_id: str
    campaign_id: Optional[str] = None
    discovery_run_id: str
    discovery_job_id: Optional[str] = None
    provider: DiscoveryProviderId
    provider_reference: Optional[str] = None
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_confidence: int = Field(default=50, ge=0, le=100)
    platform_quality_score: int = Field(default=0, ge=0, le=100)
    review_priority: int = Field(default=50, ge=0, le=100)
    origin_lineage: List[OriginLineageEntry] = Field(default_factory=list)
    source_url: Optional[str] = None
    source_type: DiscoverySourceType = DiscoverySourceType.CSV
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    email_hash: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    phone_hash: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    website: Optional[str] = None
    location: Optional[ProspectLocation] = None
    business_type: DiscoveryBusinessType = DiscoveryBusinessType.UNKNOWN
    landlord_type: DiscoveryLandlordType = DiscoveryLandlordType.UNKNOWN
    lawful_basis: DiscoveryLawfulBasis = DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B
    marketing_consent: bool = False
    duplicate_status: DiscoveryDuplicateStatus = DiscoveryDuplicateStatus.NONE
    review_status: DiscoveryReviewStatus = DiscoveryReviewStatus.DISCOVERED
    merged_into_prospect_id: Optional[str] = None
    duplicate_lead_id: Optional[str] = None
    imported_lead_id: Optional[str] = None
    raw_payload_reference: Optional[str] = None
    risk_flags: List[str] = Field(default_factory=list)
    duplicate_override_reason: Optional[str] = None
    erasure_requested_at: Optional[datetime] = None
    erasure_status: DiscoveryErasureStatus = DiscoveryErasureStatus.ACTIVE
    legal_hold: bool = False
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _sync_hashes_and_contact_rule(self) -> "DiscoveryProspectDocument":
        if self.email and not self.email_hash:
            self.email_hash = email_hash(self.email)
        if self.phone and not self.phone_hash:
            self.phone_hash = phone_hash(self.phone)
        has_contact = any(
            v and str(v).strip()
            for v in (self.email, self.phone, self.company_name, self.website)
        )
        if not has_contact:
            raise ValueError(
                "At least one of email, phone, company_name, or website is required"
            )
        return self


class DiscoveryAuditLogDocument(BaseModel):
    """
    Immutable audit record — append-only by design.
    No update/delete methods are provided in Stage B services.
    """
    audit_id: str
    event_type: str
    prospect_id: Optional[str] = None
    run_id: Optional[str] = None
    campaign_id: Optional[str] = None
    job_id: Optional[str] = None
    lead_id: Optional[str] = None
    provider: Optional[str] = None
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    reason_code: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)
    created_at: datetime

    @field_validator("event_type")
    @classmethod
    def _frozen_taxonomy(cls, v: str) -> str:
        if not is_frozen_audit_event(v):
            raise ValueError(f"Unknown or non-frozen audit event_type: {v}")
        return v


class DiscoveryMetricsDocument(BaseModel):
    """Daily rollup schema — no rollup logic in Stage B."""
    metric_date: str  # YYYY-MM-DD UTC
    provider: str
    campaign_id: Optional[str] = None
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)
    discovered: int = 0
    approved: int = 0
    rejected: int = 0
    imported: int = 0
    duplicate_rate: float = 0.0
    conversion_to_lead: int = 0
    conversion_to_pilot: int = 0
    conversion_to_customer: int = 0
    # Reserved nice-to-have fields
    estimated_cost: Optional[float] = None
    cost_per_imported_lead: Optional[float] = None
    provider_quality_score: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProviderMappingProfileDocument(BaseModel):
    """Reserved Phase 2 — column/table mapping profiles."""
    profile_id: str
    provider: DiscoveryProviderId
    name: str
    column_map: Dict[str, str] = Field(default_factory=dict)
    tenant_id: str = Field(default=PLATFORM_TENANT_ID)
    created_at: datetime
    updated_at: datetime
