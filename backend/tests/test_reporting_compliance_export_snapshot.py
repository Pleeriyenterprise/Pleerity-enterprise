"""Compliance summary CSV: snapshot honesty rows (Stream B export slice)."""

from services.reporting_service import ReportingService


def test_compliance_summary_csv_includes_score_status_message_and_export_note():
    svc = ReportingService()
    data = {
        "report_type": "Compliance Summary",
        "generated_at": "2026-04-30T12:00:00+00:00",
        "client": {"name": "Test Client"},
        "summary": {
            "total_properties": 1,
            "compliance_rate": 100.0,
            "compliance_breakdown": {"green": 1, "amber": 0, "red": 0},
            "total_requirements": 0,
            "requirements_breakdown": {
                "compliant": 0,
                "pending": 0,
                "overdue": 0,
                "expiring_soon": 0,
            },
            "expiring_next_30_days": 0,
            "expiring_next_60_days": 0,
            "expiring_next_90_days": 0,
            "compliance_score_headline": {
                "compliance_score_display": "72",
                "score_authority": "persisted",
                "score_status": "stale",
                "last_calculated_at": "2026-04-01T10:00:00+00:00",
                "score_status_message": "Background recalculation queued.",
            },
        },
    }
    out = svc._generate_compliance_csv(data)
    text = out["content"]
    assert "score_status_message,Background recalculation queued." in text
    assert "export_snapshot_note," in text
    assert "last_calculated_at" in text
    assert "score_status,stale" in text
    assert "csv_format_version,compliance_summary_executive_v1" in text
