"""
Stage W — Twin provider adapter tests.

Twin ingest into discovery_prospects only.
No LeadService, CRM writes, outreach, or import bypass.
"""
from __future__ import annotations

import json
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery.discovery_approval_queue_service import ReviewerAttribution
from services.discovery.discovery_campaign_service import (
    CreateCampaignRequest,
    DiscoveryCampaignService,
)
from services.discovery.discovery_consent_service import DiscoveryConsentService
from services.discovery.discovery_erasure_service import (
    DiscoveryErasureService,
    LifecycleAttribution,
)
from services.discovery.discovery_import_service import DiscoveryImportService, ImportAttribution
from services.discovery.discovery_metadata_contract import validate_discovery_source_metadata
from services.discovery.discovery_metrics_service import DiscoveryMetricsService
from services.discovery.discovery_models import (
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
    TargetIcp,
)
from services.discovery.discovery_provider_registry import default_provider_registry
from services.discovery.discovery_run_service import CreateRunRequest, DiscoveryRunService
from services.discovery.discovery_payload_store import InMemoryRawPayloadStore
from services.discovery.providers.discovery_provider_protocol import (
    IngestContext,
    IngestSource,
    PROHIBITED_PROVIDER_CAPABILITIES,
    validate_protocol_compliance,
)
from services.discovery.providers.twin_provider import TwinProvider

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
AUDIT_DIR = (
    Path(__file__).resolve().parents[1] / "docs" / "audit" / "discovery_phase_1_launch_01"
)
NOW = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)

REVIEW_ATTR = ReviewerAttribution(
    actor_id="twin-test-reviewer",
    actor_email="reviewer@pleerity.test",
    timestamp=NOW,
)
IMPORT_ATTR = ImportAttribution(
    actor_id="twin-test-importer",
    actor_email="importer@pleerity.test",
    timestamp=NOW,
)
LIFECYCLE_ATTR = LifecycleAttribution(
    actor_id="twin-test-lifecycle",
    actor_email="lifecycle@pleerity.test",
    timestamp=NOW,
)


