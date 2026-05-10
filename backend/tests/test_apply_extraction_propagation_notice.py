"""L-009d: propagation_notice on POST /api/documents/{id}/apply-extraction (apply_ai_extraction)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from database import database as db_singleton
from services.client_propagation_notice import NOTICE_AUTHORITY_SYNC_DEFERRED
from services.evidence_document_taxonomy import MATCH_OUTCOME_MATCH_CONFIRMED


@pytest.mark.asyncio
async def test_apply_ai_extraction_propagation_notice_when_authority_deferred():
    from routes import documents as dr
    from routes.documents import apply_ai_extraction

    doc_id = "doc-apply-pn"
    document = {
        "document_id": doc_id,
        "client_id": "cli-em",
        "property_id": "prop-em",
        "requirement_id": "req-em",
        "file_name": "gas.pdf",
        "document_type": "Gas safety certificate",
        "ai_extraction": {
            "status": "completed",
            "data": {"document_type": "Gas safety certificate", "expiry_date": "2030-01-15"},
        },
    }
    requirement = {
        "requirement_id": "req-em",
        "client_id": "cli-em",
        "property_id": "prop-em",
        "status": "PENDING",
        "due_date": None,
        "requirement_type": "gas_safety",
    }
    apply_ok = {
        "evidence_satisfies_requirement": True,
        "match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED,
        "requirement_evidence_mismatch": False,
        "match_confidence": 0.9,
        "predicted_document_type": "gas_safety",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=document)
    mock_db.requirements.find_one = AsyncMock(return_value=requirement)
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "prop-em", "client_id": "cli-em"})
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.notification_preferences.find_one = AsyncMock(return_value={"document_updates": False})

    user = {"client_id": "cli-em", "portal_user_id": "pu-cli", "role": "ROLE_CLIENT_ADMIN"}
    request = MagicMock(spec=Request)

    async def fake_document_path_sync(
        db,
        requirement_id,
        *,
        property_id,
        client_id,
        correlation_base,
        transition_origin,
        transition_fanout,
        document_id=None,
        **kwargs,
    ):
        if isinstance(transition_fanout, dict):
            transition_fanout["rst_core_backbone_activation"] = {
                "permitted": False,
                "activation_reason": "unit_test_apply_extraction",
            }

    async def guard(_req):
        return user

    with (
        patch.object(dr, "client_route_guard", guard),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(dr, "evaluate_document_requirement_match", return_value=apply_ok),
        patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(dr, "_document_path_sync_requirement_authority", new_callable=AsyncMock, side_effect=fake_document_path_sync),
        patch.object(dr, "_document_path_enqueue_recalc", new_callable=AsyncMock),
        patch.object(dr, "create_audit_log", new_callable=AsyncMock),
        patch.object(dr, "_append_document_evidence_to_work_order", new_callable=AsyncMock),
        patch.object(dr, "_set_compliance_work_order_proof_verified", new_callable=AsyncMock),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
        patch(
            "services.property_assets_service.update_asset_last_service_from_requirement",
            new_callable=AsyncMock,
        ),
    ):
        out = await apply_ai_extraction(request, doc_id, None)

    assert out.get("document_id") == doc_id
    assert (out.get("propagation_notice") or {}).get("code") == NOTICE_AUTHORITY_SYNC_DEFERRED
