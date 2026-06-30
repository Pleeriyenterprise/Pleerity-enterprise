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
from presentation.label_service import enrich_risk_signals
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
STATUS_REMEDIATION_IN_PROGRESS = "remediation_in_progress"
STATUS_RESOLVED = "resolved"
SOURCE_HEURISTIC = "heuristic"

# Monotonic lifecycle ordering for propagation transitions (bounded F4 governance).
_STATUS_LIFECYCLE_ORDER = {
    STATUS_ACTIVE: 0,
    STATUS_ACKNOWLEDGED: 1,
    STATUS_REMEDIATION_IN_PROGRESS: 2,
    STATUS_RESOLVED: 3,
}

# Client dismiss without execution closure (informational risk layer only)
RISK_DISMISS_REASONS = frozenset({"no_action_required", "handled_externally", "duplicate"})

# Rolling windows (days)
ROLLING_12_MONTHS_DAYS = 365
ROLLING_6_MONTHS_DAYS = 183
ROLLING_60_DAYS = 60
ROLLING_30_DAYS = 30
COMPLIANCE_CHURN_LOOKBACK_DAYS = 90
CHURN_SCORE_DIP_THRESHOLD = 65
CHURN_SCORE_RECOVERY_THRESHOLD = 72

# Thresholds
BOILER_AGE_YEARS_THRESHOLD = 10
DAMP_PROPERTY_AGE_YEARS_THRESHOLD = 74  # pre-1950 approx
MAINTENANCE_FREQUENCY_THRESHOLD = 4  # issues in 6 months
SLA_BREACH_COUNT_THRESHOLD = 2
RECURRING_ISSUES_THRESHOLD = 3

# Recommended actions (task §8)
RECOMMENDED_ACTIONS = {
    RISK_TYPE_BOILER_FAILURE: "Arrange a qualified gas engineer inspection externally, or start a compliance job from Operations if your account uses jobs for inspections.",
    RISK_TYPE_DAMP_MOISTURE: "Arrange a damp inspection externally and plan work to fix the underlying cause.",
    RISK_TYPE_ELECTRICAL: "Review your electrical certificate and arrange an external inspection if it is due or out of date.",
    RISK_TYPE_RECURRING_REPAIRS: "Investigate the root cause instead of repeat patch repairs.",
    RISK_TYPE_SLA_BREACH: "Review open jobs with your contractor and re-prioritise anything that is overdue.",
    RISK_TYPE_COMPLIANCE_CHURN: "Upload missing evidence and plan renewals so obligations stay up to date.",
    RISK_TYPE_MAINTENANCE_FREQUENCY: "Review property condition and inspect assets that are generating repeat reports.",
    RISK_TYPE_CERTIFICATE_EXPIRY_SOON: "Renew the certificate before expiry and upload the new document with correct dates.",
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
            actions.append(SUGGESTED_ACTION_CREATE_WORK_ORDER)  # e.g. gas safety renewal job
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
        {"_id": 0},
    )
    rows = await cursor.to_list(100)
    client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 0})
    if not prop:
        return []
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    rows = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=rows,
        client_doc=client_row,
        properties=[prop],
    )
    out = []
    for r in rows:
        out.append(
            {
                "requirement_id": r.get("requirement_id"),
                "requirement_code": r.get("requirement_code"),
                "requirement_type": r.get("requirement_type"),
                "status": r.get("status"),
            }
        )
    return out


async def _fetch_requirements_confirmed_calendar_risk(
    db, property_id: str, client_id: str
) -> List[Dict[str, Any]]:
    """Calendar-confirmed risk rows only — excludes PENDING/MISSING (pending verification)."""
    cursor = db.requirements.find(
        {"property_id": property_id, "client_id": client_id, "status": {"$in": ["OVERDUE", "EXPIRED"]}},
        {"_id": 0},
    )
    rows = await cursor.to_list(100)
    client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 0})
    if not prop:
        return []
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    rows = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=rows,
        client_doc=client_row,
        properties=[prop],
    )
    return [
        {
            "requirement_id": r.get("requirement_id"),
            "requirement_code": r.get("requirement_code"),
            "requirement_type": r.get("requirement_type"),
            "status": r.get("status"),
        }
        for r in rows
    ]


