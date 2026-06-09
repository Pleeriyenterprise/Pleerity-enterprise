"""Operational Evidence Readiness report presentation tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.pdf_report_builder import build_portfolio_report, build_property_report
from services.report_evidence_readiness_operational import (
    COMPACT_FOOTER_SNAPSHOT,
    build_operational_matrix_rows,
    build_recommended_remediation_actions,
    enrich_readiness_interpretation,
    group_audit_events_for_operational_report,
    humanize_audit_event_action,
)
from services.report_pdf_templates import build_matrix_rows


def _req(**kw):
    base = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "description": "Gas Safety Certificate annual inspection record",
        "status": "OVERDUE",
        "mandatory": True,
        "due_date": "2026-07-14",
    }
    base.update(kw)
    return base


def test_humanize_audit_event_action():
    assert humanize_audit_event_action("COMPLIANCE_RECALC_SLA_BREACH") == (
        "Compliance recalculation exceeded SLA threshold"
    )
    assert humanize_audit_event_action("RISK_SIGNAL_REGEN_COMPLETED") == (
        "Risk assessment regeneration completed"
    )
    assert "foo" in humanize_audit_event_action("FOO_BAR_EVENT").lower()


def test_group_audit_events_collapses_repetitive_telemetry():
    events = [
        {"timestamp": "2026-01-01T10:00:00", "action": "COMPLIANCE_RECALC_SLA_BREACH", "actor_role": "system"},
        {"timestamp": "2026-01-01T11:00:00", "action": "COMPLIANCE_RECALC_SLA_BREACH", "actor_role": "system"},
        {"timestamp": "2026-01-02T10:00:00", "action": "DOCUMENT_UPLOADED", "actor_role": "ROLE_CLIENT", "metadata": {"summary": "Gas cert uploaded"}},
    ]
    grouped = group_audit_events_for_operational_report(events)
    assert "Evidence lifecycle" in grouped
    assert "COMPLIANCE_RECALC_SLA_BREACH" not in str(grouped)
    assert any("Gas cert" in (e.get("summary") or "") for items in grouped.values() for e in items)


def test_enrich_readiness_interpretation_adds_context():
    ind = enrich_readiness_interpretation(
        {
            "total_obligations": 12,
            "evidence_completeness_pct": 42,
            "evidence_completeness_note": "5 of 12 obligations have evidence on file.",
            "audit_readiness": "Not audit-ready — material gaps remain",
            "audit_confidence": "Low",
            "unresolved_evidence_exposure": 4,
        }
    )
    assert any("5 of 12" in ln or "7 obligation" in ln for ln in ind["interpretation_lines"])
    assert any("remediation" in ln.lower() for ln in ind["interpretation_lines"])


def test_build_recommended_remediation_actions_priority_buckets():
    rows = build_matrix_rows(
        requirements=[_req(), _req(requirement_id="r2", status="EXPIRING_SOON", mandatory=False)],
        properties=[{"property_id": "p1"}],
        client_doc={},
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    actions = build_recommended_remediation_actions(rows)
    assert actions["Priority 1"] or actions["Priority 2"] or actions["Priority 3"]
    assert any("Upload" in a or "Review" in a for bucket in actions.values() for a in bucket)


def test_operational_matrix_six_core_columns():
    core, appendix = build_operational_matrix_rows(
        requirements=[_req()],
        properties=[{"property_id": "p1"}],
        client_doc={},
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    assert len(core) == 1
    assert set(core[0].keys()) == {
        "obligation",
        "status",
        "evidence",
        "expiry",
        "risk",
        "action_required",
        "priority",
    }
    assert "category" in appendix[0]


def test_portfolio_pdf_operational_sections(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    long_name = "HMO fire safety management plan and emergency lighting certificate " * 2
    data = {
        "client": {"company_name": "Test Co", "customer_reference": "CRN-001"},
        "properties": [{"property_id": "p1", "address_line_1": "1 High St", "compliance_score": 60, "risk_level": "Medium"}],
        "requirements": [_req(description=long_name[:90])],
        "audit_logs": [
            {"timestamp": "2026-06-01T10:00:00", "action": "DOCUMENT_UPLOADED", "actor_role": "ROLE_CLIENT", "metadata": {"summary": "Upload"}},
            {"timestamp": "2026-06-01T11:00:00", "action": "RISK_SIGNAL_REGEN_COMPLETED", "actor_role": "system"},
        ],
        "now_iso": "2026-06-01T12:00:00+00:00",
        "branding": {"primary_color": "#0B1D3A", "company_name": "Test Co"},
    }
    pdf = build_portfolio_report("c1", data)
    assert pdf.startswith(b"%PDF")
    from pypdf import PdfReader
    import io
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages).lower()
    assert "operational evidence matrix" in text
    assert "recommended remediation actions" in text
    assert "operational activity chronology" in text
    assert "audit readiness indicators" in text
    assert "frozen deterministic snapshot" in text
    assert "point-in-time export" in text or "frozen snapshot export" in text


def test_property_pdf_long_obligation_remediation(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = {
        "client": {"company_name": "Test Co", "customer_reference": "CRN-002"},
        "properties": [{"property_id": "p1", "compliance_score": 55}],
        "requirements": [
            _req(description="Right to Rent check documentation for tenancy renewal period ending December"),
        ],
        "audit_logs": [],
        "now_iso": "2026-06-01T12:00:00+00:00",
        "branding": {"primary_color": "#0B1D3A", "company_name": "Test Co"},
    }
    pdf = build_property_report("c1", "p1", data)
    assert b"Priority 1" in pdf or b"Recommended remediation" in pdf


def test_immutable_artifact_footer_unchanged_semantics(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    from services.immutable_report_artifact_service import prepare_artifact_identity

    data = {
        "client": {"company_name": "Test Co", "customer_reference": "CRN-003"},
        "properties": [{"property_id": "p1", "compliance_score": 80}],
        "requirements": [],
        "audit_logs": [],
        "now_iso": "2026-06-01T12:00:00+00:00",
        "branding": {"primary_color": "#0B1D3A", "company_name": "Test Co"},
    }
    data["artifact_lineage"] = prepare_artifact_identity(
        client_id="c1", report_type="evidence_readiness", scope="portfolio", report_data=data
    )
    pdf = build_portfolio_report("c1", data)
    assert b"IMMUTABLE GOVERNANCE ARTIFACT" in pdf
    assert b"Artifact ID" in pdf
