"""
OPERATIONAL-CLOSURE-CONVERSION-01 — closure scoring, deadlock reduction, momentum prioritisation.

Optimises for pressure reduction and trustworthy closure acceleration, not state movement.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from services.operational_value_compression_service import (
    ACTIVE_RISK_STATUSES,
    OPEN_ISSUE_STATUSES,
    OPEN_WO_STATUSES,
    load_operational_inventory,
)

logger = logging.getLogger(__name__)

PROGRAMME = "OPERATIONAL-CLOSURE-CONVERSION-01"

# Momentum priority action types (Phase 3)
ACTION_CLOSURE_CONTRACTOR_DEADLOCK = "closure_contractor_deadlock"
ACTION_CLOSURE_VERIFICATION_BACKLOG = "closure_verification_backlog"
ACTION_CLOSURE_STALE_ISSUE = "closure_stale_issue"
ACTION_CLOSURE_START_JOB = "closure_start_job"
ACTION_CLOSURE_EVIDENCE_GAP = "closure_evidence_gap"

SCORE_CONTRACTOR_DEADLOCK = 92
SCORE_VERIFICATION_BACKLOG = 90
SCORE_STALE_ISSUE = 86
SCORE_START_JOB = 84
SCORE_EVIDENCE_GAP = 82


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


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_issue_closure(issue: Dict[str, Any], linked_wo: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    st = (issue.get("status") or "").lower()
    age = _days_old(issue.get("updated_at") or issue.get("created_at")) or 0.0
    deps = 0
    blockers: List[str] = []
    if st == "ready_for_work_order":
        deps = 0 if linked_wo else 1
        if not linked_wo:
            blockers.append("no_linked_job")
    elif st in ("triaged", "monitoring", "investigating"):
        if age > 7:
            blockers.append("stale_triage_loop")
        deps = 1
    elif st == "in_progress":
        deps = 0 if linked_wo and linked_wo.get("contractor_id") else 1
        if deps:
            blockers.append("job_unassigned_or_missing")
    if st in ("closed", "cancelled", "resolved"):
        likelihood = 1.0
        momentum = 0.95
    elif st == "ready_for_work_order":
        likelihood = 0.72 if not linked_wo else 0.55
        momentum = 0.78 - min(0.25, age / 21.0)
    elif st == "in_progress":
        likelihood = 0.65 if linked_wo else 0.4
        momentum = 0.62 - min(0.3, age / 14.0)
    else:
        likelihood = 0.35
        momentum = 0.28 - min(0.2, age / 14.0)
    momentum = _clamp01(momentum)
    likelihood = _clamp01(likelihood)
    return {
        "entity_type": "issue",
        "entity_id": issue.get("issue_id"),
        "closure_likelihood": round(likelihood, 2),
        "operational_momentum_score": round(momentum, 2),
        "stalled_duration_days": round(age, 1),
        "dependency_count": deps,
        "closure_blockers": blockers,
        "likely_to_stall": momentum < 0.35 and st in OPEN_ISSUE_STATUSES,
        "fake_progress_risk": False,
        "verification_blockage": False,
        "contractor_responsive": bool(linked_wo and linked_wo.get("contractor_id")),
    }


def score_work_order_closure(wo: Dict[str, Any]) -> Dict[str, Any]:
    st = (wo.get("status") or "").upper()
    age = _days_old(wo.get("updated_at") or wo.get("assigned_at") or wo.get("created_at")) or 0.0
    completed_age = _days_old(wo.get("completed_at")) or 0.0
    blockers: List[str] = []
    deps = 0
    has_evidence = bool(wo.get("evidence_keys") or (wo.get("evidence_count") or 0) > 0)
    has_contractor = bool(wo.get("contractor_id"))

    if st in ("OPEN", "ASSIGNED", "SCHEDULED") and not has_contractor:
        blockers.append("contractor_deadlock")
        deps += 1
    if st == "COMPLETED" and not wo.get("verified_at"):
        blockers.append("verification_backlog")
        deps += 1
    if st == "COMPLETED" and not has_evidence and (wo.get("work_order_kind") or "").upper() == "COMPLIANCE":
        blockers.append("evidence_dependency")
        deps += 1
    if (wo.get("reschedule_count") or 0) >= 2:
        blockers.append("repeated_reschedule")
        deps += 1
    if st == "AWAITING_PARTS":
        blockers.append("awaiting_parts")

    fake_progress = st == "COMPLETED" and not wo.get("verified_at")
    if st == "VERIFIED":
        likelihood, momentum = 0.98, 0.95
    elif st == "IN_PROGRESS" and has_contractor:
        likelihood, momentum = 0.7, 0.68 - min(0.15, age / 14.0)
    elif st == "COMPLETED":
        likelihood = 0.55 if has_evidence else 0.35
        momentum = 0.45 - min(0.35, completed_age / 10.0)
    elif not has_contractor and st in ("OPEN", "ASSIGNED", "SCHEDULED"):
        likelihood, momentum = 0.18, 0.12 - min(0.08, age / 30.0)
    else:
        likelihood, momentum = 0.4, 0.35 - min(0.2, age / 21.0)

    return {
        "entity_type": "work_order",
        "entity_id": wo.get("work_order_id"),
        "closure_likelihood": round(_clamp01(likelihood), 2),
        "operational_momentum_score": round(_clamp01(momentum), 2),
        "stalled_duration_days": round(age if st != "COMPLETED" else completed_age, 1),
        "dependency_count": deps,
        "closure_blockers": blockers,
        "likely_to_stall": _clamp01(momentum) < 0.3 and st in OPEN_WO_STATUSES,
        "fake_progress_risk": fake_progress,
        "verification_blockage": st == "COMPLETED" and not wo.get("verified_at"),
        "contractor_responsive": has_contractor and st not in ("OPEN",),
        "unresolved_evidence_dependency": st == "COMPLETED" and not has_evidence,
    }


def score_risk_closure(signal: Dict[str, Any]) -> Dict[str, Any]:
    st = (signal.get("status") or "").lower()
    age = _days_old(signal.get("updated_at") or signal.get("generated_at")) or 0.0
    blockers: List[str] = []
    if st == "resolved" and not signal.get("resolved_at"):
        blockers.append("fake_resolved_timestamp")
    if st == "acknowledged" and not signal.get("acknowledged_at"):
        blockers.append("weak_ack_authority")
    if st == "active":
        blockers.append("execution_not_started")
    fake = st == "resolved" and not signal.get("resolved_at")
    if st == "resolved":
        likelihood, momentum = 0.9 if signal.get("resolved_at") else 0.4, 0.35 if fake else 0.85
    elif st == "remediation_in_progress":
        likelihood, momentum = 0.75, 0.7
    elif st == "acknowledged":
        likelihood, momentum = 0.45, 0.4
    else:
        likelihood, momentum = 0.3, 0.25 - min(0.1, age / 30.0)
    return {
        "entity_type": "risk_signal",
        "entity_id": signal.get("signal_id"),
        "closure_likelihood": round(_clamp01(likelihood), 2),
        "operational_momentum_score": round(_clamp01(momentum), 2),
        "stalled_duration_days": round(age, 1),
        "dependency_count": len(blockers),
        "closure_blockers": blockers,
        "likely_to_stall": st in ACTIVE_RISK_STATUSES and _clamp01(momentum) < 0.35,
        "fake_progress_risk": fake,
        "verification_blockage": False,
        "contractor_responsive": st == "remediation_in_progress",
    }


async def build_closure_conversion_scores_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 1 — per-entity closure conversion profiles."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    issues, wos, risks = inv["issues"], inv["work_orders"], inv["risk_signals"]
    wo_by_issue = {w.get("issue_id"): w for w in wos if w.get("issue_id")}

    issue_scores = [
        score_issue_closure(i, wo_by_issue.get(i.get("issue_id"))) for i in issues[:200]
    ]
    wo_scores = [score_work_order_closure(w) for w in wos[:200]]
    risk_scores = [score_risk_closure(s) for s in risks[:200]]

    likely_stall = [s for s in issue_scores + wo_scores + risk_scores if s.get("likely_to_stall")]
    fake_chains = [s for s in issue_scores + wo_scores + risk_scores if s.get("fake_progress_risk")]
    low_conversion = [s for s in issue_scores + wo_scores + risk_scores if (s.get("closure_likelihood") or 0) < 0.35]

    return {
        "issues_sample": issue_scores[:15],
        "work_orders_sample": wo_scores[:15],
        "risk_signals_sample": risk_scores[:15],
        "likely_to_stall_count": len(likely_stall),
        "likely_to_stall_sample": likely_stall[:10],
        "fake_progress_chain_count": len(fake_chains),
        "fake_progress_sample": fake_chains[:10],
        "low_conversion_count": len(low_conversion),
        "low_conversion_sample": low_conversion[:10],
    }


async def build_deadlock_reduction_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 2 — stagnation groups with ageing copy."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    issues, wos = inv["issues"], inv["work_orders"]
    now = datetime.now(timezone.utc)
    groups: List[Dict[str, Any]] = []

    contractor_deadlocks = []
    for w in wos:
        st = (w.get("status") or "").upper()
        if st in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id"):
            age = _days_old(w.get("updated_at") or w.get("created_at")) or 0
            contractor_deadlocks.append((age, w))
    if contractor_deadlocks:
        contractor_deadlocks.sort(key=lambda x: -x[0])
        max_age = int(contractor_deadlocks[0][0])
        groups.append(
            {
                "deadlock_type": "contractor_deadlock",
                "headline": f"No contractor assigned on {len(contractor_deadlocks)} open jobs"
                + (f" (oldest {max_age} days)" if max_age >= 1 else ""),
                "count": len(contractor_deadlocks),
                "priority_score": SCORE_CONTRACTOR_DEADLOCK,
                "sample_ids": [w.get("work_order_id") for _, w in contractor_deadlocks[:5]],
                "recommended_action": "Assign or route contractor to unlock execution",
            }
        )

    verification_stuck = []
    for w in wos:
        if (w.get("status") or "").upper() != "COMPLETED" or w.get("verified_at"):
            continue
        age = _days_old(w.get("completed_at") or w.get("updated_at")) or 0
        verification_stuck.append((age, w))
    if verification_stuck:
        verification_stuck.sort(key=lambda x: -x[0])
        max_age = int(verification_stuck[0][0])
        groups.append(
            {
                "deadlock_type": "verification_deadlock",
                "headline": f"Awaiting verification on {len(verification_stuck)} completed jobs"
                + (f" (oldest {max_age} days)" if max_age >= 1 else ""),
                "count": len(verification_stuck),
                "priority_score": SCORE_VERIFICATION_BACKLOG,
                "sample_ids": [w.get("work_order_id") for _, w in verification_stuck[:5]],
                "recommended_action": "Verify completed work to authoritatively close operational debt",
            }
        )

    stale_issues = []
    for i in issues:
        st = (i.get("status") or "").lower()
        if st not in ("triaged", "monitoring", "investigating"):
            continue
        age = _days_old(i.get("updated_at") or i.get("created_at")) or 0
        if age > 7:
            stale_issues.append((age, i))
    if stale_issues:
        stale_issues.sort(key=lambda x: -x[0])
        groups.append(
            {
                "deadlock_type": "review_deadlock",
                "headline": f"{len(stale_issues)} issues stale in review (>7 days)",
                "count": len(stale_issues),
                "priority_score": SCORE_STALE_ISSUE,
                "sample_ids": [i.get("issue_id") for _, i in stale_issues[:5]],
                "recommended_action": "Triage, assign, or start job to break stale loop",
            }
        )

    ready_jobs = [i for i in issues if (i.get("status") or "").lower() == "ready_for_work_order"]
    if ready_jobs:
        groups.append(
            {
                "deadlock_type": "execution_not_started",
                "headline": f"{len(ready_jobs)} issues ready but no job in progress",
                "count": len(ready_jobs),
                "priority_score": SCORE_START_JOB,
                "sample_ids": [i.get("issue_id") for i in ready_jobs[:5]],
                "recommended_action": "Start maintenance job to convert triage into closure momentum",
            }
        )

    evidence_gaps = [
        w
        for w in wos
        if (w.get("status") or "").upper() == "COMPLETED"
        and not (w.get("evidence_keys") or (w.get("evidence_count") or 0) > 0)
    ]
    if evidence_gaps:
        groups.append(
            {
                "deadlock_type": "evidence_deadlock",
                "headline": f"{len(evidence_gaps)} completed jobs without linked proof",
                "count": len(evidence_gaps),
                "priority_score": SCORE_EVIDENCE_GAP,
                "sample_ids": [w.get("work_order_id") for w in evidence_gaps[:5]],
                "recommended_action": "Upload evidence before verification can be trusted",
            }
        )

    groups.sort(key=lambda g: -int(g.get("priority_score") or 0))
    return {
        "groups": groups,
        "total_deadlock_units": sum(g.get("count") or 0 for g in groups),
        "captured_at": now.isoformat(),
    }


def _momentum_action_from_deadlock(group: Dict[str, Any], entity: Dict[str, Any], entity_kind: str) -> Dict[str, Any]:
    from services.client_priority_stream import _action

    dtype = group.get("deadlock_type") or ""
    if dtype == "contractor_deadlock":
        at = ACTION_CLOSURE_CONTRACTOR_DEADLOCK
        score = SCORE_CONTRACTOR_DEADLOCK
        wid = entity.get("work_order_id")
        url = f"/operations/work-orders/{wid}" if wid else "/operations/work-orders"
        return _action(
            at,
            group.get("headline", "Assign contractor"),
            group.get("recommended_action", ""),
            score,
            "high",
            related_property_id=entity.get("property_id"),
            related_work_order_id=wid,
            why_matters="Unassigned jobs create fleet-wide execution deadlock and compound backlog pressure.",
            recommended_action_detail=group.get("recommended_action"),
            recommended_url=url,
            recommended_action_label="Assign contractor",
        )
    if dtype == "verification_deadlock":
        wid = entity.get("work_order_id")
        return _action(
            ACTION_CLOSURE_VERIFICATION_BACKLOG,
            group.get("headline", "Verify completed job"),
            group.get("recommended_action", ""),
            SCORE_VERIFICATION_BACKLOG,
            "high",
            related_property_id=entity.get("property_id"),
            related_work_order_id=wid,
            recommended_url=f"/operations/work-orders/{wid}" if wid else "/operations/work-orders",
            recommended_action_label="Verify job",
            why_matters="Completed-without-verified is operational debt, not trustworthy closure.",
            recommended_action_detail=group.get("recommended_action"),
        )
    if dtype == "review_deadlock":
        iid = entity.get("issue_id")
        return _action(
            ACTION_CLOSURE_STALE_ISSUE,
            group.get("headline", "Break stale issue loop"),
            group.get("recommended_action", ""),
            SCORE_STALE_ISSUE,
            "high",
            related_property_id=entity.get("property_id"),
            related_issue_id=iid,
            recommended_url=f"/operations/issues/{iid}" if iid else "/operations/issues",
            recommended_action_label="Review issue",
            why_matters="Stale triage consumes attention without closure progress.",
            recommended_action_detail=group.get("recommended_action"),
        )
    if dtype == "execution_not_started":
        iid = entity.get("issue_id")
        return _action(
            ACTION_CLOSURE_START_JOB,
            group.get("headline", "Start job from ready issue"),
            group.get("recommended_action", ""),
            SCORE_START_JOB,
            "high",
            related_property_id=entity.get("property_id"),
            related_issue_id=iid,
            recommended_url=f"/operations/issues/{iid}" if iid else "/operations/issues",
            recommended_action_label="Start job",
            why_matters="Starting jobs is the highest-leverage step to convert backlog into momentum.",
            recommended_action_detail=group.get("recommended_action"),
        )
    return _action(
        ACTION_CLOSURE_EVIDENCE_GAP,
        group.get("headline", "Add completion evidence"),
        group.get("recommended_action", ""),
        SCORE_EVIDENCE_GAP,
        "medium",
        related_work_order_id=entity.get("work_order_id"),
        recommended_url="/operations/work-orders",
        recommended_action_label="Add evidence",
    )


async def fetch_momentum_closure_priority_actions(
    client_id: str,
    property_id_filter: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Phase 3 — momentum-ranked actions for Command Centre primary slice."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    issues, wos = inv["issues"], inv["work_orders"]
    deadlock = await build_deadlock_reduction_v1(client_id, property_id_filter)
    actions: List[Dict[str, Any]] = []
    seen: set = set()

    for g in deadlock.get("groups") or []:
        dtype = g.get("deadlock_type")
        if dtype == "contractor_deadlock":
            candidates = [
                w
                for w in wos
                if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED")
                and not w.get("contractor_id")
            ]
            candidates.sort(key=lambda w: -(_days_old(w.get("updated_at")) or 0))
            for w in candidates[:2]:
                key = f"wo:{w.get('work_order_id')}"
                if key in seen:
                    continue
                seen.add(key)
                act = _momentum_action_from_deadlock(g, w, "work_order")
                sc = score_work_order_closure(w)
                act["closure_likelihood"] = sc.get("closure_likelihood")
                act["operational_momentum_score"] = sc.get("operational_momentum_score")
                age = _days_old(w.get("updated_at") or w.get("created_at")) or 0
                if age >= 14:
                    act["priority"] = min(99, (act.get("priority") or SCORE_CONTRACTOR_DEADLOCK) + 6)
                elif age >= 7:
                    act["priority"] = min(98, (act.get("priority") or SCORE_CONTRACTOR_DEADLOCK) + 3)
                actions.append(act)
        elif dtype == "verification_deadlock":
            candidates = [
                w
                for w in wos
                if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
            ]
            candidates.sort(key=lambda w: -(_days_old(w.get("completed_at")) or 0))
            for w in candidates[:2]:
                key = f"wo:{w.get('work_order_id')}"
                if key in seen:
                    continue
                seen.add(key)
                act = _momentum_action_from_deadlock(g, w, "work_order")
                sc = score_work_order_closure(w)
                act["closure_likelihood"] = sc.get("closure_likelihood")
                act["operational_momentum_score"] = sc.get("operational_momentum_score")
                v_age = _days_old(w.get("completed_at") or w.get("updated_at")) or 0
                if v_age >= 14:
                    act["priority"] = min(99, (act.get("priority") or SCORE_VERIFICATION_BACKLOG) + 8)
                elif v_age >= 7:
                    act["priority"] = min(98, (act.get("priority") or SCORE_VERIFICATION_BACKLOG) + 4)
                actions.append(act)
        elif dtype == "review_deadlock":
            candidates = []
            for i in issues:
                st = (i.get("status") or "").lower()
                if st in ("triaged", "monitoring", "investigating"):
                    age = _days_old(i.get("updated_at")) or 0
                    if age > 7:
                        candidates.append(i)
            for i in candidates[:2]:
                key = f"iss:{i.get('issue_id')}"
                if key in seen:
                    continue
                seen.add(key)
                actions.append(_momentum_action_from_deadlock(g, i, "issue"))
        elif dtype == "execution_not_started":
            for i in [x for x in issues if (x.get("status") or "").lower() == "ready_for_work_order"][:2]:
                key = f"iss:{i.get('issue_id')}"
                if key in seen:
                    continue
                seen.add(key)
                act = _momentum_action_from_deadlock(g, i, "issue")
                sc = score_issue_closure(i)
                act["closure_likelihood"] = sc.get("closure_likelihood")
                act["operational_momentum_score"] = sc.get("operational_momentum_score")
                actions.append(act)

    actions.sort(key=lambda a: -(a.get("priority") or 0))
    return actions[:limit]


async def build_verification_throughput_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 4 — completed-but-unverified as operational debt."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]
    backlog = []
    for w in wos:
        if (w.get("status") or "").upper() != "COMPLETED" or w.get("verified_at"):
            continue
        age = _days_old(w.get("completed_at") or w.get("updated_at")) or 0
        sc = score_work_order_closure(w)
        backlog.append(
            {
                "work_order_id": w.get("work_order_id"),
                "property_id": w.get("property_id"),
                "completed_at": w.get("completed_at"),
                "verification_age_days": round(age, 1),
                "has_evidence": bool(w.get("evidence_keys") or (w.get("evidence_count") or 0) > 0),
                "closure_likelihood": sc.get("closure_likelihood"),
                "operational_momentum_score": sc.get("operational_momentum_score"),
            }
        )
    backlog.sort(key=lambda x: -float(x.get("verification_age_days") or 0))
    verified = sum(1 for w in wos if (w.get("status") or "").upper() == "VERIFIED")
    completed = sum(1 for w in wos if (w.get("status") or "").upper() == "COMPLETED")
    return {
        "verification_queue_count": len(backlog),
        "verification_queue_pressure": "high" if len(backlog) >= 5 else "medium" if backlog else "low",
        "completed_without_verification_count": len(backlog),
        "verified_count": verified,
        "completed_terminal_count": completed + verified,
        "verification_conversion_rate": round(verified / max(completed + verified, 1), 2),
        "queue_sample": backlog[:12],
        "sla_indicator": {
            "target_verify_within_days": 7,
            "over_sla_count": sum(1 for b in backlog if (b.get("verification_age_days") or 0) > 7),
        },
    }


async def build_closure_momentum_kpis_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 5 — closure throughput KPIs."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    issues, wos, risks = inv["issues"], inv["work_orders"], inv["risk_signals"]
    scores = await build_closure_conversion_scores_v1(client_id, property_id_filter)
    deadlock = await build_deadlock_reduction_v1(client_id, property_id_filter)
    verification = await build_verification_throughput_v1(client_id, property_id_filter)

    wo_scored = [score_work_order_closure(w) for w in wos[:150]]
    avg_momentum = sum(s.get("operational_momentum_score") or 0 for s in wo_scored) / max(len(wo_scored), 1)
    avg_stall_days = sum(s.get("stalled_duration_days") or 0 for s in wo_scored if s.get("likely_to_stall")) / max(
        1, scores.get("likely_to_stall_count") or 1
    )

    open_before = len([i for i in issues if (i.get("status") or "").lower() in OPEN_ISSUE_STATUSES]) + len(
        [w for w in wos if (w.get("status") or "").upper() in OPEN_WO_STATUSES]
    )

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "closure_conversion_rate": verification.get("verification_conversion_rate"),
        "average_stalled_duration_days": round(avg_stall_days, 1),
        "deadlock_resolution_rate": {
            "note": "Point-in-time; requires historical resolved deadlocks for true rate.",
            "open_deadlock_units": deadlock.get("total_deadlock_units"),
        },
        "verification_throughput": {
            "queue_count": verification.get("verification_queue_count"),
            "over_sla": (verification.get("sla_indicator") or {}).get("over_sla_count"),
        },
        "operational_momentum_trend": {
            "portfolio_momentum_index": round(avg_momentum, 2),
            "likely_to_stall_count": scores.get("likely_to_stall_count"),
        },
        "closure_confidence_trend": {
            "fake_progress_chains": scores.get("fake_progress_chain_count"),
            "low_conversion_entities": scores.get("low_conversion_count"),
        },
        "pressure_reduction_velocity": {
            "note": "Snapshot only; compare across sessions for velocity.",
            "open_operational_units": open_before,
        },
        "stale_recovery_velocity": {
            "stale_issue_deadlocks": sum(
                1 for g in deadlock.get("groups") or [] if g.get("deadlock_type") == "review_deadlock"
            ),
        },
        "fake_progress_reduction_trend": {
            "fake_progress_count": scores.get("fake_progress_chain_count"),
        },
    }


async def build_landlord_decision_confidence_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 6 — what still feels stuck / noisy / meaningless."""
    deadlock = await build_deadlock_reduction_v1(client_id, property_id_filter)
    verification = await build_verification_throughput_v1(client_id, property_id_filter)
    scores = await build_closure_conversion_scores_v1(client_id, property_id_filter)

    still_stuck = [g.get("headline") for g in deadlock.get("groups") or []]
    still_noisy = []
    if scores.get("fake_progress_chain_count", 0) > 5:
        still_noisy.append("Resolved risk signals without authoritative timestamps")
    if verification.get("verification_queue_count", 0) > 5:
        still_noisy.append("Large completed-but-unverified job queue")

    meaningless_risks = []
    if deadlock.get("total_deadlock_units", 0) > 20:
        meaningless_risks.append(
            "Assign-contractor and verify-job actions may feel low-impact until fleet deadlock count drops"
        )

    confidence_score = _clamp01(
        0.85
        - min(0.4, (deadlock.get("total_deadlock_units") or 0) / 60.0)
        - min(0.25, (verification.get("verification_queue_count") or 0) / 40.0)
    )

    return {
        "decision_confidence_score": round(confidence_score, 2),
        "still_feels_stuck": still_stuck[:6],
        "still_feels_noisy": still_noisy,
        "still_feels_unresolved": still_stuck[:4],
        "actions_that_feel_meaningless": meaningless_risks,
        "momentum_indicators": {
            "highest_leverage": (deadlock.get("groups") or [{}])[0].get("recommended_action")
            if deadlock.get("groups")
            else "Review operational focus",
        },
    }


