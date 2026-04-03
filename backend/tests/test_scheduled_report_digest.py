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
