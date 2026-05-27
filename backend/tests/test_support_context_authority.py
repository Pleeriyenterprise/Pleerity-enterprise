"""
INV-SU-001, INV-SU-002: support context degrades-not-fails and exposes ops_summary_v1.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from middleware import require_support_or_above
from server import app


def _fake_support_user():
    return {"user_id": "support@test", "role": "support"}


def _mock_support_db(*, audit_raises: bool = False):
    mock_db = MagicMock()
    clients = MagicMock()
    clients.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "full_name": "Test Client",
            "email": "t@example.com",
            "customer_reference": "CRN1",
        }
    )
    orders = MagicMock()
    orders.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
    properties = MagicMock()
    properties.count_documents = AsyncMock(return_value=1)

    async def prop_iter():
        yield {"property_id": "p1"}

    properties.find.return_value = prop_iter()
    requirements = MagicMock()
    requirements.count_documents = AsyncMock(return_value=0)
    documents = MagicMock()
    documents.count_documents = AsyncMock(return_value=0)
    documents.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
    notification_preferences = MagicMock()
    notification_preferences.find_one = AsyncMock(return_value={})
    audit_logs = MagicMock()
    if audit_raises:
        audit_logs.find.side_effect = RuntimeError("audit unavailable")
    else:
        audit_logs.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
    message_logs = MagicMock()
    message_logs.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[])

    collections = {
        "clients": clients,
        "orders": orders,
        "properties": properties,
        "requirements": requirements,
        "documents": documents,
        "notification_preferences": notification_preferences,
        "audit_logs": audit_logs,
        "message_logs": message_logs,
    }
    mock_db.__getitem__ = MagicMock(side_effect=lambda name: collections[name])
    return mock_db


@pytest.fixture
def support_client(client):
    app.dependency_overrides[require_support_or_above] = _fake_support_user
    yield client
    app.dependency_overrides.pop(require_support_or_above, None)


def test_support_context_returns_200_with_ops_summary_inv_su_002(support_client):
    ops = {
        "available": True,
        "degraded_sections": [],
        "counts": {"open_issues": 0},
        "recent_issues": [],
        "recent_work_orders": [],
        "recent_risk_signals": [],
        "lifecycle_highlights": [],
    }

    with patch("routes.support.database.get_db", return_value=_mock_support_db()):
        with patch("services.support_client_context_ops.build_ops_summary_v1", new_callable=AsyncMock, return_value=ops):
            resp = support_client.get("/api/admin/support/context/c1")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "ops_summary_v1" in data
    assert data["ops_summary_v1"]["available"] is True


def test_support_context_degrades_audit_failure_inv_su_001(support_client):
    with patch("routes.support.database.get_db", return_value=_mock_support_db(audit_raises=True)):
        with patch(
            "services.support_client_context_ops.build_ops_summary_v1",
            new_callable=AsyncMock,
            return_value={"available": True, "degraded_sections": []},
        ):
            resp = support_client.get("/api/admin/support/context/c1")

    assert resp.status_code == 200
    degraded = resp.json().get("context_degraded_sections") or []
    assert any(s.get("section") == "recent_audit_log" for s in degraded)
