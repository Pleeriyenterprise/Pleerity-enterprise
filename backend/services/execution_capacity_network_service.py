"""
EXECUTION-CAPACITY-AND-NETWORK-RELIABILITY-01

Execution supply-side orchestration: contractor coverage, assignment conversion,
quote throughput, recovery paths, and execution-capacity KPIs.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.operational_closure_conversion_service import _days_old, _parse_dt
from services.operational_value_compression_service import load_operational_inventory

logger = logging.getLogger(__name__)

PROGRAMME = "EXECUTION-CAPACITY-AND-NETWORK-RELIABILITY-01"

AUDIT_JOB_CAP = 28
ASSIGNMENT_ESCALATION_DAYS = 7
ASSIGNMENT_CRITICAL_DAYS = 14
QUOTE_ESCALATION_DAYS = 3
QUOTE_CRITICAL_DAYS = 7


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _primary_failure_reason(diag: Dict[str, Any], routing: Optional[Dict[str, Any]] = None) -> str:
    if routing and routing.get("no_eligible_contractors"):
        eligible = diag.get("eligible") or 0
        if eligible == 0:
            exclusions = [
                ("postcode_mismatch", diag.get("excluded_location_postcode") or 0),
                ("trade_mismatch", diag.get("excluded_maintenance_trade") or 0),
                ("not_assignment_ready", diag.get("excluded_not_assignment_ready") or 0),
                ("execution_capability", diag.get("excluded_execution_capability") or 0),
                ("jurisdiction", diag.get("excluded_service_region_jurisdiction") or 0),
                ("property_scope", diag.get("excluded_property_scope") or 0),
            ]
            exclusions.sort(key=lambda x: -x[1])
            if exclusions[0][1] > 0:
                return f"no_coverage:{exclusions[0][0]}"
            return "no_coverage:contractor_pool_exhausted"
    if (diag.get("eligible") or 0) > 0:
        return "eligible_contractors_exist_unassigned"
    return "unknown_assignment_blocker"


def _coverage_class(eligible: int, visible: int) -> str:
    if eligible >= 2:
        return "healthy_coverage"
    if eligible == 1:
        return "fragile_coverage"
    if visible > 0:
        return "fragile_coverage"
    return "no_coverage"


async def build_contractor_network_audit_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    audit_cache: Optional[Any] = None,
) -> Dict[str, Any]:
    """Phase 1 — per-job coverage diagnostics and failure taxonomy."""
    from services import contractor_service

    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]
    db = None
    try:
        from database import database

        db = database.get_db()
    except Exception:
        db = None

    unassigned = [
        w
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED")
        and not w.get("contractor_id")
        and (w.get("work_order_kind") or "MAINTENANCE").upper() != "COMPLIANCE"
    ]
    unassigned.sort(key=lambda w: -(_days_old(w.get("updated_at") or w.get("created_at")) or 0))

    job_audits: List[Dict[str, Any]] = []
    failure_counts: Dict[str, int] = defaultdict(int)
    coverage_counts: Dict[str, int] = defaultdict(int)
    postcode_zones: Dict[str, int] = defaultdict(int)

    for w in unassigned[:AUDIT_JOB_CAP]:
        wid = w.get("work_order_id")
        if not wid:
            continue
        if audit_cache is not None:
            assignable = await audit_cache.get_assignable(
                contractor_service,
                client_id,
                wid,
                limit=5,
            )
        else:
            assignable = await contractor_service.list_assignable_contractors_for_work_order(
                client_id, wid, limit=5
            )
        diag = assignable.get("filter_diagnostics") or {}
        if audit_cache is not None:
            rec = await audit_cache.get_recommendation(
                contractor_service,
                wid,
                client_id=client_id,
                limit=3,
            )
        else:
            rec = await contractor_service.recommend_contractors_for_work_order(wid, client_id=client_id, limit=3)
        routing = rec.get("routing") or {}

        reason = _primary_failure_reason(diag, routing)
        failure_counts[reason] += 1
        cov = _coverage_class(diag.get("eligible") or 0, diag.get("visible_in_directory") or 0)
        coverage_counts[cov] += 1

        prop_id = w.get("property_id")
        pc = None
        if db is not None and prop_id:
            prop = await db.properties.find_one(
                {"property_id": prop_id, "client_id": client_id},
                {"_id": 0, "postcode": 1},
            )
            pc = (prop or {}).get("postcode")
        if pc:
            postcode_zones[str(pc)[:4].upper()] = postcode_zones.get(str(pc)[:4].upper(), 0) + 1

        age = _days_old(w.get("updated_at") or w.get("created_at")) or 0
        job_audits.append(
            {
                "work_order_id": wid,
                "property_id": prop_id,
                "postcode_prefix": str(pc)[:4].upper() if pc else None,
                "category": w.get("category"),
                "status": w.get("status"),
                "assignment_age_days": round(age, 1),
                "coverage_class": cov,
                "primary_failure_reason": reason,
                "eligible_contractors": diag.get("eligible"),
                "filter_diagnostics": diag,
                "routing_flags": {
                    "no_eligible_contractors": routing.get("no_eligible_contractors"),
                    "sla_breached": (routing.get("flags") or {}).get("sla_breached"),
                },
            }
        )

    unsupported_zones = [
        {"postcode_prefix": k, "unassigned_jobs": v}
        for k, v in sorted(postcode_zones.items(), key=lambda x: -x[1])
        if v >= 2
    ]

    risk_matrix = []
    if coverage_counts.get("no_coverage", 0) >= 5:
        risk_matrix.append(
            {
                "risk": "execution_network_failure",
                "severity": "critical",
                "detail": f"{coverage_counts.get('no_coverage', 0)} jobs have zero eligible contractors",
            }
        )
    if failure_counts.get("no_coverage:postcode_mismatch", 0) + failure_counts.get("no_coverage:trade_mismatch", 0) >= 3:
        risk_matrix.append(
            {
                "risk": "geographic_or_trade_gap",
                "severity": "high",
                "detail": "Postcode or trade filtering excludes all contractors for multiple jobs",
            }
        )

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "unassigned_jobs_audited": len(job_audits),
        "unassigned_jobs_total": len(unassigned),
        "assignment_failure_taxonomy": dict(sorted(failure_counts.items(), key=lambda x: -x[1])),
        "coverage_distribution": dict(coverage_counts),
        "unsupported_operational_zones": unsupported_zones[:12],
        "execution_capacity_risk_matrix": risk_matrix,
        "job_sample": job_audits[:15],
        "contractor_coverage_map_summary": {
            "healthy": coverage_counts.get("healthy_coverage", 0),
            "fragile": coverage_counts.get("fragile_coverage", 0),
            "no_coverage": coverage_counts.get("no_coverage", 0),
        },
    }


async def build_assignment_conversion_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 2 — assignment funnel and reliability scoring."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]

    open_unassigned = 0
    assigned_not_accepted = 0
    in_progress = 0
    verified_terminal = 0
    reassignment_loops = 0
    stale_assignments = 0
    conversion_samples: List[float] = []

    for w in wos:
        st = (w.get("status") or "").upper()
        if st in ("OPEN",) and not w.get("contractor_id"):
            open_unassigned += 1
        elif st in ("ASSIGNED", "SCHEDULED") and w.get("contractor_id"):
            aa = _days_old(w.get("assigned_at")) or 0
            if not w.get("accepted_at") and aa > ASSIGNMENT_ESCALATION_DAYS:
                assigned_not_accepted += 1
            if aa >= ASSIGNMENT_CRITICAL_DAYS and st != "IN_PROGRESS":
                stale_assignments += 1
            c_dt = _parse_dt(w.get("created_at"))
            a_dt = _parse_dt(w.get("assigned_at"))
            if c_dt and a_dt:
                conversion_samples.append((a_dt - c_dt).total_seconds() / 86400)
        elif st == "IN_PROGRESS":
            in_progress += 1
        elif st == "VERIFIED":
            verified_terminal += 1
        if (w.get("reschedule_count") or 0) >= 2:
            reassignment_loops += 1

    ever_open = open_unassigned + assigned_not_accepted + in_progress + verified_terminal
    assigned_pool = len([w for w in wos if w.get("contractor_id")])
    assignment_conversion_rate = round(assigned_pool / max(ever_open + open_unassigned, 1), 2)

    avg_open_to_assigned = (
        sum(conversion_samples) / max(len(conversion_samples), 1) if conversion_samples else None
    )

    reliability_score = _clamp01(
        0.35
        + 0.25 * assignment_conversion_rate
        + 0.2 * min(1.0, in_progress / max(assigned_pool, 1))
        - min(0.3, open_unassigned / 40.0)
        - min(0.2, stale_assignments / 20.0)
    )

    return {
        "open_unassigned_count": open_unassigned,
        "assigned_pending_acceptance": assigned_not_accepted,
        "in_progress_count": in_progress,
        "verified_count": verified_terminal,
        "assignment_conversion_rate": assignment_conversion_rate,
        "avg_open_to_assigned_days": round(avg_open_to_assigned, 1) if avg_open_to_assigned is not None else None,
        "stale_assignment_count": stale_assignments,
        "reassignment_loop_count": reassignment_loops,
        "contractor_reliability_score": round(reliability_score, 2),
        "assignment_momentum_score": round(_clamp01(in_progress / max(open_unassigned + in_progress, 1)), 2),
        "escalation_headline": (
            f"{stale_assignments} assignments stale ≥{ASSIGNMENT_CRITICAL_DAYS}d without progress"
            if stale_assignments
            else None
        ),
    }


async def build_execution_recovery_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    network_audit: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Phase 3 — distinguish workflow vs execution-capacity blockage; recovery guidance."""
    audit = network_audit or await build_contractor_network_audit_v1(client_id, property_id_filter)
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]

    recovery_actions: List[Dict[str, Any]] = []
    no_cov = audit.get("coverage_distribution", {}).get("no_coverage", 0)
    if no_cov >= 3:
        recovery_actions.append(
            {
                "recovery_type": "expand_contractor_network",
                "headline": f"{no_cov} jobs blocked by execution-capacity (no eligible contractors)",
                "recommended_action": "Onboard or approve contractors for affected postcodes and trades",
                "blockage_class": "execution_capacity_blockage",
            }
        )

    quote_blocked = [
        w
        for w in wos
        if w.get("contractor_id")
        and (w.get("price_status") or "").upper() in ("AWAITING_QUOTE", "QUOTED", "REJECTED", "REVISION_REQUESTED")
        and (w.get("status") or "").upper() in ("ASSIGNED", "SCHEDULED", "OPEN")
    ]
    if quote_blocked:
        recovery_actions.append(
            {
                "recovery_type": "quote_throughput",
                "headline": f"{len(quote_blocked)} assigned jobs waiting on quote or approval",
                "recommended_action": "Chase contractor quote submission or approve pending quotes",
                "blockage_class": "quote_governance_blockage",
            }
        )

    zones = audit.get("unsupported_operational_zones") or []
    for z in zones[:3]:
        recovery_actions.append(
            {
                "recovery_type": "geographic_fallback",
                "headline": f"Postcode area {z.get('postcode_prefix')} has {z.get('unassigned_jobs')} unassigned jobs",
                "recommended_action": "Add contractors covering this postcode or request admin routing assistance",
                "blockage_class": "execution_capacity_blockage",
            }
        )

    return {
        "workflow_blockage_vs_execution_capacity": {
            "execution_capacity_dominant": no_cov >= (audit.get("unassigned_jobs_total") or 0) // 2,
            "quote_governance_secondary": len(quote_blocked) >= 3,
        },
        "recovery_actions": recovery_actions[:8],
        "truth_surface": (
            "Blocked by contractor availability — not a workflow state issue"
            if no_cov >= 5
            else "Mixed workflow and execution-capacity constraints"
        ),
        "manual_intervention_guidance": [
            "Use admin contractor approval for vetted trades in unsupported postcodes",
            "Confirm alternate contractor when recommendation pool is empty",
            "Approve quotes to unlock IN_PROGRESS for pre-quote maintenance jobs",
        ],
    }


