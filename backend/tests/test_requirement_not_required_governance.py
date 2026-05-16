from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_requirement_registry import RequirementPlanItem
from services.requirement_materialization_service import materialize_requirements_for_property
from services.requirement_not_required_governance import (
    is_already_reconciled_obsolete,
    is_operator_curated_not_required,
)


def test_operator_curated_not_required_detects_override_and_audit():
    assert is_operator_curated_not_required(
        {
            "applicability": "NOT_REQUIRED",
            "not_required_reason": "not_applicable",
            "applicability_provenance": {
                "operator_override": {"active": True, "applicability_state": "NOT_REQUIRED"}
            },
        }
    )
    assert is_operator_curated_not_required(
        {
            "applicability": "NOT_REQUIRED",
            "not_applicable_audit_reason": "Operator marked not applicable for this unit",
        }
    )
    assert not is_operator_curated_not_required(
        {
            "applicability": "NOT_REQUIRED",
            "not_required_reason": "not_applicable",
        }
    )


def test_already_reconciled_obsolete_detects_converged_row():
    assert is_already_reconciled_obsolete(
        {
            "applicability": "NOT_REQUIRED",
            "status": "NOT_REQUIRED",
            "registry_metadata": {
                "reconciled_obsolete": True,
                "reconciled_at": "2026-05-16T00:00:00+00:00",
            },
        }
    )
    assert not is_already_reconciled_obsolete(
        {
            "applicability": "NOT_REQUIRED",
            "status": "PENDING",
            "registry_metadata": {"reconciled_obsolete": True},
        }
    )


@pytest.mark.asyncio
async def test_reconcile_obsolete_skips_already_reconciled_row():
    db = MagicMock()
    db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "Wales",
            "property_type": "hmo",
        }
    )
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1"})
    db.requirements.find_one = AsyncMock(return_value=None)
    db.requirements.insert_one = AsyncMock()

    obsolete = {
        "requirement_id": "rid-ni",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "landlord_registration_ni",
        "requirement_generation_source": "catalog_registry",  # REQUIREMENT_GENERATION_SOURCE_REGISTRY
        "applicability": "NOT_REQUIRED",
        "status": "NOT_REQUIRED",
        "registry_metadata": {
            "reconciled_obsolete": True,
            "reconciled_at": "2026-05-16T00:00:00+00:00",
            "automated_not_required": {"reason": "RECONCILE_OBSOLETE", "classification": "automated"},
        },
    }

    class _ReconcileCursor:
        def __init__(self, rows):
            self._rows = list(rows)
            self._i = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._i >= len(self._rows):
                raise StopAsyncIteration
            row = self._rows[self._i]
            self._i += 1
            return row

    db.requirements.find = MagicMock(return_value=_ReconcileCursor([obsolete]))
    db.requirements.update_one = AsyncMock()

    item = RequirementPlanItem(
        requirement_type="gas_safety",
        requirement_code="gas_safety",
        description="Gas",
        frequency_days=365,
        warning_days=30,
        portfolio_jurisdiction_label="Wales",
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
        out = await materialize_requirements_for_property("c1", "p1", reconcile_obsolete=True)

    assert out["reconciled_obsolete"] == 0
    db.requirements.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_materialize_reopens_automated_not_required_in_plan():
    db = MagicMock()
    db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "Wales",
            "property_type": "hmo",
            "is_hmo": True,
        }
    )
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "default_jurisdiction": "Wales"})
    existing = {
        "requirement_id": "rid-eicr",
        "requirement_type": "eicr",
        "requirement_code": "eicr",
        "applicability": "NOT_REQUIRED",
        "status": "NOT_REQUIRED",
        "not_required_reason": "not_applicable",
        "client_surface_visible": False,
    }
    db.requirements.find_one = AsyncMock(return_value=existing)
    db.requirements.update_one = AsyncMock()

    item = RequirementPlanItem(
        requirement_type="eicr",
        requirement_code="eicr",
        description="EICR",
        frequency_days=1825,
        warning_days=30,
        portfolio_jurisdiction_label="Wales",
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

    assert out["reopened_from_not_required"] == 1
    update_doc = db.requirements.update_one.await_args[0][1]
    assert update_doc["$set"]["applicability"] == "UNKNOWN"
    assert update_doc["$set"]["status"] == "PENDING"
    assert update_doc["$set"]["not_required_reason"] is None
    assert "$unset" in update_doc
    assert "not_applicable_audit_reason" in update_doc["$unset"]


@pytest.mark.asyncio
async def test_materialize_skips_operator_curated_not_required():
    db = MagicMock()
    db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "Wales",
            "property_type": "hmo",
            "is_hmo": True,
        }
    )
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1"})
    existing = {
        "requirement_id": "rid-gas",
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "applicability": "NOT_REQUIRED",
        "status": "NOT_REQUIRED",
        "not_required_reason": "not_applicable",
        "not_applicable_audit_reason": "Operator confirmed no gas supply on site",
        "client_surface_visible": False,
    }
    db.requirements.find_one = AsyncMock(return_value=existing)
    db.requirements.update_one = AsyncMock()

    item = RequirementPlanItem(
        requirement_type="gas_safety",
        requirement_code="gas_safety",
        description="Gas",
        frequency_days=365,
        warning_days=30,
        portfolio_jurisdiction_label="Wales",
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

    assert out["reopened_from_not_required"] == 0
    db.requirements.update_one.assert_not_awaited()
