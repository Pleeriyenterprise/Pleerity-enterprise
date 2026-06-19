"""
Stage T — DiscoveryErasureService tests.
"""
from __future__ import annotations

import hashlib
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery.discovery_erasure_service import (
    DiscoveryErasureService,
    DiscoveryErasureServiceError,
    LifecycleAttribution,
)
from services.discovery.discovery_import_service import (
    DiscoveryImportService,
    ImportAttribution,
)
from services.discovery.discovery_models import (
    DiscoveryErasureStatus,
    DiscoveryLawfulBasis,
    DiscoveryReviewStatus,
    is_frozen_audit_event,
)
from services.discovery.discovery_consent_service import DiscoveryConsentService

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
LEAD_SERVICE = DISCOVERY_ROOT.parent / "lead_service.py"
NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)

ATTR = LifecycleAttribution(
    actor_id="lifecycle-1",
    actor_email="lifecycle@pleerity.com",
    timestamp=NOW,
)

IMPORT_ATTR = ImportAttribution(
    actor_id="importer-1",
    actor_email="importer@pleerity.com",
    timestamp=NOW,
)


def _hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


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
            if all(doc.get(k) == v for k, v in query.items() if not str(k).startswith("$")):
                out = dict(doc)
                out.pop("_id", None)
                return out
        for doc in self.docs:
            if doc.get("prospect_id") == query.get("prospect_id"):
                out = dict(doc)
                out.pop("_id", None)
                return out
        return None

    async def _update_one(self, query, update):
        for doc in self.docs:
            if doc.get("prospect_id") == query.get("prospect_id"):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$unset" in update:
                    for key in update["$unset"]:
                        doc.pop(key, None)
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def _find(self, query, projection=None):
        matches = [dict(d) for d in self.docs]

        class _Cursor:
            async def to_list(self, length):
                return matches[:length]

        return _Cursor()


class _FakeDB:
    def __init__(self):
        self.discovery_prospects = _FakeCollection()
        self.discovery_suppression_records = _FakeCollection()
        self.discovery_audit_logs = _FakeCollection()

    def __getitem__(self, name: str):
        return getattr(self, name)


def _prospect_doc(**overrides) -> Dict[str, Any]:
    email = overrides.pop("email", "erase@example.com")
    doc = {
        "prospect_id": "PROSP-E-1",
        "campaign_id": "DCAMP-E",
        "discovery_run_id": "DRUN-E",
        "provider": "manual",
        "email": email,
        "phone": "+441234567890",
        "email_hash": _hash(email),
        "phone_hash": _hash("441234567890"),
        "content_hash": _hash("content"),
        "contact_name": "Pat",
        "company_name": "Co",
        "review_status": DiscoveryReviewStatus.APPROVED.value,
        "erasure_status": DiscoveryErasureStatus.ACTIVE.value,
        "legal_hold": False,
        "lawful_basis": DiscoveryLawfulBasis.CONSENT.value,
        "marketing_consent": False,
        "created_at": (NOW - timedelta(days=400)).isoformat().replace("+00:00", "Z"),
        "origin_lineage": [
            {
                "provider": "manual",
                "discovery_run_id": "DRUN-E",
                "ingested_at": "2026-06-01T12:00:00Z",
                "content_hash": _hash("content"),
            }
        ],
    }
    doc.update(overrides)
    return doc


def _db_patches(db: _FakeDB):
    modules = (
        "services.discovery.discovery_prospect_service",
        "services.discovery.discovery_audit_service",
        "services.discovery.discovery_erasure_service",
        "services.discovery.discovery_consent_service",
    )
    stack = ExitStack()
    for mod in modules:
        stack.enter_context(patch(f"{mod}.database.get_db", return_value=db))
    return stack


@pytest.fixture
def lifecycle_db():
    db = _FakeDB()
    return db


@pytest.mark.asyncio
async def test_request_erasure(lifecycle_db):
    await lifecycle_db.discovery_prospects.insert_one(_prospect_doc())
    with _db_patches(lifecycle_db):
        result = await DiscoveryErasureService.request_erasure("PROSP-E-1", ATTR)
    assert result["prospect"]["erasure_requested_at"]
    events = [a["event_type"] for a in lifecycle_db.discovery_audit_logs.docs]
    assert "ERASURE_REQUESTED" in events


@pytest.mark.asyncio
async def test_execute_erasure_anonymises_and_preserves_hashes(lifecycle_db):
    await lifecycle_db.discovery_prospects.insert_one(_prospect_doc())
    with _db_patches(lifecycle_db):
        result = await DiscoveryErasureService.execute_erasure("PROSP-E-1", ATTR)
    prospect = result["prospect"]
    assert prospect["erasure_status"] == DiscoveryErasureStatus.ERASED.value
    assert prospect["email"] is None
    assert prospect["contact_name"] == "[ERASED]"
    assert prospect["email_hash"]
    assert prospect["phone_hash"]
    assert prospect["content_hash"]
    errors = DiscoveryErasureService.verify_anonymisation(prospect)
    assert errors == []


@pytest.mark.asyncio
async def test_suppression_created_and_survives_erasure(lifecycle_db):
    await lifecycle_db.discovery_prospects.insert_one(_prospect_doc())
    with _db_patches(lifecycle_db):
        result = await DiscoveryErasureService.execute_erasure("PROSP-E-1", ATTR)
    assert result["suppression"]["active"] is True
    assert lifecycle_db.discovery_suppression_records.docs


