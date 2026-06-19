"""
Discovery retention evaluation — Stage T.

Policy-driven retention status and purge eligibility evaluation only.
No scheduled purge execution or CRM changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional

from services.discovery.discovery_retention_policy import (
    RetentionPolicyRule,
    classify_prospect_policy_category,
    get_retention_policy_rule,
    get_retention_policy_rules,
    validate_retention_policy_config,
)
from services.discovery.discovery_models import DiscoveryReviewStatus


@dataclass
class RetentionStatusResult:
    category: str
    status: str  # valid | expired | archived | indefinite
    policy: RetentionPolicyRule
    expiry_at: Optional[datetime] = None
    archive_eligible_at: Optional[datetime] = None
    purge_eligible_at: Optional[datetime] = None
    retention_expiry_reached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "status": self.status,
            "policy": self.policy.category,
            "expiry_at": self.expiry_at.isoformat().replace("+00:00", "Z")
            if self.expiry_at
            else None,
            "archive_eligible_at": self.archive_eligible_at.isoformat().replace(
                "+00:00", "Z"
            )
            if self.archive_eligible_at
            else None,
            "purge_eligible_at": self.purge_eligible_at.isoformat().replace(
                "+00:00", "Z"
            )
            if self.purge_eligible_at
            else None,
            "retention_expiry_reached": self.retention_expiry_reached,
        }


@dataclass
class PurgeEligibilityResult:
    eligible: bool
    blocking_reasons: List[str] = field(default_factory=list)
    review_required: bool = False
    retention_expiry_reached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "blocking_reasons": list(self.blocking_reasons),
            "review_required": self.review_required,
            "retention_expiry_reached": self.retention_expiry_reached,
        }


class DiscoveryRetentionService:
    """Retention policy evaluation — no automatic deletion."""

    @staticmethod
    def validate_retention_policy() -> List[str]:
        return validate_retention_policy_config()

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _anchor_timestamp(prospect: Mapping[str, Any]) -> datetime:
        for key in ("archived_at", "created_at", "updated_at"):
            parsed = DiscoveryRetentionService._parse_timestamp(prospect.get(key))
            if parsed:
                return parsed
        return datetime.now(timezone.utc)

    @staticmethod
    def determine_retention_expiry(
        prospect: Mapping[str, Any],
        *,
        evaluated_at: Optional[datetime] = None,
        policy: Optional[RetentionPolicyRule] = None,
    ) -> Optional[datetime]:
        category = classify_prospect_policy_category(prospect)
        rule = policy or get_retention_policy_rule(category)
        if rule is None:
            return None
        if rule.purge_eligible_after_days is None and rule.hot_retention_days == 0:
            return None
        anchor = DiscoveryRetentionService._anchor_timestamp(prospect)
        days = rule.purge_eligible_after_days or rule.hot_retention_days
        return anchor + timedelta(days=days)

    @staticmethod
    def evaluate_retention_status(
        prospect: Mapping[str, Any],
        *,
        evaluated_at: Optional[datetime] = None,
        policy: Optional[RetentionPolicyRule] = None,
    ) -> RetentionStatusResult:
        when = evaluated_at or datetime.now(timezone.utc)
        category = classify_prospect_policy_category(prospect)
        rule = policy or get_retention_policy_rule(category)
        if rule is None:
            raise ValueError(f"No retention policy for category {category}")

        anchor = DiscoveryRetentionService._anchor_timestamp(prospect)
        archive_eligible_at = (
            anchor + timedelta(days=rule.archive_after_days)
            if rule.archive_after_days
            else None
        )
        purge_eligible_at = (
            anchor + timedelta(days=rule.purge_eligible_after_days)
            if rule.purge_eligible_after_days
            else None
        )
        expiry_at = DiscoveryRetentionService.determine_retention_expiry(
            prospect, evaluated_at=when, policy=rule
        )

        if not rule.allows_purge and rule.purge_eligible_after_days is None:
            status = "indefinite"
            retention_expiry_reached = False
        elif expiry_at and when >= expiry_at:
            status = "expired"
            retention_expiry_reached = True
        elif archive_eligible_at and when >= archive_eligible_at:
            status = "archived"
            retention_expiry_reached = False
        else:
            status = "valid"
            retention_expiry_reached = False

        return RetentionStatusResult(
            category=category,
            status=status,
            policy=rule,
            expiry_at=expiry_at,
            archive_eligible_at=archive_eligible_at,
            purge_eligible_at=purge_eligible_at,
            retention_expiry_reached=retention_expiry_reached,
        )

    @staticmethod
    def build_retention_summary(
        prospect: Mapping[str, Any],
        *,
        evaluated_at: Optional[datetime] = None,
    ) -> str:
        result = DiscoveryRetentionService.evaluate_retention_status(
            prospect, evaluated_at=evaluated_at
        )
        expiry_line = (
            result.expiry_at.date().isoformat() if result.expiry_at else "Indefinite"
        )
        status_line = "Valid" if result.status == "valid" else result.status.title()
        return (
            f"Retention Category:\n{result.category}\n\n"
            f"Retention Status:\n{status_line}\n\n"
            f"Retention Expiry:\n{expiry_line}\n\n"
            f"Policy:\n{result.policy.description}"
        )

    @staticmethod
    def determine_purge_eligibility(
        prospect: Mapping[str, Any],
        *,
        evaluated_at: Optional[datetime] = None,
    ) -> PurgeEligibilityResult:
        blocking: List[str] = []
        retention = DiscoveryRetentionService.evaluate_retention_status(
            prospect, evaluated_at=evaluated_at
        )

        if not retention.policy.allows_purge:
            blocking.append(f"policy {retention.category} does not allow purge")
        if not retention.retention_expiry_reached:
            blocking.append("retention expiry not reached")
        if bool(prospect.get("legal_hold")):
            blocking.append("legal_hold active")
        if str(prospect.get("erasure_status") or "") == "erased":
            blocking.append("record already erased — purge not applicable")

        review_status = str(prospect.get("review_status") or "")
        active_review_states = (
            DiscoveryReviewStatus.NEEDS_REVIEW.value,
            DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
            DiscoveryReviewStatus.DISCOVERED.value,
        )
        if review_status in active_review_states:
            blocking.append("active review item")
            review_required = True
        elif review_status == DiscoveryReviewStatus.APPROVED.value and not prospect.get(
            "imported_lead_id"
        ):
            review_required = True
            if retention.retention_expiry_reached:
                blocking.append("approved-not-imported requires governance review")
        else:
            review_required = bool(blocking)

        eligible = len(blocking) == 0 and retention.retention_expiry_reached
        return PurgeEligibilityResult(
            eligible=eligible,
            blocking_reasons=blocking,
            review_required=review_required and not eligible,
            retention_expiry_reached=retention.retention_expiry_reached,
        )

    @staticmethod
    def list_policy_rules() -> Dict[str, RetentionPolicyRule]:
        return get_retention_policy_rules()