async def build_quote_throughput_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 4 — quote funnel without weakening governance."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = [
        w
        for w in inv["work_orders"]
        if (w.get("pricing_mode") or "").upper() == "MAINTENANCE_PREQUOTE"
        or (w.get("price_status") or "").strip()
    ]

    awaiting = quoted = approved = rejected = 0
    deadlocks: List[Dict[str, Any]] = []
    for w in wos:
        ps = (w.get("price_status") or "").upper()
        if ps == "AWAITING_QUOTE":
            awaiting += 1
            age = _days_old(w.get("assigned_at") or w.get("updated_at")) or 0
            if age >= QUOTE_ESCALATION_DAYS:
                deadlocks.append(
                    {
                        "work_order_id": w.get("work_order_id"),
                        "quote_state": ps,
                        "age_days": round(age, 1),
                        "escalation": "critical" if age >= QUOTE_CRITICAL_DAYS else "escalated",
                    }
                )
        elif ps == "QUOTED":
            quoted += 1
            age = _days_old(w.get("quote_submitted_at")) or 0
            if age >= QUOTE_ESCALATION_DAYS:
                deadlocks.append(
                    {
                        "work_order_id": w.get("work_order_id"),
                        "quote_state": ps,
                        "age_days": round(age, 1),
                        "escalation": "approval_stalled",
                    }
                )
        elif ps == "APPROVED":
            approved += 1
        elif ps == "REJECTED":
            rejected += 1

    request_base = awaiting + quoted + approved + rejected
    return {
        "awaiting_quote_count": awaiting,
        "quoted_pending_approval_count": quoted,
        "approved_quote_count": approved,
        "rejected_quote_count": rejected,
        "request_to_quote_conversion": round((quoted + approved) / max(request_base, 1), 2),
        "quote_to_approval_conversion": round(approved / max(quoted + approved, 1), 2),
        "approval_to_execution_proxy": round(
            len([w for w in wos if (w.get("status") or "").upper() == "IN_PROGRESS" and (w.get("price_status") or "").upper() == "APPROVED"])
            / max(approved, 1),
            2,
        ),
        "quote_deadlocks": deadlocks[:12],
        "quote_turnaround_score": round(_clamp01(approved / max(awaiting + quoted + 1, 1)), 2),
    }


