"""Compliance Summary executive presentation layer tests."""
from __future__ import annotations

import io
import re
from datetime import datetime, timedelta, timezone

import pytest

from services.report_compliance_summary_executive import (
    CSV_FORMAT_VERSION,
    CSV_PROPERTY_FIELDS,
    assert_executive_safe_text,
    build_compliance_summary_executive_csv_rows,
    build_compliance_summary_executive_model,
    classify_exposure_theme,
    collect_all_executive_text,
    select_condensed_matrix_rows,
)
from services.reporting_service import ReportingService

_LEAK_PATTERN = re.compile(
    r"UNKNOWN_DATE|workflow_class|SELF_RECORDED|SATISFIED_UNVERIFIED|evidence_state",
    re.I,
)
_TRIAGE_LEAK = re.compile(
    r"immediate attention|triage at a glance|operational triage|evidence review required|monitoring only",
    re.I,
)
_SNAKE_VALUE = re.compile(r"\b[a-z]+_[a-z]{2,}\b")


def _req(**kw):
    base = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "description": "Annual gas safety inspection",
        "status": "OVERDUE",
        "due_date": "2026-07-14",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "requirement_satisfied": False,
        "missing_required_document": True,
    }
    base.update(kw)
    return base


def _props(n=1, **kw):
    return [
        {
            "property_id": f"p{i}",
            "address_line_1": f"{i} High Street",
            "postcode": f"AB{i:02d} 1CD",
            "compliance_status": kw.get("status", "AMBER"),
        }
        for i in range(1, n + 1)
    ]


def test_classify_exposure_theme_fire_safety():
    assert classify_exposure_theme(_req(requirement_type="gas_safety")) == "Fire safety"


def test_assert_executive_safe_text_rejects_backend_leak():
    with pytest.raises(ValueError, match="backend leak"):
        assert_executive_safe_text("Status UNKNOWN_DATE pending")


def test_assert_executive_safe_text_rejects_triage_wording():
    with pytest.raises(ValueError, match="triage leak"):
        assert_executive_safe_text("Immediate attention required for gas safety")


def test_condensed_matrix_caps_at_twelve():
    rows = [
        {
            "obligation": f"Obligation {i}",
            "status": "OVERDUE",
            "risk_level": "High",
            "action_required": "Yes",
            "priority": "High",
            "expiry": "2026-01-01",
            "evidence_present": "No",
        }
        for i in range(30)
    ]
    shown, omitted = select_condensed_matrix_rows(rows)
    assert len(shown) <= 12
    assert omitted == len(rows) - len(shown)
    for row in shown:
        assert "OVERDUE" not in row.get("status", "")


def test_executive_model_no_triage_leakage():
    now = datetime.now(timezone.utc)
    reqs = [
        _req(requirement_id="r1", property_id="p1"),
        _req(
            requirement_id="r2",
            property_id="p1",
            requirement_type="epc",
            status="EXPIRING_SOON",
            due_date=(now + timedelta(days=20)).isoformat(),
        ),
    ]
    props = _props(1)
    matrix = [
        {
            "obligation": "Gas safety",
            "status": "OVERDUE",
            "evidence_present": "No",
            "expiry": "2026-01-01",
            "risk_level": "High",
            "action_required": "Yes",
            "priority": "High",
        }
    ]
    readiness = {
        "evidence_completeness_pct": 65,
        "audit_readiness": "Moderate",
        "audit_confidence": "Medium",
        "unresolved_evidence_exposure": 2,
        "evidence_completeness_note": "Moderate completeness",
    }
    model = build_compliance_summary_executive_model(
        requirements=reqs,
        properties=props,
        client_doc={},
        matrix_rows=matrix,
        readiness=readiness,
        counts={
            "total_requirements": 2,
            "compliant": 0,
            "overdue": 1,
            "expiring_soon": 1,
            "missing_evidence": 1,
        },
        total_props=1,
        green=0,
        amber=1,
        red=0,
    )
    blob = "\n".join(collect_all_executive_text(model))
    assert not _LEAK_PATTERN.search(blob)
    assert not _TRIAGE_LEAK.search(blob)
    assert model["risk_concentration"]
    assert model["property_posture"]


