"""
Risk Signal Detection Layer: rule-based risk intelligence engine.
Watches property age, repeat failures, missed SLAs, compliance churn, maintenance frequency.
Produces stored, explainable risk signals in three categories: asset, operational, compliance.
No AI/ML; transparent rules only. Gated by PREDICTIVE_MAINTENANCE for visibility.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid
import logging

from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

# Signal categories (task §1)
SIGNAL_CATEGORY_ASSET = "asset"
SIGNAL_CATEGORY_OPERATIONAL = "operational"
SIGNAL_CATEGORY_COMPLIANCE = "compliance"

# Risk types (task §1)
RISK_TYPE_BOILER_FAILURE = "Boiler Failure Risk"
RISK_TYPE_DAMP_MOISTURE = "Damp / Moisture Risk"
RISK_TYPE_ELECTRICAL = "Electrical Risk"
RISK_TYPE_RECURRING_REPAIRS = "Recurring Repairs Risk"
RISK_TYPE_SLA_BREACH = "SLA Breach Risk"
RISK_TYPE_COMPLIANCE_CHURN = "Compliance Churn Risk"
RISK_TYPE_MAINTENANCE_FREQUENCY = "Maintenance Frequency Risk"
RISK_TYPE_CERTIFICATE_EXPIRY_SOON = "Certificate Expiry Soon"

# Risk levels and trend
RISK_LEVEL_LOW = "low"
RISK_LEVEL_MEDIUM = "medium"
RISK_LEVEL_HIGH = "high"
RISK_LEVEL_CRITICAL = "critical"
TREND_STABLE = "stable"
TREND_RISING = "rising"
TREND_IMPROVING = "improving"
STATUS_ACTIVE = "active"
STATUS_ACKNOWLEDGED = "acknowledged"
STATUS_RESOLVED = "resolved"
SOURCE_HEURISTIC = "heuristic"

# Rolling windows (days)
ROLLING_12_MONTHS_DAYS = 365
ROLLING_6_MONTHS_DAYS = 183
ROLLING_60_DAYS = 60
ROLLING_30_DAYS = 30

# Thresholds
BOILER_AGE_YEARS_THRESHOLD = 10
DAMP_PROPERTY_AGE_YEARS_THRESHOLD = 74  # pre-1950 approx
MAINTENANCE_FREQUENCY_THRESHOLD = 4  # issues in 6 months
SLA_BREACH_COUNT_THRESHOLD = 2
RECURRING_ISSUES_THRESHOLD = 3

# Recommended actions (task §8)
RECOMMENDED_ACTIONS = {
    RISK_TYPE_BOILER_FAILURE: "Schedule boiler inspection or replacement review",
    RISK_TYPE_DAMP_MOISTURE: "Investigate recurring area / specialist damp inspection",
    RISK_TYPE_ELECTRICAL: "Review EICR and schedule electrical inspection",
    RISK_TYPE_RECURRING_REPAIRS: "Investigate root cause instead of repeat patch repairs",
    RISK_TYPE_SLA_BREACH: "Review contractor performance and prioritise unresolved jobs",
    RISK_TYPE_COMPLIANCE_CHURN: "Review compliance workflow, upload evidence, or adjust reminders",
    RISK_TYPE_MAINTENANCE_FREQUENCY: "Review property health and inspect assets",
    RISK_TYPE_CERTIFICATE_EXPIRY_SOON: "Renew or schedule renewal before expiry; upload evidence when complete",
}

# Suggested actions (task §2): actionable codes for UI buttons
SUGGESTED_ACTION_CREATE_ISSUE = "create_issue"
SUGGESTED_ACTION_CREATE_WORK_ORDER = "create_work_order"
SUGGESTED_ACTION_SCHEDULE_INSPECTION = "schedule_inspection"
SUGGESTED_ACTION_SEND_CONTRACTOR_REMINDER = "send_contractor_reminder"
SUGGESTED_ACTION_REASSIGN_CONTRACTOR = "reassign_contractor"


def _suggested_actions_for_signal(signal_category: str, risk_type: str) -> List[str]:
    """Return list of suggested action codes for this signal. Used when persisting and by API."""
    actions: List[str] = []
    if signal_category == SIGNAL_CATEGORY_COMPLIANCE:
        actions.append(SUGGESTED_ACTION_SCHEDULE_INSPECTION)
        if risk_type == RISK_TYPE_CERTIFICATE_EXPIRY_SOON:
            actions.append(SUGGESTED_ACTION_CREATE_WORK_ORDER)  # e.g. book gas safety
        else:
            actions.append(SUGGESTED_ACTION_CREATE_ISSUE)
    elif signal_category == SIGNAL_CATEGORY_OPERATIONAL:
        actions.append(SUGGESTED_ACTION_CREATE_WORK_ORDER)
        actions.append(SUGGESTED_ACTION_CREATE_ISSUE)
    else:
        # asset
        actions.append(SUGGESTED_ACTION_CREATE_WORK_ORDER)
        actions.append(SUGGESTED_ACTION_CREATE_ISSUE)
        actions.append(SUGGESTED_ACTION_SCHEDULE_INSPECTION)
    return actions


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


async def _fetch_property(db, property_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    return await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "property_id": 1, "client_id": 1, "building_age_years": 1},
    )


async def _fetch_assets(db, property_id: str) -> List[Dict[str, Any]]:
    cursor = db.property_assets.find({"property_id": property_id}, {"_id": 0})
    return await cursor.to_list(100)


async def _fetch_work_orders(
    db, property_id: str, client_id: str, since_days: int
) -> List[Dict[str, Any]]:
    since = _now() - timedelta(days=since_days)
    since_iso = since.isoformat()
    cursor = db.work_orders.find(
        {"property_id": property_id, "client_id": client_id, "created_at": {"$gte": since_iso}},
        {"_id": 0, "work_order_id": 1, "category": 1, "asset_id": 1, "created_at": 1, "completed_at": 1, "sla_breached_at": 1, "contractor_id": 1},
    )
    return await cursor.to_list(200)


async def _fetch_work_orders_with_breach_in_window(
    db, property_id: str, client_id: str, within_days: int
) -> List[Dict[str, Any]]:
    """Work orders that have sla_breached_at set and that date falls within the last within_days."""
    since = _now() - timedelta(days=within_days)
    since_iso = since.isoformat()
    cursor = db.work_orders.find(
        {"property_id": property_id, "client_id": client_id, "sla_breached_at": {"$gte": since_iso}},
        {"_id": 0, "work_order_id": 1, "sla_breached_at": 1, "contractor_id": 1},
    )
    return await cursor.to_list(200)


async def _fetch_issues(db, property_id: str, client_id: str, since_days: int) -> List[Dict[str, Any]]:
    since = _now() - timedelta(days=since_days)
    since_iso = since.isoformat()
    cursor = db.maintenance_issues.find(
        {"property_id": property_id, "client_id": client_id, "created_at": {"$gte": since_iso}},
        {"_id": 0, "issue_id": 1, "category": 1, "asset_id": 1, "created_at": 1},
    )
    return await cursor.to_list(200)


async def _fetch_requirements_overdue(db, property_id: str, client_id: str) -> List[Dict[str, Any]]:
    cursor = db.requirements.find(
        {"property_id": property_id, "client_id": client_id, "status": {"$in": ["OVERDUE", "EXPIRED", "PENDING", "MISSING"]}},
        {"_id": 0, "requirement_id": 1, "requirement_code": 1, "requirement_type": 1, "status": 1},
    )
    return await cursor.to_list(100)


async def _fetch_requirements_expiring_soon(db, property_id: str, client_id: str) -> List[Dict[str, Any]]:
    """Requirements with status EXPIRING_SOON (certificate expiring within configured window)."""
    cursor = db.requirements.find(
        {"property_id": property_id, "client_id": client_id, "status": "EXPIRING_SOON"},
        {"_id": 0, "requirement_id": 1, "requirement_code": 1, "requirement_type": 1, "title": 1, "status": 1},
    )
    return await cursor.to_list(100)


def _normalize_category(cat: Optional[str]) -> str:
    if not cat:
        return "general"
    return (cat or "").strip().lower()


def _count_by_category(items: List[Dict], category_key: str = "category") -> Dict[str, int]:
    counts: Dict[str, Any] = {}
    for item in items:
        cat = _normalize_category(item.get(category_key))
        counts[cat] = counts.get(cat, 0) + 1
    return counts


# ---------- Rule: Boiler Failure Risk ----------
async def _rule_boiler_failure(
    db, property_id: str, client_id: str,
    property_doc: Optional[Dict], assets: List[Dict],
    work_orders: List[Dict], issues: List[Dict],
) -> List[Dict[str, Any]]:
    signals = []
    heating_cats = {"heating", "boiler", "plumbing"}
    heating_wo = [wo for wo in work_orders if _normalize_category(wo.get("category")) in heating_cats]
    heating_issues = [i for i in issues if _normalize_category(i.get("category")) in heating_cats]
    linked = []
    for a in assets:
        atype = _normalize_category(a.get("asset_type"))
        if atype not in ("boiler", "heating"):
            continue
        aid = a.get("asset_id")
        age_years = None
        if a.get("age_estimate") is not None:
            age_years = int(a["age_estimate"])
        elif a.get("installed_year"):
            try:
                age_years = _now().year - int(a["installed_year"])
            except Exception:
                pass
        elif a.get("install_date"):
            dt = _parse_dt(a["install_date"])
            if dt:
                age_years = int((_now() - dt).days / 365.25)
        if age_years is None or age_years < BOILER_AGE_YEARS_THRESHOLD:
            continue
        count_wo = len([wo for wo in heating_wo if wo.get("asset_id") == aid or not wo.get("asset_id")])
        count_issues = len([i for i in heating_issues if i.get("asset_id") == aid or not i.get("asset_id")])
        total = count_wo + count_issues
        if total < 2:
            continue
        level = RISK_LEVEL_HIGH if total >= 3 else RISK_LEVEL_MEDIUM
        reasons = [
            f"Boiler/heating asset age estimate exceeds {BOILER_AGE_YEARS_THRESHOLD} years",
            f"{total} heating-related issues or work orders in the last 12 months",
        ]
        signals.append({
            "signal_category": SIGNAL_CATEGORY_ASSET,
            "risk_type": RISK_TYPE_BOILER_FAILURE,
            "risk_level": level,
            "reasons": reasons,
            "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_BOILER_FAILURE],
            "asset_id": aid,
        })
    return signals


# ---------- Rule: Damp / Moisture Risk ----------
async def _rule_damp_moisture(
    db, property_id: str, client_id: str,
    property_doc: Optional[Dict], assets: List[Dict],
    work_orders: List[Dict], issues: List[Dict],
) -> List[Dict[str, Any]]:
    damp_cats = {"damp", "moisture", "mould"}
    damp_wo = [wo for wo in work_orders if _normalize_category(wo.get("category")) in damp_cats]
    damp_issues = [i for i in issues if _normalize_category(i.get("category")) in damp_cats]
    total = len(damp_wo) + len(damp_issues)
    if total < 2:
        return []
    building_age = (property_doc or {}).get("building_age_years")
    if building_age is not None and building_age < DAMP_PROPERTY_AGE_YEARS_THRESHOLD:
        return []
    level = RISK_LEVEL_HIGH if total >= 3 else RISK_LEVEL_MEDIUM
    reasons = [f"{total} damp-related issues or work orders in the last 12 months"]
    if building_age is not None:
        reasons.append(f"Property age {building_age} years (older stock increases damp risk)")
    return [{
        "signal_category": SIGNAL_CATEGORY_ASSET,
        "risk_type": RISK_TYPE_DAMP_MOISTURE,
        "risk_level": level,
        "reasons": reasons,
        "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_DAMP_MOISTURE],
        "asset_id": None,
    }]


# ---------- Rule: Electrical Risk ----------
async def _rule_electrical(
    db, property_id: str, client_id: str,
    property_doc: Optional[Dict], assets: List[Dict],
    work_orders: List[Dict], issues: List[Dict],
    requirements: List[Dict],
) -> List[Dict[str, Any]]:
    elec_cats = {"electrical", "electric"}
    elec_wo = [wo for wo in work_orders if _normalize_category(wo.get("category")) in elec_cats]
    elec_issues = [i for i in issues if _normalize_category(i.get("category")) in elec_cats]
    total = len(elec_wo) + len(elec_issues)
    eicr_overdue = any(
        (r.get("requirement_code") or "").lower().find("eicr") >= 0 or (r.get("requirement_type") or "").lower().find("eicr") >= 0
        for r in requirements
    )
    if total < 2 and not eicr_overdue:
        return []
    reasons = []
    if total >= 2:
        reasons.append(f"{total} electrical issues or work orders in the last 12 months")
    if eicr_overdue:
        reasons.append("EICR overdue or missing")
    level = RISK_LEVEL_HIGH if (total >= 2 and eicr_overdue) else (RISK_LEVEL_MEDIUM if reasons else RISK_LEVEL_LOW)
    return [{
        "signal_category": SIGNAL_CATEGORY_ASSET,
        "risk_type": RISK_TYPE_ELECTRICAL,
        "risk_level": level,
        "reasons": reasons or ["Electrical risk factors present"],
        "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_ELECTRICAL],
        "asset_id": None,
    }]


# ---------- Rule: Recurring Repairs Risk ----------
async def _rule_recurring_repairs(
    db, property_id: str, client_id: str,
    property_doc: Optional[Dict], assets: List[Dict],
    work_orders: List[Dict], issues: List[Dict],
) -> List[Dict[str, Any]]:
    combined = []
    for wo in work_orders:
        combined.append({"category": wo.get("category"), "asset_id": wo.get("asset_id")})
    for i in issues:
        combined.append({"category": i.get("category"), "asset_id": i.get("asset_id")})
    by_key: Dict[str, int] = {}
    for item in combined:
        cat = _normalize_category(item.get("category"))
        aid = item.get("asset_id") or ""
        key = f"{cat}|{aid}" if aid else cat
        by_key[key] = by_key.get(key, 0) + 1
    signals = []
    for key, count in by_key.items():
        if count < RECURRING_ISSUES_THRESHOLD:
            continue
        parts = key.split("|", 1)
        cat_label = (parts[0] or "same category").replace("_", " ")
        reasons = [f"Same asset/category has {count} issues or work orders in the last 12 months"]
        signals.append({
            "signal_category": SIGNAL_CATEGORY_ASSET,
            "risk_type": RISK_TYPE_RECURRING_REPAIRS,
            "risk_level": RISK_LEVEL_HIGH if count >= 4 else RISK_LEVEL_MEDIUM,
            "reasons": reasons,
            "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_RECURRING_REPAIRS],
            "asset_id": parts[1] if len(parts) > 1 and parts[1] else None,
        })
    return signals


# ---------- Rule: SLA Breach Risk ----------
async def _rule_sla_breach(
    db, property_id: str, client_id: str,
    work_orders_breached_30: List[Dict], work_orders_breached_60: List[Dict],
) -> List[Dict[str, Any]]:
    breached_30 = len(work_orders_breached_30)
    breached_60 = len(work_orders_breached_60)
    if breached_30 < SLA_BREACH_COUNT_THRESHOLD and breached_60 < SLA_BREACH_COUNT_THRESHOLD:
        return []
    reasons = []
    if breached_30 >= SLA_BREACH_COUNT_THRESHOLD:
        reasons.append(f"{breached_30} work orders breached SLA in the last 30 days")
    if breached_60 >= SLA_BREACH_COUNT_THRESHOLD and breached_60 != breached_30:
        reasons.append(f"{breached_60} work orders breached SLA in the last 60 days")
    contractor_ids = [wo.get("contractor_id") for wo in work_orders_breached_60 if wo.get("contractor_id")]
    if len(contractor_ids) > len(set(contractor_ids)) and contractor_ids:
        reasons.append("Same contractor involved in multiple breached assignments")
    return [{
        "signal_category": SIGNAL_CATEGORY_OPERATIONAL,
        "risk_type": RISK_TYPE_SLA_BREACH,
        "risk_level": RISK_LEVEL_HIGH if (breached_30 >= 3 or (reasons and "Same contractor" in str(reasons))) else RISK_LEVEL_MEDIUM,
        "reasons": reasons,
        "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_SLA_BREACH],
        "asset_id": None,
    }]


# ---------- Rule: Compliance Churn Risk ----------
async def _rule_compliance_churn(
    db, property_id: str, client_id: str,
    requirements: List[Dict],
) -> List[Dict[str, Any]]:
    if not requirements:
        return []
    by_code: Dict[str, int] = {}
    for r in requirements:
        code = (r.get("requirement_code") or r.get("requirement_type") or "unknown").strip().lower()
        by_code[code] = by_code.get(code, 0) + 1
    repeated = [code for code, count in by_code.items() if count >= 2 or len(requirements) >= 3]
    overdue_missing = [r for r in requirements if (r.get("status") or "").upper() in ("OVERDUE", "EXPIRED", "MISSING", "PENDING")]
    if not repeated and len(overdue_missing) < 2:
        return []
    reasons = []
    if repeated:
        reasons.append(f"Same obligation type repeatedly overdue or missing: {', '.join(repeated[:3])}")
    if len(overdue_missing) >= 2:
        reasons.append(f"{len(overdue_missing)} obligations overdue or missing evidence")
    return [{
        "signal_category": SIGNAL_CATEGORY_COMPLIANCE,
        "risk_type": RISK_TYPE_COMPLIANCE_CHURN,
        "risk_level": RISK_LEVEL_HIGH if len(overdue_missing) >= 4 else RISK_LEVEL_MEDIUM,
        "reasons": reasons,
        "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_COMPLIANCE_CHURN],
        "asset_id": None,
    }]


# ---------- Rule: Certificate Expiry Soon ----------
async def _rule_certificate_expiry_soon(
    db, property_id: str, client_id: str,
    requirements_expiring: List[Dict],
) -> List[Dict[str, Any]]:
    """One signal per property when any certificate is expiring soon (status EXPIRING_SOON)."""
    if not requirements_expiring:
        return []
    reasons = []
    for r in requirements_expiring[:10]:
        title = r.get("title") or r.get("requirement_code") or r.get("requirement_type") or "Certificate"
        reasons.append(f"{title} expiring soon")
    level = RISK_LEVEL_HIGH if len(requirements_expiring) >= 3 else RISK_LEVEL_MEDIUM
    return [{
        "signal_category": SIGNAL_CATEGORY_COMPLIANCE,
        "risk_type": RISK_TYPE_CERTIFICATE_EXPIRY_SOON,
        "risk_level": level,
        "reasons": reasons,
        "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_CERTIFICATE_EXPIRY_SOON],
        "asset_id": None,
    }]


# ---------- Rule: Maintenance Frequency Risk ----------
async def _rule_maintenance_frequency(
    db, property_id: str, client_id: str,
    work_orders: List[Dict], issues: List[Dict],
) -> List[Dict[str, Any]]:
    since = _now() - timedelta(days=ROLLING_6_MONTHS_DAYS)
    since_iso = since.isoformat()
    wo_in_window = [wo for wo in work_orders if (wo.get("created_at") or "") >= since_iso]
    issues_in_window = [i for i in issues if (i.get("created_at") or "") >= since_iso]
    total = len(wo_in_window) + len(issues_in_window)
    if total < MAINTENANCE_FREQUENCY_THRESHOLD:
        return []
    level = RISK_LEVEL_HIGH if total >= 6 else RISK_LEVEL_MEDIUM
    reasons = [f"{total} maintenance issues or work orders in the last 6 months"]
    return [{
        "signal_category": SIGNAL_CATEGORY_ASSET,
        "risk_type": RISK_TYPE_MAINTENANCE_FREQUENCY,
        "risk_level": level,
        "reasons": reasons,
        "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_MAINTENANCE_FREQUENCY],
        "asset_id": None,
    }]


async def generate_risk_signals_for_property(property_id: str, client_id: str) -> Dict[str, Any]:
    """
    Generate all risk signals for a single property and persist to risk_signals.
    Replaces existing active heuristic signals for this property with the new set.
    Returns { "generated": count, "signals": [ ... ] }.
    """
    db = database.get_db()
    now = _now()
    now_iso = _iso(now)

    property_doc = await _fetch_property(db, property_id, client_id)
    if not property_doc:
        return {"generated": 0, "signals": [], "previous_active_removed": 0}

    assets = await _fetch_assets(db, property_id)
    work_orders_12 = await _fetch_work_orders(db, property_id, client_id, ROLLING_12_MONTHS_DAYS)
    work_orders_breached_30 = await _fetch_work_orders_with_breach_in_window(db, property_id, client_id, ROLLING_30_DAYS)
    work_orders_breached_60 = await _fetch_work_orders_with_breach_in_window(db, property_id, client_id, ROLLING_60_DAYS)
    issues_12 = await _fetch_issues(db, property_id, client_id, ROLLING_12_MONTHS_DAYS)
    requirements = await _fetch_requirements_overdue(db, property_id, client_id)
    requirements_expiring = await _fetch_requirements_expiring_soon(db, property_id, client_id)

    all_signals: List[Dict[str, Any]] = []

    # Asset rules
    boiler_signals = await _rule_boiler_failure(db, property_id, client_id, property_doc, assets, work_orders_12, issues_12)
    all_signals.extend(boiler_signals)
    damp_signals = await _rule_damp_moisture(db, property_id, client_id, property_doc, assets, work_orders_12, issues_12)
    all_signals.extend(damp_signals)
    elec_signals = await _rule_electrical(db, property_id, client_id, property_doc, assets, work_orders_12, issues_12, requirements)
    all_signals.extend(elec_signals)
    recur_signals = await _rule_recurring_repairs(db, property_id, client_id, property_doc, assets, work_orders_12, issues_12)
    all_signals.extend(recur_signals)
    maint_signals = await _rule_maintenance_frequency(db, property_id, client_id, work_orders_12, issues_12)
    all_signals.extend(maint_signals)

    # Operational
    sla_signals = await _rule_sla_breach(db, property_id, client_id, work_orders_breached_30, work_orders_breached_60)
    all_signals.extend(sla_signals)

    # Compliance
    comp_signals = await _rule_compliance_churn(db, property_id, client_id, requirements)
    all_signals.extend(comp_signals)
    cert_expiry_signals = await _rule_certificate_expiry_soon(db, property_id, client_id, requirements_expiring)
    all_signals.extend(cert_expiry_signals)

    # Remove duplicates by (risk_type, asset_id): keep first
    seen = set()
    unique_signals = []
    for s in all_signals:
        key = (s["risk_type"], s.get("asset_id"))
        if key in seen:
            continue
        seen.add(key)
        unique_signals.append(s)

    # Replace active heuristic signals for this property
    deleted = await db.risk_signals.delete_many({
        "client_id": client_id,
        "property_id": property_id,
        "status": STATUS_ACTIVE,
        "source": SOURCE_HEURISTIC,
    })
    previous_active_removed = int(deleted.deleted_count)

    inserted = []
    for s in unique_signals:
        signal_id = f"rs_{uuid.uuid4().hex[:12]}"
        first_reason = (s["reasons"][0] if s.get("reasons") else "").strip()
        description = f"{s['risk_type']}: {first_reason}" if first_reason else s.get("recommended_action") or s["risk_type"]
        suggested_actions = _suggested_actions_for_signal(s["signal_category"], s["risk_type"])
        doc = {
            "signal_id": signal_id,
            "client_id": client_id,
            "property_id": property_id,
            "asset_id": s.get("asset_id"),
            "signal_category": s["signal_category"],
            "risk_type": s["risk_type"],
            "risk_level": s["risk_level"],
            "description": description,
            "suggested_actions": suggested_actions,
            "trend": TREND_STABLE,
            "score": None,
            "reasons": s["reasons"],
            "recommended_action": s["recommended_action"],
            "status": STATUS_ACTIVE,
            "source": SOURCE_HEURISTIC,
            "generated_at": now_iso,
            "updated_at": now_iso,
            "metadata": {},
        }
        await db.risk_signals.insert_one(doc)
        doc.pop("_id", None)
        inserted.append(doc)
        try:
            await create_audit_log(
                action=AuditAction.RISK_SIGNAL_CREATED,
                client_id=client_id,
                resource_type="risk_signal",
                resource_id=signal_id,
                metadata={"property_id": property_id, "risk_type": s["risk_type"], "risk_level": s["risk_level"]},
            )
        except Exception as e:
            logger.warning("Audit log for risk signal create failed: %s", e)

    return {"generated": len(inserted), "signals": inserted}


async def generate_risk_signals_for_org(client_id: str) -> Dict[str, Any]:
    """Generate risk signals for all properties of a client. Returns { "properties_processed": N, "total_signals": M }."""
    db = database.get_db()
    cursor = db.properties.find({"client_id": client_id, "is_active": {"$ne": False}}, {"_id": 0, "property_id": 1})
    properties = await cursor.to_list(500)
    total_signals = 0
    for p in properties:
        pid = p.get("property_id")
        if not pid:
            continue
        try:
            out = await generate_risk_signals_for_property(pid, client_id)
            total_signals += out["generated"]
        except Exception as e:
            logger.warning("Risk signal generation failed for property %s: %s", pid, e)
    return {"properties_processed": len(properties), "total_signals": total_signals}


async def get_risk_signals_for_property(
    property_id: str, client_id: str, status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """Return stored risk signals for a property with summary. Used by GET property risk-signals API."""
    db = database.get_db()
    q = {"property_id": property_id, "client_id": client_id}
    if status_filter:
        q["status"] = status_filter
    cursor = db.risk_signals.find(q).sort("generated_at", -1)
    signals = await cursor.to_list(100)
    for s in signals:
        s.pop("_id", None)

    # Last recalculated: max generated_at for this property
    last_rec = None
    if signals:
        last_rec = max(s.get("generated_at") for s in signals if s.get("generated_at"))

    high = sum(1 for s in signals if (s.get("risk_level") or "").lower() == RISK_LEVEL_HIGH or (s.get("risk_level") or "").lower() == RISK_LEVEL_CRITICAL)
    medium = sum(1 for s in signals if (s.get("risk_level") or "").lower() == RISK_LEVEL_MEDIUM)
    low = sum(1 for s in signals if (s.get("risk_level") or "").lower() == RISK_LEVEL_LOW)

    return {
        "summary": {
            "total": len(signals),
            "high": high,
            "medium": medium,
            "low": low,
            "lastRecalculatedAt": last_rec,
        },
        "signals": signals,
    }


async def get_risk_signals_for_client(
    client_id: str,
    property_id_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    risk_level: Optional[str] = None,
    risk_type: Optional[str] = None,
    trend: Optional[str] = None,
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    """Return stored risk signals for a client (portfolio) with summary, highPriority, and optional filters."""
    db = database.get_db()
    q_query = {"client_id": client_id}
    if property_id_filter:
        q_query["property_id"] = property_id_filter
    if status_filter:
        q_query["status"] = status_filter
    if risk_level:
        q_query["risk_level"] = risk_level.lower()
    if risk_type:
        q_query["risk_type"] = risk_type
    if trend:
        q_query["trend"] = trend.lower()
    if from_date or to_date:
        date_field = "updated_at"
        if from_date:
            try:
                dt_from = _parse_dt(from_date)
                if dt_from:
                    q_query.setdefault(date_field, {})["$gte"] = dt_from.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            except Exception:
                pass
        if to_date:
            try:
                dt_to = _parse_dt(to_date)
                if dt_to:
                    end_of_day = dt_to.replace(hour=23, minute=59, second=59, microsecond=999999)
                    q_query.setdefault(date_field, {})["$lte"] = end_of_day.isoformat()
            except Exception:
                pass
    if q and q.strip():
        q_strip = q.strip()
        q_query["$or"] = [
            {"risk_type": {"$regex": q_strip, "$options": "i"}},
            {"recommended_action": {"$regex": q_strip, "$options": "i"}},
            {"reasons": {"$regex": q_strip, "$options": "i"}},
        ]
    cursor = db.risk_signals.find(q_query).sort("updated_at", -1).limit(limit)
    signals = await cursor.to_list(limit)
    for s in signals:
        s.pop("_id", None)

    last_rec = None
    if signals:
        last_rec = max((s.get("generated_at") or s.get("updated_at") or "") for s in signals)
    high = sum(1 for s in signals if (s.get("risk_level") or "").lower() in (RISK_LEVEL_HIGH, RISK_LEVEL_CRITICAL))
    medium = sum(1 for s in signals if (s.get("risk_level") or "").lower() == RISK_LEVEL_MEDIUM)
    low = sum(1 for s in signals if (s.get("risk_level") or "").lower() == RISK_LEVEL_LOW)
    properties_affected = len({s.get("property_id") for s in signals if s.get("property_id")})
    preventive_actions = sum(1 for s in signals if s.get("status") == STATUS_ACTIVE and s.get("recommended_action"))

    high_priority = [s for s in signals if (s.get("risk_level") or "").lower() in (RISK_LEVEL_HIGH, RISK_LEVEL_CRITICAL)][:15]

    return {
        "summary": {
            "total": len(signals),
            "high": high,
            "medium": medium,
            "low": low,
            "propertiesAffected": properties_affected,
            "preventiveActions": preventive_actions,
            "lastRecalculatedAt": last_rec,
        },
        "signals": signals,
        "highPriority": high_priority,
    }


async def get_risk_signals_admin_summary(
    client_id_filter: Optional[str] = None,
    risk_level: Optional[str] = None,
    risk_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit_signals: int = 200,
) -> Dict[str, Any]:
    """
    Admin: aggregate risk signals across clients (or for one client).
    Returns total active, counts by level, by type, top properties, top clients, recent signals.
    """
    db = database.get_db()
    q = {}
    if client_id_filter:
        q["client_id"] = client_id_filter
    if risk_level:
        q["risk_level"] = risk_level.lower()
    if risk_type:
        q["risk_type"] = risk_type
    if status_filter:
        q["status"] = status_filter

    cursor = db.risk_signals.find(q).sort("generated_at", -1).limit(limit_signals * 2)  # fetch extra for aggregates
    signals = await cursor.to_list(limit_signals * 2)
    for s in signals:
        s.pop("_id", None)

    active = [s for s in signals if (s.get("status") or "").lower() == STATUS_ACTIVE]
    by_level: Dict[str, int] = {}
    for s in signals:
        lev = (s.get("risk_level") or "unknown").lower()
        by_level[lev] = by_level.get(lev, 0) + 1
    by_type: Dict[str, int] = {}
    for s in signals:
        rt = s.get("risk_type") or "Unknown"
        by_type[rt] = by_type.get(rt, 0) + 1

    # Top affected properties (by signal count)
    prop_counts: Dict[str, int] = {}
    for s in signals:
        pid = s.get("property_id")
        if pid:
            prop_counts[pid] = prop_counts.get(pid, 0) + 1
    top_properties = sorted(prop_counts.items(), key=lambda x: -x[1])[:20]

    # Top affected clients
    client_counts: Dict[str, int] = {}
    for s in signals:
        cid = s.get("client_id")
        if cid:
            client_counts[cid] = client_counts.get(cid, 0) + 1
    top_clients = sorted(client_counts.items(), key=lambda x: -x[1])[:20]

    recent = signals[:50]

    # Top compliance risks (signal_category compliance)
    top_compliance = [s for s in signals if (s.get("signal_category") or "").lower() == SIGNAL_CATEGORY_COMPLIANCE][:15]

    # Top maintenance risks (asset + operational)
    top_maintenance = [
        s for s in signals
        if (s.get("signal_category") or "").lower() in (SIGNAL_CATEGORY_ASSET, SIGNAL_CATEGORY_OPERATIONAL)
    ][:15]

    # Properties with repeated issues (risk_type Recurring Repairs)
    repeated_prop_counts: Dict[str, int] = {}
    for s in signals:
        if s.get("risk_type") == RISK_TYPE_RECURRING_REPAIRS:
            pid = s.get("property_id")
            if pid:
                repeated_prop_counts[pid] = repeated_prop_counts.get(pid, 0) + 1
    repeated_issues_properties = sorted(repeated_prop_counts.items(), key=lambda x: -x[1])[:15]

    # SLA breach risks (risk_type SLA Breach)
    sla_breach_signals = [s for s in signals if s.get("risk_type") == RISK_TYPE_SLA_BREACH][:15]

    # Portfolio heatmap: per-property level counts (top 30 properties by total signals)
    prop_levels: Dict[str, Dict[str, int]] = {}
    for s in signals:
        pid = s.get("property_id")
        if not pid:
            continue
        if pid not in prop_levels:
            prop_levels[pid] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        lev = (s.get("risk_level") or "medium").lower()
        if lev in prop_levels[pid]:
            prop_levels[pid][lev] += 1
        else:
            prop_levels[pid]["medium"] += 1
    # Sort by total signals, take top 30
    heatmap_properties = sorted(
        prop_levels.items(),
        key=lambda x: sum(x[1].values()),
        reverse=True,
    )[:30]
    pid_to_client: Dict[str, str] = {}
    for s in signals:
        pid = s.get("property_id")
        cid = s.get("client_id")
        if pid and cid and pid not in pid_to_client:
            pid_to_client[pid] = cid
    portfolio_heatmap = [
        {"property_id": pid, "client_id": pid_to_client.get(pid), **counts}
        for pid, counts in heatmap_properties
    ]

    return {
        "totalActive": len(active),
        "totalSignals": len(signals),
        "byLevel": by_level,
        "byType": by_type,
        "topProperties": [{"property_id": p, "count": c} for p, c in top_properties],
        "topClients": [{"client_id": c, "count": n} for c, n in top_clients],
        "recentSignals": recent,
        "topComplianceRisks": top_compliance,
        "topMaintenanceRisks": top_maintenance,
        "repeatedIssuesProperties": [{"property_id": p, "count": c} for p, c in repeated_issues_properties],
        "slaBreachRisks": sla_breach_signals,
        "portfolioHeatmap": portfolio_heatmap,
    }


async def get_risk_signal_by_id(signal_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    """Return a single risk signal by id for the detail drawer. Returns None if not found or wrong client."""
    db = database.get_db()
    doc = await db.risk_signals.find_one({"signal_id": signal_id, "client_id": client_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


async def create_issue_from_risk_signal(
    signal_id: str,
    client_id: str,
    description_override: Optional[str] = None,
    reporter_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a maintenance issue from a risk signal (user-confirmed action).
    Links issue to risk_signal_id. Audits ISSUE_CREATED_FROM_RISK_SIGNAL.
    """
    doc = await get_risk_signal_by_id(signal_id=signal_id, client_id=client_id)
    if not doc:
        raise ValueError("Risk signal not found or does not belong to this client")
    property_id = doc.get("property_id")
    if not property_id:
        raise ValueError("Risk signal has no property_id")
    description = (description_override or "").strip() or (
        f"{doc.get('risk_type', 'Risk')}: {doc.get('recommended_action', 'Follow up')}"
    )
    from services import maintenance_issues_service
    issue = await maintenance_issues_service.create_issue(
        client_id=client_id,
        property_id=property_id,
        description=description,
        source=maintenance_issues_service.SOURCE_CLIENT,
        category=None,
        asset_id=doc.get("asset_id"),
        risk_signal_id=signal_id,
    )
    await create_audit_log(
        action=AuditAction.ISSUE_CREATED_FROM_RISK_SIGNAL,
        client_id=client_id,
        actor_id=reporter_id or "system",
        resource_type="maintenance_issue",
        resource_id=issue.get("issue_id"),
        metadata={"signal_id": signal_id, "property_id": property_id, "risk_type": doc.get("risk_type")},
    )
    return issue


