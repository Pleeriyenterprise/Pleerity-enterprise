"""
Documentation-backed fallback map: storage slug / canonical code → lifecycle semantics.

Sources: REQUIREMENT_AND_LIFECYCLE_NON_EXPIRY_AUDIT_01, ADR_REQUIREMENT_LIFECYCLE_SEMANTICS,
REQUIREMENT_LIFECYCLE_REMEDIATION_READINESS_01.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from services.lifecycle_semantics_types import FieldContract, LifecycleSemantics

# (lifecycle_semantics, field_contract)
_LifecycleEntry = Tuple[LifecycleSemantics, FieldContract]

# Canonical storage slugs (lowercase) after normalize_requirement_code where applicable.
_FALLBACK_BY_STORAGE_SLUG: Dict[str, _LifecycleEntry] = {
    # Expiry-based certificates
    "gas_safety": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "eicr": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "epc": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "hmo_license": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "property_licence": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "selective_license": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "fire_risk_assessment": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "hmo_fire_risk": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "hmo_fire_risk_evidence": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "portable_appliance_test": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "fire_alarm": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    # Review-based assessments
    "legionella": (
        "REVIEW_BASED",
        FieldContract(
            requires_review_date=True,
            requires_next_review_date=False,
            does_not_expire=True,
        ),
    ),
    "lead_testing": (
        "REVIEW_BASED",
        FieldContract(requires_review_date=True, does_not_expire=True),
    ),
    "landlord_registration": (
        "REVIEW_BASED",
        FieldContract(requires_issue_date=True, does_not_expire=True),
    ),
    "scotland_landlord_registration": (
        "REVIEW_BASED",
        FieldContract(requires_issue_date=True, does_not_expire=True),
    ),
    "landlord_registration_ni": (
        "REVIEW_BASED",
        FieldContract(requires_issue_date=True, does_not_expire=True),
    ),
    "rent_smart_wales": (
        "REVIEW_BASED",
        FieldContract(requires_issue_date=True, does_not_expire=True),
    ),
    # Event-based / one-time evidence
    "smoke_heat_alarms": (
        "EVENT_BASED",
        FieldContract(requires_event_date=True, does_not_expire=True),
    ),
    "smoke_alarms": (
        "EVENT_BASED",
        FieldContract(requires_event_date=True, does_not_expire=True),
    ),
    "co_alarms": (
        "EVENT_BASED",
        FieldContract(requires_event_date=True, does_not_expire=True),
    ),
    "fire_detection": (
        "EVENT_BASED",
        FieldContract(requires_event_date=True, does_not_expire=True),
    ),
    # Declaration-based
    "deposit_pi": (
        "DECLARATION_BASED",
        FieldContract(requires_event_date=True, does_not_expire=True),
    ),
    "how_to_rent": (
        "DECLARATION_BASED",
        FieldContract(requires_event_date=True, does_not_expire=True),
    ),
    # Tenancy lifecycle
    "tenancy_agreement": (
        "TENANCY_LIFECYCLE",
        FieldContract(requires_tenancy_dates=True, does_not_expire=True),
    ),
    # Occupancy lifecycle
    "right_to_rent": (
        "OCCUPANCY_LIFECYCLE",
        FieldContract(requires_occupancy_dates=True, does_not_expire=True),
    ),
    "wales_occupation_contract": (
        "OCCUPANCY_LIFECYCLE",
        FieldContract(requires_occupancy_dates=True, does_not_expire=True),
    ),
    "occupation_contract": (
        "OCCUPANCY_LIFECYCLE",
        FieldContract(requires_occupancy_dates=True, does_not_expire=True),
    ),
    # Operational
    "fitness_for_human_habitation": (
        "OPERATIONAL",
        FieldContract(does_not_expire=True),
    ),
    "repairing_standard": (
        "OPERATIONAL",
        FieldContract(does_not_expire=True),
    ),
}

# Published registry canonical codes (uppercase)
_FALLBACK_BY_CANONICAL_CODE: Dict[str, _LifecycleEntry] = {
    "GAS_SAFETY": _FALLBACK_BY_STORAGE_SLUG["gas_safety"],
    "EICR": _FALLBACK_BY_STORAGE_SLUG["eicr"],
    "EPC": _FALLBACK_BY_STORAGE_SLUG["epc"],
    "HMO_LICENSING": _FALLBACK_BY_STORAGE_SLUG["hmo_license"],
    "HMO_LICENCE": _FALLBACK_BY_STORAGE_SLUG["hmo_license"],
    "PROPERTY_LICENCE": _FALLBACK_BY_STORAGE_SLUG["property_licence"],
    "LEGIONELLA": _FALLBACK_BY_STORAGE_SLUG["legionella"],
    "LEAD_TESTING": _FALLBACK_BY_STORAGE_SLUG["lead_testing"],
    "SMOKE_HEAT_ALARMS": _FALLBACK_BY_STORAGE_SLUG["smoke_heat_alarms"],
    "RIGHT_TO_RENT": _FALLBACK_BY_STORAGE_SLUG["right_to_rent"],
    "TENANCY_AGREEMENT": _FALLBACK_BY_STORAGE_SLUG["tenancy_agreement"],
    "TENANCY_DEPOSIT_PROTECTION": _FALLBACK_BY_STORAGE_SLUG["deposit_pi"],
    "HOW_TO_RENT": _FALLBACK_BY_STORAGE_SLUG["how_to_rent"],
    "WALES_OCCUPATION_CONTRACT": _FALLBACK_BY_STORAGE_SLUG["wales_occupation_contract"],
    "HMO_FIRE_RISK": _FALLBACK_BY_STORAGE_SLUG["hmo_fire_risk"],
    "PAT_TESTING": _FALLBACK_BY_STORAGE_SLUG["portable_appliance_test"],
    "PORTABLE_APPLIANCE_TEST": _FALLBACK_BY_STORAGE_SLUG["portable_appliance_test"],
    "FIRE_RISK_ASSESSMENT": _FALLBACK_BY_STORAGE_SLUG["fire_risk_assessment"],
    "SCOTLAND_LANDLORD_REGISTRATION": _FALLBACK_BY_STORAGE_SLUG["scotland_landlord_registration"],
    "LANDLORD_REGISTRATION_NI": _FALLBACK_BY_STORAGE_SLUG["landlord_registration_ni"],
    "RENT_SMART_WALES": _FALLBACK_BY_STORAGE_SLUG["rent_smart_wales"],
}

# Legacy catalog expiry_type → default semantics when slug unknown
_EXPIRY_TYPE_DEFAULTS: Dict[str, _LifecycleEntry] = {
    "EXPIRING": (
        "EXPIRY_BASED",
        FieldContract(requires_expiry_date=True, requires_issue_date=True),
    ),
    "NON_EXPIRING": (
        "EVENT_BASED",
        FieldContract(requires_event_date=True, does_not_expire=True),
    ),
    "EVENT_BASED": (
        "EVENT_BASED",
        FieldContract(requires_event_date=True, does_not_expire=True),
    ),
}

_DEFAULT_ENTRY: _LifecycleEntry = (
    "EVENT_BASED",
    FieldContract(requires_event_date=True, does_not_expire=True),
)


def vocabulary_family_for_semantics(semantics: LifecycleSemantics) -> str:
    return {
        "EXPIRY_BASED": "certificate_expiry",
        "REVIEW_BASED": "compliance_review",
        "EVENT_BASED": "event_completion",
        "DECLARATION_BASED": "declaration_record",
        "TENANCY_LIFECYCLE": "tenancy_lifecycle",
        "OCCUPANCY_LIFECYCLE": "occupancy_lifecycle",
        "OPERATIONAL": "operational_workflow",
    }.get(semantics, "event_completion")


def fallback_entry_for_storage_slug(slug: str) -> Optional[_LifecycleEntry]:
    key = str(slug or "").strip().lower().replace(" ", "_")
    if not key:
        return None
    return _FALLBACK_BY_STORAGE_SLUG.get(key)


def fallback_entry_for_canonical_code(code: str) -> Optional[_LifecycleEntry]:
    key = str(code or "").strip().upper().replace(" ", "_")
    if not key:
        return None
    return _FALLBACK_BY_CANONICAL_CODE.get(key)


def fallback_entry_from_expiry_type(expiry_type: Optional[str]) -> Optional[_LifecycleEntry]:
    if not expiry_type:
        return None
    return _EXPIRY_TYPE_DEFAULTS.get(str(expiry_type).strip().upper())


def fallback_entry_from_expects_expiry(expects_expiry: bool) -> _LifecycleEntry:
    if expects_expiry:
        return _EXPIRY_TYPE_DEFAULTS["EXPIRING"]
    return (
        "REVIEW_BASED",
        FieldContract(requires_review_date=True, does_not_expire=True),
    )


def default_fallback_entry() -> _LifecycleEntry:
    return _DEFAULT_ENTRY


def all_documented_storage_slugs() -> frozenset[str]:
    return frozenset(_FALLBACK_BY_STORAGE_SLUG.keys())


def all_documented_canonical_codes() -> frozenset[str]:
    return frozenset(_FALLBACK_BY_CANONICAL_CODE.keys())
