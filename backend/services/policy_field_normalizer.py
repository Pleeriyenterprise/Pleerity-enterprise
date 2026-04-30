"""
Policy-field normalization and precedence helpers (PR1 foundation only).
"""
from __future__ import annotations

from typing import Any, Dict, Optional


POLICY_CRITICALITY_VALUES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
APPLICABILITY_VALUES = frozenset({"REQUIRED", "NOT_REQUIRED", "UNKNOWN"})


def normalize_requirement_code(requirement_row: Dict[str, Any]) -> str:
    code = (
        requirement_row.get("requirement_code")
        or requirement_row.get("code")
        or requirement_row.get("requirement_type")
        or ""
    )
    return str(code).strip().lower()


def normalize_applicability_state(requirement_row: Dict[str, Any]) -> str:
    raw = requirement_row.get("applicability_state")
    if raw is None:
        raw = requirement_row.get("applicability")
    if raw is None and str(requirement_row.get("status") or "").strip().upper() == "NOT_REQUIRED":
        return "NOT_REQUIRED"
    st = str(raw or "").strip().upper()
    if st in APPLICABILITY_VALUES:
        return st
    return "UNKNOWN"


def normalize_policy_criticality(raw: Any) -> str:
    val = str(raw or "").strip().upper()
    if val in POLICY_CRITICALITY_VALUES:
        return val
    return "MEDIUM"


def normalize_evidence_state(requirement_row: Dict[str, Any], gap_payload: Optional[Dict[str, Any]] = None) -> str:
    # Evidence truth precedence: requirement evidence authority, then gap payload snapshot, then legacy field.
    ea = requirement_row.get("evidence_authority") if isinstance(requirement_row.get("evidence_authority"), dict) else {}
    ea_state = str(ea.get("state") or "").strip().upper()
    if ea_state:
        return ea_state
    if isinstance(gap_payload, dict):
        snap = gap_payload.get("authority_snapshot") if isinstance(gap_payload.get("authority_snapshot"), dict) else {}
        snap_state = str(snap.get("state") or gap_payload.get("evidence_state") or "").strip().upper()
        if snap_state:
            return snap_state
    return str(requirement_row.get("evidence_state") or "").strip().upper()


def resolve_policy_facts(
    requirement_row: Dict[str, Any],
    *,
    registry_metadata: Optional[Dict[str, Any]] = None,
    catalog_defaults: Optional[Dict[str, Any]] = None,
    gap_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve policy facts with contract precedence:
    1) normalized requirement row fields (authoritative)
    2) registry metadata fallback
    3) catalog defaults fallback
    """
    req = requirement_row if isinstance(requirement_row, dict) else {}
    reg = registry_metadata if isinstance(registry_metadata, dict) else {}
    cat = catalog_defaults if isinstance(catalog_defaults, dict) else {}

    req_code = str(req.get("requirement_code_normalized") or "").strip().lower()
    if not req_code:
        req_code = normalize_requirement_code(req)

    applicability_state = normalize_applicability_state(req)
    if applicability_state == "UNKNOWN":
        applicability_state = str(reg.get("applicability_state") or "").strip().upper() or "UNKNOWN"
        if applicability_state not in APPLICABILITY_VALUES:
            applicability_state = str(cat.get("applicability_state") or "").strip().upper() or "UNKNOWN"
            if applicability_state not in APPLICABILITY_VALUES:
                applicability_state = "UNKNOWN"

    if req.get("is_mandatory") is not None:
        is_mandatory = bool(req.get("is_mandatory"))
        mandatory_source = "requirement_row"
    elif reg.get("is_mandatory") is not None:
        is_mandatory = bool(reg.get("is_mandatory"))
        mandatory_source = "registry_metadata"
    else:
        is_mandatory = bool(cat.get("is_mandatory", False))
        mandatory_source = "catalog_fallback"

    req_crit = req.get("policy_criticality")
    if req_crit is not None and str(req_crit).strip():
        policy_criticality = normalize_policy_criticality(req_crit)
        criticality_source = "requirement_row"
    elif reg.get("policy_criticality") is not None or reg.get("criticality") is not None:
        policy_criticality = normalize_policy_criticality(
            reg.get("policy_criticality") or reg.get("criticality")
        )
        criticality_source = "registry_metadata"
    else:
        policy_criticality = normalize_policy_criticality(
            cat.get("policy_criticality") or cat.get("criticality")
        )
        criticality_source = "catalog_fallback"

    evidence_state = normalize_evidence_state(req, gap_payload=gap_payload)

    return {
        "requirement_code_normalized": req_code,
        "applicability_state": applicability_state,
        "is_mandatory": is_mandatory,
        "policy_criticality": policy_criticality,
        "evidence_state_normalized": evidence_state,
        "mandatory_source": mandatory_source,
        "criticality_source": criticality_source,
    }