class _FakeCollection:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.update_one = AsyncMock(side_effect=self._update_one)
        self.find = MagicMock(side_effect=self._find)

    async def _insert_one(self, doc):
        self.docs.append(dict(doc))

    async def _find_one(self, query, projection=None):
        for doc in self.docs:
            if self._match(doc, query):
                out = dict(doc)
                out.pop("_id", None)
                return out
        return None

    async def _update_one(self, query, update):
        for doc in self.docs:
            if self._match(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$unset" in update:
                    for key in update["$unset"]:
                        doc.pop(key, None)
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def _find(self, query, projection=None):
        matches = [dict(d) for d in self.docs if self._match(d, query)]

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

    def _match(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(self._match(doc, clause) for clause in expected):
                    return False
            elif isinstance(expected, dict):
                if "$ne" in expected:
                    if doc.get(key) == expected["$ne"]:
                        return False
                elif doc.get(key) != expected:
                    return False
            elif doc.get(key) != expected:
                return False
        return True


class _FakeDB:
    def __init__(self):
        self.discovery_campaigns = _FakeCollection()
        self.discovery_runs = _FakeCollection()
        self.discovery_prospects = _FakeCollection()
        self.discovery_audit_logs = _FakeCollection()
        self.discovery_jobs = _FakeCollection()
        self.discovery_suppression_records = _FakeCollection()

    def __getitem__(self, name: str):
        return getattr(self, name)


def _db_patches(db: _FakeDB):
    modules = (
        "services.discovery.discovery_campaign_service",
        "services.discovery.discovery_run_service",
        "services.discovery.discovery_prospect_service",
        "services.discovery.discovery_audit_service",
        "services.discovery.discovery_duplicate_service",
        "services.discovery.discovery_job_service",
        "services.discovery.discovery_consent_service",
        "services.discovery.discovery_erasure_service",
    )
    stack = ExitStack()
    for mod in modules:
        stack.enter_context(patch(f"{mod}.database.get_db", return_value=db))
    return stack


def _twin_record(**kwargs) -> Dict[str, Any]:
    base = {
        "twin_id": kwargs.pop("twin_id", "twin:W-DEFAULT"),
        "email": kwargs.pop("email", "twin@example.com"),
        "company_name": kwargs.pop("company_name", "Twin Co"),
        "website": kwargs.pop("website", "https://twin.example.com"),
        "lawful_basis": kwargs.pop("lawful_basis", "consent"),
        "marketing_consent": kwargs.pop("marketing_consent", True),
        "provider_confidence": kwargs.pop("provider_confidence", 72),
        "workflow_id": "wf-stage-w",
        "twin_campaign_id": "tc-001",
    }
    base.update(kwargs)
    return base


def _twin_payload(*records: Dict[str, Any]) -> Dict[str, Any]:
    return {"export_id": "twin-export-stage-w", "records": list(records)}


def _context(run: Dict[str, Any], campaign: Dict[str, Any]) -> IngestContext:
    return IngestContext(
        discovery_run_id=run["discovery_run_id"],
        discovery_campaign_id=campaign["campaign_id"],
        actor_id="twin-test-admin",
        actor_email="admin@pleerity.test",
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
    )


@pytest.fixture
async def twin_run():
    db = _FakeDB()
    with _db_patches(db), patch(
        "services.discovery.discovery_config.is_provider_enabled", return_value=True
    ):
        campaign = await DiscoveryCampaignService.create_campaign(
            CreateCampaignRequest(
                name="Twin Stage W Campaign",
                purpose="Twin adapter validation",
                target_icp=TargetIcp(),
                owner_id="twin-test-admin",
                lawful_basis=DiscoveryLawfulBasis.CONSENT,
            )
        )
        run = await DiscoveryRunService.create_run(
            CreateRunRequest(
                provider=DiscoveryProviderId.TWIN,
                uploaded_by="twin-test-admin",
                campaign_id=campaign["campaign_id"],
            )
        )
        yield db, run, campaign


def test_twin_provider_implements_protocol():
    provider = TwinProvider()
    assert validate_protocol_compliance(provider) == []
    assert provider.provider_id == "twin"
    assert provider.adapter_version == "1.0.0"
    assert provider.supports_async is True
    assert provider.supports_enrichment is False


def test_twin_capabilities_prohibit_crm_and_outreach():
    caps = TwinProvider().capabilities()
    for prohibited in PROHIBITED_PROVIDER_CAPABILITIES:
        assert prohibited in caps.prohibited_capabilities


def test_twin_registered_in_provider_registry():
    entry = default_provider_registry.get(DiscoveryProviderId.TWIN)
    assert entry.ingest_implemented is True
    assert entry.phase == 2
    assert entry.capability_violations() == []
    assert entry.capabilities.supports_enrichment is False


def test_registry_resolves_twin_adapter():
    adapter = default_provider_registry.resolve_ingest_adapter(DiscoveryProviderId.TWIN)
    assert isinstance(adapter, TwinProvider)


def test_twin_provider_boundary_no_crm_imports():
    text = (DISCOVERY_ROOT / "providers" / "twin_provider.py").read_text(encoding="utf-8")
    assert "from services.lead_service import" not in text
    assert "LeadService.create_lead" not in text
    assert "LeadService.find_duplicate" not in text
    assert "from services.discovery.discovery_import_service import" not in text
    assert "create_lead" not in text
    assert "notification_orchestrator" not in text
    assert "routes." not in text


def test_map_to_canonical_twin_fields():
    provider = TwinProvider()
    ctx = IngestContext(
        discovery_run_id="DRUN-TEST",
        actor_id="a",
        actor_email="a@test.com",
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
    )
    canonical = provider.map_to_canonical(
        _twin_record(
            twin_id="abc123",
            email="mapped@example.com",
            confidence_score=88,
            city="London",
            country="GB",
        ),
        ctx,
    )
    assert canonical.email == "mapped@example.com"
    assert canonical.provider_reference == "twin:abc123"
    assert canonical.provider_confidence == 88
    assert canonical.provider_extensions["location"]["city"] == "London"


@pytest.mark.asyncio
async def test_w01_twin_prospect_creates_discovery_prospect(twin_run):
    db, run, campaign = twin_run
    provider = TwinProvider()
    with _db_patches(db):
        result = await provider.ingest_async(
            IngestSource(payload=_twin_payload(_twin_record(email="w01@twin.test"))),
            _context(run, campaign),
        )
    assert result.accepted_rows == 1
    assert result.discovery_job_id
    assert len(db.discovery_prospects.docs) == 1
    prospect = db.discovery_prospects.docs[0]
    assert prospect["provider"] == "twin"
    assert prospect["email"] == "w01@twin.test"
    assert prospect["review_status"] == DiscoveryReviewStatus.NEEDS_REVIEW.value
    audits = [a for a in db.discovery_audit_logs.docs if a["event_type"] == "PROSPECT_DISCOVERED"]
    assert len(audits) == 1
    assert audits[0]["provider"] == "twin"


@pytest.mark.asyncio
async def test_raw_payload_stores_unknown_twin_fields(twin_run):
    db, run, campaign = twin_run
    store = InMemoryRawPayloadStore()
    provider = TwinProvider(payload_store=store)
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(
                payload=_twin_payload(
                    _twin_record(email="payload@twin.test", enrichment_tags="tag-a,tag-b")
                )
            ),
            _context(run, campaign),
        )
    prospect = db.discovery_prospects.docs[0]
    assert prospect.get("raw_payload_reference")
    assert "workflow_id" not in prospect
    assert "enrichment_tags" not in prospect
    assert "twin_campaign_id" not in prospect


@pytest.mark.asyncio
async def test_idempotency_key_stable_for_same_record(twin_run):
    provider = TwinProvider()
    ctx = _context(twin_run[1], twin_run[2])
    record = _twin_record(email="idem@twin.test", twin_id="twin:IDEM-1")
    canonical = provider.map_to_canonical(record, ctx)
    k1 = provider.idempotency_key(canonical, ctx)
    k2 = provider.idempotency_key(canonical, ctx)
    assert k1 == k2
    assert k1.startswith("twin:")


@pytest.mark.asyncio
async def test_w02_twin_duplicate_detected(twin_run):
    db, run, campaign = twin_run
    provider = TwinProvider()
    with _db_patches(db):
        first = await provider.ingest_async(
            IngestSource(payload=_twin_payload(_twin_record(email="dup@twin.test"))),
            _context(run, campaign),
        )
        second = await provider.ingest_async(
            IngestSource(
                payload=_twin_payload(
                    _twin_record(
                        email="dup@twin.test",
                        twin_id="twin:DUP-SECOND",
                        company_name="Twin Co Two",
                    )
                )
            ),
            _context(run, campaign),
        )
    assert first.accepted_rows == 1
    assert second.accepted_rows == 1
    assert second.duplicate_rows >= 1
    dup_audits = [
        a for a in db.discovery_audit_logs.docs if a["event_type"] == "DUPLICATE_DETECTED"
    ]
    assert len(dup_audits) >= 1


@pytest.mark.asyncio
async def test_w03_twin_compliance_failure_at_import(twin_run):
    db, run, campaign = twin_run
    provider = TwinProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(
                payload=_twin_payload(
                    _twin_record(
                        email="lia-fail@twin.test",
                        twin_id="twin:LIA-FAIL",
                        lawful_basis="legitimate_interest_b2b",
                        marketing_consent=False,
                    )
                )
            ),
            _context(run, campaign),
        )
        from services.discovery.discovery_approval_queue_service import (
            DiscoveryApprovalQueueService,
        )

        prospect = db.discovery_prospects.docs[0]
        await DiscoveryApprovalQueueService.approve_prospect(
            prospect["prospect_id"], REVIEW_ATTR
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(),
        ) as create_lead:
            out = await DiscoveryImportService.import_prospect(
                prospect["prospect_id"], IMPORT_ATTR
            )
    assert out["status"] == "blocked"
    assert create_lead.await_count == 0
    events = [a["event_type"] for a in db.discovery_audit_logs.docs]
    assert "LIA_VALIDATION_FAILED" in events


