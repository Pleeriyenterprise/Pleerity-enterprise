"""Phase 1 deposit guided declaration — structured field validation (POST + shared rules)."""

from services.compliance_evidence_record_service import (
    DEPOSIT_DECLARATION_CONFIRMATION_REQUIRED_MESSAGE,
    DEPOSIT_PRESCRIBED_INFO_FIELD_REQUIRED_MESSAGE,
    DEPOSIT_PROTECTION_CONFIRM_REQUIRED_MESSAGE,
    DEPOSIT_PROTECTION_FIELD_REQUIRED_MESSAGE,
    validate_deposit_structured_declaration_fields,
)


def _full_protection():
    return {
        "deposit_amount": {"answer": "500"},
        "deposit_received_date": {"answer": "2026-01-10"},
        "scheme_name": {"answer": "Example Scheme"},
        "scheme_reference": {"answer": "REF-1"},
        "protection_date": {"answer": "2026-01-11"},
        "protection_confirmed": {"answer": True},
    }


def test_deposit_requires_declaration_confirmed():
    err = validate_deposit_structured_declaration_fields(
        {
            "deposit_taken": {"answer": False},
            "prescribed_information_served": {"answer": False},
            "declaration_confirmed": {"answer": False},
        }
    )
    assert err == DEPOSIT_DECLARATION_CONFIRMATION_REQUIRED_MESSAGE


def test_deposit_taken_yes_requires_protection_fields():
    err = validate_deposit_structured_declaration_fields(
        {
            "deposit_taken": {"answer": True},
            "deposit_amount": {"answer": ""},
            "deposit_received_date": {"answer": "2026-01-10"},
            "scheme_name": {"answer": "X"},
            "scheme_reference": {"answer": "Y"},
            "protection_date": {"answer": "2026-01-11"},
            "protection_confirmed": {"answer": True},
            "prescribed_information_served": {"answer": False},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err == DEPOSIT_PROTECTION_FIELD_REQUIRED_MESSAGE


def test_deposit_taken_yes_requires_protection_confirmed_yes():
    base = {
        "deposit_taken": {"answer": True},
        "prescribed_information_served": {"answer": False},
        "declaration_confirmed": {"answer": True},
        **_full_protection(),
    }
    base["protection_confirmed"] = {"answer": False}
    err = validate_deposit_structured_declaration_fields(base)
    assert err == DEPOSIT_PROTECTION_CONFIRM_REQUIRED_MESSAGE


def test_prescribed_served_yes_requires_pi_fields():
    err = validate_deposit_structured_declaration_fields(
        {
            "deposit_taken": {"answer": False},
            "prescribed_information_served": {"answer": True},
            "prescribed_information_served_date": {"answer": ""},
            "served_to": {"answer": "Tenant"},
            "service_method": {"answer": "email"},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err == DEPOSIT_PRESCRIBED_INFO_FIELD_REQUIRED_MESSAGE


def test_deposit_taken_no_and_served_no_passes_with_declaration_only():
    assert (
        validate_deposit_structured_declaration_fields(
            {
                "deposit_taken": {"answer": False},
                "prescribed_information_served": {"answer": False},
                "declaration_confirmed": {"answer": True},
            }
        )
        is None
    )


def test_full_valid_deposit_and_pi():
    assert (
        validate_deposit_structured_declaration_fields(
            {
                "deposit_taken": {"answer": True},
                "prescribed_information_served": {"answer": True},
                "prescribed_information_served_date": {"answer": "2026-01-12"},
                "served_to": {"answer": "Jane"},
                "service_method": {"answer": "email"},
                "proof_of_service": {"answer": ""},
                "declaration_confirmed": {"answer": True},
                **_full_protection(),
            }
        )
        is None
    )
