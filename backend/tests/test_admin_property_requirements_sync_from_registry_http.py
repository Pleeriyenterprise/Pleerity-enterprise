"""Admin POST /api/admin/properties/{id}/requirements/sync-from-registry."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from models import AuditAction
from routes.admin import admin_post_property_requirements_sync_from_registry


@pytest.mark.asyncio
async def test_admin_sync_from_registry_materializes_and_enqueues():
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={"property_id": "p-sync-1", "client_id": "c-sync-1"},
    )

    user = {"portal_user_id": "pu-1", "role": "ROLE_ADMIN"}

    mat = AsyncMock(
        return_value={"ok": True, "planned_types": ["gas_safety"], "foo": "bar"},
    )
    upd = AsyncMock()
    enq = AsyncMock()
    audit = AsyncMock()

    with (
        patch("routes.admin.database.get_db", return_value=db),
        patch(
            "services.requirement_materialization_service.materialize_requirements_for_property",
            mat,
        ),
        patch(
            "services.provisioning.provisioning_service._update_property_compliance",
            upd,
        ),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enq),
        patch("routes.admin.create_audit_log", audit),
    ):
        out = await admin_post_property_requirements_sync_from_registry(request, "p-sync-1", user)

    assert out["ok"] is True
    assert out["property_id"] == "p-sync-1"
    assert out["client_id"] == "c-sync-1"
    assert out["planned_types"] == ["gas_safety"]
    mat.assert_awaited_once_with("c-sync-1", "p-sync-1", reconcile_obsolete=True)
    upd.assert_awaited_once_with("p-sync-1")
    enq.assert_awaited_once()
    audit.assert_awaited_once()
    call_kw = audit.await_args.kwargs
    assert call_kw["action"] == AuditAction.COMPLIANCE_REGISTRY_ADMIN_PROPERTY_REQUIREMENTS_SYNCED
    assert call_kw["client_id"] == "c-sync-1"
    assert call_kw["resource_id"] == "p-sync-1"


@pytest.mark.asyncio
async def test_admin_sync_from_registry_404_missing_property():
    request = MagicMock()
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value=None)
    user = {"portal_user_id": "pu-1", "role": "ROLE_ADMIN"}

    with patch("routes.admin.database.get_db", return_value=db):
        with pytest.raises(HTTPException) as ei:
            await admin_post_property_requirements_sync_from_registry(request, "missing", user)
        assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_sync_from_registry_400_no_client_id():
    request = MagicMock()
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value={"property_id": "p-x", "client_id": None})
    user = {"portal_user_id": "pu-1", "role": "ROLE_ADMIN"}

    with patch("routes.admin.database.get_db", return_value=db):
        with pytest.raises(HTTPException) as ei:
            await admin_post_property_requirements_sync_from_registry(request, "p-x", user)
        assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_admin_sync_from_registry_404_materializer_property_not_found():
    request = MagicMock()
    request.client = None
    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={"property_id": "p-sync-1", "client_id": "c-sync-1"},
    )
    user = {"portal_user_id": "pu-1", "role": "ROLE_SUPPORT"}

    mat = AsyncMock(return_value={"ok": False, "reason": "property_not_found"})

    with (
        patch("routes.admin.database.get_db", return_value=db),
        patch(
            "services.requirement_materialization_service.materialize_requirements_for_property",
            mat,
        ),
    ):
        with pytest.raises(HTTPException) as ei:
            await admin_post_property_requirements_sync_from_registry(request, "p-sync-1", user)
        assert ei.value.status_code == 404
