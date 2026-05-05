"""Phase 1 Lead testing external-assessment structured validation."""

from services.compliance_evidence_record_service import (
    LEAD_TESTING_ASSESSMENT_DATE_REQUIRED,
    LEAD_TESTING_DECLARATION_REQUIRED,
    LEAD_TESTING_NEXT_REVIEW_REQUIRED,
    validate_lead_testing_structured_declaration_fields,
)


def test_lead_testing_requires_declaration():
    err = validate_lead_testing_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "declaration_confirmed": {"answer": False},
        }
    )
    assert err and err["code"] == LEAD_TESTING_DECLARATION_REQUIRED


def test_lead_testing_requires_assessment_fields_when_completed():
    err = validate_lead_testing_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "assessment_date": {"answer": ""},
            "assessment_type": {"answer": "water_test"},
            "risk_level": {"answer": "medium"},
            "lead_present": {"answer": True},
            "actions_required": {"answer": False},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err and err["code"] == LEAD_TESTING_ASSESSMENT_DATE_REQUIRED


def test_lead_testing_requires_next_review_when_actions_required():
    err = validate_lead_testing_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "assessment_date": {"answer": "2026-05-01"},
            "assessment_type": {"answer": "full_assessment"},
            "risk_level": {"answer": "high"},
            "lead_present": {"answer": True},
            "actions_required": {"answer": True},
            "next_review_date": {"answer": ""},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err and err["code"] == LEAD_TESTING_NEXT_REVIEW_REQUIRED


def test_lead_testing_valid_payload_passes():
    err = validate_lead_testing_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "assessment_date": {"answer": "2026-05-01"},
            "assessment_type": {"answer": "full_assessment"},
            "risk_level": {"answer": "low"},
            "lead_present": {"answer": False},
            "actions_required": {"answer": True},
            "actions_taken": {"answer": True},
            "next_review_date": {"answer": "2027-05-01"},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err is None
