"""Enterprise report PDF template layer tests."""
from __future__ import annotations

from datetime import datetime, timezone

from services.report_layout_governance import (
    GovernancePdfContext,
    formal_report_table_width,
    proportional_col_widths,
)
from services.report_pdf_templates import (
    FROZEN_SNAPSHOT_WORDING,
    append_readiness_indicators_section,
    build_formal_report_pdf,
    build_matrix_rows,
    compute_readiness_indicators,
    create_enterprise_styles,
    create_enterprise_table_style,
    FormalReportSpec,
    group_by_action_priority,
)
from services.reporting_semantics_v1 import EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT, GRADE_REGULATORY


def _gov_ctx() -> GovernancePdfContext:
    return GovernancePdfContext(
        export_grade=GRADE_REGULATORY,
        export_grade_label="Regulatory / evidential",
        generated_at=datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc),
        determinism=EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
        jurisdiction_summary="England",
        artifact_id="exp_test123",
        report_scope="property",
        immutable_status="frozen",
    )


def _sample_req(**overrides):
    base = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "description": "Gas Safety Certificate",
        "status": "OVERDUE",
        "mandatory": True,
        "due_date": "2026-07-01",
    }
    base.update(overrides)
    return base


def test_frozen_snapshot_wording_constant():
    assert "frozen deterministic snapshot" in FROZEN_SNAPSHOT_WORDING.lower()


def test_build_matrix_rows_includes_evidence_and_risk_columns():
    rows = build_matrix_rows(
        requirements=[_sample_req()],
        properties=[{"property_id": "p1", "address_line_1": "1 Test St"}],
        client_doc={},
        docs_by_req={"r1": [{"file_name": "gas.pdf", "requirement_id": "r1"}]},
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0]["evidence_ref"] == "gas.pdf"
    assert rows[0]["risk_level"] in ("High", "Critical", "Medium")
    assert rows[0]["action_required"] in ("Yes", "Review")


def test_compute_readiness_indicators():
    ind = compute_readiness_indicators(
        requirements=[_sample_req(), _sample_req(requirement_id="r2", status="COMPLIANT", mandatory=False)],
        properties=[{"property_id": "p1"}],
        client_doc={},
    )
    assert ind["total_obligations"] == 2
    assert "audit_readiness" in ind
    assert ind["total_obligations"] >= 2
    assert "evidence_completeness_pct" in ind


def test_formal_report_pdf_contains_cover_matrix_and_snapshot_wording():
    matrix_rows = build_matrix_rows(
        requirements=[_sample_req()],
        properties=[{"property_id": "p1"}],
        client_doc={},
    )
    spec = FormalReportSpec(
        report_title="Compliance Summary",
        report_classification="Compliance Summary",
        report_kind="compliance_summary",
        branding={"primary_color": "#0B1D3A", "accent_color": "#00B8A9", "company_name": "Test Co"},
        gov_ctx=_gov_ctx(),
        generated_at_iso="2026-06-09T12:00:00+00:00",
        jurisdiction="England",
        export_id="exp_abc",
        export_generation_id="cap_xyz",
    )
    pdf = build_formal_report_pdf(
        spec,
        posture_lines=["Overall compliance posture: action required."],
        metrics=[("Total obligations", "1")],
        interpretation=["Test interpretation."],
        matrix_rows=matrix_rows,
        readiness=compute_readiness_indicators(
            requirements=[_sample_req()],
            properties=[{"property_id": "p1"}],
            client_doc={},
        ),
        action_groups=group_by_action_priority(matrix_rows),
        exceptions={"missing_evidence": ["Gas Safety Certificate"], "unverifiable_evidence": [], "expired_evidence": [], "conflicting_records": [], "missing_delivery_proof": [], "unresolved_obligations": ["Gas Safety Certificate"]},
        scope_lines=["Test scope line."],
    )
    assert pdf[:4] == b"%PDF"
    text = pdf.decode("latin-1", errors="ignore")
    assert "Evidence matrix" in text or "Evidence" in text
    assert "frozen deterministic snapshot" in text.lower() or "deterministic snapshot" in text.lower()
    assert "Executive summary" in text or "Executive" in text
    assert "Intended use" in text or "intended" in text.lower()
    assert "REGULATORY_SUBMISSION" not in text
    assert "Regulatory submission" in text or "Regulatory / evidential" in text
    assert "generation timestamp boundary." in text.lower()


def test_evidence_matrix_seven_column_portrait_width():
    width = formal_report_table_width()
    cols = proportional_col_widths(width, [0.28, 0.11, 0.13, 0.09, 0.13, 0.10, 0.16])
    assert len(cols) == 7
    assert abs(sum(cols) - width) < 0.5


def test_readiness_table_uses_paragraph_cells_no_overlap_fields():
    styles = create_enterprise_styles({})
    table_style = create_enterprise_table_style(styles)
    elements = []
    append_readiness_indicators_section(
        elements,
        indicators=compute_readiness_indicators(
            requirements=[_sample_req()],
            properties=[{"property_id": "p1"}],
            client_doc={},
        ),
        styles=styles,
        table_style=table_style,
        table_width=formal_report_table_width(),
    )
    from reportlab.platypus import Table

    table = next(item for item in elements if isinstance(item, Table))
    assert len(table._cellvalues[0]) == 3
    assert all(hasattr(cell, "text") for row in table._cellvalues for cell in row)


def test_formal_pdf_audit_trail_humanises_event_codes():
    spec = FormalReportSpec(
        report_title="Audit Evidence Pack",
        report_classification="Audit Evidence Pack",
        report_kind="audit_evidence_pack",
        branding={"primary_color": "#0B1D3A"},
        gov_ctx=_gov_ctx(),
        generated_at_iso="2026-06-09T12:00:00+00:00",
        include_matrix=False,
        include_executive_summary=False,
        include_readiness_indicators=False,
        include_action_priorities=False,
        include_exception_summaries=False,
        include_audit_trail=True,
        include_intended_use=False,
        include_scope_limitations=False,
    )
    pdf = build_formal_report_pdf(
        spec,
        audit_events=[
            {
                "timestamp": "2026-05-01T10:00:00+00:00",
                "action": "COMPLIANCE_RECALC_SLA_BREACH",
                "actor_role": "system",
                "metadata": {"summary": "SLA breach during recalculation"},
            }
        ],
    )
    text = pdf.decode("latin-1", errors="ignore")
    assert "COMPLIANCE_RECALC_SLA_BREACH" not in text
    assert "Compliance recalculation exceeded SLA threshold" in text or "SLA breach" in text
