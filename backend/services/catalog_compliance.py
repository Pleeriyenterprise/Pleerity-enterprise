"""
Catalog-driven compliance: requirement matrix, property/portfolio score, risk index, risk level.
Uses requirements_catalog + rule evaluator; joins existing requirements collection (state).
Guardrails: 1 HIGH overdue => at least HIGH risk; 2+ HIGH overdue => CRITICAL.
Do not change provisioning/auth; read-side only.
"""
from database import database
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from utils.catalog_rules import build_property_profile, evaluate_applies_to
from utils.risk_bands import score_to_risk_level
import logging

logger = logging.getLogger(__name__)

# Status -> base points; EXPIRING_SOON uses expiry decay (see _requirement_score).
STATUS_POINTS = {"COMPLIANT": 100, "VALID": 100, "PENDING": 30, "MISSING": 30, "OVERDUE": 0, "EXPIRED": 0}


def _days_to_expiry(due_date_any: Any) -> Optional[int]:
    """Return days until due (negative if overdue)."""
    if due_date_any is None:
        return None
    try:
        if isinstance(due_date_any, str):
            due = datetime.fromisoformat(due_date_any.replace("Z", "+00:00"))
        else:
            due = due_date_any
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        delta = (due - datetime.now(timezone.utc)).days
        return delta
    except Exception:
        return None


def _requirement_numeric_score(status: str, due_date_any: Any) -> int:
    """Return 0-100 score: OVERDUE/EXPIRED=>0, MISSING/PENDING=>30, EXPIRING_SOON=>decay, COMPLIANT=>100."""
    s = (status or "PENDING").upper().strip()
    if s in ("OVERDUE", "EXPIRED"):
        return 0
    if s in ("PENDING", "MISSING"):
        return 30
    if s in ("COMPLIANT", "VALID"):
        return 100
    if s == "EXPIRING_SOON":
        days = _days_to_expiry(due_date_any)
        if days is None:
            return 70
        if days < 0:
            return 0
        if days <= 30:
            return 70
        if days <= 60:
            return 85
        return 100
    return 30


async def _load_catalog(db) -> List[Dict[str, Any]]:
    """Load all active catalog items (code, weight, criticality, applies_to, etc.)."""
    cursor = db.requirements_catalog.find({}, {"_id": 0}).sort("code", 1)
    return await cursor.to_list(200)


def _requirement_matches_code(req: Dict[str, Any], code: str) -> bool:
    """True if requirement row matches catalog code (requirement_type or requirement_code)."""
    return (req.get("requirement_type") or "").strip().lower() == code.strip().lower() or (
        req.get("requirement_code") or ""
    ).strip().lower() == code.strip().lower()


def _max_risk(a: str, b: str) -> str:
    """Return the worse of two risk levels (higher severity)."""
    order = ("Low Risk", "Moderate Risk", "High Risk", "Critical Risk")
    try:
        ia = order.index(a) if a in order else -1
        ib = order.index(b) if b in order else -1
        return a if ia >= ib else b
    except (ValueError, TypeError):
        return a or b


