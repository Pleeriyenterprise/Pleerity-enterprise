"""
Lifecycle governance: predictive operational risk signals require real maintenance history.

Compliance-oriented signals (certificate expiry, compliance churn, property-age heuristics,
EICR-linked electrical concern) may still surface during onboarding. Operational intelligence
(recurring repairs, maintenance frequency, SLA breach) is suppressed until thresholds are met.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.risk_signal_service import (
    RISK_TYPE_MAINTENANCE_FREQUENCY,
    RISK_TYPE_RECURRING_REPAIRS,
    RISK_TYPE_SLA_BREACH,
)

# Risk types that require demonstrated operational history before activation.
PREDICTIVE_OPERATIONAL_RISK_TYPES = frozenset(
    {
        RISK_TYPE_RECURRING_REPAIRS,
        RISK_TYPE_MAINTENANCE_FREQUENCY,
        RISK_TYPE_SLA_BREACH,
    }
)

# Minimum completed maintenance cycles (closed jobs or resolved issues) from landlord-initiated work.
MIN_COMPLETED_OPERATIONAL_CYCLES = 2

# Minimum qualifying maintenance reports in rolling windows before recurrence/frequency rules apply.
MIN_QUALIFYING_REPORTS_FOR_RECURRENCE = 3
MIN_QUALIFYING_REPORTS_FOR_FREQUENCY = 4

WO_COMPLETED = frozenset({"COMPLETED", "VERIFIED", "CLOSED"})
ISSUE_TERMINAL = frozenset({"closed", "cancelled", "resolved"})

# Seeded / bridge records must not inflate predictive counts.
_EXCLUDED_CREATED_FROM = frozenset({"compliance", "risk_signal", "system"})
_EXCLUDED_SOURCES = frozenset({"system"})


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


def qualifies_for_predictive_operational_count(record: Dict[str, Any]) -> bool:
    """True when an issue or work order should contribute to predictive operational counting."""
    if not isinstance(record, dict):
        return False
    created_from = str(record.get("created_from") or "").strip().lower()
    if created_from in _EXCLUDED_CREATED_FROM:
        return False
    source = str(record.get("source") or "").strip().lower()
    if source in _EXCLUDED_SOURCES:
        return False
    if record.get("operational_root_key"):
        return False
    if record.get("risk_signal_id"):
        return False
    trig = str(record.get("triggering_rule") or "")
    if trig.startswith("compliance_gap:"):
        return False
    return True


def filter_qualifying_operational_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in (records or []) if qualifies_for_predictive_operational_count(r)]


async def client_predictive_operational_history_eligible(
    db,
    client_id: str,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Returns (eligible, metrics) for predictive operational risk rules at client scope.
    Eligibility requires completed landlord-initiated maintenance cycles.
    """
    completed_wo = 0
    async for wo in db.work_orders.find(
        {
            "client_id": client_id,
            "status": {"$in": list(WO_COMPLETED)},
            "created_from": {"$nin": list(_EXCLUDED_CREATED_FROM)},
            "source": {"$nin": list(_EXCLUDED_SOURCES)},
        },
        {"_id": 0, "work_order_id": 1},
    ):
        if qualifies_for_predictive_operational_count(wo):
            completed_wo += 1

    completed_issues = 0
    async for iss in db.maintenance_issues.find(
        {
            "client_id": client_id,
            "status": {"$in": list(ISSUE_TERMINAL)},
            "created_from": {"$nin": list(_EXCLUDED_CREATED_FROM)},
            "source": {"$nin": list(_EXCLUDED_SOURCES)},
        },
        {"_id": 0, "issue_id": 1},
    ):
        if qualifies_for_predictive_operational_count(iss):
            completed_issues += 1

    cycles = completed_wo + completed_issues
    metrics = {
        "completed_work_orders": completed_wo,
        "completed_issues": completed_issues,
        "completed_operational_cycles": cycles,
        "min_required_cycles": MIN_COMPLETED_OPERATIONAL_CYCLES,
    }
    return cycles >= MIN_COMPLETED_OPERATIONAL_CYCLES, metrics


def customer_safe_reasons(reasons: List[str], risk_type: str) -> List[str]:
    """Replace engine-style reason strings with landlord-readable explanations."""
    out: List[str] = []
    rt = (risk_type or "").strip()
    for raw in reasons or []:
        text = str(raw or "").strip()
        lower = text.lower()
        if "same asset/category has" in lower and "issues or work orders" in lower:
            m = re.search(r"(\d+)", text)
            n = m.group(1) if m else "several"
            out.append(
                f"You have received {n} similar maintenance reports in the past year — "
                "investigate whether there is an underlying cause."
            )
            continue
        if "maintenance issues or work orders in the last 6 months" in lower:
            m = re.search(r"^(\d+)", text)
            n = m.group(1) if m else "Several"
            out.append(
                f"{n} maintenance reports in the last six months — review property condition "
                "and whether repeat issues share a common cause."
            )
            continue
        if "work orders breached sla" in lower:
            out.append("Some jobs exceeded their expected response time — review open work with your contractors.")
            continue
        if "electrical issues or work orders" in lower:
            out.append("Multiple electrical maintenance reports in the past year — arrange a safety review if needed.")
            continue
        if rt == RISK_TYPE_RECURRING_REPAIRS and not out:
            out.append("Similar maintenance reports keep appearing — plan a permanent fix instead of repeat repairs.")
            continue
        if rt == RISK_TYPE_MAINTENANCE_FREQUENCY and not out:
            out.append("This property is generating more maintenance reports than usual — review overall condition.")
            continue
        out.append(text)
    return out or ["Review this signal and choose the next best step."]
