import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from routes import maintenance as maintenance_routes


def _req():
    return SimpleNamespace(state=SimpleNamespace(user={"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}))


@pytest.mark.asyncio
async def test_update_work_order_requires_reason_for_no_access(monkeypatch):
    async def _guard(_request):
        return {"portal_user_id": "admin-1"}

    monkeypatch.setattr(maintenance_routes, "admin_route_guard", _guard)
    body = maintenance_routes.WorkOrderUpdateBody(operational_exception="NO_ACCESS")
    with pytest.raises(HTTPException) as ex:
        await maintenance_routes.update_work_order(_req(), "wo-1", body)
    assert ex.value.status_code == 400
    assert "reason is required" in str(ex.value.detail)


@pytest.mark.asyncio
async def test_admin_mark_no_access_uses_canonical_update_and_audits(monkeypatch):
    calls = {"audit": 0, "update": 0}

    async def _guard(_request):
        return {"portal_user_id": "admin-1"}

    async def _update(work_order_id, **kwargs):
        calls["update"] += 1
        assert work_order_id == "wo-1"
        assert kwargs["operational_exception"] == "NO_ACCESS"
        assert kwargs["contractor_notes"] == "No entry granted"
        return {"work_order_id": "wo-1", "client_id": "client-1"}

    async def _audit(**_kwargs):
        calls["audit"] += 1

    async def _append(*_args, **_kwargs):
        return None

    monkeypatch.setattr(maintenance_routes, "admin_route_guard", _guard)
    monkeypatch.setattr(maintenance_routes.maintenance_service, "update_work_order", _update)
    monkeypatch.setattr(maintenance_routes, "create_audit_log", _audit)
    monkeypatch.setattr(maintenance_routes, "_append_decision_log", _append)

    out = await maintenance_routes.admin_mark_no_access(
        _req(),
        "wo-1",
        maintenance_routes.AdminActionReasonBody(reason="No entry granted"),
    )
    assert out["work_order_id"] == "wo-1"
    assert calls["update"] == 1
    assert calls["audit"] == 1


@pytest.mark.asyncio
async def test_update_work_order_requires_action_reason_when_status_changes(monkeypatch):
    async def _guard(_request):
        return {"portal_user_id": "admin-1"}

    async def _get(_wid):
        return {"work_order_id": "wo-1", "status": "OPEN", "client_id": "client-1"}

    monkeypatch.setattr(maintenance_routes, "admin_route_guard", _guard)
    monkeypatch.setattr(maintenance_routes.maintenance_service, "get_work_order", _get)

    body = maintenance_routes.WorkOrderUpdateBody(status="COMPLETED")
    with pytest.raises(HTTPException) as ex:
        await maintenance_routes.update_work_order(_req(), "wo-1", body)
    assert ex.value.status_code == 400
    assert "action_reason" in str(ex.value.detail).lower()


@pytest.mark.asyncio
async def test_update_work_order_same_status_skips_action_reason_requirement(monkeypatch):
    async def _guard(_request):
        return {"portal_user_id": "admin-1"}

    async def _get(_wid):
        return {"work_order_id": "wo-1", "status": "OPEN", "client_id": "client-1"}

    async def _update(work_order_id, **kwargs):
        assert work_order_id == "wo-1"
        return {"work_order_id": "wo-1", "client_id": "client-1", "status": "OPEN"}

    monkeypatch.setattr(maintenance_routes, "admin_route_guard", _guard)
    monkeypatch.setattr(maintenance_routes.maintenance_service, "get_work_order", _get)
    monkeypatch.setattr(maintenance_routes.maintenance_service, "update_work_order", _update)
    async def _noop_audit(**_k):
        return None

    async def _noop_append(*_a, **_k):
        return None

    monkeypatch.setattr(maintenance_routes, "create_audit_log", _noop_audit)
    monkeypatch.setattr(maintenance_routes, "_append_decision_log", _noop_append)

    body = maintenance_routes.WorkOrderUpdateBody(status="OPEN")
    out = await maintenance_routes.update_work_order(_req(), "wo-1", body)
    assert out["status"] == "OPEN"

