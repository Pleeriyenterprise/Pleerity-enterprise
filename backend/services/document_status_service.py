"""
Deterministic document status computation for compliance scoring.
Enterprise-safe, no legal verdict. Picks single evidence doc per type and computes status.
"""
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

# Config: env override
EXPIRING_SOON_DAYS = int(os.environ.get("COMPLIANCE_EXPIRING_SOON_DAYS", "60"))
_CONFIDENCE_THRESHOLD_ENV = os.environ.get("COMPLIANCE_CONFIDENCE_THRESHOLD")
CONFIDENCE_THRESHOLD: Optional[float] = float(_CONFIDENCE_THRESHOLD_ENV) if _CONFIDENCE_THRESHOLD_ENV else None

# Status and reason codes
STATUS_MISSING_EVIDENCE = "MISSING_EVIDENCE"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_VALID = "VALID"
STATUS_EXPIRING_SOON = "EXPIRING_SOON"
STATUS_EXPIRED = "EXPIRED"
REASON_NO_DOCUMENT_FOUND = "NO_DOCUMENT_FOUND"
REASON_MISSING_EXPIRY_DATE = "MISSING_EXPIRY_DATE"
REASON_DOCUMENT_EXPIRED = "DOCUMENT_EXPIRED"
REASON_DOCUMENT_EXPIRING_SOON = "DOCUMENT_EXPIRING_SOON"
REASON_LOW_CONFIDENCE = "LOW_CONFIDENCE"
REASON_UNVERIFIED_DOCUMENT = "UNVERIFIED_DOCUMENT"

# Map status -> score fraction (task spec)
STATUS_TO_FRACTION = {
    STATUS_VALID: 1.0,
    STATUS_EXPIRING_SOON: 0.8,
    STATUS_NEEDS_REVIEW: 0.5,
    STATUS_EXPIRED: 0.1,
    STATUS_MISSING_EVIDENCE: 0.0,
}


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    try:
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        s = (val.replace("Z", "+00:00") if isinstance(val, str) else str(val)).strip()
        dt = datetime.fromisoformat(s)
        return dt.date() if hasattr(dt, "date") else dt
    except Exception:
        return None


def _doc_expiry_date(doc: Dict[str, Any]) -> Optional[date]:
    """Get expiry date from doc (top-level or ai_extraction.data)."""
    if not doc:
        return None
    exp = doc.get("expiry_date")
    if exp is not None:
        return _parse_date(exp)
    ai = doc.get("ai_extraction") or {}
    data = ai.get("data") or {}
    exp = data.get("expiry_date")
    if exp is not None:
        return _parse_date(exp)
    return None


def _doc_uploaded_at(doc: Dict[str, Any]) -> Optional[datetime]:
    val = doc.get("uploaded_at")
    if val is None:
        return None
    try:
        if isinstance(val, datetime):
            return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
        s = (val.replace("Z", "+00:00") if isinstance(val, str) else str(val)).strip()
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _doc_updated_at(doc: Dict[str, Any]) -> Optional[datetime]:
    val = doc.get("updated_at")
    if val is None:
        return None
    try:
        if isinstance(val, datetime):
            return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
        s = (val.replace("Z", "+00:00") if isinstance(val, str) else str(val)).strip()
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _doc_id(doc: Dict[str, Any]) -> Any:
    return doc.get("_id") or doc.get("document_id") or id(doc)


