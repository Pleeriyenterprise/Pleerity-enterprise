"""Client requirements list vs full projection — operational authority parity."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _limit):
        return self._rows


class _FakeDb:
    def __init__(self, requirement_rows):
        self.requirements = _FakeCollection(requirement_rows)
        self.properties = _FakeCollection([])
        self.clients = _FakeClients({"client_id": "c-1"})


class _FakeCollection:
    def __init__(self, rows):
        self._rows = rows

    def find(self, *_a, **_k):
        return _FakeCursor(self._rows)


class _FakeClients:
    def __init__(self, doc):
        self._doc = doc

    async def find_one(self, *_a, **_k):
        return self._doc


@pytest.mark.asyncio
async def test_requirements_list_projection_defers_enrichment(monkeypatch):
    from routes import client as client_routes

    rows = [
        {
            "requirement_id": "r-1",
            "client_id": "c-1",
            "property_id": "p-1",
            "requirement_code": "gas_safety",
            "requirement_type": "gas_safety",
            "status": "PENDING",
            "client_surface_visible": True,
        }
    ]
    fake_db = _FakeDb(rows)

    async def fake_filter(*_a, **_k):
        return _k.get("requirements") or []

    monkeypatch.setattr(client_routes.database, "get_db", lambda: fake_db)
    monkeypatch.setattr(
        "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
        fake_filter,
    )

    request = MagicMock()
    user = {"client_id": "c-1", "portal_user_id": "u-1"}

    async def fake_guard(_request):
        return user

    monkeypatch.setattr(client_routes, "client_route_guard", fake_guard)

    out = await client_routes.get_all_requirements(request, projection="list")
    assert out["presentation"]["enrichment_deferred"] is True
    row = out["requirements"][0]
    assert not row.get("take_action")
    assert not row.get("operational_cognition")


@pytest.mark.asyncio
async def test_requirements_full_projection_includes_take_action(monkeypatch):
    from routes import client as client_routes

    rows = [
        {
            "requirement_id": "r-1",
            "client_id": "c-1",
            "property_id": "p-1",
            "requirement_code": "deposit_pi",
            "requirement_type": "deposit_pi",
            "status": "PENDING",
            "client_surface_visible": True,
        }
    ]
    fake_db = _FakeDb(rows)

    enriched_row = {
        "requirement_id": "r-1",
        "take_action": {
            "primary": {"label": "Record deposit protection", "kind": "guided_evidence_resolution"},
        },
        "why_it_matters_short": "Deposit must be protected.",
        "operational_cognition": {"read_only": True, "cognition_version": "operational_cognition_v1"},
        "client_surface_visible": True,
    }

    async def fake_filter(*_a, **_k):
        return _k.get("requirements") or []

    async def fake_enrich(_db, _cid, _rows):
        return [enriched_row], {"projection": "full"}

    monkeypatch.setattr(client_routes.database, "get_db", lambda: fake_db)
    monkeypatch.setattr(
        "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
        fake_filter,
    )
    monkeypatch.setattr("services.requirement_truth.enrich_requirements_for_client", fake_enrich)

    request = MagicMock()
    user = {"client_id": "c-1", "portal_user_id": "u-1"}

    async def fake_guard(_request):
        return user

    monkeypatch.setattr(client_routes, "client_route_guard", fake_guard)

    out = await client_routes.get_all_requirements(request, projection="full")
    row = out["requirements"][0]
    assert row["take_action"]["primary"]["label"] == "Record deposit protection"
    assert row.get("why_it_matters_short")
    assert row.get("operational_cognition", {}).get("cognition_version") == "operational_cognition_v1"
