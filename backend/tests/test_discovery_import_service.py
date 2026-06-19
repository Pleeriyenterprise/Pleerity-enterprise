"""
Stage P — DiscoveryImportService tests.

Service-only import boundary; LeadService mocked.
"""
from __future__ import annotations

import hashlib
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery.discovery_approval_queue_service import (
    DiscoveryApprovalQueueService,
    ReviewerAttribution,
)
from services.discovery.discovery_campaign_service import (
    CreateCampaignRequest,
    DiscoveryCampaignService,
)
from services.discovery.discovery_import_service import (
    DiscoveryImportService,
    ImportAttribution,
)
from services.discovery.discovery_models import (
    DiscoveryDuplicateStatus,
    DiscoveryErasureStatus,
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
    DiscoverySourceType,
    TargetIcp,
)
from services.discovery.discovery_prospect_service import (
    CreateProspectRequest,
    DiscoveryProspectService,
)
from services.discovery.discovery_run_service import CreateRunRequest, DiscoveryRunService
from services.discovery import discovery_config

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
NOW = datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc)

ATTR = ImportAttribution(
    actor_id="importer-1",
    actor_email="importer@pleerity.com",
    timestamp=NOW,
)

REVIEW_ATTR = ReviewerAttribution(
    actor_id="reviewer-1",
    actor_email="reviewer@pleerity.com",
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
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def _find(self, query, projection=None):
        matches = [dict(d) for d in self.docs if self._match(d, query)]

        class _Cursor:
            def __init__(self, items):
                self._items = items

            async def to_list(self, length):
                return self._items[:length]

        return _Cursor(matches)

    def _match(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if doc.get(key) != expected:
                return False
        return True


class _FakeDB:
    def __init__(self):
        self.discovery_campaigns = _FakeCollection()
        self.discovery_runs = _FakeCollection()
        self.discovery_prospects = _FakeCollection()
        self.discovery_audit_logs = _FakeCollection()
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
        "services.discovery.discovery_approval_queue_service",
        "services.discovery.discovery_consent_service",
    )
    stack = ExitStack()
    for mod in modules:
        stack.enter_context(patch(f"{mod}.database.get_db", return_value=db))
    return stack


def _hash_for(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


async def _seed_prospect(
    db: _FakeDB,
    *,
    email: str = "import@example.com",
    review_status: str = DiscoveryReviewStatus.NEEDS_REVIEW.value,
    duplicate_status: str = DiscoveryDuplicateStatus.NONE.value,
    lawful_basis: str = DiscoveryLawfulBasis.CONSENT.value,
    marketing_consent: bool = True,
    erasure_status: str = DiscoveryErasureStatus.ACTIVE.value,
    duplicate_override_reason: str | None = None,
    imported_lead_id: str | None = None,
) -> Dict[str, Any]:
    campaign = await DiscoveryCampaignService.create_campaign(
        CreateCampaignRequest(
            name="Import Camp",
            purpose="Stage P",
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
    lb = DiscoveryLawfulBasis(lawful_basis)
    prospect, _ = await DiscoveryProspectService.create_prospect(
        CreateProspectRequest(
            discovery_run_id=run["discovery_run_id"],
            campaign_id=campaign["campaign_id"],
            provider=DiscoveryProviderId.MANUAL,
            content_hash=_hash_for(email),
            source_type=DiscoverySourceType.MANUAL,
            lawful_basis=lb,
            email=email,
            company_name="Import Co",
            marketing_consent=marketing_consent,
            review_status=DiscoveryReviewStatus.NEEDS_REVIEW,
        )
    )
    updates: Dict[str, Any] = {
        "duplicate_status": duplicate_status,
        "platform_quality_score": 85,
        "review_priority": 70,
        "created_at": NOW.isoformat(),
        "erasure_status": erasure_status,
        "review_status": review_status,
    }
    if duplicate_override_reason:
        updates["duplicate_override_reason"] = duplicate_override_reason
    if imported_lead_id:
        updates["imported_lead_id"] = imported_lead_id
    await db.discovery_prospects.update_one(
        {"prospect_id": prospect["prospect_id"]},
        {"$set": updates},
    )
    refreshed = await DiscoveryProspectService.get_prospect(prospect["prospect_id"])
    assert refreshed is not None
    return refreshed


async def _approve(db: _FakeDB, prospect_id: str) -> Dict[str, Any]:
    out = await DiscoveryApprovalQueueService.approve_prospect(
        prospect_id, REVIEW_ATTR
    )
    return out["prospect"]


@pytest.fixture
def import_db():
    return _FakeDB()


@pytest.mark.asyncio
async def test_approved_prospect_imports_successfully(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db)
        approved = await _approve(import_db, doc["prospect_id"])
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(return_value={"lead_id": "LEAD-TEST-001", "is_duplicate": False}),
        ) as create_lead:
            result = await DiscoveryImportService.import_prospect(
                approved["prospect_id"], ATTR
            )
    assert result["status"] == "imported"
    assert result["lead_id"] == "LEAD-TEST-001"
    assert result["prospect"]["review_status"] == DiscoveryReviewStatus.IMPORTED.value
    assert result["prospect"]["imported_lead_id"] == "LEAD-TEST-001"
    create_lead.assert_awaited_once()
    event_types = [a["event_type"] for a in import_db.discovery_audit_logs.docs]
    assert "IMPORT_REQUESTED" in event_types
    assert "IMPORT_VALIDATED" in event_types
    assert "PROSPECT_IMPORTED" in event_types


@pytest.mark.asyncio
async def test_unapproved_prospect_blocked(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db, review_status=DiscoveryReviewStatus.NEEDS_REVIEW.value)
        result = await DiscoveryImportService.import_prospect(doc["prospect_id"], ATTR)
    assert result["status"] == "blocked"
    assert any("IMPORT_BLOCKED" == a["event_type"] for a in import_db.discovery_audit_logs.docs)


@pytest.mark.asyncio
async def test_archived_prospect_blocked(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db, review_status=DiscoveryReviewStatus.ARCHIVED.value)
        result = await DiscoveryImportService.import_prospect(doc["prospect_id"], ATTR)
    assert result["status"] == "blocked"


@pytest.mark.asyncio
async def test_erased_prospect_blocked(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(
            import_db,
            review_status=DiscoveryReviewStatus.APPROVED.value,
            erasure_status=DiscoveryErasureStatus.ERASED.value,
        )
        result = await DiscoveryImportService.import_prospect(doc["prospect_id"], ATTR)
    assert result["status"] == "blocked"


@pytest.mark.asyncio
async def test_invalid_lawful_basis_blocked(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db, marketing_consent=False)
        await import_db.discovery_prospects.update_one(
            {"prospect_id": doc["prospect_id"]},
            {
                "$set": {
                    "review_status": DiscoveryReviewStatus.APPROVED.value,
                    "lawful_basis": DiscoveryLawfulBasis.UNKNOWN.value,
                }
            },
        )
        result = await DiscoveryImportService.import_prospect(doc["prospect_id"], ATTR)
    assert result["status"] == "blocked"


@pytest.mark.asyncio
async def test_marketing_consent_without_consent_basis_blocked(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(
            import_db,
            lawful_basis=DiscoveryLawfulBasis.CONSENT.value,
            marketing_consent=True,
        )
        await _approve(import_db, doc["prospect_id"])
        await import_db.discovery_prospects.update_one(
            {"prospect_id": doc["prospect_id"]},
            {
                "$set": {
                    "lawful_basis": DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
                    "marketing_consent": True,
                }
            },
        )
        result = await DiscoveryImportService.import_prospect(doc["prospect_id"], ATTR)
    assert result["status"] == "blocked"
    assert any(
        "marketing_consent" in r for r in result.get("blocking_reasons", [])
    )


@pytest.mark.asyncio
async def test_confirmed_duplicate_without_override_blocked(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(
            import_db,
            review_status=DiscoveryReviewStatus.APPROVED.value,
            duplicate_status=DiscoveryDuplicateStatus.CONFIRMED.value,
        )
        result = await DiscoveryImportService.import_prospect(doc["prospect_id"], ATTR)
    assert result["status"] == "blocked"


@pytest.mark.asyncio
async def test_already_imported_idempotent(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(
            import_db,
            review_status=DiscoveryReviewStatus.IMPORTED.value,
            imported_lead_id="LEAD-EXISTING",
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(),
        ) as create_lead:
            result = await DiscoveryImportService.import_prospect(
                doc["prospect_id"], ATTR
            )
    assert result["status"] == "idempotent"
    assert result["lead_id"] == "LEAD-EXISTING"
    create_lead.assert_not_awaited()


@pytest.mark.asyncio
async def test_metadata_contract_validates(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db)
        approved = await _approve(import_db, doc["prospect_id"])
        metadata = DiscoveryImportService.build_discovery_source_metadata(approved)
        errors = DiscoveryImportService.validate_metadata_contract(metadata)
    assert errors == []


@pytest.mark.asyncio
async def test_source_metadata_includes_required_fields(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db)
        approved = await _approve(import_db, doc["prospect_id"])
        metadata = DiscoveryImportService.build_discovery_source_metadata(approved)
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
        "quality_snapshot",
    ):
        assert field in metadata


@pytest.mark.asyncio
async def test_crm_duplicate_blocks_import(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db)
        approved = await _approve(import_db, doc["prospect_id"])
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value={"lead_id": "LEAD-DUP"}),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(),
        ) as create_lead:
            result = await DiscoveryImportService.import_prospect(
                approved["prospect_id"], ATTR
            )
    assert result["status"] == "blocked"
    assert result["lead_id"] == "LEAD-DUP"
    create_lead.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_lead_called_only_after_validation(import_db):
    find_mock = AsyncMock(return_value=None)
    create_mock = AsyncMock(
        return_value={"lead_id": "LEAD-ORDER-1", "is_duplicate": False}
    )
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db)
        approved = await _approve(import_db, doc["prospect_id"])
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=find_mock,
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=create_mock,
        ):
            result = await DiscoveryImportService.import_prospect(
                approved["prospect_id"], ATTR
            )
    assert result["status"] == "imported"
    find_mock.assert_awaited_once()
    create_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_leadservice_exception_audited(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db)
        approved = await _approve(import_db, doc["prospect_id"])
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(side_effect=RuntimeError("crm down")),
        ):
            result = await DiscoveryImportService.import_prospect(
                approved["prospect_id"], ATTR
            )
    assert result["status"] == "failed"
    assert any(a["event_type"] == "IMPORT_FAILED" for a in import_db.discovery_audit_logs.docs)


@pytest.mark.asyncio
async def test_prospect_update_failure_after_lead_creation(import_db):
    from services.discovery.discovery_prospect_service import DiscoveryProspectError

    with _db_patches(import_db):
        doc = await _seed_prospect(import_db)
        approved = await _approve(import_db, doc["prospect_id"])
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(return_value={"lead_id": "LEAD-ORPHAN", "is_duplicate": False}),
        ), patch(
            "services.discovery.discovery_import_service.DiscoveryProspectService.mark_imported",
            new=AsyncMock(
                side_effect=DiscoveryProspectError("DB", "db write failed")
            ),
        ):
            result = await DiscoveryImportService.import_prospect(
                approved["prospect_id"], ATTR
            )
    assert result["status"] == "failed"
    assert result["manual_reconciliation_required"] is True
    assert result["lead_id"] == "LEAD-ORPHAN"


