"""
Jurisdiction-aware compliance rule registry.

Keys requirements by scoring jurisdiction bucket (SCOTLAND | ENGLAND_WALES) matching
compliance_scoring_v2.normalize_jurisdiction, while persisting portfolio-facing labels
(Scotland | England | Wales | Northern Ireland) on requirements and jobs.

Explicit design (avoid accidental sameness)
-----------------------------------------
- **Intentionally shared (today):** Core legal-pack cadence for GAS_SAFETY, EICR, EPC, FIRE_DETECTION,
  LEGIONELLA uses one baseline (``base_ew``) for both ENGLAND_WALES and SCOTLAND registry buckets.
  Product/legal may later fork SCOTLAND entries (e.g. different frequency_days or
  expiring_soon_days_override) without changing call sites.
- **Intentionally divergent:** England & Wales–only local authority rules (``apply_location_rules_enabled``)
  and Mongo ``requirement_rules.jurisdictions`` scoping — not mirrored to Scotland at the rule-engine level.
- **Placeholders / not law-specific:** ``warning_days`` on ComplianceRuleSpec (admin/UX hints); document
  validation (``validate_document_upload_for_requirement``) uses evidence taxonomy, not statute text.

Product-risk (steady-state)
---------------------------
- ``portfolio_jurisdiction_label`` falls back to **"England"** when property and client omit recognised
  labels → ENGLAND_WALES scoring bucket. That can mis-rank assets if jurisdiction is unset.
- ``client.enabled_jurisdictions`` is not enforced by provisioning; it does not block requirement generation
  outside listed regions. See ``compliance_expiry_policy`` for related notes on expiring-soon defaults.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Portfolio labels stored on requirement / work_order / property
UK_PORTFOLIO_LABELS: Set[str] = frozenset({"Scotland", "England", "Wales", "Northern Ireland"})


def canonicalize_uk_portfolio_label(value: Optional[str]) -> Optional[str]:
    """Return canonical portfolio label (e.g. Scotland) or None if not a recognised UK region."""
    if not value or not str(value).strip():
        return None
    t = str(value).strip()
    for label in UK_PORTFOLIO_LABELS:
        if t.lower() == label.lower():
            return label
    return None


# How we determined the label for compliance (API / UI integrity layer)
COMPLIANCE_BASIS_PROPERTY_EXPLICIT = "property_explicit"
COMPLIANCE_BASIS_CLIENT_DEFAULT = "client_default"
COMPLIANCE_BASIS_DEFAULT_FALLBACK = "default_fallback"

# Property-level jurisdiction is unset → APIs surface this (onboarding / transparency); scoring still proceeds.
COMPLIANCE_CONFIDENCE_EXPLICIT = "explicit"
COMPLIANCE_CONFIDENCE_FALLBACK = "fallback"


def _legacy_scoring_bucket_on_property_field(raw: Optional[str]) -> Optional[str]:
    """
    Historically some recalc paths wrote scoring buckets into properties.jurisdiction.
    Only SCOTLAND maps 1:1 to a portfolio label; ENGLAND_WALES is ambiguous (England vs Wales vs NI) and is not treated as explicit.
    """
    if not raw or not str(raw).strip():
        return None
    u = str(raw).strip().upper().replace(" ", "_").replace("/", "_")
    if u == "SCOTLAND":
        return "Scotland"
    return None


def property_has_explicit_portfolio_jurisdiction(property_doc: Dict[str, Any]) -> bool:
    """True when property.jurisdiction is a recognised UK portfolio label (case-insensitive), or legacy SCOTLAND bucket."""
    if canonicalize_uk_portfolio_label(property_doc.get("jurisdiction")) is not None:
        return True
    return _legacy_scoring_bucket_on_property_field(property_doc.get("jurisdiction")) is not None


def property_jurisdiction_requirement_flags(property_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    When property.jurisdiction is missing or invalid:
    jurisdiction_required=True, compliance_confidence=\"fallback\".
    """
    req = not property_has_explicit_portfolio_jurisdiction(property_doc)
    return {
        "jurisdiction_required": req,
        "compliance_confidence": COMPLIANCE_CONFIDENCE_FALLBACK if req else COMPLIANCE_CONFIDENCE_EXPLICIT,
    }


