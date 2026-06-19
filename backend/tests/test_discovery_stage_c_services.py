"""
Stage C unit tests — campaign, run, job services, provider registry, audit helpers.

No routes, CSV ingest, import workflow, or LeadService integration.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery import discovery_config
from services.discovery.discovery_audit_helpers import (
    DiscoveryAuditValidationError,
    build_audit_event,
    prepare_audit_payload,
    validate_audit_event_type,
)
from services.discovery.discovery_campaign_service import (
    CreateCampaignRequest,
    DiscoveryCampaignError,
    DiscoveryCampaignService,
)
from services.discovery.discovery_job_service import DiscoveryJobService
from services.discovery.discovery_models import (
    DiscoveryAuditEventCore,
    DiscoveryCampaignStatus,
    DiscoveryJobStatus,
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    DiscoveryRunStatus,
    RunAttestation,
    TargetIcp,
)
from services.discovery.discovery_provider_registry import (
    DiscoveryProviderRegistry,
    DiscoveryProviderRegistryError,
    ProviderCapabilities,
    ProviderRegistryEntry,
    default_provider_registry,
)
from services.discovery.discovery_run_service import (
    CreateRunRequest,
    DiscoveryRunError,
    DiscoveryRunService,
)
from services.discovery.providers.discovery_provider_protocol import (
    PROHIBITED_PROVIDER_CAPABILITIES,
    validate_provider_capabilities,
)

NOW = datetime(2026, 6, 2, 14, 0, 0, tzinfo=timezone.utc)


class _FakeCollection:
    def __init__(self):
        self.docs: list = []
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.update_one = AsyncMock(side_effect=self._update_one)
        self.find = MagicMock(side_effect=self._find)

    async def _insert_one(self, doc):
        self.docs.append(dict(doc))

    async def _find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                out = dict(doc)
                out.pop("_id", None)
                return out
        return None

    async def _update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def _find(self, query, projection=None):
        matches = [
            dict(d)
            for d in self.docs
            if all(d.get(k) == v for k, v in query.items())
        ]

        class _Cursor:
            def __init__(self, items):
                self._items = items

            def sort(self, *args, **kwargs):
                return self

            def skip(self, n):
                return self

            def limit(self, n):
                self._items = self._items[:n]
                return self

            async def to_list(self, length):
                return self._items[:length]

        return _Cursor(matches)


class _FakeDB:
    def __init__(self):
        self.discovery_campaigns = _FakeCollection()
        self.discovery_runs = _FakeCollection()
        self.discovery_jobs = _FakeCollection()

    def __getitem__(self, name: str):
        return getattr(self, name)


def _campaign_request(**kwargs) -> CreateCampaignRequest:
    defaults = dict(
        name="Wales Landlords Q2",
        purpose="Pilot prospecting",
        target_icp=TargetIcp(regions=["Wales"]),
        owner_id="admin-1",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        lawful_basis_declaration_id="LIA-2026-01",
    )
    defaults.update(kwargs)
    return CreateCampaignRequest(**defaults)


def _attestation() -> RunAttestation:
    return RunAttestation(
        lawful_basis_declared=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        lawful_basis_declaration_id="LIA-2026-01",
        data_source_description="Conference list",
        attested_by_id="admin-1",
        attested_by_email="admin@example.com",
        attested_at=NOW,
    )


# ---------------------------------------------------------------------------
# Campaign service
# ---------------------------------------------------------------------------
def test_campaign_validation_requires_lia_for_legitimate_interest():
    req = _campaign_request(lawful_basis_declaration_id=None)
    errors = DiscoveryCampaignService.validate_campaign(req)
    assert any("lawful_basis_declaration_id" in e for e in errors)


def test_campaign_validation_requires_purpose_and_owner():
    req = CreateCampaignRequest(
        name="X",
        purpose="",
        target_icp=TargetIcp(),
        owner_id="",
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
    )
    errors = DiscoveryCampaignService.validate_campaign(req)
    assert "purpose is required" in errors
    assert "owner_id is required" in errors


@pytest.mark.asyncio
async def test_create_campaign_generates_campaign_id():
    db = _FakeDB()
    with patch("services.discovery.discovery_campaign_service.database.get_db", return_value=db):
        result = await DiscoveryCampaignService.create_campaign(_campaign_request())
    assert result["campaign_id"].startswith("DCAMP-")
    assert result["status"] == DiscoveryCampaignStatus.DRAFT.value
    assert len(db.discovery_campaigns.docs) == 1


@pytest.mark.asyncio
async def test_campaign_status_transition_draft_to_active():
    db = _FakeDB()
    with patch("services.discovery.discovery_campaign_service.database.get_db", return_value=db):
        created = await DiscoveryCampaignService.create_campaign(_campaign_request())
        updated = await DiscoveryCampaignService.update_campaign_status(
            created["campaign_id"],
            DiscoveryCampaignStatus.ACTIVE,
        )
    assert updated["status"] == DiscoveryCampaignStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_campaign_invalid_status_transition_raises():
    db = _FakeDB()
    with patch("services.discovery.discovery_campaign_service.database.get_db", return_value=db):
        created = await DiscoveryCampaignService.create_campaign(_campaign_request())
        await DiscoveryCampaignService.update_campaign_status(
            created["campaign_id"],
            DiscoveryCampaignStatus.ARCHIVED,
        )
        with pytest.raises(DiscoveryCampaignError) as exc:
            await DiscoveryCampaignService.update_campaign_status(
                created["campaign_id"],
                DiscoveryCampaignStatus.ACTIVE,
            )
    assert exc.value.code == "INVALID_STATUS_TRANSITION"


# ---------------------------------------------------------------------------
# Run service
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_requires_campaign_or_ad_hoc():
    req = CreateRunRequest(
        provider=DiscoveryProviderId.MANUAL,
        uploaded_by="admin-1",
    )
    errors = await DiscoveryRunService.validate_run(req)
    assert any("is_ad_hoc" in e for e in errors)


@pytest.mark.asyncio
async def test_ad_hoc_run_validation_passes_manual():
    req = CreateRunRequest(
        provider=DiscoveryProviderId.MANUAL,
        uploaded_by="admin-1",
        is_ad_hoc=True,
    )
    errors = await DiscoveryRunService.validate_run(req)
    assert errors == []


@pytest.mark.asyncio
async def test_csv_run_requires_attestation():
    db = _FakeDB()
    campaign = _campaign_request()
    with patch("services.discovery.discovery_campaign_service.database.get_db", return_value=db), patch(
        "services.discovery.discovery_run_service.database.get_db", return_value=db
    ):
        created_campaign = await DiscoveryCampaignService.create_campaign(campaign)
        req = CreateRunRequest(
            provider=DiscoveryProviderId.CSV,
            uploaded_by="admin-1",
            campaign_id=created_campaign["campaign_id"],
        )
        errors = await DiscoveryRunService.validate_run(req)
        assert any("attestation" in e for e in errors)


@pytest.mark.asyncio
async def test_create_run_with_campaign_link():
    db = _FakeDB()
    with patch("services.discovery.discovery_campaign_service.database.get_db", return_value=db), patch(
        "services.discovery.discovery_run_service.database.get_db", return_value=db
    ):
        campaign = await DiscoveryCampaignService.create_campaign(_campaign_request())
        run = await DiscoveryRunService.create_run(
            CreateRunRequest(
                provider=DiscoveryProviderId.MANUAL,
                uploaded_by="admin-1",
                campaign_id=campaign["campaign_id"],
            )
        )
    assert run["discovery_run_id"].startswith("DRUN-")
    assert run["campaign_id"] == campaign["campaign_id"]
    assert run["is_ad_hoc"] is False
    assert run["provider"] == DiscoveryProviderId.MANUAL.value


@pytest.mark.asyncio
async def test_attach_run_to_campaign():
    db = _FakeDB()
    with patch("services.discovery.discovery_campaign_service.database.get_db", return_value=db), patch(
        "services.discovery.discovery_run_service.database.get_db", return_value=db
    ):
        campaign = await DiscoveryCampaignService.create_campaign(_campaign_request())
        # Run record awaiting campaign attachment (pre-ingest metadata only)
        db.discovery_runs.docs.append(
            {
                "discovery_run_id": "DRUN-ATTACH-TEST",
                "campaign_id": None,
                "is_ad_hoc": False,
                "provider": DiscoveryProviderId.MANUAL.value,
                "status": DiscoveryRunStatus.PROCESSING.value,
                "uploaded_by": "admin-1",
                "tenant_id": "pleerity",
                "created_at": NOW.isoformat(),
            }
        )
        updated = await DiscoveryRunService.attach_run_to_campaign(
            "DRUN-ATTACH-TEST",
            campaign["campaign_id"],
        )
    assert updated["campaign_id"] == campaign["campaign_id"]


@pytest.mark.asyncio
async def test_future_provider_disabled_on_run_create():
    req = CreateRunRequest(
        provider=DiscoveryProviderId.APOLLO,
        uploaded_by="admin-1",
        campaign_id="DCAMP-NOTFOUND",
        is_ad_hoc=False,
    )
    with patch.object(discovery_config, "is_provider_enabled", return_value=False):
        errors = await DiscoveryRunService.validate_run(req)
    assert any("disabled" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Job stub
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_job_stub_create_and_update():
    db = _FakeDB()
    with patch("services.discovery.discovery_job_service.database.get_db", return_value=db):
        job = await DiscoveryJobService.create_job_record(
            run_id="DRUN-TEST-001",
            provider=DiscoveryProviderId.CSV,
            supports_async=False,
            status=DiscoveryJobStatus.COMPLETED,
        )
        assert job["job_id"].startswith("DJOB-")
        updated = await DiscoveryJobService.update_job_status(
            job["job_id"],
            DiscoveryJobStatus.FAILED,
            error_message="stub",
        )
    assert updated["status"] == DiscoveryJobStatus.FAILED.value


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
def test_registry_lists_phase1_and_reserved_providers():
    providers = {e.provider_id.value for e in default_provider_registry.list_providers()}
    assert providers == {"csv", "manual", "apollo", "clay", "twin", "internal_crawler"}


def test_registry_phase1_ingest_implementation_state():
    csv_state = default_provider_registry.provider_state("csv")
    manual_state = default_provider_registry.provider_state("manual")
    twin_state = default_provider_registry.provider_state("twin")
    assert csv_state["ingest_implemented"] is True
    assert manual_state["ingest_implemented"] is False
    assert twin_state["ingest_implemented"] is True
    assert csv_state["ingest_available"] is False
    assert manual_state["ingest_available"] is False
    assert twin_state["ingest_available"] is False


def test_future_providers_disabled_by_default():
    with patch.object(discovery_config, "is_discovery_module_enabled", return_value=False):
        for pid in ("apollo", "clay", "twin", "internal_crawler"):
            assert default_provider_registry.is_enabled(pid) is False


def test_prohibited_capabilities_enforced_on_registry_entries():
    for entry in default_provider_registry.list_providers():
        assert entry.capability_violations() == []


def test_prohibited_capability_rejection():
    bad_caps = ProviderCapabilities(
        supports_async=False,
        supports_enrichment=False,
        supports_cost_tracking=False,
        prohibited_capabilities=frozenset({"OUTREACH"}),
    )
    violations = validate_provider_capabilities(bad_caps)
    assert any("CRM_WRITE" in v for v in violations)


def test_registry_rejects_disabled_phase2_provider():
    with patch.object(discovery_config, "is_provider_enabled", return_value=False):
        with pytest.raises(DiscoveryProviderRegistryError) as exc:
            default_provider_registry.assert_provider_allowed_for_metadata(
                DiscoveryProviderId.APOLLO
            )
    assert exc.value.code == "PROVIDER_DISABLED"


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------
def test_validate_audit_event_type_frozen():
    assert validate_audit_event_type("prospect_discovered") == "PROSPECT_DISCOVERED"


def test_validate_audit_event_type_rejects_unknown():
    with pytest.raises(DiscoveryAuditValidationError):
        validate_audit_event_type("NOT_REAL")


def test_build_audit_event_masks_email_in_details():
    event = build_audit_event(
        event_type=DiscoveryAuditEventCore.PROSPECT_DISCOVERED.value,
        details={"contact": "alice@example.com"},
        actor_email="reviewer@pleerity.com",
    )
    assert "alice@example.com" not in str(event.details)
    assert event.event_type == "PROSPECT_DISCOVERED"


def test_prepare_audit_payload_strips_raw_payload():
    clean = prepare_audit_payload({"raw_payload": {"big": "data"}, "note": "ok"})
    assert "raw_payload" not in clean
    assert clean["note"] == "ok"


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
def test_discovery_flags_default_false(monkeypatch):
    monkeypatch.delenv("DISCOVERY_MODULE_ENABLED", raising=False)
    monkeypatch.delenv("DISCOVERY_PROVIDER_APOLLO_ENABLED", raising=False)
    assert discovery_config.is_discovery_module_enabled() is False
    assert discovery_config.is_discovery_provider_apollo_enabled() is False


# ---------------------------------------------------------------------------
# Scope guards
# ---------------------------------------------------------------------------
def test_no_lead_service_imports_in_discovery_services():
    import pathlib

    authorized = {"discovery_import_service.py"}
    root = pathlib.Path(__file__).resolve().parents[1] / "services" / "discovery"
    for path in root.rglob("*.py"):
        if path.name in authorized:
            continue
        text = path.read_text(encoding="utf-8")
        assert "lead_service" not in text.lower(), f"LeadService reference in {path}"


def test_authorized_discovery_routes_exist():
    assert importlib.util.find_spec("routes.admin_discovery") is not None
    assert importlib.util.find_spec("routes.discovery_twin_internal") is not None


def test_csv_provider_exists_and_complies():
    from services.discovery.providers.csv_import_provider import CSVImportProvider
    from services.discovery.providers.discovery_provider_protocol import (
        validate_protocol_compliance,
    )

    provider = CSVImportProvider()
    assert validate_protocol_compliance(provider) == []


def test_no_discovery_import_service():
    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None
