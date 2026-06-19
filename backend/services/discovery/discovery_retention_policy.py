"""
Discovery retention policy configuration — Stage T.

Policy periods sourced from ADR_DISCOVERY_RETENTION_AND_ERASURE.md.
Services evaluate against these rules; no hardcoded decisions in service logic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

POLICY_CATEGORY_REJECTED = "rejected_prospect"
POLICY_CATEGORY_ARCHIVED = "archived_prospect"
POLICY_CATEGORY_NOT_IMPORTED = "prospect_not_imported"
POLICY_CATEGORY_IMPORTED = "prospect_imported"
POLICY_CATEGORY_ERASED = "erased_prospect"
POLICY_CATEGORY_AUDIT = "audit_record"

SUPPORTED_POLICY_CATEGORIES = frozenset(
    {
        POLICY_CATEGORY_REJECTED,
        POLICY_CATEGORY_ARCHIVED,
        POLICY_CATEGORY_NOT_IMPORTED,
        POLICY_CATEGORY_IMPORTED,
        POLICY_CATEGORY_ERASED,
        POLICY_CATEGORY_AUDIT,
    }
)


@dataclass(frozen=True)
class RetentionPolicyRule:
    """Governance-defined retention rule for a record class."""

    category: str
    hot_retention_days: int
    archive_after_days: Optional[int] = None
    purge_eligible_after_days: Optional[int] = None
    description: str = ""
    allows_purge: bool = True
    allows_erasure: bool = True


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _default_policy_rules() -> Dict[str, RetentionPolicyRule]:
    """Defaults aligned with ADR_DISCOVERY_RETENTION_AND_ERASURE.md."""
    return {
        POLICY_CATEGORY_REJECTED: RetentionPolicyRule(
            category=POLICY_CATEGORY_REJECTED,
            hot_retention_days=_env_int("DISCOVERY_RETENTION_REJECTED_HOT_DAYS", 90),
            archive_after_days=_env_int("DISCOVERY_RETENTION_REJECTED_ARCHIVE_DAYS", 90),
            purge_eligible_after_days=_env_int(
                "DISCOVERY_RETENTION_REJECTED_PURGE_DAYS", 365
            ),
            description="Rejected prospect — hot then archive then anonymise/purge eligible",
        ),
        POLICY_CATEGORY_ARCHIVED: RetentionPolicyRule(
            category=POLICY_CATEGORY_ARCHIVED,
            hot_retention_days=_env_int("DISCOVERY_RETENTION_ARCHIVED_HOT_DAYS", 90),
            archive_after_days=_env_int("DISCOVERY_RETENTION_ARCHIVED_ARCHIVE_DAYS", 0),
            purge_eligible_after_days=_env_int(
                "DISCOVERY_RETENTION_ARCHIVED_PURGE_DAYS", 365
            ),
            description="Archived prospect stub retention",
        ),
        POLICY_CATEGORY_NOT_IMPORTED: RetentionPolicyRule(
            category=POLICY_CATEGORY_NOT_IMPORTED,
            hot_retention_days=_env_int("DISCOVERY_RETENTION_APPROVED_HOT_DAYS", 180),
            archive_after_days=_env_int("DISCOVERY_RETENTION_APPROVED_ARCHIVE_DAYS", 180),
            purge_eligible_after_days=_env_int(
                "DISCOVERY_RETENTION_APPROVED_PURGE_DAYS", 365
            ),
            description="Approved but not imported prospect",
        ),
        POLICY_CATEGORY_IMPORTED: RetentionPolicyRule(
            category=POLICY_CATEGORY_IMPORTED,
            hot_retention_days=_env_int("DISCOVERY_RETENTION_IMPORTED_HOT_DAYS", 0),
            archive_after_days=None,
            purge_eligible_after_days=None,
            description="Imported prospect link row — indefinite; erasure workflow only",
            allows_purge=False,
        ),
        POLICY_CATEGORY_ERASED: RetentionPolicyRule(
            category=POLICY_CATEGORY_ERASED,
            hot_retention_days=_env_int("DISCOVERY_RETENTION_ERASED_HOT_DAYS", 0),
            archive_after_days=None,
            purge_eligible_after_days=None,
            description="Erased prospect stub — suppression retained; no purge of hashes",
            allows_purge=False,
            allows_erasure=False,
        ),
        POLICY_CATEGORY_AUDIT: RetentionPolicyRule(
            category=POLICY_CATEGORY_AUDIT,
            hot_retention_days=_env_int("DISCOVERY_RETENTION_AUDIT_HOT_DAYS", 730),
            archive_after_days=_env_int("DISCOVERY_RETENTION_AUDIT_ARCHIVE_DAYS", 730),
            purge_eligible_after_days=None,
            description="Audit records — never deleted; warm archive only",
            allows_purge=False,
        ),
    }


def get_retention_policy_rules() -> Dict[str, RetentionPolicyRule]:
    return _default_policy_rules()


def get_retention_policy_rule(category: str) -> Optional[RetentionPolicyRule]:
    return get_retention_policy_rules().get(category)


def classify_prospect_policy_category(prospect: Mapping[str, object]) -> str:
    erasure_status = str(prospect.get("erasure_status") or "active")
    if erasure_status == "erased":
        return POLICY_CATEGORY_ERASED

    review_status = str(prospect.get("review_status") or "")
    if review_status == "archived":
        return POLICY_CATEGORY_ARCHIVED
    if review_status == "rejected":
        return POLICY_CATEGORY_REJECTED
    if prospect.get("imported_lead_id") or review_status == "imported":
        return POLICY_CATEGORY_IMPORTED
    if review_status == "approved":
        return POLICY_CATEGORY_NOT_IMPORTED

    if review_status in ("duplicate_detected",):
        return POLICY_CATEGORY_REJECTED

    return POLICY_CATEGORY_NOT_IMPORTED


def validate_retention_policy_config() -> List[str]:
    errors: List[str] = []
    rules = get_retention_policy_rules()
    for category in SUPPORTED_POLICY_CATEGORIES:
        if category not in rules:
            errors.append(f"missing policy rule for category {category}")
    for category, rule in rules.items():
        if rule.hot_retention_days < 0:
            errors.append(f"{category}: hot_retention_days must be non-negative")
        if rule.purge_eligible_after_days is not None and rule.purge_eligible_after_days < 0:
            errors.append(f"{category}: purge_eligible_after_days must be non-negative")
    return errors
