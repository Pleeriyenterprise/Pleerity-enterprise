"""
Requirement catalog and applicability (deterministic, no legal verdicts).
Computes per-property applicable requirement keys for the compliance score engine.
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


def get_applicable_requirements(property_doc: dict) -> List[str]:
    """
    Return list of applicable canonical requirement keys for this property.
    Rules (MUST follow exactly):
    - EICR_CERT, EPC_CERT: always applicable.
    - GAS_SAFETY_CERT: applicable iff cert_gas_safety == "YES" (do not penalize when NO).
    - PROPERTY_LICENCE: applicable iff is_hmo or licence_required=="YES" or cert_licence=="YES" or licence_type non-empty.
    - Tenancy docs: not scored in v1 unless tenancy_active == true; if absent, exclude.
    - Deposit prescribed info: only if deposit_taken == true; if absent, exclude.
    - FIRE_SAFETY_EVIDENCE: excluded from v1.
    """
    applicable: List[str] = []

    # Always applicable
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

    # Tenancy: only if tenancy_active == true; if field absent, exclude
    if _str_truthy(property_doc.get("tenancy_active")):
        applicable.append(TENANCY_AGREEMENT)
        applicable.append(HOW_TO_RENT)

    # Deposit prescribed info: only if deposit_taken == true; if absent, exclude
    if _str_truthy(property_doc.get("deposit_taken")):
        applicable.append(DEPOSIT_PRESCRIBED_INFO)

    # FIRE_SAFETY_EVIDENCE: exclude from v1 (no add)

    return applicable
