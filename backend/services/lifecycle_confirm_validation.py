"""
Phase 2 S4 — lifecycle confirm contract validation (shadow observe-only).

Validates confirmed payloads against lifecycle_confirm_contract without blocking requests.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.lifecycle_aware_confirm_config import (
    is_lifecycle_aware_confirm_off,
    is_lifecycle_aware_confirm_shadow,
)
from services.lifecycle_confirm_contract import build_contract_for_requirement
from services.lifecycle_semantics_types import LifecycleSemantics

logger = logging.getLogger(__name__)

Violation = Dict[str, str]

_EXPIRY_PROXY_FIELDS = frozenset(
    {"expiry_date", "confirmed_expiry_date", "extracted_expiry_date"}
)
_REVIEW_DATE_FIELDS = frozenset(
    {"assessment_date", "review_date", "next_review_date"}
)
_TENANCY_END_FIELDS = frozenset({"fixed_term_end_date", "tenancy_end_date"})
_EVENT_DECLARATION_DATE_FIELDS = frozenset(
    {
        "event_date",
        "protection_date",
        "served_date",
        "delivery_date",
        "check_date",
        "completion_date",
        "document_date",
    }
)


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _parse_iso_date(value: Any) -> bool:
    if not _is_present(value):
        return False
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        datetime.fromisoformat(raw)
        return True
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            datetime.strptime(raw, fmt)
            return True
        except ValueError:
            continue
    return False


def _alias_confirm_value(payload: Dict[str, Any], field: str, contract: Dict[str, Any]) -> Any:
    if _is_present(payload.get(field)):
        return payload.get(field)
    semantics = contract.get("lifecycle_semantics")
    if semantics == "EXPIRY_BASED" and field == "expiry_date":
        return payload.get("confirmed_expiry_date")
    for rule in contract.get("validation_rules") or []:
        if rule.get("rule") != "field_alias_map":
            continue
        aliases = rule.get("aliases") or {}
        for alias, canonical in aliases.items():
            if canonical == field or alias == field:
                if _is_present(payload.get(alias)):
                    return payload.get(alias)
    return None


def _normalize_payload_for_validation(
    payload: Dict[str, Any],
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(payload)
    semantics = contract.get("lifecycle_semantics")
    if semantics == "EXPIRY_BASED":
        if not _is_present(out.get("expiry_date")) and _is_present(out.get("confirmed_expiry_date")):
            out["expiry_date"] = out["confirmed_expiry_date"]
    return out


def _detect_semantic_expiry_mapping(
    payload: Dict[str, Any],
    semantics: LifecycleSemantics,
) -> List[Violation]:
    violations: List[Violation] = []
    expiry_val = payload.get("expiry_date") or payload.get("confirmed_expiry_date")
    if not _is_present(expiry_val):
        return violations

    if semantics == "TENANCY_LIFECYCLE":
        for end_field in _TENANCY_END_FIELDS:
            end_val = payload.get(end_field)
            if _is_present(end_val) and str(end_val).strip() == str(expiry_val).strip():
                violations.append(
                    {
                        "code": "LIFECYCLE_SEMANTIC_EXPIRY_MAP",
                        "field": "expiry_date",
                        "message": "tenancy end date mapped as expiry",
                    }
                )
                break

    if semantics == "REVIEW_BASED":
        for review_field in _REVIEW_DATE_FIELDS:
            review_val = payload.get(review_field)
            if _is_present(review_val) and str(review_val).strip() == str(expiry_val).strip():
                violations.append(
                    {
                        "code": "LIFECYCLE_SEMANTIC_EXPIRY_MAP",
                        "field": "expiry_date",
                        "message": "review date mapped as expiry",
                    }
                )
                break

    if semantics in ("EVENT_BASED", "DECLARATION_BASED", "OCCUPANCY_LIFECYCLE", "OPERATIONAL"):
        for event_field in _EVENT_DECLARATION_DATE_FIELDS:
            event_val = payload.get(event_field)
            if _is_present(event_val) and str(event_val).strip() == str(expiry_val).strip():
                violations.append(
                    {
                        "code": "LIFECYCLE_SEMANTIC_EXPIRY_MAP",
                        "field": "expiry_date",
                        "message": "event or declaration date mapped as expiry",
                    }
                )
                break

    return violations


def validate_confirm_payload_against_contract(
    payload: Dict[str, Any],
    contract: Dict[str, Any],
) -> Tuple[bool, List[Violation]]:
    """
    Return (would_accept, violations). Does not raise or block callers.
    """
    if not isinstance(payload, dict):
        return False, [
            {
                "code": "LIFECYCLE_CONFIRM_CONTRACT_MISMATCH",
                "field": "*",
                "message": "payload must be an object",
            }
        ]

    violations: List[Violation] = []
    semantics = str(contract.get("lifecycle_semantics") or "")
    normalized = _normalize_payload_for_validation(payload, contract)
    forbidden = set(contract.get("forbidden_fields") or [])
    confirm_fields = list(contract.get("confirm_fields") or [])
    optional_fields = set(contract.get("optional_fields") or [])

    for field in forbidden:
        if _is_present(normalized.get(field)):
            violations.append(
                {
                    "code": "LIFECYCLE_FIELD_FORBIDDEN",
                    "field": field,
                    "message": f"forbidden field present: {field}",
                }
            )

    if semantics != "EXPIRY_BASED" and _is_present(payload.get("confirmed_expiry_date")):
        if not any(v.get("field") == "confirmed_expiry_date" for v in violations):
            violations.append(
                {
                    "code": "LIFECYCLE_CONFIRMED_EXPIRY_FORBIDDEN",
                    "field": "confirmed_expiry_date",
                    "message": "confirmed_expiry_date not permitted for non-EXPIRY lifecycle",
                }
            )

    violations.extend(_detect_semantic_expiry_mapping(normalized, semantics))  # type: ignore[arg-type]

    for field in confirm_fields:
        value = _alias_confirm_value(normalized, field, contract)
        if not _is_present(value):
            violations.append(
                {
                    "code": "LIFECYCLE_FIELD_REQUIRED",
                    "field": field,
                    "message": f"required field missing: {field}",
                }
            )

    date_fields = set(confirm_fields) | set(optional_fields)
    date_fields |= {f for f in forbidden if _is_present(normalized.get(f))}
    for field in sorted(date_fields):
        value = normalized.get(field)
        if not _is_present(value):
            continue
        if field.endswith("_date") or field in (
            "check_date",
            "completion_date",
            "document_date",
        ):
            if not _parse_iso_date(value):
                violations.append(
                    {
                        "code": "LIFECYCLE_INVALID_DATE",
                        "field": field,
                        "message": f"invalid date format: {field}",
                    }
                )

    return len(violations) == 0, violations


def observe_lifecycle_confirm_shadow_for_requirement(
    requirement: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    surface: str,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
    registry_row: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Shadow-only: validate payload, log would-accept / would-reject. No mutation, no blocking.
  Returns observation dict when shadow enabled, else None.
    """
    if is_lifecycle_aware_confirm_off() or not is_lifecycle_aware_confirm_shadow():
        return None

    contract = build_contract_for_requirement(requirement, registry_row=registry_row)
    would_accept, violations = validate_confirm_payload_against_contract(payload, contract)
    observation = {
        "surface": surface,
        "requirement_id": requirement_id or requirement.get("requirement_id"),
        "document_id": document_id,
        "lifecycle_semantics": contract.get("lifecycle_semantics"),
        "extraction_profile_id": contract.get("extraction_profile_id"),
        "contract_version": contract.get("contract_version"),
        "would_accept": would_accept,
        "violations": violations,
    }

    if would_accept:
        logger.info("lifecycle_confirm_shadow_would_accept", extra=observation)
    else:
        logger.info("lifecycle_confirm_shadow_would_reject", extra=observation)

    return observation