def test_executive_csv_format_and_hygiene():
    svc = ReportingService()
    now = datetime.now(timezone.utc)
    data = {
        "report_type": "Compliance Summary",
        "generated_at": now.isoformat(),
        "client": {"name": "Test Client"},
        "summary": {
            "total_properties": 1,
            "compliance_rate": 0.0,
            "compliance_breakdown": {"green": 0, "amber": 1, "red": 0},
            "total_requirements": 1,
            "requirements_breakdown": {
                "compliant": 0,
                "pending": 0,
                "overdue": 1,
                "expiring_soon": 0,
            },
            "expiring_next_30_days": 0,
            "expiring_next_60_days": 0,
            "expiring_next_90_days": 0,
            "compliance_score_headline": {
                "compliance_score_display": "72",
                "score_authority": "persisted",
                "score_status": "ok",
                "last_calculated_at": "2026-04-01T10:00:00+00:00",
                "score_status_message": "Headline stable.",
            },
        },
        "reporting_semantics": {"counts": {}},
        "portal_requirements": [_req()],
        "properties_portal": _props(1),
        "client_doc": {},
        "properties": [
            {
                "address": "1 High Street",
                "property_type": "flat",
                "compliance_status": "AMBER",
                "total_requirements": 1,
                "compliant": 0,
                "overdue": 1,
            }
        ],
    }
    out = svc._generate_compliance_csv(data)
    text = out["content"]
    assert f"csv_format_version,{CSV_FORMAT_VERSION}" in text
    assert "=== PORTFOLIO POSTURE (EXECUTIVE VIEW) ===" in text
    assert "posture,primary_risk_area,readiness" in text.replace("\n", "")
    assert "=== PROPERTIES ===" not in text
    assert "address,property_type,compliance_status" not in text
    assert out["report_summary"] == data["summary"]
    assert out["properties_snapshot"] == data["properties"]

    body = text.split("=== PORTFOLIO POSTURE (EXECUTIVE VIEW) ===")[-1]
    assert not _LEAK_PATTERN.search(body)
    assert not _TRIAGE_LEAK.search(body)
    for line in body.split("\n")[1:]:
        if not line.strip() or line.startswith("property,"):
            continue
        for cell in line.split(","):
            if _SNAKE_VALUE.search(cell) and "not independently" not in cell.lower():
                pytest.fail(f"snake_case in CSV cell: {cell!r}")


def test_csv_rows_direct_build():
    readiness = {
        "evidence_completeness_pct": 80,
        "audit_confidence": "High",
        "unresolved_evidence_exposure": 0,
    }
    rows = build_compliance_summary_executive_csv_rows(
        properties=_props(2),
        requirements=[
            _req(property_id="p1"),
            _req(requirement_id="r2", property_id="p2", requirement_type="epc", status="COMPLIANT"),
        ],
        client_doc={},
        readiness=readiness,
    )
    assert len(rows) == 2
    assert set(rows[0].keys()) == set(CSV_PROPERTY_FIELDS)


@pytest.mark.asyncio
async def test_compliance_summary_pdf_executive_sections(monkeypatch):
    pytest.importorskip("pypdf")
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)

    from unittest.mock import AsyncMock, MagicMock, patch

    from services.professional_reports import ProfessionalReportGenerator
    from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE

    now = datetime.now(timezone.utc)
    branding_profile = MagicMock()
    branding_profile.to_report_dict.return_value = {
        "company_name": "Pleerity",
        "primary_color": "#0B1D3A",
        "secondary_color": "#00B8A9",
        "text_color": "#1F2937",
        "report_header_text": "",
        "report_footer_text": "",
        "pdf_attribution_lines": [],
        "pdf_footer_contact_line": "",
    }
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "full_name": "Client"})
    db.properties.find = MagicMock(
        return_value=MagicMock(
            to_list=AsyncMock(
                return_value=[
                    {
                        "property_id": "p1",
                        "client_id": "c1",
                        "address_line_1": "1 Test Road",
                        "postcode": "AB1 2CD",
                        "compliance_status": "AMBER",
                    }
                ]
            )
        )
    )
    portal_rows = [
        {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_type": "gas_safety",
            "description": "Gas safety",
            "status": "OVERDUE",
            "due_date": (now - timedelta(days=5)).isoformat(),
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        }
    ]
    db.requirements.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=portal_rows))
    )

    async def fake_calculate_compliance_score(_client_id: str):
        return {
            "score": 72,
            "score_status": "ok",
            "score_authority": "persisted",
            "last_calculated_at": "2026-03-01T10:00:00+00:00",
            "score_status_message": "Persisted headline note.",
            "score_coverage": {},
        }

    gen = ProfessionalReportGenerator()
    with patch("services.professional_reports.database.get_db", return_value=db), patch(
        "services.branding_resolver_service.resolve_branding",
        new_callable=AsyncMock,
        return_value=branding_profile,
    ), patch(
        "services.reporting_semantics_v1.load_score_projection_portal_rows",
        new_callable=AsyncMock,
        return_value=portal_rows,
    ), patch(
        "services.compliance_score.calculate_compliance_score",
        new_callable=AsyncMock,
        side_effect=fake_calculate_compliance_score,
    ):
        pdf = await gen.generate_compliance_summary_pdf("c1")

    from pypdf import PdfReader

    text = "".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf.getvalue())).pages)
    low = text.lower()
    assert "portfolio posture interpretation" in low
    assert "property posture overview" in low
    assert "recommended priorities" in low
    assert "evidence summary" in low
    assert "evidence matrix" not in low
    assert "requirements overview" not in low
    assert "property compliance status" not in low
    assert not _TRIAGE_LEAK.search(text)
    assert not _LEAK_PATTERN.search(text)
    assert "portfolio compliance score" in low
    assert "72" in text or "score status" in low
