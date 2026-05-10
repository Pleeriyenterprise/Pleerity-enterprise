"""Deterministic tests for Evidence Review V2 Phase 1 (foundation)."""

from __future__ import annotations

import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.evidence_review import AssuranceTier, EvidenceReviewState
from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state
from services.evidence_review_scoring_adapter import evidence_review_contributes_positive_credit
from services.evidence_review_policy import promotions_allowed_for_accept_unverified
from services.evidence_validation_engine import EvidenceValidationEngine, build_validation_context


class _EmptyAsyncCursor:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


@pytest.fixture(autouse=True)
def reset_feature_env():
    prev = os.environ.pop("FEATURE_EVIDENCE_REVIEW_V2", None)
    yield
    if prev is None:
        os.environ.pop("FEATURE_EVIDENCE_REVIEW_V2", None)
    else:
        os.environ["FEATURE_EVIDENCE_REVIEW_V2"] = prev


def test_legacy_verified_maps_accepted_not_external():
    doc = {"status": "VERIFIED"}
    assert effective_evidence_review_state(doc) == EvidenceReviewState.ACCEPTED_UNVERIFIED.value
    assert effective_assurance_tier(doc) == AssuranceTier.HUMAN_ACCEPTED.value


def test_validation_eicr_c2_fails_when_data_present():
    req = {"requirement_id": "r1", "requirement_type": "EICR", "requirement_code": "EICR"}
    doc = {
        "document_id": "d1",
        "document_metadata": {"overall_result": "C2"},
    }
    ctx = build_validation_context(requirement=req, document=doc, property_doc=None)
    out = EvidenceValidationEngine().evaluate(ctx)
    assert out["validation_status"] == "FAIL"
    assert "EICR_UNSATISFACTORY" in " ".join(out["failures"])


def test_expired_document_fails_validation():
    doc = {"expiry_date": "1990-01-15", "document_id": "d1"}
    req = {"requirement_id": "r1", "requirement_type": "GAS_SAFETY", "requirement_code": "GAS_SAFETY"}
    ctx = build_validation_context(requirement=req, document=doc, property_doc=None)
    out = EvidenceValidationEngine().evaluate(ctx)
    assert out["validation_status"] == "FAIL"


def test_scoring_adapter_v2_off():
    os.environ["FEATURE_EVIDENCE_REVIEW_V2"] = "0"
    d = {"status": "VERIFIED"}
    assert evidence_review_contributes_positive_credit(d) is True
    d2 = {"status": "UPLOADED"}
    assert evidence_review_contributes_positive_credit(d2) is False


def test_scoring_adapter_v2_on_rejects_needs_information():
    os.environ["FEATURE_EVIDENCE_REVIEW_V2"] = "1"
    d = {"status": "VERIFIED", "evidence_review_state": EvidenceReviewState.NEEDS_INFORMATION.value}
    assert evidence_review_contributes_positive_credit(d) is False


def test_promotion_blocked_on_fail_without_override():
    snap = {"validation_status": "FAIL"}
    assert promotions_allowed_for_accept_unverified(validation_snapshot=snap, validation_override_reason="") is False
    assert promotions_allowed_for_accept_unverified(validation_snapshot=snap, validation_override_reason="  override  ") is True


