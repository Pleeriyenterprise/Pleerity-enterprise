"""
Single source of truth for per-property compliance requirement *generation*.

Each property gets its own plan from (property_doc, client_doc) — no cross-property merge.
Jurisdiction-specific applicability uses property.jurisdiction with client default fallback
(see compliance_rules_registry.resolve_portfolio_jurisdiction).

Cadence hints come from compliance_rules_registry where a scoring code exists; otherwise
defaults match legacy provisioning constants.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from services.compliance_rules_registry import (
    apply_location_rules_enabled,
    get_rule,
    iter_core_rules,
    portfolio_jurisdiction_label,
    scoring_jurisdiction_for_property,
)
from services.requirement_catalog import (
    DEPOSIT_PRESCRIBED_INFO,
    EICR_CERT,
    EPC_CERT,
    GAS_SAFETY_CERT,
    HOW_TO_RENT,
    HMO_FIRE_RISK,
    HMO_FIRE_RISK_EVIDENCE,
    PROPERTY_LICENCE,
    SCOTLAND_LANDLORD_REGISTRATION,
    TENANCY_AGREEMENT,
    WALES_OCCUPATION_CONTRACT,
    get_applicable_requirements,
)

# Align with compliance_requirement_engine.REQUIREMENT_CLASS_*
REQUIREMENT_CLASS_DOCUMENT = "DOCUMENT"
REQUIREMENT_CLASS_JOB = "JOB"
REQUIREMENT_CLASS_OBLIGATION = "OBLIGATION"
REQUIREMENT_CLASS_SYSTEM = "SYSTEM"

REQUIREMENT_GENERATION_SOURCE_REGISTRY = "catalog_registry"

# London / Manchester selective licensing (England & Wales contexts only) — legacy LOCATION_RULES
_LOCATION_SELECTIVE = {
    "LONDON": ("selective_license", "Selective licensing (local authority)", 1825),
    "MANCHESTER": ("selective_license", "Selective licensing (local authority)", 1825),
}

_HMO_EXTRA_DOCUMENT = [
    ("fire_risk_assessment", "Fire risk assessment", 365),
]
_HMO_EXTRA_JOB = [
    ("emergency_lighting", "Emergency lighting test", 365),
    ("fire_extinguisher", "Fire extinguisher service", 365),
]

_COMMUNAL_JOB = [
    ("communal_cleaning", "Communal area cleaning schedule", 30),
    ("communal_fire_doors", "Fire door inspection (communal)", 365),
]


@dataclass(frozen=True)
class RequirementPlanItem:
    """One row to create for a single property (idempotent by requirement_type per property)."""

    requirement_type: str
    requirement_code: str
    description: str
    frequency_days: int
    warning_days: int
    portfolio_jurisdiction_label: str
    compliance_requirement_class: str
    is_tracked: bool
    catalog_keys: Tuple[str, ...] = field(default_factory=tuple)


def _norm_pt(property_doc: Dict) -> str:
    return (property_doc.get("property_type") or "residential").strip().upper()


def _boolish(val, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().upper()
    if s in ("NO", "FALSE", "0", ""):
        return False
    if s in ("YES", "TRUE", "1"):
        return True
    return bool(s)


def _freq_from_rule(scoring_jurisdiction: str, canonical_code: str, default_days: int, default_warn: int) -> tuple:
    spec = get_rule(scoring_jurisdiction, canonical_code)
    if spec:
        return int(spec.frequency_days), int(spec.warning_days)
    return default_days, default_warn


def build_requirement_plan_for_property(
    property_doc: Dict,
    client_doc: Optional[Dict],
) -> List[RequirementPlanItem]:
    """
    Deterministic ordered plan for one property. Caller must not mix properties.
    """
    portfolio = portfolio_jurisdiction_label(property_doc, client_doc)
    sj = scoring_jurisdiction_for_property(property_doc, client_doc)
    prop_type = _norm_pt(property_doc)
    is_hmo = _boolish(property_doc.get("is_hmo"), False) or prop_type == "HMO"
    hmo_license_required = _boolish(property_doc.get("hmo_license_required"), False)
    has_gas = _boolish(property_doc.get("has_gas_supply"), True)
    building_age_years = property_doc.get("building_age_years")
    has_communal = _boolish(property_doc.get("has_communal_areas"), False)
    local_authority = (property_doc.get("local_authority") or "").strip().upper()

    seen_types: Set[str] = set()
    out: List[RequirementPlanItem] = []

    def add(
        rtype: str,
        code: str,
        desc: str,
        freq: int,
        warn: int,
        cls: str,
        *,
        catalog_keys: Tuple[str, ...] = (),
    ) -> None:
        if rtype in seen_types:
            return
        seen_types.add(rtype)
        tracked = cls in (REQUIREMENT_CLASS_DOCUMENT, REQUIREMENT_CLASS_JOB)
        out.append(
            RequirementPlanItem(
                requirement_type=rtype,
                requirement_code=code.strip().lower(),
                description=desc,
                frequency_days=freq,
                warning_days=warn,
                portfolio_jurisdiction_label=portfolio,
                compliance_requirement_class=cls,
                is_tracked=tracked,
                catalog_keys=catalog_keys,
            )
        )

    # --- 1) Core cadence pack (jurisdiction-specific SLA/frequency from compliance_rules_registry) ---
    for spec in iter_core_rules(sj):
        if spec.condition == "has_gas_supply" and not has_gas:
            continue
        frequency_days = int(spec.frequency_days)
        if spec.storage_type == "eicr" and building_age_years and spec.frequency_by_age:
            if int(building_age_years) > 50:
                frequency_days = int(spec.frequency_by_age.get("old", frequency_days))
        ck: Tuple[str, ...] = ()
        if spec.storage_type == "gas_safety":
            ck = (GAS_SAFETY_CERT,)
        elif spec.storage_type == "eicr":
            ck = (EICR_CERT,)
        elif spec.storage_type == "epc":
            ck = (EPC_CERT,)
        add(
            spec.storage_type,
            spec.storage_type,
            spec.description,
            frequency_days,
            int(spec.warning_days),
            REQUIREMENT_CLASS_DOCUMENT,
            catalog_keys=ck,
        )

    applicable = set(get_applicable_requirements(property_doc, client_doc))

    # --- 2) Licence / HMO registration (catalog expander; not a duplicate "HMO" meta-row) ---
    if PROPERTY_LICENCE in applicable:
        if is_hmo:
            add(
                "hmo_license",
                "hmo_license",
                "HMO licence",
                1825,
                45,
                REQUIREMENT_CLASS_DOCUMENT,
                catalog_keys=(PROPERTY_LICENCE,),
            )
        else:
            add(
                "property_licence",
                "property_licence",
                "Property licence",
                1825,
                45,
                REQUIREMENT_CLASS_DOCUMENT,
                catalog_keys=(PROPERTY_LICENCE,),
            )

    # --- 3) Jurisdiction / tenancy obligations (catalog-driven) ---
    if TENANCY_AGREEMENT in applicable:
        add(
            "tenancy_agreement",
            "tenancy_agreement",
            "Tenancy agreement",
            365,
            30,
            REQUIREMENT_CLASS_OBLIGATION,
            catalog_keys=(TENANCY_AGREEMENT,),
        )
    if HOW_TO_RENT in applicable:
        add(
            "how_to_rent",
            "how_to_rent",
            "How to Rent guide",
            365,
            30,
            REQUIREMENT_CLASS_OBLIGATION,
            catalog_keys=(HOW_TO_RENT,),
        )
    if DEPOSIT_PRESCRIBED_INFO in applicable:
        add(
            "deposit_pi",
            "deposit_pi",
            "Deposit prescribed information",
            365,
            30,
            REQUIREMENT_CLASS_OBLIGATION,
            catalog_keys=(DEPOSIT_PRESCRIBED_INFO,),
        )

    if HMO_FIRE_RISK_EVIDENCE in applicable:
        fd, fw = _freq_from_rule(sj, "HMO_FIRE_RISK", 365, 30)
        add(
            "hmo_fire_risk_evidence",
            "hmo_fire_risk_evidence",
            "HMO fire safety evidence",
            fd,
            fw,
            REQUIREMENT_CLASS_DOCUMENT,
            catalog_keys=(HMO_FIRE_RISK_EVIDENCE, HMO_FIRE_RISK),
        )

    if SCOTLAND_LANDLORD_REGISTRATION in applicable:
        fd, fw = _freq_from_rule(sj, "LANDLORD_REGISTRATION", 1095, 45)
        add(
            "scotland_landlord_registration",
            "scotland_landlord_registration",
            "Landlord registration (Scotland)",
            fd,
            fw,
            REQUIREMENT_CLASS_DOCUMENT,
            catalog_keys=(SCOTLAND_LANDLORD_REGISTRATION,),
        )

    if WALES_OCCUPATION_CONTRACT in applicable:
        fd, fw = _freq_from_rule(sj, "OCCUPATION_CONTRACT", 365, 30)
        add(
            "wales_occupation_contract",
            "wales_occupation_contract",
            "Occupation contract (Wales)",
            fd,
            fw,
            REQUIREMENT_CLASS_OBLIGATION,
            catalog_keys=(WALES_OCCUPATION_CONTRACT,),
        )

    # --- 4) HMO set expansion (additional operational / safety rows) ---
    if is_hmo or prop_type == "HMO":
        for rtype, desc, days in _HMO_EXTRA_DOCUMENT:
            if rtype == "fire_risk_assessment" and "hmo_fire_risk_evidence" in seen_types:
                continue
            add(rtype, rtype, desc, days, 30, REQUIREMENT_CLASS_DOCUMENT, catalog_keys=(HMO_FIRE_RISK,))
        if hmo_license_required and "hmo_license" not in seen_types:
            add(
                "hmo_license",
                "hmo_license",
                "HMO licence",
                1825,
                45,
                REQUIREMENT_CLASS_DOCUMENT,
                catalog_keys=(PROPERTY_LICENCE,),
            )
        for rtype, desc, days in _HMO_EXTRA_JOB:
            add(rtype, rtype, desc, days, 30, REQUIREMENT_CLASS_JOB)

    # --- 5) Communal (operational jobs) ---
    if has_communal:
        for rtype, desc, days in _COMMUNAL_JOB:
            add(rtype, rtype, desc, days, 30, REQUIREMENT_CLASS_JOB)

    # --- 6) Local authority selective licensing (EW portfolio contexts only) ---
    if apply_location_rules_enabled(sj) and local_authority in _LOCATION_SELECTIVE:
        rtype, desc, days = _LOCATION_SELECTIVE[local_authority]
        add(rtype, rtype, desc, days, 45, REQUIREMENT_CLASS_DOCUMENT, catalog_keys=(PROPERTY_LICENCE,))

    return out
