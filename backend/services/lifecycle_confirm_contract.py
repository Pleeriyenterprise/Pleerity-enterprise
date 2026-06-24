"""
Phase 2 S3 — lifecycle confirm contract builder (observe-only; no enforcement).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.lifecycle_aware_confirm_config import (
    contract_version,
    is_lifecycle_aware_confirm_off,
    is_lifecycle_aware_confirm_shadow,
)
from services.lifecycle_extraction_profile_resolver import (
    ResolvedExtractionProfile,
    resolve_extraction_profile,
    resolve_extraction_profile_from_slug,
)
from services.lifecycle_extraction_profiles import ExtractionProfile
from services.lifecycle_semantics_config import resolver_version
from services.lifecycle_semantics_types import LifecycleSemantics

logger = logging.getLogger(__name__)

_FIELD_LABELS: Dict[str, str] = {
    "expiry_date": "Certificate expiry date",
    "issue_date": "Issue date",
    "certificate_number": "Certificate number",
    "licence_number": "Licence number",
    "inspector_company": "Inspector company",
    "inspector_id": "Inspector ID",
    "tenancy_start_date": "Tenancy start date",
    "fixed_term_end_date": "Fixed term end date",
    "tenant_name": "Tenant name",
    "agreement_type": "Agreement type",
    "rent_amount": "Rent amount",
    "protection_date": "Protection date",
    "scheme_name": "Scheme name",
    "scheme_reference": "Scheme reference",
    "deposit_amount": "Deposit amount",
    "served_date": "Served date",
    "served_to": "Served to",
    "service_method": "Service method",
    "guide_version": "Guide version",
    "check_date": "Check date",
    "follow_up_date": "Follow-up date",
    "document_type": "Document type",
    "assessment_date": "Assessment date",
    "next_review_date": "Next review date",
    "risk_level": "Risk level",
    "registration_number": "Registration number",
    "issuing_authority": "Issuing authority",
    "registration_status": "Registration status",
    "event_date": "Event date",
    "event_type": "Event type",
    "completion_notes": "Completion notes",
    "installer_name": "Installer name",
    "completion_date": "Completion date",
    "responsible_person": "Responsible person",
    "work_summary": "Work summary",
    "document_date": "Document date",
    "reference_number": "Reference number",
    "summary": "Summary",
}


def _iso_date_rule(field: str, *, optional: bool = False) -> Dict[str, Any]:
    rule: Dict[str, Any] = {"rule": "iso_date", "field": field}
    if optional:
        rule["optional"] = True
    return rule


def _required_rule(field: str) -> Dict[str, Any]:
    return {"rule": "required", "field": field}


def _validation_rules_for_profile(
    profile: ExtractionProfile,
    semantics: LifecycleSemantics,
) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    for field in profile.required_fields:
        rules.append(_required_rule(field))
        rules.append(_iso_date_rule(field))

    date_fields = set(profile.required_fields) | set(profile.optional_fields)
    for field in profile.optional_fields:
        if field.endswith("_date") or field in ("check_date", "completion_date", "document_date"):
            rules.append(_iso_date_rule(field, optional=True))

    if semantics == "EXPIRY_BASED" and "issue_date" in date_fields and "expiry_date" in date_fields:
        rules.append(
            {
                "rule": "issue_not_after_expiry",
                "issue_field": "issue_date",
                "expiry_field": "expiry_date",
                "optional": True,
            }
        )

    if semantics == "TENANCY_LIFECYCLE":
        rules.append(
            {
                "rule": "date_order",
                "start_field": "tenancy_start_date",
                "end_field": "fixed_term_end_date",
                "optional": True,
            }
        )

    if semantics == "OCCUPANCY_LIFECYCLE":
        rules.append(
            {
                "rule": "conditional_required",
                "when": {
                    "any": [
                        {"field": "right_to_rent_status", "equals": "time_limited"},
                        {"field": "follow_up_required", "equals": "YES"},
                    ]
                },
                "then_required": ["follow_up_date"],
            }
        )

    if semantics == "REVIEW_BASED" and "next_review_date" in date_fields:
        rules.append(
            {
                "rule": "conditional_required",
                "when": {"field": "actions_required", "equals": "YES"},
                "then_required": ["next_review_date"],
            }
        )

    if semantics == "DECLARATION_BASED":
        rules.append(
            {
                "rule": "field_alias_map",
                "aliases": {
                    "protection_date": "event_date",
                    "served_date": "event_date",
                    "delivery_date": "event_date",
                },
            }
        )

    if semantics == "EVENT_BASED":
        rules.append(
            {
                "rule": "not_future",
                "field": "event_date",
                "max_days_past": 3650,
                "optional": True,
            }
        )

    return rules


def _forbidden_fields_for_profile(
    profile: ExtractionProfile,
    semantics: LifecycleSemantics,
) -> List[str]:
    forbidden = list(profile.forbidden_fields)
    if semantics != "EXPIRY_BASED":
        for extra in ("expiry_date", "confirmed_expiry_date", "extracted_expiry_date"):
            if extra not in forbidden:
                forbidden.append(extra)
    return forbidden


def build_lifecycle_confirm_contract(
    resolved: ResolvedExtractionProfile,
) -> Dict[str, Any]:
    profile = resolved.profile
    semantics = resolved.lifecycle_semantics
    confirm_fields = list(profile.required_fields)
    optional_fields = list(profile.optional_fields)
    forbidden_fields = _forbidden_fields_for_profile(profile, semantics)

    labels = {
        field: _FIELD_LABELS.get(field, field.replace("_", " ").title())
        for field in confirm_fields + optional_fields
    }

    return {
        "lifecycle_semantics": semantics,
        "extraction_profile_id": resolved.profile_id,
        "confirm_fields": confirm_fields,
        "optional_fields": optional_fields,
        "forbidden_fields": forbidden_fields,
        "field_labels": labels,
        "validation_rules": _validation_rules_for_profile(profile, semantics),
        "resolver_version": resolver_version(),
        "contract_version": contract_version(),
        "resolution_source": resolved.resolution_source,
    }


def build_contract_for_requirement(
    requirement: Dict[str, Any],
    *,
    registry_row: Optional[Dict[str, Any]] = None,
    document: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved = resolve_extraction_profile(
        requirement,
        registry_row=registry_row,
        document=document,
    )
    return build_lifecycle_confirm_contract(resolved)


def build_contract_for_storage_slug(
    storage_slug: Optional[str],
    *,
    registry_row: Optional[Dict[str, Any]] = None,
    document: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved = resolve_extraction_profile_from_slug(
        storage_slug,
        registry_row=registry_row,
        document=document,
    )
    return build_lifecycle_confirm_contract(resolved)


def observe_confirm_contract_shadow(
    contract: Dict[str, Any],
    *,
    surface: str,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> None:
    if not is_lifecycle_aware_confirm_shadow():
        return
    logger.info(
        "lifecycle_confirm_contract_built",
        extra={
            "surface": surface,
            "requirement_id": requirement_id,
            "document_id": document_id,
            "lifecycle_semantics": contract.get("lifecycle_semantics"),
            "extraction_profile_id": contract.get("extraction_profile_id"),
            "confirm_fields": contract.get("confirm_fields"),
            "forbidden_fields": contract.get("forbidden_fields"),
            "contract_version": contract.get("contract_version"),
        },
    )


def maybe_attach_lifecycle_confirm_contract(
    payload: Dict[str, Any],
    *,
    requirement: Optional[Dict[str, Any]] = None,
    registry_row: Optional[Dict[str, Any]] = None,
    storage_slug: Optional[str] = None,
    document: Optional[Dict[str, Any]] = None,
    surface: str,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Attach lifecycle_confirm_contract when LIFECYCLE_AWARE_CONFIRM=shadow.
    When off, payload is unchanged (no behaviour change).
    """
    if is_lifecycle_aware_confirm_off():
        return payload

    if requirement:
        contract = build_contract_for_requirement(
            requirement,
            registry_row=registry_row,
            document=document,
        )
    else:
        contract = build_contract_for_storage_slug(
            storage_slug,
            registry_row=registry_row,
            document=document,
        )

    observe_confirm_contract_shadow(
        contract,
        surface=surface,
        requirement_id=requirement_id,
        document_id=document_id,
    )
    out = dict(payload)
    out["lifecycle_confirm_contract"] = contract
    return out


def observe_confirm_payload_shadow(
    payload: Dict[str, Any],
    contract: Dict[str, Any],
    *,
    surface: str,
) -> None:
    """
    Observe-only validation logging — does not block requests (S3/S4).
    """
    if is_lifecycle_aware_confirm_off() or not is_lifecycle_aware_confirm_shadow():
        return

    from services.lifecycle_confirm_validation import validate_confirm_payload_against_contract

    would_accept, violations = validate_confirm_payload_against_contract(payload, contract)
    if would_accept:
        logger.info(
            "lifecycle_confirm_shadow_would_accept",
            extra={"surface": surface, "contract_version": contract.get("contract_version")},
        )
    else:
        logger.info(
            "lifecycle_confirm_shadow_would_reject",
            extra={
                "surface": surface,
                "violations": violations,
                "contract_version": contract.get("contract_version"),
            },
        )