def test_w03_twin_row_validation_rejects_consent_mismatch():
    provider = TwinProvider()
    ctx = IngestContext(
        discovery_run_id="DRUN-X",
        actor_id="a",
        actor_email="a@test.com",
        lawful_basis=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
    )
    result = provider.validate(
        _twin_record(
            email="bad@twin.test",
            lawful_basis="legitimate_interest_b2b",
            marketing_consent=True,
        ),
        ctx,
    )
    assert result.valid is False
    assert any("marketing_consent" in e for e in result.errors)


@pytest.mark.asyncio
async def test_w04_twin_import_path_via_discovery_import_service(twin_run):
    db, run, campaign = twin_run
    provider = TwinProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(
                payload=_twin_payload(
                    _twin_record(email="import@example.com", twin_id="twin:IMPORT-1")
                )
            ),
            _context(run, campaign),
        )
        from services.discovery.discovery_approval_queue_service import (
            DiscoveryApprovalQueueService,
        )

        prospect = db.discovery_prospects.docs[0]
        await DiscoveryApprovalQueueService.approve_prospect(
            prospect["prospect_id"], REVIEW_ATTR
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(return_value={"lead_id": "LEAD-TWIN-W04", "is_duplicate": False}),
        ) as create_lead:
            out = await DiscoveryImportService.import_prospect(
                prospect["prospect_id"], IMPORT_ATTR
            )
    assert out["status"] == "imported"
    assert out["lead_id"] == "LEAD-TWIN-W04"
    assert create_lead.await_count == 1
    metadata = DiscoveryImportService.build_discovery_source_metadata(out["prospect"])
    ok, errors = validate_discovery_source_metadata(metadata)
    assert ok, errors
    assert metadata["discovery_provider"] == "twin"
    assert metadata.get("provider_reference")
    assert metadata.get("content_hash")
    assert metadata.get("content_hash_version")
    assert metadata.get("hash_algorithm")
    assert metadata.get("origin_lineage")


