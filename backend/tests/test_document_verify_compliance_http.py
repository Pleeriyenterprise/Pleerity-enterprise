"""HTTP test: POST /api/documents/verify/{id} updates requirement compliance and finalizes active compliance jobs."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from database import database as db_singleton
from models import RequirementStatus
from routes import api_compliance_workflow as acw
from routes import documents as documents_routes
from server import app

DOC_ID = "doc-verify-http-1"
REQ_ID = "req-prop-verify-1"
CLIENT_ID = "cli-doc-verify"
PROP_ID = "prop-doc-verify"
WO_ID = "wo-compliance-active-1"


class _FakeWorkOrderCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        self._it = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def client_http():
    with TestClient(app) as c:
        yield c


def test_verify_document_updates_requirement_and_finalizes_compliance_job(client_http):
    doc = {
        "document_id": DOC_ID,
        "client_id": CLIENT_ID,
        "property_id": PROP_ID,
        "requirement_id": REQ_ID,
        "work_order_id": WO_ID,
        "status": "PENDING",
        "document_name": "Certificate",
    }
    requirement_updates = []
    wo_finalize_calls = []

    async def find_document(filt, *args, **kwargs):
        if filt.get("document_id") == DOC_ID:
            return dict(doc)
        return None

    async def capture_requirement_update(filt, update, *args, **kwargs):
        requirement_updates.append((filt, update))
        return MagicMock(modified_count=1)

    async def track_update_work_order(wid, **kwargs):
        wo_finalize_calls.append((wid, kwargs))
        return {"work_order_id": wid}

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(side_effect=find_document)
    _req_docs_cur = MagicMock()
    _req_docs_cur.to_list = AsyncMock(return_value=[])
    mock_db.documents.find = MagicMock(return_value=_req_docs_cur)
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.update_one = AsyncMock(side_effect=capture_requirement_update)
    mock_db.requirements.find_one = AsyncMock(
        return_value={"requirement_id": REQ_ID, "requirement_code": "TEST", "requirement_type": "TEST"}
    )
    mock_db.work_orders.find = MagicMock(
        return_value=_FakeWorkOrderCursor([{"work_order_id": WO_ID}])
    )
    mock_db.work_orders.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": PROP_ID, "address": {"line1": "1 Test St"}})

    admin_user = {"portal_user_id": "admin-doc-verify", "client_id": CLIENT_ID, "role": "ROLE_ADMIN"}
    with (
        patch.object(documents_routes, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.documents.create_audit_log", new_callable=AsyncMock),
        patch("services.maintenance_service.update_work_order", new_callable=AsyncMock, side_effect=track_update_work_order),
        patch("services.provisioning.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock),
        patch("services.enablement_service.emit_enablement_event", new_callable=AsyncMock),
        patch(
            "services.compliance_outcome_engine.apply_action_outcome",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        res = client_http.post(f"/api/documents/verify/{DOC_ID}")

    assert res.status_code == 200, res.text
    assert requirement_updates, "requirements.update_one should run when document has requirement_id"
    _filt, upd = requirement_updates[0]
    assert _filt.get("requirement_id") == REQ_ID
    set_payload = (upd.get("$set") or {})
    assert set_payload.get("compliance_state") == "VALID"
    assert set_payload.get("status") == RequirementStatus.COMPLIANT.value

    assert any(
        call[0] == WO_ID and "document:" + DOC_ID in (call[1].get("evidence_keys_append") or [])
        for call in wo_finalize_calls
    ), "evidence pointer should be appended to active compliance job"
    assert any(call[0] == WO_ID and call[1].get("status") == "VERIFIED" for call in wo_finalize_calls), (
        "active compliance job should move to VERIFIED"
    )


def test_get_job_reflects_verified_compliance_work_order(client_http):
    """Client GET /api/jobs/{id} exposes canonical job_status after verify-style terminal state (HTTP surface)."""
    wo = {
        "work_order_id": WO_ID,
        "client_id": CLIENT_ID,
        "property_id": PROP_ID,
        "work_order_kind": "COMPLIANCE",
        "status": "VERIFIED",
        "description": "Test compliance job",
        "linked_property_requirement_id": REQ_ID,
        "evidence_keys": [f"document:{DOC_ID}"],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-02T00:00:00+00:00",
    }

    async def _fake_mw(request: Request):
        return {"client_id": CLIENT_ID, "portal_user_id": "pu-job-get", "role": "ROLE_CLIENT_ADMIN"}

    app.dependency_overrides[acw._require_maintenance_workflows] = _fake_mw
    try:
        with patch.object(acw, "load_client_work_order", new_callable=AsyncMock, return_value=wo):
            res = client_http.get(f"/api/jobs/{WO_ID}")
    finally:
        app.dependency_overrides.pop(acw._require_maintenance_workflows, None)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("job_status") == "VERIFIED"
    assert body.get("status") == "VERIFIED"
    assert any((a.get("id") == "none" for a in (body.get("next_actions") or [])))
