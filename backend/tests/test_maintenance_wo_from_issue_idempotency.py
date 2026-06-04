"""
F2 G9 remediation: maintenance issue → work order idempotency (client route + service).
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo.errors import DuplicateKeyError
from starlette.requests import Request

from database import database as db_singleton
from middleware import client_route_guard as middleware_client_route_guard
from server import app
from services.maintenance_wo_from_issue_idempotency import (
    build_wo_from_issue_fingerprint,
    wo_from_issue_abort,
    wo_from_issue_begin,
)
from services.ops_compliance_feature_flags import MAINTENANCE_WORKFLOWS

CLIENT_ID = "cli-idem-wo"
PORTAL_USER = "pu-idem-wo"
PROPERTY_ID = "prop-idem-wo"
ISSUE_ID = "issue-idem-wo"
WO_ID = "wo-idem-1"
WO_ID_2 = "wo-idem-2"


async def _fake_client_guard(request: Request):
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": PORTAL_USER,
        "role": "ROLE_CLIENT",
        "email": "idem-wo@test.com",
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
        if "fingerprint" in query:
            return dedupe_store.get(query.get("fingerprint"))
        if query.get("issue_id") == ISSUE_ID:
            return None
        return None

    async def update_one(query, update):
        row = dedupe_store.get(query.get("fingerprint"))
        if row and "$set" in update:
            row.update(update["$set"])

    async def delete_one(query):
        fp = query.get("fingerprint")
        row = dedupe_store.get(fp)
        if row and row.get("work_order_id") is None:
            dedupe_store.pop(fp, None)

    coll = MagicMock()
    coll.insert_one = AsyncMock(side_effect=insert_one)
    coll.find_one = AsyncMock(side_effect=find_one)
    coll.update_one = AsyncMock(side_effect=update_one)
    coll.delete_one = AsyncMock(side_effect=delete_one)
    coll.create_index = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=coll)
    wo_coll = MagicMock()
    wo_coll.find_one = AsyncMock(return_value=None)
    mock_db.work_orders = wo_coll
    return mock_db, coll


def test_fingerprint_stable_for_same_issue_intent():
    fp1 = build_wo_from_issue_fingerprint(
        client_id=CLIENT_ID,
        property_id=PROPERTY_ID,
        issue_id=ISSUE_ID,
        actor_id=PORTAL_USER,
    )
    fp2 = build_wo_from_issue_fingerprint(
        client_id=CLIENT_ID,
        property_id=PROPERTY_ID,
        issue_id=ISSUE_ID,
        actor_id=PORTAL_USER,
    )
    assert fp1 == fp2
    fp3 = build_wo_from_issue_fingerprint(
        client_id=CLIENT_ID,
        property_id=PROPERTY_ID,
        issue_id="other-issue",
        actor_id=PORTAL_USER,
    )
    assert fp1 != fp3


def test_wo_from_issue_begin_replay_when_fingerprint_has_work_order():
    async def _run():
        dedupe = {
            "fingerprint": "fp1",
            "client_id": CLIENT_ID,
            "work_order_id": WO_ID,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        coll = MagicMock()
        coll.insert_one = AsyncMock(side_effect=DuplicateKeyError("dup"))
        coll.find_one = AsyncMock(return_value=dedupe)
        coll.create_index = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=coll)
        wo_doc = {"work_order_id": WO_ID, "client_id": CLIENT_ID, "status": "OPEN", "issue_id": ISSUE_ID}
        with patch(
            "services.maintenance_wo_from_issue_idempotency.maintenance_service.get_work_order",
            AsyncMock(return_value=wo_doc),
        ):
            mode, doc = await wo_from_issue_begin(
                mock_db,
                fingerprint="fp1",
                client_id=CLIENT_ID,
                property_id=PROPERTY_ID,
            )
        assert mode == "replay"
        assert doc["work_order_id"] == WO_ID
        assert doc.get("idempotent_replay") is True

    asyncio.run(_run())


def test_http_duplicate_post_returns_same_work_order_id(http_client_guard_override, client):
    dedupe_store = {}
    created_count = {"n": 0}

    async def fake_create_wo_from_issue(**_kwargs):
        created_count["n"] += 1
        return {
            "work_order_id": WO_ID if created_count["n"] == 1 else WO_ID_2,
            "client_id": CLIENT_ID,
            "property_id": PROPERTY_ID,
            "issue_id": ISSUE_ID,
            "status": "OPEN",
        }

    mock_db, _coll = _mock_db_with_dedupe(dedupe_store)
    issue_doc = {
        "issue_id": ISSUE_ID,
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "status": "triaged",
        "description": "Leak",
    }
    flags = {MAINTENANCE_WORKFLOWS: True}
    wo_doc = {
        "work_order_id": WO_ID,
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "issue_id": ISSUE_ID,
        "status": "OPEN",
    }
    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.client_maintenance.client_route_guard", new=_fake_client_guard),
        patch(
            "routes.client_maintenance.get_effective_flags",
            new_callable=AsyncMock,
            return_value=flags,
        ),
        patch(
            "routes.client_maintenance.maintenance_issues_service.get_issue",
            AsyncMock(return_value=issue_doc),
        ),
        patch(
            "routes.client_maintenance.find_existing_work_order_for_issue",
            AsyncMock(return_value=None),
        ),
        patch(
            "routes.client_maintenance.maintenance_issues_service.create_work_order_from_issue",
            side_effect=fake_create_wo_from_issue,
        ),
        patch(
            "services.maintenance_wo_from_issue_idempotency.maintenance_service.get_work_order",
            AsyncMock(return_value=wo_doc),
        ),
    ):
        r1 = client.post(f"/api/client/maintenance/issues/{ISSUE_ID}/create-work-order")
        r2 = client.post(f"/api/client/maintenance/issues/{ISSUE_ID}/create-work-order")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["work_order_id"] == WO_ID
    assert r2.json()["work_order_id"] == WO_ID
    assert r2.json().get("idempotent_replay") is True
    assert created_count["n"] == 1


def test_http_replays_existing_linked_work_order_without_create(http_client_guard_override, client):
    existing = {
        "work_order_id": WO_ID,
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "issue_id": ISSUE_ID,
        "status": "OPEN",
        "idempotent_replay": True,
    }
    flags = {MAINTENANCE_WORKFLOWS: True}
    user = {
        "client_id": CLIENT_ID,
        "portal_user_id": PORTAL_USER,
        "role": "ROLE_CLIENT",
        "email": "idem-wo@test.com",
    }
    with (
        patch(
            "routes.client_maintenance._require_maintenance_enabled",
            new_callable=AsyncMock,
            return_value=user,
        ),
        patch(
            "routes.client_maintenance.get_effective_flags",
            new_callable=AsyncMock,
            return_value=flags,
        ),
        patch(
            "routes.client_maintenance.maintenance_issues_service.get_issue",
            AsyncMock(
                return_value={
                    "issue_id": ISSUE_ID,
                    "client_id": CLIENT_ID,
                    "property_id": PROPERTY_ID,
                    "status": "ready_for_work_order",
                }
            ),
        ),
        patch(
            "routes.client_maintenance.find_existing_work_order_for_issue",
            AsyncMock(return_value=existing),
        ),
        patch(
            "routes.client_maintenance.maintenance_issues_service.create_work_order_from_issue",
            AsyncMock(),
        ) as create_mock,
        patch(
            "services.operational_continuation_service.enrich_issue_with_continuation",
            AsyncMock(side_effect=lambda issue, _cid: issue),
        ),
        patch(
            "services.operational_continuation_service.resolve_continuation_for_issue",
            AsyncMock(return_value={}),
        ),
        patch(
            "services.operational_continuation_service.merge_continuation_into_payload",
            lambda wo, _cont: wo,
        ),
    ):
        r = client.post(f"/api/client/maintenance/issues/{ISSUE_ID}/create-work-order")

    assert r.status_code == 200
    assert r.json()["work_order_id"] == WO_ID
    assert r.json().get("idempotent_replay") is True
    create_mock.assert_not_awaited()


def test_wo_from_issue_abort_clears_inflight_slot():
    async def _run():
        coll = MagicMock()
        coll.delete_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=coll)
        await wo_from_issue_abort(mock_db, fingerprint="fp-abort")
        coll.delete_one.assert_awaited_once()

    asyncio.run(_run())