async def build_operational_closure_bundle_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    import asyncio

    scores, deadlock, verification, kpis, confidence = await asyncio.gather(
        build_closure_conversion_scores_v1(client_id, property_id_filter),
        build_deadlock_reduction_v1(client_id, property_id_filter),
        build_verification_throughput_v1(client_id, property_id_filter),
        build_closure_momentum_kpis_v1(client_id, property_id_filter),
        build_landlord_decision_confidence_v1(client_id, property_id_filter),
    )
    momentum_actions = await fetch_momentum_closure_priority_actions(client_id, property_id_filter)
    return {
        "programme": PROGRAMME,
        "closure_conversion_scores_v1": scores,
        "deadlock_reduction_v1": deadlock,
        "verification_throughput_v1": verification,
        "closure_momentum_kpis_v1": kpis,
        "landlord_decision_confidence_v1": confidence,
        "momentum_priority_actions": momentum_actions,
        "what_clears_most_pressure": (
            (deadlock.get("groups") or [{}])[0].get("recommended_action")
            if deadlock.get("groups")
            else None
        ),
    }


def merge_momentum_with_compliance_actions(
    momentum: List[Dict[str, Any]],
    compliance: List[Dict[str, Any]],
    *,
    cap: int = 20,
) -> List[Dict[str, Any]]:
    """Dedupe and prioritise momentum closure actions ahead of compliance stream."""
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for a in momentum:
        key = (
            a.get("related_work_order_id")
            or a.get("related_issue_id")
            or a.get("related_requirement_id")
            or a.get("title")
        )
        if key and key not in seen:
            seen.add(key)
            out.append(a)
    for a in compliance:
        key = (
            a.get("related_work_order_id")
            or a.get("related_issue_id")
            or a.get("related_requirement_id")
            or a.get("title")
        )
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(a)
    out.sort(key=lambda x: -(x.get("priority") or 0))
    return out[:cap]
