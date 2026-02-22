"""
Compliance Score v1: evidence-based scoring (no legal verdicts).
Inputs: property record + linked requirements + linked documents.
Applicable requirements from requirement_catalog.get_applicable_requirements(); only those are scored; weights renormalize to 100.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.requirement_catalog import get_applicable_requirements, REQUIREMENT_KEY_TO_DOCUMENT_TYPE
from services.document_status_service import (
    pick_evidence_document,
    compute_requirement_status,
    STATUS_TO_FRACTION,
    EXPIRING_SOON_DAYS,
)

# Base weights keyed by canonical catalog key (used only for applicable requirements; renormalized to 100)
BASE_WEIGHTS = {
    "GAS_SAFETY_CERT": 30,
    "EICR_CERT": 25,
    "EPC_CERT": 15,
    "PROPERTY_LICENCE": 20,
    "TENANCY_AGREEMENT": 10,
    "HOW_TO_RENT": 5,
    "DEPOSIT_PRESCRIBED_INFO": 10,
}
# Critical for risk: any missing/overdue forces at least High/Critical
CRITICAL_KEYS = {"GAS_SAFETY_CERT", "EICR_CERT", "PROPERTY_LICENCE"}

# Map requirement_type (from DB) to canonical catalog key for scoring
def _req_type_to_key(requirement_type: str) -> Optional[str]:
    if not requirement_type:
        return None
    t = (requirement_type or "").strip().upper().replace("-", "_")
    if t in ("GAS_SAFETY", "GAS_SAFETY_CERTIFICATE", "CP12", "GAS_SAFETY_CERT"):
        return "GAS_SAFETY_CERT"
    if t in ("EICR", "ELECTRICAL_INSTALLATION", "EICR_CERT"):
        return "EICR_CERT"
    if t in ("EPC", "ENERGY_PERFORMANCE", "EPC_CERT"):
        return "EPC_CERT"
    if t in ("HMO_LICENCE", "HMO_LICENSE", "LICENCE", "LICENSE", "PROPERTY_LICENCE"):
        return "PROPERTY_LICENCE"
    if t in ("TENANCY_AGREEMENT", "INVENTORY", "TENANCY_BUNDLE"):
        return "TENANCY_AGREEMENT"
    if t in ("HOW_TO_RENT",):
        return "HOW_TO_RENT"
    if t in ("DEPOSIT_PROTECTION", "DEPOSIT_PRESCRIBED_INFO", "RIGHT_TO_RENT"):
        return "DEPOSIT_PRESCRIBED_INFO"
    return None


def _parse_due(due_date_any: Any) -> Optional[datetime]:
    if due_date_any is None:
        return None
    try:
        if isinstance(due_date_any, datetime):
            return due_date_any.replace(tzinfo=timezone.utc) if due_date_any.tzinfo is None else due_date_any
        s = (due_date_any.replace("Z", "+00:00") if isinstance(due_date_any, str) else str(due_date_any)).strip()
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _days_to_expiry(due_date_any: Any, as_of: Optional[datetime] = None) -> Optional[int]:
    """Days until due (negative if overdue)."""
    due = _parse_due(due_date_any)
    if due is None:
        return None
    now = as_of or datetime.now(timezone.utc)
    return (due - now).days


def status_factor(
    status: str,
    days_to_expiry: Optional[int],
    has_linked_document: bool,
    needs_review: bool,
) -> float:
    """
    S(r) per spec:
    - Valid: days_to_expiry > 30 => 1.00
    - Expiring soon: 0 < days_to_expiry <= 30 => 0.70
    - Overdue: days_to_expiry <= 0 => 0.25
    - Missing evidence: no linked document or required expiry missing => 0.00
    - Needs review: doc exists but flagged low confidence/mismatch => 0.50
    """
    status = (status or "").upper().strip()
    if needs_review and has_linked_document:
        return 0.50
    if status in ("OVERDUE", "EXPIRED"):
        return 0.25
    if not has_linked_document or (days_to_expiry is None and status not in ("COMPLIANT", "VALID")):
        return 0.00
    if days_to_expiry is not None:
        if days_to_expiry <= 0:
            return 0.25
        if 0 < days_to_expiry <= 30:
            return 0.70
        if days_to_expiry > 30:
            return 1.00
    if status in ("COMPLIANT", "VALID"):
        return 1.00
    if status == "EXPIRING_SOON":
        return 0.70
    return 0.00


def _applicable_weights(property_doc: Dict[str, Any]) -> Dict[str, float]:
    """Base weights for applicable requirements only (from requirement_catalog; renormalized to 100 in score)."""
    applicable = get_applicable_requirements(property_doc)
    return {k: float(BASE_WEIGHTS[k]) for k in applicable if k in BASE_WEIGHTS}


def _multiplier(
    key: str,
    is_hmo: bool,
    occupancy: Optional[str],
    bedrooms: Optional[int],
) -> float:
    """M(r): HMO and occupancy/bedrooms multipliers (catalog keys)."""
    m = 1.0
    if is_hmo:
        if key == "GAS_SAFETY_CERT":
            m *= 1.10
        if key == "EICR_CERT":
            m *= 1.15
        if key == "PROPERTY_LICENCE":
            m *= 1.25
    if key == "PROPERTY_LICENCE" and ((occupancy or "").strip().lower() != "single_family" or (bedrooms or 0) >= 5):
        m *= 1.10
    return m


def _needs_review(doc: Dict[str, Any]) -> bool:
    """True if document exists but low confidence or mismatch (Needs review)."""
    if not doc:
        return False
    status = (doc.get("status") or "").upper()
    if status != "VERIFIED":
        return True
    ai = doc.get("ai_extraction") or {}
    confidence = (ai.get("data") or {}).get("confidence_scores") or {}
    overall = confidence.get("overall")
    if overall is not None and float(overall) < 0.6:
        return True
    review = (ai.get("review_status") or "").lower()
    if review in ("rejected", "pending"):
        return True
    return False


def compute_property_score(
    property_doc: Dict[str, Any],
    requirements: List[Dict[str, Any]],
    documents: List[Dict[str, Any]],
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Compute v1 score for one property.
    Returns: { score_0_100, risk_level, breakdown: [ { requirement_key, weight, status, status_factor, days_to_expiry } ] }
    """
    now = as_of or datetime.now(timezone.utc)
    prop_id = property_doc.get("property_id", "")
    is_hmo = bool(property_doc.get("is_hmo", False))
    occupancy = property_doc.get("occupancy")
    bedrooms = property_doc.get("bedrooms")

    applicable_w = _applicable_weights(property_doc)
    if not applicable_w:
        return {
            "score_0_100": 100,
            "risk_level": "Low risk",
            "breakdown": [],
        }

    # requirement_id -> catalog key (for docs linked to that requirement)
    req_id_to_key: Dict[str, str] = {}
    for r in requirements:
        req_type = r.get("requirement_type") or r.get("requirement_code")
        key = _req_type_to_key(req_type)
        if key is not None and key in applicable_w:
            rid = r.get("requirement_id") or r.get("id")
            if rid:
                req_id_to_key[rid] = key

    today = now.date()
    expects_expiry_keys = {"GAS_SAFETY_CERT", "EICR_CERT", "EPC_CERT", "PROPERTY_LICENCE"}
    key_to_best: Dict[str, Dict[str, Any]] = {}
    for key in applicable_w:
        req_ids_for_key = [rid for rid, k in req_id_to_key.items() if k == key]
        candidate_docs = [d for d in documents if d.get("requirement_id") in req_ids_for_key]
        document_type = REQUIREMENT_KEY_TO_DOCUMENT_TYPE.get(key, "")
        evidence_doc = pick_evidence_document(candidate_docs, document_type)
        expects_expiry = key in expects_expiry_keys
        status_result = compute_requirement_status(today, evidence_doc, expects_expiry, EXPIRING_SOON_DAYS)
        fraction = STATUS_TO_FRACTION.get(status_result["status"], 0.0)
        key_to_best[key] = {
            "requirement_key": key,
            "weight": applicable_w[key],
            "status": status_result["status"],
            "status_factor": fraction,
            "days_to_expiry": status_result.get("days_to_expiry"),
        }

    breakdown = []
    We_total = 0.0
    for key in applicable_w:
        m = _multiplier(key, is_hmo, occupancy, bedrooms)
        we = applicable_w[key] * m
        row = key_to_best.get(key) or {
            "requirement_key": key,
            "weight": applicable_w[key],
            "status": "PENDING",
            "status_factor": 0.0,
            "days_to_expiry": None,
        }
        row["effective_weight"] = we
        breakdown.append(row)
        We_total += we

    if We_total <= 0:
        return {
            "score_0_100": 100,
            "risk_level": "Low risk",
            "breakdown": breakdown,
        }

    score_sum = 0.0
    for row in breakdown:
        we = row["effective_weight"]
        wn = 100.0 * we / We_total
        score_sum += wn * row["status_factor"]

    score_0_100 = round(max(0, min(100, score_sum)))
    risk_level = _risk_level_from_breakdown(score_0_100, breakdown, applicable_w)

    for row in breakdown:
        row.pop("effective_weight", None)

    return {
        "score_0_100": score_0_100,
        "risk_level": risk_level,
        "breakdown": breakdown,
    }


