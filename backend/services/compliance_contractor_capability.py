"""
Requirement-to-contractor capability: structured matching for compliance execution work orders.

Used by assignment validation, assignable lists, and the recommendation engine.
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


def parse_execution_capabilities(contractor: Dict[str, Any]) -> Set[str]:
    """Return set of {'maintenance', 'compliance'} implied by contractor.execution_capabilities."""
    raw = (contractor.get("execution_capabilities") or EXECUTION_CAPABILITY_MAINTENANCE).strip().lower()
    if raw == EXECUTION_CAPABILITY_BOTH:
        return {EXECUTION_CAPABILITY_MAINTENANCE, EXECUTION_CAPABILITY_COMPLIANCE}
    if raw == EXECUTION_CAPABILITY_COMPLIANCE:
        return {EXECUTION_CAPABILITY_COMPLIANCE}
    return {EXECUTION_CAPABILITY_MAINTENANCE}


def contractor_is_compliance_capable(contractor: Dict[str, Any]) -> bool:
    return EXECUTION_CAPABILITY_COMPLIANCE in parse_execution_capabilities(contractor)


def contractor_is_maintenance_capable(contractor: Dict[str, Any]) -> bool:
    return EXECUTION_CAPABILITY_MAINTENANCE in parse_execution_capabilities(contractor)


def _norm_list(vals: Optional[List[str]]) -> List[str]:
    return [str(x).strip().lower() for x in (vals or []) if str(x).strip()]


def supported_codes_normalized(contractor: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for x in contractor.get("supported_requirement_codes") or []:
        c = normalize_requirement_code(str(x))
        if c:
            out.add(c)
    return out


def contractor_qualifies_for_requirement(contractor: Dict[str, Any], canonical_requirement_code: str) -> bool:
    """
    True if contractor explicitly lists the code or matches credential/trade spec for that requirement.
    """
    code = (canonical_requirement_code or "").strip().lower()
    if not code:
        return False
    if code in supported_codes_normalized(contractor):
        return True
    spec = REQUIREMENT_EXECUTION_SPECS.get(code) or {"credential_hints": [], "trade_hints": []}
    creds = _norm_list(contractor.get("credentials"))
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


def compliance_match_reasons(contractor: Dict[str, Any], canonical_requirement_code: str) -> List[str]:
    """Human-readable reasons for compliance qualification (for recommendation UI)."""
    code = (canonical_requirement_code or "").strip().lower()
    reasons: List[str] = []
    if code in supported_codes_normalized(contractor):
        reasons.append(f"Listed capability for requirement {code}")
        return reasons
    spec = REQUIREMENT_EXECUTION_SPECS.get(code) or {}
    creds = _norm_list(contractor.get("credentials"))
    trades = _norm_list(contractor.get("trade_types"))
    for hint in spec.get("credential_hints") or []:
        h = hint.lower()
        if any(h in cr or cr in h for cr in creds):
            reasons.append(f"Credential match ({hint}) for {code}")
            break
    for hint in spec.get("trade_hints") or []:
        h = hint.lower()
        if any(h in tr or tr in h for tr in trades):
            reasons.append(f"Trade alignment ({hint}) for {code}")
            break
    return reasons


def default_expected_output_document_type(canonical_requirement_code: str) -> str:
    """Stable document-type hint for vault / evidence (not a placeholder label)."""
    return f"certificate_{canonical_requirement_code}"