@pytest.mark.asyncio
async def test_import_audit_chain_events(import_db):
    with _db_patches(import_db):
        doc = await _seed_prospect(import_db)
        approved = await _approve(import_db, doc["prospect_id"])
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(return_value={"lead_id": "LEAD-AUDIT", "is_duplicate": False}),
        ):
            await DiscoveryImportService.import_prospect(approved["prospect_id"], ATTR)
    types = {a["event_type"] for a in import_db.discovery_audit_logs.docs}
    assert {
        "IMPORT_REQUESTED",
        "IMPORT_VALIDATED",
        "PROSPECT_IMPORTED",
    } <= types


def test_no_provider_calls_in_import_service():
    text = (DISCOVERY_ROOT / "discovery_import_service.py").read_text(encoding="utf-8")
    assert "DiscoveryProvider" not in text
    assert "csv_import_provider" not in text
    assert "providers." not in text


def test_no_routes_in_import_service():
    text = (DISCOVERY_ROOT / "discovery_import_service.py").read_text(encoding="utf-8")
    assert "APIRouter" not in text
    assert "FastAPI" not in text


def test_no_notifications_in_import_service():
    text = (DISCOVERY_ROOT / "discovery_import_service.py").read_text(encoding="utf-8")
    assert "send_notification" not in text.lower()
    assert "notification_service" not in text.lower()


def test_only_import_service_calls_create_lead_in_discovery():
    for path in DISCOVERY_ROOT.glob("*.py"):
        if path.name == "discovery_import_service.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "await LeadService.create_lead" not in text, path.name


def test_production_flags_remain_false(monkeypatch):
    monkeypatch.delenv("DISCOVERY_MODULE_ENABLED", raising=False)
    assert discovery_config.is_discovery_module_enabled() is False


def test_build_lead_payload_tags(import_db):
    prospect = {
        "prospect_id": "PROSP-1",
        "discovery_run_id": "DRUN-1",
        "provider": "manual",
        "email": "a@b.com",
        "marketing_consent": False,
        "lawful_basis": "consent",
        "content_hash": "a" * 64,
        "created_at": NOW.isoformat(),
    }
    meta = DiscoveryImportService.build_discovery_source_metadata(prospect)
    payload = DiscoveryImportService.build_lead_create_payload(
        prospect, discovery_metadata=meta
    )
    assert payload.source_platform.value == "IMPORT"
    assert "discovery_import_v1" in (payload.tags or [])
    assert payload.source_metadata["discovery"]["schema_version"] == "1.0.0"
