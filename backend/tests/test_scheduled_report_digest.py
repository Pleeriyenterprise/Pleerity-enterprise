"""Unit tests: scheduled compliance report email digest (no raw dump in body)."""

from models import EmailTemplateAlias
from services.email_service import EmailService


def _svc():
    return EmailService()


def test_scheduled_report_digest_summary_path_no_raw_dump():
    model = {
        "frequency": "daily",
        "report_type": "Compliance summary",
        "generated_date": "1 April 2026",
        "portal_link": "https://app.example/today",
        "report_summary": {
            "total_properties": 2,
            "compliance_rate": 85,
            "compliance_breakdown": {"green": 1, "amber": 1, "red": 0},
            "requirements_breakdown": {
                "compliant": 5,
                "overdue": 1,
                "expiring_soon": 0,
                "pending": 0,
            },
        },
        "properties_snapshot": [
            {"address": "1 Test Street", "compliance_status": "RED", "overdue": 2},
        ],
        "report_rows": [],
        "client_name": "Alex",
    }
    html = _svc()._build_html_body(EmailTemplateAlias.SCHEDULED_REPORT, model)
    assert "=== SUMMARY" not in html
    assert "white-space: pre-wrap" not in html
    assert "Open your portal" in html
    assert "PORTFOLIO SNAPSHOT" in html


def test_scheduled_report_digest_rows_path_top_actions():
    model = {
        "frequency": "weekly",
        "report_type": "Requirements",
        "generated_date": "Monday 31 March 2026",
        "portal_link": "https://app.example/today",
        "report_rows": [
            {
                "property_address": "10 High St",
                "requirement_code": "GAS_SAFETY",
                "status": "OVERDUE",
                "due_date": "2026-03-01",
            },
        ],
        "client_name": "Sam",
    }
    html = _svc()._build_html_body(EmailTemplateAlias.SCHEDULED_REPORT, model)
    assert "REQUIREMENTS OVERVIEW" in html
    text = _svc()._build_text_body(EmailTemplateAlias.SCHEDULED_REPORT, model)
    assert "https://app.example/today" in text
    assert "=== SUMMARY" not in text


def test_scheduled_report_digest_operational_email_rows():
    """Requirements operational model rows via build_requirements_scheduled_email_rows."""
    from datetime import datetime, timezone

    from services.report_requirements_operational import (
        build_requirements_operational_csv_rows,
        build_requirements_scheduled_email_rows,
    )

    req = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "description": "Gas safety inspection",
        "status": "OVERDUE",
        "due_date": "2026-03-01",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "requirement_satisfied": False,
        "missing_required_document": True,
        "document_upload_required": True,
        "requirement_attention_eligible": True,
        "requirement_attention_reason": "collect_evidence",
    }
    props = [{"property_id": "p1", "address_line_1": "10 High St", "postcode": "AB1 2CD"}]
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    _, _, enriched = build_requirements_operational_csv_rows(
        requirements=[req],
        properties=props,
        client_doc={},
        now=now,
    )
    email_rows = build_requirements_scheduled_email_rows(enriched)
    model = {
        "frequency": "weekly",
        "report_type": "Requirements",
        "generated_date": "Monday 31 March 2026",
        "portal_link": "https://app.example/today",
        "report_rows": email_rows,
        "client_name": "Sam",
    }
    html = _svc()._build_html_body(EmailTemplateAlias.SCHEDULED_REPORT, model)
    assert "REQUIREMENTS OVERVIEW" in html
    assert "Overdue" in html or "overdue" in html.lower()
    assert "Gas safety" in html or "gas" in html.lower()


def test_scheduled_report_digest_fallback_when_no_structured_data():
    model = {
        "frequency": "monthly",
        "report_type": "Compliance",
        "generated_date": "today",
        "portal_link": "https://app.example/today",
        "report_rows": [],
        "client_name": "Jo",
    }
    html = _svc()._build_html_body(EmailTemplateAlias.SCHEDULED_REPORT, model)
    assert "Summary unavailable" in html or "summary unavailable" in html.lower()
