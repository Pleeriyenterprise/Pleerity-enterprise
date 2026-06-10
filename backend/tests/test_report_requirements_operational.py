"""Requirements Report operational triage presentation tests."""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone

import pytest

from services.pdf_report_builder import build_portfolio_report, build_requirements_report_pdf
from services.report_human_language_v1 import human_operational_renewal_date
from services.report_requirements_operational import (
    CSV_FIELDNAMES,
    CSV_FORBIDDEN_COLUMNS,
    TRIAGE_IMMEDIATE,
    TRIAGE_RECORDED,
    TRIAGE_RENEWALS,
    assert_client_safe_text,
    build_cluster_summaries,
    build_requirements_operational_csv_rows,
    build_requirements_operational_model,
    classify_issue_cluster,
    classify_operational_triage_bucket,
    collect_all_client_text,
)
from services.reporting_service import ReportingService

_LEAK_PATTERN = re.compile(
    r"UNKNOWN_DATE|workflow_class|SELF_RECORDED|SATISFIED_UNVERIFIED|evidence_state",
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
        "document_upload_required": True,
        "requirement_attention_eligible": True,
        "requirement_attention_reason": "collect_evidence",
    }
    base.update(kw)
    return base


def _self_recorded(**kw):
    defaults = {
        "requirement_id": "sr1",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "assurance_tier": "SELF_RECORDED",
        "requirement_satisfied": True,
        "missing_required_document": False,
        "document_upload_required": False,
        "requirement_attention_eligible": False,
        "truth_presentation_stage": "declaration_recorded",
        "status": "COMPLIANT",
    }
    defaults.update(kw)
    return _req(**defaults)


def _props(n=1):
    return [
        {
            "property_id": f"p{i}",
            "address_line_1": f"{i} High Street",
            "postcode": f"AB{i:02d} 1CD",
        }
        for i in range(1, n + 1)
    ]


def test_human_renewal_date_no_unknown_date():
    assert human_operational_renewal_date({"due_date": "UNKNOWN_DATE"}) == (
        "No verified renewal date recorded"
    )
    assert human_operational_renewal_date({}) == "No verified renewal date recorded"
    assert human_operational_renewal_date({"due_date": "2026-12-01"}) == "2026-12-01"


def test_classify_triage_buckets():
    assert (
        classify_operational_triage_bucket(_req(), property_doc=None, client_doc={})
        == TRIAGE_IMMEDIATE
    )
    assert (
        classify_operational_triage_bucket(
            _self_recorded(), property_doc=None, client_doc={}
        )
        == TRIAGE_RECORDED
    )
    assert (
        classify_operational_triage_bucket(
            _req(
                requirement_id="r2",
                status="EXPIRING_SOON",
                client_lifecycle_state="VERIFIED",
                requirement_satisfied=True,
                missing_required_document=False,
                requirement_attention_eligible=False,
                assurance_tier="VERIFIED_DOCUMENT",
            ),
            property_doc=None,
            client_doc={},
        )
        == TRIAGE_RENEWALS
    )


def test_issue_clustering():
    assert classify_issue_cluster(_req()) == "Fire safety"
    assert classify_issue_cluster(
        _req(requirement_type="selective_licence", description="Selective licence application")
    ) == "Licensing"
    assert classify_issue_cluster(
        _req(requirement_type="tenancy_deposit", description="Tenancy deposit protection")
    ) == "Tenancy documentation"


def test_cluster_summaries_grouped_not_spam():
    rows = [
        {
            "cluster": "Fire safety",
            "property": "1 High St",
            "obligation": "Gas safety",
            "triage_bucket": TRIAGE_IMMEDIATE,
        },
        {
            "cluster": "Fire safety",
            "property": "2 High St",
            "obligation": "Fire risk assessment",
            "triage_bucket": TRIAGE_IMMEDIATE,
        },
    ]
    summaries = build_cluster_summaries(rows, bucket=TRIAGE_IMMEDIATE)
    assert len(summaries) == 1
    assert "2 fire safety" in summaries[0].lower()
    assert summaries[0].lower().count("upload") == 0


def test_property_triage_summaries():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    model = build_requirements_operational_model(
        requirements=[_req(), _self_recorded(requirement_id="sr2")],
        properties=_props(1),
        client_doc={},
        now=now,
    )
    ps = model["property_summaries"]
    assert len(ps) == 1
    assert ps[0]["immediate"] >= 1
    assert ps[0]["recorded_unverified"] >= 1
    assert ps[0]["priority"] in ("High priority", "Elevated", "Stable", "Review suggested")


def test_no_backend_semantic_leakage_in_model():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    model = build_requirements_operational_model(
        requirements=[
            _req(due_date="UNKNOWN_DATE"),
            _self_recorded(),
            _req(
                requirement_id="r3",
                client_lifecycle_state="PENDING_REVIEW",
                truth_presentation_stage="platform_verification_pending",
                requirement_attention_eligible=True,
                requirement_attention_reason="platform_verification_pending",
            ),
        ],
        properties=_props(1),
        client_doc={},
        now=now,
    )
    for text in collect_all_client_text(model):
        assert not _LEAK_PATTERN.search(text), f"leak in: {text!r}"
        assert_client_safe_text(text)


