"""
Stage M — CSV import provider tests.

CSV ingest into discovery_prospects only.
No routes, UI, LeadService, import service, or notifications.
"""
from __future__ import annotations

import importlib.util
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery.discovery_campaign_service import (
    CreateCampaignRequest,
    DiscoveryCampaignService,
)
from services.discovery.discovery_models import (
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
    RunAttestation,
    TargetIcp,
    compute_content_hash,
)
from services.discovery.discovery_run_service import CreateRunRequest, DiscoveryRunService
from services.discovery.providers.csv_import_provider import (
    CSVImportProvider,
    CsvImportProviderError,
)
from services.discovery.providers.discovery_provider_protocol import (
    IngestContext,
    IngestSource,
    validate_protocol_compliance,
)
from services.discovery.discovery_payload_store import InMemoryRawPayloadStore

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)


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

    def __getitem__(self, name: str):
        return getattr(self, name)


def _attestation() -> RunAttestation:
    return RunAttestation(
        lawful_basis_declared=DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B,
        data_source_description="Test CSV upload",
        attested_by_id="admin-1",
        attested_by_email="admin@example.com",
        attested_at=NOW,
    )


def _db_patches(db: _FakeDB):
    modules = (
        "services.discovery.discovery_campaign_service",
        "services.discovery.discovery_run_service",
        "services.discovery.discovery_prospect_service",
        "services.discovery.discovery_audit_service",
        "services.discovery.discovery_duplicate_service",
    )
    stack = ExitStack()
    for mod in modules:
        stack.enter_context(patch(f"{mod}.database.get_db", return_value=db))
    return stack


@pytest.fixture
async def csv_run():
    db = _FakeDB()
    with _db_patches(db):
        campaign = await DiscoveryCampaignService.create_campaign(
            CreateCampaignRequest(
                name="CSV Campaign",
                purpose="Stage M",
                target_icp=TargetIcp(),
                owner_id="admin-1",
                lawful_basis=DiscoveryLawfulBasis.CONSENT,
            )
        )
        run = await DiscoveryRunService.create_run(
            CreateRunRequest(
                provider=DiscoveryProviderId.CSV,
                uploaded_by="admin-1",
                uploaded_by_email="admin@example.com",
                campaign_id=campaign["campaign_id"],
                attestation=_attestation(),
            )
        )
        yield db, run, campaign


def _context(run: Dict[str, Any], campaign: Dict[str, Any]) -> IngestContext:
    return IngestContext(
        discovery_run_id=run["discovery_run_id"],
        discovery_campaign_id=campaign["campaign_id"],
        actor_id="admin-1",
        actor_email="admin@example.com",
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
        attestation=_attestation(),
    )


@pytest.mark.asyncio
async def test_valid_csv_creates_discovery_prospects(csv_run):
    db, run, campaign = csv_run
    csv_text = (
        "email,company_name,website\n"
        "one@example.com,Acme One,https://one.example\n"
        "two@example.com,Acme Two,https://two.example\n"
    )
    provider = CSVImportProvider()
    with _db_patches(db):
        result = await provider.ingest_async(
            IngestSource(payload=csv_text, content_type="text/csv"),
            _context(run, campaign),
        )
    assert result.total_rows == 2
    assert result.accepted_rows == 2
    assert result.rejected_rows == 0
    assert len(result.created_prospect_ids) == 2
    assert len(db.discovery_prospects.docs) == 2
    assert all(p["provider"] == "csv" for p in db.discovery_prospects.docs)
    assert all(
        p["review_status"] == DiscoveryReviewStatus.NEEDS_REVIEW.value
        for p in db.discovery_prospects.docs
    )


@pytest.mark.asyncio
async def test_invalid_headers_rejected(csv_run):
    db, run, campaign = csv_run
    provider = CSVImportProvider()
    with _db_patches(db):
        with pytest.raises(CsvImportProviderError) as exc:
            await provider.ingest_async(
                IngestSource(payload="unknown_col\nvalue\n"),
                _context(run, campaign),
            )
    assert exc.value.code == "INVALID_HEADERS"


