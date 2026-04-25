"""
Controlled canonical document taxonomy for Compliance Vault Pro evidence matching.

Production logic must only use these constants (or explicit jurisdiction variants),
not ad-hoc free-text document types, when making satisfy / gap / authority decisions.
"""
from __future__ import annotations

import re
from typing import AbstractSet, Dict, FrozenSet, Tuple

# --- Canonical document families (upper snake, stable API / persistence) ---
CANONICAL_EPC = "EPC"
CANONICAL_EICR = "EICR"
CANONICAL_GAS_SAFETY = "GAS_SAFETY"
CANONICAL_FIRE_ALARM_INSPECTION = "FIRE_ALARM_INSPECTION"
CANONICAL_LEGIONELLA_RISK_ASSESSMENT = "LEGIONELLA_RISK_ASSESSMENT"
CANONICAL_PAT_TEST = "PAT_TEST"
CANONICAL_HMO_LICENCE = "HMO_LICENCE"
CANONICAL_LANDLORD_REGISTRATION = "LANDLORD_REGISTRATION"
CANONICAL_DEPOSIT_PROTECTION = "DEPOSIT_PROTECTION"
CANONICAL_RIGHT_TO_RENT_EVIDENCE = "RIGHT_TO_RENT_EVIDENCE"
CANONICAL_TENANCY_AGREEMENT = "TENANCY_AGREEMENT"
CANONICAL_OCCUPATION_CONTRACT = "OCCUPATION_CONTRACT"
CANONICAL_SMOKE_CO_ALARM_EVIDENCE = "SMOKE_CO_ALARM_EVIDENCE"
CANONICAL_FIRE_RISK_ASSESSMENT = "FIRE_RISK_ASSESSMENT"
CANONICAL_UNKNOWN = "UNKNOWN"

ALL_CANONICAL_FAMILIES: Tuple[str, ...] = (
    CANONICAL_EPC,
    CANONICAL_EICR,
    CANONICAL_GAS_SAFETY,
    CANONICAL_FIRE_ALARM_INSPECTION,
    CANONICAL_LEGIONELLA_RISK_ASSESSMENT,
    CANONICAL_PAT_TEST,
    CANONICAL_HMO_LICENCE,
    CANONICAL_LANDLORD_REGISTRATION,
    CANONICAL_DEPOSIT_PROTECTION,
    CANONICAL_RIGHT_TO_RENT_EVIDENCE,
    CANONICAL_TENANCY_AGREEMENT,
    CANONICAL_OCCUPATION_CONTRACT,
    CANONICAL_SMOKE_CO_ALARM_EVIDENCE,
    CANONICAL_FIRE_RISK_ASSESSMENT,
    CANONICAL_UNKNOWN,
)

# --- Match outcomes (persisted on documents + mirrored in evidence_authority) ---
MATCH_OUTCOME_MATCH_CONFIRMED = "MATCH_CONFIRMED"
MATCH_OUTCOME_MATCH_LIKELY = "MATCH_LIKELY"
MATCH_OUTCOME_MISMATCH_SUSPECTED = "MISMATCH_SUSPECTED"
MATCH_OUTCOME_UNKNOWN_TYPE = "UNKNOWN_TYPE"
MATCH_OUTCOME_NEEDS_ADMIN_REVIEW = "NEEDS_ADMIN_REVIEW"

# --- Reason codes (machine-stable) ---
REASON_CODE_NONE = "NONE"
REASON_CODE_STRONG_FAMILY_MISMATCH = "STRONG_FAMILY_MISMATCH"
REASON_CODE_DECLARED_TYPE_MISMATCH = "DECLARED_TYPE_MISMATCH"
REASON_CODE_FILENAME_HINT_MISMATCH = "FILENAME_HINT_MISMATCH"
REASON_CODE_EXTRACTION_FAMILY_MISMATCH = "EXTRACTION_FAMILY_MISMATCH"
REASON_CODE_EXTRACTION_AMBIGUOUS = "EXTRACTION_AMBIGUOUS"
REASON_CODE_NO_REQUIREMENT_LINK = "NO_REQUIREMENT_LINK"
REASON_CODE_ADMIN_OVERRIDE_MATCH = "ADMIN_OVERRIDE_MATCH"
REASON_CODE_LOW_SIGNAL = "LOW_SIGNAL"

