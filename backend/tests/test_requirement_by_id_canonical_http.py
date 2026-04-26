"""GET /api/requirements/{id} — canonical runtime filter, enrichment, and human workflow labels."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from database import database as db_singleton
from routes import api_compliance_workflow as acw
from server import app

CLIENT_ID = "cli-req-by-id"
REQ_ID = "req-by-id-1"
PROP_ID = "prop-by-id-1"

REQ_ROW = {
    "requirement_id": REQ_ID,
    "client_id": CLIENT_ID,
    "property_id": PROP_ID,
    "requirement_code": "gas_safety",
    "requirement_type": "gas_safety",
    "applicability": "REQUIRED",
    "status": "PENDING",
    "client_surface_visible": True,
    "requirement_generation_source": "catalog_registry",
}

CANON_ROW = {
    **REQ_ROW,
    "property_jurisdiction": "England",
    "display_name": "Gas safety",
}


async def _fake_client_guard(_request: Request):
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": "pu-req-by-id",
        "role": "ROLE_CLIENT_ADMIN",
        "email": "req-by-id@test.com",
    }


@pytest.fixture
def client_http():
    app.dependency_overrides[acw._require_client] = _fake_client_guard
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(acw._require_client, None)


def _mock_db():
    mock_db = MagicMock()
    mock_db.requirements.find_one = AsyncMock(return_value=dict(REQ_ROW))
    return mock_db


def test_get_requirement_by_id_returns_workflow_labels_and_published_metadata(client_http):
    enriched = {
        **CANON_ROW,
        "display_label": "Gas safety",
        "registry_metadata": {
            "why_it_matters_short_published": "Published why",
            "action_links_published": [{"label": "Gov", "url": "https://example.com/gas"}],
            "primary_action_mode": "document_upload",
        },
        "take_action": {
            "primary": {
                "label": "Upload certificate",
                "route": f"/documents?property_id={PROP_ID}&requirement_id={REQ_ID}",
                "handler": "navigate",
            },
            "supporting_external_links": [],
        },
    }
    mock_db = _mock_db()
    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "routes.api_compliance_workflow._client_requirement_row_eligible",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=[dict(CANON_ROW)],
        ),
        patch(
            "services.requirement_truth.enrich_requirements_for_client",
            new_callable=AsyncMock,
            return_value=([enriched], {"ok": True}),
        ),
        patch(
            "routes.api_compliance_workflow.find_active_compliance_job_for_requirement",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        res = client_http.get(f"/api/requirements/{REQ_ID}")
    assert res.status_code == 200
    body = res.json()
    req = body.get("requirement") or {}
    assert req.get("workflow_status") == "ACTION_REQUIRED"
    assert req.get("compliance_state") == "MISSING"
    assert req.get("workflow_status_label") == "Action required"
    assert req.get("compliance_state_label") == "Evidence missing"
    assert req.get("registry_metadata", {}).get("why_it_matters_short_published") == "Published why"
    assert len(req.get("registry_metadata", {}).get("action_links_published") or []) == 1
    assert (req.get("take_action") or {}).get("primary", {}).get("label") == "Upload certificate"


def test_get_requirement_by_id_404_when_runtime_filter_excludes_row(client_http):
    mock_db = _mock_db()
    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "routes.api_compliance_workflow._client_requirement_row_eligible",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        res = client_http.get(f"/api/requirements/{REQ_ID}")
    assert res.status_code == 404
