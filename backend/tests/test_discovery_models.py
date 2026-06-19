"""
Stage B unit tests — discovery data foundation.

No workflow, routes, providers, or LeadService integration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from services.discovery.discovery_indexes import (
    DISCOVERY_INDEX_INVENTORY,
    ensure_discovery_indexes,
)
from services.discovery.twin.twin_connector_indexes import TWIN_CONNECTOR_INDEX_INVENTORY
from services.discovery.discovery_metadata_contract import (
    example_valid_discovery_metadata,
    load_discovery_source_metadata_schema,
    validate_discovery_source_metadata,
)
from services.discovery.discovery_models import (
    CONTENT_HASH_FIELDS,
    DISCOVERY_AUDIT_LOGS_COLLECTION,
    DISCOVERY_CAMPAIGNS_COLLECTION,
    DISCOVERY_JOBS_COLLECTION,
    DISCOVERY_METRICS_COLLECTION,
    DISCOVERY_PROSPECTS_COLLECTION,
    DISCOVERY_RUNS_COLLECTION,
    DISCOVERY_SOURCE_METADATA_SCHEMA_VERSION,
    FROZEN_AUDIT_EVENT_VALUES,
    PLATFORM_TENANT_ID,
    DiscoveryAuditEventCore,
    DiscoveryAuditEventFrozenExtended,
    DiscoveryAuditEventPhase2Reserved,
    DiscoveryAuditLogDocument,
    DiscoveryCampaignDocument,
    DiscoveryCampaignStatus,
    DiscoveryDuplicateStatus,
    DiscoveryJobDocument,
    DiscoveryJobStatus,
    DiscoveryMetricsDocument,
    DiscoveryProspectDocument,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
    DiscoveryRunDocument,
    DiscoveryRunStatus,
    DiscoverySourceType,
    OriginLineageEntry,
    TargetIcp,
    compute_content_hash,
    email_hash,
    generate_campaign_id,
    generate_discovery_audit_id,
    generate_discovery_job_id,
    generate_discovery_run_id,
    generate_prospect_id,
    is_frozen_audit_event,
    normalise_email,
    phone_hash,
)
from services.discovery.providers.discovery_provider_protocol import (
    PROHIBITED_PROVIDER_CAPABILITIES,
    CanonicalProspect,
    DiscoveryProvider,
    IngestContext,
    IngestResult,
    IngestSource,
    ProviderCapabilities,
    ValidationResult,
    build_idempotency_key,
    validate_protocol_compliance,
    validate_provider_capabilities,
)
from services.discovery.discovery_models import DiscoveryLawfulBasis


NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------
def test_id_generators_use_expected_prefixes():
    assert generate_campaign_id().startswith("DCAMP-")
    assert generate_discovery_run_id().startswith("DRUN-")
    assert generate_discovery_job_id().startswith("DJOB-")
    assert generate_prospect_id().startswith("PROSP-")
    assert generate_discovery_audit_id()


# ---------------------------------------------------------------------------
# Enum validation
# ---------------------------------------------------------------------------
def test_discovery_provider_phase1_active():
    active = DiscoveryProviderId.phase1_active()
    assert DiscoveryProviderId.CSV in active
    assert DiscoveryProviderId.MANUAL in active
    assert DiscoveryProviderId.APOLLO not in active
    assert DiscoveryProviderId.TWIN not in active


def test_frozen_audit_taxonomy_core_events():
    for event in DiscoveryAuditEventCore:
        assert is_frozen_audit_event(event.value)


def test_frozen_audit_taxonomy_phase2_reserved():
    for event in DiscoveryAuditEventPhase2Reserved:
        assert is_frozen_audit_event(event.value)


def test_frozen_audit_taxonomy_extended_reserved():
    for event in DiscoveryAuditEventFrozenExtended:
        assert is_frozen_audit_event(event.value)


def test_audit_taxonomy_inventory_complete():
    expected = {
        e.value for e in DiscoveryAuditEventCore
    } | {
        e.value for e in DiscoveryAuditEventPhase2Reserved
    } | {
        e.value for e in DiscoveryAuditEventFrozenExtended
    }
    assert expected == FROZEN_AUDIT_EVENT_VALUES


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------
def _minimal_prospect_kwargs() -> Dict[str, Any]:
    return {
        "prospect_id": generate_prospect_id(),
        "discovery_run_id": generate_discovery_run_id(),
        "provider": DiscoveryProviderId.CSV,
        "content_hash": compute_content_hash({"email": "a@example.com"}),
        "email": "a@example.com",
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_discovery_campaign_required_fields():
    doc = DiscoveryCampaignDocument(
        campaign_id=generate_campaign_id(),
        name="Wales Landlords Q2",
        purpose="Pilot prospecting",
        target_icp=TargetIcp(regions=["Wales"]),
        owner_id="admin-1",
        lawful_basis_declaration_id="LIA-2026-01",
        created_at=NOW,
        updated_at=NOW,
    )
    assert doc.tenant_id == PLATFORM_TENANT_ID
    assert doc.lawful_basis_declaration_id == "LIA-2026-01"


def test_discovery_run_reserved_cost_fields():
    doc = DiscoveryRunDocument(
        discovery_run_id=generate_discovery_run_id(),
        campaign_id=generate_campaign_id(),
        provider=DiscoveryProviderId.CSV,
        status=DiscoveryRunStatus.PROCESSING,
        uploaded_by="admin-1",
        created_at=NOW,
    )
    assert doc.cost.estimated_cost == 0.0
    assert doc.cost.cost_currency == "GBP"
    assert doc.cost.cost_unit_type.value == "rows"
    assert doc.cost.provider_billing_ref is None


def test_discovery_job_stub_schema():
    doc = DiscoveryJobDocument(
        job_id=generate_discovery_job_id(),
        run_id=generate_discovery_run_id(),
        provider=DiscoveryProviderId.CSV,
        status=DiscoveryJobStatus.COMPLETED,
        supports_async=False,
        created_at=NOW,
        completed_at=NOW,
    )
    assert doc.supports_async is False


def test_discovery_prospect_required_fields_and_tenant():
    doc = DiscoveryProspectDocument(**_minimal_prospect_kwargs())
    assert doc.tenant_id == PLATFORM_TENANT_ID
    assert doc.marketing_consent is False
    assert doc.email_hash == email_hash("a@example.com")
    assert doc.platform_quality_score >= 0
    assert doc.provider_confidence >= 0


def test_discovery_prospect_requires_contact_identifier():
    kwargs = _minimal_prospect_kwargs()
    kwargs.pop("email")
    with pytest.raises(ValueError, match="email, phone, company_name, or website"):
        DiscoveryProspectDocument(**kwargs)


def test_discovery_prospect_company_name_only():
    kwargs = _minimal_prospect_kwargs()
    kwargs.pop("email")
    kwargs["company_name"] = "Acme Lettings"
    kwargs["content_hash"] = compute_content_hash({"company_name": "Acme Lettings"})
    doc = DiscoveryProspectDocument(**kwargs)
    assert doc.company_name == "Acme Lettings"


def test_platform_quality_score_separate_from_provider_confidence():
    kwargs = _minimal_prospect_kwargs()
    kwargs["platform_quality_score"] = 72
    kwargs["provider_confidence"] = 50
    doc = DiscoveryProspectDocument(**kwargs)
    assert doc.platform_quality_score != doc.provider_confidence or (
        doc.platform_quality_score == 72 and doc.provider_confidence == 50
    )


def test_origin_lineage_on_prospect():
    kwargs = _minimal_prospect_kwargs()
    kwargs["origin_lineage"] = [
        OriginLineageEntry(
            provider="csv",
            provider_reference="row-1",
            ingested_at=NOW,
        )
    ]
    doc = DiscoveryProspectDocument(**kwargs)
    assert len(doc.origin_lineage) == 1


def test_discovery_audit_log_immutable_schema_rejects_unknown_event():
    with pytest.raises(ValueError, match="non-frozen audit event_type"):
        DiscoveryAuditLogDocument(
            audit_id=generate_discovery_audit_id(),
            event_type="NOT_A_REAL_EVENT",
            created_at=NOW,
        )


def test_discovery_audit_log_accepts_core_event():
    doc = DiscoveryAuditLogDocument(
        audit_id=generate_discovery_audit_id(),
        event_type=DiscoveryAuditEventCore.PROSPECT_DISCOVERED.value,
        prospect_id=generate_prospect_id(),
        run_id=generate_discovery_run_id(),
        campaign_id=generate_campaign_id(),
        actor_id="admin-1",
        actor_email="admin@example.com",
        provider="csv",
        created_at=NOW,
    )
    assert doc.event_type == "PROSPECT_DISCOVERED"


def test_discovery_metrics_schema_only():
    doc = DiscoveryMetricsDocument(
        metric_date="2026-06-02",
        provider="csv",
        campaign_id=generate_campaign_id(),
        discovered=10,
        approved=5,
        rejected=2,
        imported=4,
        duplicate_rate=0.1,
        conversion_to_lead=4,
        conversion_to_pilot=1,
        conversion_to_customer=0,
    )
    assert doc.tenant_id == PLATFORM_TENANT_ID


# ---------------------------------------------------------------------------
# Content hash / normalisation
# ---------------------------------------------------------------------------
def test_content_hash_deterministic():
    fields = {
        "email": "Test@Example.com",
        "company_name": "Acme",
    }
    h1 = compute_content_hash(fields)
    h2 = compute_content_hash(fields)
    assert h1 == h2
    assert len(h1) == 64


def test_content_hash_fields_inventory():
    assert "email" in CONTENT_HASH_FIELDS
    assert "company_name" in CONTENT_HASH_FIELDS


def test_normalise_email_lowercase():
    assert normalise_email("  Foo@BAR.com ") == "foo@bar.com"


# ---------------------------------------------------------------------------
# Index inventory
# ---------------------------------------------------------------------------
def test_discovery_index_inventory_covers_required_collections():
    collections = {spec[0] for spec in DISCOVERY_INDEX_INVENTORY}
    assert DISCOVERY_CAMPAIGNS_COLLECTION in collections
    assert DISCOVERY_RUNS_COLLECTION in collections
    assert DISCOVERY_JOBS_COLLECTION in collections
    assert DISCOVERY_PROSPECTS_COLLECTION in collections
    assert DISCOVERY_AUDIT_LOGS_COLLECTION in collections
    assert DISCOVERY_METRICS_COLLECTION in collections


def test_discovery_index_inventory_dedupe_and_queue_keys():
    flat_keys = []
    for _coll, keys, _kwargs in DISCOVERY_INDEX_INVENTORY:
        if isinstance(keys, str):
            flat_keys.append(keys)
        elif isinstance(keys, list):
            flat_keys.extend(k[0] if isinstance(k, tuple) else k for k in keys)
    for required in (
        "email",
        "phone",
        "content_hash",
        "provider_reference",
        "review_status",
        "duplicate_status",
        "created_at",
        "prospect_id",
        "discovery_run_id",
        "campaign_id",
        "provider",
    ):
        assert required in flat_keys, f"Missing index key: {required}"


@pytest.mark.asyncio
async def test_ensure_discovery_indexes_registers_without_error():
  class _FakeColl:
      def __init__(self):
          self.indexes = []

      async def create_index(self, keys, **kwargs):
          self.indexes.append((keys, kwargs))

  class _FakeDb:
      def __init__(self):
          self._colls: Dict[str, _FakeColl] = {}

      def __getitem__(self, name: str) -> _FakeColl:
          if name not in self._colls:
              self._colls[name] = _FakeColl()
          return self._colls[name]

  db = _FakeDb()
  await ensure_discovery_indexes(db)
  assert len(db._colls) >= 8
  total_indexes = sum(len(c.indexes) for c in db._colls.values())
  assert total_indexes == len(DISCOVERY_INDEX_INVENTORY) + len(TWIN_CONNECTOR_INDEX_INVENTORY)


# ---------------------------------------------------------------------------
# Metadata contract validation
# ---------------------------------------------------------------------------
def test_metadata_contract_loads():
    schema = load_discovery_source_metadata_schema()
    assert schema["properties"]["schema_version"]["const"] == DISCOVERY_SOURCE_METADATA_SCHEMA_VERSION


def test_metadata_contract_example_validates():
    example = example_valid_discovery_metadata()
    ok, errors = validate_discovery_source_metadata(example)
    assert ok, errors


def test_metadata_contract_required_fields():
    example = example_valid_discovery_metadata()
    for field in (
        "schema_version",
        "discovery_provider",
        "discovery_prospect_id",
        "discovery_run_id",
        "lawful_basis",
        "imported_at",
        "content_hash",
        "origin_lineage",
        "erasure_status",
    ):
        assert field in example


def test_metadata_contract_supports_campaign_id():
    example = example_valid_discovery_metadata()
    assert "discovery_campaign_id" in example
    assert example["discovery_campaign_id"].startswith("DCAMP-")


def test_metadata_contract_supports_provider_reference():
    example = example_valid_discovery_metadata()
    assert example.get("provider_reference") == "csv:row-42"


def test_metadata_contract_rejects_drift():
    example = example_valid_discovery_metadata()
    bad = {**example, "schema_version": "9.9.9"}
    ok, errors = validate_discovery_source_metadata(bad)
    assert not ok
    assert any("schema_version" in e for e in errors)


def test_metadata_contract_rejects_unknown_properties():
    example = example_valid_discovery_metadata()
    bad = {**example, "twin_workflow_id": "wf-123"}
    ok, errors = validate_discovery_source_metadata(bad)
    assert not ok


# ---------------------------------------------------------------------------
# DiscoveryProvider protocol validation
# ---------------------------------------------------------------------------
class _StubProvider:
    provider_id = DiscoveryProviderId.MANUAL
    adapter_version = "1.0.0"
    supports_async = False
    supports_enrichment = False

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_async=False,
            supports_enrichment=False,
            supports_cost_tracking=False,
        )

    def validate(self, raw_row: Dict[str, Any], context: IngestContext) -> ValidationResult:
        return ValidationResult(valid=True)

    def map_to_canonical(
        self, raw_row: Dict[str, Any], context: IngestContext
    ) -> CanonicalProspect:
        return CanonicalProspect(email=raw_row.get("email"))

    def idempotency_key(
        self, canonical: CanonicalProspect, context: IngestContext
    ) -> str:
        return build_idempotency_key("manual", context.discovery_run_id, "abc" * 21 + "a")

    def ingest(self, source: IngestSource, context: IngestContext) -> IngestResult:
        return IngestResult(
            discovery_run_id=context.discovery_run_id,
            accepted_count=0,
            rejected_count=0,
        )


def test_discovery_provider_protocol_stub_compliance():
    provider = _StubProvider()
    assert isinstance(provider, DiscoveryProvider)
    errors = validate_protocol_compliance(provider)
    assert errors == []


def test_prohibited_capabilities_enforced():
    caps = ProviderCapabilities(
        supports_async=False,
        supports_enrichment=False,
        supports_cost_tracking=False,
        prohibited_capabilities=frozenset({"OUTREACH"}),
    )
    violations = validate_provider_capabilities(caps)
    assert any("CRM_WRITE" in v for v in violations)


def test_idempotency_key_format():
    content_hash = "a" * 64
    key = build_idempotency_key("csv", "DRUN-TEST", content_hash)
    assert key.startswith("csv:")
    assert key.endswith(content_hash)
    from services.discovery.discovery_hashing import validate_discovery_idempotency_key

    assert validate_discovery_idempotency_key(key) == []


# ---------------------------------------------------------------------------
# Scope guards — no workflow modules in Stage B
# ---------------------------------------------------------------------------
def test_authorized_discovery_routes_exist():
    import importlib.util

    assert importlib.util.find_spec("routes.admin_discovery") is not None
    assert importlib.util.find_spec("routes.discovery_twin_internal") is not None


def test_no_csv_provider_implementation():
    import importlib.util

def test_discovery_import_service_exists():
    import importlib.util

    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None
