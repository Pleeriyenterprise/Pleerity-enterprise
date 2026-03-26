from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from services.document_status_service import (
    EXPIRING_SOON_DAYS,
    STATUS_TO_FRACTION,
    compute_requirement_status,
    pick_evidence_document,
)


BUCKET_WEIGHTS = {
    "legal_core": 60.0,
    "documentation_completeness": 20.0,
    "operational_responsiveness": 10.0,
    "recency_maintenance_confidence": 10.0,
}


JURISDICTION_PROFILES: Dict[str, Dict[str, Any]] = {
    "ENGLAND_WALES": {
        "requirements": {
            "GAS_SAFETY": {"weight": 15.0, "risk_level_if_failed": "HIGH"},
            "EICR": {"weight": 15.0, "risk_level_if_failed": "HIGH"},
            "EPC": {"weight": 10.0, "risk_level_if_failed": "MEDIUM"},
            "FIRE_DETECTION": {"weight": 10.0, "risk_level_if_failed": "HIGH"},
            "LEGIONELLA": {"weight": 10.0, "risk_level_if_failed": "MEDIUM"},
        },
        "expiring_soon_days": EXPIRING_SOON_DAYS,
    },
    "SCOTLAND": {
        "requirements": {
            "GAS_SAFETY": {"weight": 15.0, "risk_level_if_failed": "HIGH"},
            "EICR": {"weight": 15.0, "risk_level_if_failed": "HIGH"},
            "EPC": {"weight": 10.0, "risk_level_if_failed": "MEDIUM"},
            "FIRE_DETECTION": {"weight": 10.0, "risk_level_if_failed": "HIGH"},
            "LEGIONELLA": {"weight": 10.0, "risk_level_if_failed": "MEDIUM"},
        },
        "expiring_soon_days": EXPIRING_SOON_DAYS,
    },
}


REQ_ALIASES = {
    "GAS_SAFETY_CERT": "GAS_SAFETY",
    "CP12": "GAS_SAFETY",
    "GAS_SAFETY_CERTIFICATE": "GAS_SAFETY",
    "EICR_CERT": "EICR",
    "ELECTRICAL_INSTALLATION": "EICR",
    "EPC_CERT": "EPC",
    "SMOKE_ALARM": "FIRE_DETECTION",
    "CO_ALARM": "FIRE_DETECTION",
    "FIRE_RISK_ASSESSMENT": "FIRE_DETECTION",
    "FIRE_DOORS": "FIRE_DETECTION",
    "EMERGENCY_LIGHTING": "FIRE_DETECTION",
    "LEGIONELLA_RISK": "LEGIONELLA",
}

REQ_TO_DOC_TYPE = {
    "GAS_SAFETY": "gas_safety",
    "EICR": "eicr",
    "EPC": "epc",
    "FIRE_DETECTION": "fire_safety",
    "LEGIONELLA": "legionella",
}


def normalize_jurisdiction(raw: Optional[str]) -> str:
    value = (raw or "").strip().upper()
    if value in ("SCOTLAND",):
        return "SCOTLAND"
    if value in ("ENGLAND", "WALES", "ENGLAND/WALES", "ENGLAND_WALES"):
        return "ENGLAND_WALES"
    return "ENGLAND_WALES"


