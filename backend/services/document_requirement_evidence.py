"""
Heuristics for linking extracted document types to compliance requirement rows.
Used to flag likely wrong-slot uploads without blocking manual confirmation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# Normalized requirement keys (requirement_type / requirement_code) → substrings that should appear
# in the AI-extracted document_type (and optional subtype) when the classification is confident.
_REQ_TYPE_HINTS: Dict[str, Tuple[str, ...]] = {
    "gas_safety": ("gas safety", "gas certificate", "cp12", "cp17", "landlord gas", "gas safe"),
    "eicr": ("eicr", "electrical installation", "electrical condition", "periodic inspection", "fixed installation"),
    "epc": ("epc", "energy performance"),
    "fire_detection": ("fire alarm", "smoke alarm", "heat alarm", "fire detection", "carbon monoxide", "co alarm"),
    "legionella": ("legionella", "water risk", "l8"),
    "hmo_fire_risk": ("fire risk", "frar", "hmo fire", "fire safety"),
    "landlord_registration": ("landlord registration", "registration", "scotland landlord"),
    "occupation_contract": ("occupation contract", "rent smart wales", "written statement", "tenancy"),
}

_REQ_ALIASES = {
    "gas_safety_cert": "gas_safety",
    "cp12": "gas_safety",
    "gas_safety_certificate": "gas_safety",
    "eicr_cert": "eicr",
    "electrical_installation": "eicr",
    "epc_cert": "epc",
    "smoke_alarm": "fire_detection",
    "co_alarm": "fire_detection",
    "fire_alarm": "fire_detection",
    "fire_risk_assessment": "hmo_fire_risk",
    "hmo_fire_risk_evidence": "hmo_fire_risk",
    "legionella_risk": "legionella",
    "scotland_landlord_registration": "landlord_registration",
    "landlord_registration_scotland": "landlord_registration",
    "wales_occupation_contract": "occupation_contract",
}


def _norm_req_key(raw: Optional[str]) -> str:
    if not raw:
        return ""
    s = str(raw).strip().lower().replace("-", "_")
    s = re.sub(r"\s+", "_", s)
    return _REQ_ALIASES.get(s, s)


def _flatten_extracted_type(extracted: Dict[str, Any]) -> str:
    parts = [
        extracted.get("document_type"),
        extracted.get("document_subtype"),
        extracted.get("doc_type"),
    ]
    return " ".join(str(p) for p in parts if p).strip().lower()


def detect_requirement_document_mismatch(
    requirement: Optional[Dict[str, Any]],
    extracted_data: Optional[Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    """
    Returns (is_mismatch, short_reason).

    When extraction did not yield a usable document_type, returns (False, None) to avoid false positives.
    """
    if not requirement or not isinstance(extracted_data, dict):
        return False, None
    rtype = _norm_req_key(requirement.get("requirement_type") or requirement.get("requirement_code"))
    if not rtype:
        return False, None
    hints = _REQ_TYPE_HINTS.get(rtype)
    if not hints:
        return False, None

    blob = _flatten_extracted_type(extracted_data)
    if len(blob) < 4:
        return False, None

    if any(h in blob for h in hints):
        return False, None

    return True, f"Extracted type “{blob[:120]}” does not match expected evidence for {rtype.replace('_', ' ')}"
