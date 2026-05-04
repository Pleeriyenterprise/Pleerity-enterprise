from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from services.compliance_expiry_policy import get_default_expiring_soon_days
from services.document_status_service import (
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
    STATUS_TO_FRACTION,
    STATUS_VALID,
    STATUS_NEEDS_REVIEW,
    compute_requirement_status,
    pick_evidence_document,
)
from services.requirement_evidence_authority import map_authority_to_scoring_status
from services.requirement_truth import (
    CONFIDENCE_ESTIMATED,
    evidence_state_for_documents_list,
    infer_confidence_state,
    infer_date_source_for_scoring,
)
from presentation.label_service import requirement_label
from services.compliance_rules_registry import (
    expiring_soon_days_for_requirement,
    expects_expiry_for_requirement,
)


BUCKET_WEIGHTS = {
    "legal_core": 60.0,
    "documentation_completeness": 20.0,
    "operational_responsiveness": 10.0,
    "recency_maintenance_confidence": 10.0,
}

# Slight discount when legal-core status is driven only by system-estimated dates (no verified evidence).
ESTIMATED_DATE_LEGAL_CORE_MULTIPLIER = 0.93


# Scoring weights / risk labels: intentionally mirrored EW ↔ Scotland until product defines divergence.
# Per-code "expiring soon" windows use compliance_rules_registry + get_default_expiring_soon_days() as profile default.
_JURISDICTION_DEFAULT_DAYS = get_default_expiring_soon_days()
_SHARED_LEGAL_CORE_WEIGHTS = {
    "GAS_SAFETY": {"weight": 15.0, "risk_level_if_failed": "HIGH"},
    "EICR": {"weight": 15.0, "risk_level_if_failed": "HIGH"},
    "EPC": {"weight": 10.0, "risk_level_if_failed": "MEDIUM"},
    "FIRE_DETECTION": {"weight": 10.0, "risk_level_if_failed": "HIGH"},
    "LEGIONELLA": {"weight": 10.0, "risk_level_if_failed": "MEDIUM"},
}
# Condition-scoped extensions (see _applies_if): HMO fire evidence, Wales occupation contract, Scotland landlord registration.
_EXTENDED_LEGAL_CORE_WEIGHTS = {
    "HMO_FIRE_RISK": {"weight": 8.0, "risk_level_if_failed": "HIGH"},
    "OCCUPATION_CONTRACT": {"weight": 3.0, "risk_level_if_failed": "LOW"},
    "RIGHT_TO_RENT": {"weight": 5.0, "risk_level_if_failed": "MEDIUM"},
    "RENT_SMART_WALES": {"weight": 5.0, "risk_level_if_failed": "MEDIUM"},
    "LANDLORD_REGISTRATION_NI": {"weight": 8.0, "risk_level_if_failed": "MEDIUM"},
    "PORTABLE_APPLIANCE": {"weight": 4.0, "risk_level_if_failed": "MEDIUM"},
}
_SCOTLAND_ONLY_WEIGHTS = {
    "LANDLORD_REGISTRATION": {"weight": 8.0, "risk_level_if_failed": "MEDIUM"},
}
JURISDICTION_PROFILES: Dict[str, Dict[str, Any]] = {
    "ENGLAND_WALES": {
        "requirements": {**dict(_SHARED_LEGAL_CORE_WEIGHTS), **dict(_EXTENDED_LEGAL_CORE_WEIGHTS)},
        "expiring_soon_days": _JURISDICTION_DEFAULT_DAYS,
    },
    "SCOTLAND": {
        "requirements": {
            **dict(_SHARED_LEGAL_CORE_WEIGHTS),
            **dict(_EXTENDED_LEGAL_CORE_WEIGHTS),
            **dict(_SCOTLAND_ONLY_WEIGHTS),
        },
        "expiring_soon_days": _JURISDICTION_DEFAULT_DAYS,
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
    # Phase-1 storage slugs: align with requirement_code_registry (same uppercase scoring key as canonical).
    "FIRE_ALARM": "FIRE_DETECTION",
    "RIGHT_TO_RENT_CHECKS": "RIGHT_TO_RENT",
    "LEGIONELLA_RISK": "LEGIONELLA",
    "HMO_FIRE_RISK_EVIDENCE": "HMO_FIRE_RISK",
    "HMO_FIRE_RISK": "HMO_FIRE_RISK",
    "SCOTLAND_LANDLORD_REGISTRATION": "LANDLORD_REGISTRATION",
    "LANDLORD_REGISTRATION_SCOTLAND": "LANDLORD_REGISTRATION",
    "WALES_OCCUPATION_CONTRACT": "OCCUPATION_CONTRACT",
    "RENT_SMART_WALES": "RENT_SMART_WALES",
    "LANDLORD_REGISTRATION_NI": "LANDLORD_REGISTRATION_NI",
    "PORTABLE_APPLIANCE_TEST": "PORTABLE_APPLIANCE",
    # Domestic alarm family (registry canonical smoke_heat_alarms); scoring bucket unchanged (FIRE_DETECTION).
    "SMOKE_HEAT_ALARMS": "FIRE_DETECTION",
    "SMOKE_ALARMS": "FIRE_DETECTION",
    "CO_ALARMS": "FIRE_DETECTION",
}

REQ_TO_DOC_TYPE = {
    "GAS_SAFETY": "gas_safety",
    "EICR": "eicr",
    "EPC": "epc",
    "RIGHT_TO_RENT": "tenancy_agreement",
    "RENT_SMART_WALES": "licence",
    "LANDLORD_REGISTRATION_NI": "licence",
    "PORTABLE_APPLIANCE": "electrical_installation",
    "FIRE_DETECTION": "fire_safety",
    "LEGIONELLA": "legionella",
    "HMO_FIRE_RISK": "fire_safety",
    "LANDLORD_REGISTRATION": "licence",
    "OCCUPATION_CONTRACT": "tenancy_agreement",
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


def _status_fraction_from_doc(
    code: str,
    docs: List[Dict[str, Any]],
    as_of: date,
    expiring_soon_days: int,
    *,
    expects_expiry: bool,
) -> Tuple[float, str, Optional[str], Optional[str], List[str]]:
    doc = pick_evidence_document(docs, REQ_TO_DOC_TYPE.get(code, ""))
    status_result = compute_requirement_status(as_of, doc, expects_expiry=expects_expiry, expiring_soon_days=expiring_soon_days)
    fraction = STATUS_TO_FRACTION.get(status_result["status"], 0.0)
    expiry_date = status_result.get("expiry_date")
    verified_at = None
    if doc and doc.get("verified_at"):
        verified_at = str(doc.get("verified_at"))
    elif doc and (doc.get("status") or "").upper() == "VERIFIED":
        verified_at = str(doc.get("updated_at") or doc.get("uploaded_at") or "")
    return fraction, status_result["status"], expiry_date, verified_at, status_result.get("reason_codes") or []


def _status_fraction_from_requirement(
    code: str,
    req: Optional[Dict[str, Any]],
    docs: List[Dict[str, Any]],
    as_of: date,
    expiring_soon_days: int,
    *,
    expects_expiry: bool,
) -> Tuple[float, str, Optional[str], Optional[str], List[str]]:
    if not req:
        return _status_fraction_from_doc(code, docs, as_of, expiring_soon_days, expects_expiry=expects_expiry)
    auth_status = map_authority_to_scoring_status(req)
    if auth_status:
        eff = req.get("evidence_authority") or {}
        exp_raw = eff.get("effective_expiry_date")
        exp_d: Optional[date] = None
        if exp_raw:
            try:
                exp_d = datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00")).date()
            except ValueError:
                exp_d = None
        if auth_status == "VALID" and exp_d is not None:
            days = (exp_d - as_of).days
            if days < 0:
                return (
                    STATUS_TO_FRACTION[STATUS_EXPIRED],
                    "EXPIRED",
                    exp_d.isoformat(),
                    None,
                    ["DOCUMENT_EXPIRED"],
                )
            if days <= expiring_soon_days:
                return (
                    STATUS_TO_FRACTION[STATUS_EXPIRING_SOON],
                    "EXPIRING_SOON",
                    exp_d.isoformat(),
                    None,
                    ["DOCUMENT_EXPIRING_SOON"],
                )
            return (
                STATUS_TO_FRACTION[STATUS_VALID],
                "VALID",
                exp_d.isoformat(),
                None,
                [],
            )
        if auth_status == "VALID":
            return (STATUS_TO_FRACTION[STATUS_VALID], "VALID", None, None, [])
        if auth_status == "EXPIRED":
            return (
                STATUS_TO_FRACTION[STATUS_EXPIRED],
                "EXPIRED",
                exp_d.isoformat() if exp_d else None,
                None,
                ["DOCUMENT_EXPIRED"],
            )
        if auth_status == "NEEDS_REVIEW":
            return (
                STATUS_TO_FRACTION[STATUS_NEEDS_REVIEW],
                "NEEDS_REVIEW",
                exp_d.isoformat() if exp_d else None,
                None,
                ["AUTHORITY_NEEDS_REVIEW"],
            )
        if auth_status == "MISSING":
            return (0.0, "MISSING", exp_d.isoformat() if exp_d else None, None, ["NO_DOCUMENT_FOUND"])
        if auth_status == "NOT_APPLICABLE":
            return (1.0, "NOT_APPLICABLE", exp_d.isoformat() if exp_d else None, None, [])
    app = (req.get("applicability") or "").strip().upper()
    if app == "NOT_REQUIRED":
        due = _parse_due(req.get("due_date") or req.get("expiry_date"))
        verified_at = req.get("verified_at")
        return 1.0, "NOT_APPLICABLE", due.isoformat() if due else None, str(verified_at) if verified_at else None, []
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
    return _status_fraction_from_doc(code, docs, as_of, expiring_soon_days, expects_expiry=expects_expiry)


def _is_commercial_property(property_doc: Dict[str, Any]) -> bool:
    pt = (property_doc.get("property_type") or "").strip().upper()
    return pt == "COMMERCIAL"


def _str_truthy(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip()
    if not s or s.upper() in ("NO", "FALSE", "0"):
        return False
    return s.upper() in ("YES", "TRUE", "1") or bool(s)


def _applies_if(code: str, property_doc: Dict[str, Any], client_doc: Optional[Dict[str, Any]] = None) -> bool:
    if code == "GAS_SAFETY":
        return _str_truthy(property_doc.get("has_gas_supply")) or str(
            property_doc.get("cert_gas_safety") or ""
        ).strip().upper() == "YES"
    if code == "LANDLORD_REGISTRATION":
        from services.compliance_rules_registry import resolve_portfolio_jurisdiction

        if _is_commercial_property(property_doc):
            return False
        r = resolve_portfolio_jurisdiction(property_doc, client_doc)
        return r.effective_label == "Scotland"
    if code == "OCCUPATION_CONTRACT":
        from services.compliance_rules_registry import resolve_portfolio_jurisdiction

        if _is_commercial_property(property_doc):
            return False
        if not _str_truthy(property_doc.get("tenancy_active")):
            return False
        r = resolve_portfolio_jurisdiction(property_doc, client_doc)
        return r.effective_label == "Wales"
    if code == "HMO_FIRE_RISK":
        return bool(property_doc.get("is_hmo"))
    if code == "RIGHT_TO_RENT":
        from services.compliance_rules_registry import resolve_portfolio_jurisdiction

        if _is_commercial_property(property_doc):
            return False
        if not _str_truthy(property_doc.get("tenancy_active")):
            return False
        r = resolve_portfolio_jurisdiction(property_doc, client_doc)
        return r.effective_label == "England"
    if code == "RENT_SMART_WALES":
        from services.compliance_rules_registry import resolve_portfolio_jurisdiction

        if _is_commercial_property(property_doc):
            return False
        if not _str_truthy(property_doc.get("tenancy_active")):
            return False
        r = resolve_portfolio_jurisdiction(property_doc, client_doc)
        return r.effective_label == "Wales"
    if code == "LANDLORD_REGISTRATION_NI":
        from services.compliance_rules_registry import resolve_portfolio_jurisdiction

        if _is_commercial_property(property_doc):
            return False
        r = resolve_portfolio_jurisdiction(property_doc, client_doc)
        return r.effective_label == "Northern Ireland"
    if code == "PORTABLE_APPLIANCE":
        if _is_commercial_property(property_doc):
            return False
        return _str_truthy(property_doc.get("tenancy_active")) and _str_truthy(property_doc.get("furnished"))
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
    expiring_soon_days = int(profile.get("expiring_soon_days", get_default_expiring_soon_days()))

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
        applies = _applies_if(code, property_doc, client_doc)
        if not applies:
            breakdown.append({
                "requirement_code": code,
                "display_label": requirement_label(code, audience="client"),
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
                "date_source": None,
                "evidence_state": None,
                "confidence_state": None,
            })
            continue

        applicable_points += float(cfg["weight"])
        code_expiring = expiring_soon_days_for_requirement(jurisdiction, code, expiring_soon_days)
        code_expects_expiry = expects_expiry_for_requirement(jurisdiction, code)
        fraction, status, expiry_date, verified_at, reasons = _status_fraction_from_requirement(
            code,
            req_by_code.get(code),
            docs_by_code.get(code, []),
            today,
            code_expiring,
            expects_expiry=code_expects_expiry,
        )
        docs_for_code = docs_by_code.get(code, [])
        evidence_state = evidence_state_for_documents_list(docs_for_code)
        req_row = req_by_code.get(code)
        date_source = infer_date_source_for_scoring(req_row, evidence_state)
        confidence_state = infer_confidence_state(date_source, evidence_state)
        reasons = list(reasons)
        req_points = round(float(cfg["weight"]) * fraction, 2)
        if confidence_state == CONFIDENCE_ESTIMATED:
            req_points = round(req_points * ESTIMATED_DATE_LEGAL_CORE_MULTIPLIER, 2)
            reasons.append("SCORE_WEIGHT_SYSTEM_ESTIMATED_DATE")
        earned_points += req_points
        breakdown.append({
            "requirement_code": code,
            "display_label": requirement_label(code, audience="client"),
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
            "date_source": date_source,
            "evidence_state": evidence_state,
            "confidence_state": confidence_state,
        })

    legal_core_applicable = sum(item["applicable_points"] for item in breakdown)
    legal_core_earned = sum(item["earned_points"] for item in breakdown)
    legal_core_pct = (legal_core_earned / legal_core_applicable * 100.0) if legal_core_applicable > 0 else 100.0

    # Documentation completeness: proportion of applicable obligations with admin-verified evidence only.
    applicable_count = sum(1 for item in breakdown if item["applies_if"])
    verified_count = sum(
        1 for item in breakdown if item["applies_if"] and item.get("evidence_state") == "VERIFIED"
    )
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
        lbl = requirement_label(item["requirement_code"], audience="client")
        if item["status"] in ("MISSING", "MISSING_EVIDENCE", "EXPIRED"):
            action = f"Upload and verify evidence for {lbl}"
        elif item["status"] == "EXPIRING_SOON":
            action = f"Renew {lbl} before expiry"
        else:
            action = f"Review compliance evidence for {lbl}"
        top_next_actions.append(
            {
                "requirement_code": item["requirement_code"],
                "display_label": lbl,
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
        "scoring_policy": {
            "estimated_date_legal_core_multiplier": ESTIMATED_DATE_LEGAL_CORE_MULTIPLIER,
            "documentation_bucket_counts_verified_evidence_only": True,
        },
    }
