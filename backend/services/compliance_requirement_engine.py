"""
Compliance requirement engine metadata (categories, client visibility, fulfillment).

This layer is product/legal scaffolding: it does not encode statute text. It drives:
- Which requirement rows appear on the client Requirements surface vs stay internal-only
- Whether Command Centre / Today priority streams surface overdue / expiring / missing-document actions
- Primary fulfillment hints (document upload vs compliance job vs informational obligation)

Row overrides (optional Mongo fields, for admins or provisioning):
- engine_client_visibility: actionable | informational | system
- engine_requirement_category: classification | licensing | safety | legal_obligation | event_based
- engine_fulfillment_mode: document | job | obligation
- engine_event_based: when true, treat as non-calendar priority (no overdue-style inbox items)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from services.compliance_requirement_registry import (
    REQUIREMENT_CLASS_DOCUMENT,
    REQUIREMENT_CLASS_JOB,
    REQUIREMENT_CLASS_OBLIGATION,
    REQUIREMENT_CLASS_SYSTEM,
)

# --- Taxonomy (API / UI stable strings) ---
CATEGORY_CLASSIFICATION = "classification"
CATEGORY_LICENSING = "licensing"
CATEGORY_SAFETY = "safety"
CATEGORY_LEGAL_OBLIGATION = "legal_obligation"
CATEGORY_EVENT_BASED = "event_based"

VISIBILITY_SYSTEM = "system"
VISIBILITY_ACTIONABLE = "actionable"
VISIBILITY_INFORMATIONAL = "informational"

FULFILLMENT_DOCUMENT = "document"
FULFILLMENT_JOB = "job"
FULFILLMENT_OBLIGATION = "obligation"


@dataclass(frozen=True)
class _EngineSpec:
    requirement_category: str
    client_visibility: str
    requirement_class: str  # DOCUMENT | JOB | OBLIGATION | SYSTEM (portal attention + UI)
    fulfillment_mode: str
    creates_compliance_job: bool
    requires_document_evidence: bool
    include_in_priority_stream: bool
    calendar_overdue_in_inbox: bool


def _spec_dict(s: _EngineSpec) -> Dict[str, Any]:
    tracked = s.requirement_class in (REQUIREMENT_CLASS_DOCUMENT, REQUIREMENT_CLASS_JOB)
    return {
        "requirement_category": s.requirement_category,
        "engine_requirement_category": s.requirement_category,
        "client_visibility": s.client_visibility,
        "engine_client_visibility": s.client_visibility,
        "compliance_requirement_class": s.requirement_class,
        "requirement_class": s.requirement_class,
        "fulfillment_mode": s.fulfillment_mode,
        "engine_fulfillment_mode": s.fulfillment_mode,
        "creates_compliance_job": s.creates_compliance_job,
        "engine_creates_compliance_job": s.creates_compliance_job,
        "requires_document_evidence": s.requires_document_evidence,
        "engine_requires_document_evidence": s.requires_document_evidence,
        "include_in_priority_stream": s.include_in_priority_stream,
        "engine_include_in_priority_stream": s.include_in_priority_stream,
        "calendar_overdue_in_inbox": s.calendar_overdue_in_inbox,
        "engine_calendar_overdue_in_inbox": s.calendar_overdue_in_inbox,
        "client_surface_visible": s.client_visibility != VISIBILITY_SYSTEM,
        "engine_informational": s.client_visibility == VISIBILITY_INFORMATIONAL,
        "is_tracked": tracked,
    }


_CERT = _EngineSpec(
    requirement_category=CATEGORY_SAFETY,
    client_visibility=VISIBILITY_ACTIONABLE,
    requirement_class=REQUIREMENT_CLASS_DOCUMENT,
    fulfillment_mode=FULFILLMENT_DOCUMENT,
    creates_compliance_job=True,
    requires_document_evidence=True,
    include_in_priority_stream=True,
    calendar_overdue_in_inbox=True,
)

_LICENCE = _EngineSpec(
    requirement_category=CATEGORY_LICENSING,
    client_visibility=VISIBILITY_ACTIONABLE,
    requirement_class=REQUIREMENT_CLASS_DOCUMENT,
    fulfillment_mode=FULFILLMENT_DOCUMENT,
    creates_compliance_job=False,
    requires_document_evidence=True,
    include_in_priority_stream=True,
    calendar_overdue_in_inbox=True,
)

_LANDLORD_REG = _EngineSpec(
    requirement_category=CATEGORY_LICENSING,
    client_visibility=VISIBILITY_ACTIONABLE,
    requirement_class=REQUIREMENT_CLASS_DOCUMENT,
    fulfillment_mode=FULFILLMENT_DOCUMENT,
    creates_compliance_job=False,
    requires_document_evidence=True,
    include_in_priority_stream=True,
    calendar_overdue_in_inbox=True,
)

_TENANCY_SOFT = _EngineSpec(
    requirement_category=CATEGORY_LEGAL_OBLIGATION,
    client_visibility=VISIBILITY_INFORMATIONAL,
    requirement_class=REQUIREMENT_CLASS_OBLIGATION,
    fulfillment_mode=FULFILLMENT_OBLIGATION,
    creates_compliance_job=False,
    requires_document_evidence=False,
    include_in_priority_stream=False,
    calendar_overdue_in_inbox=False,
)

_HMO_FIRE = _EngineSpec(
    requirement_category=CATEGORY_SAFETY,
    client_visibility=VISIBILITY_ACTIONABLE,
    requirement_class=REQUIREMENT_CLASS_DOCUMENT,
    fulfillment_mode=FULFILLMENT_DOCUMENT,
    creates_compliance_job=True,
    requires_document_evidence=True,
    include_in_priority_stream=True,
    calendar_overdue_in_inbox=True,
)

_JOB_EXECUTION = _EngineSpec(
    requirement_category=CATEGORY_SAFETY,
    client_visibility=VISIBILITY_ACTIONABLE,
    requirement_class=REQUIREMENT_CLASS_JOB,
    fulfillment_mode=FULFILLMENT_JOB,
    creates_compliance_job=True,
    requires_document_evidence=False,
    include_in_priority_stream=True,
    calendar_overdue_in_inbox=True,
)

_EVENT = _EngineSpec(
    requirement_category=CATEGORY_EVENT_BASED,
    client_visibility=VISIBILITY_ACTIONABLE,
    requirement_class=REQUIREMENT_CLASS_OBLIGATION,
    fulfillment_mode=FULFILLMENT_OBLIGATION,
    creates_compliance_job=False,
    requires_document_evidence=False,
    include_in_priority_stream=False,
    calendar_overdue_in_inbox=False,
)

_SYSTEM_CLASSIFICATION = _EngineSpec(
    requirement_category=CATEGORY_CLASSIFICATION,
    client_visibility=VISIBILITY_SYSTEM,
    requirement_class=REQUIREMENT_CLASS_SYSTEM,
    fulfillment_mode=FULFILLMENT_OBLIGATION,
    creates_compliance_job=False,
    requires_document_evidence=False,
    include_in_priority_stream=False,
    calendar_overdue_in_inbox=False,
)

_DEFAULT = _CERT

# Scoring-normalized uppercase keys (compliance_scoring_v2.normalize_requirement_code output)
_SPECS_BY_SCORING_CODE: Dict[str, _EngineSpec] = {
    "GAS_SAFETY": _CERT,
    "EICR": _CERT,
    "EPC": _CERT,
    "FIRE_DETECTION": _CERT,
    "LEGIONELLA": _CERT,
    "LANDLORD_REGISTRATION": _LANDLORD_REG,
    "HMO_FIRE_RISK": _HMO_FIRE,
    "OCCUPATION_CONTRACT": _TENANCY_SOFT,
}

# requirement_type / requirement_code slugs (before scoring normalize)
_SPECS_BY_STORAGE_SLUG: Dict[str, _EngineSpec] = {
    "gas_safety": _SPECS_BY_SCORING_CODE["GAS_SAFETY"],
    "eicr": _SPECS_BY_SCORING_CODE["EICR"],
    "epc": _SPECS_BY_SCORING_CODE["EPC"],
    "smoke_heat_alarms": _SPECS_BY_SCORING_CODE["FIRE_DETECTION"],
    "legionella": _SPECS_BY_SCORING_CODE["LEGIONELLA"],
    "hmo_license": _LICENCE,
    "licence": _LICENCE,
    "property_licence": _LICENCE,
    "landlord_registration": _LANDLORD_REG,
    "scotland_landlord_registration": _LANDLORD_REG,
    "hmo_fire_risk": _HMO_FIRE,
    "hmo_fire_risk_evidence": _HMO_FIRE,
    "wales_occupation_contract": _TENANCY_SOFT,
    "occupation_contract": _TENANCY_SOFT,
    "how_to_rent": _TENANCY_SOFT,
    "tenancy_agreement": _TENANCY_SOFT,
    "deposit_pi": _TENANCY_SOFT,
    "deposit_prescribed_info": _TENANCY_SOFT,
    "right_to_rent": _TENANCY_SOFT,
    "rent_smart_wales": _LANDLORD_REG,
    "landlord_registration_ni": _LANDLORD_REG,
    "fire_risk_assessment": _HMO_FIRE,
    "portable_appliance_test": _CERT,
    "emergency_lighting": _JOB_EXECUTION,
    "fire_extinguisher": _JOB_EXECUTION,
    "communal_cleaning": _JOB_EXECUTION,
    "communal_fire_doors": _JOB_EXECUTION,
    "selective_license": _LICENCE,
    # Internal / derived classification rows (if ever materialised as requirements)
    "hmo_classification": _SYSTEM_CLASSIFICATION,
    "property_classification": _SYSTEM_CLASSIFICATION,
}


def _slug_key(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return str(raw).strip().lower().replace("-", "_")


def _base_spec_for_raw_code(raw: Optional[str]) -> _EngineSpec:
    if not raw:
        return _DEFAULT
    from services.requirement_code_registry import normalize_requirement_code as _norm_store_slug

    n = _norm_store_slug(str(raw).strip())
    if n and n in _SPECS_BY_STORAGE_SLUG:
        return _SPECS_BY_STORAGE_SLUG[n]
    s = _slug_key(raw)
    if s in _SPECS_BY_STORAGE_SLUG:
        return _SPECS_BY_STORAGE_SLUG[s]
    # Lazy import avoids import cycle (compliance_scoring_v2 → requirement_truth → this module).
    from services.compliance_scoring_v2 import normalize_requirement_code as normalize_scoring_code

    scoring = normalize_scoring_code(raw)
    if scoring and scoring in _SPECS_BY_SCORING_CODE:
        return _SPECS_BY_SCORING_CODE[scoring]
    return _DEFAULT


def _apply_row_overrides(row: Optional[Dict[str, Any]], base: _EngineSpec) -> _EngineSpec:
    if not row:
        return base
    if row.get("engine_event_based") is True:
        return _EVENT
    cat = row.get("engine_requirement_category")
    vis = row.get("engine_client_visibility")
    ful = row.get("engine_fulfillment_mode")
    if not cat and not vis and not ful:
        return base
    cat_s = _slug_key(cat) if cat else base.requirement_category
    vis_s = _slug_key(vis) if vis else base.client_visibility
    ful_s = _slug_key(ful) if ful else base.fulfillment_mode
    rc = base.requirement_class
    if ful_s == "job":
        rc = REQUIREMENT_CLASS_JOB
    elif ful_s == "obligation":
        rc = REQUIREMENT_CLASS_OBLIGATION
    elif ful_s == "document":
        rc = REQUIREMENT_CLASS_DOCUMENT
    return _EngineSpec(
        requirement_category=cat_s,
        client_visibility=vis_s,
        requirement_class=rc,
        fulfillment_mode=ful_s,
        creates_compliance_job=base.creates_compliance_job
        if row.get("engine_creates_compliance_job") is None
        else bool(row.get("engine_creates_compliance_job")),
        requires_document_evidence=base.requires_document_evidence
        if row.get("engine_requires_document_evidence") is None
        else bool(row.get("engine_requires_document_evidence")),
        include_in_priority_stream=base.include_in_priority_stream
        if row.get("engine_include_in_priority_stream") is None
        else bool(row.get("engine_include_in_priority_stream")),
        calendar_overdue_in_inbox=base.calendar_overdue_in_inbox
        if row.get("engine_calendar_overdue_in_inbox") is None
        else bool(row.get("engine_calendar_overdue_in_inbox")),
    )


def resolve_engine_payload_from_requirement_row(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("requirement_code") or row.get("requirement_type") or row.get("code")
    base = _base_spec_for_raw_code(str(raw) if raw else None)
    spec = _apply_row_overrides(row, base)
    out = _spec_dict(spec)
    ov_cls = (row.get("compliance_requirement_class") or row.get("requirement_class") or "").strip().upper()
    if ov_cls in (
        REQUIREMENT_CLASS_DOCUMENT,
        REQUIREMENT_CLASS_JOB,
        REQUIREMENT_CLASS_OBLIGATION,
        REQUIREMENT_CLASS_SYSTEM,
    ):
        out["compliance_requirement_class"] = ov_cls
        out["requirement_class"] = ov_cls
        out["is_tracked"] = ov_cls in (REQUIREMENT_CLASS_DOCUMENT, REQUIREMENT_CLASS_JOB)
    if row.get("is_tracked") is not None:
        out["is_tracked"] = bool(row.get("is_tracked"))
    # Persisted Mongo contract wins over catalog-derived engine defaults (enrichment must not hide SYSTEM rows).
    if row.get("client_surface_visible") is not None:
        out["client_surface_visible"] = bool(row.get("client_surface_visible"))
    if row.get("requires_document") is not None:
        out["requires_document"] = bool(row.get("requires_document"))
    if row.get("requires_job") is not None:
        out["requires_job"] = bool(row.get("requires_job"))
    return out


def resolve_engine_payload_from_code(raw_code: Optional[str]) -> Dict[str, Any]:
    return _spec_dict(_base_spec_for_raw_code(raw_code))


def requirement_row_in_client_priority_stream(row: Dict[str, Any], *, kind: str) -> Tuple[bool, Dict[str, Any]]:
    """
    kind: overdue | expiring | missing
    """
    payload = resolve_engine_payload_from_requirement_row(row)
    if row.get("is_tracked") is False:
        return False, payload
    cls = (
        row.get("compliance_requirement_class")
        or row.get("requirement_class")
        or payload.get("compliance_requirement_class")
        or ""
    )
    cls_u = str(cls).strip().upper()
    if cls_u and cls_u not in (REQUIREMENT_CLASS_DOCUMENT, REQUIREMENT_CLASS_JOB):
        return False, payload
    if not cls_u:
        # Legacy rows without persisted class: treat as actionable certificate-style
        cls_u = REQUIREMENT_CLASS_DOCUMENT
    if not payload["include_in_priority_stream"]:
        return False, payload
    if kind == "missing" and not payload["requires_document_evidence"]:
        return False, payload
    if kind == "overdue" and not payload["calendar_overdue_in_inbox"]:
        return False, payload
    if payload["client_visibility"] == VISIBILITY_SYSTEM:
        return False, payload
    if payload["client_visibility"] == VISIBILITY_INFORMATIONAL and kind in ("overdue", "expiring", "missing"):
        return False, payload
    return True, payload
