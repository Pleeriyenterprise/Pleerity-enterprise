"""AI-assisted extraction normalization + reviewer assistance + anomaly checks.

Safety model:
- Suggestions only; never marks compliance as verified.
- Outputs are auditable and deterministic-friendly.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


def _parse_date(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    s = str(v).strip()
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        if "T" in s:
            d = datetime.fromisoformat(s)
        else:
            d = datetime.fromisoformat(f"{s[:10]}T00:00:00+00:00")
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _normalize_req_code(requirement: Optional[Dict[str, Any]], extracted_doc_type: Optional[str]) -> str:
    if isinstance(requirement, dict):
        code = str(requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip().upper()
        if code:
            return code
    return str(extracted_doc_type or "").strip().upper() or "UNKNOWN"


def normalize_extracted_fields_by_requirement(raw: Dict[str, Any], requirement_code: str) -> Dict[str, Any]:
    """Map heterogeneous extraction payload into deterministic field names by requirement family."""
    r = raw or {}
    rc = str(requirement_code or "").upper()
    out: Dict[str, Any] = {
        "address": r.get("property_address") or r.get("address") or r.get("address_line_1"),
        "inspection_date": r.get("issue_date") or r.get("inspection_date"),
        "next_inspection_date": r.get("expiry_date") or r.get("next_inspection_date"),
        "certificate_number": r.get("certificate_number"),
    }
    engineer = r.get("engineer_details") if isinstance(r.get("engineer_details"), dict) else {}
    result_summary = r.get("result_summary") if isinstance(r.get("result_summary"), dict) else {}
    findings = r.get("findings") if isinstance(r.get("findings"), dict) else {}
    defects = findings.get("defects") if isinstance(findings.get("defects"), list) else []
    warnings = findings.get("warnings") if isinstance(findings.get("warnings"), list) else []

    if "GAS" in rc:
        out.update(
            {
                "engineer_name": engineer.get("name") or r.get("inspector_company"),
                "gas_safe_number": engineer.get("registration_number") or r.get("inspector_id"),
                "appliance_list": r.get("appliances_or_items") or [],
                "pass_fail_indicator": result_summary.get("overall_result"),
            }
        )
    elif "EICR" in rc:
        out.update(
            {
                "electrician_details": {
                    "name": engineer.get("name"),
                    "registration_number": engineer.get("registration_number"),
                    "scheme": engineer.get("registration_scheme"),
                },
                "overall_outcome": result_summary.get("overall_result") or result_summary.get("rating"),
                "observations_c1_c2_fi": [x for x in defects + warnings if str(x).upper().find("C1") >= 0 or str(x).upper().find("C2") >= 0 or str(x).upper().find("FI") >= 0],
            }
        )
    elif "EPC" in rc:
        out.update(
            {
                "epc_rating": result_summary.get("rating"),
                "expiry_date": out.get("next_inspection_date"),
            }
        )
    elif "HMO" in rc:
        out.update(
            {
                "authority": r.get("issuing_authority") or engineer.get("company_name"),
                "licence_number": r.get("certificate_number"),
                "expiry_date": out.get("next_inspection_date"),
                "occupancy_limits": r.get("occupancy_limits"),
            }
        )
    elif "DEPOSIT" in rc:
        out.update(
            {
                "scheme_name": engineer.get("company_name") or r.get("scheme_name"),
                "protection_reference": r.get("certificate_number"),
                "protected_date": out.get("inspection_date"),
            }
        )
    return out


def build_reviewer_assistance_signals(
    *,
    extracted_fields: Dict[str, Any],
    property_doc: Optional[Dict[str, Any]],
    requirement_code: str,
    extraction_confidence: float,
) -> Tuple[List[str], List[str]]:
    """Returns (ai_flags, extraction_warnings)."""
    flags: List[str] = []
    warnings: List[str] = []
    rc = str(requirement_code or "").upper()

    addr = str(extracted_fields.get("address") or "").strip().lower()
    paddr = ""
    if isinstance(property_doc, dict):
        ad = property_doc.get("address") if isinstance(property_doc.get("address"), dict) else {}
        paddr = str((ad.get("line1") if isinstance(ad, dict) else None) or property_doc.get("address_line_1") or "").strip().lower()
    if addr and paddr and addr not in paddr and paddr not in addr:
        flags.append("POSSIBLE_ADDRESS_MISMATCH")

    exp = _parse_date(extracted_fields.get("expiry_date") or extracted_fields.get("next_inspection_date"))
    if exp and exp < datetime.now(timezone.utc):
        flags.append("DOCUMENT_APPEARS_EXPIRED")
    if exp is None and any(x in rc for x in ("GAS", "EICR", "EPC", "HMO")):
        warnings.append("EXPIRY_UNREADABLE_OR_MISSING")
    if extraction_confidence < 0.55:
        warnings.append("LOW_EXTRACTION_CONFIDENCE")
    if "EICR" in rc:
        outcome = str(extracted_fields.get("overall_outcome") or "").upper()
        obs = extracted_fields.get("observations_c1_c2_fi") if isinstance(extracted_fields.get("observations_c1_c2_fi"), list) else []
        if any(tok in outcome for tok in ("C1", "C2", "FI", "UNSATISFACTORY")) or obs:
            flags.append("EICR_CONTAINS_SERIOUS_OBSERVATIONS")
    if "GAS" in rc and not str(extracted_fields.get("gas_safe_number") or "").strip():
        warnings.append("GAS_SAFE_NUMBER_MISSING")
    return flags, warnings


async def detect_anomalies_for_extraction(
    db: Any,
    *,
    document: Dict[str, Any],
    extracted_fields: Dict[str, Any],
    extraction_confidence: float,
    extraction_source: str,
) -> Tuple[List[Dict[str, Any]], float]:
    flags: List[Dict[str, Any]] = []
    risk = 0.0

    cert = str(extracted_fields.get("certificate_number") or extracted_fields.get("licence_number") or extracted_fields.get("protection_reference") or "").strip()
    if cert:
        dup_q = {
            "document_id": {"$ne": document.get("document_id")},
            "$or": [
                {"ai_assistance.extracted_fields.certificate_number": cert},
                {"ai_assistance.extracted_fields.licence_number": cert},
                {"ai_assistance.extracted_fields.protection_reference": cert},
            ],
            "deleted": {"$ne": True},
        }
        dup_rows = await db.documents.find(dup_q, {"_id": 0, "document_id": 1, "property_id": 1}).limit(10).to_list(10)
        if dup_rows:
            other_props = {str(x.get("property_id") or "") for x in dup_rows}
            if str(document.get("property_id") or "") not in other_props:
                flags.append({"code": "DUPLICATE_CERTIFICATE_NUMBER", "severity": "high", "details": {"certificate_number": cert, "other_document_count": len(dup_rows)}})
                risk += 0.35

    issue = _parse_date(extracted_fields.get("inspection_date"))
    expiry = _parse_date(extracted_fields.get("expiry_date") or extracted_fields.get("next_inspection_date"))
    upload = _parse_date(document.get("uploaded_at"))
    if issue and upload and issue > upload + timedelta(days=2):
        flags.append({"code": "DOCUMENT_DATE_AFTER_UPLOAD", "severity": "medium", "details": {"inspection_date": issue.isoformat(), "uploaded_at": upload.isoformat()}})
        risk += 0.2
    if issue and expiry and expiry < issue:
        flags.append({"code": "IMPOSSIBLE_EXPIRY_BEFORE_ISSUE", "severity": "high", "details": {"inspection_date": issue.isoformat(), "expiry_date": expiry.isoformat()}})
        risk += 0.3
    if issue and expiry and (expiry - issue).days > 3650:
        flags.append({"code": "IMPOSSIBLE_EXPIRY_RANGE", "severity": "medium", "details": {"inspection_date": issue.isoformat(), "expiry_date": expiry.isoformat()}})
        risk += 0.2
    if extraction_source == "ocr" and extraction_confidence < 0.6:
        flags.append({"code": "LOW_OCR_CONFIDENCE", "severity": "medium", "details": {"confidence": extraction_confidence}})
        risk += 0.15
    return flags, min(1.0, risk)

