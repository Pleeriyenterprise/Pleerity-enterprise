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
"""
from typing import Dict, List

# Canonical requirement keys (task spec)
GAS_SAFETY_CERT = "GAS_SAFETY_CERT"
EICR_CERT = "EICR_CERT"
EPC_CERT = "EPC_CERT"
PROPERTY_LICENCE = "PROPERTY_LICENCE"
TENANCY_AGREEMENT = "TENANCY_AGREEMENT"
HOW_TO_RENT = "HOW_TO_RENT"
DEPOSIT_PRESCRIBED_INFO = "DEPOSIT_PRESCRIBED_INFO"
FIRE_SAFETY_EVIDENCE = "FIRE_SAFETY_EVIDENCE"

# Evidence mapping: requirement key -> document_type (for scoring pipeline)
REQUIREMENT_KEY_TO_DOCUMENT_TYPE: Dict[str, str] = {
    GAS_SAFETY_CERT: "gas_safety",
    EICR_CERT: "eicr",
    EPC_CERT: "epc",
    PROPERTY_LICENCE: "licence",
}


def _norm(s: str) -> str:
    return (s or "").strip().upper()


def _str_truthy(val) -> bool:
    if val is None:
        return False
    s = str(val).strip()
    return s.upper() in ("YES", "TRUE", "1") or bool(s)


def _is_commercial(property_doc: dict) -> bool:
    """True if property type is commercial (different regulatory regime; exclude residential-only items)."""
    pt = (property_doc.get("property_type") or "").strip().upper()
    return pt == "COMMERCIAL"


def get_applicable_requirements(property_doc: dict) -> List[str]:
    """
    Return list of applicable canonical requirement keys for this property.
    Rules (MUST follow exactly):
    - Property type: COMMERCIAL excludes residential-only items (tenancy, How to Rent, deposit prescribed info).
    - EICR_CERT, EPC_CERT: always applicable (residential and commercial lettings).
    - GAS_SAFETY_CERT: applicable iff cert_gas_safety == "YES" (do not penalize when NO).
    - PROPERTY_LICENCE: applicable iff is_hmo or licence_required=="YES" or cert_licence=="YES" or licence_type non-empty.
    - Tenancy docs: only if tenancy_active and NOT commercial; if absent, exclude.
    - Deposit prescribed info: only if deposit_taken and NOT commercial; if absent, exclude.
    - FIRE_SAFETY_EVIDENCE: excluded from v1.
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

    # Tenancy / How to Rent / Deposit: residential regime only; exclude for commercial
    if not is_commercial:
        if _str_truthy(property_doc.get("tenancy_active")):
            applicable.append(TENANCY_AGREEMENT)
            applicable.append(HOW_TO_RENT)
        if _str_truthy(property_doc.get("deposit_taken")):
            applicable.append(DEPOSIT_PRESCRIBED_INFO)

    # FIRE_SAFETY_EVIDENCE: exclude from v1 (no add)

    return applicable
