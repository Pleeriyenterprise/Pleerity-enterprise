from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.ai_reviewer_assistance import (
    build_reviewer_assistance_signals,
    detect_anomalies_for_extraction,
    normalize_extracted_fields_by_requirement,
)
from services.evidence_validation_engine import EvidenceValidationEngine, build_validation_context


@pytest.fixture(autouse=True)
def _v2_on():
    prev = os.environ.get("FEATURE_EVIDENCE_REVIEW_V2")
    os.environ["FEATURE_EVIDENCE_REVIEW_V2"] = "1"
    yield
    if prev is None:
        os.environ.pop("FEATURE_EVIDENCE_REVIEW_V2", None)
    else:
        os.environ["FEATURE_EVIDENCE_REVIEW_V2"] = prev


def test_normalize_extracted_fields_eicr_shape():
    raw = {
        "address_line_1": "10 Test Street",
        "issue_date": "2026-01-01",
        "expiry_date": "2027-01-01",
        "certificate_number": "EICR-123",
        "engineer_details": {"name": "Jane", "registration_number": "NICEIC-9", "registration_scheme": "NICEIC"},
        "result_summary": {"overall_result": "UNSATISFACTORY"},
        "findings": {"defects": ["C2 socket issue"]},
    }
    out = normalize_extracted_fields_by_requirement(raw, "EICR")
    assert out["certificate_number"] == "EICR-123"
    assert out["electrician_details"]["name"] == "Jane"
    assert out["overall_outcome"] == "UNSATISFACTORY"
    assert out["observations_c1_c2_fi"]


def test_reviewer_assistance_flags_address_and_low_confidence():
    flags, warns = build_reviewer_assistance_signals(
        extracted_fields={"address": "99 Wrong Road"},
        property_doc={"address": {"line1": "10 Right Road"}},
        requirement_code="GAS_SAFETY",
        extraction_confidence=0.42,
    )
    assert "POSSIBLE_ADDRESS_MISMATCH" in flags
    assert "LOW_EXTRACTION_CONFIDENCE" in warns


@pytest.mark.asyncio
async def test_anomaly_detection_duplicate_cert_high_risk():
    db = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.limit.return_value = fake_cursor
    fake_cursor.to_list = AsyncMock(return_value=[{"document_id": "other", "property_id": "p-2"}])
    db.documents.find.return_value = fake_cursor
    rows, risk = await detect_anomalies_for_extraction(
        db,
        document={"document_id": "doc-1", "property_id": "p-1"},
        extracted_fields={"certificate_number": "CERT-1"},
        extraction_confidence=0.91,
        extraction_source="pdf_text",
    )
    assert any(r["code"] == "DUPLICATE_CERTIFICATE_NUMBER" for r in rows)
    assert risk > 0.3


def test_validation_engine_uses_ai_assistance_signals():
    req = {"requirement_type": "GAS_SAFETY", "requirement_code": "GAS_SAFETY"}
    doc = {
        "document_id": "d",
        "expiry_date": "2099-01-01",
        "ai_assistance": {
            "extracted_fields": {"address": "bad addr"},
            "ai_flags": ["POSSIBLE_ADDRESS_MISMATCH"],
            "extraction_warnings": ["LOW_EXTRACTION_CONFIDENCE"],
            "anomaly_flags": [],
            "anomaly_risk_score": 0.7,
        },
    }
    prop = {"address": {"line1": "good addr"}}
    out = EvidenceValidationEngine().evaluate(build_validation_context(requirement=req, document=doc, property_doc=prop))
    assert "PROPERTY_ADDRESS_MISMATCH" in out["failures"]
    assert "AI_LOW_CONFIDENCE_EXTRACTION" in out["warnings"]
    assert out["ai_assistance_summary"]["anomaly_risk_score"] == 0.7


