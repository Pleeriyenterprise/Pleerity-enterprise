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
    GAS_SAFETY_CERT,
    EICR_CERT,
    EPC_CERT,
    PROPERTY_LICENCE,
    TENANCY_AGREEMENT,
    HOW_TO_RENT,
    DEPOSIT_PRESCRIBED_INFO,
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
