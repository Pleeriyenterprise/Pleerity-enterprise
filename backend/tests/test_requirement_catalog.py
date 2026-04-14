"""
Unit tests for Requirement Catalog applicability.
- cert_gas_safety='NO' => GAS_SAFETY_CERT not in applicable list
- is_hmo=true => PROPERTY_LICENCE in applicable list
- licence_required='YES' => PROPERTY_LICENCE in applicable list
- Base case always includes EPC_CERT and EICR_CERT
"""
import pytest
from services.requirement_catalog import (
    get_applicable_requirements,
    explain_catalog_keys_for_property,
    GAS_SAFETY_CERT,
    EICR_CERT,
    EPC_CERT,
    PROPERTY_LICENCE,
    TENANCY_AGREEMENT,
    HOW_TO_RENT,
    DEPOSIT_PRESCRIBED_INFO,
    HMO_FIRE_RISK_EVIDENCE,
    SCOTLAND_LANDLORD_REGISTRATION,
    WALES_OCCUPATION_CONTRACT,
    REQUIREMENT_KEY_TO_DOCUMENT_TYPE,
)


class TestGasApplicability:
    """GAS_SAFETY_CERT applicable only when cert_gas_safety == 'YES'."""

    def test_cert_gas_safety_no_excludes_gas(self):
        prop = {"cert_gas_safety": "NO"}
        applicable = get_applicable_requirements(prop)
        assert GAS_SAFETY_CERT not in applicable

    def test_cert_gas_safety_yes_includes_gas(self):
        prop = {"cert_gas_safety": "YES"}
        applicable = get_applicable_requirements(prop)
        assert GAS_SAFETY_CERT in applicable

    def test_cert_gas_safety_absent_excludes_gas(self):
        prop = {}
        applicable = get_applicable_requirements(prop)
        assert GAS_SAFETY_CERT not in applicable


class TestLicenceApplicability:
    """PROPERTY_LICENCE when is_hmo or licence_required or cert_licence or licence_type."""

    def test_is_hmo_includes_property_licence(self):
        prop = {"is_hmo": True}
        applicable = get_applicable_requirements(prop)
        assert PROPERTY_LICENCE in applicable

    def test_licence_required_yes_includes_property_licence(self):
        prop = {"licence_required": "YES"}
        applicable = get_applicable_requirements(prop)
        assert PROPERTY_LICENCE in applicable

    def test_cert_licence_yes_includes_property_licence(self):
        prop = {"cert_licence": "YES"}
        applicable = get_applicable_requirements(prop)
        assert PROPERTY_LICENCE in applicable

    def test_licence_type_non_empty_includes_property_licence(self):
        prop = {"licence_type": "selective"}
        applicable = get_applicable_requirements(prop)
        assert PROPERTY_LICENCE in applicable

    def test_none_of_above_excludes_property_licence(self):
        prop = {"is_hmo": False, "licence_required": "NO", "cert_licence": "", "licence_type": None}
        applicable = get_applicable_requirements(prop)
        assert PROPERTY_LICENCE not in applicable


class TestBaseCaseAlwaysEpcEicr:
    """EICR_CERT and EPC_CERT always in applicable list."""

    def test_base_case_includes_epc_and_eicr(self):
        prop = {}
        applicable = get_applicable_requirements(prop)
        assert EPC_CERT in applicable
        assert EICR_CERT in applicable

    def test_minimal_property_includes_epc_and_eicr(self):
        prop = {"cert_gas_safety": "NO", "licence_required": "NO"}
        applicable = get_applicable_requirements(prop)
        assert EPC_CERT in applicable
        assert EICR_CERT in applicable


class TestEvidenceMapping:
    """Requirement key -> document_type for scoring pipeline."""

    def test_core_evidence_mapping(self):
        assert REQUIREMENT_KEY_TO_DOCUMENT_TYPE[GAS_SAFETY_CERT] == "gas_safety"
        assert REQUIREMENT_KEY_TO_DOCUMENT_TYPE[EICR_CERT] == "eicr"
        assert REQUIREMENT_KEY_TO_DOCUMENT_TYPE[EPC_CERT] == "epc"
        assert REQUIREMENT_KEY_TO_DOCUMENT_TYPE[PROPERTY_LICENCE] == "licence"


