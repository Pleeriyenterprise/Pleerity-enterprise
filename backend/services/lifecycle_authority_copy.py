"""
Lifecycle authority presentation copy (PRESENTATION-AUTHORITY-ALIGNMENT-01).

Single source for customer-facing wording that must align with backend lifecycle authority.
Does not define lifecycle rules — only governed phrases for reports, digests, and shared FE sync.
"""
from __future__ import annotations

from typing import Optional

CALENDAR_OVERDUE_SUBLINE = (
    "Past effective expiry — renew or confirm dates. "
    "This reflects your certificate calendar, not a legal compliance verdict."
)

EVIDENCE_REQUIRED_LABEL = "Evidence required"
AWAITING_VERIFICATION_LABEL = "Awaiting verification"

DIGEST_SUFFIX_OVERDUE = " — calendar overdue"
DIGEST_SUFFIX_EVIDENCE_REQUIRED = " — evidence required"
DIGEST_SUFFIX_URGENT = " — urgent"
DIGEST_SUFFIX_DUE_SOON = " — due soon"

COUNT_SEMANTICS_EXPLANATION = (
    "Some identified obligations are informational, conditional, jurisdiction-specific, archived, "
    "or otherwise outside active operational tracking. Nothing has been removed."
)


def calendar_overdue_subline() -> str:
    return CALENDAR_OVERDUE_SUBLINE


def digest_action_line_suffix(
    *,
    section: str = "",
    overdue_days: int = 0,
    primary_action_type: Optional[str] = None,
) -> str:
    sec = (section or "").lower()
    if sec == "urgent":
        if overdue_days > 0:
            return DIGEST_SUFFIX_OVERDUE
        return DIGEST_SUFFIX_URGENT
    if primary_action_type == "upload_evidence":
        return DIGEST_SUFFIX_EVIDENCE_REQUIRED
    if sec == "upcoming":
        return DIGEST_SUFFIX_DUE_SOON
    return ""


def requirement_count_footnote(*, applicable_count: int, tracked_count: int) -> Optional[str]:
    if applicable_count <= tracked_count:
        return None
    return COUNT_SEMANTICS_EXPLANATION
