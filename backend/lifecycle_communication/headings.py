"""Heading authority — grouped sections and surface headings."""

from __future__ import annotations

from typing import Dict, Optional

from lifecycle_communication.constants import LifecycleFamily, REMINDER_GROUP_KEYS

GROUP_HEADINGS: Dict[str, str] = {
    "certificate_reminders": "Certificates, licences and registrations",
    "declaration_reminders": "Declarations and tenancy records",
    "assessment_reminders": "Assessments and reviews",
    "condition_reminders": "Property conditions and remediation",
    "other_reminders": "Outstanding compliance obligations",
}

FAMILY_HEADINGS: Dict[str, str] = {
    "EXPIRY_BASED": "Certificate renewal required",
    "LICENSING": "Licence renewal required",
    "REGISTRATION": "Registration renewal required",
    "DECLARATION_BASED": "Declaration required",
    "SELF_CERTIFIED": "Declaration required",
    "STRUCTURED_EVIDENCE": "Declaration required",
    "TENANCY_LIFECYCLE": "Tenancy record required",
    "OCCUPANCY_LIFECYCLE": "Occupancy verification required",
    "REVIEW_BASED": "Review required",
    "EVENT_BASED": "Compliance action required",
    "DOCUMENT_EVIDENCE": "Evidence required",
    "INSPECTION": "Inspection required",
    "ASSESSMENT": "Assessment required",
    "OPERATIONAL": "Operational issue requires attention",
}

REMINDER_HEADER_TITLES: Dict[str, str] = {
    "CERTIFICATE_EXPIRING": "Compliance renewal reminder",
    "REVIEW_DUE": "Compliance review reminder",
    "EVENT_ACTION_REQUIRED": "Compliance action reminder",
    "TENANCY_TERM_ENDING": "Tenancy milestone reminder",
    "OCCUPANCY_REVIEW_DUE": "Occupancy review reminder",
    "OPERATIONAL_ACTION_REQUIRED": "Operational action reminder",
}


def heading_for_reminder_group(group_key: str) -> str:
    key = str(group_key or "").strip()
    if key in REMINDER_GROUP_KEYS:
        return GROUP_HEADINGS[key]
    return GROUP_HEADINGS["other_reminders"]


def heading_for_family(family: LifecycleFamily, *, is_overdue: bool = False) -> str:
    base = FAMILY_HEADINGS.get(str(family or ""), "Compliance action required")
    if is_overdue and family in ("EXPIRY_BASED", "LICENSING", "REGISTRATION"):
        return base.replace("required", "overdue")
    if is_overdue and family == "REVIEW_BASED":
        return "Review overdue"
    if is_overdue and family == "OPERATIONAL":
        return "Operational issue overdue"
    return base


def reminder_header_title(attention_kind: Optional[str]) -> str:
    return REMINDER_HEADER_TITLES.get(str(attention_kind or ""), REMINDER_HEADER_TITLES["CERTIFICATE_EXPIRING"])
