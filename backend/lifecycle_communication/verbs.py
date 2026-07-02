"""Governed lifecycle verb authority — one verb per family."""

from __future__ import annotations

from typing import Dict

from lifecycle_communication.constants import LifecycleFamily

GOVERNED_VERBS: Dict[str, str] = {
    "EXPIRY_BASED": "Renew",
    "LICENSING": "Renew",
    "REGISTRATION": "Renew",
    "DECLARATION_BASED": "Complete",
    "SELF_CERTIFIED": "Complete",
    "STRUCTURED_EVIDENCE": "Complete",
    "DOCUMENT_EVIDENCE": "Upload",
    "INSPECTION": "Arrange",
    "ASSESSMENT": "Complete",
    "REVIEW_BASED": "Review",
    "OCCUPANCY_LIFECYCLE": "Record",
    "TENANCY_LIFECYCLE": "Upload",
    "OPERATIONAL": "Resolve",
    "EVENT_BASED": "Record",
}


def governed_verb(family: LifecycleFamily) -> str:
    return GOVERNED_VERBS.get(str(family or ""), "Complete")
