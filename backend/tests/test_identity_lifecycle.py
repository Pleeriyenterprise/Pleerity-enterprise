"""Unified identity lifecycle facade and contractor / portal user delete preflight."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models import UserRole
from services.contractor_identity_lifecycle import contractor_permanent_delete_preflight
from services.portal_user_lifecycle_service import permanent_delete_preflight as portal_user_delete_preflight


@pytest.mark.asyncio
async def test_contractor_delete_preflight_blocks_work_orders():
    db = MagicMock()
    db.contractors.find_one = AsyncMock(return_value={"contractor_id": "c1"})

    async def fake_count(_, name, __):
        return 3 if name == "work_orders" else 0

    with patch("services.contractor_identity_lifecycle._count", new_callable=AsyncMock, side_effect=fake_count):
        ok, blockers = await contractor_permanent_delete_preflight(db, "c1")
    assert ok is False
    assert any(b.startswith("work_orders_count:") for b in blockers)


@pytest.mark.asyncio
async def test_contractor_delete_preflight_allows_clean():
    db = MagicMock()
    db.contractors.find_one = AsyncMock(return_value={"contractor_id": "c1"})

    with patch("services.contractor_identity_lifecycle._count", new_callable=AsyncMock, return_value=0):
        ok, blockers = await contractor_permanent_delete_preflight(db, "c1")
    assert ok is True
    assert blockers == []


@pytest.mark.asyncio
async def test_portal_user_delete_preflight_blocks_tenant_assignments():
    db = MagicMock()
    db.portal_users.find_one = AsyncMock(
        return_value={
            "portal_user_id": "t1",
            "client_id": None,
            "role": UserRole.ROLE_TENANT.value,
        }
    )
    db.tenant_assignments = MagicMock()
    db.tenant_assignments.count_documents = AsyncMock(return_value=1)
    db.tenant_requests = MagicMock()
    db.tenant_requests.count_documents = AsyncMock(return_value=0)
    db.maintenance_issues = MagicMock()
    db.maintenance_issues.count_documents = AsyncMock(return_value=0)
    db.audit_logs = MagicMock()
    db.audit_logs.count_documents = AsyncMock(return_value=0)

    ok, blockers = await portal_user_delete_preflight(db, "t1")
    assert ok is False
    assert "tenant_assignments_exist" in blockers


@pytest.mark.asyncio
async def test_portal_user_delete_preflight_allows_clean_non_tenant():
    db = MagicMock()
    db.portal_users.find_one = AsyncMock(
        return_value={"portal_user_id": "u1", "client_id": None, "role": UserRole.ROLE_ADMIN.value}
    )
    db.audit_logs = MagicMock()
    db.audit_logs.count_documents = AsyncMock(return_value=0)

    ok, blockers = await portal_user_delete_preflight(db, "u1")
    assert ok is True
    assert blockers == []
