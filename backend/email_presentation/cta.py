"""CTA authority — governed labels and button styling."""

from __future__ import annotations

import html
from typing import Optional

from email_presentation.brand import get_brand_profile

# Governed CTA label registry (templates must reference these keys).
CTA_OPEN_PORTAL = "Open portal to review"
CTA_OPEN_PORTAL_DETAILS = "Open portal for details"
CTA_VIEW_EVIDENCE = "View evidence"
CTA_REVIEW_ISSUE = "Review issue"
CTA_UPLOAD_EVIDENCE = "Upload evidence"
CTA_REVIEW_DOCUMENT = "Review uploaded document"
CTA_VIEW_SUBMISSION = "View submission"
CTA_CONTINUE = "Continue"
CTA_MANAGE_PREFERENCES = "Manage notification preferences"
CTA_GO_DASHBOARD = "Go to your dashboard"
CTA_SET_UP_ACCESS = "Set Up Your Access"
CTA_START_MONITORING = "Start Compliance Monitoring"

CTA_BY_KEY = {
    "open_portal": CTA_OPEN_PORTAL,
    "open_portal_details": CTA_OPEN_PORTAL_DETAILS,
    "view_evidence": CTA_VIEW_EVIDENCE,
    "review_issue": CTA_REVIEW_ISSUE,
    "upload_evidence": CTA_UPLOAD_EVIDENCE,
    "review_document": CTA_REVIEW_DOCUMENT,
    "view_submission": CTA_VIEW_SUBMISSION,
    "continue": CTA_CONTINUE,
    "manage_preferences": CTA_MANAGE_PREFERENCES,
    "go_dashboard": CTA_GO_DASHBOARD,
    "set_up_access": CTA_SET_UP_ACCESS,
    "start_monitoring": CTA_START_MONITORING,
}


def cta_label(key: str, *, fallback: Optional[str] = None) -> str:
    return CTA_BY_KEY.get(key) or fallback or CTA_OPEN_PORTAL


def render_cta_html(url: str, label: str, *, model: Optional[dict] = None) -> str:
    brand = get_brand_profile(model)
    esc_url = html.escape(url, quote=True)
    esc_label = html.escape(label, quote=False)
    return (
        f'<a href="{esc_url}" '
        f'style="display:inline-block;background:{brand.button_bg};color:#ffffff;'
        f'text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:600;">'
        f"{esc_label}</a>"
    )
