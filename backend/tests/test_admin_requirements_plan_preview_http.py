"""Admin read-only GET /api/admin/properties/{id}/requirements/plan-preview."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes.admin import get_property_requirements_plan_preview


@pytest.mark.asyncio
async def test_plan_preview_returns_planned_types_and_mongo_snapshot():
    request = MagicMock()
    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p-prev-1",
            "client_id": "c-prev-1",
            "jurisdiction": "England",
            "property_type": "house",
            "is_hmo": False,
            "has_gas_supply": True,
        }
    )
    db.clients.find_one = AsyncMock(return_value={"client_id": "c-prev-1", "default_jurisdiction": None})
    db.requirements.find = MagicMock(
        return_value=MagicMock(
            to_list=AsyncMock(
                return_value=[
                    {
                        "requirement_id": "r1",
                        "requirement_type": "gas_safety",
                        "requirement_code": "gas_safety",
                        "requirement_generation_source": "catalog_registry",
                        "client_surface_visible": True,
                        "applicability": "UNKNOWN",
                        "status": "PENDING",
                        "is_tracked": True,
                    }
                ]
            )
        )
    )

    with (
        patch("routes.admin.admin_route_guard", new_callable=AsyncMock),
        patch("routes.admin.database.get_db", return_value=db),
    ):
        out = await get_property_requirements_plan_preview(
            request,
            "p-prev-1",
            include_mongo_snapshot=True,
            include_explanations=True,
        )

    assert out["property_id"] == "p-prev-1"
    assert out["client_id"] == "c-prev-1"
    assert "gas_safety" in out["planned_types"]
    assert out.get("plan_builder") == "build_requirement_plan_for_property"
    assert "catalog_key_explanations" in out
    assert any("explanation" in p for p in out["planned"])
    assert out["portfolio_jurisdiction_label"]
    assert out["mongo_snapshot"]["row_count"] == 1
    assert out["mongo_snapshot"]["requirement_generation_source_counts"].get("catalog_registry") == 1
    assert out["mongo_snapshot"]["portal_visible_row_count"] == 1


@pytest.mark.asyncio
async def test_plan_preview_404_when_property_missing():
    request = MagicMock()
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value=None)

    with (
        patch("routes.admin.admin_route_guard", new_callable=AsyncMock),
        patch("routes.admin.database.get_db", return_value=db),
    ):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as ei:
            await get_property_requirements_plan_preview(request, "missing", include_mongo_snapshot=False)
        assert ei.value.status_code == 404
