"""Lifecycle semantics types — ADR_REQUIREMENT_LIFECYCLE_SEMANTICS Phase 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

LifecycleSemantics = Literal[
    "EXPIRY_BASED",
    "REVIEW_BASED",
    "EVENT_BASED",
    "DECLARATION_BASED",
    "TENANCY_LIFECYCLE",
    "OCCUPANCY_LIFECYCLE",
    "OPERATIONAL",
]

AttentionKind = Literal[
    "CERTIFICATE_EXPIRING",
    "REVIEW_DUE",
    "EVENT_ACTION_REQUIRED",
    "TENANCY_TERM_ENDING",
    "OCCUPANCY_REVIEW_DUE",
    "OPERATIONAL_ACTION_REQUIRED",
]

ResolutionSource = Literal["registry", "governance_fallback", "legacy_map", "default"]

LIFECYCLE_SEMANTICS_VALUES: frozenset[str] = frozenset(
    {
        "EXPIRY_BASED",
        "REVIEW_BASED",
        "EVENT_BASED",
        "DECLARATION_BASED",
        "TENANCY_LIFECYCLE",
        "OCCUPANCY_LIFECYCLE",
        "OPERATIONAL",
    }
)

ATTENTION_KIND_VALUES: frozenset[str] = frozenset(
    {
        "CERTIFICATE_EXPIRING",
        "REVIEW_DUE",
        "EVENT_ACTION_REQUIRED",
        "TENANCY_TERM_ENDING",
        "OCCUPANCY_REVIEW_DUE",
        "OPERATIONAL_ACTION_REQUIRED",
    }
)


@dataclass(frozen=True)
class FieldContract:
    requires_expiry_date: bool = False
    requires_issue_date: bool = False
    requires_review_date: bool = False
    requires_next_review_date: bool = False
    requires_event_date: bool = False
    requires_tenancy_dates: bool = False
    requires_occupancy_dates: bool = False
    allows_estimated_expiry: bool = False
    does_not_expire: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requires_expiry_date": self.requires_expiry_date,
            "requires_issue_date": self.requires_issue_date,
            "requires_review_date": self.requires_review_date,
            "requires_next_review_date": self.requires_next_review_date,
            "requires_event_date": self.requires_event_date,
            "requires_tenancy_dates": self.requires_tenancy_dates,
            "requires_occupancy_dates": self.requires_occupancy_dates,
            "allows_estimated_expiry": self.allows_estimated_expiry,
            "does_not_expire": self.does_not_expire,
        }


@dataclass(frozen=True)
class CanonicalLifecycleDates:
    """Informational canonical date slots per lifecycle semantics (Phase 1 observe-only)."""

    expiry_date: Optional[datetime] = None
    issue_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    next_review_date: Optional[datetime] = None
    event_date: Optional[datetime] = None
    tenancy_start_date: Optional[datetime] = None
    tenancy_end_date: Optional[datetime] = None
    occupancy_check_date: Optional[datetime] = None
    occupancy_follow_up_date: Optional[datetime] = None
    operational_due_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        def _iso(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None

        return {
            "expiry_date": _iso(self.expiry_date),
            "issue_date": _iso(self.issue_date),
            "review_date": _iso(self.review_date),
            "next_review_date": _iso(self.next_review_date),
            "event_date": _iso(self.event_date),
            "tenancy_start_date": _iso(self.tenancy_start_date),
            "tenancy_end_date": _iso(self.tenancy_end_date),
            "occupancy_check_date": _iso(self.occupancy_check_date),
            "occupancy_follow_up_date": _iso(self.occupancy_follow_up_date),
            "operational_due_date": _iso(self.operational_due_date),
        }


@dataclass(frozen=True)
class LegacyLifecycleSignals:
    expects_expiry: Optional[bool] = None
    expiry_type: Optional[str] = None
    legacy_effective_expiry_present: bool = False
    workflow_class: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expects_expiry": self.expects_expiry,
            "expiry_type": self.expiry_type,
            "legacy_effective_expiry_present": self.legacy_effective_expiry_present,
            "workflow_class": self.workflow_class,
        }


@dataclass(frozen=True)
class ResolvedLifecycle:
    requirement_id: Optional[str]
    requirement_code: str
    lifecycle_semantics: LifecycleSemantics
    field_contract: FieldContract
    attention_kind: Optional[AttentionKind]
    canonical_dates: CanonicalLifecycleDates
    effective_attention_date: Optional[datetime]
    vocabulary_family: str
    resolution_source: ResolutionSource
    resolver_version: str
    legacy_signals: LegacyLifecycleSignals
    validation_issues: List[str] = field(default_factory=list)

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_code": self.requirement_code,
            "lifecycle_semantics": self.lifecycle_semantics,
            "field_contract": self.field_contract.to_dict(),
            "attention_kind": self.attention_kind,
            "canonical_dates": self.canonical_dates.to_dict(),
            "effective_attention_date": (
                self.effective_attention_date.isoformat() if self.effective_attention_date else None
            ),
            "vocabulary_family": self.vocabulary_family,
            "resolution_source": self.resolution_source,
            "resolver_version": self.resolver_version,
            "legacy_signals": self.legacy_signals.to_dict(),
            "validation_issues": list(self.validation_issues),
        }


def field_contract_from_dict(raw: Optional[Dict[str, Any]]) -> FieldContract:
    data = raw if isinstance(raw, dict) else {}
    return FieldContract(
        requires_expiry_date=bool(data.get("requires_expiry_date")),
        requires_issue_date=bool(data.get("requires_issue_date")),
        requires_review_date=bool(data.get("requires_review_date")),
        requires_next_review_date=bool(data.get("requires_next_review_date")),
        requires_event_date=bool(data.get("requires_event_date")),
        requires_tenancy_dates=bool(data.get("requires_tenancy_dates")),
        requires_occupancy_dates=bool(data.get("requires_occupancy_dates")),
        allows_estimated_expiry=bool(data.get("allows_estimated_expiry")),
        does_not_expire=bool(data.get("does_not_expire")),
    )
