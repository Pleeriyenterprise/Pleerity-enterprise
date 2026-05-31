"""Tests for requirement satisfaction vs document-gap convergence."""
from __future__ import annotations

from services.requirement_satisfaction_service import (
    RESOLUTION_RESOLVED,
    RESOLUTION_UNRESOLVED,
    SOURCE_SELF_CERTIFIED,
    attach_satisfaction_fields,
    derive_missing_document_status,
    is_requirement_satisfied,
    reconcile_client_lifecycle_with_satisfaction,
    summarize_client_compliance_diagnostics,
)
from services.client_requirement_lifecycle import ACTION_REQUIRED, SATISFIED_UNVERIFIED


def _legionella_declaration_row() -> dict:
    return {
        "requirement_id": "r-leg",
        "requirement_type": "legionella",
        "requirement_code": "legionella",
        "status": "PENDING",
        "client_surface_visible": True,
        "client_lifecycle_state": ACTION_REQUIRED,
        "truth_presentation_stage": "declaration_recorded",
        "truth_presentation_label": "Assessment recorded",
        "semantic_state": "DECLARATION_RECORDED",
        "governance_family": "PLATFORM_OVERSIGHT_OPTIONAL",
        "primary_evidence_record_id": "cer_abc",
        "take_action": {"suppressed": True, "primary": None},
    }


def test_legionella_declaration_not_missing_document():
    row = _legionella_declaration_row()
    assert derive_missing_document_status(row) == "NOT_REQUIRED"
    assert is_requirement_satisfied(row) is True


def test_legionella_reconcile_lifecycle_from_action_required():
    row = _legionella_declaration_row()
    patched = reconcile_client_lifecycle_with_satisfaction(row)
    assert patched.get("client_lifecycle_state") == SATISFIED_UNVERIFIED


def test_gas_pending_without_doc_counts_as_missing():
    row = {
        "requirement_id": "r-gas",
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "status": "PENDING",
        "client_surface_visible": True,
        "client_lifecycle_state": ACTION_REQUIRED,
        "truth_presentation_stage": "collect_evidence",
        "governance_family": "PLATFORM_VERIFIED",
    }
    fields = attach_satisfaction_fields(row)
    assert fields["document_upload_required"] is True
    assert fields["missing_required_document"] is True
    assert fields["requirement_satisfied"] is False


def test_admin_diagnostics_split():
    rows = [
        _legionella_declaration_row(),
        {
            "requirement_id": "r-gas",
            "requirement_type": "gas_safety",
            "status": "PENDING",
            "client_surface_visible": True,
            "client_lifecycle_state": ACTION_REQUIRED,
            "truth_presentation_stage": "collect_evidence",
            "governance_family": "PLATFORM_VERIFIED",
        },
    ]
    enriched = [{**r, **attach_satisfaction_fields(r)} for r in rows]
    diag = summarize_client_compliance_diagnostics(enriched)
    assert diag["missing_required_documents"] == 1
    assert diag["requirements_unresolved"] == 1
    assert diag["satisfied_by_declaration"] >= 1


def test_verified_epc_not_unresolved():
    row = {
        "requirement_id": "r-epc",
        "requirement_type": "epc",
        "status": "PENDING",
        "client_surface_visible": True,
        "client_lifecycle_state": "VERIFIED",
        "truth_presentation_stage": "verified",
        "semantic_state": "VERIFIED",
        "document_id": "doc1",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT"},
    }
    fields = attach_satisfaction_fields(row)
    assert fields["requirement_satisfied"] is True
    assert fields["requirement_resolution_status"] == RESOLUTION_RESOLVED
    assert fields["missing_required_document"] is False