async def _fetch_requirements_expiring_soon(db, property_id: str, client_id: str) -> List[Dict[str, Any]]:
    """Requirements with status EXPIRING_SOON (certificate expiring within configured window)."""
    cursor = db.requirements.find(
        {"property_id": property_id, "client_id": client_id, "status": "EXPIRING_SOON"},
        {"_id": 0},
    )
    rows = await cursor.to_list(100)
    client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 0})
    if not prop:
        return []
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    rows = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=rows,
        client_doc=client_row,
        properties=[prop],
    )
    out = []
    for r in rows:
        out.append(
            {
                "requirement_id": r.get("requirement_id"),
                "requirement_code": r.get("requirement_code"),
                "requirement_type": r.get("requirement_type"),
                "title": r.get("title"),
                "status": r.get("status"),
            }
        )
    return out


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
_CONFIRMED_CALENDAR_EICR_STATUSES = frozenset({"OVERDUE", "EXPIRED"})


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
        (
            (r.get("requirement_code") or "").lower().find("eicr") >= 0
            or (r.get("requirement_type") or "").lower().find("eicr") >= 0
        )
        and str(r.get("status") or "").strip().upper() in _CONFIRMED_CALENDAR_EICR_STATUSES
        for r in requirements
    )
    if total < 2 and not eicr_overdue:
        return []
    reasons = []
    if total >= 2:
        reasons.append(f"{total} electrical issues or work orders in the last 12 months")
    if eicr_overdue:
        reasons.append("EICR overdue (calendar-confirmed)")
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


# ---------- Temporal compliance churn (evidence-based) ----------
_CHURN_BAD_NEW_STATUSES = frozenset(
    {"OVERDUE", "EXPIRED", "MISSING", "PENDING", "NON_COMPLIANT", "AT_RISK", "REJECTED"}
)


async def _temporal_churn_metrics(db, property_id: str, client_id: str) -> Dict[str, Any]:
    """
    Uses score_change_log (per-requirement transitions) and property_compliance_score_history
    (score lapse/recovery cycles). Explainable, defensible churn evidence — not a snapshot-only count.
    """
    since = _now() - timedelta(days=COMPLIANCE_CHURN_LOOKBACK_DAYS)
    since_iso = since.isoformat()
    cursor = db.score_change_log.find(
        {"property_id": property_id, "client_id": client_id, "created_at": {"$gte": since_iso}},
        {"_id": 0, "changed_requirements": 1},
    )
    logs = await cursor.to_list(800)
    bad_transitions_per_key: Dict[str, int] = {}
    for row in logs:
        for ch in row.get("changed_requirements") or []:
            new_s = (ch.get("new_status") or "").upper()
            if new_s in _CHURN_BAD_NEW_STATUSES:
                k = (ch.get("requirement_key") or "unknown").strip().lower()
                bad_transitions_per_key[k] = bad_transitions_per_key.get(k, 0) + 1
    max_bad_single_key = max(bad_transitions_per_key.values()) if bad_transitions_per_key else 0
    keys_with_repeat = sum(1 for c in bad_transitions_per_key.values() if c >= 2)

    hcursor = db.property_compliance_score_history.find(
        {"property_id": property_id, "client_id": client_id, "created_at": {"$gte": since_iso}},
        {"_id": 0, "score": 1},
    ).sort("created_at", 1)
    hist = await hcursor.to_list(500)
    recovery_cycles = 0
    below = False
    for h in hist:
        sc = h.get("score")
        if sc is None:
            continue
        try:
            val = float(sc)
        except (TypeError, ValueError):
            continue
        if val < CHURN_SCORE_DIP_THRESHOLD:
            below = True
        elif below and val >= CHURN_SCORE_RECOVERY_THRESHOLD:
            recovery_cycles += 1
            below = False

    activity_deteriorations = 0
    try:
        ac = db.compliance_activity_log.count_documents(
            {
                "property_id": property_id,
                "client_id": client_id,
                "created_at": {"$gte": since_iso},
                "score_change": {"$lt": 0},
            }
        )
        activity_deteriorations = int(ac)
    except Exception:
        pass

    return {
        "max_bad_transitions_single_key": max_bad_single_key,
        "obligation_keys_with_repeat_bad": keys_with_repeat,
        "recovery_cycles": recovery_cycles,
        "negative_activity_events": activity_deteriorations,
    }


