"""Lifecycle Communication Authority constants."""

from __future__ import annotations

from typing import Final, FrozenSet, Literal

AUTHORITY_VERSION: Final[str] = "lifecycle_communication_v1"

LifecycleFamily = Literal[
    "EXPIRY_BASED",
    "LICENSING",
    "REGISTRATION",
    "DECLARATION_BASED",
    "TENANCY_LIFECYCLE",
    "OCCUPANCY_LIFECYCLE",
    "REVIEW_BASED",
    "EVENT_BASED",
    "DOCUMENT_EVIDENCE",
    "STRUCTURED_EVIDENCE",
    "SELF_CERTIFIED",
    "INSPECTION",
    "ASSESSMENT",
    "OPERATIONAL",
]

CommunicationSurface = Literal[
    "reminder_email",
    "reminder_sms",
    "enablement",
    "digest",
    "risk_card",
    "portal_chip",
    "portal_detail",
    "portal_cta",
    "today",
    "command_centre",
    "notification",
    "pdf_report",
    "admin_preview",
    "completion",
    "empty_state",
    "tooltip",
]

CommunicationChannel = Literal["EMAIL", "SMS", "IN_APP", "PORTAL", "PDF"]

LIFECYCLE_FAMILIES: FrozenSet[str] = frozenset(
    {
        "EXPIRY_BASED",
        "LICENSING",
        "REGISTRATION",
        "DECLARATION_BASED",
        "TENANCY_LIFECYCLE",
        "OCCUPANCY_LIFECYCLE",
        "REVIEW_BASED",
        "EVENT_BASED",
        "DOCUMENT_EVIDENCE",
        "STRUCTURED_EVIDENCE",
        "SELF_CERTIFIED",
        "INSPECTION",
        "ASSESSMENT",
        "OPERATIONAL",
    }
)

REMINDER_GROUP_KEYS: FrozenSet[str] = frozenset(
    {
        "certificate_reminders",
        "declaration_reminders",
        "assessment_reminders",
        "condition_reminders",
        "other_reminders",
    }
)

TONE_PROFESSIONAL: Final[str] = "professional"
TONE_SUPPORTIVE: Final[str] = "supportive"
