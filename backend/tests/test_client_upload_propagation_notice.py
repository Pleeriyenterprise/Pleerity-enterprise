"""L-009e: propagation_notice on client document upload (perform_client_document_upload)."""

from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import UploadFile

from database import database as db_singleton
from routes import documents as dr
from routes.documents import perform_client_document_upload
from services.client_propagation_notice import NOTICE_AUTHORITY_SYNC_DEFERRED
from services.evidence_document_taxonomy import MATCH_OUTCOME_MATCH_LIKELY, POLICY_ACCEPT_PENDING


@pytest.mark.asyncio
async def test_perform_client_upload_propagation_notice_when_backbone_defers_authority(tmp_path):
    user = {"client_id": "cli-cu", "portal_user_id": "pu-cu", "role": "ROLE_CLIENT_ADMIN"}
    pid, rid = "prop-cu", "req-cu"
    prop = {"property_id": pid, "client_id": user["client_id"], "is_active": True}
    req = {"requirement_id": rid, "client_id": user["client_id"], "property_id": pid, "requirement_type": "gas_safety"}
    ev_ok = {
        "evidence_match_policy": POLICY_ACCEPT_PENDING,
        "evidence_satisfies_requirement": True,
        "match_outcome": MATCH_OUTCOME_MATCH_LIKELY,
        "match_confidence": 0.7,
        "predicted_document_type": "gas_safety",
        "user_messages": [],
        "mismatch_reason_code": None,
        "mismatch_reason_text": None,
    }

    mock_db = MagicMock()

    async def find_one(filter_q, *args, **kwargs):
        if filter_q.get("property_id") == pid and filter_q.get("client_id") == user["client_id"]:
            return prop
        if filter_q.get("requirement_id") == rid:
            return req
        if filter_q.get("client_id") == user["client_id"] and "default_jurisdiction" in str(kwargs):
            return {}
        return None

    mock_db.properties.find_one = AsyncMock(side_effect=find_one)
    mock_db.requirements.find_one = AsyncMock(side_effect=find_one)
    mock_db.clients.find_one = AsyncMock(return_value={})
    mock_db.documents.insert_one = AsyncMock()

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
                "activation_reason": "unit_test_client_upload",
            }

    buf = BytesIO(b"%PDF-1.4")
    uf = UploadFile(filename="cert.pdf", file=buf)

    def _discard_background_task(coro):
        if asyncio.iscoroutine(coro):
            coro.close()
        return MagicMock()

    with (
        patch.object(dr, "DOCUMENT_STORAGE_PATH", tmp_path),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "services.compliance_rules_registry.validate_document_upload_for_requirement",
            return_value={"valid": True},
        ),
        patch.object(dr, "evaluate_document_requirement_match", return_value=ev_ok),
        patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(dr, "_validate_optional_work_order_document_link", new_callable=AsyncMock, return_value=None),
        patch.object(dr, "safe_upsert_document_upload_evidence_for_linked_document", new_callable=AsyncMock),
        patch.object(dr, "_document_path_sync_requirement_authority", new_callable=AsyncMock, side_effect=fake_document_path_sync),
        patch.object(dr, "_document_path_enqueue_recalc", new_callable=AsyncMock),
        patch("services.provisioning.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
        patch("routes.documents.create_audit_log", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
        patch("services.analytics_service.log_event", new_callable=AsyncMock),
        patch("services.analytics_service.log_first_doc_uploaded_once", new_callable=AsyncMock),
        patch("routes.documents.asyncio.create_task", side_effect=_discard_background_task),
    ):
        out = await perform_client_document_upload(
            user=user,
            file=uf,
            property_id=pid,
            requirement_id=rid,
            document_type="Gas safety certificate",
        )

    assert out.get("document_id")
    assert (out.get("propagation_notice") or {}).get("code") == NOTICE_AUTHORITY_SYNC_DEFERRED
