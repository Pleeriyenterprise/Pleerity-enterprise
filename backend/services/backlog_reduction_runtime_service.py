"""
BACKLOG-REDUCTION-RUNTIME-01 — measurable backlog reduction, throughput tracking, pressure validation.

Proves operational guidance improves fleet state — not merely visibility.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.operational_closure_conversion_service import (
    build_closure_conversion_scores_v1,
    build_deadlock_reduction_v1,
    build_landlord_decision_confidence_v1,
    build_verification_throughput_v1,
    _days_old,
    _parse_dt,
)
from services.operational_value_compression_service import (
    ACTIVE_RISK_STATUSES,
    OPEN_ISSUE_STATUSES,
    OPEN_WO_STATUSES,
    load_operational_inventory,
)

logger = logging.getLogger(__name__)

PROGRAMME = "BACKLOG-REDUCTION-RUNTIME-01"

ASSIGNMENT_ESCALATION_DAYS = 7
ASSIGNMENT_CRITICAL_DAYS = 14
VERIFICATION_ESCALATION_DAYS = 7
VERIFICATION_CRITICAL_DAYS = 14


def _open_wo_status(st: str) -> bool:
    return (st or "").upper() in OPEN_WO_STATUSES


async def build_contractor_throughput_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 2 — assignment deadlock metrics and escalation surfacing."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]
    now = datetime.now(timezone.utc)

    unassigned: List[Dict[str, Any]] = []
    assigned_not_started: List[Dict[str, Any]] = []
    in_progress: List[Dict[str, Any]] = []
    conversion_samples: List[Dict[str, Any]] = []

    for w in wos:
        st = (w.get("status") or "").upper()
        if st in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id"):
            age = _days_old(w.get("created_at") or w.get("updated_at")) or 0
            tier = "critical" if age >= ASSIGNMENT_CRITICAL_DAYS else "escalated" if age >= ASSIGNMENT_ESCALATION_DAYS else "watch"
            unassigned.append(
                {
                    "work_order_id": w.get("work_order_id"),
                    "property_id": w.get("property_id"),
                    "status": st,
                    "assignment_age_days": round(age, 1),
                    "escalation_tier": tier,
                    "reschedule_count": w.get("reschedule_count") or 0,
                }
            )
        elif st in ("ASSIGNED", "SCHEDULED") and w.get("contractor_id"):
            assign_age = _days_old(w.get("assigned_at") or w.get("updated_at")) or 0
            if assign_age >= ASSIGNMENT_ESCALATION_DAYS and st != "IN_PROGRESS":
                assigned_not_started.append(
                    {
                        "work_order_id": w.get("work_order_id"),
                        "assignment_age_days": round(assign_age, 1),
                        "escalation_tier": "stalled_assignment",
                    }
                )
        elif st == "IN_PROGRESS":
            in_progress.append(w.get("work_order_id"))

        c_dt = _parse_dt(w.get("created_at"))
        a_dt = _parse_dt(w.get("assigned_at"))
        if w.get("contractor_id") and c_dt and a_dt and a_dt >= c_dt:
            open_to_assigned = (a_dt - c_dt).total_seconds() / 86400
            conversion_samples.append(
                {
                    "work_order_id": w.get("work_order_id"),
                    "open_to_assigned_days": round(open_to_assigned, 1),
                }
            )

    unassigned.sort(key=lambda x: -float(x.get("assignment_age_days") or 0))
    critical = [u for u in unassigned if u.get("escalation_tier") == "critical"]
    escalated = [u for u in unassigned if u.get("escalation_tier") == "escalated"]

    avg_open_to_assigned = (
        sum(c.get("open_to_assigned_days") or 0 for c in conversion_samples) / max(len(conversion_samples), 1)
    )

    return {
        "captured_at": now.isoformat(),
        "unassigned_count": len(unassigned),
        "critical_unassigned_count": len(critical),
        "escalated_unassigned_count": len(escalated),
        "stalled_assignment_count": len(assigned_not_started),
        "in_progress_count": len(in_progress),
        "assignment_momentum_index": round(
            len(in_progress) / max(len(unassigned) + len(in_progress), 1),
            2,
        ),
        "avg_open_to_assigned_days": round(avg_open_to_assigned, 1),
        "deadlock_recovery_rate": {
            "note": "Point-in-time; compare sessions after assignment interventions.",
            "unassigned_ratio": round(len(unassigned) / max(len([w for w in wos if _open_wo_status(w.get("status") or "")]), 1), 2),
        },
        "escalation_headline": (
            f"{len(critical)} jobs unassigned ≥{ASSIGNMENT_CRITICAL_DAYS} days — assignment throughput blocked"
            if critical
            else (
                f"{len(escalated)} jobs unassigned ≥{ASSIGNMENT_ESCALATION_DAYS} days"
                if escalated
                else None
            )
        ),
        "unassigned_sample": unassigned[:12],
        "stalled_assignment_sample": assigned_not_started[:8],
    }


async def build_verification_throughput_execution_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 3 — verification queue with ageing escalation and conversion metrics."""
    base = await build_verification_throughput_v1(client_id, property_id_filter)
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]

    escalated: List[Dict[str, Any]] = []
    critical: List[Dict[str, Any]] = []
    no_proof: List[Dict[str, Any]] = []

    for w in wos:
        if (w.get("status") or "").upper() != "COMPLETED" or w.get("verified_at"):
            continue
        age = _days_old(w.get("completed_at") or w.get("updated_at")) or 0
        has_evidence = bool(w.get("evidence_keys") or (w.get("evidence_count") or 0) > 0)
        row = {
            "work_order_id": w.get("work_order_id"),
            "verification_age_days": round(age, 1),
            "has_evidence": has_evidence,
            "priority_boost": 0,
        }
        if age >= VERIFICATION_CRITICAL_DAYS:
            row["escalation_tier"] = "critical"
            row["priority_boost"] = 12
            critical.append(row)
        elif age >= VERIFICATION_ESCALATION_DAYS:
            row["escalation_tier"] = "escalated"
            row["priority_boost"] = 6
            escalated.append(row)
        else:
            row["escalation_tier"] = "watch"
        if not has_evidence:
            no_proof.append(row)

    verified = base.get("verified_count") or 0
    completed_unverified = base.get("completed_without_verification_count") or 0
    total_terminal = verified + completed_unverified

    return {
        **base,
        "programme_phase": "verification_throughput_execution",
        "critical_verification_count": len(critical),
        "escalated_verification_count": len(escalated),
        "completed_without_proof_count": len(no_proof),
        "avg_verification_age_days": round(
            sum((b.get("verification_age_days") or 0) for b in (base.get("queue_sample") or []))
            / max(len(base.get("queue_sample") or []), 1),
            1,
        ),
        "verification_conversion_rate": base.get("verification_conversion_rate"),
        "unresolved_after_completion_trend": {
            "queue_count": completed_unverified,
            "over_sla": (base.get("sla_indicator") or {}).get("over_sla_count"),
        },
        "escalation_headline": (
            f"{len(critical)} completed jobs awaiting verification ≥{VERIFICATION_CRITICAL_DAYS} days"
            if critical
            else (
                f"{len(escalated)} completed jobs past verification SLA ({VERIFICATION_ESCALATION_DAYS}d)"
                if escalated
                else None
            )
        ),
        "priority_queue_sample": sorted(
            critical + escalated + (base.get("queue_sample") or [])[:6],
            key=lambda x: -float(x.get("verification_age_days") or x.get("priority_boost") or 0),
        )[:12],
    }


