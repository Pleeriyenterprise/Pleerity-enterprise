"""Tests for downgrade support: PLAN_LIMIT 403, over_limit in setup-status, no data deletion."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_property_over_limit_returns_403_with_plan_limit(client):
    """When at plan limit, POST /api/properties/create returns 403 with error_code PLAN_LIMIT."""
    async def mock_guard(_request):
        return {"client_id": "c1", "portal_user_id": "u1", "role": "ROLE_CLIENT"}

    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "onboarding_status": "PROVISIONED"})
    # Active count 2 (Solo limit), so 2+1=3 is over limit
    db.properties.count_documents = AsyncMock(return_value=2)
    db.properties.insert_one = AsyncMock()
    db.requirements = MagicMock()
    db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    db.requirements.update_one = AsyncMock()
    db.audit_logs = MagicMock()
    db.audit_logs.insert_one = AsyncMock()

    with patch("routes.properties.client_route_guard", side_effect=mock_guard), \
         patch("routes.properties.database.get_db", return_value=db):
        # enforce_property_limit("c1", 3) will be called; client has 2 active, so 3 > 2 -> denied
        # Mock plan_registry to return denied for 3 properties (Solo allows 2)
        with patch("services.plan_registry.plan_registry") as pr:
            pr.enforce_property_limit = AsyncMock(return_value=(
                False,
                "You've reached the maximum of 2 properties for the Solo plan",
                {"error_code": "PROPERTY_LIMIT_EXCEEDED", "current_limit": 2, "requested_count": 3},
            ))
            response = client.post(
                "/api/properties/create",
                json={
                    "address_line_1": "1 High St",
                    "city": "London",
                    "postcode": "SW1A 1AA",
                },
                headers={"Authorization": "Bearer fake"},
            )

    assert response.status_code == 403
    data = response.json()
    detail = data.get("detail", data)
    assert isinstance(detail, dict) and detail.get("error_code") == "PLAN_LIMIT"


def test_over_limit_archived_property_blocks_upload(client):
    """Upload to an archived (is_active=False) property returns 403 with PLAN_LIMIT."""
    async def mock_guard(_request):
        return {"client_id": "c1", "portal_user_id": "u1", "role": "CLIENT"}

    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value={
        "property_id": "p1", "client_id": "c1", "is_active": False,
    })
    db.requirements.find_one = AsyncMock(return_value={"requirement_id": "r1", "client_id": "c1"})

    with patch("routes.documents.client_route_guard", side_effect=mock_guard), \
         patch("routes.documents.database.get_db", return_value=db):
        response = client.post(
            "/api/documents/upload",
            data={"property_id": "p1", "requirement_id": "r1"},
            files={"file": ("test.pdf", b"fake", "application/pdf")},
            headers={"Authorization": "Bearer fake"},
        )

    assert response.status_code == 403
    data = response.json()
    assert data.get("detail", {}).get("error_code") == "PLAN_LIMIT"


def test_data_remains_archived_property_still_listed(client):
    """Archived properties remain in list (no deletion); is_active flag exposed."""
    async def mock_guard(_request):
        return {"client_id": "c1", "portal_user_id": "u1", "role": "ROLE_CLIENT"}

    db = MagicMock()
    db.properties.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[
            {"property_id": "p1", "address_line_1": "1 High St", "is_active": True},
            {"property_id": "p2", "address_line_1": "2 Low St", "is_active": False},
        ])
    ))
    db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

    with patch("routes.properties.client_route_guard", side_effect=mock_guard), \
         patch("routes.properties.database.get_db", return_value=db):
        response = client.get("/api/properties/list", headers={"Authorization": "Bearer fake"})

    assert response.status_code == 200
    data = response.json()
    assert len(data.get("properties", [])) == 2
    assert any(p.get("property_id") == "p2" and p.get("is_active") is False for p in data["properties"])
