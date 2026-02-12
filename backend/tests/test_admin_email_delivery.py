"""
Tests for admin Email Delivery view:
- RBAC: non-admin gets 403 on GET /api/admin/email-delivery
- Pagination shape: total, returned, has_more, items; item shape (no recipient)
- Filters produce correct DB queries (template_alias, status, client_id, since_hours)
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_non_admin_gets_403_for_email_delivery():
    """Non-admin (e.g. ROLE_CLIENT) gets 403 on GET /api/admin/email-delivery."""
    from fastapi import Request, HTTPException
    from middleware import require_owner_or_admin
    from models import UserRole

    request = MagicMock(spec=Request)
    request.headers = {"Authorization": "Bearer fake"}
    request.url = MagicMock(path="/api/admin/email-delivery")

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


@pytest.mark.asyncio
async def test_email_delivery_response_shape_and_no_recipient():
    """GET /admin/email-delivery returns total, returned, has_more, items; items have no recipient."""
    from routes.admin import get_email_delivery
    from fastapi import Request
    from models import AuditAction

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    msg_cursor = MagicMock()
    msg_cursor.sort = MagicMock(return_value=msg_cursor)
    msg_cursor.limit = MagicMock(return_value=msg_cursor)
    msg_cursor.to_list = AsyncMock(
        return_value=[
            {
                "created_at": "2025-02-10T12:00:00+00:00",
                "template_alias": "monthly_digest",
                "status": "sent",
                "client_id": "client-1",
                "message_id": "msg-123",
                "provider_error_type": None,
                "provider_error_code": None,
            }
        ]
    )
    audit_cursor = MagicMock()
    audit_cursor.sort = MagicMock(return_value=audit_cursor)
    audit_cursor.limit = MagicMock(return_value=audit_cursor)
    audit_cursor.to_list = AsyncMock(return_value=[])

    db = MagicMock()
    db.message_logs = MagicMock()
    db.message_logs.count_documents = AsyncMock(return_value=1)
    db.message_logs.find = MagicMock(return_value=msg_cursor)
    db.audit_logs = MagicMock()
    db.audit_logs.count_documents = AsyncMock(return_value=0)
    db.audit_logs.find = MagicMock(return_value=audit_cursor)

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock), patch(
        "routes.admin.database.get_db", return_value=db
    ):
        result = await get_email_delivery(
            request,
            template_alias=None,
            status=None,
            client_id=None,
            since_hours=72,
            limit=50,
            skip=0,
        )

    assert "total" in result
    assert "returned" in result
    assert "has_more" in result
    assert "items" in result
    assert result["total"] == 1
    assert result["returned"] == 1
    assert result["has_more"] is False
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert "created_at" in item
    assert "template_alias" in item
    assert "status" in item
    assert "client_id" in item
    assert "message_id" in item
    assert "provider_error_type" in item
    assert "provider_error_code" in item
    assert "recipient" not in item


@pytest.mark.asyncio
async def test_email_delivery_filters_produce_correct_queries():
    """Filters template_alias, status, client_id, since_hours are passed to message_logs and audit_logs queries."""
    from routes.admin import get_email_delivery
    from fastapi import Request
    from models import AuditAction

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    msg_cursor = MagicMock()
    msg_cursor.sort = MagicMock(return_value=msg_cursor)
    msg_cursor.limit = MagicMock(return_value=msg_cursor)
    msg_cursor.to_list = AsyncMock(return_value=[])
    audit_cursor = MagicMock()
    audit_cursor.sort = MagicMock(return_value=audit_cursor)
    audit_cursor.limit = MagicMock(return_value=audit_cursor)
    audit_cursor.to_list = AsyncMock(return_value=[])

    db = MagicMock()
    db.message_logs = MagicMock()
    db.message_logs.count_documents = AsyncMock(return_value=0)
    db.message_logs.find = MagicMock(return_value=msg_cursor)
    db.audit_logs = MagicMock()
    db.audit_logs.count_documents = AsyncMock(return_value=0)
    db.audit_logs.find = MagicMock(return_value=audit_cursor)

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock), patch(
        "routes.admin.database.get_db", return_value=db
    ):
        await get_email_delivery(
            request,
            template_alias="monthly_digest",
            status=None,
            client_id="client-xyz",
            since_hours=24,
            limit=50,
            skip=0,
        )

    # message_logs find: query should have template_alias, client_id, created_at $gte
    msg_call = db.message_logs.find.call_args
    q = msg_call[0][0]
    assert q.get("template_alias") == "monthly_digest"
    assert q.get("client_id") == "client-xyz"
    assert "created_at" in q
    assert q["created_at"]["$gte"]  # since ISO string

    # audit_logs find: query should have action, client_id, metadata.template, timestamp $gte
    audit_call = db.audit_logs.find.call_args
    q_audit = audit_call[0][0]
    assert q_audit.get("action") == AuditAction.EMAIL_SKIPPED_NO_RECIPIENT.value
    assert q_audit.get("client_id") == "client-xyz"
    assert q_audit.get("metadata.template") == "monthly_digest"
    assert "timestamp" in q_audit
    assert q_audit["timestamp"]["$gte"]


@pytest.mark.asyncio
async def test_email_delivery_status_filter_failed_only_queries_message_logs():
    """When status=failed, only message_logs is queried (not audit_logs for skipped)."""
    from routes.admin import get_email_delivery
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    msg_cursor = MagicMock()
    msg_cursor.sort = MagicMock(return_value=msg_cursor)
    msg_cursor.limit = MagicMock(return_value=msg_cursor)
    msg_cursor.to_list = AsyncMock(return_value=[])
    db = MagicMock()
    db.message_logs = MagicMock()
    db.message_logs.count_documents = AsyncMock(return_value=0)
    db.message_logs.find = MagicMock(return_value=msg_cursor)
    db.audit_logs = MagicMock()
    db.audit_logs.count_documents = AsyncMock(return_value=0)
    db.audit_logs.find = MagicMock()

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock), patch(
        "routes.admin.database.get_db", return_value=db
    ):
        await get_email_delivery(
            request,
            template_alias=None,
            status="failed",
            client_id=None,
            since_hours=72,
            limit=50,
            skip=0,
        )

    db.message_logs.find.assert_called_once()
    q = db.message_logs.find.call_args[0][0]
    assert q.get("status") == "failed"
    db.audit_logs.find.assert_not_called()
