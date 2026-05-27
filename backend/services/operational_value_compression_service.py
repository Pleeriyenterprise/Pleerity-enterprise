"""
OPERATIONAL-VALUE-COMPRESSION-01 — consequence-aware prioritisation and pressure compression.

Additive operational truth layer: compresses cognitive load while preserving counts.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from database import database

logger = logging.getLogger(__name__)

# Consequence categories (Phase 1)
CONSEQUENCE_OPERATIONALLY_DANGEROUS = "operationally_dangerous"
CONSEQUENCE_FINANCIALLY_RISKY = "financially_risky"
CONSEQUENCE_COMPLIANCE_BLOCKING = "compliance_blocking"
CONSEQUENCE_RECURRING_DEGRADATION = "recurring_degradation"
CONSEQUENCE_STALE_OPERATIONAL_DEBT = "stale_operational_debt"
CONSEQUENCE_INFORMATIONAL_ONLY = "informational_only"

ALL_CONSEQUENCE_CATEGORIES = (
    CONSEQUENCE_OPERATIONALLY_DANGEROUS,
    CONSEQUENCE_FINANCIALLY_RISKY,
    CONSEQUENCE_COMPLIANCE_BLOCKING,
    CONSEQUENCE_RECURRING_DEGRADATION,
    CONSEQUENCE_STALE_OPERATIONAL_DEBT,
    CONSEQUENCE_INFORMATIONAL_ONLY,
)

OPEN_ISSUE_STATUSES = frozenset(
    {
        "open",
        "new",
        "triaged",
        "monitoring",
        "investigating",
        "ready_for_work_order",
        "in_progress",
    }
)
OPEN_WO_STATUSES = frozenset({"OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS", "AWAITING_PARTS", "DRAFT"})
ACTIVE_RISK_STATUSES = frozenset({"active", "acknowledged", "remediation_in_progress"})


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _days_old(value: Any) -> Optional[float]:
    d = _parse_dt(value)
    if not d:
        return None
    return (datetime.now(timezone.utc) - d).total_seconds() / 86400


def _if_ignored_message(consequence: str, entity: str) -> str:
    messages = {
        CONSEQUENCE_OPERATIONALLY_DANGEROUS: f"If ignored, this {entity} can stall all dependent maintenance and increase complaint or damage risk.",
        CONSEQUENCE_FINANCIALLY_RISKY: f"If ignored, this {entity} may lead to fines, rent disputes, or emergency repair costs.",
        CONSEQUENCE_COMPLIANCE_BLOCKING: f"If ignored, compliance evidence or certification may remain blocked.",
        CONSEQUENCE_RECURRING_DEGRADATION: f"If ignored, repeat failures are likely across the portfolio.",
        CONSEQUENCE_STALE_OPERATIONAL_DEBT: f"If ignored, operational debt compounds and queue pressure grows.",
        CONSEQUENCE_INFORMATIONAL_ONLY: f"This {entity} is informational; no immediate operational block.",
    }
    return messages.get(consequence, messages[CONSEQUENCE_INFORMATIONAL_ONLY])


def classify_risk_consequence(signal: Dict[str, Any]) -> Dict[str, Any]:
    rt = (signal.get("risk_type") or "").lower()
    level = (signal.get("risk_level") or "").lower()
    status = (signal.get("status") or "").lower()
    if status == "resolved":
        cat = CONSEQUENCE_INFORMATIONAL_ONLY
    elif "compliance" in rt or "certificate" in rt or "expir" in rt:
        cat = CONSEQUENCE_COMPLIANCE_BLOCKING
    elif "recurr" in rt or "repair" in rt or "frequency" in rt:
        cat = CONSEQUENCE_RECURRING_DEGRADATION
    elif level in ("critical", "high") or "sla" in rt or "breach" in rt:
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    elif "electric" in rt:
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    elif status == "acknowledged":
        cat = CONSEQUENCE_INFORMATIONAL_ONLY
    else:
        cat = CONSEQUENCE_FINANCIALLY_RISKY if "rent" in rt else CONSEQUENCE_OPERATIONALLY_DANGEROUS
    escalating = status == "active" and level in ("critical", "high")
    return {
        "consequence_category": cat,
        "if_ignored": _if_ignored_message(cat, "risk signal"),
        "blocked_area": "compliance" if cat == CONSEQUENCE_COMPLIANCE_BLOCKING else "maintenance_execution",
        "compliance_exposure": cat == CONSEQUENCE_COMPLIANCE_BLOCKING,
        "escalating": escalating,
        "backlog_compounding": status in ACTIVE_RISK_STATUSES,
        "estimated_impact": "high" if cat in (CONSEQUENCE_OPERATIONALLY_DANGEROUS, CONSEQUENCE_COMPLIANCE_BLOCKING) else "medium",
        "closure_likelihood": "low" if status == "active" else "medium",
    }


def classify_issue_consequence(issue: Dict[str, Any]) -> Dict[str, Any]:
    st = (issue.get("status") or "").lower()
    age = _days_old(issue.get("updated_at") or issue.get("created_at"))
    if st in ("closed", "cancelled", "resolved"):
        cat = CONSEQUENCE_INFORMATIONAL_ONLY
    elif st in ("triaged", "monitoring", "investigating") and age and age > 7:
        cat = CONSEQUENCE_STALE_OPERATIONAL_DEBT
    elif issue.get("recurrence_flag"):
        cat = CONSEQUENCE_RECURRING_DEGRADATION
    elif (issue.get("severity") or "").lower() in ("high", "critical"):
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    elif st == "ready_for_work_order":
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    else:
        cat = CONSEQUENCE_STALE_OPERATIONAL_DEBT if age and age > 14 else CONSEQUENCE_OPERATIONALLY_DANGEROUS
    return {
        "consequence_category": cat,
        "if_ignored": _if_ignored_message(cat, "issue"),
        "blocked_area": "work_order_creation" if st == "ready_for_work_order" else "triage",
        "compliance_exposure": False,
        "escalating": bool(age and age > 14),
        "backlog_compounding": st in OPEN_ISSUE_STATUSES,
        "estimated_impact": "high" if cat == CONSEQUENCE_STALE_OPERATIONAL_DEBT else "medium",
        "closure_likelihood": "high" if st in ("in_progress",) else "low" if st == "ready_for_work_order" else "medium",
    }


def classify_work_order_consequence(wo: Dict[str, Any]) -> Dict[str, Any]:
    st = (wo.get("status") or "").upper()
    hold = (wo.get("operational_exception") or "").upper()
    if st in ("CLOSED", "VERIFIED", "CANCELLED"):
        cat = CONSEQUENCE_INFORMATIONAL_ONLY
    elif hold == "NO_ACCESS":
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    elif st == "AWAITING_PARTS":
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    elif st in ("OPEN", "ASSIGNED", "SCHEDULED") and not wo.get("contractor_id"):
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    elif st == "COMPLETED" and not wo.get("verified_at"):
        cat = CONSEQUENCE_STALE_OPERATIONAL_DEBT
    elif (wo.get("work_order_kind") or "").upper() == "COMPLIANCE":
        cat = CONSEQUENCE_COMPLIANCE_BLOCKING
    else:
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    fake_progress = st == "COMPLETED" and not (wo.get("evidence_keys") or wo.get("evidence_count"))
    return {
        "consequence_category": cat,
        "if_ignored": _if_ignored_message(cat, "job"),
        "blocked_area": "contractor_assignment" if not wo.get("contractor_id") else "execution",
        "compliance_exposure": (wo.get("work_order_kind") or "").upper() == "COMPLIANCE",
        "escalating": (wo.get("reschedule_count") or 0) >= 2,
        "backlog_compounding": st in OPEN_WO_STATUSES,
        "estimated_impact": "high" if cat == CONSEQUENCE_OPERATIONALLY_DANGEROUS else "medium",
        "closure_likelihood": "high" if st == "VERIFIED" else "low" if fake_progress else "medium",
        "fake_progress_risk": fake_progress,
    }


def enrich_entity_operational_consequence(entity: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
    out = dict(entity)
    if entity_type == "risk_signal":
        out["operational_consequence"] = classify_risk_consequence(entity)
    elif entity_type == "issue":
        out["operational_consequence"] = classify_issue_consequence(entity)
    elif entity_type == "work_order":
        out["operational_consequence"] = classify_work_order_consequence(entity)
    return out


async def _load_inventory(client_id: str, property_id_filter: Optional[str] = None) -> Dict[str, Any]:
    db = database.get_db()
    q_client: Dict[str, Any] = {"client_id": client_id}
    q_prop: Dict[str, Any] = dict(q_client)
    if property_id_filter:
        q_prop["property_id"] = property_id_filter

    issues = await db.maintenance_issues.find(q_prop, {"_id": 0}).to_list(500)
    wos = await db.work_orders.find(q_prop, {"_id": 0}).to_list(500)
    risks = await db.risk_signals.find(q_prop, {"_id": 0}).to_list(500)

    return {"issues": issues, "work_orders": wos, "risk_signals": risks}


async def build_pressure_compression_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 2 — group raw pressure into landlord-meaningful clusters."""
    inv = await _load_inventory(client_id, property_id_filter)
    issues, wos, risks = inv["issues"], inv["work_orders"], inv["risk_signals"]

    groups: List[Dict[str, Any]] = []

    # Contractor deadlocks
    deadlock_wos = [
        w
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id")
    ]
    if deadlock_wos:
        props = len({w.get("property_id") for w in deadlock_wos if w.get("property_id")})
        groups.append(
            {
                "group_key": "contractor_deadlock",
                "headline": f"{len(deadlock_wos)} maintenance job{'s' if len(deadlock_wos)!=1 else ''} lack an assigned contractor",
                "detail": "Assignment deadlock blocks execution; backlog pressure compounds until a contractor is routed.",
                "consequence_category": CONSEQUENCE_OPERATIONALLY_DANGEROUS,
                "count": len(deadlock_wos),
                "affected_properties": props,
                "action_paths_available": 1,
                "unresolved_dependencies": len(deadlock_wos),
                "sample_ids": [w.get("work_order_id") for w in deadlock_wos[:5]],
            }
        )

    # Stale operational debt (issues)
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stale_issues = []
    for i in issues:
        st = (i.get("status") or "").lower()
        if st not in ("triaged", "monitoring", "investigating"):
            continue
        ts = _parse_dt(i.get("updated_at") or i.get("created_at"))
        if ts and ts < stale_cutoff:
            stale_issues.append(i)
    if stale_issues:
        groups.append(
            {
                "group_key": "stale_operational_debt",
                "headline": f"{len(stale_issues)} issue{'s' if len(stale_issues)!=1 else ''} stale in review (>7 days)",
                "detail": "Ageing triage debt increases cognitive load without closure progress.",
                "consequence_category": CONSEQUENCE_STALE_OPERATIONAL_DEBT,
                "count": len(stale_issues),
                "affected_properties": len({i.get("property_id") for i in stale_issues if i.get("property_id")}),
                "action_paths_available": 1,
                "unresolved_dependencies": len(stale_issues),
                "sample_ids": [i.get("issue_id") for i in stale_issues[:5]],
            }
        )

    # Completed-but-unverified (fake progress risk)
    stuck = [w for w in wos if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")]
    if stuck:
        groups.append(
            {
                "group_key": "completed_unverified",
                "headline": f"{len(stuck)} completed job{'s' if len(stuck)!=1 else ''} awaiting verification",
                "detail": "Completion without verification may be cosmetic progress — closure not yet authoritative.",
                "consequence_category": CONSEQUENCE_STALE_OPERATIONAL_DEBT,
                "count": len(stuck),
                "affected_properties": len({w.get("property_id") for w in stuck if w.get("property_id")}),
                "action_paths_available": 1,
                "unresolved_dependencies": len(stuck),
                "sample_ids": [w.get("work_order_id") for w in stuck[:5]],
            }
        )

    # Recurring risk clusters by type
    by_risk_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in risks:
        if (s.get("status") or "").lower() not in ACTIVE_RISK_STATUSES:
            continue
        rt = (s.get("risk_type") or "Unknown").strip()
        by_risk_type[rt].append(s)
    for rt, cluster in sorted(by_risk_type.items(), key=lambda x: -len(x[1])):
        if len(cluster) < 2:
            continue
        props = len({s.get("property_id") for s in cluster if s.get("property_id")})
        label = rt.replace(" Risk", "").strip() or rt
        groups.append(
            {
                "group_key": f"risk_cluster_{label.lower().replace(' ', '_')[:40]}",
                "headline": f"Recurring {label.lower()} risk affecting {props} propert{'ies' if props!=1 else 'y'}",
                "detail": f"{len(cluster)} active signals — compresses {len(cluster)} separate warnings into one decision path.",
                "consequence_category": CONSEQUENCE_RECURRING_DEGRADATION,
                "count": len(cluster),
                "affected_properties": props,
                "action_paths_available": 1,
                "unresolved_dependencies": len(cluster),
                "sample_ids": [s.get("signal_id") for s in cluster[:5]],
            }
        )

    # Resolved signals missing authority (fake progress)
    fake_resolved = [
        s for s in risks if (s.get("status") or "").lower() == "resolved" and not s.get("resolved_at")
    ]
    if fake_resolved:
        groups.append(
            {
                "group_key": "fake_progress_risk_signals",
                "headline": f"{len(fake_resolved)} resolved risk signal{'s' if len(fake_resolved)!=1 else ''} lack closure timestamps",
                "detail": "State shows resolved but operational replay cannot reconstruct when risk cleared.",
                "consequence_category": CONSEQUENCE_INFORMATIONAL_ONLY,
                "count": len(fake_resolved),
                "affected_properties": 0,
                "action_paths_available": 0,
                "unresolved_dependencies": len(fake_resolved),
                "sample_ids": [s.get("signal_id") for s in fake_resolved[:5]],
            }
        )

    raw_items = len(
        [s for s in risks if (s.get("status") or "").lower() in ACTIVE_RISK_STATUSES]
    ) + len([i for i in issues if (i.get("status") or "").lower() in OPEN_ISSUE_STATUSES]) + len(
        [w for w in wos if (w.get("status") or "").upper() in OPEN_WO_STATUSES]
    )
    compressed_items = len(groups)
    return {
        "groups": groups[:12],
        "compressed_from": {
            "raw_pressure_items": raw_items,
            "raw_active_risk_signals": len([s for s in risks if (s.get("status") or "").lower() in ACTIVE_RISK_STATUSES]),
            "raw_open_issues": len([i for i in issues if (i.get("status") or "").lower() in OPEN_ISSUE_STATUSES]),
            "raw_open_jobs": len([w for w in wos if (w.get("status") or "").upper() in OPEN_WO_STATUSES]),
        },
        "cognitive_load": {
            "estimated_raw_units": raw_items,
            "compressed_decision_units": max(compressed_items, 1),
            "compression_ratio": round(raw_items / max(compressed_items, 1), 1) if raw_items else 1.0,
        },
    }


async def build_operational_focus_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    compression: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Phase 3 — landlord-first guidance: what first, what is dangerous, what is fake progress."""
    inv = await _load_inventory(client_id, property_id_filter)
    compression = compression or await build_pressure_compression_v1(client_id, property_id_filter)
    issues, wos, risks = inv["issues"], inv["work_orders"], inv["risk_signals"]

    highest_impact: List[Dict[str, Any]] = []
    silently_dangerous: List[Dict[str, Any]] = []
    fake_progress: List[Dict[str, Any]] = []
    blockers: List[Dict[str, Any]] = []

    for g in compression.get("groups") or []:
        if g.get("consequence_category") == CONSEQUENCE_OPERATIONALLY_DANGEROUS:
            silently_dangerous.append(
                {"kind": g.get("group_key"), "headline": g.get("headline"), "detail": g.get("detail")}
            )
        if g.get("group_key") == "fake_progress_risk_signals":
            fake_progress.append({"kind": "risk_signals", "headline": g.get("headline"), "count": g.get("count")})
        if g.get("group_key") in ("contractor_deadlock", "completed_unverified"):
            blockers.append({"kind": g.get("group_key"), "headline": g.get("headline"), "count": g.get("count")})

    # Rank next actions from compression groups + top single items
    for g in (compression.get("groups") or [])[:5]:
        if g.get("group_key") == "fake_progress_risk_signals":
            continue
        highest_impact.append(
            {
                "priority": len(highest_impact) + 1,
                "headline": g.get("headline"),
                "why_first": g.get("detail"),
                "consequence_category": g.get("consequence_category"),
                "estimated_pressure_reduction": "high" if g.get("consequence_category") == CONSEQUENCE_OPERATIONALLY_DANGEROUS else "medium",
                "action_path": "/operations/work-orders" if "contractor" in (g.get("group_key") or "") else "/operations/issues",
            }
        )

    ready = [i for i in issues if (i.get("status") or "").lower() == "ready_for_work_order"]
    if ready and len(highest_impact) < 6:
        highest_impact.append(
            {
                "priority": len(highest_impact) + 1,
                "headline": f"{len(ready)} issues ready for job creation",
                "why_first": "Starting jobs converts triage into executable work — improves closure likelihood.",
                "consequence_category": CONSEQUENCE_OPERATIONALLY_DANGEROUS,
                "estimated_pressure_reduction": "medium",
                "action_path": "/operations/issues",
            }
        )

    what_first = (
        highest_impact[0]["headline"]
        if highest_impact
        else "No critical operational blockers detected in current inventory."
    )

    disclosures: List[str] = []
    if fake_progress:
        disclosures.append("Some items show resolved/completed state without authoritative closure timestamps.")
    if not silently_dangerous and not blockers:
        disclosures.append("Operational pressure is present but no critical deadlock clusters were detected.")

    return {
        "what_to_do_first": what_first,
        "highest_impact_next_actions": highest_impact[:8],
        "silently_dangerous": silently_dangerous[:6],
        "fake_progress_warnings": fake_progress,
        "operational_blockers": blockers,
        "unresolved_dependency_count": sum(g.get("unresolved_dependencies") or 0 for g in compression.get("groups") or []),
        "pressure_compression_ref": "pressure_compression_v1",
        "disclosures": disclosures,
        "cannot_reduce_pressure_yet": (
            [{"reason": "Historical resolved signals need authority backfill before dismiss outcomes are fully trusted."}]
            if fake_progress
            else []
        ),
    }


async def build_landlord_outcome_kpis_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 5 — measure operational improvement, not workflow activity."""
    inv = await _load_inventory(client_id, property_id_filter)
    issues, wos, risks = inv["issues"], inv["work_orders"], inv["risk_signals"]

    open_issues = [i for i in issues if (i.get("status") or "").lower() in OPEN_ISSUE_STATUSES]
    open_wos = [w for w in wos if (w.get("status") or "").upper() in OPEN_WO_STATUSES]
    stale = 0
    for i in issues:
        st = (i.get("status") or "").lower()
        if st in ("triaged", "monitoring", "investigating"):
            age = _days_old(i.get("updated_at") or i.get("created_at"))
            if age and age > 7:
                stale += 1

    deadlock = sum(
        1
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id")
    )
    completed_unverified = sum(
        1 for w in wos if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
    )
    verified = sum(1 for w in wos if (w.get("status") or "").upper() == "VERIFIED")
    completed = sum(1 for w in wos if (w.get("status") or "").upper() == "COMPLETED")
    closure_conversion = round(verified / max(completed + verified, 1), 2)

    active_risk = [s for s in risks if (s.get("status") or "").lower() in ACTIVE_RISK_STATUSES]
    resolved_no_ts = [s for s in risks if (s.get("status") or "").lower() == "resolved" and not s.get("resolved_at")]

    recurring_types: Dict[str, int] = defaultdict(int)
    for s in active_risk:
        rt = (s.get("risk_type") or "").lower()
        if "recurr" in rt or "repair" in rt:
            recurring_types[rt] += 1

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "backlog": {
            "open_issues": len(open_issues),
            "open_jobs": len(open_wos),
            "active_risk_signals": len(active_risk),
        },
        "deadlock_count": deadlock,
        "stale_review_count": stale,
        "completed_but_unverified_count": completed_unverified,
        "closure_conversion_rate": closure_conversion,
        "fake_progress": {
            "resolved_signals_missing_timestamp": len(resolved_no_ts),
            "completed_jobs_unverified": completed_unverified,
        },
        "recurring_risk_active_by_type": dict(recurring_types),
        "operational_pressure_trend": {
            "note": "Point-in-time snapshot; trend requires historical series.",
            "pressure_index": len(open_issues) + len(open_wos) + len(active_risk),
        },
        "ignored_alert_proxy": {
            "stale_issues_ratio": round(stale / max(len(open_issues), 1), 2),
        },
    }