def test_csv_hygiene():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows, counts, _enriched = build_requirements_operational_csv_rows(
        requirements=[_req(), _self_recorded(requirement_id="sr1")],
        properties=_props(1),
        client_doc={},
        now=now,
    )
    assert sum(counts.values()) == 2
    for row in rows:
        assert set(row.keys()) == set(CSV_FIELDNAMES)
        for col in CSV_FORBIDDEN_COLUMNS:
            assert col not in row
        for val in row.values():
            assert not _LEAK_PATTERN.search(str(val))
            if isinstance(val, str) and _SNAKE_VALUE.search(val):
                pytest.fail(f"snake_case in CSV value: {val!r}")


def test_scheduled_email_rows_legacy_keys_from_operational():
    from services.report_requirements_operational import build_requirements_scheduled_email_rows

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    _, _, enriched = build_requirements_operational_csv_rows(
        requirements=[_req(), _self_recorded(requirement_id="sr1")],
        properties=_props(1),
        client_doc={},
        now=now,
    )
    email_rows = build_requirements_scheduled_email_rows(enriched)
    assert email_rows[0]["status"] == "OVERDUE"
    assert email_rows[0]["description"]
    assert email_rows[0]["due_date"]
    assert email_rows[1]["status"] == "COMPLIANT"


def test_reporting_service_csv_operational_columns():
    svc = ReportingService()
    data = {
        "report_type": "Requirements Report",
        "generated_at": "2026-06-01T12:00:00+00:00",
        "reporting_semantics": {"counts": {}},
        "portal_requirements": [_req(), _self_recorded(requirement_id="sr1")],
        "properties_portal": _props(1),
        "requirements": [],
    }
    out = svc._generate_requirements_csv(data)
    content = out["content"]
    assert "=== TRIAGE SUMMARY ===" in content
    assert "triage_category" in content
    assert "csv_format_version,requirements_operational_v1" in content
    assert "evidence_state" not in content.split("=== OBLIGATIONS")[1]
    assert "UNKNOWN_DATE" not in content
    assert out["rows"][0].get("status") in ("OVERDUE", "PENDING", "EXPIRING_SOON", "COMPLIANT")


def test_requirements_pdf_operational_sections(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = {
        "client": {"company_name": "Test Co", "customer_reference": "CRN-1"},
        "properties": _props(2),
        "requirements": [
            _req(property_id="p1"),
            _req(requirement_id="r2", property_id="p2", description="Fire alarm test"),
            _self_recorded(requirement_id="sr1", property_id="p1"),
        ],
        "now_iso": "2026-06-01T12:00:00+00:00",
        "branding": {"primary_color": "#0B1D3A", "secondary_color": "#00B8A9", "company_name": "Test Co"},
    }
    pdf = build_requirements_report_pdf("c1", data)
    text = pdf.decode("latin-1", errors="ignore").lower()
    assert pdf[:4] == b"%PDF"
    assert "triage at a glance" in text
    assert "immediate attention" in text
    assert "property operational summaries" in text
    assert "property detail" not in text or "requirement matrix" not in text
    assert "unresolved obligations" not in text
    assert "unknown_date" not in text


def test_sparse_portfolio_pdf_no_orphan_headers(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = {
        "client": {"company_name": "Sparse Co", "customer_reference": "CRN-S"},
        "properties": _props(1),
        "requirements": [_self_recorded()],
        "now_iso": "2026-06-01T12:00:00+00:00",
        "branding": {"primary_color": "#0B1D3A", "secondary_color": "#00B8A9"},
    }
    pdf = build_requirements_report_pdf("c-sparse", data)
    text = pdf.decode("latin-1", errors="ignore")
    assert "Recorded but not independently verified" in text
    assert text.count("Immediate attention") >= 1


def test_large_portfolio_pagination_stable(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    n_props = 8
    reqs = []
    for i in range(1, n_props + 1):
        for j in range(5):
            reqs.append(
                _req(
                    requirement_id=f"r{i}_{j}",
                    property_id=f"p{i}",
                    description=f"Obligation {i}-{j}",
                )
            )
    data = {
        "client": {"company_name": "Large Co", "customer_reference": "CRN-L"},
        "properties": _props(n_props),
        "requirements": reqs,
        "now_iso": "2026-06-01T12:00:00+00:00",
        "branding": {"primary_color": "#0B1D3A", "secondary_color": "#00B8A9"},
    }
    pdf = build_requirements_report_pdf("c-large", data)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 5000
    text = pdf.decode("latin-1", errors="ignore").lower()
    assert "triage at a glance" in text
    assert "immediate attention" in text


def test_evidence_readiness_unchanged_report_class_isolation(monkeypatch):
    """Requirements convergence must not alter Evidence Readiness PDF."""
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = {
        "client": {"company_name": "Iso Co", "customer_reference": "CRN-I"},
        "properties": [{"property_id": "p1", "address_line_1": "1 St", "compliance_score": 70}],
        "requirements": [
            {
                "property_id": "p1",
                "client_lifecycle_state": "ACTION_REQUIRED",
                "description": "EPC",
                "due_date": "2026-12-01",
            }
        ],
        "audit_logs": [],
        "now_iso": "2026-06-01T12:00:00+00:00",
        "branding": {"primary_color": "#0B1D3A", "secondary_color": "#00B8A9"},
    }
    pdf = build_portfolio_report("c1", data)
    assert b"Unresolved obligations" in pdf
    assert b"Export grade" in pdf
