"""PRESENTATION-AUTHORITY-ALIGNMENT-01 — lifecycle copy and checklist presentation."""
from services.lifecycle_authority_copy import (
    calendar_overdue_subline,
    digest_action_line_suffix,
    requirement_count_footnote,
)
from services.onboarding_checklist_service import (
    ITEM_UPLOAD_OR_COMPLIANCE_ACTION,
    _derive_setup_presentation,
)


def test_calendar_overdue_subline_not_legal_verdict():
    assert "not a legal compliance verdict" in calendar_overdue_subline().lower()


def test_digest_upload_suffix_evidence_required_not_missing():
    suffix = digest_action_line_suffix(primary_action_type="upload_evidence")
    assert "evidence required" in suffix
    assert "missing evidence" not in suffix


def test_requirement_count_footnote_when_applicable_exceeds_tracked():
    note = requirement_count_footnote(applicable_count=18, tracked_count=12)
    assert note is not None
    assert "removed" in note.lower()


def test_setup_presentation_documents_step_from_checklist_item():
    items = [
        {"id": ITEM_UPLOAD_OR_COMPLIANCE_ACTION, "label": "Upload first document", "completed_at": None},
    ]
    sp = _derive_setup_presentation(items)
    assert sp["documents_step_recommended"] is True
    assert sp["authority"] == "onboarding_checklist"

    items[0]["completed_at"] = "2026-01-01T00:00:00Z"
    sp2 = _derive_setup_presentation(items)
    assert sp2["documents_step_recommended"] is False