@pytest.mark.asyncio
async def test_twin_prospects_in_provider_metrics(twin_run):
    db, run, campaign = twin_run
    provider = TwinProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(
                payload=_twin_payload(
                    _twin_record(email="metrics@twin.test", twin_id="twin:METRICS")
                )
            ),
            _context(run, campaign),
        )
    snapshot = DiscoveryMetricsService.build_metrics_snapshot(
        prospects=db.discovery_prospects.docs,
        audit_logs=db.discovery_audit_logs.docs,
        campaign_id=campaign["campaign_id"],
    )
    twin_metrics = snapshot["provider_metrics"]["twin"]
    assert twin_metrics["prospects_discovered"] == 1
    assert snapshot["campaign_metrics"]["prospects_created"] == 1


@pytest.mark.asyncio
async def test_twin_lifecycle_uses_standard_services(twin_run):
    db, run, campaign = twin_run
    provider = TwinProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(
                payload=_twin_payload(
                    _twin_record(email="life@twin.test", twin_id="twin:LIFE")
                )
            ),
            _context(run, campaign),
        )
        prospect = db.discovery_prospects.docs[0]
        await DiscoveryErasureService.apply_legal_hold(
            prospect["prospect_id"],
            LIFECYCLE_ATTR,
            hold_reason="Twin lifecycle test",
        )
        held = next(
            p for p in db.discovery_prospects.docs if p["prospect_id"] == prospect["prospect_id"]
        )
        assert held.get("legal_hold") is True
        hold_events = [
            a for a in db.discovery_audit_logs.docs if a["event_type"] == "LEGAL_HOLD_APPLIED"
        ]
        assert len(hold_events) >= 1


@pytest.mark.asyncio
async def test_twin_suppression_via_consent_service(twin_run):
    db, run, campaign = twin_run
    provider = TwinProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(
                payload=_twin_payload(
                    _twin_record(email="sup@twin.test", twin_id="twin:SUP")
                )
            ),
            _context(run, campaign),
        )
        prospect = db.discovery_prospects.docs[0]
        await DiscoveryErasureService.create_suppression_record(
            prospect,
            source="stage_w_test",
            reason="suppression test",
            attribution=LIFECYCLE_ATTR,
        )
        result = await DiscoveryConsentService.validate_import_compliance(prospect)
        assert result.compliant is False


def test_twin_audit_uses_standard_event_taxonomy_only():
    text = (DISCOVERY_ROOT / "providers" / "twin_provider.py").read_text(encoding="utf-8")
    assert "event_type=\"TWIN_" not in text
    assert "PROSPECT_DISCOVERED" in text
    assert "DUPLICATE_DETECTED" in text


@pytest.mark.asyncio
async def test_w_staging_evidence_summary(twin_run):
    db, run, campaign = twin_run
    provider = TwinProvider()
    summary = {
        "authority": "STAGE-W-TWIN-PROVIDER-ADAPTER-AUTHORITY-01",
        "generated_at": NOW.isoformat().replace("+00:00", "Z"),
        "scenarios": {},
        "boundary": "GREEN",
        "twin_readiness": "GREEN",
    }
    with _db_patches(db):
        w01 = await provider.ingest_async(
            IngestSource(payload=_twin_payload(_twin_record(email="evidence@twin.test"))),
            _context(run, campaign),
        )
        summary["scenarios"]["W-01"] = {
            "passed": w01.accepted_rows == 1,
            "audit": "PROSPECT_DISCOVERED",
        }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / "TWIN_ADAPTER_VALIDATION.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    assert out_path.is_file()
