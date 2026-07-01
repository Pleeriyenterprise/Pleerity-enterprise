"""POST-SUBMISSION-EVIDENCE-UX-FIX-P0 regression tests."""

from services.cer_actionability_presentation import build_reopen_prefill_from_record
from services.operational_cognition_service import build_envelope_for_requirement
from services.requirement_action_resolver import resolve_take_action_envelope


def test_structured_satisfied_no_upload_suppresses_uploaded_not_verified():
    req = {
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "state_reason": "guided_declaration_not_independently_verified",
            "primary_evidence_record_id": "cer_1",
        },
        "take_action": {"primary": {"label": "View submission", "kind": "guided_evidence_resolution"}},
    }
    env = build_envelope_for_requirement(req)
    assert env["operational_truth_flags"]["uploaded_not_verified"] is False


def test_upload_pending_review_with_document_keeps_uploaded_not_verified():
    req = {
        "client_lifecycle_state": "PENDING_REVIEW",
        "document_id": "doc_1",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "state_reason": "document_upload_pending_verification",
            "effective_verified_document_id": "doc_1",
        },
        "take_action": {"primary": {"label": "Upload evidence", "route": "/documents?x=1"}},
    }
    env = build_envelope_for_requirement(req)
    assert env["operational_truth_flags"]["uploaded_not_verified"] is True


def test_verified_structured_routes_to_intel_submission_not_documents():
    req = {
        "property_id": "prop_1",
        "requirement_id": "req_1",
        "client_lifecycle_state": "VERIFIED",
        "evidence_authority": {
            "state": "VERIFIED_CURRENT",
            "state_reason": "verified_non_document_evidence",
            "primary_evidence_record_id": "cer_leg",
        },
        "take_action": {"primary": {"label": "Record Legionella risk assessment"}},
    }
    env = build_envelope_for_requirement(req)
    primary = env["primary_action"]
    assert primary["label"] == "View evidence"
    assert primary["url"] == "/properties/prop_1?tab=evidence&requirement_id=req_1&open=intel&focus=submission"
    assert env["operational_truth_flags"]["uploaded_not_verified"] is False


def test_verified_document_routes_to_evidence_registry():
    req = {
        "property_id": "prop_1",
        "requirement_id": "req_1",
        "client_lifecycle_state": "VERIFIED",
        "document_id": "doc_1",
        "evidence_authority": {
            "state": "VERIFIED_CURRENT",
            "effective_verified_document_id": "doc_1",
        },
        "take_action": {"primary": {"label": "Upload Gas Safety Certificate"}},
    }
    env = build_envelope_for_requirement(req)
    assert env["primary_action"]["url"] == "/properties/prop_1?tab=evidence&requirement_id=req_1"
    assert env["primary_action"]["intent"] == "view_settled_evidence"


def test_reopen_prefill_accepts_scalar_structured_fields():
    rec = {
        "evidence_record_id": "cer_x",
        "evidence_mode": "STRUCTURED_DECLARATION",
        "evidence_payload": {
            "declaration_statement": "I confirm",
            "structured_fields": {
                "assessment_date": "2025-01-01",
                "actions_required": {"answer": True},
            },
        },
    }
    pre = build_reopen_prefill_from_record(rec)
    assert pre["structured_fields_prefill"]["assessment_date"]["answer"] == "2025-01-01"
    assert pre["structured_fields_prefill"]["actions_required"]["answer"] is True


def test_reopen_prefill_checklist_scalar_and_metadata():
    rec = {
        "evidence_record_id": "cer_chk",
        "evidence_mode": "INSPECTION_CHECKLIST",
        "evidence_payload": {
            "inspection_date": "2025-02-01",
            "responsible_person": "Jane",
            "checklist_answers": {"smoke_alarm": True, "co_alarm": {"answer": False}},
        },
    }
    pre = build_reopen_prefill_from_record(rec)
    assert pre["inspection_date"] == "2025-02-01"
    assert pre["checklist_answers_prefill"]["smoke_alarm"]["answer"] is True


def test_pat_job_class_resolves_document_upload_route():
    req = {
        "requirement_code": "portable_appliance_test",
        "compliance_requirement_class": "JOB",
        "property_id": "prop_pat",
        "requirement_id": "req_pat",
    }
    env = resolve_take_action_envelope(req)
    assert env["action_type"] == "DOCUMENT"
    pri = env["take_action"]["primary"]
    assert "upload PAT" in pri["label"] or "PAT" in pri["label"]
    assert pri["route"] == "/documents?property_id=prop_pat&requirement_id=req_pat"
    assert pri["intent"] == "upload_evidence"