@pytest.mark.asyncio
async def test_unknown_columns_in_raw_payload_only(csv_run):
    db, run, campaign = csv_run
    store = InMemoryRawPayloadStore()
    csv_text = (
        "email,company_name,custom_field\n"
        "payload@example.com,Acme,custom-value\n"
    )
    provider = CSVImportProvider(payload_store=store)
    with _db_patches(db):
        result = await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    assert result.accepted_rows == 1
    prospect = db.discovery_prospects.docs[0]
    assert "custom_field" not in prospect
    ref = prospect["raw_payload_reference"]
    stored = store.get(ref)
    assert stored["unknown_columns"]["custom_field"] == "custom-value"


@pytest.mark.asyncio
async def test_missing_identity_rejected(csv_run):
    db, run, campaign = csv_run
    csv_text = "email,contact_name\n,Jane Doe\n"
    provider = CSVImportProvider()
    with _db_patches(db):
        result = await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    assert result.accepted_rows == 0
    assert result.rejected_rows == 1
    assert any("email" in e for err in result.errors for e in err.errors)


@pytest.mark.asyncio
async def test_missing_lawful_basis_rejected(csv_run):
    db, run, campaign = csv_run
    ctx = IngestContext(
        discovery_run_id=run["discovery_run_id"],
        discovery_campaign_id=campaign["campaign_id"],
        actor_id="admin-1",
        actor_email="admin@example.com",
        lawful_basis=DiscoveryLawfulBasis.UNKNOWN,
        attestation=_attestation(),
    )
    csv_text = "email,company_name\nnobasis@example.com,Acme\n"
    provider = CSVImportProvider()
    with _db_patches(db):
        result = await provider.ingest_async(
            IngestSource(payload=csv_text),
            ctx,
        )
    assert result.rejected_rows == 1
    assert any("lawful_basis" in e for err in result.errors for e in err.errors)


@pytest.mark.asyncio
async def test_marketing_consent_without_consent_rejected(csv_run):
    db, run, campaign = csv_run
    csv_text = (
        "email,company_name,marketing_consent,lawful_basis\n"
        "bad@example.com,Acme,true,legitimate_interest_b2b\n"
    )
    provider = CSVImportProvider()
    with _db_patches(db):
        result = await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    assert result.rejected_rows == 1
    assert any("marketing_consent" in e for err in result.errors for e in err.errors)


@pytest.mark.asyncio
async def test_provider_reference_validated(csv_run):
    db, run, campaign = csv_run
    csv_text = (
        "email,company_name,provider_reference\n"
        "ref@example.com,Acme,manual:bad-ref\n"
    )
    provider = CSVImportProvider()
    with _db_patches(db):
        result = await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    assert result.rejected_rows == 1
    assert any("provider_reference" in e for err in result.errors for e in err.errors)


@pytest.mark.asyncio
async def test_content_hash_created(csv_run):
    db, run, campaign = csv_run
    csv_text = "email,company_name\nhash@example.com,Acme Hash Co\n"
    provider = CSVImportProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    prospect = db.discovery_prospects.docs[0]
    assert prospect["content_hash"]
    assert len(prospect["content_hash"]) == 64


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_retry(csv_run):
    db, run, campaign = csv_run
    csv_text = "email,company_name\nretry@example.com,Retry Co\n"
    provider = CSVImportProvider()
    ctx = _context(run, campaign)
    with _db_patches(db):
        first = await provider.ingest_async(IngestSource(payload=csv_text), ctx)
        second = await provider.ingest_async(IngestSource(payload=csv_text), ctx)
    assert first.accepted_rows == 1
    assert second.accepted_rows == 0
    assert len(db.discovery_prospects.docs) == 1


@pytest.mark.asyncio
async def test_origin_lineage_populated(csv_run):
    db, run, campaign = csv_run
    csv_text = "email,company_name,source_url\n"
    csv_text += "line@example.com,Lineage Co,https://source.example/page\n"
    provider = CSVImportProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    lineage = db.discovery_prospects.docs[0]["origin_lineage"]
    assert len(lineage) == 1
    assert lineage[0]["provider"] == "csv"
    assert lineage[0]["discovery_run_id"] == run["discovery_run_id"]


