from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.catalog_compliance import get_property_compliance_detail


@pytest.mark.asyncio
async def test_compliance_detail_matrix_includes_canonical_take_action_for_multi_mode_requirement():
    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value={"property_id": "prop-1", "client_id": "client-1"})
    db.clients.find_one = AsyncMock(return_value={"client_id": "client-1", "default_jurisdiction": "england"})
    db.requirements.find.return_value.to_list = AsyncMock(
        return_value=[{"requirement_id": "req-1", "requirement_code": "gas_safety"}]
    )
    db.documents.find.return_value.to_list = AsyncMock(return_value=[])

    enriched_rows = [
        {
            "requirement_id": "req-1",
            "canonical_code": "gas_safety",
            "status": "MISSING",
            "display_name": "Gas Safety Certificate",
            "take_action": {
                "primary": {
                    "kind": "guided",
                    "intent": "guided_evidence",
                    "label": "Start guided evidence",
                }
            },
            "registry_metadata": {
                "evidence_resolution": {
                    "allowed_evidence_modes": ["DOCUMENT_UPLOAD", "STRUCTURED_DECLARATION"]
                }
            },
        }
    ]

    with patch("services.catalog_compliance.database.get_db", return_value=db), patch(
        "services.catalog_compliance.filter_requirement_rows_for_client_runtime_surfaces",
        AsyncMock(return_value=[{"requirement_id": "req-1", "requirement_code": "gas_safety"}]),
    ), patch(
        "services.requirement_truth.enrich_requirements_for_client",
        AsyncMock(return_value=(enriched_rows, {})),
    ), patch(
        "services.catalog_compliance._load_catalog",
        AsyncMock(return_value=[{"code": "gas_safety", "weight": 3, "criticality": "HIGH"}]),
    ):
        result = await get_property_compliance_detail("client-1", "prop-1")

    assert result is not None
    assert len(result["matrix"]) == 1
    row = result["matrix"][0]
    assert row["take_action"]["primary"]["kind"] == "guided"
    assert row["take_action"]["primary"]["intent"] == "guided_evidence"
    assert row["allowed_evidence_modes"] == ["DOCUMENT_UPLOAD", "STRUCTURED_DECLARATION"]
    assert row["primary_action_kind"] == "guided"
    assert row["primary_action_intent"] == "guided_evidence"
