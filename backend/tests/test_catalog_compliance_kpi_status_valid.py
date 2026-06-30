"""Regression: catalog compliance KPI status_valid aligns with COMPLIANT|VALID filter semantics."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.catalog_compliance import get_property_compliance_detail


def _apply_catalog_patches(stack: ExitStack, db, enriched_rows, *, canonical_ids=None):
    canonical_ids = canonical_ids or {r["requirement_id"] for r in enriched_rows}
    stack.enter_context(patch("services.catalog_compliance.database.get_db", return_value=db))
    stack.enter_context(
        patch(
            "services.catalog_compliance.filter_requirement_rows_for_client_runtime_surfaces",
            AsyncMock(return_value=[{"requirement_id": r["requirement_id"]} for r in enriched_rows]),
        )
    )
    stack.enter_context(
        patch(
            "services.requirement_truth.enrich_requirements_for_client",
            AsyncMock(return_value=(enriched_rows, {})),
        )
    )
    stack.enter_context(
        patch(
            "services.catalog_compliance._load_catalog",
            AsyncMock(return_value=[{"code": "gas_safety", "weight": 1, "criticality": "HIGH"}]),
        )
    )
    stack.enter_context(
        patch(
            "services.catalog_compliance.get_canonical_requirement_ids_for_property",
            AsyncMock(return_value=canonical_ids),
        )
    )


def _base_db():
    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={"property_id": "prop-a", "client_id": "client-1", "nickname": "Cottage"}
    )
    db.clients.find_one = AsyncMock(return_value={"client_id": "client-1", "default_jurisdiction": "england"})
    db.requirements.find.return_value.to_list = AsyncMock(return_value=[])
    db.documents.find.return_value.to_list = AsyncMock(return_value=[])
    return db


def _row(*, rid, code, status, missing_evidence=True, satisfied=False):
    return {
        "requirement_id": rid,
        "canonical_code": code,
        "requirement_code": code,
        "status": status,
        "display_name": code,
        "requirement_satisfied": satisfied,
        "missing_required_document": missing_evidence,
        "client_surface_visible": True,
    }


@pytest.mark.asyncio
async def test_status_valid_zero_when_pending_non_missing_evidence_but_compliant_kpi_nonzero():
    """Property A pattern: PENDING rows with missing_evidence=false count as compliant, not status_valid."""
    db = _base_db()
    enriched = [
        _row(rid="r-gas", code="gas_safety", status="PENDING", missing_evidence=True),
        _row(rid="r-leg", code="legionella", status="PENDING", missing_evidence=False, satisfied=True),
        _row(rid="r-hmo", code="hmo_fire_risk", status="PENDING", missing_evidence=False, satisfied=True),
    ]
    with ExitStack() as stack:
        _apply_catalog_patches(stack, db, enriched)
        result = await get_property_compliance_detail("client-1", "prop-a")

    assert result is not None
    assert result["kpis"]["compliant"] == 2
    assert result["kpis"]["status_valid"] == 0
    assert result["kpis"]["missing"] == 1
    assert result["kpis"]["lifecycle_satisfied_count"] == 2


@pytest.mark.asyncio
async def test_lifecycle_satisfied_counts_satisfied_rows_independent_of_status_valid():
    """Mixed evidence: PENDING satisfied rows count toward lifecycle_satisfied, not status_valid."""
    db = _base_db()
    enriched = [
        _row(rid="r-eicr", code="eicr", status="COMPLIANT", missing_evidence=False, satisfied=True),
        _row(rid="r-epc", code="epc", status="COMPLIANT", missing_evidence=False, satisfied=True),
        _row(rid="r-leg", code="legionella", status="PENDING", missing_evidence=False, satisfied=True),
        _row(rid="r-fire", code="fire_risk", status="PENDING", missing_evidence=False, satisfied=True),
        _row(rid="r-hmo", code="hmo_fire_risk", status="PENDING", missing_evidence=False, satisfied=True),
    ]
    with ExitStack() as stack:
        _apply_catalog_patches(stack, db, enriched)
        result = await get_property_compliance_detail("client-1", "prop-mixed")

    assert result["kpis"]["status_valid"] == 2
    assert result["kpis"]["lifecycle_satisfied_count"] == 5


@pytest.mark.asyncio
async def test_status_valid_matches_compliant_status_rows():
    """Property B pattern: COMPLIANT rows increment both compliant and status_valid."""
    db = _base_db()
    enriched = [
        _row(rid="r-eicr", code="eicr", status="COMPLIANT", missing_evidence=False),
        _row(rid="r-epc", code="epc", status="COMPLIANT", missing_evidence=False),
        _row(rid="r-leg", code="legionella", status="COMPLIANT", missing_evidence=False),
    ]
    with ExitStack() as stack:
        _apply_catalog_patches(stack, db, enriched)
        result = await get_property_compliance_detail("client-1", "prop-b")

    assert result is not None
    assert result["kpis"]["compliant"] == 3
    assert result["kpis"]["status_valid"] == 3
    assert result["kpis"]["missing"] == 0
    assert result["kpis"]["lifecycle_satisfied_count"] == 3


@pytest.mark.asyncio
async def test_status_valid_counts_valid_status_alias():
    db = _base_db()
    enriched = [_row(rid="r1", code="epc", status="VALID", missing_evidence=False)]
    with ExitStack() as stack:
        _apply_catalog_patches(stack, db, enriched)
        result = await get_property_compliance_detail("client-1", "prop-b")

    assert result["kpis"]["status_valid"] == 1
    assert result["kpis"]["compliant"] == 1
