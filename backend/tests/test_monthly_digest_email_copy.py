"""Monthly Operations Intelligence Digest — email copy and rendering convergence tests."""
from __future__ import annotations

from models import EmailTemplateAlias
from services.email_service import EmailService
from services.monthly_digest_naming import (
    DIGEST_REPORT_TITLE,
    digest_attachment_filename,
    digest_email_subject,
    digest_primary_cta_label,
    digest_why_received,
)
from services.monthly_digest_operational_intelligence import (
    build_digest_intelligence,
    build_email_operational_themes,
    operational_posture_label,
)
from tests.test_monthly_digest_operational_intelligence import _base_model


_LEGACY_EMAIL_PHRASES = (
    "monthly compliance summary",
    "monthly compliance reporting",
    "open portal for compliance summary",
    "missing evidence",
    "critical risk",
    "items to review soon",
    "fffbeb",
    "fcd34d",
)


def _leo_like_model(**overrides):
    """Fixture resembling legacy alert-heavy digest (repeated work-order urgent lines)."""
    urgent = [
        {"line": "Work order — SLA deadline missed — urgent (Kelso Place)", "title": "Work order", "url": "https://app/today"},
        {"line": "Work order — SLA deadline missed — urgent (Kelso Place)", "title": "Work order", "url": "https://app/today"},
        {"line": "Work order — SLA deadline missed — urgent (Kelso Place)", "title": "Work order", "url": "https://app/today"},
        {"line": "Work order — SLA deadline missed — urgent (Kelso Place)", "title": "Work order", "url": "https://app/today"},
        {"line": "Work order — SLA deadline missed — urgent (Kelso Place)", "title": "Work order", "url": "https://app/today"},
    ]
    model = _base_model(
        reporting_month_label="May 2026",
        account_name="Signal Rise Labs",
        client_name="Leo",
        compliance_score=14,
        compliance_score_display="14",
        risk_level="Critical Risk",
        missing_evidence_count=9,
        overdue=0,
        urgent_items=urgent,
        digest_report_title=DIGEST_REPORT_TITLE,
        subject=digest_email_subject("May 2026"),
        email_header_title=digest_email_subject("May 2026"),
        digest_pdf_attached=True,
        digest_hiua_line="2 high-impact item(s) are open while applicability is still being confirmed.",
        digest_hiua_report_framing_notice="Treat as operational priority until applicability is resolved.",
        digest_email_top_properties_at_risk=[
            {
                "name": "Kelso Place",
                "score": 14,
                "risk_level": "Critical Risk",
                "overdue_count": 0,
                "missing_evidence_count": 9,
            }
        ],
        **overrides,
    )
    model["digest_intelligence"] = build_digest_intelligence(model)
    return model


def test_canonical_naming_subject_attachment_and_why_received():
    subj = digest_email_subject("May 2026")
    assert "Monthly Operations Intelligence Digest" in subj
    assert "Monthly Compliance Summary" not in subj
    assert digest_attachment_filename("2026-05") == "monthly-operations-intelligence-digest-2026-05.pdf"
    assert DIGEST_REPORT_TITLE in digest_why_received()
    assert "monthly compliance" not in digest_why_received().lower()
    assert "portfolio" in digest_primary_cta_label().lower()


def test_operational_posture_replaces_critical_risk_shouting():
    assert operational_posture_label("Critical Risk") == "Elevated operational exposure"
    assert "Critical" not in operational_posture_label("Critical Risk")


def test_grouped_themes_replace_repeated_urgent_spam():
    themes = build_email_operational_themes(_leo_like_model())
    assert themes
    joined = " ".join(f"{t.get('theme')} {t.get('summary')}" for t in themes).lower()
    assert "work-order" in joined or "work order" in joined
    assert joined.count("sla deadline missed") <= 1
    assert "5 unresolved work-order" in joined or "5 related items" in joined


def test_monthly_digest_email_html_executive_structure_no_alert_spam():
    svc = EmailService()
    html = svc._build_html_body(EmailTemplateAlias.MONTHLY_DIGEST, _leo_like_model())
    combined = html.lower()
    assert "monthly operations intelligence digest" in combined
    assert "portfolio overview" in combined
    assert "what changed this month" in combined
    assert "priority operational themes" in combined
    assert "recommended next actions" in combined
    assert "elevated operational exposure" in combined
    assert "unresolved documentation gap" in combined
    for phrase in _LEGACY_EMAIL_PHRASES:
        assert phrase not in combined


def test_monthly_digest_email_no_repeated_yellow_warning_cards():
    svc = EmailService()
    html = svc._build_html_body(EmailTemplateAlias.MONTHLY_DIGEST, _leo_like_model())
    assert html.count("fffbeb") == 0
    assert html.count("Items to review soon") == 0
    assert html.count("SLA deadline missed — urgent") <= 1


def test_monthly_digest_full_html_cta_and_attachment_note():
    svc = EmailService()
    html = svc._build_html_body(EmailTemplateAlias.MONTHLY_DIGEST, _leo_like_model())
    assert "Review portfolio in portal" in html
    assert "governance and operational review" in html.lower()
    assert digest_why_received().split("you have ")[1].rstrip(".") in html.lower() or "monthly operations intelligence digest delivery" in html.lower()


def test_monthly_digest_plain_text_canonical_and_grouped():
    svc = EmailService()
    text = svc._build_text_body(EmailTemplateAlias.MONTHLY_DIGEST, _leo_like_model())
    low = text.lower()
    assert "monthly operations intelligence digest" in low
    assert "priority operational themes" in low
    assert "monthly compliance summary" not in low
    assert low.count("sla deadline missed") <= 1


def test_monthly_digest_intelligence_includes_email_themes():
    intel = build_digest_intelligence(_leo_like_model())
    assert intel.get("email_operational_themes")
    assert intel.get("operational_posture_label") == "Elevated operational exposure"


def test_monthly_digest_email_readability_polish_no_duplicate_themes():
    svc = EmailService()
    html = svc._build_html_body(EmailTemplateAlias.MONTHLY_DIGEST, _leo_like_model())
    low = html.lower()
    assert low.count("evidence verification") <= 2
    assert low.count("portfolio trajectory:") == 0
    assert "improving. score movement" not in low or low.count("score movement and resolved") <= 2
    theme_labels = []
    for marker in ("work-order follow-up", "evidence verification", "renewals", "portfolio concentration"):
        if marker in low:
            theme_labels.append(marker)
    assert len(theme_labels) == len(set(theme_labels))
