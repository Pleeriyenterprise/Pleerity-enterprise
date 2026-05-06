from services.compliance_evidence_record_service import (
    TENANCY_AGREEMENT_DECLARATION_REQUIRED_MESSAGE,
    TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE,
    validate_tenancy_agreement_structured_declaration_fields,
)


def test_tenancy_agreement_requires_declaration_confirmation():
    err = validate_tenancy_agreement_structured_declaration_fields(
        {
            "agreement_exists": {"answer": True},
            "declaration_confirmed": {"answer": False},
        }
    )
    assert err == TENANCY_AGREEMENT_DECLARATION_REQUIRED_MESSAGE


def test_tenancy_agreement_requires_detail_fields_when_agreement_exists():
    err = validate_tenancy_agreement_structured_declaration_fields(
        {
            "agreement_exists": {"answer": True},
            "agreement_type": {"answer": ""},
            "tenancy_start_date": {"answer": "2026-01-01"},
            "tenant_or_occupier_name": {"answer": "Jane Tenant"},
            "signed_by_parties": {"answer": None},
            "declaration_confirmed": {"answer": True},
        }
    )
    assert err == TENANCY_AGREEMENT_DETAILS_REQUIRED_MESSAGE


def test_tenancy_agreement_passes_when_required_fields_present():
    assert (
        validate_tenancy_agreement_structured_declaration_fields(
            {
                "agreement_exists": {"answer": True},
                "agreement_type": {"answer": "Assured shorthold tenancy"},
                "tenancy_start_date": {"answer": "2026-01-01"},
                "tenant_or_occupier_name": {"answer": "Jane Tenant"},
                "signed_by_parties": {"answer": True},
                "declaration_confirmed": {"answer": True},
            }
        )
        is None
    )

