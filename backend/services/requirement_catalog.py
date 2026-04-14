"""
Requirement catalog and applicability (deterministic, no legal verdicts).
Computes per-property applicable requirement keys for the compliance score engine.

Property-type rules (professional approach):
- Commercial: EICR/EPC and gas (if declared) and licence (if applicable) are scored;
  residential-only items (tenancy bundle, How to Rent, deposit prescribed info) are
  excluded so commercial premises are not penalised under PRS rules.
- Residential (house, flat, bungalow, etc.): full applicability including tenancy/deposit
  when tenancy_active/deposit_taken are set.
- HMO / licence: driven by is_hmo, licence_required, licence_type (unchanged).
- HMO: additional HMO fire-risk evidence key expands the tracked set (stricter safety posture).
- Jurisdiction (optional client_doc): Scotland landlord registration; Wales occupation contract;
  Northern Ireland shares ENGLAND_WALES scoring bucket but portfolio label drives presentation.
"""
from typing import Any, Dict, List, Optional

# Canonical requirement keys (task spec)
GAS_SAFETY_CERT = "GAS_SAFETY_CERT"
EICR_CERT = "EICR_CERT"
EPC_CERT = "EPC_CERT"
PROPERTY_LICENCE = "PROPERTY_LICENCE"
TENANCY_AGREEMENT = "TENANCY_AGREEMENT"
HOW_TO_RENT = "HOW_TO_RENT"
DEPOSIT_PRESCRIBED_INFO = "DEPOSIT_PRESCRIBED_INFO"
FIRE_SAFETY_EVIDENCE = "FIRE_SAFETY_EVIDENCE"
# HMO supplementary fire evidence (maps to HMO_FIRE_RISK in scoring)
HMO_FIRE_RISK_EVIDENCE = "HMO_FIRE_RISK_EVIDENCE"
# Scoring-aligned label (materialised row metadata; same Mongo type as HMO_FIRE_RISK_EVIDENCE)
HMO_FIRE_RISK = "HMO_FIRE_RISK"
SCOTLAND_LANDLORD_REGISTRATION = "SCOTLAND_LANDLORD_REGISTRATION"
WALES_OCCUPATION_CONTRACT = "WALES_OCCUPATION_CONTRACT"

# Evidence mapping: requirement key -> document_type (for scoring pipeline)
REQUIREMENT_KEY_TO_DOCUMENT_TYPE: Dict[str, str] = {
    GAS_SAFETY_CERT: "gas_safety",
    EICR_CERT: "eicr",
    EPC_CERT: "epc",
    PROPERTY_LICENCE: "licence",
    FIRE_SAFETY_EVIDENCE: "fire_safety",
    HMO_FIRE_RISK_EVIDENCE: "fire_safety",
    SCOTLAND_LANDLORD_REGISTRATION: "licence",
    WALES_OCCUPATION_CONTRACT: "tenancy_agreement",
}


def _norm(s: str) -> str:
    return (s or "").strip().upper()


def _str_truthy(val) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip()
    if not s or s.upper() in ("NO", "FALSE", "0"):
        return False
    return s.upper() in ("YES", "TRUE", "1") or bool(s)


def _is_commercial(property_doc: dict) -> bool:
    """True if property type is commercial (different regulatory regime; exclude residential-only items)."""
    pt = (property_doc.get("property_type") or "").strip().upper()
    return pt == "COMMERCIAL"


def get_applicable_requirements(property_doc: dict, client_doc: Optional[dict] = None) -> List[str]:
    """
    Return list of applicable canonical requirement keys for this property.
    Rules (MUST follow exactly):
    - Property type: COMMERCIAL excludes residential-only items (tenancy, How to Rent, deposit prescribed info).
    - EICR_CERT, EPC_CERT: always applicable (residential and commercial lettings).
    - GAS_SAFETY_CERT: applicable iff cert_gas_safety == "YES" (do not penalize when NO).
    - PROPERTY_LICENCE: applicable iff is_hmo or licence_required=="YES" or cert_licence=="YES" or licence_type non-empty.
    - Tenancy docs: only if tenancy_active and NOT commercial; if absent, exclude.
    - Deposit prescribed info: only if deposit_taken and NOT commercial; if absent, exclude.
    - HMO_FIRE_RISK_EVIDENCE: applicable when is_hmo (supplementary fire safety / FRA posture).
    - SCOTLAND_LANDLORD_REGISTRATION: residential Scotland (uses client default jurisdiction when property unset).
    - WALES_OCCUPATION_CONTRACT: residential Wales with an active tenancy flag.
    """
    applicable: List[str] = []
    is_commercial = _is_commercial(property_doc)

    # Always applicable (residential and commercial lettings)
    applicable.append(EICR_CERT)
    applicable.append(EPC_CERT)

    # GAS_SAFETY_CERT: only when cert_gas_safety == "YES"
    if _norm(property_doc.get("cert_gas_safety") or "") == "YES":
        applicable.append(GAS_SAFETY_CERT)

    # PROPERTY_LICENCE: any of is_hmo, licence_required==YES, cert_licence==YES, licence_type non-empty
    is_hmo = bool(property_doc.get("is_hmo", False))
    licence_required_yes = _norm(property_doc.get("licence_required") or "") == "YES"
    cert_licence_yes = _norm(property_doc.get("cert_licence") or "") == "YES"
    licence_type_val = property_doc.get("licence_type")
    licence_type_non_empty = bool(licence_type_val and str(licence_type_val).strip())
    if is_hmo or licence_required_yes or cert_licence_yes or licence_type_non_empty:
        applicable.append(PROPERTY_LICENCE)

    if is_hmo:
        applicable.append(HMO_FIRE_RISK_EVIDENCE)

    # Tenancy / How to Rent / Deposit: residential regime only; exclude for commercial
    if not is_commercial:
        if _str_truthy(property_doc.get("tenancy_active")):
            applicable.append(TENANCY_AGREEMENT)
            applicable.append(HOW_TO_RENT)
        if _str_truthy(property_doc.get("deposit_taken")):
            applicable.append(DEPOSIT_PRESCRIBED_INFO)

    try:
        from services.compliance_rules_registry import resolve_portfolio_jurisdiction

        juris = resolve_portfolio_jurisdiction(property_doc, client_doc).effective_label
        if not is_commercial and juris == "Scotland":
            applicable.append(SCOTLAND_LANDLORD_REGISTRATION)
        if not is_commercial and juris == "Wales" and _str_truthy(property_doc.get("tenancy_active")):
            applicable.append(WALES_OCCUPATION_CONTRACT)
    except Exception:
        pass

    return applicable


