"""Canonical outward-facing naming for Monthly Operations Intelligence Digest."""
from __future__ import annotations

import re

DIGEST_REPORT_TITLE = "Monthly Operations Intelligence Digest"
DIGEST_REPORT_SHORT = "Operations intelligence digest"
DIGEST_EMAIL_SUBJECT_PREFIX = DIGEST_REPORT_TITLE
DIGEST_ATTACHMENT_BASENAME = "monthly-operations-intelligence-digest"


def digest_email_subject(reporting_month_label: str, *, subset: bool = False) -> str:
    label = (reporting_month_label or "Reporting period").strip()
    suffix = " (selected properties)" if subset else ""
    return f"{DIGEST_EMAIL_SUBJECT_PREFIX} — {label}{suffix}"


def digest_attachment_filename(report_month_key: str) -> str:
    key = re.sub(r"[^\w\-]", "-", (report_month_key or "report").strip())[:32]
    return f"{DIGEST_ATTACHMENT_BASENAME}-{key}.pdf"


def digest_download_filename(*, period_end: str = "", digest_id: str = "") -> str:
    if period_end:
        pe = period_end[:10].replace("/", "-")
        return f"{DIGEST_ATTACHMENT_BASENAME}-{pe}.pdf"
    if digest_id:
        return f"{DIGEST_ATTACHMENT_BASENAME}-{digest_id[:8]}.pdf"
    return f"{DIGEST_ATTACHMENT_BASENAME}.pdf"