def test_validation_engine_not_auto_verified_from_ai():
    req = {"requirement_type": "EPC", "requirement_code": "EPC"}
    doc = {
        "document_id": "d",
        "ai_assistance": {"extracted_fields": {"address": "x"}, "anomaly_risk_score": 0.1},
    }
    out = EvidenceValidationEngine().evaluate(build_validation_context(requirement=req, document=doc, property_doc=None))
    assert out["suggested_review_outcome"] != "VERIFIED"


def test_ai_assistance_endpoint_exposes_shape(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-a",
            "ai_assistance": {"extracted_fields": {"certificate_number": "C1"}, "anomaly_risk_score": 0.2},
        }
    )
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.get("/api/documents/doc-a/review/ai-assistance")
    assert res.status_code == 200
    payload = res.json()["ai_assistance"]
    assert payload["extracted_fields"]["certificate_number"] == "C1"
    assert "ai_flags" in payload


def test_ai_override_endpoint_audits_and_no_state_shift(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-a",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
            "status": "UPLOADED",
            "ai_assistance": {"extracted_fields": {"certificate_number": "OLD"}},
        }
    )
    db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.evidence_review_events.insert_one = AsyncMock(return_value=MagicMock())
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.post(
            "/api/documents/doc-a/review/ai-extraction/apply",
            json={"notes": "Reviewed", "accepted_fields": {"certificate_number": "NEW"}, "rejected_fields": ["foo"]},
        )
    assert res.status_code == 200
    upd = db.documents.update_one.await_args.args[1]
    set_doc = upd["$set"]
    assert "evidence_review_state" not in set_doc
    assert set_doc["ai_assistance.extracted_fields"]["certificate_number"] == "NEW"
    assert db.evidence_review_events.insert_one.await_count == 1


def test_list_documents_includes_ai_assistance_default(client):
    from database import database as db_singleton
    from routes import documents as dmod

    db = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[{"document_id": "d1", "status": "UPLOADED"}])
    db.documents.find.return_value = cursor
    user = {"client_id": "c1"}
    with (
        patch.object(dmod, "client_route_guard", new_callable=AsyncMock, return_value=user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.get("/api/documents")
    assert res.status_code == 200
    doc = res.json()["documents"][0]
    assert "ai_assistance" in doc


def test_ai_field_action_override_requires_reason(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-f1",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
            "status": "UPLOADED",
            "ai_assistance": {"extracted_fields": {"certificate_number": "OLD"}},
        }
    )
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.post(
            "/api/documents/doc-f1/review/ai-extraction/field-action",
            json={"field_name": "certificate_number", "action": "OVERRIDE", "override_value": "NEW"},
        )
    assert res.status_code == 422
    assert "OVERRIDE_REASON_REQUIRED" in str(res.json())


def test_ai_field_action_accept_reject_override_each_audited(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-f2",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
            "status": "UPLOADED",
            "ai_assistance": {
                "extracted_fields": {"certificate_number": "CERT-1", "address": "A", "expiry_date": "2027-01-01"},
                "original_extracted_fields": {"certificate_number": "CERT-1", "address": "A", "expiry_date": "2027-01-01"},
            },
        }
    )
    db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.evidence_review_events.insert_one = AsyncMock(return_value=MagicMock())
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        r1 = client.post(
            "/api/documents/doc-f2/review/ai-extraction/field-action",
            json={"field_name": "certificate_number", "action": "ACCEPT", "notes": "looks good"},
        )
        r2 = client.post(
            "/api/documents/doc-f2/review/ai-extraction/field-action",
            json={"field_name": "address", "action": "REJECT", "notes": "unreadable"},
        )
        r3 = client.post(
            "/api/documents/doc-f2/review/ai-extraction/field-action",
            json={
                "field_name": "expiry_date",
                "action": "OVERRIDE",
                "override_value": "2028-01-01",
                "override_reason": "manual evidence check",
                "notes": "override applied",
            },
        )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 200
    assert db.evidence_review_events.insert_one.await_count == 3