@pytest.mark.asyncio
async def test_suppression_blocks_reimport(lifecycle_db):
    doc = _prospect_doc(prospect_id="PROSP-E-2", email="blocked@example.com")
    await lifecycle_db.discovery_prospects.insert_one(doc)
    with _db_patches(lifecycle_db):
        await DiscoveryErasureService.execute_erasure("PROSP-E-2", ATTR)
        check = await DiscoveryConsentService.check_suppression_lists(
            await lifecycle_db.discovery_prospects.find_one(
                {"prospect_id": "PROSP-E-2"}
            )
        )
    assert check.status == "blocked"


@pytest.mark.asyncio
async def test_audit_preserved_after_erasure(lifecycle_db):
    await lifecycle_db.discovery_prospects.insert_one(_prospect_doc())
    with _db_patches(lifecycle_db):
        await DiscoveryErasureService.request_erasure("PROSP-E-1", ATTR)
        await DiscoveryErasureService.execute_erasure("PROSP-E-1", ATTR)
    assert len(lifecycle_db.discovery_audit_logs.docs) >= 3


@pytest.mark.asyncio
async def test_apply_legal_hold(lifecycle_db):
    await lifecycle_db.discovery_prospects.insert_one(_prospect_doc())
    with _db_patches(lifecycle_db):
        result = await DiscoveryErasureService.apply_legal_hold(
            "PROSP-E-1", ATTR, hold_reason="Litigation hold"
        )
    assert result["prospect"]["legal_hold"] is True
    events = [a["event_type"] for a in lifecycle_db.discovery_audit_logs.docs]
    assert "LEGAL_HOLD_APPLIED" in events


@pytest.mark.asyncio
async def test_release_legal_hold(lifecycle_db):
    await lifecycle_db.discovery_prospects.insert_one(_prospect_doc(legal_hold=True))
    with _db_patches(lifecycle_db):
        result = await DiscoveryErasureService.release_legal_hold(
            "PROSP-E-1", ATTR, release_reason="Case closed"
        )
    assert result["prospect"]["legal_hold"] is False


@pytest.mark.asyncio
async def test_hold_blocks_erasure(lifecycle_db):
    await lifecycle_db.discovery_prospects.insert_one(_prospect_doc(legal_hold=True))
    with _db_patches(lifecycle_db):
        with pytest.raises(DiscoveryErasureServiceError):
            await DiscoveryErasureService.execute_erasure("PROSP-E-1", ATTR)


@pytest.mark.asyncio
async def test_hold_blocks_purge_evaluation(lifecycle_db):
    await lifecycle_db.discovery_prospects.insert_one(_prospect_doc(legal_hold=True))
    with _db_patches(lifecycle_db):
        purge = DiscoveryErasureService.determine_purge_eligibility(
            await lifecycle_db.discovery_prospects.find_one({"prospect_id": "PROSP-E-1"}),
            evaluated_at=NOW,
        )
    assert purge["eligible"] is False


@pytest.mark.asyncio
async def test_import_blocked_by_legal_hold(lifecycle_db):
    doc = _prospect_doc(legal_hold=True)
    await lifecycle_db.discovery_prospects.insert_one(doc)
    with _db_patches(lifecycle_db):
        result = await DiscoveryImportService.validate_import_eligibility(doc)
    assert result.eligible is False
    assert any("legal_hold" in r for r in result.blocking_reasons)


@pytest.mark.asyncio
async def test_evaluate_lifecycle_purge_emits_events(lifecycle_db):
    doc = _prospect_doc(review_status=DiscoveryReviewStatus.REJECTED.value)
    await lifecycle_db.discovery_prospects.insert_one(doc)
    with _db_patches(lifecycle_db):
        result = await DiscoveryErasureService.evaluate_lifecycle_purge(
            "PROSP-E-1", ATTR, evaluated_at=NOW
        )
    events = [a["event_type"] for a in lifecycle_db.discovery_audit_logs.docs]
    assert "RETENTION_EXPIRY_REACHED" in events
    assert "PURGE_ELIGIBLE" in events or "PURGE_BLOCKED" in events
    assert result["purge"]["retention_expiry_reached"] is True


def test_lifecycle_summary():
    prospect = _prospect_doc(
        review_status=DiscoveryReviewStatus.REJECTED.value,
        erasure_status=DiscoveryErasureStatus.ACTIVE.value,
    )
    summary = DiscoveryErasureService.build_lifecycle_summary(
        prospect, evaluated_at=NOW
    )
    assert "Retention:" in summary
    assert "Legal Hold:" in summary
    assert "Purge Eligibility:" in summary


def test_suppression_record_validation():
    ok = DiscoveryErasureService.validate_suppression_record(
        {
            "suppression_id": "DSUP-1",
            "email_hash": _hash("x"),
            "active": True,
        }
    )
    assert ok.valid is True


def test_erasure_summary():
    summary = DiscoveryErasureService.build_erasure_summary(_prospect_doc())
    assert "Erasure Status:" in summary


def test_scope_no_leadservice_changes():
    assert "DiscoveryErasureService" not in LEAD_SERVICE.read_text(encoding="utf-8")


def test_scope_no_provider_integrations():
    text = (DISCOVERY_ROOT / "discovery_erasure_service.py").read_text(encoding="utf-8")
    assert "csv_import_provider" not in text


def test_scope_no_routes_or_ui():
    for name in ("discovery_erasure_service.py", "discovery_retention_service.py"):
        text = (DISCOVERY_ROOT / name).read_text(encoding="utf-8")
        assert "APIRouter" not in text
        assert "FastAPI" not in text


def test_scope_no_notifications():
    text = (DISCOVERY_ROOT / "discovery_erasure_service.py").read_text(encoding="utf-8")
    assert "notification_service" not in text


def test_new_lifecycle_events_in_taxonomy():
    assert is_frozen_audit_event("ERASURE_EXECUTED")
    assert is_frozen_audit_event("PURGE_BLOCKED")
