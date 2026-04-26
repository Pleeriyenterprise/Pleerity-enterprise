"""Monthly digest snapshot comparison and reporting period helpers."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.monthly_digest_assembly_service import reporting_period_for_previous_calendar_month
from services.monthly_digest_assembly_service import _missing_evidence
from services.monthly_digest_snapshot_service import build_fingerprint_map, compute_deltas, requirement_fingerprint
from services.jobs import effective_digest_calendar_day
from services.monthly_digest_pdf_service import build_monthly_digest_pdf_bytes


def test_reporting_period_previous_month():
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    start, end, key, label = reporting_period_for_previous_calendar_month(now)
    assert key == "2026-03"
    assert label == "March 2026"
    assert start.month == 3 and end.month == 3


def test_requirement_fingerprint_stable():
    r = {
        "requirement_id": "r1",
        "status": "COMPLIANT",
        "evidence_state": "VERIFIED",
        "due_date": "2026-12-01T00:00:00+00:00",
    }
    fp = requirement_fingerprint(r)
    assert "r1" in fp
    assert "COMPLIANT" in fp


def test_compute_deltas_first_report():
    reqs = [
        {"requirement_id": "a", "status": "OVERDUE", "evidence_state": "VERIFIED", "due_date": "2020-01-01"},
    ]
    fps = build_fingerprint_map(reqs)
    d = compute_deltas(None, fps, reqs, current_score=50, current_missing_evidence=1, documents_uploaded_period=2)
    assert d["has_prior_snapshot"] is False
    assert d["score_delta"] is None


def test_effective_digest_calendar_day_end_of_month():
    """Preference 31 maps to last day of month (April → 30, Feb 2025 → 28)."""
    april = datetime(2026, 4, 15, tzinfo=timezone.utc)
    assert effective_digest_calendar_day(31, april) == 30
    assert effective_digest_calendar_day(30, april) == 30
    feb = datetime(2025, 2, 10, tzinfo=timezone.utc)
    assert effective_digest_calendar_day(31, feb) == 28
    feb_leap = datetime(2024, 2, 10, tzinfo=timezone.utc)
    assert effective_digest_calendar_day(31, feb_leap) == 29
    assert effective_digest_calendar_day(5, april) == 5


def test_pdf_reflects_white_label_company_on_cover(monkeypatch):
    """Scenario E: PDF letterhead uses resolved brand company name (not Pleerity) when provided."""
    # ReportLab compresses page streams by default; contiguous text is not searchable in raw bytes.
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    brand = MagicMock()
    brand.company_name = "Acme Portfolio Group Ltd"
    brand.tagline = "Your compliance partner"
    brand.primary_color = "#112233"
    brand.logo_path = None
    brand.include_pleerity_attribution = False
    brand.powered_by_text = ""

    model = {
        "reporting_month_label": "March 2026",
        "generated_at_display": "01 April 2026 10:00 UTC",
        "account_name": "Test User",
        "properties_count": 1,
        "compliance_score": 80,
        "risk_level": "Low Risk",
        "total_requirements": 3,
        "valid_count": 2,
        "compliant": 2,
        "expiring_soon": 0,
        "overdue": 0,
        "missing_evidence_count": 0,
        "open_compliance_jobs": 0,
        "open_maintenance_jobs": 0,
        "deltas": {"has_prior_snapshot": False},
        "include_compliance_summary": True,
        "include_action_items": True,
        "include_upcoming_expiries": True,
        "include_recent_documents": True,
        "include_recommendations": True,
        "include_audit_summary": False,
        "property_rows_pdf": [],
        "requirement_rows_pdf": [],
        "top_risk_drivers": [],
        "top_next_actions": [],
    }
    pdf = build_monthly_digest_pdf_bytes(model, brand=brand)
    assert pdf.startswith(b"%PDF")
    assert b"Acme Portfolio" in pdf


def test_pdf_omits_property_section_when_preference_off(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    brand = MagicMock()
    brand.company_name = "Co"
    brand.tagline = "T"
    brand.primary_color = "#0B1D3A"
    brand.logo_path = None
    brand.include_pleerity_attribution = False
    brand.powered_by_text = ""
    model = {
        "reporting_month_label": "March 2026",
        "generated_at_display": "01 April 2026",
        "account_name": "A",
        "properties_count": 2,
        "compliance_score": 80,
        "risk_level": "Low Risk",
        "total_requirements": 1,
        "valid_count": 1,
        "compliant": 1,
        "expiring_soon": 0,
        "overdue": 0,
        "missing_evidence_count": 0,
        "open_compliance_jobs": 0,
        "open_maintenance_jobs": 0,
        "deltas": {"has_prior_snapshot": False},
        "include_compliance_summary": True,
        "include_action_items": False,
        "include_upcoming_expiries": True,
        "include_recent_documents": True,
        "include_recommendations": False,
        "include_audit_summary": False,
        "include_property_breakdown": False,
        "property_rows_pdf": [{"name": "X", "score": 80, "risk_level": "Low", "overdue_count": 0, "expiring_soon_count": 0, "missing_evidence_count": 0, "open_jobs_count": 0}],
        "requirement_rows_pdf": [],
        "top_risk_drivers": [],
        "top_next_actions": [],
    }
    pdf = build_monthly_digest_pdf_bytes(model, brand=brand)
    assert b"4. Requirement breakdown" in pdf
    assert b"4. Property summary" not in pdf


def test_compute_deltas_newly_overdue():
    prev_req = {
        "requirement_id": "x",
        "status": "COMPLIANT",
        "evidence_state": "VERIFIED",
        "due_date": "2026-06-01T00:00:00+00:00",
    }
    prev_fp = requirement_fingerprint(prev_req)
    prev = {
        "compliance_score": 80,
        "requirement_fingerprints": {
            "x": prev_fp,
        },
        "missing_evidence_count": 0,
        "documents_uploaded_in_report_period": 1,
    }
    reqs = [
        {"requirement_id": "x", "status": "OVERDUE", "evidence_state": "VERIFIED", "due_date": "2020-01-01"},
    ]
    fps = build_fingerprint_map(reqs)
    d = compute_deltas(prev, fps, reqs, current_score=70, current_missing_evidence=0, documents_uploaded_period=3)
    assert d["has_prior_snapshot"] is True
    assert d["score_delta"] == -10
    assert "x" in d["newly_overdue_ids"]
    assert d["documents_uploaded_delta_vs_prev_period"] == 2


def test_missing_evidence_uses_projected_status_not_raw_evidence_state():
    assert _missing_evidence({"status": "PENDING", "applicability": "REQUIRED"}) is True
    assert _missing_evidence({"status": "MISSING", "applicability": "REQUIRED"}) is True
    assert _missing_evidence({"status": "COMPLIANT", "evidence_state": "MISSING", "applicability": "REQUIRED"}) is False
