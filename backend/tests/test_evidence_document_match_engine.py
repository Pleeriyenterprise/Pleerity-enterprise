"""Tests for requirement-aware evidence document matching (Compliance Vault Pro)."""
import pytest

from services.evidence_document_match_engine import (
    document_blocks_verified_satisfaction,
    evaluate_document_requirement_match,
    match_evaluation_to_persisted_document_fields,
)
from services.evidence_document_taxonomy import (
    MATCH_OUTCOME_MATCH_LIKELY,
    MATCH_OUTCOME_MISMATCH_SUSPECTED,
    POLICY_BLOCK_UPLOAD,
)


def _gas_req():
    return {
        "requirement_id": "r1",
        "requirement_type": "gas_safety",
        "property_id": "p1",
    }


def test_strong_extraction_mismatch_against_gas_requirement():
    ev = evaluate_document_requirement_match(
        requirement=_gas_req(),
        filename="electrical-certificate.pdf",
        user_declared_document_type="Gas safety certificate",
        extracted_data={
            "document_type": "EICR",
            "summary": "Electrical Installation Condition Report BS7671",
        },
        upload_route_context="test",
    )
    assert ev["match_outcome"] == MATCH_OUTCOME_MISMATCH_SUSPECTED
    assert ev["evidence_satisfies_requirement"] is False
    assert document_blocks_verified_satisfaction(
        {"match_outcome": ev["match_outcome"], "evidence_satisfies_requirement": ev["evidence_satisfies_requirement"]}
    )


def test_aligned_extraction_for_gas():
    ev = evaluate_document_requirement_match(
        requirement=_gas_req(),
        filename="gas-safety-2024.pdf",
        user_declared_document_type=None,
        extracted_data={
            "document_type": "Landlord Gas Safety Record",
            "summary": "Gas Safe Register CP12",
        },
        upload_route_context="test",
    )
    assert ev["match_outcome"] in (MATCH_OUTCOME_MATCH_LIKELY, "MATCH_CONFIRMED")
    assert ev.get("evidence_satisfies_requirement") is True
    assert not document_blocks_verified_satisfaction(
        match_evaluation_to_persisted_document_fields(ev) | {"match_outcome": ev["match_outcome"]}
    )


def test_declared_wrong_family_blocks_upload_policy():
    ev = evaluate_document_requirement_match(
        requirement=_gas_req(),
        filename="misc.pdf",
        user_declared_document_type="EPC certificate",
        extracted_data=None,
        upload_route_context="client_upload_pre_analysis",
    )
    assert ev["evidence_match_policy"] == POLICY_BLOCK_UPLOAD


def test_persist_subset_contains_core_keys():
    ev = evaluate_document_requirement_match(
        requirement=_gas_req(),
        filename="x.pdf",
        user_declared_document_type=None,
        extracted_data={"document_type": "EICR"},
        upload_route_context="test",
    )
    patch = match_evaluation_to_persisted_document_fields(ev)
    assert "predicted_document_type" in patch
    assert "match_outcome" in patch


def test_unknown_without_requirement():
    ev = evaluate_document_requirement_match(
        requirement=None,
        filename="scan001.pdf",
        user_declared_document_type=None,
        extracted_data=None,
        upload_route_context="test",
    )
    assert ev.get("predicted_document_type") is not None
