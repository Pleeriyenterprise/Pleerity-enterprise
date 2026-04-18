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
from typing import Any, Dict, List, Optional, Set, Tuple

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
    client_surface_visible_override: Optional[bool] = None
    action_links: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    why_it_matters_short: Optional[str] = None
    why_it_matters_long: Optional[str] = None
    why_it_matters_by_jurisdiction: Optional[Dict[str, Any]] = None


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


def apply_published_registry_entries_to_plan(
    items: List["RequirementPlanItem"],
    portfolio_label: str,
    entries: Optional[Dict[str, Any]],
    *,
    property_doc: Optional[Dict[str, Any]] = None,
) -> List["RequirementPlanItem"]:
    """
    Merge active published registry entries onto planner output (same shapes as Mongo drafts).

    ``entries`` maps ``CANONICAL|SCOPE`` (or similar stable keys) to draft-shaped dicts with at least
    ``canonical_code``, ``scope_key``, ``identity``, ``classification``, ``frequency``, ``jurisdiction``.
    """
    if not entries or not isinstance(entries, dict):
        return items
    from services.compliance_registry_admin_service import (
        draft_applies_to_portfolio_label,
        draft_overlay_specificity,
        merge_draft_overlay_onto_plan_row,
        plan_types_for_draft_canonical,
    )
    from services.compliance_registry_conditions import property_matches_registry_conditions

    best: Dict[str, Tuple[int, Dict[str, Any]]] = {}
    for _key, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        cc = str(entry.get("canonical_code") or "").strip().upper()
        if not cc or not draft_applies_to_portfolio_label(entry, portfolio_label):
            continue
        if not property_matches_registry_conditions(property_doc, entry.get("conditions")):
            continue
        spec = draft_overlay_specificity(entry)
        for rt in plan_types_for_draft_canonical(cc):
            prev = best.get(rt)
            if prev is None or spec > prev[0]:
                best[rt] = (spec, entry)

    merged: List[RequirementPlanItem] = []
    for item in items:
        rt = (item.requirement_type or "").strip().lower()
        match = best.get(rt)
        if not match:
            merged.append(item)
            continue
        entry = match[1]
        prod_row = {
            "description": item.description,
            "frequency_days": item.frequency_days,
            "warning_days": item.warning_days,
            "compliance_requirement_class": item.compliance_requirement_class,
            "client_surface_visible": item.client_surface_visible_override,
            "action_links": list(item.action_links),
            "why_it_matters_short": item.why_it_matters_short,
            "why_it_matters_long": item.why_it_matters_long,
            "why_it_matters_by_jurisdiction": item.why_it_matters_by_jurisdiction,
        }
        m = merge_draft_overlay_onto_plan_row(prod_row, entry)
        cls = str(m.get("compliance_requirement_class") or item.compliance_requirement_class).strip().upper()
        if cls not in (REQUIREMENT_CLASS_DOCUMENT, REQUIREMENT_CLASS_JOB, REQUIREMENT_CLASS_OBLIGATION, REQUIREMENT_CLASS_SYSTEM):
            cls = item.compliance_requirement_class
        tracked = cls in (REQUIREMENT_CLASS_DOCUMENT, REQUIREMENT_CLASS_JOB)
        merged.append(
            RequirementPlanItem(
                requirement_type=item.requirement_type,
                requirement_code=item.requirement_code,
                description=str(m.get("description", item.description)),
                frequency_days=int(m.get("frequency_days", item.frequency_days)),
                warning_days=int(m.get("warning_days", item.warning_days)),
                portfolio_jurisdiction_label=item.portfolio_jurisdiction_label,
                compliance_requirement_class=cls,
                is_tracked=tracked,
                catalog_keys=item.catalog_keys,
                client_surface_visible_override=(
                    bool(m.get("client_surface_visible")) if m.get("client_surface_visible") is not None else None
                ),
                action_links=tuple(
                    dict(x) for x in (m.get("action_links") or []) if isinstance(x, dict)
                ),
                why_it_matters_short=(
                    str(m.get("why_it_matters_short") or "").strip()
                    if str(m.get("why_it_matters_short") or "").strip()
                    else None
                ),
                why_it_matters_long=(
                    str(m.get("why_it_matters_long") or "").strip()
                    if str(m.get("why_it_matters_long") or "").strip()
                    else None
                ),
                why_it_matters_by_jurisdiction=(
                    m.get("why_it_matters_by_jurisdiction")
                    if isinstance(m.get("why_it_matters_by_jurisdiction"), dict)
                    else None
                ),
            )
        )
    return merged


