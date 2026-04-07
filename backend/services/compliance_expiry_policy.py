"""
Single source for "expiring soon" windows used across requirement status, scoring, and document status.

All paths should derive the threshold via resolve_expiring_soon_days_for_requirement() or
resolve_expiring_soon_days_for_v1_catalog_key() so jurisdiction + per-rule registry overrides stay aligned.

Environment:
  COMPLIANCE_EXPIRING_SOON_DAYS — default calendar/scoring window (default: 60). Must match operational expectation.

Product-risk (steady-state behaviour that can mislead users if unreviewed):
- Missing property and client portfolio labels fall back to "England" / ENGLAND_WALES via
  portfolio_jurisdiction_label() — see compliance_rules_registry.portfolio_jurisdiction_label.
- client.enabled_jurisdictions is a settings/onboarding field only; provisioning and scoring do not
  reject or filter work outside those regions — portfolios can still mix jurisdictions per property.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

_ENV_KEY = "COMPLIANCE_EXPIRING_SOON_DAYS"


def get_default_expiring_soon_days() -> int:
    """Profile default before per-code registry overrides (env COMPLIANCE_EXPIRING_SOON_DAYS, default 60)."""
    return int(os.environ.get(_ENV_KEY, "60"))


def resolve_expiring_soon_days_for_requirement(
    requirement: Dict[str, Any],
    property_doc: Optional[Dict[str, Any]] = None,
    client_doc: Optional[Dict[str, Any]] = None,
) -> int:
    """Jurisdiction-aware days-until-expiry threshold for requirement-row calendar / patch status."""
    from services.compliance_rules_registry import (
        expiring_soon_days_for_requirement,
        scoring_jurisdiction_for_property,
    )
    from services.compliance_scoring_v2 import normalize_requirement_code

    profile_default = get_default_expiring_soon_days()
    prop = dict(property_doc or {})
    if not prop.get("jurisdiction") and requirement.get("jurisdiction"):
        prop = {**prop, "jurisdiction": requirement.get("jurisdiction")}
    sj = scoring_jurisdiction_for_property(prop, client_doc or {})
    code = normalize_requirement_code(requirement.get("requirement_code") or requirement.get("requirement_type"))
    if not code:
        return profile_default
    return expiring_soon_days_for_requirement(sj, code, profile_default)


# v1 catalog keys → canonical codes used in compliance_rules_registry / scoring v2
_V1_KEY_TO_CANONICAL = {
    "GAS_SAFETY_CERT": "GAS_SAFETY",
    "EICR_CERT": "EICR",
    "EPC_CERT": "EPC",
}


def resolve_expiring_soon_days_for_v1_catalog_key(
    catalog_key: str,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]] = None,
) -> int:
    """Threshold for compliance_scoring v1 evidence rows (registry-backed codes only)."""
    from services.compliance_rules_registry import (
        expiring_soon_days_for_requirement,
        scoring_jurisdiction_for_property,
    )

    profile_default = get_default_expiring_soon_days()
    canon = _V1_KEY_TO_CANONICAL.get(catalog_key)
    if not canon:
        return profile_default
    sj = scoring_jurisdiction_for_property(property_doc, client_doc or {})
    return expiring_soon_days_for_requirement(sj, canon, profile_default)
