"""
Lifecycle Semantics Resolver — Phase 1 observe-only authority foundation.

ADR: backend/docs/architecture/ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md

Phase 1: classify and log only. Must not send reminders, alter scores, statuses, dashboards, or reports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.compliance_rules_registry import (
    expects_expiry_for_requirement,
    normalize_jurisdiction,
    work_order_requirement_code_to_registry_key,
)
from services.lifecycle_semantics_config import resolver_version
from services.lifecycle_semantics_fallback_map import (
    default_fallback_entry,
    fallback_entry_for_canonical_code,
    fallback_entry_for_storage_slug,
    fallback_entry_from_expiry_type,
    fallback_entry_from_expects_expiry,
    vocabulary_family_for_semantics,
)
from services.lifecycle_semantics_registry_loader import extract_lifecycle_from_registry_row
from services.lifecycle_semantics_types import (
    AttentionKind,
    CanonicalLifecycleDates,
    FieldContract,
    LegacyLifecycleSignals,
    LifecycleSemantics,
    ResolutionSource,
    ResolvedLifecycle,
)
from services.requirement_code_registry import normalize_requirement_code

logger = logging.getLogger(__name__)


def _parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = (value.replace("Z", "+00:00") if isinstance(value, str) else str(value)).strip()
        if not s:
            return None
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (TypeError, ValueError):
        return None


def _requirement_storage_slug(requirement: Dict[str, Any]) -> str:
    for key in ("requirement_code", "requirement_type", "code", "type"):
        raw = requirement.get(key)
        if raw:
            normalized = normalize_requirement_code(str(raw))
            if normalized:
                return normalized
            return str(raw).strip().lower().replace(" ", "_")
    return ""


def _requirement_canonical_upper(requirement: Dict[str, Any], storage_slug: str) -> str:
    raw = requirement.get("canonical_code") or requirement.get("requirement_canonical_code")
    if raw:
        return str(raw).strip().upper().replace(" ", "_")
    cc = work_order_requirement_code_to_registry_key(storage_slug)
    if cc:
        return str(cc).strip().upper()
    return storage_slug.upper().replace(" ", "_")


def _structured_payload(requirement: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("structured_declaration", "structured_payload", "declaration_payload"):
        val = requirement.get(key)
        if isinstance(val, dict):
            return val
    cer = requirement.get("compliance_evidence_record")
    if isinstance(cer, dict):
        decl = cer.get("structured_declaration") or cer.get("declaration")
        if isinstance(decl, dict):
            return decl
    return {}


def _collect_legacy_signals(requirement: Dict[str, Any], storage_slug: str) -> LegacyLifecycleSignals:
    from utils.expiry_utils import get_effective_expiry_date

    jurisdiction = normalize_jurisdiction(
        requirement.get("jurisdiction") or requirement.get("portfolio_jurisdiction") or "ENGLAND_WALES"
    )
    canonical = _requirement_canonical_upper(requirement, storage_slug)
    expects = expects_expiry_for_requirement(jurisdiction, canonical)
    expiry_type = requirement.get("expiry_type") or requirement.get("catalog_expiry_type")
    eff = get_effective_expiry_date(requirement)
    wf = (
        requirement.get("workflow_class")
        or requirement.get("client_workflow_class")
        or requirement.get("primary_resolution_workflow")
    )
    return LegacyLifecycleSignals(
        expects_expiry=expects,
        expiry_type=str(expiry_type).strip().upper() if expiry_type else None,
        legacy_effective_expiry_present=eff is not None,
        workflow_class=str(wf).strip().upper() if wf else None,
    )


def _collect_canonical_dates(requirement: Dict[str, Any]) -> CanonicalLifecycleDates:
    from utils.expiry_utils import get_effective_expiry_date

    payload = _structured_payload(requirement)
    eff_expiry = get_effective_expiry_date(requirement)
    return CanonicalLifecycleDates(
        expiry_date=eff_expiry if eff_expiry else _parse_date(requirement.get("confirmed_expiry_date")),
        issue_date=_parse_date(requirement.get("confirmed_issue_date") or requirement.get("issue_date")),
        review_date=_parse_date(payload.get("assessment_date") or payload.get("check_date")),
        next_review_date=_parse_date(payload.get("next_review_date") or requirement.get("next_review_date")),
        event_date=_parse_date(
            payload.get("delivery_date")
            or payload.get("pi_served_date")
            or payload.get("protection_date")
            or payload.get("deposit_received_date")
        ),
        tenancy_start_date=_parse_date(payload.get("tenancy_start_date")),
        tenancy_end_date=_parse_date(payload.get("fixed_term_end_date")),
        occupancy_check_date=_parse_date(payload.get("check_date")),
        occupancy_follow_up_date=_parse_date(payload.get("follow_up_date")),
        operational_due_date=_parse_date(requirement.get("due_date") or requirement.get("job_due_date")),
    )


def _infer_attention_kind(
    semantics: LifecycleSemantics,
    dates: CanonicalLifecycleDates,
    requirement: Dict[str, Any],
    *,
    as_of: Optional[datetime] = None,
) -> Optional[AttentionKind]:
    """Informational only — Phase 1 must not drive runtime from this output."""
    now = as_of or datetime.now(timezone.utc)

    if semantics == "EXPIRY_BASED" and dates.expiry_date:
        if dates.expiry_date < now:
            return "CERTIFICATE_EXPIRING"  # overdue still cert family in Phase 1 observe
        window_days = 60
        if (dates.expiry_date - now).days <= window_days:
            return "CERTIFICATE_EXPIRING"
        return None

    if semantics == "REVIEW_BASED":
        target = dates.next_review_date or dates.review_date
        if target and target <= now:
            return "REVIEW_DUE"
        if target and (target - now).days <= 60:
            return "REVIEW_DUE"
        return None

    if semantics == "TENANCY_LIFECYCLE" and dates.tenancy_end_date:
        if (dates.tenancy_end_date - now).days <= 90:
            return "TENANCY_TERM_ENDING"
        return None

    if semantics == "OCCUPANCY_LIFECYCLE":
        target = dates.occupancy_follow_up_date or dates.occupancy_check_date
        if target and target <= now:
            return "OCCUPANCY_REVIEW_DUE"
        if target and (target - now).days <= 60:
            return "OCCUPANCY_REVIEW_DUE"
        return None

    if semantics == "OPERATIONAL" and dates.operational_due_date:
        if dates.operational_due_date <= now:
            return "OPERATIONAL_ACTION_REQUIRED"
        return None

    if semantics in ("EVENT_BASED", "DECLARATION_BASED"):
        status = str(requirement.get("status") or "").strip().upper()
        from services.requirement_satisfaction_service import is_requirement_satisfied

        if not is_requirement_satisfied(requirement) and status not in ("COMPLIANT", "VALID", "SATISFIED"):
            return "EVENT_ACTION_REQUIRED"
        return None

    return None


def _effective_attention_date(
    semantics: LifecycleSemantics,
    dates: CanonicalLifecycleDates,
    attention_kind: Optional[AttentionKind],
) -> Optional[datetime]:
    if not attention_kind:
        return None
    if semantics == "EXPIRY_BASED":
        return dates.expiry_date
    if semantics == "REVIEW_BASED":
        return dates.next_review_date or dates.review_date
    if semantics == "TENANCY_LIFECYCLE":
        return dates.tenancy_end_date
    if semantics == "OCCUPANCY_LIFECYCLE":
        return dates.occupancy_follow_up_date or dates.occupancy_check_date
    if semantics == "OPERATIONAL":
        return dates.operational_due_date
    return dates.event_date


def _resolve_semantics_and_contract(
    requirement: Dict[str, Any],
    storage_slug: str,
    canonical_upper: str,
    registry_row: Optional[Dict[str, Any]],
    legacy: LegacyLifecycleSignals,
) -> tuple[LifecycleSemantics, FieldContract, str, ResolutionSource, List[str]]:
    issues: List[str] = []

    registry_hit = extract_lifecycle_from_registry_row(registry_row)
    if registry_hit:
        semantics, field_contract, vocab_override = registry_hit
        vocab = vocab_override or vocabulary_family_for_semantics(semantics)
        return semantics, field_contract, vocab, "registry", issues

    by_canonical = fallback_entry_for_canonical_code(canonical_upper)
    if by_canonical:
        semantics, field_contract = by_canonical
        return semantics, field_contract, vocabulary_family_for_semantics(semantics), "legacy_map", issues

    by_slug = fallback_entry_for_storage_slug(storage_slug)
    if by_slug:
        semantics, field_contract = by_slug
        return semantics, field_contract, vocabulary_family_for_semantics(semantics), "legacy_map", issues

    if legacy.expiry_type:
        from_type = fallback_entry_from_expiry_type(legacy.expiry_type)
        if from_type:
            semantics, field_contract = from_type
            issues.append("resolved_from_expiry_type")
            return semantics, field_contract, vocabulary_family_for_semantics(semantics), "legacy_map", issues

    if legacy.expects_expiry is not None:
        semantics, field_contract = fallback_entry_from_expects_expiry(bool(legacy.expects_expiry))
        issues.append("resolved_from_expects_expiry")
        return semantics, field_contract, vocabulary_family_for_semantics(semantics), "governance_fallback", issues

    semantics, field_contract = default_fallback_entry()
    issues.append("unresolved_used_default")
    return semantics, field_contract, vocabulary_family_for_semantics(semantics), "default", issues


def _detect_conflicts(
    semantics: LifecycleSemantics,
    field_contract: FieldContract,
    legacy: LegacyLifecycleSignals,
) -> List[str]:
    issues: List[str] = []
    if legacy.expects_expiry is True and semantics != "EXPIRY_BASED":
        issues.append("conflict_expects_expiry_true_non_expiry_semantics")
    if legacy.expects_expiry is False and semantics == "EXPIRY_BASED":
        issues.append("conflict_expects_expiry_false_expiry_semantics")
    if field_contract.does_not_expire and field_contract.requires_expiry_date:
        issues.append("conflict_does_not_expire_and_requires_expiry")
    if legacy.expiry_type == "EXPIRING" and semantics != "EXPIRY_BASED":
        issues.append("conflict_catalog_expiring_non_expiry_semantics")
    return issues


def resolve_lifecycle_semantics(
    requirement: Dict[str, Any],
    *,
    registry_row: Optional[Dict[str, Any]] = None,
    as_of: Optional[datetime] = None,
) -> ResolvedLifecycle:
    """
    Classify lifecycle semantics for a requirement row. Phase 1: observe-only.
    """
    storage_slug = _requirement_storage_slug(requirement)
    canonical_upper = _requirement_canonical_upper(requirement, storage_slug)
    legacy = _collect_legacy_signals(requirement, storage_slug)
    dates = _collect_canonical_dates(requirement)

    semantics, field_contract, vocabulary_family, source, issues = _resolve_semantics_and_contract(
        requirement, storage_slug, canonical_upper, registry_row, legacy
    )
    issues.extend(_detect_conflicts(semantics, field_contract, legacy))

    attention_kind = _infer_attention_kind(semantics, dates, requirement, as_of=as_of)
    eff_attention = _effective_attention_date(semantics, dates, attention_kind)

    req_id = (
        requirement.get("requirement_id")
        or requirement.get("_id")
        or requirement.get("id")
    )
    return ResolvedLifecycle(
        requirement_id=str(req_id) if req_id is not None else None,
        requirement_code=storage_slug or canonical_upper.lower(),
        lifecycle_semantics=semantics,
        field_contract=field_contract,
        attention_kind=attention_kind,
        canonical_dates=dates,
        effective_attention_date=eff_attention,
        vocabulary_family=vocabulary_family,
        resolution_source=source,
        resolver_version=resolver_version(),
        legacy_signals=legacy,
        validation_issues=issues,
    )


def resolve_lifecycle_semantics_batch(
    requirements: List[Dict[str, Any]],
    *,
    registry_index: Optional[Dict[str, Dict[str, Any]]] = None,
    as_of: Optional[datetime] = None,
) -> List[ResolvedLifecycle]:
    index = registry_index or {}
    out: List[ResolvedLifecycle] = []
    for req in requirements:
        slug = _requirement_storage_slug(req)
        canonical = _requirement_canonical_upper(req, slug)
        row = index.get(canonical) or index.get(slug.upper()) or index.get(slug)
        out.append(
            resolve_lifecycle_semantics(req, registry_row=row, as_of=as_of)
        )
    return out