# ---------- Rule: Compliance Churn Risk ----------
async def _rule_compliance_churn(
    db, property_id: str, client_id: str,
    requirements: List[Dict],
) -> List[Dict[str, Any]]:
    metrics = await _temporal_churn_metrics(db, property_id, client_id)
    max_bad = metrics["max_bad_transitions_single_key"]
    cycles = metrics["recovery_cycles"]
    repeat_keys = metrics["obligation_keys_with_repeat_bad"]

    overdue_missing = [
        r
        for r in requirements
        if (r.get("status") or "").upper() in ("OVERDUE", "EXPIRED", "MISSING", "PENDING")
    ]
    current_bad_count = len(overdue_missing)

    temporal_hit = (
        max_bad >= 3
        or cycles >= 2
        or (repeat_keys >= 2 and max_bad >= 2)
        or (metrics["negative_activity_events"] >= 4 and max_bad >= 2)
    )
    if not temporal_hit:
        return []

    if current_bad_count < 1 and cycles < 2 and max_bad < 4:
        return []

    # Recovered obligations with no active operational workflows — historical churn only.
    if current_bad_count == 0:
        open_wo = await db.work_orders.count_documents(
            {
                "client_id": client_id,
                "property_id": property_id,
                "status": {"$nin": ["COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"]},
            }
        )
        open_issues = await db.maintenance_issues.count_documents(
            {
                "client_id": client_id,
                "property_id": property_id,
                "status": {"$nin": ["closed", "cancelled", "resolved"]},
            }
        )
        if open_wo == 0 and open_issues == 0:
            return []

    reasons: List[str] = []
    if max_bad >= 3:
        reasons.append(
            f"In the last {COMPLIANCE_CHURN_LOOKBACK_DAYS}d, at least one obligation moved into a bad status "
            f"{max_bad} times (from compliance score change history)."
        )
    elif max_bad >= 2:
        reasons.append(
            f"Repeated deterioration on tracked obligations in the last {COMPLIANCE_CHURN_LOOKBACK_DAYS}d "
            f"(score_change_log)."
        )
    if cycles >= 2:
        reasons.append(
            f"Compliance score dipped below {CHURN_SCORE_DIP_THRESHOLD} and recovered above "
            f"{CHURN_SCORE_RECOVERY_THRESHOLD} {cycles} times in the last {COMPLIANCE_CHURN_LOOKBACK_DAYS}d."
        )
    if current_bad_count >= 2:
        reasons.append(f"{current_bad_count} obligations are currently overdue or missing evidence.")
    elif current_bad_count == 1:
        reasons.append("At least one obligation is currently overdue or missing evidence.")
    if metrics["negative_activity_events"] >= 4 and max_bad >= 2:
        reasons.append(
            f"{metrics['negative_activity_events']} compliance activity events with negative score impact "
            f"in the lookback window."
        )

    level = RISK_LEVEL_HIGH if current_bad_count >= 4 or max_bad >= 5 or cycles >= 3 else RISK_LEVEL_MEDIUM
    return [{
        "signal_category": SIGNAL_CATEGORY_COMPLIANCE,
        "risk_type": RISK_TYPE_COMPLIANCE_CHURN,
        "risk_level": level,
        "reasons": reasons,
        "recommended_action": RECOMMENDED_ACTIONS[RISK_TYPE_COMPLIANCE_CHURN],
        "asset_id": None,
        "metadata": {"churn_metrics": metrics},
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
    requirements = await _fetch_requirements_confirmed_calendar_risk(db, property_id, client_id)
    requirements_expiring = await _fetch_requirements_expiring_soon(db, property_id, client_id)

    from services.risk_signal_operational_history_governance import (
        client_predictive_operational_history_eligible,
        customer_safe_reasons,
        filter_qualifying_operational_records,
    )

    predictive_ops_eligible, predictive_ops_metrics = await client_predictive_operational_history_eligible(
        db, client_id
    )
    qualifying_work_orders_12 = filter_qualifying_operational_records(work_orders_12)
    qualifying_issues_12 = filter_qualifying_operational_records(issues_12)

    all_signals: List[Dict[str, Any]] = []

    # Asset rules
    boiler_signals = await _rule_boiler_failure(db, property_id, client_id, property_doc, assets, work_orders_12, issues_12)
    all_signals.extend(boiler_signals)
    damp_signals = await _rule_damp_moisture(db, property_id, client_id, property_doc, assets, work_orders_12, issues_12)
    all_signals.extend(damp_signals)
    elec_signals = await _rule_electrical(db, property_id, client_id, property_doc, assets, work_orders_12, issues_12, requirements)
    all_signals.extend(elec_signals)
    if predictive_ops_eligible:
        recur_signals = await _rule_recurring_repairs(
            db, property_id, client_id, property_doc, assets, qualifying_work_orders_12, qualifying_issues_12
        )
        all_signals.extend(recur_signals)
        maint_signals = await _rule_maintenance_frequency(
            db, property_id, client_id, qualifying_work_orders_12, qualifying_issues_12
        )
        all_signals.extend(maint_signals)
        sla_signals = await _rule_sla_breach(db, property_id, client_id, work_orders_breached_30, work_orders_breached_60)
        all_signals.extend(sla_signals)
    else:
        logger.debug(
            "predictive operational risk suppressed client_id=%s property_id=%s metrics=%s",
            client_id,
            property_id,
            predictive_ops_metrics,
        )

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

    # Lineage-preserving regen: merge heuristic refresh in place; never hard-delete operational debt.
    from services.risk_signal_regen_governance import (
        collect_operational_debt_signal_ids,
        should_retain_signal_on_regen,
        stable_signal_key,
    )

    existing_cursor = db.risk_signals.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "source": SOURCE_HEURISTIC,
            "status": {"$ne": STATUS_RESOLVED},
        },
        {"_id": 0},
    )
    existing_signals = await existing_cursor.to_list(500)
    existing_by_key: Dict[tuple, Dict[str, Any]] = {}
    for doc in existing_signals:
        key = stable_signal_key(doc.get("risk_type") or "", doc.get("asset_id"))
        if key not in existing_by_key:
            existing_by_key[key] = doc

    operational_debt_ids = await collect_operational_debt_signal_ids(db, client_id, property_id)
    merged_retained_ids: set = set()
    inserted: List[Dict[str, Any]] = []
    merged_count = 0

    for s in unique_signals:
        s["reasons"] = customer_safe_reasons(s.get("reasons") or [], s.get("risk_type") or "")
        key = stable_signal_key(s["risk_type"], s.get("asset_id"))
        first_reason = (s["reasons"][0] if s.get("reasons") else "").strip()
        description = first_reason or s.get("recommended_action") or "Risk signal requires review"
        suggested_actions = _suggested_actions_for_signal(s["signal_category"], s["risk_type"])
        refresh_fields: Dict[str, Any] = {
            "signal_category": s["signal_category"],
            "risk_type": s["risk_type"],
            "risk_level": s["risk_level"],
            "description": description,
            "suggested_actions": suggested_actions,
            "reasons": s["reasons"],
            "recommended_action": s["recommended_action"],
            "updated_at": now_iso,
            "metadata": s.get("metadata") or {},
        }

        existing_doc = existing_by_key.get(key)
        if existing_doc and existing_doc.get("signal_id"):
            signal_id = existing_doc["signal_id"]
            merged_retained_ids.add(signal_id)
            current_status = (existing_doc.get("status") or STATUS_ACTIVE).lower()
            if current_status not in (STATUS_ACKNOWLEDGED, STATUS_REMEDIATION_IN_PROGRESS):
                refresh_fields["status"] = STATUS_ACTIVE
            await db.risk_signals.update_one(
                {"signal_id": signal_id, "client_id": client_id},
                {"$set": refresh_fields},
            )
            updated = {**existing_doc, **refresh_fields, "signal_id": signal_id}
            inserted.append(updated)
            merged_count += 1
            continue

        signal_id = f"rs_{uuid.uuid4().hex[:12]}"
        doc = {
            "signal_id": signal_id,
            "client_id": client_id,
            "property_id": property_id,
            "asset_id": s.get("asset_id"),
            "trend": TREND_STABLE,
            "score": None,
            "status": STATUS_ACTIVE,
            "source": SOURCE_HEURISTIC,
            "generated_at": now_iso,
            **refresh_fields,
        }
        await db.risk_signals.insert_one(doc)
        doc.pop("_id", None)
        inserted.append(doc)
        merged_retained_ids.add(signal_id)
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

    delete_ids: List[str] = []
    for doc in existing_signals:
        sid = doc.get("signal_id")
        if not sid or sid in merged_retained_ids:
            continue
        if should_retain_signal_on_regen(
            doc,
            operational_debt_ids=operational_debt_ids,
            merged_retained_ids=merged_retained_ids,
        ):
            continue
        if (doc.get("status") or "").lower() == STATUS_ACTIVE:
            delete_ids.append(sid)

    previous_active_removed = 0
    if delete_ids:
        deleted = await db.risk_signals.delete_many(
            {
                "client_id": client_id,
                "property_id": property_id,
                "signal_id": {"$in": delete_ids},
                "status": STATUS_ACTIVE,
                "source": SOURCE_HEURISTIC,
            }
        )
        previous_active_removed = int(deleted.deleted_count)

    try:
        from services.automation_status_service import record_risk_refresh

        await record_risk_refresh(client_id)
    except Exception as e:
        logger.debug("automation_status risk refresh stamp skipped: %s", e)

    out = {
        "generated": len(inserted),
        "signals": inserted,
        "previous_active_removed": previous_active_removed,
        "merged_in_place": merged_count,
        "operational_debt_signal_count": len(operational_debt_ids),
    }
    try:
        from services.compliance_evidence_graph.producers.hooks import dispatch_p1_producer
        from services.compliance_evidence_graph.producers.registry import ProducerContext

        await dispatch_p1_producer(
            ProducerContext(
                mutation_kind="risk_signal_generation",
                client_id=client_id,
                source_collection="risk_signals",
                source_id=property_id,
                property_id=property_id,
                correlation_id=f"RISK_GEN:{property_id}:{now_iso}",
                mutation_timestamp=now_iso,
                authoritative_payload=out,
            )
        )
    except Exception:
        pass
    return out


