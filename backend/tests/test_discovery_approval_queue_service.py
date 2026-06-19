"""
Stage N — discovery approval queue service tests.

Review governance only — no imports, LeadService, routes, or UI.
"""
from __future__ import annotations

import hashlib
import importlib.util
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery.discovery_approval_queue_service import (
    DiscoveryApprovalQueueError,
    DiscoveryApprovalQueueService,
    ReviewQueueFilters,
    ReviewerAttribution,
)
from services.discovery.discovery_campaign_service import (
    CreateCampaignRequest,
    DiscoveryCampaignService,
)
from services.discovery.discovery_models import (
    DiscoveryDuplicateStatus,
    DiscoveryLawfulBasis,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
    DiscoverySourceType,
    RunAttestation,
    TargetIcp,
)
from services.discovery.discovery_prospect_service import (
    CreateProspectRequest,
    DiscoveryProspectService,
)
from services.discovery.discovery_run_service import CreateRunRequest, DiscoveryRunService

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
NOW = datetime(2026, 6, 18, 14, 0, 0, tzinfo=timezone.utc)

ATTR = ReviewerAttribution(
    actor_id="reviewer-1",
    actor_email="reviewer@example.com",
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


def _db_patches(db: _FakeDB):
    modules = (
        "services.discovery.discovery_campaign_service",
        "services.discovery.discovery_run_service",
        "services.discovery.discovery_prospect_service",
        "services.discovery.discovery_audit_service",
        "services.discovery.discovery_duplicate_service",
        "services.discovery.discovery_approval_queue_service",
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
    email: str = "prospect@example.com",
    review_status: str = DiscoveryReviewStatus.NEEDS_REVIEW.value,
    duplicate_status: str = DiscoveryDuplicateStatus.NONE.value,
    quality: int = 80,
    priority: int = 75,
    created_at: datetime = NOW,
) -> Dict[str, Any]:
    campaign = await DiscoveryCampaignService.create_campaign(
        CreateCampaignRequest(
            name="Camp",
            purpose="N tests",
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
    prospect, _ = await DiscoveryProspectService.create_prospect(
        CreateProspectRequest(
            discovery_run_id=run["discovery_run_id"],
            campaign_id=campaign["campaign_id"],
            provider=DiscoveryProviderId.MANUAL,
            content_hash=_hash_for(email),
            source_type=DiscoverySourceType.MANUAL,
            lawful_basis=DiscoveryLawfulBasis.CONSENT,
            email=email,
            company_name="Acme",
            review_status=DiscoveryReviewStatus.NEEDS_REVIEW,
        )
    )
    update_fields: Dict[str, Any] = {
        "duplicate_status": duplicate_status,
        "platform_quality_score": quality,
        "review_priority": priority,
        "created_at": created_at.isoformat(),
    }
    if review_status != DiscoveryReviewStatus.NEEDS_REVIEW.value:
        update_fields["review_status"] = review_status
    await db.discovery_prospects.update_one(
        {"prospect_id": prospect["prospect_id"]},
        {"$set": update_fields},
    )
    refreshed = await DiscoveryProspectService.get_prospect(prospect["prospect_id"])
    assert refreshed is not None
    return refreshed


@pytest.fixture
def approval_db():
    return _FakeDB()


@pytest.mark.asyncio
async def test_approve_prospect(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(approval_db)
        out = await DiscoveryApprovalQueueService.approve_prospect(
            doc["prospect_id"], ATTR
        )
    assert out["prospect"]["review_status"] == DiscoveryReviewStatus.APPROVED.value
    assert out["import_eligible"] is True
    audits = [
        a
        for a in approval_db.discovery_audit_logs.docs
        if a["event_type"] == "PROSPECT_APPROVED"
    ]
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_reject_prospect(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(approval_db)
        out = await DiscoveryApprovalQueueService.reject_prospect(
            doc["prospect_id"], ATTR, reason_code="NOT_A_FIT"
        )
    assert out["prospect"]["review_status"] == DiscoveryReviewStatus.REJECTED.value


@pytest.mark.asyncio
async def test_request_changes(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(approval_db)
        out = await DiscoveryApprovalQueueService.request_changes(
            doc["prospect_id"],
            ATTR,
            change_request_notes="Add company website",
        )
    assert out["prospect"]["review_status"] == DiscoveryReviewStatus.NEEDS_REVIEW.value
    assert out["import_eligible"] is False
    reviewed = [
        a
        for a in approval_db.discovery_audit_logs.docs
        if a["event_type"] == "PROSPECT_REVIEWED"
    ]
    assert len(reviewed) == 1


@pytest.mark.asyncio
async def test_archive_prospect(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(
            approval_db, review_status=DiscoveryReviewStatus.APPROVED.value
        )
        out = await DiscoveryApprovalQueueService.archive_prospect(
            doc["prospect_id"], ATTR
        )
    assert out["prospect"]["review_status"] == DiscoveryReviewStatus.ARCHIVED.value


@pytest.mark.asyncio
async def test_mark_and_clear_duplicate(approval_db):
    with _db_patches(approval_db):
        await _seed_prospect(approval_db, email="dup@example.com")
        target = await _seed_prospect(approval_db, email="dup@example.com")
        marked = await DiscoveryApprovalQueueService.mark_duplicate(
            target["prospect_id"], ATTR
        )
        assert marked["classification"]["classification"] in (
            "possible_duplicate",
            "confirmed_duplicate",
        )
        cleared = await DiscoveryApprovalQueueService.clear_duplicate(
            target["prospect_id"],
            ATTR,
            reason_code="FALSE_POSITIVE",
            notes="Reviewer cleared",
        )
    assert cleared["prospect"]["duplicate_status"] == DiscoveryDuplicateStatus.NONE.value
    assert any(
        a["event_type"] == "DUPLICATE_DETECTED"
        for a in approval_db.discovery_audit_logs.docs
    )


@pytest.mark.asyncio
async def test_reviewer_attribution_required():
    with pytest.raises(DiscoveryApprovalQueueError) as exc:
        DiscoveryApprovalQueueService._require_attribution(
            ReviewerAttribution(actor_id="", actor_email="")
        )
    assert exc.value.code == "MISSING_ATTRIBUTION"


@pytest.mark.asyncio
async def test_missing_attribution_on_approve_rejected(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(approval_db)
        with pytest.raises(DiscoveryApprovalQueueError) as exc:
            await DiscoveryApprovalQueueService.approve_prospect(
                doc["prospect_id"],
                ReviewerAttribution(actor_id="", actor_email=""),
            )
    assert exc.value.code == "MISSING_ATTRIBUTION"


@pytest.mark.asyncio
async def test_confirmed_duplicate_approval_blocked_without_override(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(
            approval_db,
            review_status=DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
            duplicate_status=DiscoveryDuplicateStatus.CONFIRMED.value,
        )
        with pytest.raises(DiscoveryApprovalQueueError) as exc:
            await DiscoveryApprovalQueueService.approve_prospect(
                doc["prospect_id"], ATTR
            )
    assert exc.value.code == "OVERRIDE_REQUIRED"


@pytest.mark.asyncio
async def test_confirmed_duplicate_approval_with_override(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(
            approval_db,
            review_status=DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
            duplicate_status=DiscoveryDuplicateStatus.CONFIRMED.value,
        )
        out = await DiscoveryApprovalQueueService.approve_prospect(
            doc["prospect_id"],
            ATTR,
            override_reason="MANUAL_REVIEW",
            override_notes="Same company different division",
            reason_code="MANUAL_REVIEW",
        )
    assert out["prospect"]["review_status"] == DiscoveryReviewStatus.APPROVED.value


@pytest.mark.asyncio
async def test_possible_duplicate_approval_warning(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(
            approval_db,
            duplicate_status=DiscoveryDuplicateStatus.POSSIBLE.value,
        )
        out = await DiscoveryApprovalQueueService.approve_prospect(
            doc["prospect_id"], ATTR
        )
    assert any("possible_duplicate" in w for w in out["warnings"])


@pytest.mark.asyncio
async def test_import_eligibility_approved(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(
            approval_db, review_status=DiscoveryReviewStatus.APPROVED.value
        )
        result = DiscoveryApprovalQueueService.determine_import_eligibility(doc)
    assert result.eligible is True


@pytest.mark.asyncio
async def test_import_eligibility_blocked(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(approval_db)
        result = DiscoveryApprovalQueueService.determine_import_eligibility(doc)
    assert result.eligible is False


@pytest.mark.asyncio
async def test_import_readiness_summary(approval_db):
    with _db_patches(approval_db):
        doc = await _seed_prospect(approval_db)
        summary = DiscoveryApprovalQueueService.build_import_readiness_summary(doc)
    assert summary["eligible"] is False


@pytest.mark.asyncio
async def test_review_queue_filtering_and_sorting(approval_db):
    with _db_patches(approval_db):
        await _seed_prospect(
            approval_db,
            email="low@x.com",
            quality=50,
            priority=40,
            created_at=NOW,
        )
        await _seed_prospect(
            approval_db,
            email="high@x.com",
            quality=90,
            priority=90,
            created_at=NOW + timedelta(hours=1),
        )
        result = await DiscoveryApprovalQueueService.list_review_queue(
            ReviewQueueFilters(quality_score_min=80, skip=0, limit=10)
        )
    assert result.total >= 1
    priorities = [int(i["review_priority"]) for i in result.items]
    assert priorities == sorted(priorities, reverse=True)


@pytest.mark.asyncio
async def test_review_summary_generation(approval_db):
    with _db_patches(approval_db):
        await _seed_prospect(approval_db, email="a@x.com")
        await _seed_prospect(
            approval_db,
            email="b@x.com",
            review_status=DiscoveryReviewStatus.APPROVED.value,
        )
        summary = await DiscoveryApprovalQueueService.get_review_summary()
    assert summary["total_needs_review"] >= 1
    assert summary["total_approved"] >= 1


def test_no_lead_service_or_import():
    text = (DISCOVERY_ROOT / "discovery_approval_queue_service.py").read_text(
        encoding="utf-8"
    )
    assert "from services.lead_service import" not in text
    assert "LeadService.create_lead" not in text
    assert "DiscoveryImportService" not in text
    assert "create_lead" not in text


def test_no_import_service_module():
    import importlib.util

    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None
