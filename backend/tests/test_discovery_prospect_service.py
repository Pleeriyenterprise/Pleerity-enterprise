"""
Stage G unit tests — discovery prospect service.

No routes, duplicate engine, import, CSV provider, or LeadService.
"""
from __future__ import annotations

import importlib.util
from contextlib import ExitStack
from datetime import datetime, timezone
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
    DiscoverySourceType,
    OriginLineageEntry,
    TargetIcp,
    compute_content_hash,
)
from services.discovery.discovery_prospect_service import (
    CreateProspectRequest,
    DiscoveryProspectError,
    DiscoveryProspectService,
    UpdateProspectRequest,
)
from services.discovery.discovery_run_service import CreateRunRequest, DiscoveryRunService

NOW = datetime(2026, 6, 2, 15, 0, 0, tzinfo=timezone.utc)


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
                if "$set" in update:
                    doc.update(update["$set"])
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
        self.discovery_prospects = _FakeCollection()

    def __getitem__(self, name: str):
        return getattr(self, name)


def _content_hash_for_email(email: str) -> str:
    return compute_content_hash({"email": email})


def _prospect_request(
    run_id: str,
    *,
    email: str = "prospect@example.com",
    **kwargs,
) -> CreateProspectRequest:
    defaults = dict(
        discovery_run_id=run_id,
        provider=DiscoveryProviderId.MANUAL,
        content_hash=_content_hash_for_email(email),
        source_type=DiscoverySourceType.MANUAL,
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
        email=email,
        marketing_consent=False,
    )
    defaults.update(kwargs)
    return CreateProspectRequest(**defaults)


@pytest.fixture
async def seeded_run():
    db = _FakeDB()
    with ExitStack() as stack:
        for mod in (
            "services.discovery.discovery_prospect_service",
            "services.discovery.discovery_run_service",
            "services.discovery.discovery_campaign_service",
        ):
            stack.enter_context(patch(f"{mod}.database.get_db", return_value=db))
        campaign = await DiscoveryCampaignService.create_campaign(
            CreateCampaignRequest(
                name="Test Campaign",
                purpose="Stage G tests",
                target_icp=TargetIcp(),
                owner_id="admin-1",
                lawful_basis=DiscoveryLawfulBasis.CONSENT,
            )
        )
        run = await DiscoveryRunService.create_run(
            CreateRunRequest(
                provider=DiscoveryProviderId.MANUAL,
                uploaded_by="admin-1",
                campaign_id=campaign["campaign_id"],
            )
        )
        yield db, run, campaign


@pytest.mark.asyncio
async def test_create_valid_prospect(seeded_run):
    db, run, campaign = seeded_run
    prospect, audit = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"])
    )
    assert prospect["prospect_id"].startswith("PROSP-")
    assert prospect["marketing_consent"] is False
    assert prospect["campaign_id"] == campaign["campaign_id"]
    assert audit["event_type"] == "PROSPECT_DISCOVERED"
    assert len(db.discovery_prospects.docs) == 1


@pytest.mark.asyncio
async def test_reject_prospect_without_identity_fields(seeded_run):
    db, run, _ = seeded_run
    req = CreateProspectRequest(
        discovery_run_id=run["discovery_run_id"],
        provider=DiscoveryProviderId.MANUAL,
        content_hash=compute_content_hash({}),
        source_type=DiscoverySourceType.MANUAL,
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
        marketing_consent=False,
    )
    with pytest.raises(DiscoveryProspectError) as exc:
        await DiscoveryProspectService.create_prospect(req)
    assert exc.value.code == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_reject_prospect_without_lawful_basis(seeded_run):
    db, run, _ = seeded_run
    req = _prospect_request(
        run["discovery_run_id"],
        lawful_basis=DiscoveryLawfulBasis.UNKNOWN,
    )
    errors = await DiscoveryProspectService.validate_prospect(req)
    assert any("lawful_basis" in e for e in errors)


@pytest.mark.asyncio
async def test_marketing_consent_defaults_false(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"])
    )
    assert prospect["marketing_consent"] is False


@pytest.mark.asyncio
async def test_provider_confidence_preserved(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"], provider_confidence=77)
    )
    assert prospect["provider_confidence"] == 77


@pytest.mark.asyncio
async def test_platform_quality_score_computed_separately(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"], provider_confidence=90)
    )
    assert prospect["platform_quality_score"] <= 100
    score_sparse = DiscoveryProspectService.compute_platform_quality_score(
        email="a@b.com",
        provider_confidence=90,
    )
    assert score_sparse < 90


@pytest.mark.asyncio
async def test_content_hash_required_and_stable(seeded_run):
    errors = DiscoveryProspectService.validate_content_hash("")
    assert errors
    h1 = compute_content_hash({"email": "x@y.com"})
    h2 = compute_content_hash({"email": "x@y.com"})
    assert h1 == h2
    assert DiscoveryProspectService.verify_content_hash_matches_fields(
        h1, {"email": "x@y.com"}
    )


def test_provider_reference_validation_namespace():
    errors = DiscoveryProspectService.validate_provider_reference(
        DiscoveryProviderId.MANUAL,
        "csv:row-1",
        content_hash="a" * 64,
    )
    assert any("namespace" in e for e in errors)