async def create_inspection_issue_from_risk_signal(
    signal_id: str,
    client_id: str,
    description_override: Optional[str] = None,
    reporter_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an inspection-type maintenance issue from a risk signal (schedule_inspection action).
    Description is prefixed with "Inspection: ". Audits INSPECTION_CREATED_FROM_RISK_SIGNAL.
    """
    doc = await get_risk_signal_by_id(signal_id=signal_id, client_id=client_id)
    if not doc:
        raise ValueError("Risk signal not found or does not belong to this client")
    property_id = doc.get("property_id")
    if not property_id:
        raise ValueError("Risk signal has no property_id")
    base_desc = (description_override or "").strip() or (
        f"{doc.get('risk_type', 'Risk')}: {doc.get('recommended_action', 'Schedule inspection')}"
    )
    description = f"Inspection: {base_desc}"
    from services import maintenance_issues_service
    issue = await maintenance_issues_service.create_issue(
        client_id=client_id,
        property_id=property_id,
        description=description,
        source=maintenance_issues_service.SOURCE_CLIENT,
        category=None,
        asset_id=doc.get("asset_id"),
        risk_signal_id=signal_id,
    )
    await create_audit_log(
        action=AuditAction.INSPECTION_CREATED_FROM_RISK_SIGNAL,
        client_id=client_id,
        actor_id=reporter_id or "system",
        resource_type="maintenance_issue",
        resource_id=issue.get("issue_id"),
        metadata={"signal_id": signal_id, "property_id": property_id, "risk_type": doc.get("risk_type")},
    )
    return issue


async def create_work_order_from_risk_signal(
    signal_id: str,
    client_id: str,
    description_override: Optional[str] = None,
    reporter_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a work order from a risk signal (user-confirmed action).
    Links work order to risk_signal_id. Audits WORK_ORDER_CREATED_FROM_RISK_SIGNAL.
    """
    doc = await get_risk_signal_by_id(signal_id=signal_id, client_id=client_id)
    if not doc:
        raise ValueError("Risk signal not found or does not belong to this client")
    property_id = doc.get("property_id")
    if not property_id:
        raise ValueError("Risk signal has no property_id")
    description = (description_override or "").strip() or (
        f"{doc.get('risk_type', 'Risk')}: {doc.get('recommended_action', 'Follow up')}"
    )
    from services import maintenance_service
    wo = await maintenance_service.create_work_order(
        client_id=client_id,
        property_id=property_id,
        description=description,
        source=maintenance_service.SOURCE_CLIENT,
        reporter_id=reporter_id,
        asset_id=doc.get("asset_id"),
        risk_signal_id=signal_id,
    )
    await create_audit_log(
        action=AuditAction.WORK_ORDER_CREATED_FROM_RISK_SIGNAL,
        client_id=client_id,
        actor_id=reporter_id or "system",
        resource_type="work_order",
        resource_id=wo.get("work_order_id"),
        metadata={"signal_id": signal_id, "property_id": property_id, "risk_type": doc.get("risk_type")},
    )
    return wo


async def update_signal_status(
    signal_id: str, client_id: str, new_status: str
) -> Optional[Dict[str, Any]]:
    """Set status to acknowledged or resolved. Returns updated doc or None."""
    if new_status not in (STATUS_ACKNOWLEDGED, STATUS_RESOLVED):
        return None
    db = database.get_db()
    now_iso = _iso(_now())
    action = AuditAction.RISK_SIGNAL_ACKNOWLEDGED if new_status == STATUS_ACKNOWLEDGED else AuditAction.RISK_SIGNAL_RESOLVED
    result = await db.risk_signals.find_one_and_update(
        {"signal_id": signal_id, "client_id": client_id},
        {"$set": {"status": new_status, "updated_at": now_iso}},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
        try:
            await create_audit_log(
                action=action,
                client_id=client_id,
                resource_type="risk_signal",
                resource_id=signal_id,
                metadata={"property_id": result.get("property_id"), "new_status": new_status},
            )
        except Exception as e:
            logger.warning("Audit log for risk signal status update failed: %s", e)
    return result
