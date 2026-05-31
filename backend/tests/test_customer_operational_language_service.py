"""Customer operational language governance — translation, sanitisation, CTA drift prevention."""
from __future__ import annotations

import json
import re
from copy import deepcopy

import pytest

from services.customer_operational_language_service import (
    UUID_PATTERN,
    contains_forbidden_customer_language,
    customer_severity_phrase,
    derive_customer_safe_cta,
    derive_customer_safe_issue_detail,
    derive_customer_safe_issue_summary,
    is_customer_safe_maintenance_escalation,
    sanitize_customer_visible_payload,
    sanitize_task_for_customer,
    suppress_internal_operational_fields,
    translate_internal_operational_message,
    translation_matrix_export,
)

_LEGACY_GAP_DESC = (
    "Ambiguous classification signals.\n\n"
    "Gap: MISMATCHED_EVIDENCE (HIGH). Key: "
    "10b2ddba-e952-4484-91d1-a8f0299d0824:6b33492c-5e24-453b-bcde-49844fd4aede:1b48c"
)
_LEGACY_MISSING = (
    "No acceptable evidence is linked for Gas Safety Certificate (CP12) at this property.\n\n"
    "Gap: MISSING_EVIDENCE (HIGH). Key: "
    "10b2ddba-e952-4484-91d1-a8f0299d0824:fedac677-cd2b-41fe-b5b8-b00f00ddfe67:5b1bb"
)


def _assert_no_internal_leaks(payload: dict) -> None:
    blob = json.dumps(payload, default=str)
    assert "MISMATCHED_EVIDENCE" not in blob
    assert "MISSING_EVIDENCE" not in blob
    assert "Gap:" not in blob
    assert "Key:" not in blob
    assert not re.search(r"\(\s*HIGH\s*\)", blob, re.I)
    assert not UUID_PATTERN.search(blob) or "screenshot" in blob  # no uuid in task fields
    for key in ("gap_key", "gap_kind", "triggering_rule", "operational_root_key", "classifier_state"):
        assert key not in payload
        meta = payload.get("metadata") or {}
        assert key not in meta


@pytest.mark.parametrize(
    "raw, code, expected_fragment",
    [
        (_LEGACY_GAP_DESC, "MISMATCHED_EVIDENCE", "could not confidently match"),
            (_LEGACY_MISSING, "MISSING_EVIDENCE", "valid evidence"),
        ("RECONCILIATION_PENDING queue sync", "RECONCILIATION_PENDING", "still processing"),
    ],
)
def test_translate_internal_operational_message(raw, code, expected_fragment):
    out = translate_internal_operational_message(raw, internal_code=code)
    assert expected_fragment.lower() in out.lower()
    assert not contains_forbidden_customer_language(out)
    assert "Gap:" not in out
    assert "Key:" not in out


def test_derive_customer_safe_issue_summary_legacy_db_issue():
    issue = {
        "description": _LEGACY_GAP_DESC,
        "triggering_rule": "compliance_gap:MISMATCHED_EVIDENCE",
        "created_from": "compliance",
    }
    summary = derive_customer_safe_issue_summary(issue)
    assert "classification signal" not in summary.lower()
    assert "MISMATCHED_EVIDENCE" not in summary
    assert "match" in summary.lower() or "information" in summary.lower()


def test_derive_customer_safe_issue_summary_gas_certificate():
    issue = {
        "description": _LEGACY_MISSING,
        "triggering_rule": "compliance_gap:MISSING_EVIDENCE",
        "created_from": "compliance",
    }
    summary = derive_customer_safe_issue_summary(issue)
    assert "gas safety" in summary.lower()
    assert "Gap:" not in summary


def test_maintenance_escalation_blocked_for_evidence_gaps():
    ctx = {
        "triggering_rule": "compliance_gap:MISMATCHED_EVIDENCE",
        "created_from": "compliance",
        "operational_root_key": "client:prop:req:CODE",
    }
    assert is_customer_safe_maintenance_escalation(ctx) is False


def test_maintenance_escalation_allowed_for_true_maintenance():
    ctx = {
        "triggering_rule": "maintenance:leak_report",
        "created_from": "tenant",
        "source_type": "issue",
    }
    assert is_customer_safe_maintenance_escalation(ctx) is True