async def build_execution_momentum_kpis_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    network_audit: Optional[Dict[str, Any]] = None,
    assignment: Optional[Dict[str, Any]] = None,
    quote: Optional[Dict[str, Any]] = None,
    audit_cache: Optional[Any] = None,
) -> Dict[str, Any]:
    """Phase 5 — execution-capacity confidence and velocity."""
    audit = network_audit or await build_contractor_network_audit_v1(
        client_id,
        property_id_filter,
        audit_cache=audit_cache,
    )
    assignment = assignment or await build_assignment_conversion_v1(client_id, property_id_filter)
    quote = quote or await build_quote_throughput_v1(client_id, property_id_filter)

    total_unassigned = audit.get("unassigned_jobs_total") or 0
    no_cov = audit.get("coverage_distribution", {}).get("no_coverage", 0)
    unsupported_ratio = round(no_cov / max(total_unassigned, 1), 2)

    coverage_score = round(
        _clamp01(
            1.0
            - unsupported_ratio * 0.7
            - min(0.3, (assignment.get("open_unassigned_count") or 0) / 35.0)
        ),
        2,
    )

    execution_capacity_confidence = round(
        _clamp01(
            coverage_score * 0.45
            + (assignment.get("contractor_reliability_score") or 0) * 0.35
            + (quote.get("quote_turnaround_score") or 0) * 0.2
        ),
        2,
    )

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "contractor_coverage_score": coverage_score,
        "assignment_conversion_rate": assignment.get("assignment_conversion_rate"),
        "execution_responsiveness_score": assignment.get("assignment_momentum_score"),
        "quote_turnaround_score": quote.get("quote_turnaround_score"),
        "execution_capacity_confidence": execution_capacity_confidence,
        "unsupported_job_ratio": unsupported_ratio,
        "contractor_deadlock_trend": {
            "open_unassigned": assignment.get("open_unassigned_count"),
            "no_coverage_jobs": no_cov,
        },
        "execution_recovery_rate": {
            "note": "Compare sessions after contractor onboarding or assignment interventions",
            "recovery_actions_available": True,
        },
        "operational_execution_velocity": {
            "in_progress": assignment.get("in_progress_count"),
            "verified": assignment.get("verified_count"),
        },
    }