async def build_operational_value_bundle_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Single bundle for Command Centre + Support alignment (Phase 6)."""
    compression, focus, kpis = await asyncio_gather_bundle(client_id, property_id_filter)
    return {
        "pressure_compression_v1": compression,
        "operational_focus_v1": focus,
        "landlord_outcome_kpis_v1": kpis,
        "programme": "OPERATIONAL-VALUE-COMPRESSION-01",
    }


async def asyncio_gather_bundle(client_id: str, property_id_filter: Optional[str]) -> Tuple[Dict, Dict, Dict]:
    import asyncio

    compression = await build_pressure_compression_v1(client_id, property_id_filter)
    focus, kpis = await asyncio.gather(
        build_operational_focus_v1(client_id, property_id_filter, compression=compression),
        build_landlord_outcome_kpis_v1(client_id, property_id_filter),
    )
    return compression, focus, kpis


def attach_consequence_to_priority_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """Phase 1 — enrich priority-stream row metadata."""
    at = str(action.get("action_type") or "")
    cat = CONSEQUENCE_COMPLIANCE_BLOCKING
    if "breach" in at or "overdue" in at:
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    elif "risk" in at:
        cat = CONSEQUENCE_RECURRING_DEGRADATION
    elif "issue" in at:
        cat = CONSEQUENCE_STALE_OPERATIONAL_DEBT
    elif "work_order" in at:
        cat = CONSEQUENCE_OPERATIONALLY_DANGEROUS
    out = dict(action)
    out["consequence_category"] = cat
    out["if_ignored"] = _if_ignored_message(cat, "item")
    return out
