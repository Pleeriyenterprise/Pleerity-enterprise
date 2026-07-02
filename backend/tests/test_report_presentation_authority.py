"""REPORT-PRESENTATION-AUTHORITY-01 regression tests."""
from __future__ import annotations

from report_presentation.actions import format_actions_closing_lines, present_recommended_actions
from report_presentation.actors import present_actor_label
from report_presentation.authority import ReportPresentationAuthority
from report_presentation.constants import AUTHORITY_VERSION
from report_presentation.evidence import infer_document_title, present_evidence_row
from report_presentation.profiles import resolve_profile
from report_presentation.technical_language import contains_technical_language_leak, sanitize_customer_section_text
from report_presentation.timeline import build_layered_timeline, humanize_audit_event_action


def test_authority_version():
    assert ReportPresentationAuthority.version == AUTHORITY_VERSION


def test_executive_profile_for_compliance_summary():
    assert resolve_profile("compliance_summary") == "executive"


def test_evidential_profile_for_audit_pack():
    assert resolve_profile("audit_evidence_pack") == "evidential"


def test_risk_signal_created_business_narrative():
    ev = {
        "action": "RISK_SIGNAL_CREATED",
        "timestamp": "2026-06-13T13:15:42.445699+00:00",
        "actor_role": "SYSTEM",
        "metadata": {"risk_type": "ELECTRICAL", "risk_level": "high"},
    }
    row = ReportPresentationAuthority.present_timeline_row(ev, profile="evidential")
    assert "Electrical" in row["business_event"]
    assert row["summary"] != row["business_event"]
    assert row["actor"] == "Automated Compliance Monitoring"
    assert "445699" not in row["timestamp"]


def test_score_updated_with_delta():
    ev = {
        "action": "COMPLIANCE_SCORE_UPDATED",
        "metadata": {"previous_score": 92, "new_score": 74, "reason": "OVERDUE_EICR"},
    }
    row = ReportPresentationAuthority.present_timeline_row(ev)
    assert "reduced" in row["summary"].lower() or "74" in row["summary"]
    assert "Compliance score" in row["business_event"] or "revised" in row["business_event"].lower()


def test_regen_suppressed_from_primary_layer():
    events = [
        {"action": "RISK_SIGNAL_CREATED", "metadata": {"risk_type": "ELECTRICAL"}},
        {"action": "RISK_SIGNAL_REGEN_COMPLETED"},
        {"action": "RISK_SIGNAL_REGEN_COMPLETED"},
        {"action": "COMPLIANCE_SCORE_UPDATED", "metadata": {"previous_score": 90, "new_score": 80}},
    ]
    layered = build_layered_timeline(events, report_class="audit_trail")
    primary_actions = {r["action_raw"] for r in layered["primary_rows"]}
    assert "RISK_SIGNAL_REGEN_COMPLETED" not in primary_actions
    assert len(layered["technical_rows"]) == 4
    assert layered["suppressed_from_primary"] >= 2


def test_technical_appendix_included_for_evidential():
    events = [{"action": "DOCUMENT_VERIFIED", "metadata": {"document_name": "gas_cert.pdf"}}]
    layered = build_layered_timeline(events, report_class="audit_evidence_pack")
    assert layered["include_technical_appendix"] is True


def test_actor_landlord_for_client():
    assert present_actor_label("ROLE_CLIENT") == "Landlord"


def test_actor_not_generic_system_for_score_events():
    label = present_actor_label("SYSTEM", metadata={"action": "COMPLIANCE_SCORE_UPDATED"})
    assert label == "Automated Compliance Monitoring"
    assert label != "System"


def test_humanize_no_engineering_regeneration_phrase():
    label = humanize_audit_event_action("RISK_SIGNAL_REGEN_COMPLETED")
    assert "regeneration completed" not in label.lower()
    assert "risk assessment" in label.lower() or "updated" in label.lower()


def test_technical_language_sanitized():
    raw = "Frozen deterministic snapshot at generation boundary with manifest checksums."
    clean = sanitize_customer_section_text(raw)
    assert "generation boundary" not in clean.lower()
    assert contains_technical_language_leak(raw) is True
    assert contains_technical_language_leak(clean) is False


def test_technical_language_audit_pack_phrases():
    raw = "Compliance metrics reflect runtime-visible obligations at the generation boundary."
    clean = sanitize_customer_section_text(raw)
    assert "runtime-visible" not in clean.lower()
    assert "generation boundary" not in clean.lower()
    assert contains_technical_language_leak(clean) is False


def test_audit_pack_scope_statement_lines_professional():
    from services.compliance_audit_evidence_pack_service import _build_scope_statement_lines

    lines = _build_scope_statement_lines(
        generated_at="2026-06-30T12:00:00+00:00",
        jurisdiction="England",
    )
    blob = "\n".join(lines).lower()
    assert "generation boundary" not in blob
    assert "runtime-visible" not in blob
    assert "report generated (utc)" in blob


def test_evidence_title_prefers_certificate_name():
    title = infer_document_title(filename="NewTownGeorgian_EICR.pdf", requirement_type="eicr")
    assert "Electrical Installation Condition Report" in title


def test_present_evidence_row():
    row = present_evidence_row(
        {"obligation": "Gas Safety Certificate", "status": "VERIFIED"},
        doc={"filename": "upload_123.pdf"},
    )
    assert "Gas Safety" in row["title"]


def test_recommended_actions_structure():
    matrix = [
        {
            "obligation": "Gas Safety Certificate",
            "priority": "Critical",
            "status": "OVERDUE",
            "property": "1 High Street",
            "expiry": "2026-06-01",
        }
    ]
    actions = present_recommended_actions(matrix)
    assert len(actions) == 1
    assert actions[0]["priority"] == "Critical"
    assert "Gas Safety" in actions[0]["evidence_required"]
    lines = format_actions_closing_lines(actions)
    assert len(lines) >= 1
    assert "Critical" in lines[0]


def test_executive_summary_payload():
    payload = ReportPresentationAuthority.build_executive_summary(
        report_class="compliance_summary",
        posture_lines=["Favourable posture"],
    )
    assert payload["title"] == "Executive summary"
    assert payload["posture_lines"]


def test_no_duplicate_event_summary_for_risk_created():
    ev = {
        "action": "RISK_SIGNAL_CREATED",
        "metadata": {"risk_type": "ELECTRICAL", "risk_level": "medium"},
    }
    row = ReportPresentationAuthority.present_timeline_row(ev)
    assert row["business_event"].lower() != row["summary"].lower()
