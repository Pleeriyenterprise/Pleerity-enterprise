"""Unit tests for property occupancy operational summary (mocked DB)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_build_summary_raises_when_property_missing():
    from services.property_occupancy_operational_service import build_property_occupancy_operational_summary

    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(return_value=None)
    with patch("services.property_occupancy_operational_service.database") as db_mod:
        db_mod.get_db.return_value = mock_db
        with pytest.raises(ValueError, match="not found"):
            await build_property_occupancy_operational_summary("c1", "p1", include_tenant_portal=False)


@pytest.mark.asyncio
async def test_build_summary_includes_applicability():
    from services.property_occupancy_operational_service import build_property_occupancy_operational_summary

    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "occupancy": "student",
            "tenancy_active": True,
            "bedrooms": 3,
            "property_type": "hmo",
        }
    )
    mock_db.portal_users.find = MagicMock(return_value=_async_iter([]))
    mock_db.tenant_assignments.find = MagicMock(return_value=_async_iter([]))
    mock_db.tenant_requests.find = MagicMock(return_value=_async_iter([]))
    mock_db.tenant_messages.count_documents = AsyncMock(return_value=0)
    mock_db.tenant_delivery_proofs.find = MagicMock(return_value=_async_iter([]))
    mock_db.maintenance_issues.find = MagicMock(return_value=_async_iter([]))
    mock_db.work_orders.find = MagicMock(return_value=_async_iter([]))
    mock_db.property_tenancies.find_one = AsyncMock(return_value=None)

    with patch("services.property_occupancy_operational_service.database") as db_mod:
        db_mod.get_db.return_value = mock_db
        with patch(
            "services.client_calendar_timeline_service.get_timeline_events_for_range",
            new=AsyncMock(return_value=[]),
        ):
            body = await build_property_occupancy_operational_summary(
                "c1", "p1", include_rent=False, include_maintenance=False, include_tenant_portal=True
            )
    assert body["applicability"]["occupancy"] == "student"
    assert body["tenancy_lifecycle"]["tenancy_active"] is True
    assert body["tenancy_lifecycle"]["rent_tenancy_ready"] is False
    assert body["rent_tenancy"]["ready"] is False
    assert "authority_note" in body
    assert any(a.get("kind") == "rent_tenancy_not_set_up" for a in body["operational_alerts"])


@pytest.mark.asyncio
async def test_build_summary_rent_tenancy_ready_when_property_tenancy_exists():
    from services.property_occupancy_operational_service import build_property_occupancy_operational_summary

    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "occupancy": "student",
            "tenancy_active": True,
            "nickname": "Oak City",
        }
    )
    mock_db.property_tenancies.find_one = AsyncMock(
        return_value={
            "tenancy_id": "pty_oak",
            "tenant_display_name": "Oak City",
            "status": "active",
            "rent_tracking_enabled": True,
            "started_at": "2026-08-01T00:00:00+00:00",
        }
    )
    mock_db.portal_users.find = MagicMock(return_value=_async_iter([]))
    mock_db.tenant_assignments.find = MagicMock(return_value=_async_iter([]))
    mock_db.tenant_requests.find = MagicMock(return_value=_async_iter([]))
    mock_db.tenant_messages.count_documents = AsyncMock(return_value=0)
    mock_db.tenant_delivery_proofs.find = MagicMock(return_value=_async_iter([]))
    mock_db.maintenance_issues.find = MagicMock(return_value=_async_iter([]))
    mock_db.work_orders.find = MagicMock(return_value=_async_iter([]))

    with patch("services.property_occupancy_operational_service.database") as db_mod:
        db_mod.get_db.return_value = mock_db
        with patch(
            "services.client_calendar_timeline_service.get_timeline_events_for_range",
            new=AsyncMock(return_value=[]),
        ):
            body = await build_property_occupancy_operational_summary(
                "c1", "p1", include_rent=False, include_maintenance=False, include_tenant_portal=True
            )
    assert body["tenancy_lifecycle"]["rent_tenancy_ready"] is True
    assert body["rent_tenancy"]["tenant_display_name"] == "Oak City"
    assert not any(a.get("kind") == "rent_tenancy_not_set_up" for a in body["operational_alerts"])


def _async_iter(items):
    class _Cursor:
        def sort(self, *args, **kwargs):
            return self

        def limit(self, n):
            return self

        async def to_list(self, n=None):
            return list(items)

    return _Cursor()