async def generate_risk_signals_for_org(client_id: str) -> Dict[str, Any]:
    """Generate risk signals for all properties of a client. Returns counts aligned with job metrics."""
    db = database.get_db()
    cursor = db.properties.find({"client_id": client_id, "is_active": {"$ne": False}}, {"_id": 0, "property_id": 1})
    properties = await cursor.to_list(500)
    total_signals = 0
    total_cleared = 0
    for p in properties:
        pid = p.get("property_id")
        if not pid:
            continue
        try:
            out = await generate_risk_signals_for_property(pid, client_id)
            total_signals += int(out.get("generated") or 0)
            total_cleared += int(out.get("previous_active_removed") or 0)
        except Exception as e:
            logger.warning("Risk signal generation failed for property %s: %s", pid, e)
    return {
        "properties_processed": len(properties),
        "total_signals": total_signals,
        "previous_active_signals_cleared": total_cleared,
    }


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
    enrich_risk_signals(signals)
    from services.operational_continuation_service import enrich_risk_signals_with_continuation

    await enrich_risk_signals_with_continuation(signals, client_id)

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
    enrich_risk_signals(signals)
    from services.operational_continuation_service import enrich_risk_signals_with_continuation

    await enrich_risk_signals_with_continuation(signals, client_id)

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
    enrich_risk_signals(signals)

    # Enrich with friendly labels so admin UI can avoid exposing raw IDs.
    client_ids = sorted({str(s.get("client_id")) for s in signals if s.get("client_id")})
    property_ids = sorted({str(s.get("property_id")) for s in signals if s.get("property_id")})
    client_name_by_id: Dict[str, str] = {}
    property_name_by_id: Dict[str, str] = {}
    if client_ids:
        async for c in db.clients.find(
            {"client_id": {"$in": client_ids}},
            {"_id": 0, "client_id": 1, "company_name": 1, "full_name": 1},
        ):
            cid = c.get("client_id")
            if not cid:
                continue
            client_name_by_id[cid] = c.get("company_name") or c.get("full_name") or cid
    if property_ids:
        async for p in db.properties.find(
            {"property_id": {"$in": property_ids}},
            {"_id": 0, "property_id": 1, "nickname": 1, "address_line_1": 1, "address_line_2": 1, "city": 1},
        ):
            pid = p.get("property_id")
            if not pid:
                continue
            property_name_by_id[pid] = (
                p.get("nickname")
                or p.get("address_line_1")
                or p.get("address_line_2")
                or p.get("city")
                or pid
            )

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

    recent = []
    for s in signals[:50]:
        enriched = dict(s)
        pid = enriched.get("property_id")
        cid = enriched.get("client_id")
        if pid:
            enriched["property_name"] = property_name_by_id.get(pid) or pid
        if cid:
            enriched["client_name"] = client_name_by_id.get(cid) or cid
        recent.append(enriched)

    # Top compliance risks (signal_category compliance)
    top_compliance = []
    for s in [x for x in signals if (x.get("signal_category") or "").lower() == SIGNAL_CATEGORY_COMPLIANCE][:15]:
        enriched = dict(s)
        pid = enriched.get("property_id")
        cid = enriched.get("client_id")
        if pid:
            enriched["property_name"] = property_name_by_id.get(pid) or pid
        if cid:
            enriched["client_name"] = client_name_by_id.get(cid) or cid
        top_compliance.append(enriched)

    # Top maintenance risks (asset + operational)
    top_maintenance = []
    for s in [
        x for x in signals
        if (x.get("signal_category") or "").lower() in (SIGNAL_CATEGORY_ASSET, SIGNAL_CATEGORY_OPERATIONAL)
    ][:15]:
        enriched = dict(s)
        pid = enriched.get("property_id")
        cid = enriched.get("client_id")
        if pid:
            enriched["property_name"] = property_name_by_id.get(pid) or pid
        if cid:
            enriched["client_name"] = client_name_by_id.get(cid) or cid
        top_maintenance.append(enriched)

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
    portfolio_heatmap = []
    for pid, counts in heatmap_properties:
        cid = pid_to_client.get(pid)
        portfolio_heatmap.append(
            {
                "property_id": pid,
                "property_name": property_name_by_id.get(pid) or pid,
                "client_id": cid,
                "client_name": client_name_by_id.get(cid) or cid if cid else None,
                **counts,
            }
        )

    return {
        "totalActive": len(active),
        "totalSignals": len(signals),
        "byLevel": by_level,
        "byType": by_type,
        "topProperties": [{"property_id": p, "property_name": property_name_by_id.get(p) or p, "count": c} for p, c in top_properties],
        "topClients": [{"client_id": c, "client_name": client_name_by_id.get(c) or c, "count": n} for c, n in top_clients],
        "recentSignals": recent,
        "topComplianceRisks": top_compliance,
        "topMaintenanceRisks": top_maintenance,
        "repeatedIssuesProperties": [{"property_id": p, "property_name": property_name_by_id.get(p) or p, "count": c} for p, c in repeated_issues_properties],
        "slaBreachRisks": [
            {
                **s,
                "property_name": property_name_by_id.get(s.get("property_id")) or s.get("property_id"),
                "client_name": client_name_by_id.get(s.get("client_id")) or s.get("client_id"),
            }
            for s in sla_breach_signals
        ],
        "portfolioHeatmap": portfolio_heatmap,
    }


