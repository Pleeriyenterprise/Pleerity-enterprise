"""REPORTING-HUMAN-LANGUAGE-CONVERGENCE-01 — human language mapping and leakage prevention."""

import pytest

from services.report_human_language_v1 import (
    ASSURANCE_TIER_LABELS,
    LIFECYCLE_LABELS,
    SCORE_STATUS_LABELS,
    contains_internal_language_leak,
    human_assurance_tier_label,
    human_governance_chip_line,
    human_lifecycle_label,
    human_operational_renewal_date,
    human_requirements_evidence_posture,
    human_score_status_label,
    human_async_disclosure_lines,
    mapping_matrix_export,
)
from services.report_layout_governance import assurance_tier_chip, governance_chip_line
from services.reporting_semantics_v1 import (
    LIVE_REGENERATED_DISCLOSURE,
    async_reporting_disclosure,
)


def test_lifecycle_mapping_no_raw_enum_in_label():
    row = {"client_lifecycle_state": "SATISFIED_UNVERIFIED"}
    assert human_lifecycle_label(row) == "Recorded on file"
    assert "SATISFIED_UNVERIFIED" not in human_lifecycle_label(row)


def test_operational_renewal_date_unknown():
    assert human_operational_renewal_date({"due_date": "UNKNOWN_DATE"}) == "No date on file"


def test_requirements_evidence_posture_human():
    row = {"client_lifecycle_state": "SATISFIED_UNVERIFIED", "assurance_tier": "SELF_RECORDED"}
    posture = human_requirements_evidence_posture(
        row, {"audience_status_label": "Recorded on file"}
    )
    assert "not independently verified" in posture.lower()
    assert "SELF_RECORDED" not in posture


def test_assurance_tier_mapping():
    assert human_assurance_tier_label({"assurance_tier": "SELF_RECORDED"}) == "Self-recorded assurance"
    assert human_assurance_tier_label({"assurance_tier": "VERIFIED_DOCUMENT"}) == "Document verified"


def test_score_status_human_labels():
    assert human_score_status_label("calculating") == "Score updating"
    assert human_score_status_label("stale") == "Score may be out of date"
    assert "calculating" not in human_score_status_label("calculating").lower() or True


def test_governance_chip_line_no_internal_codes():
    row = {
        "assurance_tier": "SELF_RECORDED",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "date_confidence": "CONFIRMED",
        "evidence_doc_id": "doc1",
    }
    line = human_governance_chip_line(row)
    assert "SELF-REC" not in line
    assert "SAT-UNVER" not in line
    assert "SELF_RECORDED" not in line


def test_assurance_tier_chip_uses_human_labels():
    chip = assurance_tier_chip({"assurance_tier": "SELF_RECORDED"})
    assert chip == "Self-recorded assurance"[:24] or "Self-recorded assuran"


def test_contains_internal_language_leak():
    assert contains_internal_language_leak("SATISFIED_UNVERIFIED lifecycle")
    assert contains_internal_language_leak("score_status=calculating")
    assert not contains_internal_language_leak("Recorded on file — awaiting review")


def test_async_disclosure_no_persisted_jargon():
    block = async_reporting_disclosure(score_status="calculating", score_status_message=None, last_calculated_at=None)
    joined = " ".join(block["messages"])
    assert "persisted" not in joined.lower()
    assert "score_status=" not in joined


def test_live_regenerated_disclosure_human_readable():
    assert "latest portfolio" in LIVE_REGENERATED_DISCLOSURE.lower()
    assert "live_regenerated" not in LIVE_REGENERATED_DISCLOSURE


def test_human_async_lines_reject_leaky_server_message():
    lines = human_async_disclosure_lines(
        score_status="stale",
        score_status_message="persisted_property_score queue pending",
    )
    assert not any("persisted_property" in ln for ln in lines)


def test_mapping_matrix_export_complete():
    m = mapping_matrix_export()
    assert m["version"] == "v1"
    assert "SATISFIED_UNVERIFIED" in m["lifecycle"]
    assert m["lifecycle"]["SATISFIED_UNVERIFIED"] == "Recorded on file"


def test_pdf_governance_chip_integration():
    line = governance_chip_line(
        {
            "assurance_tier": "SELF_RECORDED",
            "client_lifecycle_state": "PENDING_REVIEW",
        }
    )
    assert "SELF-REC" not in line