@pytest.mark.asyncio
async def test_platform_quality_score_computed(csv_run):
    db, run, campaign = csv_run
    csv_text = (
        "email,phone,company_name,website,source_url\n"
        "score@example.com,07700900123,Score Co,https://score.example,"
        "https://source.example\n"
    )
    provider = CSVImportProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    score = db.discovery_prospects.docs[0]["platform_quality_score"]
    assert isinstance(score, int)
    assert 0 <= score <= 100


@pytest.mark.asyncio
async def test_duplicate_detection_and_audit_snapshot(csv_run):
    db, run, campaign = csv_run
    from services.discovery.discovery_models import email_hash, generate_prospect_id

    db.discovery_prospects.docs.append(
        {
            "prospect_id": generate_prospect_id(),
            "tenant_id": "pleerity",
            "discovery_run_id": "DRUN-OTHER",
            "provider": "manual",
            "email": "dup@example.com",
            "email_hash": email_hash("dup@example.com"),
            "company_name": "Existing Co",
            "content_hash": compute_content_hash({"email": "dup@example.com"}),
            "review_status": DiscoveryReviewStatus.NEEDS_REVIEW.value,
            "duplicate_status": "none",
            "erasure_status": "active",
        }
    )
    csv_text = "email,company_name\nDup@example.com,New Co\n"
    provider = CSVImportProvider()
    with _db_patches(db):
        result = await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    assert result.accepted_rows == 1
    assert result.duplicate_rows == 1
    dup_audits = [
        a for a in db.discovery_audit_logs.docs if a["event_type"] == "DUPLICATE_DETECTED"
    ]
    assert len(dup_audits) == 1
    snap = dup_audits[0]["details"]["duplicate_evidence_snapshot"]
    assert snap["frozen"] is True
    assert snap["classification"] in ("possible_duplicate", "confirmed_duplicate")


@pytest.mark.asyncio
async def test_audit_logs_created(csv_run):
    db, run, campaign = csv_run
    csv_text = "email,company_name\naudit@example.com,Audit Co\n"
    provider = CSVImportProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    discovered = [
        a for a in db.discovery_audit_logs.docs if a["event_type"] == "PROSPECT_DISCOVERED"
    ]
    assert len(discovered) == 1
    assert "raw_payload" not in discovered[0].get("details", {})


@pytest.mark.asyncio
async def test_raw_payload_not_stored_inline(csv_run):
    db, run, campaign = csv_run
    csv_text = "email,company_name,notes\ninline@example.com,Inline Co,secret note\n"
    provider = CSVImportProvider()
    with _db_patches(db):
        await provider.ingest_async(
            IngestSource(payload=csv_text),
            _context(run, campaign),
        )
    prospect = db.discovery_prospects.docs[0]
    assert prospect.get("raw_payload_reference")
    assert "notes" not in prospect
    assert "secret note" not in str(prospect)


def test_csv_provider_implements_protocol():
    provider = CSVImportProvider()
    assert validate_protocol_compliance(provider) == []
    assert provider.provider_id == "csv"
    assert provider.supports_async is False
    assert provider.supports_enrichment is False


def test_no_lead_service_calls():
    text = (DISCOVERY_ROOT / "providers" / "csv_import_provider.py").read_text(
        encoding="utf-8"
    )
    assert "from services.lead_service import" not in text
    assert "LeadService.create_lead" not in text
    assert "LeadService.find_duplicate" not in text


def test_no_routes_ui_import_service():
    assert importlib.util.find_spec("routes.admin_discovery") is not None
    assert importlib.util.find_spec("routes.discovery_twin_internal") is not None
    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None


def test_no_lead_creation_or_notifications():
    text = (DISCOVERY_ROOT / "providers" / "csv_import_provider.py").read_text(
        encoding="utf-8"
    )
    assert "create_lead" not in text
    assert "notification_orchestrator" not in text
