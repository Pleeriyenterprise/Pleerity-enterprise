"""AUDIENCE-GOVERNANCE-CONVERGENCE-01 — audience model and export section split."""

import pytest

from services.audience_governance_v1 import (
    AUDIENCE_LANDLORD_OPERATIONAL,
    AUDIENCE_REGULATOR_EVIDENTIAL,
    EXPORT_SECTION_RECORDED_NOT_VERIFIED,
    EXPORT_SECTION_UNRESOLVED,
    classify_export_section_bucket,
    interpret_requirement_for_audience,
    audience_export_preamble_paragraph,
)
from services.report_layout_governance import is_unresolved_row


def _self_recorded_satisfied():
    return {
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "assurance_tier": "SELF_RECORDED",
        "requirement_satisfied": True,
        "missing_required_document": False,
        "requirement_attention_eligible": False,
        "truth_presentation_stage": "declaration_recorded",
        "document_upload_required": False,
    }


def test_self_recorded_not_in_unresolved_bucket():
    row = _self_recorded_satisfied()
    assert not is_unresolved_row(row, property_doc=None, client_doc={})
    assert (
        classify_export_section_bucket(row, audience=AUDIENCE_REGULATOR_EVIDENTIAL)
        == EXPORT_SECTION_RECORDED_NOT_VERIFIED
    )


def test_landlord_operational_calm_for_satisfied_self_recorded():
    interp = interpret_requirement_for_audience(_self_recorded_satisfied(), AUDIENCE_LANDLORD_OPERATIONAL)
    assert interp["audience_status_label"] == "Recorded on file"
    assert interp["action_visibility"] == "none"
    assert interp["unresolved_bucket"] == "none"


def test_regulator_recorded_not_verified_disclosure():
    interp = interpret_requirement_for_audience(_self_recorded_satisfied(), AUDIENCE_REGULATOR_EVIDENTIAL)
    assert "not independently verified" in interp["audience_status_label"].lower()
    assert interp["disclosure_bucket"] == "recorded_not_verified"


def test_platform_review_pending_awaiting_review_bucket():
    row = {
        "client_lifecycle_state": "PENDING_REVIEW",
        "truth_presentation_stage": "platform_verification_pending",
        "requirement_satisfied": False,
        "requirement_attention_eligible": True,
        "requirement_attention_reason": "platform_verification_pending",
    }
    from services.audience_governance_v1 import EXPORT_SECTION_AWAITING_REVIEW

    assert (
        classify_export_section_bucket(row, audience=AUDIENCE_REGULATOR_EVIDENTIAL)
        == EXPORT_SECTION_AWAITING_REVIEW
    )


def test_action_required_stays_unresolved():
    row = {
        "client_lifecycle_state": "ACTION_REQUIRED",
        "status": "PENDING",
        "requirement_satisfied": False,
        "missing_required_document": True,
        "document_upload_required": True,
    }
    assert is_unresolved_row(row, property_doc=None, client_doc={})
    assert (
        classify_export_section_bucket(row, audience=AUDIENCE_REGULATOR_EVIDENTIAL)
        == EXPORT_SECTION_UNRESOLVED
    )


def test_export_preamble_present():
    assert "operational completion" in audience_export_preamble_paragraph(AUDIENCE_REGULATOR_EVIDENTIAL).lower()


def test_csv_fields_no_raw_enum():
    interp = interpret_requirement_for_audience(_self_recorded_satisfied(), AUDIENCE_REGULATOR_EVIDENTIAL)
    assert "SATISFIED_UNVERIFIED" not in interp["audience_status_label"]
    assert interp["operational_status"] == "recorded_on_file"


def test_pdf_sections_collect_split():
    from services.report_layout_governance import _collect_obligations_for_export_bucket
    from services.audience_governance_v1 import EXPORT_SECTION_AWAITING_REVIEW

    props = [{"property_id": "p1", "address_line_1": "1 High St"}]
    reqs = [
        _self_recorded_satisfied() | {"property_id": "p1", "description": "Legionella"},
        {
            "property_id": "p1",
            "client_lifecycle_state": "ACTION_REQUIRED",
            "description": "Gas",
            "requirement_satisfied": False,
            "missing_required_document": True,
            "document_upload_required": True,
        },
    ]
    un_rows, un_total = _collect_obligations_for_export_bucket(
        reqs, props, {}, bucket=EXPORT_SECTION_UNRESOLVED
    )
    rec_rows, rec_total = _collect_obligations_for_export_bucket(
        reqs, props, {}, bucket=EXPORT_SECTION_RECORDED_NOT_VERIFIED
    )
    assert un_total == 1
    assert rec_total == 1
    assert "Legionella" in rec_rows[0]["requirement"] or "legionella" in rec_rows[0]["requirement"].lower()


def test_evidence_readiness_pdf_has_governed_sections(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    from services.pdf_report_builder import build_portfolio_report
    from tests.test_pdf_report_builder import _minimal_report_data

    data = _minimal_report_data()
    data["requirements"] = [
        {
            "property_id": "p1",
            "client_lifecycle_state": "SATISFIED_UNVERIFIED",
            "assurance_tier": "SELF_RECORDED",
            "requirement_satisfied": True,
            "missing_required_document": False,
            "requirement_attention_eligible": False,
            "truth_presentation_stage": "declaration_recorded",
            "description": "Legionella assessment",
        }
    ]
    pdf = build_portfolio_report("client-1", data)
    text = pdf.decode("latin-1", errors="ignore")
    assert "Recorded but not independently verified" in text
    assert "operational completion" in text.lower() or "evidential assurance" in text.lower()
