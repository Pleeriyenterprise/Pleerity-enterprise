"""Thin HTTP tests: PATCH rematerialisation and POST requirements/sync."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server import app


@pytest.fixture
def client():
    return TestClient(app)


async def _mock_guard(_request):
    return {"client_id": "c1", "portal_user_id": "u1", "role": "ROLE_CLIENT"}


def _base_prop(**overrides):
    doc = {
        "property_id": "p1",
        "client_id": "c1",
        "property_type": "house",
        "is_hmo": False,
        "bedrooms": 2,
        "occupancy": None,
        "licence_required": None,
        "has_gas_supply": True,
        "has_gas": None,
        "tenancy_active": None,
        "furnished": None,
        "is_active": True,
    }
    doc.update(overrides)
    return doc


def test_patch_is_hmo_change_calls_materialize_before_recalc(client):
    """Applicability change (is_hmo) must await registry materialisation."""
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value=_base_prop(is_hmo=False))
    db.properties.update_one = AsyncMock()

    mat = AsyncMock(return_value={"ok": True, "planned_types": ["gas_safety", "eicr"]})
    enqueue = AsyncMock()

    with (
        patch("routes.properties.client_route_guard", side_effect=_mock_guard),
        patch("routes.properties.database.get_db", return_value=db),
        patch(
            "services.provisioning_status_hook.update_provisioning_status_for_property",
            new_callable=AsyncMock,
        ),
        patch(
            "services.requirement_materialization_service.materialize_requirements_for_property",
            mat,
        ),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
    ):
        r = client.patch(
            "/api/properties/p1",
            json={"is_hmo": True},
            headers={"Authorization": "Bearer t"},
        )

    assert r.status_code == 200
    assert r.json().get("property_id") == "p1"
    mat.assert_awaited_once()
    assert mat.await_args[0][0] == "c1"
    assert mat.await_args[0][1] == "p1"
    assert mat.await_args[1].get("reconcile_obsolete") is True
    enqueue.assert_awaited_once()


def test_patch_jurisdiction_change_calls_materialize_and_recalculate(client):
    """Jurisdiction change must rematerialise then run synchronous score path (mocked)."""
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value=_base_prop(jurisdiction="England"))
    db.properties.update_one = AsyncMock()

    mat = AsyncMock(return_value={"ok": True, "planned_types": ["scotland_landlord_registration"]})
    recalc = AsyncMock(return_value=None)

    with (
        patch("routes.properties.client_route_guard", side_effect=_mock_guard),
        patch("routes.properties.database.get_db", return_value=db),
        patch(
            "services.provisioning_status_hook.update_provisioning_status_for_property",
            new_callable=AsyncMock,
        ),
        patch(
            "services.requirement_materialization_service.materialize_requirements_for_property",
            mat,
        ),
        patch("services.compliance_scoring_service.recalculate_and_persist", recalc),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
    ):
        r = client.patch(
            "/api/properties/p1",
            json={"jurisdiction": "Scotland"},
            headers={"Authorization": "Bearer t"},
        )

    assert r.status_code == 200
    mat.assert_awaited_once()
    recalc.assert_awaited_once()


def test_post_requirements_sync_calls_materialize_update_compliance_enqueue(client):
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "client_id": "c1"})

    mat = AsyncMock(return_value={"ok": True, "reconciled_obsolete": 0})
    upd_compliance = AsyncMock()
    enqueue = AsyncMock()

    with (
        patch("routes.properties.client_route_guard", side_effect=_mock_guard),
        patch("routes.properties.database.get_db", return_value=db),
        patch(
            "services.requirement_materialization_service.materialize_requirements_for_property",
            mat,
        ),
        patch(
            "services.provisioning.provisioning_service._update_property_compliance",
            upd_compliance,
        ),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue),
    ):
        r = client.post(
            "/api/properties/p1/requirements/sync",
            headers={"Authorization": "Bearer t"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body.get("message") == "Requirements synchronized"
    assert body.get("ok") is True
    mat.assert_awaited_once()
    upd_compliance.assert_awaited_once_with("p1")
    enqueue.assert_awaited_once()


def test_post_requirements_sync_404_when_property_missing(client):
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value=None)

    with (
        patch("routes.properties.client_route_guard", side_effect=_mock_guard),
        patch("routes.properties.database.get_db", return_value=db),
    ):
        r = client.post(
            "/api/properties/p-missing/requirements/sync",
            headers={"Authorization": "Bearer t"},
        )

    assert r.status_code == 404
