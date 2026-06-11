"""S2-B Lite — report interpretability helpers and bounded copy."""

from __future__ import annotations

from datetime import datetime, timezone

from email_templates.unified.scheduled_report_digest import build_scheduled_report_digest_html
from models import EmailTemplateAlias
from services.email_service import EmailService
from services.report_compliance_summary_executive import (
    build_compliance_summary_executive_model,
    enrich_readiness_narrative,
)
from services.report_interpretation_v1 import (
    audit_readiness_scope_note,
    digest_directional_caveat_lines,
    how_to_read_email_html_bullets,
    how_to_read_paragraphs,
    metric_interpretation_line,
    report_relationship_note,
    scheduled_summary_has_material_exposure,
)
from services.report_requirements_operational import TRIAGE_SECTION_TITLES, TRIAGE_COMPLIANT
from services.reporting_service import ReportingService
from services.vocabulary_contract_v1 import find_prohibited_phrases, metric_boundary_note


def test_metric_boundary_helpers_cover_key_metrics():
    for metric_id in (
        "cvp",
        "completion_pct",
        "compliance_rate",
        "evidence_confidence",
        "audit_readiness",
        "operational_posture",
        "operational_exposure",
        "property_readiness",
        "verification_maturity",
    ):
        line = metric_interpretation_line(metric_id)
        assert line
        lower = line.lower()
        assert any(
            token in lower
            for token in (
                "legal",
                "export",
                "operational",
                "readiness",
                "portfolio",
                "verified",
                "recorded",
            )
        )


def test_metric_boundary_notes_no_equivalence_language():
    cvp = metric_boundary_note("cvp")
    completion = metric_boundary_note("completion_pct")
    combined = f"{cvp} {completion}".lower()
    assert "same as" not in combined
    assert "equivalent" not in combined
    assert "may differ" in cvp.lower() or "distinct" in completion.lower()


def test_audit_readiness_scope_prevents_external_approval_assumption():
    note = audit_readiness_scope_note("Audit-ready")
    low = note.lower()
    assert "external auditor" in low or "does not mean" in low
    assert find_prohibited_phrases(note) == []


def test_how_to_read_paragraphs_per_report_class():
    for report_class in (
        "compliance_summary",
        "requirements",
        "evidence_readiness",
        "monthly_digest",
        "scheduled_compliance_summary",
    ):
        paras = how_to_read_paragraphs(report_class)
        min_paras = 2 if report_class.startswith("scheduled_") else 3
        assert len(paras) >= min_paras
        blob = " ".join(paras).lower()
        assert any(
            token in blob
            for token in ("legal", "export", "operational", "audit", "verified", "portal", "directional")
        )


def test_report_relationship_notes_human_readable_not_authority_routing():
    for report_class in ("compliance_summary", "requirements", "evidence_readiness", "monthly_digest"):
        note = report_relationship_note(report_class)
        low = note.lower()
        assert "digest" in low or "requirements report" in low or "compliance summary" in low
        assert "governed" not in low
        assert "immutable" not in low
        assert "ontology" not in low


def test_digest_directional_caveats_first_snapshot_and_movement():
    first = digest_directional_caveat_lines(has_prior_snapshot=False)
    assert any("first digest" in ln.lower() for ln in first)
    later = digest_directional_caveat_lines(has_prior_snapshot=True)
    assert any("directional" in ln.lower() for ln in later)
    assert not any("first digest" in ln.lower() for ln in later)


def test_scheduled_exposure_guard_high_score_with_overdue():
    summary = {
        "requirements_breakdown": {"overdue": 2, "pending": 0, "compliant": 10},
        "compliance_breakdown": {"green": 5, "amber": 0, "red": 0},
    }
    assert scheduled_summary_has_material_exposure(summary, properties=[])
    html, _ = build_scheduled_report_digest_html(
        {
            "frequency": "weekly",
            "report_type": "compliance_summary",
            "generated_date": "02 Jun 2026",
            "portal_link": "https://app.example/today",
            "report_summary": summary,
            "properties_snapshot": [],
            "report_rows": [],
        }
    )
    assert "all clear" not in html.lower()
    assert "operational follow-up" in html.lower()


def test_scheduled_favourable_posture_with_unresolved_evidence():
    summary = {
        "requirements_breakdown": {"overdue": 0, "pending": 3, "compliant": 8},
        "compliance_breakdown": {"green": 4, "amber": 0, "red": 0},
        "compliance_rate": 90,
    }
    assert scheduled_summary_has_material_exposure(summary, [])
    html, _ = build_scheduled_report_digest_html(
        {
            "frequency": "daily",
            "report_type": "compliance_summary",
            "generated_date": "02 Jun 2026",
            "portal_link": "https://app.example/today",
            "report_summary": summary,
            "properties_snapshot": [{"address": "1 St", "compliance_status": "GREEN"}],
            "report_rows": [],
        }
    )
    assert "green (favourable)" in html.lower()
    assert "all clear" not in html.lower()