def _risk_level_from_breakdown(
    score: int,
    breakdown: List[Dict[str, Any]],
    applicable_weights: Dict[str, float],
) -> str:
    """
    Critical = Gas, EICR, Licence (when required).
    Critical if any critical missing OR score < 40.
    High if any critical overdue OR 40 <= score < 60.
    Medium if 60 <= score < 80.
    Low if score >= 80 AND no critical overdue/missing.
    """
    critical_keys = {k for k in CRITICAL_KEYS if k in applicable_weights}
    critical_missing = False
    critical_overdue = False
    for row in breakdown:
        key = row.get("requirement_key")
        if key not in critical_keys:
            continue
        s = row.get("status_factor", 0)
        status = (row.get("status") or "").upper()
        if s <= 0.0:
            critical_missing = True
        if s in (0.25, 0.1) or status in ("EXPIRED", "OVERDUE"):
            critical_overdue = True

    if critical_missing:
        return "Critical risk"
    if score < 40:
        return "Critical risk"
    if critical_overdue:
        return "High risk"
    if score < 60:
        return "High risk"
    if score < 80:
        return "Medium risk"
    return "Low risk"


def portfolio_score_and_risk(
    properties_with_scores: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    E(p) = 1 + 0.5 if HMO + 0.2 if bedrooms >= 4 + 0.2 if occupancy != single_family.
    portfolioScore = weighted average by E(p).
    portfolioRisk = worst(property risk).
    """
    if not properties_with_scores:
        return {"portfolio_score": 100, "portfolio_risk_level": "Low risk"}

    order = ("Low risk", "Medium risk", "High risk", "Critical risk")
    def risk_ord(r: str) -> int:
        try:
            return order.index(r) if r in order else -1
        except (ValueError, TypeError):
            return -1

    weighted_sum = 0.0
    weight_sum = 0.0
    worst_risk = "Low risk"
    for p in properties_with_scores:
        score = p.get("compliance_score") or p.get("score_0_100") or p.get("score")
        risk = p.get("risk_level") or "Low risk"
        is_hmo = bool(p.get("is_hmo", False))
        bedrooms = p.get("bedrooms") or 0
        occupancy = (p.get("occupancy") or "").strip().lower()
        e = 1.0 + (0.5 if is_hmo else 0) + (0.2 if bedrooms >= 4 else 0) + (0.2 if occupancy != "single_family" else 0)
        if score is not None:
            weighted_sum += float(score) * e
            weight_sum += e
        if risk_ord(risk) > risk_ord(worst_risk):
            worst_risk = risk

    portfolio_score = round(weighted_sum / weight_sum) if weight_sum > 0 else 100
    portfolio_score = max(0, min(100, portfolio_score))
    return {
        "portfolio_score": portfolio_score,
        "portfolio_risk_level": worst_risk,
    }