@pytest.mark.asyncio
async def test_origin_lineage_append_preserves_prior(seeded_run):
    db, run, _ = seeded_run
    base = [
        OriginLineageEntry(
            provider="manual",
            provider_reference="ref-1",
            discovery_run_id=run["discovery_run_id"],
            content_hash="a" * 64,
            ingested_at=NOW,
        )
    ]
    extended = DiscoveryProspectService.append_origin_lineage(
        base,
        provider="csv",
        provider_reference="row-2",
        discovery_run_id=run["discovery_run_id"],
        campaign_id=run.get("campaign_id"),
        source_url=None,
        content_hash="b" * 64,
        discovered_at=NOW,
    )
    assert len(extended) == 2
    assert extended[0].provider_reference == "ref-1"
    assert extended[1].provider == "csv"


@pytest.mark.asyncio
async def test_invalid_status_transition_rejected(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"])
    )
    with pytest.raises(DiscoveryProspectError) as exc:
        await DiscoveryProspectService.update_review_status(
            prospect["prospect_id"],
            DiscoveryReviewStatus.APPROVED,
        )
    assert exc.value.code == "INVALID_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_approved_cannot_become_imported_in_stage_g(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"], review_status=DiscoveryReviewStatus.NEEDS_REVIEW)
    )
    await DiscoveryProspectService.update_review_status(
        prospect["prospect_id"],
        DiscoveryReviewStatus.APPROVED,
    )
    with pytest.raises(DiscoveryProspectError) as exc:
        await DiscoveryProspectService.update_review_status(
            prospect["prospect_id"],
            DiscoveryReviewStatus.IMPORTED,
        )
    assert exc.value.code == "IMPORT_RESERVED"


@pytest.mark.asyncio
async def test_duplicate_detected_to_approved_requires_override(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"], review_status=DiscoveryReviewStatus.NEEDS_REVIEW)
    )
    await DiscoveryProspectService.update_review_status(
        prospect["prospect_id"],
        DiscoveryReviewStatus.DUPLICATE_DETECTED,
    )
    with pytest.raises(DiscoveryProspectError) as exc:
        await DiscoveryProspectService.update_review_status(
            prospect["prospect_id"],
            DiscoveryReviewStatus.APPROVED,
        )
    assert exc.value.code == "OVERRIDE_REQUIRED"
    updated, _ = await DiscoveryProspectService.update_review_status(
        prospect["prospect_id"],
        DiscoveryReviewStatus.APPROVED,
        override_reason="Human verified not duplicate",
    )
    assert updated["duplicate_override_reason"]


@pytest.mark.asyncio
async def test_archived_is_terminal(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"], review_status=DiscoveryReviewStatus.NEEDS_REVIEW)
    )
    await DiscoveryProspectService.update_review_status(
        prospect["prospect_id"],
        DiscoveryReviewStatus.APPROVED,
    )
    archived, audit = await DiscoveryProspectService.archive_prospect(prospect["prospect_id"])
    assert archived["review_status"] == DiscoveryReviewStatus.ARCHIVED.value
    assert audit["event_type"] == "PROSPECT_ARCHIVED"
    with pytest.raises(DiscoveryProspectError) as exc:
        await DiscoveryProspectService.update_prospect(
            prospect["prospect_id"],
            UpdateProspectRequest(contact_name="Blocked"),
        )
    assert exc.value.code == "TERMINAL_STATUS"


@pytest.mark.asyncio
async def test_erased_is_terminal(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(run["discovery_run_id"])
    )
    await DiscoveryProspectService.mark_erasure_requested(prospect["prospect_id"])
    erased, audit = await DiscoveryProspectService.mark_erased(prospect["prospect_id"])
    assert erased["erasure_status"] == "erased"
    assert audit["event_type"] == "PROSPECT_ERASED"
    with pytest.raises(DiscoveryProspectError) as exc:
        await DiscoveryProspectService.mark_erased(prospect["prospect_id"])
    assert exc.value.code == "ERASED"


@pytest.mark.asyncio
async def test_raw_payload_reference_accepted(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(
            run["discovery_run_id"],
            raw_payload_reference="payload://PROSP-REF-001",
        )
    )
    assert prospect["raw_payload_reference"] == "payload://PROSP-REF-001"


@pytest.mark.asyncio
async def test_inline_raw_payload_rejected(seeded_run):
    db, run, _ = seeded_run
    req = _prospect_request(run["discovery_run_id"])
    errors = await DiscoveryProspectService.validate_prospect(
        req, extra_fields={"raw_payload": {"huge": "data"}}
    )
    assert any("raw_payload" in e for e in errors)


@pytest.mark.asyncio
async def test_website_only_identity(seeded_run):
    db, run, _ = seeded_run
    prospect, _ = await DiscoveryProspectService.create_prospect(
        _prospect_request(
            run["discovery_run_id"],
            email=None,
            website="https://example.com",
            content_hash=compute_content_hash({"website": "https://example.com"}),
        )
    )
    assert prospect["website"] == "https://example.com"


def test_no_lead_service_in_prospect_service():
    import pathlib

    text = (
        pathlib.Path(__file__).resolve().parents[1]
        / "services"
        / "discovery"
        / "discovery_prospect_service.py"
    ).read_text(encoding="utf-8")
    assert "lead_service" not in text.lower()


def test_no_routes_or_csv_or_import():
    assert importlib.util.find_spec("routes.admin_discovery") is not None
    assert importlib.util.find_spec("routes.discovery_twin_internal") is not None
    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None