def test_ai_field_action_does_not_mutate_review_state_tier_or_requirement(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-f3",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
            "status": "UPLOADED",
            "evidence_review_state": "UNDER_REVIEW",
            "assurance_tier": "USER_UPLOADED",
            "ai_assistance": {"extracted_fields": {"certificate_number": "CERT-1"}},
        }
    )
    db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.requirements.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.evidence_review_events.insert_one = AsyncMock(return_value=MagicMock())
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.post(
            "/api/documents/doc-f3/review/ai-extraction/field-action",
            json={"field_name": "certificate_number", "action": "ACCEPT", "notes": "ok"},
        )
    assert res.status_code == 200
    update_doc = db.documents.update_one.await_args.args[1]
    set_doc = update_doc["$set"]
    assert all(k.startswith("ai_assistance.") for k in set_doc.keys())
    assert "evidence_review_state" not in set_doc
    assert "assurance_tier" not in set_doc
    assert db.requirements.update_one.await_count == 0


def test_ai_field_actions_write_expected_decision_reason_and_event_shape(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    base_doc = {
        "document_id": "doc-f4",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "status": "UPLOADED",
        "evidence_review_state": "UNDER_REVIEW",
        "assurance_tier": "USER_UPLOADED",
        "ai_assistance": {
            "extracted_fields": {"certificate_number": "CERT-1", "address": "A", "expiry_date": "2027-01-01"},
            "original_extracted_fields": {"certificate_number": "CERT-1", "address": "A", "expiry_date": "2027-01-01"},
            "field_reviews": {},
            "reviewer_overrides": [],
        },
    }

    db = MagicMock()
    db.documents.find_one = AsyncMock(side_effect=[dict(base_doc), dict(base_doc), dict(base_doc)])
    db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    captured_events = []

    async def _capture_event(row):
        captured_events.append(row)

    db.evidence_review_events.insert_one = AsyncMock(side_effect=_capture_event)
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        r_accept = client.post(
            "/api/documents/doc-f4/review/ai-extraction/field-action",
            json={"field_name": "certificate_number", "action": "ACCEPT", "notes": "ok"},
        )
        r_reject = client.post(
            "/api/documents/doc-f4/review/ai-extraction/field-action",
            json={"field_name": "address", "action": "REJECT", "notes": "bad OCR"},
        )
        r_override = client.post(
            "/api/documents/doc-f4/review/ai-extraction/field-action",
            json={
                "field_name": "expiry_date",
                "action": "OVERRIDE",
                "override_value": "2028-01-01",
                "override_reason": "manual cert check",
                "notes": "override",
            },
        )

    assert r_accept.status_code == 200
    assert r_reject.status_code == 200
    assert r_override.status_code == 200
    assert len(captured_events) == 3

    by_reason = {ev.get("decision_reason"): ev for ev in captured_events}
    assert "AI_FIELD_ACCEPT" in by_reason
    assert "AI_FIELD_REJECT" in by_reason
    assert "AI_FIELD_OVERRIDE" in by_reason

    for ev in captured_events:
        assert ev.get("document_id") == "doc-f4"
        assert ev.get("reviewer_id") == "adm1"
        assert "validation_snapshot" in ev
        assert isinstance(ev.get("validation_snapshot"), dict)
        assert ev["validation_snapshot"].get("field_action")
        assert ev.get("created_at")


def test_verification_helpers_only_supported_sources_for_epc(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-vh1",
            "requirement_id": "r-epc",
            "ai_assistance": {"extracted_fields": {"certificate_number": "EPC-1", "postcode": "AB1 2CD"}},
        }
    )
    db.requirements.find_one = AsyncMock(return_value={"requirement_id": "r-epc", "requirement_code": "EPC"})
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.get("/api/documents/doc-vh1/review/verification-helpers")
    assert res.status_code == 200
    helpers = res.json()["helpers"]
    urls = {h.get("url") for h in helpers}
    assert "https://www.gov.uk/find-energy-certificate" in urls
    assert "https://www.gassaferegister.co.uk/" not in urls