class TestPropertyTypeCommercial:
    """Commercial property type: residential-only items (tenancy, How to Rent, deposit) excluded."""

    def test_commercial_excludes_tenancy_and_deposit_even_when_active(self):
        prop = {"property_type": "commercial", "tenancy_active": True, "deposit_taken": True}
        applicable = get_applicable_requirements(prop)
        assert EICR_CERT in applicable
        assert EPC_CERT in applicable
        assert TENANCY_AGREEMENT not in applicable
        assert HOW_TO_RENT not in applicable
        assert DEPOSIT_PRESCRIBED_INFO not in applicable

    def test_commercial_still_includes_epc_eicr_gas_if_yes_licence_if_applicable(self):
        prop = {"property_type": "COMMERCIAL", "cert_gas_safety": "YES", "licence_required": "YES"}
        applicable = get_applicable_requirements(prop)
        assert EICR_CERT in applicable
        assert EPC_CERT in applicable
        assert GAS_SAFETY_CERT in applicable
        assert PROPERTY_LICENCE in applicable
        assert TENANCY_AGREEMENT not in applicable
        assert DEPOSIT_PRESCRIBED_INFO not in applicable

    def test_residential_with_tenancy_includes_tenancy_and_deposit(self):
        prop = {"property_type": "house", "tenancy_active": True, "deposit_taken": True}
        applicable = get_applicable_requirements(prop)
        assert TENANCY_AGREEMENT in applicable
        assert HOW_TO_RENT in applicable
        assert DEPOSIT_PRESCRIBED_INFO in applicable


class TestHmoFireExpansion:
    def test_hmo_adds_hmo_fire_risk_evidence(self):
        prop = {"is_hmo": True}
        applicable = get_applicable_requirements(prop)
        assert HMO_FIRE_RISK_EVIDENCE in applicable
        assert PROPERTY_LICENCE in applicable

    def test_non_hmo_no_hmo_fire_risk_evidence(self):
        prop = {"is_hmo": False, "licence_required": "NO"}
        applicable = get_applicable_requirements(prop)
        assert HMO_FIRE_RISK_EVIDENCE not in applicable


class TestJurisdictionSpecificCatalog:
    def test_scotland_landlord_registration_residential(self):
        prop = {"jurisdiction": "Scotland", "property_type": "flat"}
        applicable = get_applicable_requirements(prop, client_doc=None)
        assert SCOTLAND_LANDLORD_REGISTRATION in applicable

    def test_scotland_skipped_for_commercial(self):
        prop = {"jurisdiction": "Scotland", "property_type": "commercial"}
        applicable = get_applicable_requirements(prop)
        assert SCOTLAND_LANDLORD_REGISTRATION not in applicable

    def test_wales_occupation_contract_with_tenancy(self):
        prop = {"jurisdiction": "Wales", "property_type": "house", "tenancy_active": True}
        applicable = get_applicable_requirements(prop)
        assert WALES_OCCUPATION_CONTRACT in applicable

    def test_wales_no_contract_without_tenancy(self):
        prop = {"jurisdiction": "Wales", "property_type": "house", "tenancy_active": False}
        applicable = get_applicable_requirements(prop)
        assert WALES_OCCUPATION_CONTRACT not in applicable


class TestEvidenceMappingExtended:
    def test_jurisdiction_keys_mapped(self):
        assert REQUIREMENT_KEY_TO_DOCUMENT_TYPE[HMO_FIRE_RISK_EVIDENCE] == "fire_safety"
        assert REQUIREMENT_KEY_TO_DOCUMENT_TYPE[SCOTLAND_LANDLORD_REGISTRATION] == "licence"
        assert REQUIREMENT_KEY_TO_DOCUMENT_TYPE[WALES_OCCUPATION_CONTRACT] == "tenancy_agreement"


class TestExplainCatalogKeys:
    """explain_catalog_keys_for_property mirrors get_applicable_requirements inclusion flags."""

    def test_wales_no_tenancy_wales_contract_excluded_with_reason(self):
        prop = {"jurisdiction": "Wales", "property_type": "house", "tenancy_active": False}
        expl = explain_catalog_keys_for_property(prop, {})
        wales = next(x for x in expl if x["catalog_key"] == WALES_OCCUPATION_CONTRACT)
        assert wales["included"] is False
        assert "tenancy" in wales["reason"].lower()

    def test_explain_included_flags_match_applicable_set(self):
        prop = {"jurisdiction": "England", "property_type": "house", "cert_gas_safety": "YES", "is_hmo": True}
        applicable = set(get_applicable_requirements(prop, {}))
        expl = explain_catalog_keys_for_property(prop, {})
        for row in expl:
            assert row["included"] == (row["catalog_key"] in applicable)
