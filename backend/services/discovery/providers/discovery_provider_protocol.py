"""
DiscoveryProvider protocol — authoritative contract (Stage B).

No provider implementations in this module.
See docs/contracts/DISCOVERY_PROVIDER_PROTOCOL.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from services.discovery.discovery_models import (
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    OriginLineageEntry,
    RunAttestation,
)

# Capabilities prohibited for all providers, all phases
PROHIBITED_PROVIDER_CAPABILITIES = frozenset(
    {
        "OUTREACH",
        "CRM_WRITE",
        "NURTURE_TRIGGER",
        "COMPLIANCE_ACCESS",
        "NOTIFICATION_SEND",
        "BILLING_WRITE",
    }
)


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_async: bool
    supports_enrichment: bool
    supports_cost_tracking: bool
    supports_webhook: bool = False
    max_batch_size: int = 2000
    prohibited_capabilities: frozenset[str] = PROHIBITED_PROVIDER_CAPABILITIES


@dataclass
class IngestContext:
    discovery_run_id: str
    actor_id: str
    actor_email: str
    lawful_basis: DiscoveryLawfulBasis
    discovery_campaign_id: Optional[str] = None
    discovery_job_id: Optional[str] = None
    tenant_id: str = "pleerity"
    attestation: Optional[RunAttestation] = None
    provider_mapping_profile_id: Optional[str] = None


@dataclass
class IngestSource:
    """Opaque ingest payload — CSV bytes, manual dict, or Phase 2 API cursor."""
    payload: Any
    content_type: Optional[str] = None
    file_name: Optional[str] = None


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)


@dataclass
class CanonicalProspect:
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    source_url: Optional[str] = None
    business_type: Optional[str] = None
    landlord_type: Optional[str] = None
    provider_confidence: int = 50
    marketing_consent: bool = False
    lawful_basis: Optional[DiscoveryLawfulBasis] = None
    provider_reference: Optional[str] = None
    provider_extensions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RowError:
    row_index: int
    errors: List[str]


@dataclass
class IngestResult:
    discovery_run_id: str
    accepted_count: int
    rejected_count: int
    discovery_job_id: Optional[str] = None
    errors: List[RowError] = field(default_factory=list)


@runtime_checkable
class DiscoveryProvider(Protocol):
  """
  Provider-neutral discovery adapter contract.

  Phase 1: only csv and manual adapters may be registered.
  """

  @property
  def provider_id(self) -> DiscoveryProviderId | str:
    ...

  @property
  def adapter_version(self) -> str:
    ...

  @property
  def supports_async(self) -> bool:
    ...

  @property
  def supports_enrichment(self) -> bool:
    ...

  def capabilities(self) -> ProviderCapabilities:
    ...

  def validate(self, raw_row: Dict[str, Any], context: IngestContext) -> ValidationResult:
    ...

  def map_to_canonical(
    self, raw_row: Dict[str, Any], context: IngestContext
  ) -> CanonicalProspect:
    ...

  def idempotency_key(
    self, canonical: CanonicalProspect, context: IngestContext
  ) -> str:
    ...

  def ingest(self, source: IngestSource, context: IngestContext) -> IngestResult:
    ...


def build_idempotency_key(
    provider_id: str,
    provider_reference: str,
    content_hash: str,
) -> str:
    """Standard idempotency key — delegates to Stage H canonical builder."""
    from services.discovery.discovery_hashing import build_discovery_idempotency_key

    return build_discovery_idempotency_key(provider_id, provider_reference, content_hash)


def validate_provider_capabilities(caps: ProviderCapabilities) -> List[str]:
    """Return violations if prohibited capabilities are not marked prohibited."""
    violations: List[str] = []
    for required in PROHIBITED_PROVIDER_CAPABILITIES:
        if required not in caps.prohibited_capabilities:
            violations.append(f"Missing prohibited capability declaration: {required}")
    return violations


def validate_protocol_compliance(provider: DiscoveryProvider) -> List[str]:
    """Structural validation that an object satisfies DiscoveryProvider protocol."""
    errors: List[str] = []
    if not isinstance(provider, DiscoveryProvider):
        errors.append("Object does not satisfy DiscoveryProvider runtime protocol")
    for attr in (
        "provider_id",
        "adapter_version",
        "supports_async",
        "supports_enrichment",
        "capabilities",
        "validate",
        "map_to_canonical",
        "idempotency_key",
        "ingest",
    ):
        if not hasattr(provider, attr):
            errors.append(f"Missing required attribute/method: {attr}")
    if hasattr(provider, "capabilities"):
        try:
            cap_errors = validate_provider_capabilities(provider.capabilities())
            errors.extend(cap_errors)
        except Exception as exc:
            errors.append(f"capabilities() failed: {exc}")
    return errors