def _freq_from_rule(scoring_jurisdiction: str, canonical_code: str, default_days: int, default_warn: int) -> tuple:
    spec = get_rule(scoring_jurisdiction, canonical_code)
    if spec:
        return int(spec.frequency_days), int(spec.warning_days)
    return default_days, default_warn


def _portfolio_region_key(portfolio_label: Optional[str]) -> str:
    s = (portfolio_label or "").strip().lower()
    if "scotland" in s:
        return "SCOTLAND"
    if "northern ireland" in s or "northern_ireland" in s:
        return "NORTHERN_IRELAND"
    if "wales" in s and "england" not in s:
        return "WALES"
    return "ENGLAND"


def resolve_published_entry_for_requirement(
    *,
    published_registry_entries: Optional[Dict[str, Any]],
    requirement_type: str,
    portfolio_label: str,
    property_doc: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Pick the best matching published entry for one requirement_type + jurisdiction label."""
    if not isinstance(published_registry_entries, dict) or not published_registry_entries:
        return None
    from services.compliance_registry_admin_service import (
        draft_applies_to_portfolio_label,
        draft_overlay_specificity,
        plan_types_for_draft_canonical,
    )
    from services.compliance_registry_conditions import property_matches_registry_conditions

    rt = (requirement_type or "").strip().lower()
    best: Optional[Tuple[int, Dict[str, Any]]] = None
    for entry in published_registry_entries.values():
        if not isinstance(entry, dict):
            continue
        cc = str(entry.get("canonical_code") or "").strip().upper()
        if not cc:
            continue
        if rt not in plan_types_for_draft_canonical(cc):
            continue
        if not draft_applies_to_portfolio_label(entry, portfolio_label):
            continue
        if not property_matches_registry_conditions(property_doc, entry.get("conditions")):
            continue
        spec = draft_overlay_specificity(entry)
        if best is None or spec > best[0]:
            best = (spec, entry)
    return best[1] if best else None


def resolve_effective_why_it_matters(
    *,
    entry: Optional[Dict[str, Any]],
    portfolio_label: str,
) -> Dict[str, Optional[str]]:
    """Resolve short/long why-it-matters from entry using jurisdiction override then defaults."""
    if not isinstance(entry, dict):
        return {"why_it_matters_short": None, "why_it_matters_long": None}
    short = str(entry.get("why_it_matters_short") or entry.get("why_it_matters") or "").strip() or None
    long_text = str(entry.get("why_it_matters_long") or "").strip() or None
    by_j = entry.get("why_it_matters_by_jurisdiction")
    if isinstance(by_j, dict):
        reg = _portfolio_region_key(portfolio_label)
        ov = by_j.get(reg)
        if isinstance(ov, dict):
            ov_short = str(ov.get("short") or "").strip()
            ov_long = str(ov.get("long") or "").strip()
            if ov_short:
                short = ov_short
            if ov_long:
                long_text = ov_long
    return {"why_it_matters_short": short, "why_it_matters_long": long_text}


def build_requirement_plan_for_property(
    property_doc: Dict,
    client_doc: Optional[Dict],
    *,
    published_registry_entries: Optional[Dict[str, Any]] = None,
) -> List[RequirementPlanItem]:
    """
    Deterministic ordered plan for one property. Caller must not mix properties.

    Optional ``published_registry_entries`` merges the active published registry snapshot onto plan
    rows (same overlay semantics as admin draft preview); it does not add net-new requirement types.
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

    if published_registry_entries:
        out = apply_published_registry_entries_to_plan(
            out,
            portfolio,
            published_registry_entries,
            property_doc=property_doc,
        )

    return out
