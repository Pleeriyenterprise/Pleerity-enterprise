"""Phase 1 Legionella external-assessment structured validation."""

from services.compliance_evidence_record_service import (
    LEGIONELLA_ACTIONS_REQUIRED,
    LEGIONELLA_ASSESSMENT_DATE_REQUIRED,
    LEGIONELLA_DECLARATION_REQUIRED,
    LEGIONELLA_NEXT_REVIEW_REQUIRED,
    validate_legionella_structured_declaration_fields,
)


def test_legionella_requires_declaration():
    err = validate_legionella_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "declaration_confirmed": {"answer": False},
        }
    )
    assert err and err["code"] == LEGIONELLA_DECLARATION_REQUIRED


def test_legionella_requires_assessment_date_when_completed():
    err = validate_legionella_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "assessment_date": {"answer": ""},
            "risk_level": {"answer": "low"},
            "control_measures_in_place": {"answer": True},
            "actions_required": {"answer": False},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err and err["code"] == LEGIONELLA_ASSESSMENT_DATE_REQUIRED


def test_legionella_requires_actions_flag_when_completed():
    err = validate_legionella_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "assessment_date": {"answer": "2026-03-01"},
            "risk_level": {"answer": "medium"},
            "control_measures_in_place": {"answer": True},
            "actions_required": {"answer": None},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err and err["code"] == LEGIONELLA_ACTIONS_REQUIRED


def test_legionella_requires_next_review_when_actions_required():
    err = validate_legionella_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "assessment_date": {"answer": "2026-03-01"},
            "risk_level": {"answer": "high"},
            "control_measures_in_place": {"answer": True},
            "actions_required": {"answer": True},
            "next_review_date": {"answer": ""},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err and err["code"] == LEGIONELLA_NEXT_REVIEW_REQUIRED


def test_legionella_valid_payload_passes():
    err = validate_legionella_structured_declaration_fields(
        {
            "assessment_completed": {"answer": True},
            "assessment_date": {"answer": "2026-03-01"},
            "assessor_type": {"answer": "external"},
            "assessor_name": {"answer": "Assessor A"},
            "risk_level": {"answer": "medium"},
            "control_measures_in_place": {"answer": True},
            "actions_required": {"answer": True},
            "next_review_date": {"answer": "2026-09-01"},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err is None