def test_v2_disabled_preserve_verify_path(client):
    """With V2 off, verify follows legacy and should not import V2-only side effects first."""
    from database import database as db_singleton
    from routes import documents as documents_routes

    os.environ.pop("FEATURE_EVIDENCE_REVIEW_V2", None)

    doc = {
        "document_id": "doc-v2-legacy",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": "UPLOADED",
        "evidence_satisfies_requirement": True,
        "match_outcome": "MATCH_CONFIRMED",
    }

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=dict(doc))
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.find_one = AsyncMock(
        return_value={"requirement_id": "r1", "requirement_type": "TEST", "requirement_code": "TEST"}
    )
    mock_db.properties.find_one = AsyncMock(return_value={"address": {"line1": "1 St"}, "property_id": "p1"})
    mock_db.work_orders.find = MagicMock(return_value=_EmptyAsyncCursor())
    mock_db.work_orders.find_one = AsyncMock(return_value={"work_order_kind": "COMPLIANCE"})
    mock_db.work_orders.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.evidence_review_events = MagicMock()
    mock_db.evidence_review_events.insert_one = AsyncMock()

    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(documents_routes, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.documents.create_audit_log", new_callable=AsyncMock),
        patch("routes.documents.authority_sync_with_transition_observability", new_callable=AsyncMock),
        patch("routes.documents.enqueue_compliance_recalc_with_fanout", new_callable=AsyncMock),
        patch("services.provisioning.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("services.enablement_service.emit_enablement_event", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
    ):
        res = client.post("/api/documents/verify/doc-v2-legacy", json={})

    assert res.status_code == 200, res.text
    assert not mock_db.evidence_review_events.insert_one.called


def test_v2_verify_writes_review_event():
    from services.evidence_review_verify import execute_verify_document_v2
    os.environ["FEATURE_EVIDENCE_REVIEW_V2"] = "1"

    doc = {
        "document_id": "doc-v2-ev",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": "UPLOADED",
        "evidence_satisfies_requirement": True,
        "match_outcome": "MATCH_CONFIRMED",
        "document_metadata": {},
        "expiry_date": "2099-12-31",
    }

    inserted_events = []

    async def capture_ev_insert(doc_row):
        inserted_events.append(doc_row)

    final_doc = {
        **doc,
        "status": "VERIFIED",
        "evidence_review_state": "ACCEPTED_UNVERIFIED",
        "assurance_tier": "HUMAN_ACCEPTED",
    }

    seq = [
        dict(doc),
        dict(final_doc),
    ]

    async def find_two(filt, *args, **kwargs):
        if filt.get("document_id") == doc["document_id"]:
            return seq.pop(0) if seq else dict(final_doc)
        return None

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(side_effect=find_two)
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.requirements.find_one = AsyncMock(
        return_value={"requirement_id": "r1", "requirement_type": "EPC", "requirement_code": "EPC"}
    )
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": "p1", "address": {"line1": "Same Rd"}})
    mock_db.work_orders.find = MagicMock(return_value=_EmptyAsyncCursor())
    mock_db.work_orders.find_one = AsyncMock(return_value={"work_order_kind": "COMPLIANCE"})
    mock_db.work_orders.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.evidence_review_events = MagicMock()
    mock_db.evidence_review_events.insert_one = AsyncMock(side_effect=capture_ev_insert)

    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch("services.evidence_review_verify.create_audit_log", new_callable=AsyncMock),
        patch("services.evidence_review_verify.authority_sync_with_transition_observability", new_callable=AsyncMock),
        patch("services.evidence_review_verify.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("services.evidence_review_verify.enqueue_compliance_recalc_with_fanout", new_callable=AsyncMock),
        patch("services.enablement_service.emit_enablement_event", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
    ):
        out = asyncio.run(
            execute_verify_document_v2(
                mock_db,
                document_id=doc["document_id"],
                document=dict(doc),
                user=admin_user,
                old_status="UPLOADED",
                validation_override_reason=None,
            )
        )

    assert out.get("evidence_review_state") == "ACCEPTED_UNVERIFIED"
    assert inserted_events, "append-only ledger insert_one should run"


def test_v2_validation_fail_blocks_without_override(client):
    from database import database as db_singleton
    from routes import documents as documents_routes

    os.environ["FEATURE_EVIDENCE_REVIEW_V2"] = "1"

    doc = {
        "document_id": "doc-v2-fail",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": "UPLOADED",
        "evidence_satisfies_requirement": True,
        "match_outcome": "MATCH_CONFIRMED",
        "expiry_date": "1990-01-01",
    }

    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=dict(doc))
    mock_db.evidence_review_events = MagicMock()
    mock_db.evidence_review_events.insert_one = AsyncMock()

    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(documents_routes, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
    ):
        res = client.post("/api/documents/verify/doc-v2-fail", json={})

    assert res.status_code == 400


def test_v2_reject_event_recorded(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    os.environ["FEATURE_EVIDENCE_REVIEW_V2"] = "1"

    doc = {
        "document_id": "doc-rej",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": "UPLOADED",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=dict(doc))
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.evidence_review_events.insert_one = AsyncMock()

    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.evidence_review.authority_sync_with_transition_observability", new_callable=AsyncMock),
        patch("routes.evidence_review.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("routes.evidence_review.enqueue_compliance_recalc_with_fanout", new_callable=AsyncMock),
    ):
        res = client.post("/api/documents/doc-rej/review/reject", json={"notes": "bad scan"})

    assert res.status_code == 200, res.text
    assert mock_db.evidence_review_events.insert_one.called
