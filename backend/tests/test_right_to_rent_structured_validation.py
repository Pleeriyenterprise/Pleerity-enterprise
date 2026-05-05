"""Phase 1.1 conditional follow_up_date validation for Right to Rent structured declarations."""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_validate_r2r_time_limited_requires_follow_up_date():
    from services.compliance_evidence_record_service import (
        RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE,
        validate_right_to_rent_structured_declaration_fields,
    )

    fields = {
        "right_to_rent_status": {"answer": "time_limited"},
        "follow_up_required": {"answer": False},
        "follow_up_date": {"answer": ""},
    }
    assert validate_right_to_rent_structured_declaration_fields(fields) == RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE


def test_validate_r2r_follow_up_required_yes_requires_date():
    from services.compliance_evidence_record_service import (
        RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE,
        validate_right_to_rent_structured_declaration_fields,
    )

    for yes in (True, "YES", "yes", "Y"):
        fields = {
            "right_to_rent_status": {"answer": "unlimited"},
            "follow_up_required": {"answer": yes},
            "follow_up_date": {"answer": None},
        }
        assert validate_right_to_rent_structured_declaration_fields(fields) == RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE


def test_validate_r2r_unlimited_follow_up_no_passes_without_date():
    from services.compliance_evidence_record_service import validate_right_to_rent_structured_declaration_fields

    fields = {
        "right_to_rent_status": {"answer": "unlimited"},
        "follow_up_required": {"answer": False},
        "follow_up_date": {"answer": ""},
    }
    assert validate_right_to_rent_structured_declaration_fields(fields) is None


def test_validate_r2r_time_limited_with_date_passes():
    from services.compliance_evidence_record_service import validate_right_to_rent_structured_declaration_fields

    fields = {
        "right_to_rent_status": {"answer": "time_limited"},
        "follow_up_required": {"answer": False},
        "follow_up_date": {"answer": "2026-12-01"},
    }
    assert validate_right_to_rent_structured_declaration_fields(fields) is None


def test_policy_normalizes_structured_declaration_conditional_rules():
    from services.compliance_evidence_record_service import (
        RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE,
        normalize_evidence_resolution_dict,
    )

    out = normalize_evidence_resolution_dict(
        {
            "allowed_evidence_modes": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
            "structured_declaration_conditional_rules": [
                {
                    "id": "x",
                    "when_any": [{"field": "right_to_rent_status", "equals": "time_limited"}],
                    "require_non_empty_fields": ["follow_up_date"],
                    "message": RIGHT_TO_RENT_FOLLOW_UP_DATE_REQUIRED_MESSAGE,
                },
            ],
        }
    )
    assert len(out.get("structured_declaration_conditional_rules") or []) == 1
