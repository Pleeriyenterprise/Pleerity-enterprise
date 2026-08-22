"""Property Activity & Evidence Report — organisational pack, not legal certification."""
from services.property_activity_evidence_service import (
    DISCLAIMER,
    REPORT_TITLE,
    render_property_activity_evidence_html,
)


def test_html_report_is_human_readable_and_not_legal_certification():
    html = render_property_activity_evidence_html(
        {
            "report_title": REPORT_TITLE,
            "disclaimer": DISCLAIMER,
            "generated_at": "2026-08-20T09:00:00+00:00",
            "date_range": {"from": "2026-08-01", "to": "2026-08-20"},
            "property": {"name": "Oak City", "address_line_1": "1 High St", "postcode": "EN10 6AF"},
            "account": {"account_reference": "PLE-CVP-2026-000038"},
            "tenancies": [{"tenant_display_name": "Occupancy tenancy", "status": "active", "started_at": "2026-08-01"}],
            "compliance": [{"name": "Gas Safety Certificate", "status": "OVERDUE", "due_date": "2026-08-10"}],
            "maintenance": [
                {
                    "description": "Leak under bathroom sink",
                    "category": "plumbing",
                    "status": "ASSIGNED",
                    "contractor_name": "Hartley Plumbing Ltd",
                }
            ],
            "rent": {"payments": [{"payment_date": "2026-08-05", "amount_minor": 50000}]},
            "chronology": [
                {
                    "timestamp": "2026-08-18T10:42:00+00:00",
                    "headline": "Contractor assigned",
                    "summary": "Hartley Plumbing Ltd was assigned to “Bathroom sink leak” at Oak City.",
                }
            ],
        }
    )
    assert "Property Activity &amp; Evidence Report" in html
    assert "does not determine legal sufficiency" in html.lower()
    assert "tribunal-approved" not in html.lower()
    assert "Oak City" in html
    assert "Hartley Plumbing Ltd" in html
    assert "Leak under bathroom sink" in html
    assert "<script>" not in html
