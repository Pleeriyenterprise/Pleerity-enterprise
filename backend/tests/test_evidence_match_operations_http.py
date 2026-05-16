"""HTTP tests for evidence document match blocking (upload, verify, apply-extraction, admin resolve)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from database import database as db_singleton
from routes import documents as documents_routes
from server import app
from services.evidence_document_taxonomy import POLICY_BLOCK_UPLOAD
from services.client_propagation_notice import (
    NOTICE_AUTHORITY_SYNC_DEFERRED,
    NOTICE_RECALC_ENQUEUE_DEFERRED,
)


@pytest.fixture
def client_http():
    with TestClient(app) as c:
        yield c


def test_client_upload_evidence_mismatch_returns_400_structured(client_http):
    """Wrong document for obligation: perform_client path raises 400 with error_code + evidence_match."""
    user = {"client_id": "cli-em", "portal_user_id": "pu-em", "role": "ROLE_CLIENT_ADMIN"}
    pid, rid = "prop-em", "req-em"
    prop = {"property_id": pid, "client_id": user["client_id"], "is_active": True}
    req = {"requirement_id": rid, "client_id": user["client_id"], "property_id": pid, "requirement_type": "gas_safety"}

    async def guard(request):
        return user

    block_eval = {
        "evidence_match_policy": POLICY_BLOCK_UPLOAD,
        "mismatch_reason_text": "Declared document type does not match this obligation.",
        "user_messages": ["Choose the correct requirement or upload the matching certificate."],
        "match_outcome": "MISMATCH_SUSPECTED",
        "predicted_document_type": "EPC",
        "match_confidence": 0.2,
        "mismatch_reason_code": "TYPE_FAMILY_MISMATCH",
        "evidence_satisfies_requirement": False,
        "manual_review_flag_suggested": True,
        "requirement_evidence_mismatch": True,
    }

    mock_db = MagicMock()

    async def find_one(filter_q, *args, **kwargs):
        if "property_id" in filter_q and filter_q.get("property_id") == pid:
            return prop
        if "requirement_id" in filter_q and filter_q.get("requirement_id") == rid:
            return req
        if filter_q.get("client_id") == user["client_id"] and "default_jurisdiction" in str(kwargs):
            return {}
        return None

    mock_db.properties.find_one = AsyncMock(side_effect=find_one)
    mock_db.clients.find_one = AsyncMock(return_value={})
    mock_db.requirements.find_one = AsyncMock(return_value=req)

    with (
        patch.object(documents_routes, "client_route_guard", guard),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "services.compliance_rules_registry.validate_document_upload_for_requirement",
            return_value={"valid": True},
        ),
        patch.object(documents_routes, "evaluate_document_requirement_match", return_value=block_eval),
        patch("utils.rate_limiter.rate_limiter.check_rate_limit", new_callable=AsyncMock, return_value=(True, None)),
        patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(documents_routes, "_validate_optional_work_order_document_link", new_callable=AsyncMock, return_value=None),
    ):
        res = client_http.post(
            "/api/documents/upload",
            files={"file": ("cert.pdf", b"%PDF-1.4", "application/pdf")},
            data={
                "property_id": pid,
                "requirement_id": rid,
                "document_type": "Gas safety certificate",
            },
        )

    assert res.status_code == 400, res.text
    body = res.json()
    detail = body.get("detail") or {}
    assert detail.get("error_code") == "EVIDENCE_DOCUMENT_TYPE_MISMATCH"
    assert detail.get("evidence_match")


def test_verify_document_409_when_evidence_blocks(client_http):
    doc = {
        "document_id": "doc-em-verify",
        "client_id": "cli-em",
        "property_id": "prop-em",
        "requirement_id": "req-em",
        "status": "UPLOADED",
        "evidence_satisfies_requirement": False,
        "match_outcome": "MISMATCH_SUSPECTED",
    }

    async def find_document(filt, *args, **kwargs):
        if filt.get("document_id") == doc["document_id"]:
            return dict(doc)
        return None

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(side_effect=find_document)
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    admin_user = {"portal_user_id": "admin-em", "client_id": "cli-em", "role": "ROLE_ADMIN"}
    with (
        patch.object(documents_routes, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.documents.create_audit_log", new_callable=AsyncMock),
        patch("services.evidence_review_config.is_feature_evidence_review_v2", return_value=False),
        patch.object(documents_routes, "authority_sync_with_transition_observability", new_callable=AsyncMock),
    ):
        res = client_http.post(f"/api/documents/verify/{doc['document_id']}", json={})

    assert res.status_code == 409, res.text
    detail = res.json().get("detail") or {}
    assert detail.get("error_code") == "EVIDENCE_MATCH_VERIFICATION_BLOCKED"
    assert detail.get("evidence_match")


def test_verify_document_200_with_override_and_audit(client_http):
    doc_id = "doc-em-verify-ov"
    base = {
        "document_id": doc_id,
        "client_id": "cli-em",
        "property_id": "prop-em",
        "requirement_id": "req-em",
        "status": "UPLOADED",
        "evidence_satisfies_requirement": False,
        "match_outcome": "MISMATCH_SUSPECTED",
    }
    calls = {"n": 0}

    async def find_document(filt, *args, **kwargs):
        if filt.get("document_id") != doc_id:
            return None
        calls["n"] += 1
        if calls["n"] == 1:
            return dict(base)
        return {
            **base,
            "evidence_satisfies_requirement": True,
            "match_outcome": "MATCH_CONFIRMED",
            "requirement_evidence_mismatch": False,
        }

    audit_calls = []

    async def capture_audit(**kwargs):
        audit_calls.append(kwargs)

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(side_effect=find_document)
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.find_one = AsyncMock(
        return_value={"requirement_id": "req-em", "requirement_type": "gas_safety", "requirement_code": "GAS"}
    )
    mock_db.requirements.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "prop-em", "address": {"line1": "1 Test"}})

    admin_user = {"portal_user_id": "admin-em", "client_id": "cli-em", "role": "ROLE_ADMIN"}
    with (
        patch.object(documents_routes, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.documents.create_audit_log", new_callable=AsyncMock, side_effect=capture_audit),
        patch("services.evidence_review_config.is_feature_evidence_review_v2", return_value=False),
        patch.object(documents_routes, "authority_sync_with_transition_observability", new_callable=AsyncMock),
        patch(
            "routes.documents._finalize_active_compliance_jobs_after_certificate_verified",
            new_callable=AsyncMock,
        ),
        patch("routes.documents._append_document_evidence_to_work_order", new_callable=AsyncMock),
        patch("routes.documents._set_compliance_work_order_proof_verified", new_callable=AsyncMock),
        patch("services.provisioning.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock),
        patch("services.enablement_service.emit_enablement_event", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
    ):
        res = client_http.post(
            f"/api/documents/verify/{doc_id}",
            json={"evidence_mismatch_override": True, "evidence_mismatch_override_reason": "Manual review OK"},
        )

    assert res.status_code == 200, res.text
    assert any(
        (c.get("metadata") or {}).get("action_type") == "EVIDENCE_MATCH_OVERRIDE_VERIFY" for c in audit_calls
    ), audit_calls


def test_apply_extraction_409_when_match_blocks(client_http):
    doc_id = "doc-em-apply"
    document = {
        "document_id": doc_id,
        "client_id": "cli-em",
        "property_id": "prop-em",
        "requirement_id": "req-em",
        "file_name": "gas.pdf",
        "document_type": "Gas safety certificate",
        "ai_extraction": {"status": "completed", "data": {"document_type": "EICR", "expiry_date": "2030-01-01"}},
    }
    requirement = {"requirement_id": "req-em", "client_id": "cli-em", "property_id": "prop-em"}

    apply_mev = {
        "evidence_satisfies_requirement": False,
        "match_outcome": "MISMATCH_SUSPECTED",
        "user_messages": ["Extraction does not match obligation"],
    }

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=document)
    mock_db.requirements.find_one = AsyncMock(return_value=requirement)
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "prop-em", "client_id": "cli-em"})

    user = {"client_id": "cli-em", "portal_user_id": "pu-cli", "role": "ROLE_CLIENT_ADMIN"}

    async def guard(request):
        return user

    with (
        patch.object(documents_routes, "client_route_guard", guard),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(documents_routes, "evaluate_document_requirement_match", return_value=apply_mev),
        patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        res = client_http.post(
            f"/api/documents/{doc_id}/apply-extraction",
            json={"confirmed_data": {"document_type": "EICR", "expiry_date": "2030-01-01"}},
        )

    assert res.status_code == 409, res.text
    detail = res.json().get("detail") or {}
    assert detail.get("error_code") == "EVIDENCE_MATCH_BLOCKS_APPLY"


@pytest.mark.asyncio
async def test_admin_resolve_evidence_match_approve_direct():
    """POST handler logic without full HTTP auth stack (router uses Depends bound at import)."""
    from fastapi import Request
    from routes.admin import admin_resolve_evidence_match, AdminEvidenceMatchResolutionBody

    doc_id = "doc-em-resolve"
    doc = {
        "document_id": doc_id,
        "client_id": "cli-em",
        "property_id": "prop-em",
        "requirement_id": "req-em",
        "status": "UPLOADED",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=doc)
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    admin_user = {"portal_user_id": "admin-em", "role": "ROLE_ADMIN"}
    request = MagicMock(spec=Request)
    body = AdminEvidenceMatchResolutionBody(action="approve_override", reason="CP12 verified manually")

    async def authority_sync_mutate_fanout(*args, **kwargs):
        fo = kwargs.get("transition_fanout")
        if isinstance(fo, dict):
            fo["rst_core_backbone_activation"] = {
                "permitted": False,
                "activation_reason": "unit_test_registry",
            }

    with (
        patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.admin.create_audit_log", new_callable=AsyncMock),
        patch(
            "services.authority_mutation_fanout.authority_sync_with_transition_observability",
            new_callable=AsyncMock,
            side_effect=authority_sync_mutate_fanout,
        ),
        patch(
            "routes.admin._enqueue_recalc_after_standalone_authority_sync",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        out = await admin_resolve_evidence_match(request, doc_id, body)

    assert out.get("document_id") == doc_id
    assert out.get("verification_status") == "pending"
    assert out.get("match_resolution") == "requirement_link_confirmed"
    assert "verification is still required" in (out.get("message") or "").lower()
    assert "verify" not in (out.get("message") or "").lower() or "still required" in (out.get("message") or "").lower()
    pn = out.get("propagation_notice") or {}
    assert pn.get("code") == NOTICE_AUTHORITY_SYNC_DEFERRED


@pytest.mark.asyncio
async def test_admin_resolve_evidence_match_reject_propagation_notice_recalc_deferred():
    from fastapi import Request
    from routes.admin import admin_resolve_evidence_match, AdminEvidenceMatchResolutionBody

    doc_id = "doc-em-reject"
    doc = {
        "document_id": doc_id,
        "client_id": "cli-em",
        "property_id": "prop-em",
        "requirement_id": "req-em",
        "status": "UPLOADED",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=doc)
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    async def authority_sync_recalc_row(*args, **kwargs):
        fo = kwargs.get("transition_fanout")
        if isinstance(fo, dict):
            fo["rst_core_backbone_activation"] = {"permitted": True}
            fo["downstream_trigger_targets"] = [
                {
                    "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                    "propagation_stage": "post_evidence_match_reject:rst_core_backbone_blocked_skip_enqueue",
                }
            ]

    admin_user = {"portal_user_id": "admin-em", "role": "ROLE_ADMIN"}
    request = MagicMock(spec=Request)
    body = AdminEvidenceMatchResolutionBody(action="reject_evidence", reason="Evidence rejected in review")

    with (
        patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.admin.create_audit_log", new_callable=AsyncMock),
        patch(
            "services.authority_mutation_fanout.authority_sync_with_transition_observability",
            new_callable=AsyncMock,
            side_effect=authority_sync_recalc_row,
        ),
        patch("routes.admin._enqueue_recalc_after_standalone_authority_sync", new_callable=AsyncMock),
    ):
        out = await admin_resolve_evidence_match(request, doc_id, body)

    assert out.get("document_id") == doc_id
    assert (out.get("propagation_notice") or {}).get("code") == NOTICE_RECALC_ENQUEUE_DEFERRED


@pytest.mark.asyncio
async def test_admin_resolve_evidence_match_relink_merge_propagation_notice():
    """Prior fanout recalc-deferred, new fanout authority-deferred → merged notice prefers authority."""
    from fastapi import Request
    from routes.admin import admin_resolve_evidence_match, AdminEvidenceMatchResolutionBody

    doc_id = "doc-relink-pn"
    doc = {
        "document_id": doc_id,
        "client_id": "cli-em",
        "property_id": "prop-em",
        "requirement_id": "req-prior",
        "status": "UPLOADED",
        "file_name": "cert.pdf",
    }
    new_req = {
        "requirement_id": "req-new",
        "client_id": "cli-em",
        "property_id": "prop-em",
        "requirement_type": "gas_safety",
    }

    async def find_req(filter_q, *args, **kwargs):
        rid = filter_q.get("requirement_id")
        if rid == "req-new":
            return new_req
        if rid == "req-prior":
            return {"requirement_id": "req-prior", "client_id": "cli-em", "property_id": "prop-em"}
        return None

    async def authority_sync_relink_fanouts(db, requirement_id, *args, transition_fanout=None, **kwargs):
        fo = transition_fanout
        if not isinstance(fo, dict):
            return
        rid = str(requirement_id)
        fo.clear()
        if rid == "req-prior":
            fo.update(
                {
                    "rst_core_backbone_activation": {"permitted": True},
                    "downstream_trigger_targets": [
                        {
                            "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                            "propagation_stage": "r:rst_core_backbone_blocked_skip_enqueue",
                        }
                    ],
                }
            )
        elif rid == "req-new":
            fo.update(
                {
                    "rst_core_backbone_activation": {
                        "permitted": False,
                        "activation_reason": "unit_test",
                    }
                }
            )

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=doc)
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.find_one = AsyncMock(side_effect=find_req)

    admin_user = {"portal_user_id": "admin-em", "role": "ROLE_ADMIN"}
    request = MagicMock(spec=Request)
    body = AdminEvidenceMatchResolutionBody(
        action="relink_requirement",
        reason="Correct obligation linkage",
        relink_requirement_id="req-new",
    )

    with (
        patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.admin.create_audit_log", new_callable=AsyncMock),
        patch(
            "services.authority_mutation_fanout.authority_sync_with_transition_observability",
            new_callable=AsyncMock,
            side_effect=authority_sync_relink_fanouts,
        ),
        patch("routes.admin._enqueue_recalc_after_standalone_authority_sync", new_callable=AsyncMock),
        patch(
            "services.compliance_evidence_record_service.safe_upsert_document_upload_evidence_for_linked_document",
            new_callable=AsyncMock,
        ),
        patch(
            "services.evidence_document_match_engine.persist_document_evidence_match_after_extraction",
            new_callable=AsyncMock,
        ),
        patch(
            "services.requirement_evidence_authority.document_evidence_compatible_with_requirement",
            return_value=True,
        ),
    ):
        out = await admin_resolve_evidence_match(request, doc_id, body)

    assert out.get("document_id") == doc_id
    assert (out.get("propagation_notice") or {}).get("code") == NOTICE_AUTHORITY_SYNC_DEFERRED


def test_requirement_authority_stays_mismatch_flagged_when_doc_unsatisfied():
    """Authority sync: verified doc that still does not satisfy obligation → MISMATCH_FLAGGED."""
    from services.requirement_evidence_authority import EA_MISMATCH_FLAGGED, sync_requirement_evidence_authority

    doc_row = {
        "document_id": "d1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": "VERIFIED",
        "evidence_satisfies_requirement": False,
        "match_outcome": "MISMATCH_SUSPECTED",
        "uploaded_at": "2026-01-01T00:00:00+00:00",
    }
    _find_cur = MagicMock()
    _find_cur.to_list = AsyncMock(return_value=[doc_row])

    db = MagicMock()
    db.documents.find = MagicMock(return_value=_find_cur)
    db.requirements.find_one = AsyncMock(
        return_value={"requirement_id": "r1", "client_id": "c1", "property_id": "p1", "status": "PENDING"}
    )
    db.properties.find_one = AsyncMock(return_value={"property_id": "p1"})
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1"})
    _ev_cur = MagicMock()
    _ev_cur.to_list = AsyncMock(return_value=[])
    db.compliance_evidence_records = MagicMock()
    db.compliance_evidence_records.find = MagicMock(return_value=_ev_cur)
    db.compliance_evidence_records.find_one = AsyncMock(return_value=None)
    db.compliance_evidence_records.insert_one = AsyncMock()
    captured = {}

    async def capture_update(filt, update, *args, **kwargs):
        captured["update"] = update

    db.requirements.update_one = AsyncMock(side_effect=capture_update)

    asyncio.run(sync_requirement_evidence_authority(db, "r1", property_id_hint="p1"))
    assert "update" in captured
    auth = (captured["update"].get("$set") or {}).get("evidence_authority") or {}
    assert auth.get("state") == EA_MISMATCH_FLAGGED
