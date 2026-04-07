"""
Deterministic certificate expiry: single source of truth for effective date and status.
Use confirmed_expiry_date if present, else extracted_expiry_date, else none.
Calendar and reminders must use this same rule.

"Expiring soon" uses compliance_expiry_policy.resolve_expiring_soon_days_for_requirement when
property_doc/client_doc are supplied; otherwise requirement.jurisdiction alone can inform the bucket.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from models import Applicability, ExpirySource, RequirementStatus


def _parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = (value.replace("Z", "+00:00") if isinstance(value, str) else str(value)).strip()
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def get_effective_expiry_date(requirement: Dict[str, Any]) -> Optional[datetime]:
    """
    Single rule: use confirmed_expiry_date if present, else extracted_expiry_date, else none.
    """
    confirmed = _parse_date(requirement.get("confirmed_expiry_date"))
    if confirmed is not None:
        return confirmed
    extracted = _parse_date(requirement.get("extracted_expiry_date"))
    if extracted is not None:
        return extracted
    # Fallback: legacy due_date (treat as effective expiry when new fields absent)
    due = _parse_date(requirement.get("due_date"))
    return due


def get_computed_status(
    requirement: Dict[str, Any],
    as_of: Optional[datetime] = None,
    *,
    property_doc: Optional[Dict[str, Any]] = None,
    client_doc: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Compute status from applicability and effective expiry: VALID | EXPIRING_SOON | OVERDUE | UNKNOWN_DATE | NOT_REQUIRED.
    Returns string for API compatibility (COMPLIANT used as VALID equivalent where existing code expects it).

    expiring_soon window is jurisdiction- and requirement-code-aware when property_doc / client_doc are provided
    (or requirement.jurisdiction is set); see compliance_expiry_policy.
    """
    from services.compliance_expiry_policy import resolve_expiring_soon_days_for_requirement

    now = as_of or datetime.now(timezone.utc)
    applicability = (requirement.get("applicability") or "UNKNOWN").strip().upper()
    if applicability == "NOT_REQUIRED":
        return RequirementStatus.NOT_REQUIRED.value

    effective = get_effective_expiry_date(requirement)
    if effective is None:
        return RequirementStatus.UNKNOWN_DATE.value

    days = (effective - now).days
    if days < 0:
        return RequirementStatus.OVERDUE.value
    window = resolve_expiring_soon_days_for_requirement(requirement, property_doc, client_doc)
    if days <= window:
        return RequirementStatus.EXPIRING_SOON.value
    return RequirementStatus.COMPLIANT.value  # VALID equivalent


def is_included_for_calendar(requirement: Dict[str, Any]) -> bool:
    """True if requirement has an effective expiry and is not NOT_REQUIRED (so include in calendar events)."""
    applicability = (requirement.get("applicability") or "UNKNOWN").strip().upper()
    if applicability == "NOT_REQUIRED":
        return False
    return get_effective_expiry_date(requirement) is not None
