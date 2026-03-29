"""
Requirement-to-contractor capability: structured matching for compliance execution work orders.

Declared fields (self-registration / intake) are for review and UI hints only.
Compliance routing and assignment gates MUST use verified_* fields (see parse_verified_* /
contractor_verified_qualifies_for_requirement).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from services.requirement_code_registry import normalize_requirement_code
from services.work_order_execution_constants import (
    EXECUTION_CAPABILITY_BOTH,
    EXECUTION_CAPABILITY_COMPLIANCE,
    EXECUTION_CAPABILITY_MAINTENANCE,
)

# Per canonical requirement: credential substrings (any match) and trade_types hints (any match).
# Used only for declared/intake hinting — not for compliance routing authority.
REQUIREMENT_EXECUTION_SPECS: Dict[str, Dict[str, List[str]]] = {
    "gas_safety": {
        "credential_hints": ["gas_safe", "gas safe", "cp12", "gassafe"],
        "trade_hints": ["heating", "gas", "gas_safe", "boiler", "plumbing"],
    },
    "eicr": {
        "credential_hints": ["eicr", "electrical", "niceic", "napit", "elecsa"],
        "trade_hints": ["electrical", "electrician"],
    },
    "epc": {
        "credential_hints": ["epc", "energy assessor", "domestic energy assessor", "deas"],
        "trade_hints": ["epc", "energy", "assessor"],
    },
    "fire_detection": {
        "credential_hints": ["fire alarm", "fire_detection", "bafe", "fds"],
        "trade_hints": ["fire", "alarm", "electrical"],
    },
    "legionella": {
        "credential_hints": ["legionella", "water hygiene", "l8"],
        "trade_hints": ["legionella", "plumbing", "water"],
    },
    "fire_risk_assessment": {
        "credential_hints": ["fire risk", "fra", "ife", "nfcc"],
        "trade_hints": ["fire", "risk", "assessment"],
    },
    "portable_appliance_test": {
        "credential_hints": ["pat", "portable appliance"],
        "trade_hints": ["electrical", "pat"],
    },
    "smoke_alarms": {
        "credential_hints": ["smoke", "fire alarm"],
        "trade_hints": ["fire", "electrical", "general"],
    },
    "co_alarms": {
        "credential_hints": ["co alarm", "carbon monoxide"],
        "trade_hints": ["fire", "electrical", "heating", "general"],
    },
    "hmo_license": {
        "credential_hints": ["hmo", "licence", "license"],
        "trade_hints": ["general"],
    },
    "deposit_pi": {"credential_hints": [], "trade_hints": ["general"]},
    "right_to_rent": {"credential_hints": [], "trade_hints": ["general"]},
    "how_to_rent": {"credential_hints": [], "trade_hints": ["general"]},
    "tenancy_agreement": {"credential_hints": [], "trade_hints": ["general"]},
}


def _caps_from_string(raw: str) -> Set[str]:
    v = (raw or "").strip().lower()
    if v == EXECUTION_CAPABILITY_BOTH:
        return {EXECUTION_CAPABILITY_MAINTENANCE, EXECUTION_CAPABILITY_COMPLIANCE}
    if v == EXECUTION_CAPABILITY_COMPLIANCE:
        return {EXECUTION_CAPABILITY_COMPLIANCE}
    return {EXECUTION_CAPABILITY_MAINTENANCE}


SOURCE_SELF_REGISTERED = "self_registered"


def parse_verified_execution_capabilities(contractor: Dict[str, Any]) -> Set[str]:
    """
    Compliance routing: trusted capability only.

    - If verified_execution_capabilities is set on the document, that string wins (empty/absent value
      means no verified compliance surface unless inferred from verified requirement codes).
    - self_registered contractors never inherit compliance from legacy execution_capabilities alone
      (prevents fuzzy/legacy intake from authorizing compliance execution).
    - Other source types fall back to legacy execution_capabilities when verified_* was never stored
      (backward compatibility / post-migration mirror).
    """
    st = (contractor.get("source_type") or "").strip().lower()
    is_self_reg = st == SOURCE_SELF_REGISTERED

    if "verified_execution_capabilities" in contractor:
        r = contractor.get("verified_execution_capabilities")
        if r is not None and str(r).strip():
            return _caps_from_string(str(r).strip().lower())
        if verified_supported_requirement_codes_set(contractor):
            return {EXECUTION_CAPABILITY_COMPLIANCE}
        return set()

    if is_self_reg:
        if "verified_supported_requirement_codes" in contractor and verified_supported_requirement_codes_set(
            contractor
        ):
            return {EXECUTION_CAPABILITY_COMPLIANCE}
        return set()

    legacy = (contractor.get("execution_capabilities") or EXECUTION_CAPABILITY_MAINTENANCE).strip().lower()
    return _caps_from_string(legacy)


def parse_execution_capabilities(contractor: Dict[str, Any]) -> Set[str]:
    """
    Maintenance routing: prefer legacy execution_capabilities, then declared_execution_capabilities,
    default maintenance. (Self-declared compliance intent does not enable maintenance routing.)
    """
    raw = (contractor.get("execution_capabilities") or "").strip().lower()
    if raw:
        return _caps_from_string(raw)
    decl = (contractor.get("declared_execution_capabilities") or "").strip().lower()
    if decl:
        return _caps_from_string(decl)
    return {EXECUTION_CAPABILITY_MAINTENANCE}


def contractor_is_compliance_capable(contractor: Dict[str, Any]) -> bool:
    return EXECUTION_CAPABILITY_COMPLIANCE in parse_verified_execution_capabilities(contractor)


def contractor_is_maintenance_capable(contractor: Dict[str, Any]) -> bool:
    return EXECUTION_CAPABILITY_MAINTENANCE in parse_execution_capabilities(contractor)


def _norm_list(vals: Optional[List[str]]) -> List[str]:
    return [str(x).strip().lower() for x in (vals or []) if str(x).strip()]


def supported_codes_normalized(contractor: Dict[str, Any]) -> Set[str]:
    """Legacy supported_requirement_codes on the contractor document (mirror of verified after admin sync)."""
    out: Set[str] = set()
    for x in contractor.get("supported_requirement_codes") or []:
        c = normalize_requirement_code(str(x))
        if c:
            out.add(c)
    return out


def verified_supported_requirement_codes_set(contractor: Dict[str, Any]) -> Set[str]:
    """
    Codes trusted for compliance routing.

    When verified_supported_requirement_codes exists on the document, that list is the authority
    (may be empty). self_registered contractors never fall back to legacy supported_requirement_codes
    so admin-only updates to legacy fields cannot bypass verification.
    """
    st = (contractor.get("source_type") or "").strip().lower()
    if "verified_supported_requirement_codes" in contractor:
        out: Set[str] = set()
        for x in contractor.get("verified_supported_requirement_codes") or []:
            c = normalize_requirement_code(str(x))
            if c:
                out.add(c)
        return out
    if st == SOURCE_SELF_REGISTERED:
        return set()
    return supported_codes_normalized(contractor)


def contractor_verified_qualifies_for_requirement(
    contractor: Dict[str, Any], canonical_requirement_code: str
) -> bool:
    """True only if the requirement code is in the verified (or legacy-mirrored) supported set — no fuzzy match."""
    code = normalize_requirement_code(canonical_requirement_code)
    if not code:
        return False
    return code in verified_supported_requirement_codes_set(contractor)


def declared_supported_requirement_codes_set(contractor: Dict[str, Any]) -> Set[str]:
    if "declared_supported_requirement_codes" not in contractor:
        return set()
    out: Set[str] = set()
    for x in contractor.get("declared_supported_requirement_codes") or []:
        c = normalize_requirement_code(str(x))
        if c:
            out.add(c)
    return out


def _intake_credentials_list(contractor: Dict[str, Any]) -> List[str]:
    if contractor.get("declared_credentials") is not None:
        return _norm_list(contractor.get("declared_credentials"))
    return _norm_list(contractor.get("credentials"))


def contractor_qualifies_for_requirement(contractor: Dict[str, Any], canonical_requirement_code: str) -> bool:
    """
    Declared / intake / admin-review hinting only. Uses declared_supported_requirement_codes (if present)
    and fuzzy credential/trade hints — NOT sufficient for compliance work order routing.
    """
    code = normalize_requirement_code(canonical_requirement_code)
    if not code:
        return False
    if code in declared_supported_requirement_codes_set(contractor):
        return True
    spec = REQUIREMENT_EXECUTION_SPECS.get(code) or {"credential_hints": [], "trade_hints": []}
    creds = _intake_credentials_list(contractor)
    trades = _norm_list(contractor.get("trade_types"))
    for hint in spec.get("credential_hints") or []:
        h = hint.lower()
        if any(h in cr or cr in h for cr in creds):
            return True
    for hint in spec.get("trade_hints") or []:
        h = hint.lower()
        if any(h in tr or tr in h for tr in trades):
            return True
    return False


def compliance_match_reasons_verified(
    contractor: Dict[str, Any], canonical_requirement_code: str
) -> List[str]:
    """Human-readable reasons based on verified capability only (recommendation / compliance pool)."""
    code = normalize_requirement_code(canonical_requirement_code)
    if not code:
        return []
    if code in verified_supported_requirement_codes_set(contractor):
        return [f"Verified capability for requirement {code}"]
    return []


def compliance_match_reasons(contractor: Dict[str, Any], canonical_requirement_code: str) -> List[str]:
    """Human-readable reasons for declared/intake matching (admin review — not routing authority)."""
    code = normalize_requirement_code(canonical_requirement_code)
    reasons: List[str] = []
    if code in declared_supported_requirement_codes_set(contractor):
        reasons.append(f"Declared capability for requirement {code}")
        return reasons
    spec = REQUIREMENT_EXECUTION_SPECS.get(code) or {}
    creds = _intake_credentials_list(contractor)
    trades = _norm_list(contractor.get("trade_types"))
    for hint in spec.get("credential_hints") or []:
        h = hint.lower()
        if any(h in cr or cr in h for cr in creds):
            reasons.append(f"Declared credential hint ({hint}) for {code}")
            break
    for hint in spec.get("trade_hints") or []:
        h = hint.lower()
        if any(h in tr or tr in h for tr in trades):
            reasons.append(f"Declared trade hint ({hint}) for {code}")
            break
    return reasons


def default_expected_output_document_type(canonical_requirement_code: str) -> str:
    """Stable document-type hint for vault / evidence (not a placeholder label)."""
    return f"certificate_{canonical_requirement_code}"