def test_verification_helpers_unsupported_type_returns_no_irrelevant_links(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(return_value={"document_id": "doc-vh2", "requirement_id": "r-unk", "ai_assistance": {}})
    db.requirements.find_one = AsyncMock(return_value={"requirement_id": "r-unk", "requirement_code": "TENANCY"})
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.get("/api/documents/doc-vh2/review/verification-helpers")
    assert res.status_code == 200
    helpers = res.json()["helpers"]
    assert helpers == []


def test_external_verification_requires_explicit_post_action(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    # read-only helper endpoint should not mutate document tier/state
    db.documents.find_one = AsyncMock(return_value={"document_id": "doc-vh3", "requirement_id": "r3", "ai_assistance": {}})
    db.requirements.find_one = AsyncMock(return_value={"requirement_id": "r3", "requirement_code": "EPC"})
    db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.evidence_review_events.insert_one = AsyncMock(return_value=MagicMock())
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        helper_res = client.get("/api/documents/doc-vh3/review/verification-helpers")
    assert helper_res.status_code == 200
    assert db.documents.update_one.await_count == 0
    assert db.evidence_review_events.insert_one.await_count == 0


def test_external_verification_post_sets_tier_and_audits_without_requirement_auto_approval(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-vh4",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
            "status": "UPLOADED",
            "evidence_review_state": "UNDER_REVIEW",
            "assurance_tier": "USER_UPLOADED",
            "ai_assistance": {},
        }
    )
    db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.requirements.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.evidence_review_events.insert_one = AsyncMock(return_value=MagicMock())
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.post(
            "/api/documents/doc-vh4/review/record-external-verification",
            json={
                "verification_method": "EPC_REGISTER_CHECK",
                "verification_reference": "EPC-REF-1",
                "verification_notes": "Matched certificate and postcode",
            },
        )
    assert res.status_code == 200
    set_doc = db.documents.update_one.await_args.args[1]["$set"]
    assert set_doc["assurance_tier"] == "EXTERNALLY_VERIFIED"
    assert set_doc["evidence_review_state"] == "VERIFIED"
    assert db.evidence_review_events.insert_one.await_count == 1
    assert db.requirements.update_one.await_count == 0
    assert set_doc["external_verification_method"] == "EPC_REGISTER_CHECK"
    event_doc = db.evidence_review_events.insert_one.await_args.args[0]
    method = event_doc["validation_snapshot"]["external_verification_record"]["verification_method"]
    assert method in {
        "EPC_REGISTER_CHECK",
        "GAS_SAFE_LOOKUP",
        "NICEIC_LOOKUP",
        "NAPIT_LOOKUP",
        "COMPANIES_HOUSE_CHECK",
        "MANUAL_CONFIRMATION",
    }


def test_external_verification_post_rejects_unsupported_method_422(client):
    from database import database as db_singleton
    from routes import evidence_review as er_mod

    db = MagicMock()
    db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-vh5",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
            "status": "UPLOADED",
            "evidence_review_state": "UNDER_REVIEW",
            "assurance_tier": "USER_UPLOADED",
            "ai_assistance": {},
        }
    )
    db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.evidence_review_events.insert_one = AsyncMock(return_value=MagicMock())
    admin_user = {"portal_user_id": "adm1", "client_id": "c1", "role": "ROLE_ADMIN"}
    with (
        patch.object(er_mod, "admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=db),
    ):
        res = client.post(
            "/api/documents/doc-vh5/review/record-external-verification",
            json={
                "verification_method": "RANDOM_LOOKUP",
                "verification_reference": "REF-1",
            },
        )
    assert res.status_code == 422
    assert "VERIFICATION_METHOD_UNSUPPORTED" in str(res.json())
    assert db.documents.update_one.await_count == 0
    assert db.evidence_review_events.insert_one.await_count == 0