async def build_pressure_reduction_validation_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 4 — map focus recommendations to measurable closure impact."""
    from services.operational_value_compression_service import build_operational_focus_v1, build_pressure_compression_v1

    compression = await build_pressure_compression_v1(client_id, property_id_filter)
    focus = await build_operational_focus_v1(client_id, property_id_filter, compression=compression)
    contractor = await build_contractor_throughput_v1(client_id, property_id_filter)
    verification = await build_verification_throughput_execution_v1(client_id, property_id_filter)
    deadlock = await build_deadlock_reduction_v1(client_id, property_id_filter)

    recommendations: List[Dict[str, Any]] = []
    primary = focus.get("what_to_do_first")
    if primary:
        impact_units = 0
        weak = False
        if "contractor" in primary.lower():
            impact_units = contractor.get("unassigned_count") or 0
            weak = impact_units == 0
        elif "verif" in primary.lower():
            impact_units = verification.get("verification_queue_count") or 0
            weak = impact_units == 0
        else:
            impact_units = deadlock.get("total_deadlock_units") or 0
        recommendations.append(
            {
                "recommendation": primary,
                "estimated_pressure_units": impact_units,
                "closure_impact": "high" if impact_units >= 5 else "medium" if impact_units else "low",
                "weak_closure_impact": weak,
            }
        )

    stagnant_groups = []
    for g in compression.get("groups") or []:
        key = g.get("group_key") or ""
        if key == "contractor_deadlock" and (contractor.get("unassigned_count") or 0) > 10:
            stagnant_groups.append({"group_key": key, "reason": "high_count_persistent_assignment_deadlock"})
        if key == "verification_backlog" and (verification.get("verification_queue_count") or 0) > 5:
            stagnant_groups.append({"group_key": key, "reason": "verification_queue_not_draining"})

    return {
        "primary_recommendation_validation": recommendations,
        "stagnant_compression_groups": stagnant_groups,
        "guidance_improves_reality_when": [
            "Assign contractor on escalated unassigned jobs",
            "Verify completed jobs with evidence attached",
            "Break stale triage loops with job start or close",
        ],
    }


async def build_operational_momentum_validation_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    baseline: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Phase 5 — trend deltas when baseline snapshot supplied."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    scores = await build_closure_conversion_scores_v1(client_id, property_id_filter)
    confidence = await build_landlord_decision_confidence_v1(client_id, property_id_filter)
    contractor = await build_contractor_throughput_v1(client_id, property_id_filter)
    verification = await build_verification_throughput_execution_v1(client_id, property_id_filter)

    issues, wos, risks = inv["issues"], inv["work_orders"], inv["risk_signals"]
    open_units = len([i for i in issues if (i.get("status") or "").lower() in OPEN_ISSUE_STATUSES]) + len(
        [w for w in wos if _open_wo_status(w.get("status") or "")]
    )
    fake_progress = scores.get("fake_progress_chain_count") or 0
    resolved_missing_ts = sum(
        1 for s in risks if (s.get("status") or "").lower() == "resolved" and not s.get("resolved_at")
    )

    current = {
        "open_operational_units": open_units,
        "unassigned_jobs": contractor.get("unassigned_count"),
        "verification_queue": verification.get("verification_queue_count"),
        "fake_progress_chains": fake_progress,
        "resolved_missing_resolved_at": resolved_missing_ts,
        "likely_to_stall": scores.get("likely_to_stall_count"),
        "decision_confidence": confidence.get("decision_confidence_score"),
        "portfolio_assignment_momentum": contractor.get("assignment_momentum_index"),
        "verification_conversion_rate": verification.get("verification_conversion_rate"),
    }

    deltas: Dict[str, Any] = {}
    if baseline:
        for k, v in current.items():
            b = baseline.get(k)
            if isinstance(v, (int, float)) and isinstance(b, (int, float)):
                deltas[k] = round(float(v) - float(b), 2)

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "current": current,
        "deltas_vs_baseline": deltas if baseline else None,
        "pressure_reduction_velocity": {
            "open_units": open_units,
            "note": "Negative delta vs baseline indicates backlog shrinkage.",
        },
    }


async def build_staging_simulation_coverage_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 6 — detect real operational entropy patterns in fleet (read-only audit)."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos, issues = inv["work_orders"], inv["issues"]

    scenarios: Dict[str, Any] = {}

    no_access = [
        w
        for w in wos
        if (w.get("operational_exception") or w.get("operational_hold") or "").upper() == "NO_ACCESS"
    ]
    scenarios["no_access_loops"] = {"count": len(no_access), "present": len(no_access) > 0}

    awaiting_parts = [w for w in wos if (w.get("status") or "").upper() == "AWAITING_PARTS"]
    scenarios["awaiting_parts_loops"] = {"count": len(awaiting_parts), "present": len(awaiting_parts) > 0}

    reschedule_chains = [w for w in wos if (w.get("reschedule_count") or 0) >= 2]
    scenarios["repeated_reschedule_chains"] = {"count": len(reschedule_chains), "present": len(reschedule_chains) > 0}

    abandoned = [
        w
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED")
        and not w.get("contractor_id")
        and (_days_old(w.get("updated_at")) or 0) >= ASSIGNMENT_CRITICAL_DAYS
    ]
    scenarios["contractor_abandonment"] = {"count": len(abandoned), "present": len(abandoned) > 0}

    evidence_backlog = [
        w
        for w in wos
        if (w.get("status") or "").upper() == "COMPLETED"
        and not (w.get("evidence_keys") or (w.get("evidence_count") or 0) > 0)
    ]
    scenarios["evidence_backlog"] = {"count": len(evidence_backlog), "present": len(evidence_backlog) > 0}

    verification_backlog = [
        w for w in wos if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
    ]
    scenarios["verification_backlog"] = {"count": len(verification_backlog), "present": len(verification_backlog) > 0}

    stale_review = [
        i
        for i in issues
        if (i.get("status") or "").lower() in ("triaged", "monitoring", "investigating")
        and (_days_old(i.get("updated_at")) or 0) > 7
    ]
    scenarios["stale_review_escalation"] = {"count": len(stale_review), "present": len(stale_review) > 0}

    covered = sum(1 for s in scenarios.values() if s.get("present"))
    return {
        "scenarios": scenarios,
        "coverage_count": covered,
        "coverage_total": len(scenarios),
        "entropy_coverage_ratio": round(covered / max(len(scenarios), 1), 2),
    }


async def build_backlog_reduction_bundle_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    momentum_baseline: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    import asyncio

    contractor, verification, pressure, momentum, simulation = await asyncio.gather(
        build_contractor_throughput_v1(client_id, property_id_filter),
        build_verification_throughput_execution_v1(client_id, property_id_filter),
        build_pressure_reduction_validation_v1(client_id, property_id_filter),
        build_operational_momentum_validation_v1(client_id, property_id_filter, baseline=momentum_baseline),
        build_staging_simulation_coverage_v1(client_id, property_id_filter),
    )
    return {
        "programme": PROGRAMME,
        "contractor_throughput_v1": contractor,
        "verification_throughput_execution_v1": verification,
        "pressure_reduction_validation_v1": pressure,
        "operational_momentum_validation_v1": momentum,
        "staging_simulation_coverage_v1": simulation,
        "top_backlog_action": contractor.get("escalation_headline")
        or verification.get("escalation_headline")
        or "Review operational focus for highest-leverage backlog reduction",
    }