def test_derive_customer_safe_cta_evidence_not_maintenance():
    cta = derive_customer_safe_cta(
        {
            "triggering_rule": "compliance_gap:MISMATCHED_EVIDENCE",
            "created_from": "compliance",
            "related_property_id": "prop-1",
        }
    )
    assert cta["label"] == "Review uploaded document"
    assert "maintenance" not in cta["label"].lower()
    assert "/documents" in cta["url"]


def test_customer_severity_phrase_governance():
    assert customer_severity_phrase("HIGH") == "Needs attention soon"
    assert customer_severity_phrase("MEDIUM") == "Needs follow-up"
    assert customer_severity_phrase("LOW") is None


def test_suppress_internal_operational_fields():
    payload = {
        "title": "Safe",
        "gap_key": "secret",
        "gap_kind": "MISMATCHED_EVIDENCE",
        "metadata": {"gap_key": "nested", "timing_label": "Due today"},
    }
    out = suppress_internal_operational_fields(payload)
    assert "gap_key" not in out
    assert "gap_kind" not in out
    assert out["metadata"]["timing_label"] == "Due today"
    assert "gap_key" not in out["metadata"]


def test_sanitize_task_for_customer_legacy_issue():
    task = {
        "id": "issue:abc",
        "source_type": "issue",
        "title": _LEGACY_GAP_DESC[:80],
        "description": _LEGACY_GAP_DESC,
        "primary_action_label": "Create maintenance job",
        "primary_action_url": "/operations/issues/abc",
        "metadata": {
            "gap_key": "10b2ddba:6b33:MISMATCHED_EVIDENCE",
            "issue_triggering_rule": "compliance_gap:MISMATCHED_EVIDENCE",
            "issue_created_from": "compliance",
            "severity": "HIGH",
        },
    }
    out = sanitize_task_for_customer(deepcopy(task))
    _assert_no_internal_leaks(out)
    assert out["primary_action_label"] == "Review uploaded document"
    assert "Create maintenance job" not in out["primary_action_label"]
    assert out.get("customer_safe_title")
    assert "Gap:" not in out["title"]
    assert "Gap:" not in out["description"]


def test_sanitize_today_payload_sections():
    sections = ["urgent", "in_progress", "upcoming"]
    for section in sections:
        task = sanitize_task_for_customer(
            {
                "id": f"{section}:1",
                "source_type": "issue",
                "section": section,
                "description": _LEGACY_MISSING,
                "metadata": {
                    "issue_triggering_rule": "compliance_gap:MISSING_EVIDENCE",
                    "issue_created_from": "compliance",
                },
            }
        )
        _assert_no_internal_leaks(task)
        assert "gas safety" in task["title"].lower() or "evidence" in task["title"].lower()


def test_sanitize_command_centre_payload():
    row = sanitize_customer_visible_payload(
        {
            "id": "issue:x",
            "source_type": "issue",
            "title": "Gap: MISSING_EVIDENCE (HIGH)",
            "description": _LEGACY_MISSING,
            "metadata": {"gap_kind": "MISSING_EVIDENCE", "semantic_state": "PENDING"},
            "triggering_rule": "compliance_gap:MISSING_EVIDENCE",
            "created_from": "compliance",
        },
        surface="command_center",
    )
    _assert_no_internal_leaks(row)
    assert row["metadata"].get("semantic_state") is None


def test_cognition_payload_sanitisation():
    envelope = sanitize_customer_visible_payload(
        {
            "user_safe_summary": _LEGACY_GAP_DESC,
            "why_matters": "Gap: AUTHORITY_UNSYNCED (MEDIUM)",
            "recommended_action": "Start maintenance job",
            "gap_kind": "MISMATCHED_EVIDENCE",
        },
        surface="cognition",
    )
    assert not contains_forbidden_customer_language(envelope.get("user_safe_summary", ""))
    assert "Gap:" not in envelope.get("why_matters", "")
    assert "AUTHORITY_UNSYNCED" not in json.dumps(envelope)


def test_translation_matrix_export_complete():
    matrix = translation_matrix_export()
    assert matrix["version"] == 1
    for code in ("MISMATCHED_EVIDENCE", "MISSING_EVIDENCE", "CLASSIFICATION_AMBIGUOUS"):
        assert code in matrix["mappings"]
        assert "summary" in matrix["mappings"][code]
        assert "cta" in matrix["mappings"][code]


def test_contains_forbidden_customer_language_detector():
    assert contains_forbidden_customer_language(_LEGACY_GAP_DESC)
    assert contains_forbidden_customer_language("Queue reconciliation pending")
    assert not contains_forbidden_customer_language("Upload gas safety certificate for this property.")
