"""Tests: building_age_years on property create/PATCH triggers rematerialisation."""
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
        "property_type": "flat",
        "jurisdiction": "Scotland",
        "is_hmo": False,
        "bedrooms": 2,
        "occupancy": None,
        "licence_required": None,
        "has_gas_supply": True,
        "has_gas": None,
        "tenancy_active": True,
        "furnished": None,
        "building_age_years": None,
        "is_active": True,
    }
    doc.update(overrides)
    return doc


def test_patch_building_age_years_change_calls_materialize(client):
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value=_base_prop(building_age_years=None))
    db.properties.update_one = AsyncMock()

    mat = AsyncMock(return_value={"ok": True, "planned_types": ["lead_testing"]})
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
            json={"building_age_years": 70},
            headers={"Authorization": "Bearer t"},
        )

    assert r.status_code == 200
    mat.assert_awaited_once()
    enqueue.assert_awaited_once()


def test_patch_building_age_years_rejects_out_of_range(client):
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value=_base_prop())

    with (
        patch("routes.properties.client_route_guard", side_effect=_mock_guard),
        patch("routes.properties.database.get_db", return_value=db),
    ):
        r = client.patch(
            "/api/properties/p1",
            json={"building_age_years": 501},
            headers={"Authorization": "Bearer t"},
        )

    assert r.status_code == 422


def test_create_property_accepts_optional_building_age_years(client):
    db = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={"client_id": "c1", "onboarding_status": "PROVISIONED", "default_jurisdiction": "Scotland"}
    )
    db.properties.count_documents = AsyncMock(return_value=0)
    db.properties.insert_one = AsyncMock()

    with (
        patch("routes.properties.client_route_guard", side_effect=_mock_guard),
        patch("routes.properties.database.get_db", return_value=db),
        patch("services.plan_registry.plan_registry.enforce_property_limit", new_callable=AsyncMock, return_value=(True, None, None)),
        patch("routes.properties.create_audit_log", new_callable=AsyncMock),
        patch("services.provisioning.provisioning_service._generate_requirements", new_callable=AsyncMock),
        patch("services.provisioning.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock),
        patch("services.provisioning_status_hook.update_provisioning_status_for_property", new_callable=AsyncMock),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
    ):
        r = client.post(
            "/api/properties/create",
            json={
                "address_line_1": "1 Test Street",
                "city": "Edinburgh",
                "postcode": "EH1 1AA",
                "property_type": "flat",
                "jurisdiction": "Scotland",
                "building_age_years": 80,
            },
            headers={"Authorization": "Bearer t"},
        )

    assert r.status_code == 200
    insert_doc = db.properties.insert_one.call_args[0][0]
    assert insert_doc.get("building_age_years") == 80
