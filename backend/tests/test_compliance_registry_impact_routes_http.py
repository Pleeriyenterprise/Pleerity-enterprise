"""Route-level tests: GET publish-impact and GET published/entry-keys (admin compliance registry)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from models import UserRole
from server import app
from services.compliance_registry_admin_service import COLLECTION as DRAFTS_COLLECTION


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


_ADMIN_USER = {"role": UserRole.ROLE_ADMIN.value, "portal_user_id": "admin-1", "email": "admin@example.com"}


def _patch_admin_auth():
    return patch("middleware.require_auth", new_callable=AsyncMock, return_value=_ADMIN_USER)


def _valid_minimal_draft(entry_id: str) -> dict:
    return {
        "entry_id": entry_id,
        "canonical_code": "GAS_SAFETY",
        "scope_key": "DEFAULT",
        "jurisdiction": {"display_jurisdictions": ["England", "Wales", "Scotland", "Northern Ireland"]},
        "identity": {"name": "Draft gas", "category": "SAFETY"},
        "classification": {
            "requirement_type": "DOCUMENT",
            "requires_document": True,
            "criticality": "HIGH",
            "client_surface_visible": True,
        },
        "action_behaviour": {"primary_action_mode": "upload_document"},
        "conditions": {"logic": "ALL", "rules": []},
        "governance": {"needs_review_fields": []},
        "action_links": [],
        "why_it_matters_short": "Statutory gas safety compliance for this property.",
        "why_it_matters_long": "",
        "why_it_matters_by_jurisdiction": {},
        "frequency": {"frequency_days": 365, "reminder_lead_days": 30},
    }


class _DraftsCollection:
    def __init__(self, by_entry_id: dict[str, dict]):
        self._by = dict(by_entry_id)

    async def find_one(self, filt: dict, projection=None):
        del projection
        eid = filt.get("entry_id")
        if not eid:
            return None
        row = self._by.get(eid)
        if not row:
            return None
        return {k: v for k, v in row.items() if k != "_id"}


class _RegistryDb:
    def __init__(self, drafts: _DraftsCollection):
        self._drafts = drafts

    def __getitem__(self, name: str):
        if name == DRAFTS_COLLECTION:
            return self._drafts
        raise KeyError(name)


def _patch_drafts_db(drafts: dict[str, dict]):
    coll = _DraftsCollection(drafts)
    return patch("routes.admin_compliance_registry.database.get_db", return_value=_RegistryDb(coll))


def test_get_publish_impact_404_missing_draft(client: TestClient):
    with _patch_admin_auth(), _patch_drafts_db({}):
        with patch(
            "routes.admin_compliance_registry.fetch_active_published_registry_entries",
            new_callable=AsyncMock,
            return_value={},
        ):
            r = client.get("/api/admin/compliance/registry/publish-impact?entry_ids=missing-entry-1")
    assert r.status_code == 404
    assert "draft_not_found" in (r.json().get("detail") or "")


def test_get_publish_impact_200_shape(client: TestClient):
    eid = "e-impact-99"
    d = _valid_minimal_draft(eid)
    published = {
        "GAS_SAFETY|DEFAULT": {
            "canonical_code": "GAS_SAFETY",
            "scope_key": "DEFAULT",
        }
    }
    with _patch_admin_auth(), _patch_drafts_db({eid: d}):
        with patch(
            "routes.admin_compliance_registry.fetch_active_published_registry_entries",
            new_callable=AsyncMock,
            return_value=published,
        ):
            r = client.get(f"/api/admin/compliance/registry/publish-impact?entry_ids={eid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("entry_ids") == [eid]
    assert "rematerialisation" in body
    impact = body.get("impact") or {}
    assert impact.get("draft_count") == 1
    per = impact.get("per_draft") or []
    assert len(per) == 1
    assert per[0].get("entry_id") == eid
    assert per[0].get("in_active_published") is True
    assert per[0].get("change_kind") == "update"
    assert impact.get("has_blocking_validation_errors") is False


def test_get_publish_impact_400_no_entry_ids_after_split(client: TestClient):
    with _patch_admin_auth(), _patch_drafts_db({}):
        with patch(
            "routes.admin_compliance_registry.fetch_active_published_registry_entries",
            new_callable=AsyncMock,
            return_value={},
        ):
            r = client.get("/api/admin/compliance/registry/publish-impact?entry_ids=,++")
    assert r.status_code == 400


def test_get_published_entry_keys_active_sorted(client: TestClient):
    pub = {
        "Z|SCOPE2": {"canonical_code": "Z", "scope_key": "SCOPE2"},
        "A|DEFAULT": {"canonical_code": "A", "scope_key": "DEFAULT"},
    }
    with _patch_admin_auth():
        with patch(
            "routes.admin_compliance_registry.fetch_active_published_registry_entries",
            new_callable=AsyncMock,
            return_value=pub,
        ):
            r = client.get("/api/admin/compliance/registry/published/entry-keys")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("active") is True
    assert body.get("keys") == ["A|DEFAULT", "Z|SCOPE2"]


def test_get_controlled_field_options_200(client: TestClient):
    with _patch_admin_auth():
        r = client.get("/api/admin/compliance/registry/controlled-field-options")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "identity_categories" in body
    assert "action_link_kinds" in body
    assert "condition_fields" in body
    assert len(body.get("condition_fields") or []) >= 5
    vals = [x["value"] for x in body.get("action_link_kinds") or []]
    assert set(vals) == {"directory", "official", "partner"}


def test_get_published_entry_keys_empty_active_false(client: TestClient):
    with _patch_admin_auth():
        with patch(
            "routes.admin_compliance_registry.fetch_active_published_registry_entries",
            new_callable=AsyncMock,
            return_value={},
        ):
            r = client.get("/api/admin/compliance/registry/published/entry-keys")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("active") is False
    assert body.get("keys") == []
