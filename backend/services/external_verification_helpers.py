"""Official external verification helper mappings (reviewer support only)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


OFFICIAL_EPC = "https://www.gov.uk/find-energy-certificate"
OFFICIAL_GAS_SAFE = "https://www.gassaferegister.co.uk/"
OFFICIAL_NICEIC = "https://www.niceic.com/"
OFFICIAL_NAPIT = "https://search.napit.org.uk/"
OFFICIAL_COMPANIES_HOUSE = "https://find-and-update.company-information.service.gov.uk/"


def _req_code(requirement: Optional[Dict[str, Any]], document: Dict[str, Any]) -> str:
    req = requirement or {}
    code = str(req.get("requirement_code") or req.get("requirement_type") or document.get("document_type") or "").strip().upper()
    return code.replace("-", "_")


def _extract_fields(document: Dict[str, Any]) -> Dict[str, Any]:
    ai = document.get("ai_assistance") if isinstance(document.get("ai_assistance"), dict) else {}
    ef = ai.get("extracted_fields") if isinstance(ai.get("extracted_fields"), dict) else {}
    meta = document.get("document_metadata") if isinstance(document.get("document_metadata"), dict) else {}
    out = dict(meta)
    out.update(ef)
    return out


def build_verification_helpers(requirement: Optional[Dict[str, Any]], document: Dict[str, Any]) -> Dict[str, Any]:
    """Returns supported helper links + relevant extracted hints. No verification side effects."""
    code = _req_code(requirement, document)
    extracted = _extract_fields(document)
    helpers: List[Dict[str, Any]] = []

    if "EPC" in code:
        helpers.append(
            {
                "helper_type": "EPC",
                "official_source": "EPC Register",
                "url": OFFICIAL_EPC,
                "suggested_method": "EPC_REGISTER_CHECK",
                "extracted_hints": {
                    "certificate_number": extracted.get("certificate_number"),
                    "property_postcode": extracted.get("postcode") or extracted.get("property_postcode"),
                },
            }
        )
    if "GAS" in code:
        helpers.append(
            {
                "helper_type": "GAS_SAFETY",
                "official_source": "Gas Safe Register",
                "url": OFFICIAL_GAS_SAFE,
                "suggested_method": "GAS_SAFE_LOOKUP",
                "extracted_hints": {
                    "engineer_name": extracted.get("engineer_name"),
                    "gas_safe_number": extracted.get("gas_safe_number"),
                    "certificate_number": extracted.get("certificate_number"),
                },
            }
        )
    if "EICR" in code or "ELECTRICAL" in code:
        helpers.append(
            {
                "helper_type": "ELECTRICAL_CONTRACTOR",
                "official_source": "NICEIC",
                "url": OFFICIAL_NICEIC,
                "suggested_method": "NICEIC_LOOKUP",
                "extracted_hints": {
                    "contractor_name": extracted.get("electrician_details", {}).get("name")
                    if isinstance(extracted.get("electrician_details"), dict)
                    else extracted.get("engineer_name"),
                    "registration_number": extracted.get("electrician_details", {}).get("registration_number")
                    if isinstance(extracted.get("electrician_details"), dict)
                    else extracted.get("inspector_id"),
                },
            }
        )
        helpers.append(
            {
                "helper_type": "ELECTRICAL_CONTRACTOR",
                "official_source": "NAPIT",
                "url": OFFICIAL_NAPIT,
                "suggested_method": "NAPIT_LOOKUP",
                "extracted_hints": {
                    "contractor_name": extracted.get("electrician_details", {}).get("name")
                    if isinstance(extracted.get("electrician_details"), dict)
                    else extracted.get("engineer_name"),
                    "registration_number": extracted.get("electrician_details", {}).get("registration_number")
                    if isinstance(extracted.get("electrician_details"), dict)
                    else extracted.get("inspector_id"),
                },
            }
        )

    # Optional helper - company verification
    company = extracted.get("inspector_company") or extracted.get("company_name")
    if company:
        helpers.append(
            {
                "helper_type": "COMPANY_VERIFICATION",
                "official_source": "Companies House",
                "url": OFFICIAL_COMPANIES_HOUSE,
                "suggested_method": "MANUAL_CONFIRMATION",
                "extracted_hints": {"company_name": company},
            }
        )

    return {"requirement_code": code or "UNKNOWN", "helpers": helpers}

