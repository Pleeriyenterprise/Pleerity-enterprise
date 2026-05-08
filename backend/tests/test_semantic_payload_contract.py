from __future__ import annotations

from unittest.mock import patch

from services.semantic_payload_contract import (
    CANONICAL_REQUIREMENT_ROW,
    COMMAND_CENTRE_REQUIREMENT_ACTION,
    GENERIC_PRIORITY_ACTION,
    OPERATIONAL_TASK_ROW,
    REQUIREMENT_BACKED_TASK,
    SCORE_DRIVER_REQUIREMENT,
    validate_semantic_payload_contract,
    validate_semantic_payload_contract_batch,
)


def test_canonical_requirement_row_requires_core_semantic_fields():
    row = {
        "requirement_id": "r1",
        "property_id": "p1",
        "workflow_class": "MULTI_EVIDENCE",
        "take_action": {"primary": {"kind": "guided_evidence_resolution"}},
        "requirement_display": {"short_name": "Gas Safety"},
        "evidence_authority": {"state": "MISSING"},
        "evidence_completeness": {"is_incomplete": True},
    }
    d = validate_semantic_payload_contract(row, CANONICAL_REQUIREMENT_ROW)
    assert d["severity"] == "WARNING"  # expected_if_available fields may be absent
    assert d["missing_required"] == []
    assert d["unexpected_fields"] == []


def test_requirement_backed_task_missing_semantics_is_error():
    row = {
        "source_type": "requirement",
        "requirement_id": "r1",
        "property_id": "p1",
    }
    d = validate_semantic_payload_contract(row, REQUIREMENT_BACKED_TASK)
    assert d["severity"] == "ERROR"
    assert "workflow_class" in d["missing_required"]
    assert "take_action" in d["missing_required"]
    assert "requirement_display" in d["missing_required"]


def test_command_center_requirement_action_contract_works():
    row = {
        "source_type": "requirement",
        "requirement_id": "r1",
        "property_id": "p1",
        "workflow_class": "DOCUMENT_UPLOAD",
        "take_action": {"primary": {"kind": "navigate"}},
        "requirement_display": {"short_name": "EPC"},
        "primary_action_type": "upload_evidence",
        "primary_action_label": "Upload document",
        "primary_action_url": "/documents?property_id=p1&requirement_id=r1",
        "cta_url": "/documents?property_id=p1&requirement_id=r1",
    }
    d = validate_semantic_payload_contract(row, COMMAND_CENTRE_REQUIREMENT_ACTION)
    assert d["severity"] in ("OK", "WARNING")
    assert d["missing_required"] == []
    assert d["unexpected_fields"] == []


def test_operational_row_forbids_requirement_only_fields():
    row = {
        "source_type": "work_order",
        "property_id": "p1",
        "primary_action_type": "work_order",
        "primary_action_label": "View job details",
        "workflow_class": "MULTI_EVIDENCE",
        "evidence_authority": {"state": "MISSING"},
    }
    d = validate_semantic_payload_contract(row, OPERATIONAL_TASK_ROW)
    assert d["severity"] == "ERROR"
    assert "evidence_authority" in d["unexpected_fields"]


def test_generic_priority_action_forbids_requirement_semantics():
    row = {
        "source_type": "priority_action",
        "primary_action_type": "view_details",
        "primary_action_label": "View details",
        "workflow_class": "DOCUMENT_UPLOAD",
        "take_action": {"primary": {"kind": "navigate"}},
    }
    d = validate_semantic_payload_contract(row, GENERIC_PRIORITY_ACTION)
    assert d["severity"] == "ERROR"
    assert "workflow_class" in d["unexpected_fields"]
    assert "take_action" in d["unexpected_fields"]


def test_score_driver_sparse_row_flagged_honestly():
    row = {
        "property_id": "p1",
        "requirement_id": "r1",
        # missing workflow_class and requirement_display
    }
    d = validate_semantic_payload_contract(row, SCORE_DRIVER_REQUIREMENT)
    assert d["severity"] == "ERROR"
    assert "workflow_class" in d["missing_required"]


def test_batch_validation_reports_severity_counts():
    rows = [
        {
            "source_type": "requirement",
            "requirement_id": "r1",
            "property_id": "p1",
            "workflow_class": "DOCUMENT_UPLOAD",
            "take_action": {"primary": {"kind": "navigate"}},
            "requirement_display": {"short_name": "EPC"},
        },
        {
            "source_type": "requirement",
            "requirement_id": "r2",
            "property_id": "p1",
        },
    ]
    out = validate_semantic_payload_contract_batch(rows, REQUIREMENT_BACKED_TASK)
    assert out["severity"] == "ERROR"
    assert out["counts"]["ERROR"] >= 1


def test_requirement_truth_enrichment_output_meets_canonical_contract():
    from services.requirement_truth import enrich_requirement_dict

    req = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_code": "gas_safety",
        "requirement_type": "gas_safety",
        "status": "MISSING",
        "jurisdiction": "England",
    }
    with patch(
        "services.requirement_truth.resolve_engine_payload_from_requirement_row",
        return_value={},
    ), patch(
        "services.requirement_truth.resolve_take_action_envelope",
        return_value={},
    ), patch(
        "services.requirement_truth.enrich_take_action_envelope_for_client",
        return_value={
            "workflow_class": "DOCUMENT_UPLOAD",
            "take_action": {"primary": {"kind": "navigate", "label": "Upload document"}},
            "guidance_target": "evidence_resolution",
            "allowed_evidence_modes": ["document_upload"],
        },
    ), patch(
        "presentation.requirement_display_contract.build_requirement_display",
        return_value={"short_name": "Gas Safety"},
    ):
        out = enrich_requirement_dict(req, "MISSING", audience="client", published_registry_entries={})

    d = validate_semantic_payload_contract(
        {
            "requirement_id": out.get("requirement_id"),
            "property_id": out.get("property_id"),
            "workflow_class": out.get("workflow_class"),
            "take_action": out.get("take_action"),
            "requirement_display": out.get("requirement_display"),
            "evidence_authority": out.get("evidence_authority"),
            "evidence_completeness": out.get("evidence_completeness"),
            "guidance_target": out.get("guidance_target"),
            "allowed_evidence_modes": out.get("allowed_evidence_modes"),
        },
        CANONICAL_REQUIREMENT_ROW,
    )
    assert d["severity"] in ("OK", "WARNING")
    assert not d["missing_required"]
