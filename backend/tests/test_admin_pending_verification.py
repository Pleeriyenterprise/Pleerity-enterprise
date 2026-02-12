"""
Tests for admin-only verification safeguards:
- GET /api/admin/documents/pending-verification (list endpoint, filterable by hours and client_id)
- Admin dashboard stats.unverified_documents_count (count badge).
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_pending_verification_list_endpoint_shape_and_filtering():
    """GET /admin/documents/pending-verification returns documents, total, returned, has_more; respects limit/skip and client_id."""
    from routes.admin import list_pending_verification_documents
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    sample_docs = [
        {
            "document_id": "doc-1",
            "client_id": "client-a",
            "property_id": "prop-1",
            "requirement_id": "req-1",
            "uploaded_at": "2025-02-10T10:00:00+00:00",
        },
        {
            "document_id": "doc-2",
            "client_id": "client-a",
            "property_id": "prop-2",
            "requirement_id": "req-2",
            "uploaded_at": "2025-02-09T12:00:00+00:00",
        },
    ]
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=sample_docs)

    db = MagicMock()
    db.documents = MagicMock()
    db.documents.count_documents = AsyncMock(return_value=2)
    db.documents.find = MagicMock(return_value=cursor)

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock), patch(
        "routes.admin.database.get_db", return_value=db
    ):
        result = await list_pending_verification_documents(
            request, hours=24, client_id=None, limit=50, skip=0
        )
    assert "documents" in result
    assert result["documents"] == sample_docs
    assert result["total"] == 2
    assert result["returned"] == 2
    assert result["has_more"] is False
    assert result["hours"] == 24
    assert result.get("client_id_filter") is None

    # With client_id filter, find should be called with client_id in query
    db.documents.find.reset_mock()
    db.documents.count_documents = AsyncMock(return_value=1)
    cursor.to_list = AsyncMock(return_value=[sample_docs[0]])
    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock), patch(
        "routes.admin.database.get_db", return_value=db
    ):
        result2 = await list_pending_verification_documents(
            request, hours=48, client_id="client-a", limit=50, skip=0
        )
    assert result2["documents"] == [sample_docs[0]]
    assert result2["total"] == 1
    assert result2["returned"] == 1
    assert result2["has_more"] is False
    assert result2["hours"] == 48
    assert result2["client_id_filter"] == "client-a"
    call_kw = db.documents.find.call_args
    assert call_kw[0][0].get("client_id") == "client-a"
    assert call_kw[0][0].get("status") == "UPLOADED"
    assert "uploaded_at" in call_kw[0][0]


@pytest.mark.asyncio
async def test_pending_verification_sort_order_oldest_first():
    """Pending verification list is sorted by uploaded_at ascending (oldest first)."""
    from routes.admin import list_pending_verification_documents
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=[])

    db = MagicMock()
    db.documents = MagicMock()
    db.documents.count_documents = AsyncMock(return_value=0)
    db.documents.find = MagicMock(return_value=cursor)

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock), patch(
        "routes.admin.database.get_db", return_value=db
    ):
        await list_pending_verification_documents(
            request, hours=24, client_id=None, limit=50, skip=0
        )

    # sort must be called with ("uploaded_at", 1) for ascending (oldest first)
    cursor.sort.assert_called_once_with("uploaded_at", 1)


@pytest.mark.asyncio
async def test_admin_dashboard_includes_unverified_documents_count():
    """GET /admin/dashboard returns stats.unverified_documents_count for badge."""
    from routes.admin import get_admin_dashboard
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    db = MagicMock()
    db.clients = MagicMock()
    db.clients.count_documents = AsyncMock(return_value=10)
    db.properties = MagicMock()
    db.properties.count_documents = AsyncMock(return_value=50)
    db.properties.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[
            {"compliance_status": "GREEN"},
            {"compliance_status": "GREEN"},
            {"compliance_status": "AMBER"},
        ]))
    )
    db.documents = MagicMock()
    db.documents.count_documents = AsyncMock(return_value=3)  # unverified count

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock), patch(
        "routes.admin.database.get_db", return_value=db
    ):
        result = await get_admin_dashboard(request)

    assert "stats" in result
    assert "unverified_documents_count" in result["stats"]
    assert result["stats"]["unverified_documents_count"] == 3


@pytest.mark.asyncio
async def test_non_admin_gets_403_for_pending_verification():
    """Non-admin (e.g. ROLE_CLIENT) gets 403 on GET /admin/documents/pending-verification."""
    from fastapi import Request, HTTPException
    from middleware import require_owner_or_admin
    from models import UserRole

    request = MagicMock(spec=Request)
    request.headers = {"Authorization": "Bearer fake"}
    request.url = MagicMock(path="/api/admin/documents/pending-verification")

    with patch("middleware.require_auth", new_callable=AsyncMock) as require_auth:
        require_auth.return_value = {
            "portal_user_id": "client-1",
            "role": UserRole.ROLE_CLIENT.value,
            "client_id": "client-a",
        }
        with pytest.raises(HTTPException) as exc_info:
            await require_owner_or_admin(request)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)