async def build_execution_entropy_coverage_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 6 — detect realistic execution failure patterns (read-only)."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]

    scenarios: Dict[str, Any] = {}

    scenarios["contractor_ghosting"] = {
        "count": sum(
            1
            for w in wos
            if w.get("contractor_id")
            and not w.get("accepted_at")
            and (_days_old(w.get("assigned_at")) or 0) > ASSIGNMENT_ESCALATION_DAYS
        ),
        "present": False,
    }
    scenarios["contractor_ghosting"]["present"] = scenarios["contractor_ghosting"]["count"] > 0

    scenarios["unsupported_postcode"] = {
        "count": 0,
        "present": False,
    }

    scenarios["delayed_quote_response"] = {
        "count": sum(
            1
            for w in wos
            if (w.get("price_status") or "").upper() == "AWAITING_QUOTE"
            and (_days_old(w.get("assigned_at")) or 0) > QUOTE_ESCALATION_DAYS
        ),
        "present": False,
    }
    scenarios["delayed_quote_response"]["present"] = scenarios["delayed_quote_response"]["count"] > 0

    scenarios["quote_approval_stall"] = {
        "count": sum(
            1
            for w in wos
            if (w.get("price_status") or "").upper() == "QUOTED"
            and (_days_old(w.get("quote_submitted_at")) or 0) > QUOTE_ESCALATION_DAYS
        ),
        "present": False,
    }
    scenarios["quote_approval_stall"]["present"] = scenarios["quote_approval_stall"]["count"] > 0

    scenarios["reassignment_loops"] = {
        "count": sum(1 for w in wos if (w.get("reschedule_count") or 0) >= 2),
        "present": False,
    }
    scenarios["reassignment_loops"]["present"] = scenarios["reassignment_loops"]["count"] > 0

    scenarios["exhausted_contractor_pool"] = {"count": 0, "present": False}

    scenarios["execution_abandonment"] = {
        "count": sum(
            1
            for w in wos
            if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED")
            and not w.get("contractor_id")
            and (_days_old(w.get("updated_at")) or 0) > ASSIGNMENT_CRITICAL_DAYS
        ),
        "present": False,
    }
    scenarios["execution_abandonment"]["present"] = scenarios["execution_abandonment"]["count"] > 0

    covered = sum(1 for s in scenarios.values() if s.get("present"))

    return {
        "scenarios": scenarios,
        "coverage_count": covered,
        "coverage_total": len(scenarios),
        "entropy_coverage_ratio": round(covered / max(len(scenarios), 1), 2),
    }


