"""
Canonical compliance requirement codes (internal snake_case) and normalization.

All new code should use normalize_requirement_code() so legacy catalog/UI variants
do not spread through routing, work orders, or contractor capability fields.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Optional, Tuple

# Canonical codes used across booking, work orders, and contractor.supported_requirement_codes.
# Domestic smoke / CO / fire alarm & detection testing: canonical ``smoke_heat_alarms`` (Phase 2).
# Legacy slugs ``fire_detection``, ``smoke_alarms``, ``co_alarms``, ``fire_alarm`` normalize here.
CANONICAL_REQUIREMENT_CODES: FrozenSet[str] = frozenset(
    {
        "gas_safety",
        "eicr",
        "epc",
        "smoke_heat_alarms",
        "legionella",
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
        "lead_testing",
    }
)

# Documented low-risk storage slugs (Phase 1–2 alias alignment). Used for audit severity only.
DOCUMENTED_LOW_RISK_ALIAS_SLUGS: FrozenSet[str] = frozenset(
    {
        "gas_safety_certificate",
        "fire_alarm",
        "fire_detection",
        "smoke_alarms",
        "co_alarms",
        "right_to_rent_checks",
        "deposit_prescribed_info",
        "tenancy_deposit_protection",
        "lead_testing_scotland",
    }
)


def is_documented_low_risk_alias_slug(raw_slug: str) -> bool:
    """True when ``raw_slug`` is a Phase-1 legacy slug listed in the decision record (alias cleanup only)."""
    s = str(raw_slug or "").strip().lower().replace(" ", "_")
    return s in DOCUMENTED_LOW_RISK_ALIAS_SLUGS


# Map arbitrary legacy or external strings -> canonical code (lowercase keys).
_LEGACY_ALIASES: Dict[str, str] = {
    # gas
    "gas": "gas_safety",
    "gas safety": "gas_safety",
    "gas_safety": "gas_safety",
    "gas_safety_certificate": "gas_safety",
    "cp12": "gas_safety",
    "gassafety": "gas_safety",
    # electrical
    "eicr": "eicr",
    "electrical installation condition report": "eicr",
    "electrical": "eicr",
    # energy
    "epc": "epc",
    "energy performance certificate": "epc",
    # Domestic alarms / detection / testing — canonical smoke_heat_alarms (Phase 2).
    "fire_alarm": "smoke_heat_alarms",
    "fire alarm": "smoke_heat_alarms",
    "fire_alarm_inspection": "smoke_heat_alarms",
    "fire detection": "smoke_heat_alarms",
    "fire_detection": "smoke_heat_alarms",
    "smoke_alarm": "smoke_heat_alarms",
    "smoke_alarms": "smoke_heat_alarms",
    "smoke alarms": "smoke_heat_alarms",
    "co_alarm": "smoke_heat_alarms",
    "co_alarms": "smoke_heat_alarms",
    "carbon_monoxide": "smoke_heat_alarms",
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
    "deposit_prescribed_info": "deposit_pi",
    "tenancy_deposit_protection": "deposit_pi",
    "right_to_rent": "right_to_rent",
    "right_to_rent_checks": "right_to_rent",
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
    "lead_testing": "lead_testing",
    "lead_testing_scotland": "lead_testing",
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
        "smoke_heat_alarms",
        "legionella",
        "fire_risk_assessment",
        "hmo_fire_risk",
        "hmo_fire_risk_evidence",
        "portable_appliance_test",
    }
)