async def get_property_compliance_detail(
    client_id: str, property_id: str
) -> Optional[Dict[str, Any]]:
    """
    Catalog-driven compliance detail for one property.
    Returns matrix (per applicable requirement: code, title, status, score, criticality, weight, expiry_date, days_to_expiry, evidence_doc_id),
    property_score, risk_index, risk_level. If catalog empty, returns None (caller can fall back to legacy).
    """
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    if not prop:
        return None
    catalog = await _load_catalog(db)
    if not catalog:
        return None
    profile = build_property_profile(prop)
    applicable = [c for c in catalog if evaluate_applies_to(profile, c.get("applies_to"))]
    if not applicable:
        return {
            "property_id": property_id,
            "property_name": prop.get("nickname") or prop.get("address_line_1") or property_id,
            "matrix": [],
            "property_score": 100,
            "risk_index": 0.0,
            "risk_level": "Low Risk",
            "kpis": {"overdue": 0, "expiring_30": 0, "missing": 0, "compliant": 0},
        }
    reqs = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0, "requirement_id": 1, "requirement_type": 1, "requirement_code": 1, "status": 1, "due_date": 1, "applicability": 1},
    ).to_list(200)
    docs = await db.documents.find(
        {"client_id": client_id, "property_id": property_id, "status": "VERIFIED"},
        {"_id": 0, "requirement_id": 1, "document_id": 1},
    ).to_list(500)
    req_id_to_doc = {}
    for d in docs:
        rid = d.get("requirement_id")
        if rid and rid not in req_id_to_doc:
            req_id_to_doc[rid] = d.get("document_id")

    matrix = []
    weighted_sum = 0.0
    weight_sum = 0.0
    high_overdue = 0
    high_missing = 0
    high_expiring = 0
    high_total = 0
    kpis = {"overdue": 0, "expiring_30": 0, "missing": 0, "compliant": 0}

    for cat in applicable:
        code = cat.get("code", "")
        weight = int(cat.get("weight") or 1)
        criticality = (cat.get("criticality") or "MED").upper()
        is_high = criticality == "HIGH"
        if is_high:
            high_total += 1
        row = next((r for r in reqs if _requirement_matches_code(r, code)), None)
        # Exclude from matrix and score if a requirement row exists with applicability=NOT_REQUIRED
        if row and (row.get("applicability") or "").strip().upper() == "NOT_REQUIRED":
            continue
        status = (row.get("status") or "PENDING").strip() if row else "PENDING"
        due_date = row.get("due_date") if row else None
        days = _days_to_expiry(due_date) if due_date else None
        score = _requirement_numeric_score(status, due_date)
        evidence_doc_id = req_id_to_doc.get(row["requirement_id"]) if row else None
        if row:
            if status in ("OVERDUE", "EXPIRED"):
                kpis["overdue"] += 1
                if is_high:
                    high_overdue += 1
            elif status == "EXPIRING_SOON" and days is not None and 0 <= days <= 30:
                kpis["expiring_30"] += 1
                if is_high:
                    high_expiring += 1
            elif status in ("PENDING", "MISSING"):
                kpis["missing"] += 1
                if is_high:
                    high_missing += 1
            else:
                kpis["compliant"] += 1
        else:
            kpis["missing"] += 1
            if is_high:
                high_missing += 1
        weighted_sum += weight * score
        weight_sum += weight
        matrix.append({
            "requirement_code": code,
            "title": cat.get("title") or code,
            "status": status,
            "numeric_score": score,
            "criticality": criticality,
            "weight": weight,
            "expiry_date": due_date.isoformat() if hasattr(due_date, "isoformat") else due_date,
            "days_to_expiry": days,
            "evidence_doc_id": evidence_doc_id,
            "requirement_id": row.get("requirement_id") if row else None,
        })

    if weight_sum <= 0:
        property_score = 100
    else:
        property_score = round(weighted_sum / weight_sum)
        property_score = max(0, min(100, property_score))
    risk_from_score = score_to_risk_level(property_score)
    if high_total == 0:
        risk_index_val = 0.0
        risk_level = risk_from_score
    else:
        risk_index_val = (3 * high_overdue + 2 * high_missing + 1 * high_expiring) / high_total
        if risk_index_val >= 1.2:
            risk_level = "Critical Risk"
        elif risk_index_val >= 0.6:
            risk_level = "High Risk"
        elif risk_index_val >= 0.25:
            risk_level = "Moderate Risk"
        else:
            risk_level = "Low Risk"
        risk_level = _max_risk(risk_from_score, risk_level)
    if high_overdue >= 2:
        risk_level = "Critical Risk"
    elif high_overdue >= 1:
        if risk_level != "Critical Risk" and risk_level != "High Risk":
            risk_level = "High Risk"
    return {
        "property_id": property_id,
        "property_name": prop.get("nickname") or prop.get("address_line_1") or property_id,
        "matrix": matrix,
        "property_score": property_score,
        "risk_index": round(risk_index_val, 2),
        "risk_level": risk_level,
        "kpis": kpis,
    }


async def get_portfolio_compliance_from_catalog(
    client_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Catalog-driven portfolio summary. If catalog empty, returns None (caller uses legacy).
    Returns portfolio_score, portfolio_risk_level, updated_at, kpis, properties (with name, score, risk_level, overdue_count, expiring_30_count, missing_count).
    """
    db = database.get_db()
    catalog = await _load_catalog(db)
    if not catalog:
        return None
    properties = await db.properties.find(
        {"client_id": client_id},
        {"_id": 0, "property_id": 1, "address_line_1": 1, "nickname": 1, "postcode": 1},
    ).to_list(100)
    if not properties:
        return {
            "portfolio_score": 100,
            "portfolio_risk_level": "Low Risk",
            "risk_level": "Low Risk",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": {"overdue": 0, "expiring_30": 0, "missing": 0, "compliant": 0},
            "properties": [],
        }
    total_weighted = 0.0
    total_weights = 0.0
    portfolio_risk_level = "Low Risk"
    kpis_agg = {"overdue": 0, "expiring_30": 0, "missing": 0, "compliant": 0}
    property_list = []
    for prop in properties:
        detail = await get_property_compliance_detail(client_id, prop["property_id"])
        if not detail:
            continue
        total_weighted += detail["property_score"] * sum(m.get("weight", 1) for m in detail["matrix"])
        total_weights += sum(m.get("weight", 1) for m in detail["matrix"])
        portfolio_risk_level = _max_risk(portfolio_risk_level, detail["risk_level"])
        for k in kpis_agg:
            kpis_agg[k] += detail["kpis"].get(k, 0)
        property_list.append({
            "property_id": prop["property_id"],
            "name": detail["property_name"],
            "score": detail["property_score"],
            "risk_level": detail["risk_level"],
            "overdue_count": detail["kpis"].get("overdue", 0),
            "expiring_30_count": detail["kpis"].get("expiring_30", 0),
            "missing_count": detail["kpis"].get("missing", 0),
        })
    if total_weights <= 0:
        portfolio_score = 100
    else:
        portfolio_score = round(total_weighted / total_weights)
        portfolio_score = max(0, min(100, portfolio_score))
    portfolio_risk_level = score_to_risk_level(portfolio_score)
    for p in property_list:
        portfolio_risk_level = _max_risk(portfolio_risk_level, p["risk_level"])
    return {
        "portfolio_score": portfolio_score,
        "portfolio_risk_level": portfolio_risk_level,
        "risk_level": portfolio_risk_level,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "kpis": kpis_agg,
        "properties": property_list,
    }
