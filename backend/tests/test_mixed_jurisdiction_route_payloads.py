"""
Thin route-level integration checks for mixed-jurisdiction requirement-backed payloads.

Scope:
- /api/client/requirements
- /api/client/dashboard
- /api/today/items
- /api/client/command-center
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import api_compliance_workflow as acw
from server import app
from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE


CLIENT_ID = "mix-route-client"
P_ENG = "prop-eng"
P_WAL = "prop-wal"


class _FakeCursor:
    def __init__(self, items: List[Dict[str, Any]]):
        self._items = [dict(x) for x in items]

    async def to_list(self, _limit: int = 0, **kwargs):
        return [dict(x) for x in self._items]

    def __aiter__(self):
        self._it = iter(self._items)
        return self

    def sort(self, *_args, **_kwargs):
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration as e:
            raise StopAsyncIteration from e


class _Collection:
    def __init__(self, items: List[Dict[str, Any]]):
        self._items = [dict(x) for x in items]

    async def find_one(self, query: Dict[str, Any], projection: Dict[str, Any] | None = None):
        for doc in self._items:
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None

    def find(self, query: Dict[str, Any], projection: Dict[str, Any] | None = None):
        out: List[Dict[str, Any]] = []
        for doc in self._items:
            ok = True
            for k, v in query.items():
                if isinstance(v, dict) and "$in" in v:
                    if doc.get(k) not in set(v.get("$in") or []):
                        ok = False
                        break
                elif doc.get(k) != v:
                    ok = False
                    break
            if ok:
                out.append(doc)
        return _FakeCursor(out)


class _FakeDB:
    def __init__(self, client_doc: Dict[str, Any], properties: List[Dict[str, Any]], requirements: List[Dict[str, Any]]):
        self.clients = _Collection([client_doc])
        self.properties = _Collection(properties)
        self.requirements = _Collection(requirements)
        self.requirements_catalog = _Collection([])
        self.documents = _Collection([])


def _prop(pid: str, jurisdiction: str) -> Dict[str, Any]:
    return {
        "property_id": pid,
        "client_id": CLIENT_ID,
        "jurisdiction": jurisdiction,
        "property_type": "residential",
        "tenancy_active": True,
        "has_gas_supply": True,
        "deposit_taken": True,
        "furnished": False,
        "is_hmo": False,
    }


def _req(rid: str, pid: str, rtype: str, jurisdiction: str) -> Dict[str, Any]:
    return {
        "requirement_id": rid,
        "client_id": CLIENT_ID,
        "property_id": pid,
        "requirement_type": rtype,
        "requirement_code": rtype,
        "jurisdiction": jurisdiction,
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        "updated_at": "2026-01-01T00:00:00Z",
    }


@pytest.fixture
def mixed_user():
    return {"client_id": CLIENT_ID, "portal_user_id": "pu-mix", "role": "ROLE_CLIENT_ADMIN"}


@pytest.fixture
def _override_client_guard(mixed_user):
    async def _fake_guard(request: Request):
        return mixed_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    app.dependency_overrides[acw._require_client] = _fake_guard
    with patch("routes.client.client_route_guard", new=AsyncMock(return_value=mixed_user)), patch(
        "routes.portfolio.client_route_guard", new=AsyncMock(return_value=mixed_user)
    ):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)
    app.dependency_overrides.pop(acw._require_client, None)


def test_requirements_route_preserves_mixed_jurisdiction_attribution_and_cta_fields(client, _override_client_guard):
    props = [_prop(P_ENG, "England"), _prop(P_WAL, "Wales")]
    rows = [
        _req("eng-gas", P_ENG, "gas_safety", "England"),
        _req("wal-gas", P_WAL, "gas_safety", "Wales"),
        # Wrong-jurisdiction leakage candidates: should be filtered out by runtime gates.
        _req("leak-eng-on-wal", P_WAL, "right_to_rent", "England"),
        _req("leak-wal-on-eng", P_ENG, "wales_occupation_contract", "Wales"),
    ]
    fake_db = _FakeDB({"client_id": CLIENT_ID, "default_jurisdiction": "England"}, props, rows)

    def _capture_enrich(req: Dict[str, Any], _live_ev: str, **kwargs):
        pd = kwargs.get("property_doc") or {}
        jur = str(pd.get("jurisdiction") or "")
        out = dict(req)
        out["why_it_matters_short"] = f"why-{jur}"
        out["take_action"] = {"primary": {"action_type": "view", "label": f"cta-{jur}", "url": "/"}}
        out["action_links"] = [{"label": f"link-{jur}"}]
        return out

    with (
        patch("routes.client.database.get_db", return_value=fake_db),
        patch("services.requirement_truth.fetch_active_published_registry_entries", new_callable=AsyncMock, return_value={}),
        patch("services.requirement_truth.load_evidence_state_by_requirement_id", new_callable=AsyncMock, return_value={}),
        patch("services.requirement_truth.enrich_requirement_dict", side_effect=_capture_enrich),
    ):
        res = client.get("/api/client/requirements")

    assert res.status_code == 200
    body = res.json()
    reqs = body.get("requirements") or []
    assert len(reqs) == 2
    by_pid = {r["property_id"]: r for r in reqs}
    assert set(by_pid.keys()) == {P_ENG, P_WAL}
    assert by_pid[P_ENG]["jurisdiction"] == "England"
    assert by_pid[P_WAL]["jurisdiction"] == "Wales"
    assert by_pid[P_ENG]["why_it_matters_short"] == "why-England"
    assert by_pid[P_WAL]["why_it_matters_short"] == "why-Wales"
    assert by_pid[P_ENG]["take_action"]["primary"]["label"] == "cta-England"
    assert by_pid[P_WAL]["take_action"]["primary"]["label"] == "cta-Wales"
    assert by_pid[P_ENG]["action_links"][0]["label"] == "link-England"
    assert by_pid[P_WAL]["action_links"][0]["label"] == "link-Wales"
    # Same canonical obligation appears separately for each property.
    assert sum(1 for r in reqs if str(r.get("canonical_code")) == "gas_safety") == 2


def test_dashboard_route_requirement_counts_stay_property_scoped(client, _override_client_guard):
    props = [_prop(P_ENG, "England"), _prop(P_WAL, "Wales")]
    rows = [
        _req("eng-gas", P_ENG, "gas_safety", "England"),
        _req("wal-gas", P_WAL, "gas_safety", "Wales"),
        _req("leak-eng-on-wal", P_WAL, "right_to_rent", "England"),
    ]
    fake_db = _FakeDB({"client_id": CLIENT_ID, "default_jurisdiction": "England"}, props, rows)
    with patch("routes.client.database.get_db", return_value=fake_db), patch(
        "services.onboarding_checklist_service.get_checklist_for_client",
        new=AsyncMock(return_value={"items": [], "completed_at": None, "all_required_complete": False}),
    ):
        res = client.get("/api/client/dashboard")

    assert res.status_code == 200
    body = res.json()
    summary = body.get("compliance_summary") or {}
    # Leak row excluded; two property-scoped gas rows survive.
    assert summary.get("total_requirements") == 2
    assert summary.get("compliant") == 0
    assert len(body.get("properties") or []) == 2
    assert {p.get("property_id") for p in body.get("properties") or []} == {P_ENG, P_WAL}


def test_today_route_requirement_backed_items_preserve_property_and_jurisdiction(client, _override_client_guard):
    payload = {
        "tasks": {
            "urgent": [
                {
                    "id": "requirement:eng-gas",
                    "source_type": "requirement",
                    "source_id": "eng-gas",
                    "source_entity_type": "requirement",
                    "source_entity_id": "eng-gas",
                    "property_id": P_ENG,
                    "jurisdiction": "England",
                    "title": "Gas safety due",
                    "section": "urgent",
                    "primary_action_type": "view_requirement",
                    "primary_action_label": "cta-England",
                    "primary_action_url": f"/requirements?property_id={P_ENG}",
                    "why_it_matters_short": "why-England",
                    "action_links": [{"label": "link-England"}],
                },
                {
                    "id": "requirement:wal-gas",
                    "source_type": "requirement",
                    "source_id": "wal-gas",
                    "source_entity_type": "requirement",
                    "source_entity_id": "wal-gas",
                    "property_id": P_WAL,
                    "jurisdiction": "Wales",
                    "title": "Gas safety due",
                    "section": "urgent",
                    "primary_action_type": "view_requirement",
                    "primary_action_label": "cta-Wales",
                    "primary_action_url": f"/requirements?property_id={P_WAL}",
                    "why_it_matters_short": "why-Wales",
                    "action_links": [{"label": "link-Wales"}],
                },
            ],
            "upcoming": [],
            "in_progress": [],
            "recently_completed": [],
            "snoozed": [],
            "hidden": [],
        },
        "summary": {"total_open": 2},
        "freshness": {},
        "activity_feed": [],
    }
    with patch.object(acw, "get_unified_tasks_for_client", new_callable=AsyncMock, return_value=payload):
        res = client.get("/api/today/items")

    assert res.status_code == 200
    body = res.json()
    urgent = (body.get("tasks") or {}).get("urgent") or []
    assert len(urgent) == 2
    assert {t.get("property_id") for t in urgent} == {P_ENG, P_WAL}
    assert {t.get("jurisdiction") for t in urgent} == {"England", "Wales"}
    assert any((t.get("primary_action_label") == "cta-England") for t in urgent)
    assert any((t.get("primary_action_label") == "cta-Wales") for t in urgent)
    assert not any(t.get("property_id") == P_WAL and t.get("jurisdiction") == "England" for t in urgent)


def test_command_center_route_requirement_backed_urgent_actions_preserve_attribution(client, _override_client_guard):
    bundle = {
        "urgent_actions": [
            {
                "id": "requirement:eng-gas",
                "source_type": "requirement",
                "source_id": "eng-gas",
                "property_id": P_ENG,
                "jurisdiction": "England",
                "canonical_code": "gas_safety",
                "why_it_matters_short": "why-England",
                "action_links": [{"label": "link-England"}],
                "primary_cta": {"action_type": "view_requirement", "label": "cta-England", "route": f"/requirements?property_id={P_ENG}"},
            },
            {
                "id": "requirement:wal-gas",
                "source_type": "requirement",
                "source_id": "wal-gas",
                "property_id": P_WAL,
                "jurisdiction": "Wales",
                "canonical_code": "gas_safety",
                "why_it_matters_short": "why-Wales",
                "action_links": [{"label": "link-Wales"}],
                "primary_cta": {"action_type": "view_requirement", "label": "cta-Wales", "route": f"/requirements?property_id={P_WAL}"},
            },
        ],
        "upcoming_risks": [],
        "recent_activity": [],
        "compliance_status_summary": {"total_requirements": 2},
        "tasks_digest_summary": {"total_open": 2},
        "freshness": {},
    }
    with patch("services.ops_compliance_feature_flags.get_effective_flags", new=AsyncMock(return_value={"predictive_maintenance": True})), patch(
        "services.command_center_service.get_command_center_bundle",
        new=AsyncMock(return_value=bundle),
    ):
        res = client.get("/api/client/command-center")

    assert res.status_code == 200
    body = res.json()
    urgent = body.get("urgent_actions") or []
    assert len(urgent) == 2
    assert {u.get("property_id") for u in urgent} == {P_ENG, P_WAL}
    assert {u.get("jurisdiction") for u in urgent} == {"England", "Wales"}
    assert sum(1 for u in urgent if u.get("canonical_code") == "gas_safety") == 2
    assert body.get("compliance_status_summary", {}).get("total_requirements") == 2
    assert not any(u.get("property_id") == P_WAL and u.get("jurisdiction") == "England" for u in urgent)


def test_property_requirements_ids_align_with_client_requirements_set(client, _override_client_guard):
    props = [_prop(P_ENG, "England"), _prop(P_WAL, "Wales")]
    rows = [
        _req("eng-gas", P_ENG, "gas_safety", "England"),
        _req("eng-r2r", P_ENG, "right_to_rent", "England"),
        _req("wal-gas", P_WAL, "gas_safety", "Wales"),
    ]
    fake_db = _FakeDB({"client_id": CLIENT_ID, "default_jurisdiction": "England"}, props, rows)
    with patch("routes.client.database.get_db", return_value=fake_db), patch(
        "services.requirement_truth.fetch_active_published_registry_entries", new_callable=AsyncMock, return_value={}
    ), patch(
        "services.requirement_truth.load_evidence_state_by_requirement_id", new_callable=AsyncMock, return_value={}
    ):
        all_res = client.get("/api/client/requirements")
        prop_res = client.get(f"/api/client/properties/{P_ENG}/requirements")
    assert all_res.status_code == 200
    assert prop_res.status_code == 200
    all_ids = {str(r.get("requirement_id")) for r in (all_res.json().get("requirements") or []) if r.get("property_id") == P_ENG}
    prop_ids = {str(r.get("requirement_id")) for r in (prop_res.json().get("requirements") or [])}
    assert prop_ids
    assert prop_ids == all_ids


def test_property_requirements_route_excludes_noncanonical_ids_and_logs(client, _override_client_guard, caplog):
    props = [_prop(P_ENG, "England")]
    rows = [
        _req("eng-gas", P_ENG, "gas_safety", "England"),
        _req("eng-r2r", P_ENG, "right_to_rent", "England"),
    ]
    fake_db = _FakeDB({"client_id": CLIENT_ID, "default_jurisdiction": "England"}, props, rows)
    with patch("routes.client.database.get_db", return_value=fake_db), patch(
        "services.requirement_truth.fetch_active_published_registry_entries", new_callable=AsyncMock, return_value={}
    ), patch(
        "services.requirement_truth.load_evidence_state_by_requirement_id", new_callable=AsyncMock, return_value={}
    ), patch(
        "services.requirement_read_model_guard.get_canonical_requirement_ids_for_property",
        new=AsyncMock(return_value={"eng-gas"}),
    ):
        res = client.get(f"/api/client/properties/{P_ENG}/requirements")
    assert res.status_code == 200
    ids = {str(r.get("requirement_id")) for r in (res.json().get("requirements") or [])}
    assert ids == {"eng-gas"}
    assert any("dropped non-canonical requirement row" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_property_compliance_detail_matrix_excludes_noncanonical_ids():
    props = [_prop(P_ENG, "England")]
    rows = [
        _req("eng-gas", P_ENG, "gas_safety", "England"),
        _req("eng-r2r", P_ENG, "right_to_rent", "England"),
    ]
    fake_db = _FakeDB({"client_id": CLIENT_ID, "default_jurisdiction": "England"}, props, rows)
    with patch("services.catalog_compliance.database.get_db", return_value=fake_db), patch(
        "services.requirement_truth.enrich_requirements_for_client",
        new=AsyncMock(return_value=(rows, {})),
    ), patch(
        "services.catalog_compliance.filter_requirement_rows_for_client_runtime_surfaces",
        new=AsyncMock(return_value=rows),
    ), patch(
        "services.catalog_compliance._load_catalog",
        new=AsyncMock(return_value=[]),
    ), patch(
        "services.catalog_compliance.get_canonical_requirement_ids_for_property",
        new=AsyncMock(return_value={"eng-gas"}),
    ):
        from services.catalog_compliance import get_property_compliance_detail

        detail = await get_property_compliance_detail(CLIENT_ID, P_ENG)
    matrix = (detail or {}).get("matrix") or []
    ids = {str(r.get("requirement_id")) for r in matrix}
    assert ids == {"eng-gas"}
