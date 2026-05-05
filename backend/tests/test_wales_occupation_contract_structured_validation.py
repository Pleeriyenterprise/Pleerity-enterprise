"""Phase 1 Wales occupation contract guided-declaration validation."""

from services.compliance_evidence_record_service import (
    WALES_OCCUPATION_CONTRACT_DECLARATION_REQUIRED_MESSAGE,
    WALES_OCCUPATION_CONTRACT_ISSUED_FIELD_REQUIRED_MESSAGE,
    validate_wales_occupation_contract_structured_declaration_fields,
)


def test_requires_declaration_confirmed():
    err = validate_wales_occupation_contract_structured_declaration_fields(
        {
            "occupation_contract_issued": {"answer": False},
            "declaration_confirmed": {"answer": False},
        }
    )
    assert err == WALES_OCCUPATION_CONTRACT_DECLARATION_REQUIRED_MESSAGE


def test_requires_issued_fields_when_issued_yes():
    err = validate_wales_occupation_contract_structured_declaration_fields(
        {
            "occupation_contract_issued": {"answer": True},
            "issue_date": {"answer": ""},
            "contract_holder_name": {"answer": "A"},
            "service_method": {"answer": "email"},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err == WALES_OCCUPATION_CONTRACT_ISSUED_FIELD_REQUIRED_MESSAGE


def test_passes_when_not_issued_and_declaration_yes():
    assert (
        validate_wales_occupation_contract_structured_declaration_fields(
            {
                "occupation_contract_issued": {"answer": False},
                "declaration_confirmed": {"answer": True},
            }
        )
        is None
    )


def test_passes_when_issued_and_required_fields_present():
    assert (
        validate_wales_occupation_contract_structured_declaration_fields(
            {
                "occupation_contract_issued": {"answer": True},
                "issue_date": {"answer": "2026-02-01"},
                "contract_holder_name": {"answer": "Contract Holder"},
                "service_method": {"answer": "email"},
                "declaration_confirmed": {"answer": True},
            }
        )
        is None
    )