# Keys surfaced in plan-preview “catalog explanations” (subset of scoring/catalog universe).
_EXPLAINABLE_CATALOG_KEYS: tuple = (
    GAS_SAFETY_CERT,
    EICR_CERT,
    EPC_CERT,
    PROPERTY_LICENCE,
    TENANCY_AGREEMENT,
    HOW_TO_RENT,
    DEPOSIT_PRESCRIBED_INFO,
    HMO_FIRE_RISK_EVIDENCE,
    SCOTLAND_LANDLORD_REGISTRATION,
    WALES_OCCUPATION_CONTRACT,
)


def explain_catalog_keys_for_property(
    property_doc: dict,
    client_doc: Optional[dict] = None,
) -> List[Dict[str, Any]]:
    """
    Per canonical catalog key: whether it is applicable for scoring/catalog expansion on this property,
    with a short reason (staging / support debugging). Logic mirrors get_applicable_requirements.
    """
    applicable_set = set(get_applicable_requirements(property_doc, client_doc))
    is_commercial = _is_commercial(property_doc)
    juris = ""
    try:
        from services.compliance_rules_registry import resolve_portfolio_jurisdiction

        juris = resolve_portfolio_jurisdiction(property_doc, client_doc).effective_label
    except Exception:
        pass

    out: List[Dict[str, Any]] = []
    for key in _EXPLAINABLE_CATALOG_KEYS:
        included = key in applicable_set
        if included:
            if key == EICR_CERT:
                reason = "Always applicable for lettings (EICR)."
            elif key == EPC_CERT:
                reason = "Always applicable for lettings (EPC)."
            elif key == GAS_SAFETY_CERT:
                reason = "cert_gas_safety is YES on the property."
            elif key == PROPERTY_LICENCE:
                reason = "Licence signals: is_hmo, licence_required YES, cert_licence YES, or licence_type set."
            elif key == HMO_FIRE_RISK_EVIDENCE:
                reason = "Property is HMO (is_hmo)."
            elif key in (TENANCY_AGREEMENT, HOW_TO_RENT):
                reason = "Residential and tenancy_active is true."
            elif key == DEPOSIT_PRESCRIBED_INFO:
                reason = "Residential and deposit_taken is true."
            elif key == SCOTLAND_LANDLORD_REGISTRATION:
                reason = f"Residential and portfolio jurisdiction is Scotland (effective={juris!r})."
            elif key == WALES_OCCUPATION_CONTRACT:
                reason = f"Residential Wales and tenancy_active is true (effective jurisdiction={juris!r})."
            else:
                reason = "Applicable under catalog rules for this property."
        else:
            if key in (EICR_CERT, EPC_CERT):
                reason = "Unexpected exclusion (should always apply); check get_applicable_requirements."
            elif key == GAS_SAFETY_CERT:
                reason = "Excluded: cert_gas_safety is not YES (no scoring penalty for undeclared gas)."
            elif key == PROPERTY_LICENCE:
                reason = "Excluded: not HMO and no licence_required/cert_licence/licence_type signals."
            elif key == HMO_FIRE_RISK_EVIDENCE:
                reason = "Excluded: property is not HMO."
            elif key in (TENANCY_AGREEMENT, HOW_TO_RENT):
                reason = (
                    "Excluded: commercial property (PRS tenancy bundle not scored)."
                    if is_commercial
                    else "Excluded: tenancy_active is false or unset."
                )
            elif key == DEPOSIT_PRESCRIBED_INFO:
                reason = (
                    "Excluded: commercial property."
                    if is_commercial
                    else "Excluded: deposit_taken is false or unset."
                )
            elif key == SCOTLAND_LANDLORD_REGISTRATION:
                reason = f"Excluded: commercial or not Scotland (effective jurisdiction={juris!r})."
            elif key == WALES_OCCUPATION_CONTRACT:
                if is_commercial:
                    reason = "Excluded: commercial property."
                elif juris != "Wales":
                    reason = f"Excluded: effective jurisdiction is not Wales ({juris!r})."
                else:
                    reason = "Excluded: tenancy_active is false or unset."
            else:
                reason = "Excluded for this property configuration."
        out.append({"catalog_key": key, "included": included, "reason": reason})
    return out
