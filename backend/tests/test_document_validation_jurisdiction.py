"""Jurisdiction-aware document validation for requirement-linked uploads."""
from unittest.mock import patch

from services.compliance_rules_registry import (
    ComplianceRuleSpec,
    allowed_document_type_tokens,
    get_rule,
    validate_document_type_for_requirement,
    validate_document_upload_for_requirement,
)


def _req_legionella():
    return {"requirement_code": "LEGIONELLA", "requirement_type": "legionella"}


def test_scotland_accepts_legionella_risk_assessment_document_type():
    req = {**_req_legionella(), "jurisdiction": "Scotland"}
    r = validate_document_upload_for_requirement(
        "legionella_risk_assessment",
        req,
        {},
        property_doc={"jurisdiction": "England"},
        client_doc={},
    )
    assert r["valid"] is True
    assert r["scoring_jurisdiction"] == "SCOTLAND"
    assert r["portfolio_jurisdiction"] == "Scotland"


def test_england_rejects_legionella_risk_assessment_document_type():
    req = {**_req_legionella(), "jurisdiction": "England"}
    r = validate_document_upload_for_requirement(
        "legionella_risk_assessment",
        req,
        {},
        property_doc=None,
        client_doc={},
    )
    assert r["valid"] is False
    assert r["scoring_jurisdiction"] == "ENGLAND_WALES"
    assert "jurisdiction" in r and r["reason"]


def test_property_jurisdiction_used_when_requirement_jurisdiction_blank():
    req = _req_legionella()
    prop_scot = {"jurisdiction": "Scotland"}
    r = validate_document_upload_for_requirement(
        "legionella_risk_assessment",
        req,
        {},
        property_doc=prop_scot,
        client_doc={"default_jurisdiction": "England"},
    )
    assert r["valid"] is True
    assert r["portfolio_jurisdiction"] == "Scotland"


def test_england_property_blocks_scotland_only_document_type():
    req = _req_legionella()
    r = validate_document_upload_for_requirement(
        "legionella_risk_assessment",
        req,
        {},
        property_doc={"jurisdiction": "England"},
        client_doc={},
    )
    assert r["valid"] is False


def test_structured_result_includes_jurisdiction_keys():
    r = validate_document_upload_for_requirement(
        "gas_safety",
        {"requirement_code": "GAS_SAFETY", "requirement_type": "gas_safety", "jurisdiction": "Wales"},
        {},
        property_doc=None,
        client_doc={},
    )
    assert r["valid"] is True
    assert set(r.keys()) >= {
        "valid",
        "reason",
        "jurisdiction",
        "scoring_jurisdiction",
        "portfolio_jurisdiction",
        "missing_metadata_fields",
    }


def test_validate_document_type_for_requirement_legacy_string():
    msg = validate_document_type_for_requirement(
        "legionella_risk_assessment",
        {**_req_legionella(), "jurisdiction": "England"},
    )
    assert msg is not None
    assert validate_document_type_for_requirement(
        "legionella",
        {**_req_legionella(), "jurisdiction": "England"},
    ) is None


def test_required_metadata_fields_rejected_when_missing():
    spec = ComplianceRuleSpec(
        canonical_code="GAS_SAFETY",
        storage_type="gas_safety",
        description="Gas Safety Certificate",
        frequency_days=365,
        warning_days=30,
        expects_expiry=True,
        required_metadata_fields=("engineer_id", "issue_date"),
    )
    with patch(
        "services.compliance_rules_registry.get_rule",
        return_value=spec,
    ):
        r = validate_document_upload_for_requirement(
            "gas_safety",
            {"requirement_code": "GAS_SAFETY", "requirement_type": "gas_safety", "jurisdiction": "England"},
            {},
            property_doc=None,
            client_doc={},
        )
    assert r["valid"] is False
    assert set(r["missing_metadata_fields"]) == {"engineer_id", "issue_date"}


def test_required_metadata_satisfied():
    spec = ComplianceRuleSpec(
        canonical_code="GAS_SAFETY",
        storage_type="gas_safety",
        description="Gas Safety Certificate",
        frequency_days=365,
        warning_days=30,
        expects_expiry=True,
        required_metadata_fields=("engineer_id",),
    )
    with patch("services.compliance_rules_registry.get_rule", return_value=spec):
        r = validate_document_upload_for_requirement(
            "gas_safety",
            {"requirement_code": "GAS_SAFETY", "requirement_type": "gas_safety", "jurisdiction": "England"},
            {"engineer_id": "REG-999", "issue_date": "2025-01-01"},
            property_doc=None,
            client_doc={},
        )
    assert r["valid"] is True


def test_allowed_document_type_tokens_from_spec():
    spec = get_rule("ENGLAND_WALES", "EPC")
    assert "epc" in allowed_document_type_tokens("ENGLAND_WALES", "EPC", spec)


def test_build_validation_result_persist_minimum_fields():
    from routes.documents import _build_validation_result_persist

    snap = _build_validation_result_persist(
        {
            "valid": True,
            "jurisdiction": "ENGLAND_WALES",
            "reason": None,
            "missing_metadata_fields": ["engineer_id"],
            "scoring_jurisdiction": "ENGLAND_WALES",
            "portfolio_jurisdiction": "England",
        },
        document_type_input="gas_safety",
        validated_at_iso="2026-04-02T12:00:00+00:00",
    )
    assert snap["valid"] is True
    assert snap["jurisdiction"] == "ENGLAND_WALES"
    assert snap["validated_at"] == "2026-04-02T12:00:00+00:00"
    assert snap["missing_metadata_fields"] == ["engineer_id"]
    assert snap["document_type_input"] == "gas_safety"
    assert snap["scoring_jurisdiction"] == "ENGLAND_WALES"
    assert snap["portfolio_jurisdiction"] == "England"