def build_portfolio_jurisdiction_attestation(
    _client_doc: Optional[Dict[str, Any]],
    properties: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Portfolio roll-up: any property without explicit jurisdiction ⇒ required + fallback confidence.
    _client_doc is unused; included so call sites match other jurisdiction helpers.

    Staged enforcement: truth is per property; portfolio flags surface gaps. Client-level onboarding
    acknowledgement (see routes) is phase-1 gating only — not a substitute for property records.
    """
    req_ids: List[str] = []
    for p in properties or []:
        pid = p.get("property_id")
        if not pid:
            continue
        if not property_has_explicit_portfolio_jurisdiction(p):
            req_ids.append(str(pid))
    active = bool(req_ids)
    return {
        "jurisdiction_required": active,
        "compliance_confidence": COMPLIANCE_CONFIDENCE_FALLBACK if active else COMPLIANCE_CONFIDENCE_EXPLICIT,
        "jurisdiction_required_property_ids": req_ids,
        "jurisdiction_required_property_count": len(req_ids),
    }


@dataclass(frozen=True)
class PortfolioJurisdictionResolution:
    """effective_label: portfolio-facing string (e.g. England, Scotland)."""

    effective_label: str
    compliance_basis: str


def resolve_portfolio_jurisdiction(
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
) -> PortfolioJurisdictionResolution:
    """
    Resolve jurisdiction label and whether compliance used explicit property data, client default, or system fallback.

    compliance_basis == COMPLIANCE_BASIS_DEFAULT_FALLBACK when the property has no recognised jurisdiction and
    client.default_jurisdiction is missing or not a recognised UK portfolio label — evaluation then assumes England / EW bucket.

    Property and client values are normalised with canonicalize_uk_portfolio_label (case-insensitive) so stored variants
    still resolve to client_default instead of incorrectly falling through to default_fallback.
    """
    p_label = canonicalize_uk_portfolio_label(property_doc.get("jurisdiction"))
    if p_label:
        return PortfolioJurisdictionResolution(p_label, COMPLIANCE_BASIS_PROPERTY_EXPLICIT)
    legacy = _legacy_scoring_bucket_on_property_field(property_doc.get("jurisdiction"))
    if legacy:
        return PortfolioJurisdictionResolution(legacy, COMPLIANCE_BASIS_PROPERTY_EXPLICIT)
    c_label = canonicalize_uk_portfolio_label((client_doc or {}).get("default_jurisdiction"))
    if c_label:
        return PortfolioJurisdictionResolution(c_label, COMPLIANCE_BASIS_CLIENT_DEFAULT)
    return PortfolioJurisdictionResolution("England", COMPLIANCE_BASIS_DEFAULT_FALLBACK)


def jurisdiction_attribution_for_property(
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    *,
    _resolution: Optional[PortfolioJurisdictionResolution] = None,
) -> Dict[str, Any]:
    """
    Per-property jurisdiction context for APIs and UI (mixed-jurisdiction portfolios).

    jurisdiction_source:
      - property_record: explicit recognised label on the property document (authoritative).
      - account_default: property has no explicit label; client's default_jurisdiction applies.
      - system_default: neither property nor client has a valid label; scoring uses England / EW bucket.
    """
    r = _resolution or resolve_portfolio_jurisdiction(property_doc, client_doc)
    if r.compliance_basis == COMPLIANCE_BASIS_PROPERTY_EXPLICIT:
        src = "property_record"
    elif r.compliance_basis == COMPLIANCE_BASIS_CLIENT_DEFAULT:
        src = "account_default"
    else:
        src = "system_default"
    return {
        "jurisdiction_source": src,
        "compliance_basis": r.compliance_basis,
        "effective_jurisdiction_label": r.effective_label,
    }


def log_jurisdiction_resolution_debug(
    *,
    context: str,
    property_id: Optional[str],
    raw_property_jurisdiction: Any,
    raw_client_default_jurisdiction: Any,
    resolution: PortfolioJurisdictionResolution,
) -> None:
    """Temporary diagnostics; enable with JURISDICTION_RESOLUTION_DEBUG=1."""
    if (os.environ.get("JURISDICTION_RESOLUTION_DEBUG") or "").strip().lower() not in ("1", "true", "yes"):
        return
    logger.info(
        "JURISDICTION_RESOLUTION_DEBUG context=%s property_id=%s property.jurisdiction(raw)=%r "
        "client.default_jurisdiction(raw)=%r compliance_basis=%s effective_jurisdiction_label=%s",
        context,
        property_id,
        raw_property_jurisdiction,
        raw_client_default_jurisdiction,
        resolution.compliance_basis,
        resolution.effective_label,
    )


def build_jurisdiction_compliance_notice(
    client_doc: Optional[Dict[str, Any]],
    properties: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Portfolio-level notice for APIs when any property uses default_fallback (non-blocking)."""
    affected: List[str] = []
    for p in properties or []:
        pid = p.get("property_id")
        if not pid:
            continue
        r = resolve_portfolio_jurisdiction(p, client_doc)
        if r.compliance_basis == COMPLIANCE_BASIS_DEFAULT_FALLBACK:
            affected.append(str(pid))
    active = bool(affected)
    return {
        "active": active,
        "compliance_basis": COMPLIANCE_BASIS_DEFAULT_FALLBACK if active else None,
        "affected_property_ids": affected,
        "affected_property_count": len(affected),
    }


def normalize_jurisdiction(raw: Optional[str]) -> str:
    """Match compliance_scoring_v2.normalize_jurisdiction (duplicated to avoid import cycles)."""
    value = (raw or "").strip().upper()
    if value in ("SCOTLAND",):
        return "SCOTLAND"
    if value in ("ENGLAND", "WALES", "ENGLAND/WALES", "ENGLAND_WALES", "NORTHERN IRELAND", "NORTHERN_IRELAND"):
        return "ENGLAND_WALES"
    return "ENGLAND_WALES"


def portfolio_jurisdiction_label(property_doc: Dict[str, Any], client_doc: Optional[Dict[str, Any]]) -> str:
    """Label persisted on requirement rows; must be one of UK_PORTFOLIO_LABELS when possible."""
    return resolve_portfolio_jurisdiction(property_doc, client_doc).effective_label


def scoring_jurisdiction_for_property(property_doc: Dict[str, Any], client_doc: Optional[Dict[str, Any]]) -> str:
    return normalize_jurisdiction(portfolio_jurisdiction_label(property_doc, client_doc))


@dataclass(frozen=True)
class ComplianceRuleSpec:
    """Canonical compliance rule for generation + evaluation hints."""

    canonical_code: str  # e.g. GAS_SAFETY
    storage_type: str  # lowercase slug stored in requirement_type (e.g. gas_safety)
    description: str
    frequency_days: int
    warning_days: int
    expects_expiry: bool
    condition: Optional[str] = None  # has_gas_supply | hmo_license_required | None
    frequency_by_age: Optional[Dict[str, int]] = None
    expiring_soon_days_override: Optional[int] = None  # None → use profile default from scoring
    # Evidence / upload validation (jurisdiction-specific when registry rows differ by bucket).
    allowed_document_types: Optional[Tuple[str, ...]] = None  # None → derive from REQ_TO_DOC_TYPE + legacy aliases
    required_metadata_fields: Tuple[str, ...] = ()  # Keys expected on upload metadata (e.g. engineer_id, issue_date)
    # COMPLIANCE work order SLA (jurisdiction-specific). None → use global defaults in compliance_execution_sla_policy().
    sla_complete_days: Optional[int] = None
    sla_respond_hours: Optional[int] = None
    # Near-breach windows for run_work_order_sla_breach_job (None → global defaults).
    sla_risk_days_before_complete: Optional[int] = None
    sla_risk_hours_before_respond: Optional[int] = None


# Per scoring bucket, canonical requirement definitions (frequencies can diverge by jurisdiction over time).
def _build_registry() -> Dict[str, Dict[str, ComplianceRuleSpec]]:
    base_ew = {
        "GAS_SAFETY": ComplianceRuleSpec(
            canonical_code="GAS_SAFETY",
            storage_type="gas_safety",
            description="Gas Safety Certificate",
            frequency_days=365,
            warning_days=30,
            expects_expiry=True,
            condition="has_gas_supply",
            allowed_document_types=("gas_safety", "cp12", "gas_certificate"),
            sla_complete_days=10,
            sla_respond_hours=24,
            sla_risk_days_before_complete=2,
            sla_risk_hours_before_respond=4,
        ),
        "EICR": ComplianceRuleSpec(
            canonical_code="EICR",
            storage_type="eicr",
            description="Electrical Installation Condition Report",
            frequency_days=1825,
            warning_days=30,
            expects_expiry=True,
            condition=None,
            frequency_by_age={"old": 1095, "standard": 1825},
            allowed_document_types=("eicr", "electrical_installation", "electrical_installation_condition_report"),
            sla_complete_days=14,
            sla_respond_hours=24,
            sla_risk_days_before_complete=3,
            sla_risk_hours_before_respond=4,
        ),
        "EPC": ComplianceRuleSpec(
            canonical_code="EPC",
            storage_type="epc",
            description="Energy Performance Certificate",
            frequency_days=3650,
            warning_days=30,
            expects_expiry=True,
            allowed_document_types=("epc", "energy_performance"),
            sla_complete_days=21,
            sla_respond_hours=48,
            sla_risk_days_before_complete=3,
            sla_risk_hours_before_respond=6,
        ),
        "FIRE_DETECTION": ComplianceRuleSpec(
            canonical_code="FIRE_DETECTION",
            storage_type="fire_alarm",
            description="Fire Alarm Inspection",
            frequency_days=365,
            warning_days=30,
            expects_expiry=False,
            allowed_document_types=("fire_safety", "fire_alarm", "smoke_alarm", "co_alarm"),
            sla_complete_days=10,
            sla_respond_hours=24,
            sla_risk_days_before_complete=2,
            sla_risk_hours_before_respond=4,
        ),
        "LEGIONELLA": ComplianceRuleSpec(
            canonical_code="LEGIONELLA",
            storage_type="legionella",
            description="Legionella Risk Assessment",
            frequency_days=730,
            warning_days=30,
            expects_expiry=False,
            allowed_document_types=("legionella", "legionella_risk"),
            sla_complete_days=14,
            sla_respond_hours=24,
            sla_risk_days_before_complete=3,
            sla_risk_hours_before_respond=4,
        ),
        "HMO_FIRE_RISK": ComplianceRuleSpec(
            canonical_code="HMO_FIRE_RISK",
            storage_type="hmo_fire_risk",
            description="HMO fire safety evidence / fire risk assessment",
            frequency_days=365,
            warning_days=30,
            expects_expiry=True,
            allowed_document_types=("fire_safety", "fire_risk_assessment", "fire_alarm", "smoke_alarm"),
            sla_complete_days=14,
            sla_respond_hours=24,
            sla_risk_days_before_complete=3,
            sla_risk_hours_before_respond=4,
        ),
        "OCCUPATION_CONTRACT": ComplianceRuleSpec(
            canonical_code="OCCUPATION_CONTRACT",
            storage_type="occupation_contract",
            description="Occupation contract / tenancy documentation (Wales)",
            frequency_days=365,
            warning_days=30,
            expects_expiry=True,
            allowed_document_types=("tenancy_agreement", "occupation_contract", "contract"),
            sla_complete_days=21,
            sla_respond_hours=48,
            sla_risk_days_before_complete=3,
            sla_risk_hours_before_respond=6,
        ),
        "LANDLORD_REGISTRATION": ComplianceRuleSpec(
            canonical_code="LANDLORD_REGISTRATION",
            storage_type="landlord_registration",
            description="Landlord registration (Scotland)",
            frequency_days=1095,
            warning_days=45,
            expects_expiry=True,
            allowed_document_types=("licence", "landlord_registration", "registration_certificate"),
            sla_complete_days=14,
            sla_respond_hours=48,
            sla_risk_days_before_complete=3,
            sla_risk_hours_before_respond=6,
        ),
    }
    # SCOTLAND: shared cadence baseline; document evidence rules may diverge (e.g. extra accepted types).
    scotland = dict(base_ew)
    scotland["GAS_SAFETY"] = ComplianceRuleSpec(
        canonical_code="GAS_SAFETY",
        storage_type="gas_safety",
        description="Gas Safety Certificate",
        frequency_days=365,
        warning_days=30,
        expects_expiry=True,
        condition="has_gas_supply",
        allowed_document_types=("gas_safety", "cp12", "gas_certificate"),
        sla_complete_days=7,
        sla_respond_hours=24,
        sla_risk_days_before_complete=2,
        sla_risk_hours_before_respond=4,
    )
    scotland["LEGIONELLA"] = ComplianceRuleSpec(
        canonical_code="LEGIONELLA",
        storage_type="legionella",
        description="Legionella Risk Assessment",
        frequency_days=730,
        warning_days=30,
        expects_expiry=False,
        allowed_document_types=("legionella", "legionella_risk", "legionella_risk_assessment"),
        sla_complete_days=10,
        sla_respond_hours=24,
        sla_risk_days_before_complete=4,
        sla_risk_hours_before_respond=4,
    )
    # Shared extended rules (HMO fire, Wales contract) use same cadence hints as EW unless forked later.
    scotland["HMO_FIRE_RISK"] = base_ew["HMO_FIRE_RISK"]
    scotland["OCCUPATION_CONTRACT"] = base_ew["OCCUPATION_CONTRACT"]
    return {"ENGLAND_WALES": base_ew, "SCOTLAND": scotland}


REGISTRY_BY_JURISDICTION: Dict[str, Dict[str, ComplianceRuleSpec]] = _build_registry()

# COMPLIANCE work order SLA when no registry row / field override
DEFAULT_COMPLIANCE_WO_SLA_COMPLETE_DAYS = 5
DEFAULT_COMPLIANCE_WO_SLA_RESPOND_HOURS = 24
DEFAULT_COMPLIANCE_WO_SLA_RISK_DAYS_BEFORE_COMPLETE = 1
DEFAULT_COMPLIANCE_WO_SLA_RISK_HOURS_BEFORE_RESPOND = 4

# REQ_TO_DOC_TYPE aligned with compliance_scoring_v2
REQ_TO_DOC_TYPE: Dict[str, str] = {
    "GAS_SAFETY": "gas_safety",
    "EICR": "eicr",
    "EPC": "epc",
    "FIRE_DETECTION": "fire_safety",
    "LEGIONELLA": "legionella",
    "HMO_FIRE_RISK": "fire_safety",
    "LANDLORD_REGISTRATION": "licence",
    "OCCUPATION_CONTRACT": "tenancy_agreement",
}


def _normalize_req_alias(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    from services.compliance_scoring_v2 import normalize_requirement_code

    return normalize_requirement_code(raw)


def get_rule(scoring_jurisdiction: str, canonical_code: str) -> Optional[ComplianceRuleSpec]:
    bucket = scoring_jurisdiction if scoring_jurisdiction in REGISTRY_BY_JURISDICTION else "ENGLAND_WALES"
    return REGISTRY_BY_JURISDICTION.get(bucket, {}).get(canonical_code)


def work_order_requirement_code_to_registry_key(storage_slug: Optional[str]) -> Optional[str]:
    """Map work order requirement_code (e.g. gas_safety) to registry key (GAS_SAFETY)."""
    from services.requirement_code_registry import normalize_requirement_code

    c = normalize_requirement_code(storage_slug)
    if not c:
        return None
    return str(c).strip().upper()


def compliance_execution_sla_policy(
    portfolio_jurisdiction_label: Optional[str],
    requirement_code_storage: Optional[str],
) -> Dict[str, int]:
    """
    SLA profile for COMPLIANCE execution work orders: complete/respond deadlines and near-breach windows.
    portfolio_jurisdiction_label: Scotland | England | Wales | Northern Ireland (or unset → EW bucket via normalize_jurisdiction).
    """
    bucket = normalize_jurisdiction(portfolio_jurisdiction_label or "")
    key = work_order_requirement_code_to_registry_key(requirement_code_storage)
    base = {
        "complete_days": DEFAULT_COMPLIANCE_WO_SLA_COMPLETE_DAYS,
        "respond_hours": DEFAULT_COMPLIANCE_WO_SLA_RESPOND_HOURS,
        "risk_days_before_complete": DEFAULT_COMPLIANCE_WO_SLA_RISK_DAYS_BEFORE_COMPLETE,
        "risk_hours_before_respond": DEFAULT_COMPLIANCE_WO_SLA_RISK_HOURS_BEFORE_RESPOND,
    }
    if not key:
        return base
    spec = get_rule(bucket, key)
    if not spec:
        return base
    return {
        "complete_days": int(spec.sla_complete_days)
        if spec.sla_complete_days is not None
        else base["complete_days"],
        "respond_hours": int(spec.sla_respond_hours)
        if spec.sla_respond_hours is not None
        else base["respond_hours"],
        "risk_days_before_complete": int(spec.sla_risk_days_before_complete)
        if spec.sla_risk_days_before_complete is not None
        else base["risk_days_before_complete"],
        "risk_hours_before_respond": int(spec.sla_risk_hours_before_respond)
        if spec.sla_risk_hours_before_respond is not None
        else base["risk_hours_before_respond"],
    }


def iter_core_rules(scoring_jurisdiction: str) -> Iterator[ComplianceRuleSpec]:
    bucket = scoring_jurisdiction if scoring_jurisdiction in REGISTRY_BY_JURISDICTION else "ENGLAND_WALES"
    for spec in REGISTRY_BY_JURISDICTION.get(bucket, {}).values():
        yield spec


def expiring_soon_days_for_requirement(
    scoring_jurisdiction: str,
    canonical_code: str,
    profile_default: int,
) -> int:
    spec = get_rule(scoring_jurisdiction, canonical_code)
    if spec and spec.expiring_soon_days_override is not None:
        return int(spec.expiring_soon_days_override)
    return int(profile_default)


def expects_expiry_for_requirement(scoring_jurisdiction: str, canonical_code: str) -> bool:
    spec = get_rule(scoring_jurisdiction, canonical_code)
    if spec:
        return spec.expects_expiry
    return canonical_code in (
        "GAS_SAFETY",
        "EICR",
        "EPC",
        "HMO_FIRE_RISK",
        "LANDLORD_REGISTRATION",
        "OCCUPATION_CONTRACT",
    )


def rule_applies_to_db_row(rule: Dict[str, Any], portfolio_label: str, scoring_jurisdiction: str) -> bool:
    """Optional jurisdictions[] on Mongo requirement_rules: portfolio labels; omit = all regions."""
    jurs = rule.get("jurisdictions")
    if not jurs:
        return True
    if not isinstance(jurs, (list, tuple)):
        return True
    labels = {str(x).strip() for x in jurs if x}
    if not labels:
        return True
    if portfolio_label in labels:
        return True
    # Allow admins to store scoring bucket keys optionally
    if scoring_jurisdiction in labels:
        return True
    return False


def _normalize_doc_type_token(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return str(raw).strip().lower().replace(" ", "_").replace("-", "_")


def _legacy_alias_tokens_for_code(code: str) -> Set[str]:
    """Fallback allowed tokens when ComplianceRuleSpec.allowed_document_types is unset."""
    expected = REQ_TO_DOC_TYPE.get(code)
    if not expected:
        return set()
    out = {expected}
    if code == "FIRE_DETECTION":
        out.update({"fire_safety", "fire_alarm", "smoke_alarm", "co_alarm"})
    aliases = {
        "gas_safety": ("gas_safety", "cp12", "gas_certificate"),
        "eicr": ("eicr", "electrical_installation", "electrical_installation_condition_report"),
        "epc": ("epc", "energy_performance"),
        "legionella": ("legionella", "legionella_risk"),
    }.get(expected, (expected,))
    out.update(aliases)
    return out


def allowed_document_type_tokens(
    scoring_jurisdiction: str,
    canonical_code: str,
    spec: Optional[ComplianceRuleSpec],
) -> Set[str]:
    if spec and spec.allowed_document_types:
        return {_normalize_doc_type_token(x) for x in spec.allowed_document_types if x}
    return _legacy_alias_tokens_for_code(canonical_code)


def resolve_scoring_jurisdiction_for_requirement_row(
    requirement_row: Dict[str, Any],
    property_doc: Optional[Dict[str, Any]],
    client_doc: Optional[Dict[str, Any]],
) -> Tuple[str, Optional[str]]:
    """
    Return (scoring_jurisdiction_bucket, portfolio_jurisdiction_label_used).
    Prefer requirement.jurisdiction when set on the row; else property + client resolution.
    """
    j = (requirement_row.get("jurisdiction") or "").strip()
    if j in UK_PORTFOLIO_LABELS:
        return normalize_jurisdiction(j), j
    if property_doc is not None:
        lbl = portfolio_jurisdiction_label(property_doc, client_doc)
        return normalize_jurisdiction(lbl), lbl
    return "ENGLAND_WALES", None


def _metadata_field_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return True


def validate_document_upload_for_requirement(
    document_type: Optional[str],
    requirement_row: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    *,
    property_doc: Optional[Dict[str, Any]] = None,
    client_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Jurisdiction-aware validation for evidence linked to a requirement.

    Returns a structured dict: valid, reason (user-safe), jurisdiction (display label or scoring bucket),
    scoring_jurisdiction, portfolio_jurisdiction, missing_metadata_fields (when invalid).
    """
    meta = metadata if isinstance(metadata, dict) else {}
    code = _normalize_req_alias(requirement_row.get("requirement_code") or requirement_row.get("requirement_type"))
    scoring_jur, port_lbl = resolve_scoring_jurisdiction_for_requirement_row(
        requirement_row, property_doc, client_doc
    )
    display_jurisdiction = port_lbl or scoring_jur

    def _ok() -> Dict[str, Any]:
        return {
            "valid": True,
            "reason": None,
            "jurisdiction": display_jurisdiction,
            "scoring_jurisdiction": scoring_jur,
            "portfolio_jurisdiction": port_lbl,
            "missing_metadata_fields": [],
        }

    if not code:
        return _ok()

    spec = get_rule(scoring_jur, code)
    required_meta: Tuple[str, ...] = tuple(spec.required_metadata_fields) if spec else ()

    missing_meta = [k for k in required_meta if not _metadata_field_present(meta.get(k))]
    if missing_meta:
        return {
            "valid": False,
            "reason": (
                f"This requirement ({code.replace('_', ' ')}) in {display_jurisdiction} needs metadata: "
                f"{', '.join(missing_meta)}. Add them in the upload form (document metadata) or leave document type blank for AI classification first."
            ),
            "jurisdiction": display_jurisdiction,
            "scoring_jurisdiction": scoring_jur,
            "portfolio_jurisdiction": port_lbl,
            "missing_metadata_fields": missing_meta,
        }

    dt_raw = (document_type or "").strip() if document_type else ""
    if not dt_raw:
        return _ok()

    allowed = allowed_document_type_tokens(scoring_jur, code, spec)
    dt = _normalize_doc_type_token(dt_raw)
    if not allowed:
        return _ok()
    if dt in allowed:
        return _ok()

    return {
        "valid": False,
        "reason": (
            f"This upload was labeled as '{document_type}', which does not match the linked requirement "
            f"({code.replace('_', ' ')}) for jurisdiction {display_jurisdiction}. "
            f"Use an evidence type in line with this region or leave type blank for AI classification."
        ),
        "jurisdiction": display_jurisdiction,
        "scoring_jurisdiction": scoring_jur,
        "portfolio_jurisdiction": port_lbl,
        "missing_metadata_fields": [],
    }


def validate_document_type_for_requirement(
    document_type: Optional[str],
    requirement_row: Dict[str, Any],
    *,
    property_doc: Optional[Dict[str, Any]] = None,
    client_doc: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Back-compat: returns user-safe error message if invalid; None if OK or skipped.
    Prefer validate_document_upload_for_requirement for structured API responses.
    """
    vr = validate_document_upload_for_requirement(
        document_type,
        requirement_row,
        metadata,
        property_doc=property_doc,
        client_doc=client_doc,
    )
    return vr["reason"] if not vr.get("valid") else None


def apply_location_rules_enabled(scoring_jurisdiction: str) -> bool:
    """LA-style selective licensing rules are England & Wales portfolio contexts only."""
    return scoring_jurisdiction == "ENGLAND_WALES"
