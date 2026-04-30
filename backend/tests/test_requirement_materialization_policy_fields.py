from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_requirement_registry import RequirementPlanItem
from services.requirement_materialization_service import materialize_requirements_for_property


@pytest.mark.asyncio
async def test_materialize_writes_normalized_policy_fields_on_insert():
    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "England",
            "property_type": "house",
            "has_gas_supply": True,
        }
    )
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "default_jurisdiction": "England"})
    db.requirements.find_one = AsyncMock(return_value=None)
    db.requirements.insert_one = AsyncMock()

    item = RequirementPlanItem(
        requirement_type="gas_safety",
        requirement_code="gas_safety",
        description="Gas safety",
        frequency_days=365,
        warning_days=30,
        portfolio_jurisdiction_label="England",
        compliance_requirement_class="DOCUMENT",
        is_tracked=True,
    )

    with patch("services.requirement_materialization_service.database.get_db", return_value=db), patch(
        "services.requirement_materialization_service.fetch_active_published_registry_entries",
        new=AsyncMock(return_value={}),
    ), patch(
        "services.requirement_materialization_service.build_requirement_plan_for_property",
        return_value=[item],
    ):
        out = await materialize_requirements_for_property("c1", "p1", reconcile_obsolete=False)

    assert out["ok"] is True
    args, _kwargs = db.requirements.insert_one.await_args
    doc = args[0]
    assert doc["requirement_code_normalized"] == "gas_safety"
    assert doc["applicability_state"] == "UNKNOWN"
    assert doc["is_mandatory"] is True
    assert doc["policy_criticality"] == "MEDIUM"
    assert doc["evidence_state_normalized"] == "MISSING"
    assert doc["policy_classification_version"] == "v1"