async def get_risk_signal_by_id(signal_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    """Return a single risk signal by id for the detail drawer. Returns None if not found or wrong client."""
    db = database.get_db()
    doc = await db.risk_signals.find_one({"signal_id": signal_id, "client_id": client_id})
    if not doc:
        return None
    doc.pop("_id", None)
    from presentation.label_service import enrich_risk_signal
    from services.operational_continuation_service import enrich_risk_signals_with_continuation

    enrich_risk_signal(doc)
    await enrich_risk_signals_with_continuation([doc], client_id)
    return doc


def _suggested_priority_from_level(risk_level: Optional[str]) -> str:
    l = (risk_level or "medium").strip().lower()
    if l == RISK_LEVEL_CRITICAL:
        return "critical"
    if l == RISK_LEVEL_HIGH:
        return "high"
    if l == RISK_LEVEL_LOW:
        return "low"
    return "medium"


def _recommended_trade_from_risk_type(risk_type: Optional[str]) -> Optional[str]:
    """Lightweight trade hint from risk_type label (not a booking system)."""
    rt = (risk_type or "").lower()
    if any(x in rt for x in ("boiler", "gas", "heating", "cp12")):
        return "gas_engineer"
    if any(x in rt for x in ("electrical", "eicr")):
        return "electrician"
    if any(x in rt for x in ("damp", "moisture", "plumb", "leak", "roof")):
        return "plumber"
    if "sla" in rt or "contractor" in rt:
        return "general_contractor"
    return None


def _action_code_title(code: str) -> str:
    labels = {
        SUGGESTED_ACTION_CREATE_ISSUE: "Create maintenance issue",
        SUGGESTED_ACTION_CREATE_WORK_ORDER: "Create work order",
        SUGGESTED_ACTION_SCHEDULE_INSPECTION: "Schedule inspection",
        SUGGESTED_ACTION_SEND_CONTRACTOR_REMINDER: "Send contractor reminder",
        SUGGESTED_ACTION_REASSIGN_CONTRACTOR: "Reassign contractor",
    }
    return labels.get(code, code.replace("_", " ").title())


def _build_recommended_action_dict(signal_doc: Dict[str, Any], action_code: str) -> Dict[str, Any]:
    rtype = signal_doc.get("risk_type") or ""
    body = (
        signal_doc.get("description")
        or signal_doc.get("recommended_action")
        or rtype
        or action_code
    )
    return {
        "type": action_code,
        "title": _action_code_title(action_code),
        "priority": _suggested_priority_from_level(signal_doc.get("risk_level")),
        "estimated_cost": None,
        "recommended_trade": _recommended_trade_from_risk_type(rtype),
        "description": (body or "")[:500],
    }


async def get_risk_signal_suggested_actions_view(
    signal_id: str, client_id: str
) -> Optional[Dict[str, Any]]:
    """
    Read-only projection for integrations and UI: primary recommended_action + alternatives.
    Aligns with POST .../create-issue, create-work-order, schedule-inspection routes.
    """
    doc = await get_risk_signal_by_id(signal_id=signal_id, client_id=client_id)
    if not doc:
        return None
    from services.operational_continuation_service import resolve_continuation_for_risk_signal

    continuation = await resolve_continuation_for_risk_signal(doc, client_id)
    if continuation.get("has_active_lineage"):
        cta = continuation.get("continuation_cta") or {}
        return {
            "signal_id": signal_id,
            "recommended_action": {
                "type": "view_workflow",
                "title": cta.get("label") or "View workflow",
                "priority": "high",
                "estimated_cost": None,
                "recommended_trade": None,
                "description": continuation.get("user_safe_reason") or "",
            },
            "suggested_action_codes": ["view_workflow"],
            "alternatives": [],
            "operational_continuation": continuation,
        }
    cat = doc.get("signal_category") or ""
    rtype = doc.get("risk_type") or ""
    actions = doc.get("suggested_actions")
    if not isinstance(actions, list) or not actions:
        actions = _suggested_actions_for_signal(cat, rtype)
    primary = actions[0] if actions else SUGGESTED_ACTION_CREATE_ISSUE
    recommended = _build_recommended_action_dict(doc, primary)
    alternatives = [_build_recommended_action_dict(doc, c) for c in actions[1:] if c and c != primary][:6]
    return {
        "signal_id": signal_id,
        "recommended_action": recommended,
        "suggested_action_codes": list(actions),
        "alternatives": alternatives,
        "operational_continuation": continuation,
    }


async def _advance_signal_lifecycle(
    signal_id: str,
    client_id: str,
    target_status: str,
    *,
    propagation_meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Monotonic lifecycle transition for operational propagation (F4 governance)."""
    if target_status not in _STATUS_LIFECYCLE_ORDER:
        return
    db = database.get_db()
    doc = await db.risk_signals.find_one({"signal_id": signal_id, "client_id": client_id}, {"_id": 0, "status": 1})
    if not doc:
        return
    current = (doc.get("status") or STATUS_ACTIVE).lower()
    if current == STATUS_RESOLVED:
        return
    if _STATUS_LIFECYCLE_ORDER.get(current, 0) >= _STATUS_LIFECYCLE_ORDER[target_status]:
        if not propagation_meta:
            return
    now_iso = _iso(_now())
    set_doc: Dict[str, Any] = {"updated_at": now_iso}
    if _STATUS_LIFECYCLE_ORDER.get(current, 0) < _STATUS_LIFECYCLE_ORDER[target_status]:
        set_doc["status"] = target_status
    if propagation_meta:
        set_doc["propagation"] = propagation_meta
    await db.risk_signals.update_one(
        {"signal_id": signal_id, "client_id": client_id, "status": {"$ne": STATUS_RESOLVED}},
        {"$set": set_doc},
    )


async def mark_signal_remediation_in_progress(
    signal_id: str,
    client_id: str,
    *,
    work_order_id: Optional[str] = None,
    issue_id: Optional[str] = None,
) -> None:
    meta: Dict[str, Any] = {"work_order_id": work_order_id, "issue_id": issue_id}
    await _advance_signal_lifecycle(
        signal_id,
        client_id,
        STATUS_REMEDIATION_IN_PROGRESS,
        propagation_meta={k: v for k, v in meta.items() if v},
    )


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
    from services.risk_signal_issue_idempotency import replay_open_issue_for_signal

    replay = await replay_open_issue_for_signal(signal_id, client_id)
    if replay:
        return replay
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
    issue_id = issue.get("issue_id")
    await _advance_signal_lifecycle(
        signal_id,
        client_id,
        STATUS_ACKNOWLEDGED,
        propagation_meta={"issue_id": issue_id, "propagated_at": _iso(_now())},
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
    from services.risk_signal_issue_idempotency import replay_open_issue_for_signal

    replay_issue = await replay_open_issue_for_signal(signal_id, client_id)
    if replay_issue:
        from services.operational_continuation_service import (
            merge_continuation_into_payload,
            resolve_continuation_for_risk_signal,
        )

        continuation = await resolve_continuation_for_risk_signal(doc, client_id)
        return merge_continuation_into_payload(replay_issue, continuation)
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
    await _advance_signal_lifecycle(
        signal_id,
        client_id,
        STATUS_ACKNOWLEDGED,
        propagation_meta={"issue_id": issue.get("issue_id"), "propagated_at": _iso(_now()), "kind": "inspection_issue"},
    )
    await create_audit_log(
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
    from services.operational_continuation_service import (
        merge_continuation_into_payload,
        resolve_continuation_for_risk_signal,
    )
    from services.risk_signal_wo_idempotency import replay_active_work_order_for_risk_signal

    replay = await replay_active_work_order_for_risk_signal(signal_id, client_id)
    if replay:
        continuation = await resolve_continuation_for_risk_signal(doc, client_id)
        return merge_continuation_into_payload(replay, continuation)
    property_id = doc.get("property_id")
    if not property_id:
        raise ValueError("Risk signal has no property_id")
    description = (description_override or "").strip() or (
        f"{doc.get('risk_type', 'Risk')}: {doc.get('recommended_action', 'Follow up')}"
    )
    from services import maintenance_service
    rt = doc.get("risk_type") or ""
    aid = doc.get("asset_id")
    root = f"risk:{rt}:{(aid or '').strip() or 'none'}"
    wo = await maintenance_service.create_work_order(
        client_id=client_id,
        property_id=property_id,
        description=description,
        source=maintenance_service.SOURCE_CLIENT,
        reporter_id=reporter_id,
        asset_id=doc.get("asset_id"),
        risk_signal_id=signal_id,
        created_from="risk_signal",
        triggering_rule="user_confirmed_risk_signal_work_order",
        operational_root_key=root,
    )
    await mark_signal_remediation_in_progress(
        signal_id,
        client_id,
        work_order_id=wo.get("work_order_id"),
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


async def arrange_compliance_inspection_from_risk_signal(
    signal_id: str,
    client_id: str,
    requirement_code_raw: str,
    linked_property_requirement_id: str,
    reporter_id: Optional[str] = None,
    compliance_purpose: str = "inspection",
    description_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Start compliance execution (COMPLIANCE work order) from a risk signal — not a maintenance issue placeholder.
    Requires the same booking rules as POST /compliance-execution/work-orders/book.
    """
    doc = await get_risk_signal_by_id(signal_id=signal_id, client_id=client_id)
    if not doc:
        raise ValueError("Risk signal not found or does not belong to this client")
    property_id = doc.get("property_id")
    if not property_id:
        raise ValueError("Risk signal has no property_id")
    from services.compliance_booking_service import create_compliance_execution_work_order

    return await create_compliance_execution_work_order(
        client_id=client_id,
        property_id=str(property_id).strip(),
        requirement_code_raw=requirement_code_raw,
        compliance_purpose=compliance_purpose,
        compliance_generated_from="risk_signal",
        actor_portal_user_id=reporter_id,
        description_override=description_override,
        compliance_due_at=None,
        linked_property_requirement_id=linked_property_requirement_id.strip(),
        risk_signal_id=signal_id,
        issue_id=None,
    )


async def _risk_signal_has_execution_closure(db, signal_id: str, client_id: str) -> bool:
    """True if a linked maintenance issue or work order shows the signal was operationally closed."""
    if await db.maintenance_issues.find_one(
        {
            "client_id": client_id,
            "risk_signal_id": signal_id,
            "status": {"$in": ["closed", "cancelled", "resolved"]},
        },
        {"_id": 1},
    ):
        return True
    if await db.work_orders.find_one(
        {
            "client_id": client_id,
            "risk_signal_id": signal_id,
            "status": {"$in": ["COMPLETED", "VERIFIED", "CLOSED"]},
        },
        {"_id": 1},
    ):
        return True
    return False


async def update_signal_status(
    signal_id: str,
    client_id: str,
    new_status: str,
    dismiss_reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Set status to acknowledged or resolved. Resolved requires execution closure or an explicit dismiss_reason."""
    if new_status not in (STATUS_ACKNOWLEDGED, STATUS_RESOLVED):
        return None
    db = database.get_db()
    existing = await db.risk_signals.find_one(
        {"signal_id": signal_id, "client_id": client_id},
        {"_id": 0, "status": 1, "acknowledged_at": 1, "resolved_at": 1},
    )
    if not existing:
        return None
    now_iso = _iso(_now())
    set_doc: Dict[str, Any] = {"status": new_status, "updated_at": now_iso}
    # INV-RS-001 / INV-RS-002: authoritative lifecycle timestamps (additive, preserve first write).
    if new_status == STATUS_ACKNOWLEDGED and not existing.get("acknowledged_at"):
        set_doc["acknowledged_at"] = now_iso
    if new_status == STATUS_RESOLVED:
        if not existing.get("resolved_at"):
            set_doc["resolved_at"] = now_iso
    if new_status == STATUS_RESOLVED:
        if not await _risk_signal_has_execution_closure(db, signal_id, client_id):
            dr = (dismiss_reason or "").strip().lower()
            if dr not in RISK_DISMISS_REASONS:
                raise ValueError(
                    "To dismiss this risk signal, choose a reason (no_action_required, handled_externally, duplicate) "
                    "or complete linked maintenance work (issue or work order) first."
                )
            set_doc["dismiss_reason"] = dr
        else:
            set_doc["dismiss_reason"] = None
    else:
        set_doc["dismiss_reason"] = None

    action = AuditAction.RISK_SIGNAL_ACKNOWLEDGED if new_status == STATUS_ACKNOWLEDGED else AuditAction.RISK_SIGNAL_RESOLVED
    result = await db.risk_signals.find_one_and_update(
        {"signal_id": signal_id, "client_id": client_id},
        {"$set": set_doc},
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
                metadata={
                    "property_id": result.get("property_id"),
                    "new_status": new_status,
                    "dismiss_reason": result.get("dismiss_reason"),
                },
            )
        except Exception as e:
            logger.warning("Audit log for risk signal status update failed: %s", e)
        try:
            from services.compliance_outcome_engine import (
                apply_action_outcome,
                EVENT_RISK_SIGNAL_ACKNOWLEDGED,
                EVENT_RISK_SIGNAL_RESOLVED,
            )
            event_type = EVENT_RISK_SIGNAL_ACKNOWLEDGED if new_status == STATUS_ACKNOWLEDGED else EVENT_RISK_SIGNAL_RESOLVED
            result["outcome"] = await apply_action_outcome(
                {
                    "event_type": event_type,
                    "client_id": client_id,
                    "property_id": result.get("property_id"),
                    "asset_id": result.get("asset_id"),
                    "requirement_type": None,
                    "timestamp": now_iso,
                    "source_id": signal_id,
                    "dedupe_key": f"{event_type}:{signal_id}",
                    "actor_id": None,
                    "actor_role": "CLIENT",
                    "metadata": {"signal_id": signal_id},
                }
            )
        except Exception as outcome_err:
            logger.debug("Action outcome risk signal status skip: %s", outcome_err)
    return result