# --- Policy: upload-time blocking (HTTP 400) vs quarantine (persist + authority) ---
POLICY_BLOCK_UPLOAD = "BLOCK_UPLOAD"
POLICY_QUARANTINE = "QUARANTINE"
POLICY_ACCEPT_PENDING = "ACCEPT_PENDING"
POLICY_ACCEPT_CONFIRMED = "ACCEPT_CONFIRMED"

# --- Legacy rows predating engine persistence (admin / audit visibility only) ---
EVIDENCE_MATCH_LEGACY_STATE_UNCLASSIFIED_PRE_ENGINE = "UNCLASSIFIED_PRE_ENGINE"
REASON_CODE_LEGACY_UNCLASSIFIED = "LEGACY_UNCLASSIFIED"


def _norm_key(raw: str) -> str:
    s = (raw or "").strip().lower().replace("-", "_")
    return re.sub(r"\s+", "_", s)


# requirement_type / requirement_code (normalized) -> expected canonical families
REQUIREMENT_TO_EXPECTED_CANONICAL: Dict[str, FrozenSet[str]] = {
    "gas_safety": frozenset({CANONICAL_GAS_SAFETY}),
    "gas_safety_certificate": frozenset({CANONICAL_GAS_SAFETY}),
    "cp12": frozenset({CANONICAL_GAS_SAFETY}),
    "eicr": frozenset({CANONICAL_EICR}),
    "electrical_installation_condition_report": frozenset({CANONICAL_EICR}),
    "epc": frozenset({CANONICAL_EPC}),
    "energy_performance": frozenset({CANONICAL_EPC}),
    "fire_alarm": frozenset({CANONICAL_FIRE_ALARM_INSPECTION, CANONICAL_SMOKE_CO_ALARM_EVIDENCE}),
    "fire_detection": frozenset({CANONICAL_FIRE_ALARM_INSPECTION, CANONICAL_SMOKE_CO_ALARM_EVIDENCE}),
    "smoke_alarm": frozenset({CANONICAL_SMOKE_CO_ALARM_EVIDENCE}),
    "co_alarm": frozenset({CANONICAL_SMOKE_CO_ALARM_EVIDENCE}),
    "legionella": frozenset({CANONICAL_LEGIONELLA_RISK_ASSESSMENT}),
    "legionella_risk_assessment": frozenset({CANONICAL_LEGIONELLA_RISK_ASSESSMENT}),
    "pat_testing": frozenset({CANONICAL_PAT_TEST}),
    "pat": frozenset({CANONICAL_PAT_TEST}),
    "hmo_license": frozenset({CANONICAL_HMO_LICENCE}),
    "hmo_licence": frozenset({CANONICAL_HMO_LICENCE}),
    "landlord_registration": frozenset({CANONICAL_LANDLORD_REGISTRATION}),
    "deposit_protection": frozenset({CANONICAL_DEPOSIT_PROTECTION}),
    "right_to_rent": frozenset({CANONICAL_RIGHT_TO_RENT_EVIDENCE}),
    "right_to_rent_check": frozenset({CANONICAL_RIGHT_TO_RENT_EVIDENCE}),
    "tenancy_agreement": frozenset({CANONICAL_TENANCY_AGREEMENT}),
    "occupation_contract": frozenset({CANONICAL_OCCUPATION_CONTRACT}),
    "wales_occupation_contract": frozenset({CANONICAL_OCCUPATION_CONTRACT}),
    "hmo_fire_risk": frozenset({CANONICAL_FIRE_RISK_ASSESSMENT}),
    "fire_risk_assessment": frozenset({CANONICAL_FIRE_RISK_ASSESSMENT}),
}


def expected_canonical_families_for_requirement(requirement: Dict) -> AbstractSet[str]:
    """Return expected canonical evidence families for this requirement row (may be empty)."""
    keys = (
        _norm_key(str(requirement.get("requirement_type") or "")),
        _norm_key(str(requirement.get("requirement_code") or "")),
    )
    for k in keys:
        if not k:
            continue
        fam = REQUIREMENT_TO_EXPECTED_CANONICAL.get(k)
        if fam:
            return fam
    return frozenset()
