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
}


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
        return {"generated": 0, "signals": []}

    assets = await _fetch_assets(db, property_id)
    work_orders_12 = await _fetch_work_orders(db, property_id, client_id, ROLLING_12_MONTHS_DAYS)
    work_orders_breached_30 = await _fetch_work_orders_with_breach_in_window(db, property_id, client_id, ROLLING_30_DAYS)
    work_orders_breached_60 = await _fetch_work_orders_with_breach_in_window(db, property_id, client_id, ROLLING_60_DAYS)
    issues_12 = await _fetch_issues(db, property_id, client_id, ROLLING_12_MONTHS_DAYS)
    requirements = await _fetch_requirements_overdue(db, property_id, client_id)

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

    inserted = []
    for s in unique_signals:
        signal_id = f"rs_{uuid.uuid4().hex[:12]}"
        doc = {
            "signal_id": signal_id,
            "client_id": client_id,
            "property_id": property_id,
            "asset_id": s.get("asset_id"),
            "signal_category": s["signal_category"],
            "risk_type": s["risk_type"],
            "risk_level": s["risk_level"],
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


async def get_risk_signal_by_id(signal_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    """Return a single risk signal by id for the detail drawer. Returns None if not found or wrong client."""
    db = database.get_db()
    doc = await db.risk_signals.find_one({"signal_id": signal_id, "client_id": client_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


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
