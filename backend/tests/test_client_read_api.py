"""Client read API: management (JWT) and data plane (ple_read_ API keys)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
CLIENT_ID = "read-api-test-client"


def _contract(*, plan="PLAN_3_PRO"):
    return build_runtime_contract(
        client={"client_id": CLIENT_ID, "billing_plan": plan, "subscription_status": "ACTIVE"},
        billing={
            "client_id": CLIENT_ID,
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "active",
            "canonical_entitlement_state": "ENABLED",
        },
        now=NOW,
    )


def _mock_evaluate(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


@pytest.fixture
def client_user():
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": "pu-read-api-1",
        "role": "ROLE_CLIENT",
    }


@pytest.fixture
def override_client_guard(client_user):
    async def _fake_guard(request: Request):
        return client_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch("routes.client_read_api.client_route_guard", new=AsyncMock(return_value=client_user)):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


@pytest.fixture
def mock_db():
    store = {"keys": {}}

    class _Coll:
        def __init__(self):
            self._docs = []

        async def count_documents(self, q):
            cid = q.get("client_id")
            revoked = q.get("revoked_at")
            if revoked is None:
                return sum(1 for d in self._docs if d["client_id"] == cid and d.get("revoked_at") is None)
            return 0

        async def insert_one(self, doc):
            self._docs.append(doc)
            store["keys"][doc["token_hash"]] = doc

        def find(self, q, projection=None):
            cid = q.get("client_id")
            rev = q.get("revoked_at")

            def _match(d):
                if cid and d.get("client_id") != cid:
                    return False
                if rev is None and d.get("revoked_at") is not None:
                    return False
                return True

            rows = [d for d in self._docs if _match(d)]

            class _Cur:
                def sort(self, *a, **k):
                    return self

                async def to_list(self, n):
                    out = []
                    for d in rows[:n]:
                        item = {k: v for k, v in d.items() if k != "_id"}
                        if projection and projection.get("token_hash") == 0:
                            item.pop("token_hash", None)
                        out.append(item)
                    return out

            return _Cur()

        async def find_one(self, q):
            if "token_hash" in q:
                d = store["keys"].get(q["token_hash"])
                return dict(d) if d else None
            return None

        async def update_one(self, q, upd):
            if "token_hash" in q:
                return MagicMock(modified_count=0)
            kid = q.get("key_id")
            for d in self._docs:
                if d.get("key_id") == kid:
                    if "$set" in upd:
                        d.update(upd["$set"])
                    return MagicMock(modified_count=1)
            return MagicMock(modified_count=0)

    class _PropColl:
        def find(self, q, projection=None):
            class _Cur:
                async def to_list(self, n):
                    return []

            return _Cur()

    class _DB:
        """Motor-style db[collection] and db.properties attribute access."""

        def __init__(self):
            self._keys = _Coll()
            self.properties = _PropColl()

        def __getitem__(self, name):
            if name == "client_read_api_keys":
                return self._keys
            if name == "properties":
                return self.properties
            raise KeyError(name)

    db = _DB()

    def _get_db():
        return db

    with patch("routes.client_read_api.database.get_db", _get_db), patch(
        "services.client_read_api_service.database.get_db", _get_db
    ):
        yield db


def test_openapi_includes_read_api_paths(client):
    schema = client.app.openapi()
    paths = schema.get("paths") or {}
    assert "/api/client/integrations/read-api-keys" in paths
    assert "/api/client-data/v1/properties" in paths
    assert "/api/client-data/v1/priorities" in paths
    assert "/api/client-data/v1/capabilities" in paths


def test_data_plane_401_without_key(client):
    r = client.get("/api/client-data/v1/properties")
    assert r.status_code == 401


def test_management_list_requires_webhooks(client, override_client_guard, mock_db):
    with patch(
        "middleware.capability_gating.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate(_contract())),
    ):
        r = client.get("/api/client/integrations/read-api-keys")
    assert r.status_code == 200
    body = r.json()
    assert body["keys"] == []
    assert "/api/client-data/v1" in body.get("data_base_path", "")


def test_management_403_when_not_entitled(client, override_client_guard, mock_db):
    with patch(
        "middleware.capability_gating.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate(_contract(plan="PLAN_1_SOLO"))),
    ):
        r = client.get("/api/client/integrations/read-api-keys")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "capability_denied"


def test_create_then_read_properties_with_token(client, override_client_guard, mock_db):
    allow = _contract()
    with patch(
        "middleware.capability_gating.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate(allow)),
    ), patch(
        "routes.client_read_api.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate(allow)),
    ), patch("routes.client_read_api.create_audit_log", new_callable=AsyncMock):
        cr = client.post("/api/client/integrations/read-api-keys", json={"name": "CI"})
    assert cr.status_code == 200
    secret = cr.json()["secret"]
    assert secret.startswith("ple_read_")

    with patch(
        "routes.client_read_api.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate(allow)),
    ):
        pr = client.get(
            "/api/client-data/v1/properties",
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert pr.status_code == 200
    assert pr.json() == {"properties": []}

    with patch(
        "routes.client_read_api.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate(allow)),
    ):
        cap = client.get(
            "/api/client-data/v1/capabilities",
            headers={"Authorization": f"Bearer {secret}"},
        )
    assert cap.status_code == 200
    body = cap.json()
    assert body.get("version") == "v1"
    assert any(r.get("id") == "properties" for r in body.get("resources", []))
    assert "read:properties" in (body.get("scopes_on_key") or [])
