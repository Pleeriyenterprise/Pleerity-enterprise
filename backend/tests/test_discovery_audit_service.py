"""
Stage L — discovery audit service tests.

Append-only audit persistence, retrieval, validation, and integrity.
No routes, UI, imports, LeadService, or workflow execution.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.discovery.discovery_audit_helpers import DiscoveryAuditValidationError
from services.discovery.discovery_audit_service import (
    DEFAULT_CONTENT_HASH_VERSION,
    DEFAULT_HASH_ALGORITHM,
    DEFAULT_SOURCE_METADATA_VERSION,
    AuditListFilters,
    DiscoveryAuditService,
    DiscoveryAuditServiceError,
)
from services.discovery.discovery_models import FROZEN_AUDIT_EVENT_VALUES

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
T0 = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 6, 1, 11, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
VALID_HASH = "a" * 64


class _AuditFakeCollection:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []
        self.insert_one = AsyncMock(side_effect=self._insert_one)
        self.find_one = AsyncMock(side_effect=self._find_one)
        self.find = MagicMock(side_effect=self._find)

    async def _insert_one(self, doc: Dict[str, Any]):
        stored = dict(doc)
        stored["_id"] = f"oid-{len(self.docs)}"
        self.docs.append(stored)
        return MagicMock(inserted_id=stored["_id"])

    async def _find_one(self, query, projection=None):
        for doc in self.docs:
            if self._match(doc, query):
                out = dict(doc)
                if projection and projection.get("_id") == 0:
                    out.pop("_id", None)
                return out
        return None

    def _find(self, query, projection=None):
        matches = []
        for doc in self.docs:
            if self._match(doc, query):
                out = dict(doc)
                if projection and projection.get("_id") == 0:
                    out.pop("_id", None)
                matches.append(out)

        class _Cursor:
            def __init__(self, items):
                self._items = items

            async def to_list(self, length):
                return self._items[:length]

        return _Cursor(matches)

    def _match(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if isinstance(expected, dict):
                if "$gte" in expected or "$lte" in expected:
                    value = str(doc.get(key) or "")
                    if "$gte" in expected and value < str(expected["$gte"]):
                        return False
                    if "$lte" in expected and value > str(expected["$lte"]):
                        return False
                elif doc.get(key) != expected:
                    return False
            elif doc.get(key) != expected:
                return False
        return True


class _AuditFakeDB:
    def __init__(self):
        self.discovery_audit_logs = _AuditFakeCollection()

    def __getitem__(self, name: str):
        return getattr(self, name)


@pytest.fixture
def audit_db():
    return _AuditFakeDB()


def _duplicate_snapshot(
    classification: str = "possible_duplicate",
    *,
    captured_at: datetime = T1,
) -> Dict[str, Any]:
    return DiscoveryAuditService.freeze_duplicate_evidence_snapshot(
        {
            "classification": classification,
            "evidence": [
                {
                    "evidence_type": "email_hash_match",
                    "matched_prospect_id": "PROSP-OTHER",
                    "confidence": "medium",
                }
            ],
            "primary_match_prospect_id": "PROSP-OTHER",
        },
        captured_at=captured_at,
    )


@pytest.mark.asyncio
async def test_create_audit_event(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        created = await DiscoveryAuditService.create_audit_event(
            event_type="PROSPECT_DISCOVERED",
            prospect_id="PROSP-001",
            run_id="DRUN-001",
            campaign_id="DCAMP-001",
            provider="manual",
            created_at=T0,
        )
    assert created["audit_id"]
    assert created["event_type"] == "PROSPECT_DISCOVERED"
    assert created["prospect_id"] == "PROSP-001"
    assert len(audit_db.discovery_audit_logs.docs) == 1


@pytest.mark.asyncio
async def test_get_audit_event(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        created = await DiscoveryAuditService.create_audit_event(
            event_type="PROSPECT_UPDATED",
            prospect_id="PROSP-001",
            run_id="DRUN-001",
            created_at=T0,
        )
        fetched = await DiscoveryAuditService.get_audit_event(created["audit_id"])
    assert fetched is not None
    assert fetched["audit_id"] == created["audit_id"]


@pytest.mark.asyncio
async def test_list_audit_events(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        for idx, ts in enumerate((T0, T1, T2)):
            await DiscoveryAuditService.create_audit_event(
                event_type="PROSPECT_UPDATED",
                prospect_id=f"PROSP-{idx}",
                run_id="DRUN-001",
                created_at=ts,
            )
        result = await DiscoveryAuditService.list_audit_events(limit=10)
    assert result.total == 3
    assert len(result.items) == 3
    assert result.items[0]["created_at"] >= result.items[1]["created_at"]


@pytest.mark.asyncio
async def test_list_prospect_audit_events(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        await DiscoveryAuditService.create_audit_event(
            event_type="PROSPECT_DISCOVERED",
            prospect_id="PROSP-A",
            run_id="DRUN-001",
            created_at=T0,
        )
        await DiscoveryAuditService.create_audit_event(
            event_type="PROSPECT_DISCOVERED",
            prospect_id="PROSP-B",
            run_id="DRUN-001",
            created_at=T1,
        )
        result = await DiscoveryAuditService.list_prospect_audit_events("PROSP-A")
    assert result.total == 1
    assert result.items[0]["prospect_id"] == "PROSP-A"


@pytest.mark.asyncio
async def test_list_run_audit_events(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        await DiscoveryAuditService.create_audit_event(
            event_type="RUN_CREATED",
            run_id="DRUN-001",
            campaign_id="DCAMP-001",
            created_at=T0,
        )
        await DiscoveryAuditService.create_audit_event(
            event_type="RUN_CREATED",
            run_id="DRUN-002",
            campaign_id="DCAMP-001",
            created_at=T1,
        )
        result = await DiscoveryAuditService.list_run_audit_events("DRUN-001")
    assert result.total == 1
    assert result.items[0]["run_id"] == "DRUN-001"


@pytest.mark.asyncio
async def test_list_campaign_audit_events(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        await DiscoveryAuditService.create_audit_event(
            event_type="RUN_CREATED",
            campaign_id="DCAMP-001",
            run_id="DRUN-001",
            created_at=T0,
        )
        await DiscoveryAuditService.create_audit_event(
            event_type="RUN_CREATED",
            campaign_id="DCAMP-002",
            run_id="DRUN-002",
            created_at=T1,
        )
        result = await DiscoveryAuditService.list_campaign_audit_events("DCAMP-001")
    assert result.total == 1
    assert result.items[0]["campaign_id"] == "DCAMP-001"


def test_validate_event_type_frozen_taxonomy():
    assert DiscoveryAuditService.validate_event_type("prospect_discovered") == "PROSPECT_DISCOVERED"
    with pytest.raises(DiscoveryAuditValidationError):
        DiscoveryAuditService.validate_event_type("NOT_A_REAL_EVENT")


def test_frozen_taxonomy_enforcement():
    assert DiscoveryAuditService.frozen_taxonomy_values() == FROZEN_AUDIT_EVENT_VALUES
    assert "PROSPECT_DISCOVERED" in DiscoveryAuditService.frozen_taxonomy_values()


@pytest.mark.asyncio
async def test_duplicate_evidence_snapshot_preserved(audit_db):
    snapshot = _duplicate_snapshot("possible_duplicate", captured_at=T1)
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        created = await DiscoveryAuditService.create_audit_event(
            event_type="DUPLICATE_DETECTED",
            prospect_id="PROSP-001",
            run_id="DRUN-001",
            actor_id="admin-1",
            duplicate_evidence_snapshot=snapshot,
            created_at=T1,
        )
    stored = created["details"]["duplicate_evidence_snapshot"]
    assert stored["classification"] == "possible_duplicate"
    assert stored["frozen"] is True
    assert stored["evidence"][0]["evidence_type"] == "email_hash_match"
    assert stored["content_hash_version"] == DEFAULT_CONTENT_HASH_VERSION
    assert stored["hash_algorithm"] == DEFAULT_HASH_ALGORITHM


@pytest.mark.asyncio
async def test_duplicate_detected_requires_snapshot(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        with pytest.raises(DiscoveryAuditServiceError) as exc:
            await DiscoveryAuditService.create_audit_event(
                event_type="DUPLICATE_DETECTED",
                prospect_id="PROSP-001",
                run_id="DRUN-001",
                actor_id="admin-1",
                created_at=T1,
            )
    assert exc.value.code == "DUPLICATE_EVIDENCE_REQUIRED"


def test_build_audit_summary():
    events = [
        {
            "audit_id": "AUD-1",
            "event_type": "PROSPECT_DISCOVERED",
            "prospect_id": "PROSP-001",
            "created_at": T0.isoformat(),
            "details": {"review_status": "needs_review"},
        },
        {
            "audit_id": "AUD-2",
            "event_type": "DUPLICATE_DETECTED",
            "prospect_id": "PROSP-001",
            "created_at": T1.isoformat(),
            "details": {
                "review_status": "duplicate_detected",
                "duplicate_evidence_snapshot": {
                    "classification": "possible_duplicate",
                    "evidence": [],
                    "captured_at": T1.isoformat(),
                    "frozen": True,
                },
            },
        },
        {
            "audit_id": "AUD-3",
            "event_type": "PROSPECT_UPDATED",
            "prospect_id": "PROSP-001",
            "created_at": T2.isoformat(),
            "details": {"review_status": "needs_review"},
        },
    ]
    summary = DiscoveryAuditService.build_audit_summary(events)
    assert summary["prospect_id"] == "PROSP-001"
    assert summary["event_count"] == 3
    assert summary["latest_status"] == "needs_review"
    assert summary["duplicate_classification"] == "possible_duplicate"
    assert summary["latest_event_type"] == "PROSPECT_UPDATED"
    assert "Prospect:" in summary["lines"]
    assert "PROSP-001" in summary["lines"]
    assert "12" not in summary["lines"]  # template uses actual count
    assert "3" in summary["lines"]


@pytest.mark.asyncio
async def test_pagination_deterministic(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        for idx in range(5):
            await DiscoveryAuditService.create_audit_event(
                event_type="PROSPECT_UPDATED",
                prospect_id="PROSP-001",
                run_id="DRUN-001",
                created_at=T0 + timedelta(minutes=idx),
            )
        page1 = await DiscoveryAuditService.list_prospect_audit_events(
            "PROSP-001", skip=0, limit=2
        )
        page2 = await DiscoveryAuditService.list_prospect_audit_events(
            "PROSP-001", skip=2, limit=2
        )
    assert page1.total == 5
    assert len(page1.items) == 2
    assert len(page2.items) == 2
    ids_page1 = {e["audit_id"] for e in page1.items}
    ids_page2 = {e["audit_id"] for e in page2.items}
    assert ids_page1.isdisjoint(ids_page2)


@pytest.mark.asyncio
async def test_invalid_event_rejection(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        with pytest.raises(DiscoveryAuditValidationError):
            await DiscoveryAuditService.create_audit_event(
                event_type="FAKE_EVENT",
                prospect_id="PROSP-001",
                run_id="DRUN-001",
            )


@pytest.mark.asyncio
async def test_actor_required_for_governance_events(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        with pytest.raises(DiscoveryAuditServiceError) as exc:
            await DiscoveryAuditService.create_audit_event(
                event_type="PROSPECT_APPROVED",
                prospect_id="PROSP-001",
                run_id="DRUN-001",
                created_at=T0,
            )
    assert exc.value.code == "INVALID_AUDIT_EVENT"
    assert "actor_id" in exc.value.message


@pytest.mark.asyncio
async def test_version_metadata_in_audit_context(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        created = await DiscoveryAuditService.create_audit_event(
            event_type="PROSPECT_DISCOVERED",
            prospect_id="PROSP-001",
            run_id="DRUN-001",
            content_hash=VALID_HASH,
            content_hash_version="2",
            hash_algorithm="sha256",
            source_metadata_version="1.1.0",
            created_at=T0,
        )
    ctx = created["details"]["audit_context"]
    assert ctx["content_hash_version"] == "2"
    assert ctx["hash_algorithm"] == "sha256"
    assert ctx["source_metadata_version"] == "1.1.0"
    assert ctx["content_hash"] == VALID_HASH


def test_build_audit_context_defaults():
    ctx = DiscoveryAuditService.build_audit_context(
        prospect_id="PROSP-001",
        discovery_run_id="DRUN-001",
    )
    assert ctx["content_hash_version"] == DEFAULT_CONTENT_HASH_VERSION
    assert ctx["hash_algorithm"] == DEFAULT_HASH_ALGORITHM
    assert ctx["source_metadata_version"] == DEFAULT_SOURCE_METADATA_VERSION


def test_validate_audit_event_rejects_malformed_duplicate_snapshot():
    event = {
        "audit_id": "AUD-TEST",
        "event_type": "DUPLICATE_DETECTED",
        "prospect_id": "PROSP-001",
        "run_id": "DRUN-001",
        "actor_id": "admin-1",
        "created_at": T0.isoformat(),
        "details": {
            "duplicate_evidence_snapshot": {"classification": "possible_duplicate"},
        },
    }
    errors = DiscoveryAuditService.validate_audit_event(event)
    assert any("duplicate_evidence_snapshot" in e for e in errors)


@pytest.mark.asyncio
async def test_filter_by_provider_actor_event_type_and_date(audit_db):
    with patch("services.discovery.discovery_audit_service.database") as mock_db:
        mock_db.get_db.return_value = audit_db
        await DiscoveryAuditService.create_audit_event(
            event_type="PROSPECT_DISCOVERED",
            prospect_id="PROSP-001",
            run_id="DRUN-001",
            provider="manual",
            actor_id="actor-1",
            created_at=T0,
        )
        await DiscoveryAuditService.create_audit_event(
            event_type="PROSPECT_UPDATED",
            prospect_id="PROSP-001",
            run_id="DRUN-001",
            provider="apollo",
            actor_id="actor-2",
            created_at=T2,
        )
        result = await DiscoveryAuditService.list_audit_events(
            AuditListFilters(
                provider="manual",
                actor_id="actor-1",
                event_type="PROSPECT_DISCOVERED",
                created_from=T0 - timedelta(hours=1),
                created_to=T1,
            )
        )
    assert result.total == 1
    assert result.items[0]["provider"] == "manual"


def test_no_update_operation_exists():
    text = (DISCOVERY_ROOT / "discovery_audit_service.py").read_text(encoding="utf-8")
    assert "update_audit_event" not in text
    assert "delete_audit_event" not in text
    assert "overwrite_audit_event" not in text
    assert "update_one" not in text
    assert "delete_one" not in text


def test_no_lead_service_changes():
    text = (DISCOVERY_ROOT / "discovery_audit_service.py").read_text(encoding="utf-8")
    assert "from services.lead_service import" not in text
    assert "LeadService.create_lead" not in text
    assert "LeadService.find_duplicate" not in text


def test_no_routes_ui_imports():
    assert importlib.util.find_spec("routes.admin_discovery") is not None
    assert importlib.util.find_spec("routes.discovery_twin_internal") is not None
    assert importlib.util.find_spec("services.discovery.discovery_import_service") is not None
    service_text = (DISCOVERY_ROOT / "discovery_audit_service.py").read_text(encoding="utf-8")
    assert "DiscoveryImportService" not in service_text
    assert "admin_discovery" not in service_text
