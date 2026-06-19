"""
Stage O — admin discovery review route tests.

Review workflow API only — no import, LeadService, or raw payload exposure.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from routes import admin_discovery
from server import app
from services.discovery import discovery_config
from services.discovery.discovery_campaign_service import (
    CreateCampaignRequest,
    DiscoveryCampaignService,
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

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
NOW = datetime(2026, 6, 18, 14, 0, 0, tzinfo=timezone.utc)

ADMIN_USER = {
    "portal_user_id": "admin-reviewer-1",
    "email": "reviewer@pleerity.com",
    "role": "ROLE_ADMIN",
}


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
                elif "$gte" in expected or "$lte" in expected:
                    val = str(doc.get(key) or "")
                    if "$gte" in expected and val < str(expected["$gte"]):
                        return False
                    if "$lte" in expected and val > str(expected["$lte"]):
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
    stack.enter_context(patch("database.database.get_db", return_value=db))
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
    raw_payload_reference: str = "payload-ref-secret",
) -> Dict[str, Any]:
    campaign = await DiscoveryCampaignService.create_campaign(
        CreateCampaignRequest(
            name="Camp",
            purpose="O route tests",
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
            company_name="Acme Ltd",
            review_status=DiscoveryReviewStatus.NEEDS_REVIEW,
        )
    )
    await db.discovery_prospects.update_one(
        {"prospect_id": prospect["prospect_id"]},
        {
            "$set": {
                "duplicate_status": duplicate_status,
                "platform_quality_score": quality,
                "review_priority": priority,
                "created_at": NOW.isoformat(),
                "review_status": review_status,
                "raw_payload_reference": raw_payload_reference,
                "raw_payload": {"secret": "must-not-leak"},
                "provider_raw_response": {"vendor": "secret"},
            }
        },
    )
    refreshed = await DiscoveryProspectService.get_prospect(prospect["prospect_id"])
    assert refreshed is not None
    return refreshed


async def _override_discovery_admin(request: Request):
    return ADMIN_USER


@pytest.fixture
def route_db():
    return _FakeDB()


@pytest.fixture
def client(route_db, monkeypatch):
    monkeypatch.setenv("DISCOVERY_MODULE_ENABLED", "true")
    app.dependency_overrides[admin_discovery._require_discovery_admin] = _override_discovery_admin
    with _db_patches(route_db):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


def _assert_no_forbidden_payloads(payload: Any):
    text = json.dumps(payload)
    for forbidden in (
        "raw_payload",
        "raw_row",
        "csv_row",
        "html_payload",
        "provider_raw_response",
        "payload-ref-secret",
        "must-not-leak",
    ):
        assert forbidden not in text


def test_no_import_route_exists():
    spec = importlib.util.spec_from_file_location(
        "admin_discovery_routes",
        Path(__file__).resolve().parents[1] / "routes" / "admin_discovery.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    paths = [getattr(r, "path", "") for r in module.router.routes]
    assert not any("import" in p.lower() for p in paths)
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "from services.lead" not in source.lower()
    assert "LeadService.create" not in source
    assert "discovery_import_service" not in source.lower()


def test_no_leadservice_calls_in_route_module():
    path = Path(__file__).resolve().parents[1] / "routes" / "admin_discovery.py"
    source = path.read_text(encoding="utf-8")
    assert "LeadService.create" not in source
    assert "from services.lead_service" not in source.lower()
    assert "discovery_import_service" not in source.lower()


@pytest.mark.asyncio
async def test_queue_route(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(route_db)
        res = client.get("/api/admin/discovery/review/queue")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["prospect_id"] == doc["prospect_id"])
    assert item["company_name"] == "Acme Ltd"
    assert item["has_email"] is True
    _assert_no_forbidden_payloads(body)


@pytest.mark.asyncio
async def test_summary_route(client, route_db):
    with _db_patches(route_db):
        await _seed_prospect(route_db)
        res = client.get("/api/admin/discovery/review/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_needs_review" in data
    assert "average_quality_score" in data


@pytest.mark.asyncio
async def test_detail_route(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(route_db)
        res = client.get(f"/api/admin/discovery/review/{doc['prospect_id']}")
    assert res.status_code == 200
    data = res.json()
    assert data["review_status"] == DiscoveryReviewStatus.NEEDS_REVIEW.value
    assert data["platform_quality_score"] == 80
    assert data["quality_breakdown"] is not None
    assert data["import_readiness_notice"].startswith("Import readiness only")
    assert "/audit" in data["audit_history_path"]
    _assert_no_forbidden_payloads(data)


@pytest.mark.asyncio
async def test_audit_route(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(route_db)
        res = client.get(f"/api/admin/discovery/review/{doc['prospect_id']}/audit")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "summary" in data


@pytest.mark.asyncio
async def test_approve_action(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(route_db)
        res = client.post(
            f"/api/admin/discovery/review/{doc['prospect_id']}/approve",
            json={},
        )
    assert res.status_code == 200
    assert res.json()["prospect"]["review_status"] == DiscoveryReviewStatus.APPROVED.value


@pytest.mark.asyncio
async def test_reject_action(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(route_db)
        res = client.post(
            f"/api/admin/discovery/review/{doc['prospect_id']}/reject",
            json={"reason_code": "low_quality", "notes": "Incomplete profile"},
        )
    assert res.status_code == 200
    assert res.json()["prospect"]["review_status"] == DiscoveryReviewStatus.REJECTED.value


@pytest.mark.asyncio
async def test_request_changes_action(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(route_db)
        res = client.post(
            f"/api/admin/discovery/review/{doc['prospect_id']}/request-changes",
            json={"change_request_notes": "Add company website"},
        )
    assert res.status_code == 200
    assert res.json()["prospect"]["review_status"] == DiscoveryReviewStatus.NEEDS_REVIEW.value


@pytest.mark.asyncio
async def test_mark_duplicate_no_match_returns_400(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(route_db, email="solo@example.com")
        res = client.post(
            f"/api/admin/discovery/review/{doc['prospect_id']}/mark-duplicate",
            json={},
        )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_clear_duplicate_action(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(
            route_db,
            duplicate_status=DiscoveryDuplicateStatus.POSSIBLE.value,
        )
        res = client.post(
            f"/api/admin/discovery/review/{doc['prospect_id']}/clear-duplicate",
            json={"reason_code": "reviewer_override", "notes": "False positive"},
        )
    assert res.status_code == 200
    assert res.json()["prospect"]["duplicate_status"] == DiscoveryDuplicateStatus.NONE.value


@pytest.mark.asyncio
async def test_archive_action(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(
            route_db,
            review_status=DiscoveryReviewStatus.APPROVED.value,
        )
        res = client.post(
            f"/api/admin/discovery/review/{doc['prospect_id']}/archive",
            json={},
        )
    assert res.status_code == 200
    assert res.json()["prospect"]["review_status"] == DiscoveryReviewStatus.ARCHIVED.value


def test_feature_flag_disabled(route_db, monkeypatch):
    monkeypatch.delenv("DISCOVERY_MODULE_ENABLED", raising=False)
    monkeypatch.setenv("DISCOVERY_MODULE_ENABLED", "false")
    with _db_patches(route_db):
        with TestClient(app) as c:
            res = c.get("/api/admin/discovery/review/queue")
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "DISCOVERY_MODULE_DISABLED"


def test_admin_auth_required(route_db, monkeypatch):
    monkeypatch.setenv("DISCOVERY_MODULE_ENABLED", "true")
    app.dependency_overrides.clear()
    with _db_patches(route_db):
        with TestClient(app) as c:
            res = c.get("/api/admin/discovery/review/queue")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_erased_pii_not_exposed(client, route_db):
    with _db_patches(route_db):
        doc = await _seed_prospect(route_db)
        await route_db.discovery_prospects.update_one(
            {"prospect_id": doc["prospect_id"]},
            {
                "$set": {
                    "erasure_status": DiscoveryErasureStatus.ERASED.value,
                    "email": None,
                    "phone": None,
                    "company_name": "[ERASED]",
                    "contact_name": "[ERASED]",
                    "raw_payload_reference": None,
                }
            },
        )
        res = client.get(f"/api/admin/discovery/review/{doc['prospect_id']}")
    assert res.status_code == 200
    data = res.json()
    assert data["prospect"].get("email") is None
    assert data["prospect"].get("company_name") == "[ERASED]"
    _assert_no_forbidden_payloads(data)


def test_production_flags_default_false(monkeypatch):
    monkeypatch.delenv("DISCOVERY_MODULE_ENABLED", raising=False)
    assert discovery_config.is_discovery_module_enabled() is False