def pick_evidence_document(docs: List[Dict[str, Any]], document_type: str) -> Optional[Dict[str, Any]]:
    """
    From candidate docs, pick the single evidence document.
    Rules:
    - Filter out: deleted=true, quarantined=true, malware_flagged=true, status=="DISABLED"
    - Among remaining: 1) Prefer docs with expiry_date in the future; pick latest expiry_date
    - 2) If none have expiry_date, pick newest by uploaded_at
    - 3) Ties: newest updated_at then _id
    """
    if not docs:
        return None
    today = date.today()
    eligible = []
    for d in docs:
        if d.get("deleted") is True or d.get("quarantined") is True or d.get("malware_flagged") is True:
            continue
        if (d.get("status") or "").upper().strip() == "DISABLED":
            continue
        # Optional: if doc has document_type, filter to match
        doc_type = (d.get("document_type") or (d.get("ai_extraction") or {}).get("data") or {}).get("document_type")
        if doc_type is not None and document_type and str(doc_type).strip().lower() != str(document_type).strip().lower():
            continue
        eligible.append(d)
    if not eligible:
        return None
    # With future expiry: pick latest expiry_date
    with_expiry = [d for d in eligible if _doc_expiry_date(d) is not None and _doc_expiry_date(d) >= today]
    if with_expiry:
        with_expiry.sort(key=lambda d: (_doc_expiry_date(d) or date.min), reverse=True)
        return with_expiry[0]
    # No future expiry: pick newest by uploaded_at
    with_upload = [(d, _doc_uploaded_at(d)) for d in eligible]
    with_upload.sort(key=lambda x: (x[1] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    best_upload = with_upload[0][1]
    tied = [d for d, u in with_upload if u == best_upload]
    if len(tied) == 1:
        return tied[0]
    # Tie-break: updated_at then _id
    tied_with_updated = [(d, _doc_updated_at(d), _doc_id(d)) for d in tied]
    tied_with_updated.sort(key=lambda x: (x[1] or datetime.min.replace(tzinfo=timezone.utc), str(x[2])), reverse=True)
    return tied_with_updated[0][0]


def compute_requirement_status(
    today: date,
    doc: Optional[Dict[str, Any]],
    expects_expiry: bool,
    expiring_soon_days: int,
) -> Dict[str, Any]:
    """
    Returns { status, expiry_date, days_to_expiry, reason_codes }.
    - doc None -> MISSING_EVIDENCE, NO_DOCUMENT_FOUND
    - expects_expiry and no doc.expiry_date -> NEEDS_REVIEW, MISSING_EXPIRY_DATE
    - expiry_date < today -> EXPIRED, DOCUMENT_EXPIRED
    - days_to_expiry <= expiring_soon_days -> EXPIRING_SOON, DOCUMENT_EXPIRING_SOON
    - else -> VALID
    - If verification_status != VERIFIED or confidence < CONFIDENCE_THRESHOLD: downgrade VALID/EXPIRING_SOON -> NEEDS_REVIEW (only if fields exist).
    """
    reason_codes: List[str] = []
    if doc is None:
        return {
            "status": STATUS_MISSING_EVIDENCE,
            "expiry_date": None,
            "days_to_expiry": None,
            "reason_codes": [REASON_NO_DOCUMENT_FOUND],
        }
    expiry_date = _doc_expiry_date(doc)
    if expects_expiry and expiry_date is None:
        return {
            "status": STATUS_NEEDS_REVIEW,
            "expiry_date": None,
            "days_to_expiry": None,
            "reason_codes": [REASON_MISSING_EXPIRY_DATE],
        }
    status = STATUS_VALID
    days_to_expiry: Optional[int] = None
    if expiry_date is not None:
        days_to_expiry = (expiry_date - today).days
        if days_to_expiry < 0:
            status = STATUS_EXPIRED
            reason_codes.append(REASON_DOCUMENT_EXPIRED)
        elif days_to_expiry <= expiring_soon_days:
            status = STATUS_EXPIRING_SOON
            reason_codes.append(REASON_DOCUMENT_EXPIRING_SOON)
    # Downgrade for unverified or low confidence (only if fields exist)
    verification_status = (doc.get("verification_status") or doc.get("status") or "").upper().strip()
    if verification_status == "UNVERIFIED" or (verification_status and verification_status != "VERIFIED"):
        if status in (STATUS_VALID, STATUS_EXPIRING_SOON):
            status = STATUS_NEEDS_REVIEW
            reason_codes.append(REASON_UNVERIFIED_DOCUMENT)
    if CONFIDENCE_THRESHOLD is not None:
        confidence = doc.get("confidence_score")
        if confidence is None:
            ai = doc.get("ai_extraction") or {}
            data = ai.get("data") or {}
            conf_obj = (data.get("confidence_scores") or data.get("confidence")) or {}
            confidence = conf_obj.get("overall") if isinstance(conf_obj, dict) else conf_obj
        if confidence is not None and float(confidence) < CONFIDENCE_THRESHOLD:
            if status in (STATUS_VALID, STATUS_EXPIRING_SOON):
                status = STATUS_NEEDS_REVIEW
                reason_codes.append(REASON_LOW_CONFIDENCE)
    return {
        "status": status,
        "expiry_date": expiry_date.isoformat() if expiry_date else None,
        "days_to_expiry": days_to_expiry,
        "reason_codes": reason_codes,
    }
