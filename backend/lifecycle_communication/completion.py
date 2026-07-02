"""Completion and next-step wording authority."""

from __future__ import annotations

from typing import Dict

from lifecycle_communication.constants import LifecycleFamily

COMPLETION_WORDING: Dict[str, str] = {
    "EXPIRY_BASED": "Evidence verified. No further action required until the next renewal date.",
    "LICENSING": "Licence evidence verified. No further action required until the next renewal date.",
    "REGISTRATION": "Registration evidence verified. No further action required until the next renewal date.",
    "DECLARATION_BASED": "Declaration recorded. No further action required unless your circumstances change.",
    "SELF_CERTIFIED": "Declaration recorded. No further action required unless your circumstances change.",
    "STRUCTURED_EVIDENCE": "Declaration submitted. We will confirm once it has been reviewed.",
    "TENANCY_LIFECYCLE": "Tenancy record received. No further action required for this milestone.",
    "OCCUPANCY_LIFECYCLE": "Occupancy verification recorded. No further action required until the next review.",
    "REVIEW_BASED": "Review completed. No further action required until the next review date.",
    "EVENT_BASED": "Event recorded. No further action required for this obligation.",
    "DOCUMENT_EVIDENCE": "Evidence received. We will confirm once it has been reviewed.",
    "INSPECTION": "Inspection evidence received. We will confirm once it has been reviewed.",
    "ASSESSMENT": "Assessment completed. No further action required until the next assessment date.",
    "OPERATIONAL": "Issue resolved. No further action required for this item.",
}

RECEIVED_WORDING: Dict[str, str] = {
    "EXPIRY_BASED": "Evidence received. We will confirm once it has been reviewed.",
    "LICENSING": "Licence evidence received. We will confirm once it has been reviewed.",
    "REGISTRATION": "Registration evidence received. We will confirm once it has been reviewed.",
    "DECLARATION_BASED": "Declaration received. We will confirm once it has been reviewed.",
    "SELF_CERTIFIED": "Declaration received. We will confirm once it has been reviewed.",
    "STRUCTURED_EVIDENCE": "Declaration received. We will confirm once it has been reviewed.",
    "TENANCY_LIFECYCLE": "Tenancy document received. We will confirm once it has been reviewed.",
    "OCCUPANCY_LIFECYCLE": "Occupancy evidence received. We will confirm once it has been reviewed.",
    "REVIEW_BASED": "Review evidence received. We will confirm once it has been reviewed.",
    "EVENT_BASED": "Event evidence received. We will confirm once it has been reviewed.",
    "DOCUMENT_EVIDENCE": "Evidence received. We will confirm once it has been reviewed.",
    "INSPECTION": "Inspection report received. We will confirm once it has been reviewed.",
    "ASSESSMENT": "Assessment evidence received. We will confirm once it has been reviewed.",
    "OPERATIONAL": "Update received. We will confirm once it has been reviewed.",
}

NEXT_STEP_REMINDER: Dict[str, str] = {
    "EXPIRY_BASED": "We will remind you before the next renewal date.",
    "LICENSING": "We will remind you before the licence renewal date.",
    "REGISTRATION": "We will remind you before the registration renewal date.",
    "DECLARATION_BASED": "We will remind you if this declaration needs to be updated.",
    "SELF_CERTIFIED": "We will remind you if this declaration needs to be updated.",
    "STRUCTURED_EVIDENCE": "We will remind you if this declaration needs to be updated.",
    "TENANCY_LIFECYCLE": "We will remind you before the next tenancy milestone.",
    "OCCUPANCY_LIFECYCLE": "We will remind you before the next occupancy review.",
    "REVIEW_BASED": "We will remind you before the next review date.",
    "EVENT_BASED": "We will remind you if further action is needed.",
    "DOCUMENT_EVIDENCE": "We will remind you if further evidence is needed.",
    "INSPECTION": "We will remind you before the next inspection is due.",
    "ASSESSMENT": "We will remind you before the next assessment date.",
    "OPERATIONAL": "We will remind you if follow-up action is needed.",
}


def completion_wording(family: LifecycleFamily, *, verified: bool = True) -> str:
    if verified:
        return COMPLETION_WORDING.get(str(family or ""), "Requirement satisfied. No further action required.")
    return RECEIVED_WORDING.get(str(family or ""), "Evidence received. We will confirm once it has been reviewed.")


def next_step_wording(family: LifecycleFamily) -> str:
    return NEXT_STEP_REMINDER.get(str(family or ""), "We will remind you if further action is needed.")