def test_scheduled_no_red_amber_without_exposure_uses_bounded_panel():
    summary = {
        "requirements_breakdown": {"overdue": 0, "pending": 0, "compliant": 8},
        "compliance_breakdown": {"green": 2, "amber": 0, "red": 0},
    }
    html, _ = build_scheduled_report_digest_html(
        {
            "frequency": "daily",
            "report_type": "compliance_summary",
            "generated_date": "02 Jun 2026",
            "portal_link": "https://app.example/today",
            "report_summary": summary,
            "properties_snapshot": [],
            "report_rows": [],
        }
    )
    assert "no red or amber property indicators" in html.lower()
    assert "all clear" not in html.lower()


def test_scheduled_email_no_on_track_green_stale_phrase():
    model = {
        "frequency": "daily",
        "report_type": "compliance_summary",
        "generated_date": "02 Jun 2026",
        "portal_link": "https://app.example/today",
        "report_summary": {
            "total_properties": 1,
            "compliance_rate": 80,
            "compliance_breakdown": {"green": 1, "amber": 0, "red": 0},
            "requirements_breakdown": {"compliant": 4, "overdue": 0, "expiring_soon": 0, "pending": 0},
        },
        "properties_snapshot": [],
        "report_rows": [],
    }
    html = EmailService()._build_html_body(EmailTemplateAlias.SCHEDULED_REPORT, model)
    assert "on track (green)" not in html.lower()
    assert "obligation satisfaction rate" in html.lower()


def test_compliance_csv_includes_how_to_read_and_scoped_rate_label():
    svc = ReportingService()
    data = {
        "report_type": "Compliance Summary",
        "generated_at": "2026-06-02T12:00:00Z",
        "client": {"name": "Test Client"},
        "summary": {
            "total_properties": 1,
            "compliance_rate": 75,
            "compliance_breakdown": {"green": 1, "amber": 0, "red": 0},
            "total_requirements": 4,
            "requirements_breakdown": {
                "compliant": 3,
                "pending": 1,
                "overdue": 0,
                "expiring_soon": 0,
            },
            "expiring_next_30_days": 0,
            "expiring_next_60_days": 0,
            "expiring_next_90_days": 0,
            "compliance_score_headline": {},
        },
        "properties": [],
        "reporting_semantics": {"counts": {}},
    }
    out = svc._generate_compliance_csv(data)
    csv_text = out["content"]
    assert "HOW TO READ THIS REPORT" in csv_text
    assert "Obligation satisfaction rate," in csv_text
    assert "(export scope)" not in csv_text
    assert "Compliance Rate," not in csv_text


def test_evidence_readiness_how_to_read_audit_ready_not_external_pass():
    paras = how_to_read_paragraphs("evidence_readiness")
    blob = " ".join(paras).lower()
    assert "external auditor" in blob or "does not mean" in blob


def test_compliance_audit_scope_note_once_not_in_executive_notes():
    readiness = {
        "evidence_completeness_pct": 92,
        "unresolved_evidence_exposure": 0,
        "audit_readiness": "Audit-ready",
    }
    out = enrich_readiness_narrative(readiness)
    notes = " ".join(out.get("executive_notes") or []).lower()
    assert "external auditor" not in notes
    scope = audit_readiness_scope_note("Audit-ready").lower()
    assert "external auditor" in scope or "does not mean" in scope


def test_requirements_triage_verified_accepted_not_fully_compliant_title():
    assert TRIAGE_SECTION_TITLES[TRIAGE_COMPLIANT] == "Verified or accepted obligations"
    assert "fully compliant" not in TRIAGE_SECTION_TITLES[TRIAGE_COMPLIANT].lower()


def test_improving_trend_fixture_recorded_unverified_portfolio():
    """Recorded-but-unverified obligations remain scoped separately from verified counts."""
    from services.report_requirements_operational import build_requirements_operational_csv_rows

    req = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "epc",
        "description": "EPC certificate",
        "status": "COMPLIANT",
        "due_date": "2027-01-01",
        "client_lifecycle_state": "MONITORING",
        "requirement_satisfied": True,
        "self_recorded": True,
        "requirement_attention_eligible": False,
    }
    props = [{"property_id": "p1", "address_line_1": "1 Test Lane", "postcode": "AB1 2CD"}]
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    _, _, enriched = build_requirements_operational_csv_rows(
        requirements=[req],
        properties=props,
        client_doc={},
        now=now,
    )
    paras = how_to_read_paragraphs("requirements")
    assert any("recorded" in p.lower() or "verified" in p.lower() for p in paras)
    assert enriched  # model builds without regression


def test_email_how_to_read_bullets_capped_at_two():
    assert len(how_to_read_email_html_bullets("monthly_digest")) == 2
    assert len(how_to_read_email_html_bullets("scheduled_compliance_summary")) == 2


def test_monthly_digest_intelligence_includes_how_to_read():
    from services.monthly_digest_operational_intelligence import build_digest_intelligence

    intel = build_digest_intelligence({"deltas": {"has_prior_snapshot": True}, "risk_level": "low"})
    assert intel.get("how_to_read")
    assert intel.get("directional_caveats")
    assert "digest" in (intel.get("report_relationship_note") or "").lower()
