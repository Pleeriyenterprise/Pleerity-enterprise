"""
F1 G9 remediation: maintenance issue create idempotency (client route + service).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo.errors import DuplicateKeyError
from starlette.requests import Request

from database import database as db_singleton
from middleware import client_route_guard as middleware_client_route_guard
from server import app
from services.maintenance_issue_create_idempotency import (
    build_issue_create_fingerprint,
    issue_create_abort,
    issue_create_begin,
    normalize_issue_create_fields,
)
from services.ops_compliance_feature_flags import MAINTENANCE_WORKFLOWS

CLIENT_ID = "cli-idem-issue"
PORTAL_USER = "pu-idem-issue"
PROPERTY_ID = "prop-idem-1"
ISSUE_ID = "issue-idem-1"
ISSUE_ID_2 = "issue-idem-2"


async def _fake_client_guard(request: Request):
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": PORTAL_USER,
        "role": "ROLE_CLIENT",
        "email": "idem@test.com",
    }


@pytest.fixture
def http_client_guard_override():
    app.dependency_overrides[middleware_client_route_guard] = _fake_client_guard
    yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


def _mock_db_with_dedupe(dedupe_store: dict):
    async def insert_one(doc):
        fp = doc["fingerprint"]
        if fp in dedupe_store:
            raise DuplicateKeyError("dup")
        dedupe_store[fp] = dict(doc)

    async def find_one(query):
        return dedupe_store.get(query.get("fingerprint"))

    async def update_one(query, update):
        row = dedupe_store.get(query.get("fingerprint"))
        if row and "$set" in update:
            row.update(update["$set"])

    async def delete_one(query):
        fp = query.get("fingerprint")
        row = dedupe_store.get(fp)
        if row and row.get("issue_id") is None:
            dedupe_store.pop(fp, None)

    coll = MagicMock()
    coll.insert_one = AsyncMock(side_effect=insert_one)
    coll.find_one = AsyncMock(side_effect=find_one)
    coll.update_one = AsyncMock(side_effect=update_one)
    coll.delete_one = AsyncMock(side_effect=delete_one)
    coll.create_index = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=coll)
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": PROPERTY_ID})
    return mock_db, coll


def test_normalize_and_fingerprint_differs_by_description():
    d1, c1 = normalize_issue_create_fields("  Leak  under sink ", "plumbing")
    d2, c2 = normalize_issue_create_fields("Electrical fault", "electrical")
    assert d1 != d2
    fp1 = build_issue_create_fingerprint(
        client_id=CLIENT_ID,
        property_id=PROPERTY_ID,
        actor_id=PORTAL_USER,
        description="Leak under sink",
        category="plumbing",
    )
    fp2 = build_issue_create_fingerprint(
        client_id=CLIENT_ID,
        property_id=PROPERTY_ID,
        actor_id=PORTAL_USER,
        description="Electrical fault",
        category="electrical",
    )
    assert fp1 != fp2
    fp1b = build_issue_create_fingerprint(
        client_id=CLIENT_ID,
        property_id=PROPERTY_ID,
        actor_id=PORTAL_USER,
        description="  leak   under   sink ",
        category="plumbing",
    )
    assert fp1 == fp1b


def test_issue_create_begin_replay_when_fingerprint_has_issue():
    async def _run():
        dedupe = {
            "fingerprint": "fp1",
            "client_id": CLIENT_ID,
            "issue_id": ISSUE_ID,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        coll = MagicMock()
        coll.insert_one = AsyncMock(side_effect=DuplicateKeyError("dup"))
        coll.find_one = AsyncMock(return_value=dedupe)
        coll.create_index = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=coll)
        issue_doc = {"issue_id": ISSUE_ID, "client_id": CLIENT_ID, "status": "triaged"}
        with patch(
            "services.maintenance_issue_create_idempotency.maintenance_issues_service.get_issue",
            AsyncMock(return_value=issue_doc),
        ):
            mode, doc = await issue_create_begin(
                mock_db,
                fingerprint="fp1",
                client_id=CLIENT_ID,
                property_id=PROPERTY_ID,
            )
        assert mode == "replay"
        assert doc["issue_id"] == ISSUE_ID
        assert doc.get("idempotent_replay") is True

    asyncio.run(_run())


def test_issue_create_begin_allows_create_on_first_insert():
    async def _run():
        coll = MagicMock()
        coll.insert_one = AsyncMock()
        coll.create_index = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=coll)
        mode, doc = await issue_create_begin(
            mock_db,
            fingerprint="fp-new",
            client_id=CLIENT_ID,
            property_id=PROPERTY_ID,
        )
        assert mode == "create"
        assert doc is None

    asyncio.run(_run())


def test_http_duplicate_post_returns_same_issue_id(client, http_client_guard_override):
    """Rapid duplicate POST: second response is idempotent replay, single issue row created."""
    dedupe_store = {}
    created_count = {"n": 0}

    async def fake_create_issue(**_kwargs):
        created_count["n"] += 1
        return {
            "issue_id": ISSUE_ID if created_count["n"] == 1 else ISSUE_ID_2,
            "client_id": CLIENT_ID,
            "property_id": PROPERTY_ID,
            "status": "triaged",
            "description": "Duplicate probe",
        }

    mock_db, _coll = _mock_db_with_dedupe(dedupe_store)

    body = {
        "property_id": PROPERTY_ID,
        "description": "Duplicate probe",
        "category": "general",
    }

    async def fake_get_issue(issue_id, client_id=None):
        return {
            "issue_id": issue_id,
            "client_id": client_id,
            "property_id": PROPERTY_ID,
            "status": "triaged",
            "description": "Duplicate probe",
        }

    flags = {MAINTENANCE_WORKFLOWS: True}
    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.client_maintenance.client_route_guard", new=_fake_client_guard),
        patch(
            "routes.client_maintenance.get_effective_flags",
            new_callable=AsyncMock,
            return_value=flags,
        ),
        patch("routes.client_maintenance._enforce_maintenance_issue_create_rate_limit", AsyncMock()),
        patch("routes.client_maintenance.maintenance_issues_service.create_issue", side_effect=fake_create_issue),
        patch("services.maintenance_issue_create_idempotency.maintenance_issues_service.get_issue", side_effect=fake_get_issue),
        patch("routes.client_maintenance.create_audit_log", AsyncMock()),
    ):
        r1 = client.post("/api/client/maintenance/issues", json=body)
        r2 = client.post("/api/client/maintenance/issues", json=body)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["issue_id"] == ISSUE_ID
    assert r2.json()["issue_id"] == ISSUE_ID
    assert r2.json().get("idempotent_replay") is True
    assert created_count["n"] == 1


def test_http_different_description_creates_second_issue(client, http_client_guard_override):
    dedupe_store = {}
    call_n = {"n": 0}

    async def fake_create_issue(**kwargs):
        call_n["n"] += 1
        return {
            "issue_id": ISSUE_ID if call_n["n"] == 1 else ISSUE_ID_2,
            "client_id": CLIENT_ID,
            "property_id": PROPERTY_ID,
            "status": "triaged",
            "description": kwargs.get("description"),
        }

    mock_db, _coll = _mock_db_with_dedupe(dedupe_store)
    flags = {MAINTENANCE_WORKFLOWS: True}
    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.client_maintenance.client_route_guard", new=_fake_client_guard),
        patch(
            "routes.client_maintenance.get_effective_flags",
            new_callable=AsyncMock,
            return_value=flags,
        ),
        patch("routes.client_maintenance._enforce_maintenance_issue_create_rate_limit", AsyncMock()),
        patch("routes.client_maintenance.maintenance_issues_service.create_issue", side_effect=fake_create_issue),
        patch("routes.client_maintenance.create_audit_log", AsyncMock()),
    ):
        r1 = client.post(
            "/api/client/maintenance/issues",
            json={"property_id": PROPERTY_ID, "description": "First issue", "category": "general"},
        )
        r2 = client.post(
            "/api/client/maintenance/issues",
            json={"property_id": PROPERTY_ID, "description": "Second distinct issue", "category": "general"},
        )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["issue_id"] != r2.json()["issue_id"]
    assert call_n["n"] == 2


def test_issue_create_abort_clears_inflight_slot():
    async def _run():
        coll = MagicMock()
        coll.delete_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=coll)
        await issue_create_abort(mock_db, fingerprint="fp-abort")
        coll.delete_one.assert_awaited_once()

    asyncio.run(_run())