async def fetch_execution_capacity_priority_actions(
    client_id: str,
    property_id_filter: Optional[str] = None,
    limit: int = 6,
    *,
    recovery: Optional[Dict[str, Any]] = None,
    network_audit: Optional[Dict[str, Any]] = None,
    audit_cache: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """High-leverage execution-capacity actions for Command Centre."""
    from services.client_priority_stream import _action

    recovery = recovery or await build_execution_recovery_v1(
        client_id,
        property_id_filter,
        network_audit=network_audit,
    )
    actions: List[Dict[str, Any]] = []
    for i, r in enumerate(recovery.get("recovery_actions") or []):
        score = 88 - i * 2
        actions.append(
            _action(
                "execution_capacity_recovery",
                r.get("headline", "Execution capacity recovery"),
                r.get("recommended_action", ""),
                score,
                "high",
                why_matters=r.get("truth_surface") or "Execution supply must exist before workflow progress converts to closure.",
                recommended_action_detail=r.get("recommended_action"),
                recommended_url="/operations/work-orders",
                recommended_action_label="Resolve execution block",
            )
        )
    actions.sort(key=lambda a: -(a.get("priority") or 0))
    return actions[:limit]


def merge_execution_with_momentum_actions(
    execution: List[Dict[str, Any]],
    momentum: List[Dict[str, Any]],
    *,
    cap: int = 22,
) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for a in execution + momentum:
        key = a.get("title") or a.get("related_work_order_id")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(a)
    out.sort(key=lambda x: -(x.get("priority") or 0))
    return out[:cap]


async def build_execution_capacity_bundle_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    audit_cache: Optional[Any] = None,
) -> Dict[str, Any]:
    import asyncio

    network_audit = await build_contractor_network_audit_v1(
        client_id,
        property_id_filter,
        audit_cache=audit_cache,
    )
    assignment, quote = await asyncio.gather(
        build_assignment_conversion_v1(client_id, property_id_filter),
        build_quote_throughput_v1(client_id, property_id_filter),
    )
    recovery, kpis, entropy = await asyncio.gather(
        build_execution_recovery_v1(client_id, property_id_filter, network_audit=network_audit),
        build_execution_momentum_kpis_v1(
            client_id,
            property_id_filter,
            network_audit=network_audit,
            assignment=assignment,
            quote=quote,
            audit_cache=audit_cache,
        ),
        build_execution_entropy_coverage_v1(client_id, property_id_filter),
    )
    priority_actions = await fetch_execution_capacity_priority_actions(
        client_id,
        property_id_filter,
        recovery=recovery,
        network_audit=network_audit,
        audit_cache=audit_cache,
    )
    return {
        "programme": PROGRAMME,
        "contractor_network_audit_v1": network_audit,
        "assignment_conversion_v1": assignment,
        "quote_throughput_v1": quote,
        "execution_recovery_v1": recovery,
        "execution_momentum_kpis_v1": kpis,
        "execution_entropy_coverage_v1": entropy,
        "execution_capacity_priority_actions": priority_actions,
        "primary_execution_bottleneck": (
            (recovery.get("recovery_actions") or [{}])[0].get("headline")
            if recovery.get("recovery_actions")
            else "Review contractor network coverage"
        ),
    }
