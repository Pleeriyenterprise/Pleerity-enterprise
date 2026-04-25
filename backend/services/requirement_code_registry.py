"""
Canonical compliance requirement codes (internal snake_case) and normalization.

All new code should use normalize_requirement_code() so legacy catalog/UI variants
do not spread through routing, work orders, or contractor capability fields.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Optional, Tuple

# Canonical codes used across booking, work orders, and contractor.supported_requirement_codes.
# Aligned with requirements_catalog seeds where applicable; fire_detection subsumes legacy fire_alarm.
CANONICAL_REQUIREMENT_CODES: FrozenSet[str] = frozenset(
    {
        "gas_safety",
        "eicr",
        "epc",
        "fire_detection",
        "legionella",
        "smoke_alarms",
        "co_alarms",
        "fire_risk_assessment",
        "hmo_fire_risk",
        "hmo_fire_risk_evidence",
        "portable_appliance_test",
        "hmo_license",
        "property_licence",
        "selective_license",
        "landlord_registration",
        "scotland_landlord_registration",
        "occupation_contract",
        "wales_occupation_contract",
        "deposit_pi",
        "right_to_rent",
        "rent_smart_wales",
        "landlord_registration_ni",
        "how_to_rent",
        "tenancy_agreement",
    }
)

# Map arbitrary legacy or external strings -> canonical code (lowercase keys).
_LEGACY_ALIASES: Dict[str, str] = {
    # gas
    "gas": "gas_safety",
    "gas safety": "gas_safety",
    "gas_safety": "gas_safety",
    "cp12": "gas_safety",
    "gassafety": "gas_safety",
    # electrical
    "eicr": "eicr",
    "electrical installation condition report": "eicr",
    "electrical": "eicr",
    # energy
    "epc": "epc",
    "energy performance certificate": "epc",
    # fire / detection (catalog used fire_alarm; canonical is fire_detection)
    "fire_alarm": "fire_detection",
    "fire alarm": "fire_detection",
    "fire_alarm_inspection": "fire_detection",
    "fire detection": "fire_detection",
    "fire_detection": "fire_detection",
    "smoke_alarm": "smoke_alarms",
    "smoke_alarms": "smoke_alarms",
    "smoke alarms": "smoke_alarms",
    "co_alarm": "co_alarms",
    "co_alarms": "co_alarms",
    "carbon_monoxide": "co_alarms",
    # legionella
    "legionella": "legionella",
    "legionnaires": "legionella",
    # other catalog codes
    "fire_risk_assessment": "fire_risk_assessment",
    "fire risk assessment": "fire_risk_assessment",
    "pat": "portable_appliance_test",
    "portable_appliance_test": "portable_appliance_test",
    "hmo_license": "hmo_license",
    "property_licence": "property_licence",
    "selective_license": "selective_license",
    "deposit_pi": "deposit_pi",
    "right_to_rent": "right_to_rent",
    "rent_smart_wales": "rent_smart_wales",
    "landlord_registration_ni": "landlord_registration_ni",
    "how_to_rent": "how_to_rent",
    "tenancy_agreement": "tenancy_agreement",
    "landlord_registration": "landlord_registration",
    "scotland_landlord_registration": "scotland_landlord_registration",
    "hmo_fire_risk": "hmo_fire_risk",
    "hmo_fire_risk_evidence": "hmo_fire_risk_evidence",
    "occupation_contract": "occupation_contract",
    "wales_occupation_contract": "wales_occupation_contract",
}


def _strip_key(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def normalize_requirement_code(raw: Optional[str]) -> Optional[str]:
    """
    Return canonical snake_case code or None if unknown.
    Accepts catalog codes, titles, and common aliases.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    key_snake = s.lower().replace(" ", "_").replace("-", "_")
    while "__" in key_snake:
        key_snake = key_snake.replace("__", "_")
    if key_snake in CANONICAL_REQUIREMENT_CODES:
        return key_snake
    if key_snake in _LEGACY_ALIASES:
        return _LEGACY_ALIASES[key_snake]
    spaced = _strip_key(s.replace("_", " "))
    if spaced in _LEGACY_ALIASES:
        return _LEGACY_ALIASES[spaced]
    # Title-like "Gas Safety (CP12)"
    compact = spaced.replace("(", " ").replace(")", " ").replace(".", " ")
    if compact in _LEGACY_ALIASES:
        return _LEGACY_ALIASES[compact]
    return None


def normalize_requirement_code_strict(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (canonical, error_message). Use when invalid codes must be rejected.
    """
    canon = normalize_requirement_code(raw)
    if not raw or not str(raw).strip():
        return None, "requirement_code is required"
    if canon is None:
        return None, f"Unknown or unsupported requirement_code: {raw!r}"
    return canon, None


def is_bookable_compliance_requirement(code: Optional[str]) -> bool:
    """Requirements we support for compliance execution / inspection booking v1."""
    if not code:
        return False
    return code in _BOOKABLE_COMPLIANCE_CODES


_BOOKABLE_COMPLIANCE_CODES: FrozenSet[str] = frozenset(
    {
        "gas_safety",
        "eicr",
        "epc",
        "fire_detection",
        "legionella",
        "fire_risk_assessment",
        "hmo_fire_risk",
        "hmo_fire_risk_evidence",
        "portable_appliance_test",
        "smoke_alarms",
        "co_alarms",
    }
)
