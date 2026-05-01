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


def test_patch_jurisdiction_change_syncs_gaps_after_materialization(client):
    """Stream E2.3: after successful materialisation, sync compliance gaps for property requirements."""
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value=_base_prop(jurisdiction="England"))
    db.properties.update_one = AsyncMock()
    req_rows = [
        {"requirement_id": "r1", "client_id": "c1", "property_id": "p1", "requirement_type": "GAS_SAFETY"},
        {"requirement_id": "r2", "client_id": "c1", "property_id": "p1", "requirement_type": "EICR"},
    ]
    req_find = MagicMock()
    req_find.to_list = AsyncMock(return_value=req_rows)
    db.requirements.find = MagicMock(return_value=req_find)

    mat = AsyncMock(return_value={"ok": True, "planned_types": ["scotland_landlord_registration"]})
    recalc = AsyncMock(return_value=None)
    gap_sync = AsyncMock()

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
        patch("services.compliance_gap_sync.sync_compliance_gaps_for_requirement", gap_sync),
    ):
        r = client.patch(
            "/api/properties/p1",
            json={"jurisdiction": "Scotland"},
            headers={"Authorization": "Bearer t"},
        )

    assert r.status_code == 200
    mat.assert_awaited_once()
    assert gap_sync.await_count == 2
    gap_sync.assert_any_call(db, req_rows[0], property_doc=_base_prop(jurisdiction="England"))
    gap_sync.assert_any_call(db, req_rows[1], property_doc=_base_prop(jurisdiction="England"))
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
