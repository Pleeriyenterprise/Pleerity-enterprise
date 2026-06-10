"""Monthly digest snapshot comparison and reporting period helpers."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.monthly_digest_assembly_service import reporting_period_for_previous_calendar_month
from services.monthly_digest_assembly_service import _missing_evidence
from services.monthly_digest_assembly_service import digest_pr5_override_observability
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
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    pdf = build_monthly_digest_pdf_bytes(model, brand=brand)
    assert pdf.startswith(b"%PDF")
    assert b"Acme Portfolio Group Ltd" in pdf


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
    assert b"Property movement summary" not in pdf
    assert b"Executive snapshot" in pdf


def test_compute_deltas_newly_overdue():
    prev = {
        "compliance_score": 80,
        "requirement_fingerprints": {
            "x": "x|COMPLIANT|VERIFIED|2026-06-01T00:00:00+00:00",
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


def test_pdf_includes_hiua_payload_lines_when_present(monkeypatch):
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
        "properties_count": 1,
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
        "include_action_items": True,
        "include_upcoming_expiries": True,
        "include_recent_documents": True,
        "include_recommendations": True,
        "include_audit_summary": False,
        "property_rows_pdf": [],
        "requirement_rows_pdf": [],
        "top_risk_drivers": [],
        "top_next_actions": [],
        "digest_hiua_line": "HIUA_UNIQUE_DIGEST_LINE_XYZ",
        "digest_hiua_report_framing_notice": "HIUA_UNIQUE_FRAME_NOTICE_ABC",
    }
    pdf = build_monthly_digest_pdf_bytes(model, brand=brand)
    assert b"HIUA_UNIQUE_DIGEST_LINE_XYZ" in pdf
    assert b"HIUA_UNIQUE_FRAME_NOTICE_ABC" in pdf


def test_digest_pr5_override_observability_policy_path():
    sb = {
        "effective_override_output": {
            "override_output_source": "policy",
            "fallback_applied": False,
            "fallback_reason_codes": [],
            "effective_portfolio_risk_state": "Critical Risk",
        }
    }
    o = digest_pr5_override_observability(sb)
    assert o["override_output_source"] == "policy"
    assert o["fallback_applied"] is False
    assert o["fallback_reason_codes"] == []


def test_digest_pr5_override_observability_legacy_fallback():
    sb = {
        "effective_override_output": {
            "override_output_source": "legacy_fallback",
            "fallback_applied": True,
            "fallback_reason_codes": ["POLICY_FIELDS_INCOMPLETE", "RECONCILIATION_IN_PROGRESS"],
        }
    }
    o = digest_pr5_override_observability(sb)
    assert o["override_output_source"] == "legacy_fallback"
    assert o["fallback_applied"] is True
    assert o["fallback_reason_codes"] == ["POLICY_FIELDS_INCOMPLETE", "RECONCILIATION_IN_PROGRESS"]


def test_digest_pr5_override_observability_missing_effective_defaults():
    assert digest_pr5_override_observability({}) == {
        "override_output_source": None,
        "fallback_applied": False,
        "fallback_reason_codes": [],
    }


def test_digest_payload_merge_includes_pr5_keys_like_assemble():
    """Same merge as ``assemble_monthly_digest_payload`` after building ``score_block``."""
    score_block = {
        "effective_override_output": {
            "override_output_source": "policy",
            "fallback_applied": False,
            "fallback_reason_codes": [],
        }
    }
    merged = {"compliance_score": 18, **digest_pr5_override_observability(score_block)}
    assert merged["compliance_score"] == 18
    assert merged["override_output_source"] == "policy"
    assert merged["fallback_applied"] is False
    assert merged["fallback_reason_codes"] == []


def test_digest_pr5_observability_with_pr5_env_allowlist(monkeypatch):
    """PR5 allowlist env on; digest observability still mirrors score_block only (no logic change)."""
    monkeypatch.setenv("FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE", "true")
    monkeypatch.setenv(
        "FEATURE_POLICY_BACKED_PORTFOLIO_OVERRIDE_TENANT_ALLOWLIST",
        "04ceda9f-dd72-4b70-a6f5-809bef1b7b6a",
    )
    from services.portfolio_risk_override_flag import is_feature_policy_backed_portfolio_override_enabled

    assert is_feature_policy_backed_portfolio_override_enabled("04ceda9f-dd72-4b70-a6f5-809bef1b7b6a") is True
    sb = {
        "effective_override_output": {
            "override_output_source": "policy",
            "fallback_applied": False,
            "fallback_reason_codes": [],
        }
    }
    o = digest_pr5_override_observability(sb)
    assert o["override_output_source"] == "policy"
    assert "fallback_applied" in o and "fallback_reason_codes" in o


def test_monthly_digest_plain_text_includes_hiua_payload():
    from models.core import EmailTemplateAlias
    from services.email_service import EmailService

    svc = EmailService()
    txt = svc._build_text_body(
        EmailTemplateAlias.MONTHLY_DIGEST,
        {
            "reporting_month_label": "March 2026",
            "account_name": "Test",
            "client_name": "Test",
            "properties_count": 1,
            "digest_snapshot_framing_line": "Snapshot as of 01 April 2026 10:00 UTC",
            "compliance_score": 80,
            "score_status": "ok",
            "last_calculated_at": "2026-04-01",
            "portfolio_last_calculated_at": None,
            "risk_level": "Low Risk",
            "total_requirements": 1,
            "valid_count": 1,
            "compliant": 1,
            "expiring_soon": 0,
            "overdue": 0,
            "missing_evidence_count": 0,
            "deltas": {"has_prior_snapshot": False},
            "urgent_items": [],
            "primary_cta_url": "https://example.test/today",
            "portal_link": "https://example.test/",
            "digest_pdf_attached": False,
            "digest_hiua_line": "PLAIN_HIUA_LINE",
            "digest_hiua_report_framing_notice": "PLAIN_HIUA_FRAME",
        },
    )
    assert "PLAIN_HIUA_LINE" in txt
    assert "PLAIN_HIUA_FRAME" in txt
    assert "GOVERNANCE CONTEXT" in txt
    assert "Snapshot as of 01 April 2026 10:00 UTC" in txt


def test_monthly_digest_email_html_includes_hiua_payload():
    from services.email_service import EmailService

    svc = EmailService()
    html = svc._build_monthly_digest_action_body_html(
        {
            "reporting_month_label": "March 2026",
            "account_name": "Test",
            "client_name": "Test",
            "generated_at_display": "1 Apr 2026",
            "digest_snapshot_framing_line": "Snapshot as of 01 April 2026 10:00 UTC",
            "data_as_of": "2026-04-01",
            "properties_count": 1,
            "compliance_score": 80,
            "score_status": "ok",
            "last_calculated_at": "2026-04-01",
            "score_status_message": "Headline uses last completed batch.",
            "risk_level": "Low Risk",
            "total_requirements": 2,
            "valid_count": 2,
            "compliant": 2,
            "expiring_soon": 0,
            "overdue": 0,
            "missing_evidence_count": 0,
            "include_compliance_summary": True,
            "include_action_items": False,
            "include_recommendations": True,
            "deltas": {"has_prior_snapshot": False},
            "digest_hiua_line": "EMAIL_HIUA_LINE_MARKER",
            "digest_hiua_report_framing_notice": "EMAIL_HIUA_FRAME_MARKER",
        }
    )
    assert "EMAIL_HIUA_LINE_MARKER" in html
    assert "EMAIL_HIUA_FRAME_MARKER" in html
    assert "Applicability follow-up" in html
    assert "Portfolio overview" in html
    assert "Snapshot as of 01 April 2026 10:00 UTC" in html
    assert "Headline uses last completed batch." in html


def test_monthly_digest_pdf_executive_summary_includes_snapshot_and_score_rows(monkeypatch):
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
        "generated_at_display": "30 April 2026 12:00 UTC",
        "digest_snapshot_framing_line": "Snapshot as of 30 April 2026 12:00 UTC",
        "account_name": "A",
        "properties_count": 1,
        "compliance_score": 80,
        "score_status": "stale",
        "last_calculated_at": "2026-04-01T08:00:00Z",
        "score_status_message": "Recalculation pending for one property.",
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
    assert b"Snapshot as of 30 April 2026 12:00 UTC" in pdf
    assert b"Executive snapshot" in pdf
    assert b"Score trend" in pdf
    assert b"Last calculated" in pdf
    assert b"2026-04-01" in pdf
    # Headline note is surfaced via executive interpretation when present in model
    assert b"Monthly Operations Intelligence Digest" in pdf
    assert b"Portfolio trajectory" in pdf
