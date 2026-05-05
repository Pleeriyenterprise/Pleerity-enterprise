"""
Catalog-driven compliance: requirement matrix, property/portfolio score, risk index, risk level.
Uses requirements_catalog + rule evaluator; joins existing requirements collection (state).
Guardrails: 1 HIGH overdue => at least HIGH risk; 2+ HIGH overdue => CRITICAL.
Do not change provisioning/auth; read-side only.
"""
from database import database
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from utils.risk_bands import score_to_risk_level
from services.requirement_client_runtime_surface import (
    filter_requirement_rows_for_client_runtime_surfaces,
    project_requirement_row_client_runtime,
)
from services.requirement_read_model_guard import (
    filter_rows_to_canonical_requirement_ids,
    get_canonical_requirement_ids_for_property,
)
import logging

logger = logging.getLogger(__name__)

_HIGH_CRITICALITY_CODES = {
    "gas_safety",
    "eicr",
    "epc",
    "hmo_license",
    "right_to_rent",
    "landlord_registration_ni",
    "deposit_pi",
}

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
    Returns matrix (per applicable requirement: code, title, status, score, criticality, weight, expiry_date, days_to_expiry, evidence_doc_id, property_id),
    property_score, risk_index, risk_level. If catalog empty, returns None (caller can fall back to legacy).
    """
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    if not prop:
        return None
    client_row = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}
    from services.compliance_rules_registry import (
        jurisdiction_attribution_for_property,
        log_jurisdiction_resolution_debug,
        property_jurisdiction_requirement_flags,
        resolve_portfolio_jurisdiction,
    )

    _rj = resolve_portfolio_jurisdiction(prop, client_row)
    log_jurisdiction_resolution_debug(
        context="catalog_compliance.get_property_compliance_detail",
        property_id=property_id,
        raw_property_jurisdiction=prop.get("jurisdiction"),
        raw_client_default_jurisdiction=(client_row or {}).get("default_jurisdiction"),
        resolution=_rj,
    )
    _att = jurisdiction_attribution_for_property(prop, client_row, _resolution=_rj)
    _jf = property_jurisdiction_requirement_flags(prop)
    _jurisdiction_extra = {
        "compliance_basis": _att["compliance_basis"],
        "effective_jurisdiction_label": _att["effective_jurisdiction_label"],
        "jurisdiction_source": _att["jurisdiction_source"],
        "jurisdiction_required": _jf["jurisdiction_required"],
        "compliance_confidence": _jf["compliance_confidence"],
    }
    # Client-facing compliance matrix must represent active canonical runtime obligations only.
    # Broader catalog-applicability rows are not emitted here to avoid split-brain across surfaces.
    reqs = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).to_list(200)
    reqs = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=reqs or [],
        client_doc=client_row,
        properties=[prop],
    )
    from services.requirement_truth import enrich_requirements_for_client

    enriched, _presentation = await enrich_requirements_for_client(db, client_id, reqs)
    enriched = [r for r in enriched if r.get("client_surface_visible", True)]
    canonical_ids = await get_canonical_requirement_ids_for_property(client_id, property_id, db=db)
    enriched, dropped = filter_rows_to_canonical_requirement_ids(enriched, canonical_ids)
    for d in dropped:
        logger.warning(
            "catalog_compliance: dropped non-canonical requirement row before matrix projection",
            extra={
                "client_id": client_id,
                "property_id": property_id,
                "requirement_id": d.get("requirement_id"),
                "requirement_code": d.get("requirement_code"),
                "requirement_type": d.get("requirement_type"),
                "source": d.get("source"),
                "reason": d.get("reason"),
            },
        )
    catalog_items = await _load_catalog(db)
    catalog_by_code = {
        str(x.get("code") or "").strip().lower(): x
        for x in catalog_items
        if str(x.get("code") or "").strip()
    }
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

    for row in enriched:
        code = str(row.get("canonical_code") or row.get("requirement_code") or row.get("requirement_type") or "").strip().lower()
        if not code:
            continue
        cat_meta = catalog_by_code.get(code, {})
        weight = int(row.get("weight") or cat_meta.get("weight") or 1)
        criticality = str(row.get("risk") or row.get("criticality") or cat_meta.get("criticality") or "").upper()
        if not criticality:
            criticality = "HIGH" if code in _HIGH_CRITICALITY_CODES else "MED"
        is_high = criticality == "HIGH"
        if is_high:
            high_total += 1
        if (row.get("applicability") or "").strip().upper() == "NOT_REQUIRED":
            continue
        proj = project_requirement_row_client_runtime(dict(row))
        status = str(proj.get("status") or "PENDING").strip().upper()
        due_date = proj.get("due_date")
        days = _days_to_expiry(due_date) if due_date else None
        score = _requirement_numeric_score(status, due_date)
        evidence_doc_id = req_id_to_doc.get(row.get("requirement_id"))
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
        weighted_sum += weight * score
        weight_sum += weight
        matrix.append({
            "requirement_code": code,
            "display_name": row.get("display_name") or row.get("display_label") or row.get("description") or code,
            "title": row.get("display_name") or row.get("display_label") or row.get("description") or code,
            "status": status,
            "numeric_score": score,
            "criticality": criticality,
            "weight": weight,
            "property_jurisdiction": row.get("property_jurisdiction") or _att.get("effective_jurisdiction_label"),
            "category": row.get("category") or cat_meta.get("category"),
            "risk": row.get("risk") or criticality,
            "expiry_date": due_date.isoformat() if hasattr(due_date, "isoformat") else due_date,
            "days_to_expiry": days,
            "evidence_doc_id": evidence_doc_id,
            "cta_action_mode": row.get("cta_action_mode"),
            "cta_label": row.get("cta_label"),
            "cta_url": row.get("cta_url"),
            "action_links": row.get("action_links") or [],
            "why_it_matters_short": row.get("why_it_matters_short"),
            "why_it_matters_long": row.get("why_it_matters_long"),
            "source": row.get("source"),
            "trigger_explanation": row.get("trigger_explanation"),
            "requirement_id": row.get("requirement_id"),
            "canonical_code": row.get("canonical_code"),
            "property_id": property_id,
            # Canonical requirement CTA contract (shared with /client/properties/{id}/requirements).
            "take_action": row.get("take_action"),
            "allowed_evidence_modes": (
                (row.get("registry_metadata") or {}).get("evidence_resolution", {}).get("allowed_evidence_modes")
                if isinstance(row.get("registry_metadata"), dict)
                else None
            ),
            "primary_action_kind": (
                ((row.get("take_action") or {}).get("primary") or {}).get("kind")
                if isinstance(row.get("take_action"), dict)
                else None
            ),
            "primary_action_intent": (
                ((row.get("take_action") or {}).get("primary") or {}).get("intent")
                if isinstance(row.get("take_action"), dict)
                else None
            ),
            "evidence_resolution": (
                (row.get("registry_metadata") or {}).get("evidence_resolution")
                if isinstance(row.get("registry_metadata"), dict)
                else None
            ),
        })

    if weight_sum <= 0:
        property_score = None
    else:
        property_score = round(weighted_sum / weight_sum)
        property_score = max(0, min(100, property_score))
    risk_from_score = score_to_risk_level(property_score) if property_score is not None else None
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
        risk_level = _max_risk(risk_from_score, risk_level) if risk_from_score is not None else risk_level
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
        **_jurisdiction_extra,
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
    ).to_list(500_000)
    if not properties:
        return {
            "portfolio_score": None,
            "portfolio_risk_level": None,
            "risk_level": None,
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
        wsum = sum(m.get("weight", 1) for m in detail["matrix"])
        ps = detail.get("property_score")
        if ps is not None and wsum:
            total_weighted += float(ps) * wsum
            total_weights += wsum
        d_risk = detail.get("risk_level")
        if d_risk:
            portfolio_risk_level = d_risk if portfolio_risk_level is None else _max_risk(portfolio_risk_level, d_risk)
        for k in kpis_agg:
            kpis_agg[k] += detail["kpis"].get(k, 0)
        property_list.append({
            "property_id": prop["property_id"],
            "name": detail["property_name"],
            "nickname": prop.get("nickname"),
            "address_line_1": prop.get("address_line_1"),
            "postcode": prop.get("postcode"),
            "score": detail["property_score"],
            "risk_level": detail["risk_level"],
            "overdue_count": detail["kpis"].get("overdue", 0),
            "expiring_30_count": detail["kpis"].get("expiring_30", 0),
            "missing_count": detail["kpis"].get("missing", 0),
        })
    if total_weights <= 0:
        portfolio_score = None
        portfolio_risk_level = None
    else:
        portfolio_score = round(total_weighted / total_weights)
        portfolio_score = max(0, min(100, portfolio_score))
        portfolio_risk_level = score_to_risk_level(portfolio_score)
    for p in property_list:
        prl = p.get("risk_level")
        if prl:
            portfolio_risk_level = prl if portfolio_risk_level is None else _max_risk(portfolio_risk_level, prl)
    return {
        "portfolio_score": portfolio_score,
        "portfolio_risk_level": portfolio_risk_level,
        "risk_level": portfolio_risk_level,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "kpis": kpis_agg,
        "properties": property_list,
    }