def normalize_requirement_code(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    key = str(raw).strip().upper().replace("-", "_")
    return REQ_ALIASES.get(key, key)


def _parse_due(v: Any) -> Optional[date]:
    if v is None:
        return None
    try:
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
    except Exception:
        return None


def _status_fraction_from_doc(code: str, docs: List[Dict[str, Any]], as_of: date, expiring_soon_days: int) -> Tuple[float, str, Optional[str], Optional[str], List[str]]:
    doc = pick_evidence_document(docs, REQ_TO_DOC_TYPE.get(code, ""))
    status_result = compute_requirement_status(as_of, doc, expects_expiry=code in ("GAS_SAFETY", "EICR", "EPC"), expiring_soon_days=expiring_soon_days)
    fraction = STATUS_TO_FRACTION.get(status_result["status"], 0.0)
    expiry_date = status_result.get("expiry_date")
    verified_at = None
    if doc and doc.get("verified_at"):
        verified_at = str(doc.get("verified_at"))
    elif doc and (doc.get("status") or "").upper() == "VERIFIED":
        verified_at = str(doc.get("updated_at") or doc.get("uploaded_at") or "")
    return fraction, status_result["status"], expiry_date, verified_at, status_result.get("reason_codes") or []


def _status_fraction_from_requirement(code: str, req: Optional[Dict[str, Any]], docs: List[Dict[str, Any]], as_of: date, expiring_soon_days: int) -> Tuple[float, str, Optional[str], Optional[str], List[str]]:
    if not req:
        return _status_fraction_from_doc(code, docs, as_of, expiring_soon_days)
    req_status = (req.get("status") or "").upper()
    due = _parse_due(req.get("due_date") or req.get("expiry_date"))
    verified_at = req.get("verified_at")
    if req_status in ("NOT_REQUIRED", "NOT_APPLICABLE"):
        return 1.0, "NOT_APPLICABLE", due.isoformat() if due else None, str(verified_at) if verified_at else None, []
    if due is not None:
        days = (due - as_of).days
        if days < 0:
            return 0.0, "EXPIRED", due.isoformat(), str(verified_at) if verified_at else None, ["DOCUMENT_EXPIRED"]
        if days <= expiring_soon_days:
            base = 0.7
            return base, "EXPIRING_SOON", due.isoformat(), str(verified_at) if verified_at else None, ["DOCUMENT_EXPIRING_SOON"]
    if req_status in ("COMPLIANT", "VALID", "VERIFIED"):
        return 1.0, "VALID", due.isoformat() if due else None, str(verified_at) if verified_at else None, []
    if req_status in ("EXPIRING_SOON",):
        return 0.7, "EXPIRING_SOON", due.isoformat() if due else None, str(verified_at) if verified_at else None, ["DOCUMENT_EXPIRING_SOON"]
    if req_status in ("OVERDUE", "EXPIRED"):
        return 0.0, "EXPIRED", due.isoformat() if due else None, str(verified_at) if verified_at else None, ["DOCUMENT_EXPIRED"]
    if req_status in ("PENDING", "MISSING"):
        return 0.0, "MISSING", due.isoformat() if due else None, str(verified_at) if verified_at else None, ["NO_DOCUMENT_FOUND"]
    return _status_fraction_from_doc(code, docs, as_of, expiring_soon_days)


def _applies_if(code: str, property_doc: Dict[str, Any]) -> bool:
    if code == "GAS_SAFETY":
        gas_decl = str(property_doc.get("cert_gas_safety") or "").upper() == "YES"
        has_gas = bool(property_doc.get("has_gas_supply") or property_doc.get("has_gas"))
        return gas_decl or has_gas
    return True


def compute_property_score_v2(
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    requirements: List[Dict[str, Any]],
    documents: List[Dict[str, Any]],
    open_issues_count: int,
    overdue_work_orders_count: int,
    open_risks_count: int,
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    today = now.date()
    jurisdiction = normalize_jurisdiction(property_doc.get("jurisdiction") or (client_doc or {}).get("default_jurisdiction"))
    profile = JURISDICTION_PROFILES[jurisdiction]
    expiring_soon_days = int(profile.get("expiring_soon_days", EXPIRING_SOON_DAYS))

    req_by_code: Dict[str, Dict[str, Any]] = {}
    docs_by_code: Dict[str, List[Dict[str, Any]]] = {}
    for req in requirements:
        code = normalize_requirement_code(req.get("requirement_code") or req.get("requirement_type"))
        if code:
            req_by_code[code] = req
    for doc in documents:
        code = normalize_requirement_code(doc.get("requirement_code") or doc.get("requirement_type") or doc.get("document_type"))
        if code:
            docs_by_code.setdefault(code, []).append(doc)

    earned_points = 0.0
    applicable_points = 0.0
    breakdown: List[Dict[str, Any]] = []

    for code, cfg in profile["requirements"].items():
        applies = _applies_if(code, property_doc)
        if not applies:
            breakdown.append({
                "requirement_code": code,
                "jurisdiction": jurisdiction,
                "applies_if": False,
                "weight": cfg["weight"],
                "status": "NOT_APPLICABLE",
                "expiry_date": None,
                "verified_at": None,
                "risk_level_if_failed": cfg["risk_level_if_failed"],
                "earned_points": 0.0,
                "applicable_points": 0.0,
                "reasons": [],
            })
            continue

        applicable_points += float(cfg["weight"])
        fraction, status, expiry_date, verified_at, reasons = _status_fraction_from_requirement(
            code,
            req_by_code.get(code),
            docs_by_code.get(code, []),
            today,
            expiring_soon_days,
        )
        req_points = round(float(cfg["weight"]) * fraction, 2)
        earned_points += req_points
        breakdown.append({
            "requirement_code": code,
            "jurisdiction": jurisdiction,
            "applies_if": True,
            "weight": float(cfg["weight"]),
            "status": status,
            "expiry_date": expiry_date,
            "verified_at": verified_at,
            "risk_level_if_failed": cfg["risk_level_if_failed"],
            "earned_points": req_points,
            "applicable_points": float(cfg["weight"]),
            "reasons": reasons,
        })

    legal_core_applicable = sum(item["applicable_points"] for item in breakdown)
    legal_core_earned = sum(item["earned_points"] for item in breakdown)
    legal_core_pct = (legal_core_earned / legal_core_applicable * 100.0) if legal_core_applicable > 0 else 100.0

    # Documentation completeness: proportion of applicable obligations with verified evidence.
    applicable_count = sum(1 for item in breakdown if item["applies_if"])
    verified_count = sum(1 for item in breakdown if item["applies_if"] and item["status"] in ("VALID", "EXPIRING_SOON"))
    docs_pct = (verified_count / applicable_count * 100.0) if applicable_count else 100.0
    docs_points = round(BUCKET_WEIGHTS["documentation_completeness"] * (docs_pct / 100.0), 2)

    # Operational responsiveness: unresolved issues/work-orders reduce confidence.
    op_penalty = min(100.0, open_issues_count * 8.0 + overdue_work_orders_count * 12.0)
    op_pct = max(0.0, 100.0 - op_penalty)
    op_points = round(BUCKET_WEIGHTS["operational_responsiveness"] * (op_pct / 100.0), 2)

    # Recency / maintenance confidence: unresolved risks + many expiring items.
    expiring_count = sum(1 for item in breakdown if item["status"] == "EXPIRING_SOON")
    recency_penalty = min(100.0, open_risks_count * 12.0 + expiring_count * 6.0)
    recency_pct = max(0.0, 100.0 - recency_penalty)
    recency_points = round(BUCKET_WEIGHTS["recency_maintenance_confidence"] * (recency_pct / 100.0), 2)

    legal_core_points = round(BUCKET_WEIGHTS["legal_core"] * (legal_core_pct / 100.0), 2)
    total_earned = round(legal_core_points + docs_points + op_points + recency_points, 2)
    total_applicable = round(
        BUCKET_WEIGHTS["legal_core"] + BUCKET_WEIGHTS["documentation_completeness"] + BUCKET_WEIGHTS["operational_responsiveness"] + BUCKET_WEIGHTS["recency_maintenance_confidence"],
        2,
    )
    score = int(round((total_earned / total_applicable) * 100.0)) if total_applicable > 0 else 100
    score = max(0, min(100, score))

    deficits = sorted(
        [item for item in breakdown if item["applies_if"]],
        key=lambda r: (r["applicable_points"] - r["earned_points"]),
        reverse=True,
    )
    top_deficits = [
        {
            "requirement_code": item["requirement_code"],
            "status": item["status"],
            "missing_points": round(item["applicable_points"] - item["earned_points"], 2),
            "risk_level_if_failed": item["risk_level_if_failed"],
        }
        for item in deficits[:5]
        if (item["applicable_points"] - item["earned_points"]) > 0
    ]
    top_next_actions = []
    for item in top_deficits[:5]:
        if item["status"] in ("MISSING", "MISSING_EVIDENCE", "EXPIRED"):
            action = f"Upload and verify {item['requirement_code']} evidence"
        elif item["status"] == "EXPIRING_SOON":
            action = f"Renew {item['requirement_code']} before expiry"
        else:
            action = f"Review {item['requirement_code']} compliance evidence"
        top_next_actions.append(
            {
                "requirement_code": item["requirement_code"],
                "action": action,
                "impact_points": item["missing_points"],
                "priority": "high" if item["risk_level_if_failed"] == "HIGH" else "medium",
            }
        )

    bucket_breakdown = {
        "legal_core": {"earned_points": legal_core_points, "applicable_points": BUCKET_WEIGHTS["legal_core"], "percent": round(legal_core_pct, 1)},
        "documentation_completeness": {"earned_points": docs_points, "applicable_points": BUCKET_WEIGHTS["documentation_completeness"], "percent": round(docs_pct, 1)},
        "operational_responsiveness": {"earned_points": op_points, "applicable_points": BUCKET_WEIGHTS["operational_responsiveness"], "percent": round(op_pct, 1)},
        "recency_maintenance_confidence": {"earned_points": recency_points, "applicable_points": BUCKET_WEIGHTS["recency_maintenance_confidence"], "percent": round(recency_pct, 1)},
    }

    return {
        "score_0_100": score,
        "jurisdiction": jurisdiction,
        "earned_points": total_earned,
        "applicable_points": total_applicable,
        "bucket_breakdown": bucket_breakdown,
        "requirement_breakdown": breakdown,
        "top_deficits": top_deficits,
        "top_next_actions": top_next_actions,
        "weights_version": "v2_jurisdictional",
    }
