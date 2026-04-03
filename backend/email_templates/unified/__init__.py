"""
Unified customer email building blocks (Phase 6).

All customer-facing HTML composition for governed templates should prefer these helpers
plus ``email_templates.email_layout.build_customer_email_layout`` — not ad-hoc full documents
in business services.

See ``docs/EMAIL_TRIGGER_MAP.md`` for trigger → template → payload ownership.
"""

from email_templates.unified.scheduled_report_digest import (
    build_scheduled_report_digest_html,
    build_scheduled_report_digest_text,
)

__all__ = [
    "build_scheduled_report_digest_html",
    "build_scheduled_report_digest_text",
]
