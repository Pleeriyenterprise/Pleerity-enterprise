"""Evidence Review V2 canonical enums (additive to legacy DocumentStatus)."""

from __future__ import annotations

from enum import Enum


EVIDENCE_REVIEW_EVENTS_COLLECTION = "evidence_review_events"


class EvidenceReviewState(str, Enum):
    UPLOADED = "UPLOADED"
    UNDER_REVIEW = "UNDER_REVIEW"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    REJECTED = "REJECTED"
    ACCEPTED_UNVERIFIED = "ACCEPTED_UNVERIFIED"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class AssuranceTier(str, Enum):
    NONE = "NONE"
    USER_UPLOADED = "USER_UPLOADED"
    HUMAN_ACCEPTED = "HUMAN_ACCEPTED"
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"
    SYSTEM_EXPIRED = "SYSTEM_EXPIRED"
    REJECTED = "REJECTED"
