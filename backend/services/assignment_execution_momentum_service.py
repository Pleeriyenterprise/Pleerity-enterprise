"""
ASSIGNMENT-CONVERSION-AND-EXECUTION-MOMENTUM-01

Coordination infrastructure: assignment conversion traces, momentum states,
quote momentum, accountability surfaces, and coordination nudges.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.operational_closure_conversion_service import _days_old, _parse_dt
from services.operational_value_compression_service import load_operational_inventory
from services.work_order_assignment_constants import (
    ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN,
    ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
    ASSIGNMENT_ROUTING_UNASSIGNED,
)

logger = logging.getLogger(__name__)

PROGRAMME = "ASSIGNMENT-CONVERSION-AND-EXECUTION-MOMENTUM-01"

TRACE_JOB_CAP = 22
STALL_DAYS = 7
DECAY_DAYS = 14
QUOTE_STALL_DAYS = 3
QUOTE_ABANDON_DAYS = 7


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _meaningful_action_age_days(wo: Dict[str, Any]) -> float:
    candidates = [
        wo.get("updated_at"),
        wo.get("assigned_at"),
        wo.get("recommended_at"),
        wo.get("quote_submitted_at"),
        wo.get("quote_approved_at"),
        wo.get("accepted_at"),
        wo.get("created_at"),
    ]
    ages = [_days_old(c) for c in candidates if _days_old(c) is not None]
    if ages:
        return min(ages)
    return _days_old(wo.get("updated_at") or wo.get("created_at")) or 0.0


def _quote_momentum_state(wo: Dict[str, Any]) -> Optional[str]:
    ps = (wo.get("price_status") or "").upper()
    if not ps and (wo.get("pricing_mode") or "").upper() != "MAINTENANCE_PREQUOTE":
        return None
    if ps == "APPROVED":
        if (wo.get("status") or "").upper() == "IN_PROGRESS":
            return "executing"
        return "approved"
    if ps == "REJECTED":
        return "abandoned"
    if ps == "QUOTED":
        age = _days_old(wo.get("quote_submitted_at")) or 0
        if age >= QUOTE_ABANDON_DAYS:
            return "abandoned"
        if age >= QUOTE_STALL_DAYS:
            return "stalled"
        return "delayed"
    if ps == "AWAITING_QUOTE":
        age = _days_old(wo.get("assigned_at") or wo.get("updated_at")) or 0
        if age >= QUOTE_ABANDON_DAYS:
            return "abandoned"
        if age >= QUOTE_STALL_DAYS:
            return "stalled"
        return "requested"
    return None


def _execution_momentum_state(
    wo: Dict[str, Any],
    *,
    eligible_count: int = 0,
    coordination_failure: Optional[str] = None,
) -> str:
    st = (wo.get("status") or "").upper()
    inactivity = _meaningful_action_age_days(wo)
    if st in ("IN_PROGRESS", "COMPLETED", "VERIFIED"):
        if inactivity <= STALL_DAYS:
            return "progressing"
        if inactivity <= DECAY_DAYS:
            return "stalled"
        return "decaying"
    if wo.get("contractor_id") and st in ("ASSIGNED", "SCHEDULED"):
        qm = _quote_momentum_state(wo)
        if qm in ("stalled", "abandoned", "delayed"):
            return "stalled"
        if inactivity <= STALL_DAYS:
            return "progressing"
        return "decaying"
    if eligible_count > 0 and not wo.get("contractor_id"):
        if inactivity >= DECAY_DAYS:
            return "deadlocked"
        if inactivity >= STALL_DAYS:
            return "decaying"
        return "stalled"
    if coordination_failure in ("support_inaction", "escalation_failure"):
        return "deadlocked"
    if inactivity >= DECAY_DAYS:
        return "deadlocked"
    if inactivity >= STALL_DAYS:
        return "decaying"
    return "stalled"


def _classify_coordination_failure(
    wo: Dict[str, Any],
    eligible_count: int,
    routing: Optional[Dict[str, Any]] = None,
) -> str:
    if eligible_count == 0:
        return "routing_failure"

    rs = (wo.get("assignment_routing_state") or ASSIGNMENT_ROUTING_UNASSIGNED).strip().upper()
    ps = (wo.get("price_status") or "").upper()

    if rs == ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION:
        deadline = _parse_dt(wo.get("client_confirmation_deadline_at"))
        if deadline and datetime.now(timezone.utc) > deadline:
            return "landlord_inaction"
        return "governance_delay"

    if rs == ASSIGNMENT_ROUTING_ESCALATED_TO_ADMIN or wo.get("routing_pending_admin"):
        return "support_inaction"

    if not wo.get("recommended_at") and rs in (ASSIGNMENT_ROUTING_UNASSIGNED, "CONTRACTOR_RECOMMENDED"):
        age = _days_old(wo.get("created_at")) or 0
        if age >= STALL_DAYS:
            return "orchestration_failure"
        return "landlord_inaction"

    if wo.get("confirmation_escalated_at") and not wo.get("contractor_id"):
        return "escalation_failure"

    if routing and (routing.get("flags") or {}).get("sla_breached"):
        if eligible_count > 0:
            return "orchestration_failure"

    if ps in ("AWAITING_QUOTE", "QUOTED") and wo.get("contractor_id"):
        return "quote_bottleneck"

    if ps == "QUOTED" and not wo.get("quote_approved_at"):
        return "governance_delay"

    return "orchestration_failure"


def _expected_actor(coordination_failure: str) -> str:
    return {
        "landlord_inaction": "client",
        "support_inaction": "admin_support",
        "contractor_non_response": "contractor",
        "quote_bottleneck": "contractor",
        "governance_delay": "client",
        "orchestration_failure": "platform_coordination",
        "escalation_failure": "admin_support",
        "routing_failure": "contractor_network",
    }.get(coordination_failure, "unknown")


async def build_assignment_conversion_trace_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 1 — per-job coordination failure path."""
    from services import contractor_service

    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]

    unassigned = [
        w
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED")
        and not w.get("contractor_id")
        and (w.get("work_order_kind") or "MAINTENANCE").upper() != "COMPLIANCE"
    ]
    unassigned.sort(key=lambda w: -(_days_old(w.get("updated_at") or w.get("created_at")) or 0))

    traces: List[Dict[str, Any]] = []
    taxonomy: Dict[str, int] = defaultdict(int)
    eligible_unassigned = 0

    for w in unassigned[:TRACE_JOB_CAP]:
        wid = w.get("work_order_id")
        if not wid:
            continue
        assignable = await contractor_service.list_assignable_contractors_for_work_order(
            client_id, wid, limit=3
        )
        eligible = assignable.get("total") or len(assignable.get("contractors") or [])
        rec = await contractor_service.recommend_contractors_for_work_order(wid, client_id=client_id, limit=1)
        routing = rec.get("routing") or {}
        if eligible > 0:
            eligible_unassigned += 1

        cf = _classify_coordination_failure(w, eligible, routing)
        taxonomy[cf] += 1
        mom = _execution_momentum_state(w, eligible_count=eligible, coordination_failure=cf)

        traces.append(
            {
                "work_order_id": wid,
                "property_id": w.get("property_id"),
                "status": w.get("status"),
                "assignment_age_days": round(_days_old(w.get("created_at")) or 0, 1),
                "eligible_contractor_count": eligible,
                "assignment_routing_state": w.get("assignment_routing_state"),
                "recommended_at": w.get("recommended_at"),
                "recommended_contractor_id": w.get("recommended_contractor_id"),
                "client_confirmation_deadline_at": w.get("client_confirmation_deadline_at"),
                "confirmation_escalated_at": w.get("confirmation_escalated_at"),
                "routing_pending_admin": wo.get("routing_pending_admin") if (wo := w) else False,
                "coordination_failure": cf,
                "expected_actor": _expected_actor(cf),
                "execution_momentum_state": mom,
                "recommendation_surfaced": bool(w.get("recommended_at") or w.get("recommended_contractor_id")),
                "stalled_step": _stalled_step_label(w, cf),
                "price_status": w.get("price_status"),
            }
        )

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "eligible_but_unassigned_count": eligible_unassigned,
        "unassigned_audited": len(traces),
        "coordination_failure_taxonomy": dict(sorted(taxonomy.items(), key=lambda x: -x[1])),
        "traces_sample": traces[:15],
        "dominant_failure": max(taxonomy.items(), key=lambda x: x[1])[0] if taxonomy else None,
    }


def _stalled_step_label(wo: Dict[str, Any], cf: str) -> str:
    rs = (wo.get("assignment_routing_state") or "").upper()
    if cf == "landlord_inaction":
        if rs == ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION:
            return "client_confirm_recommended_contractor"
        if not wo.get("recommended_at"):
            return "generate_or_confirm_contractor_assignment"
        return "client_assignment_confirmation"
    if cf == "orchestration_failure":
        return "assignment_routing_never_completed"
    if cf == "support_inaction":
        return "admin_routing_pending"
    if cf == "quote_bottleneck":
        return "awaiting_contractor_quote"
    if cf == "governance_delay":
        return "awaiting_quote_approval"
    return "coordination_stalled"


async def build_execution_momentum_engine_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Phase 2 — fleet momentum states and latency metrics."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]

    state_counts: Dict[str, int] = defaultdict(int)
    inactivity_samples: List[float] = []
    escalation_latencies: List[float] = []

    for w in wos:
        if (w.get("work_order_kind") or "MAINTENANCE").upper() == "COMPLIANCE":
            continue
        mom = _execution_momentum_state(w)
        state_counts[mom] += 1
        inactivity_samples.append(_meaningful_action_age_days(w))
        if w.get("confirmation_escalated_at") and w.get("created_at"):
            c = _parse_dt(w.get("created_at"))
            e = _parse_dt(w.get("confirmation_escalated_at"))
            if c and e:
                escalation_latencies.append((e - c).total_seconds() / 86400)

    total = sum(state_counts.values()) or 1
    stalled_ratio = round(
        (state_counts.get("stalled", 0) + state_counts.get("decaying", 0) + state_counts.get("deadlocked", 0)) / total,
        2,
    )

    return {
        "execution_momentum_states": dict(state_counts),
        "stalled_momentum_ratio": stalled_ratio,
        "avg_inactivity_days": round(sum(inactivity_samples) / max(len(inactivity_samples), 1), 1),
        "avg_escalation_latency_days": round(
            sum(escalation_latencies) / max(len(escalation_latencies), 1), 1
        )
        if escalation_latencies
        else None,
        "eligible_but_unassigned": (trace or {}).get("eligible_but_unassigned_count"),
    }


async def build_coordination_nudges_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Phase 3 — low-risk acceleration surfaces (no auto-assign)."""
    trace = trace or await build_assignment_conversion_trace_v1(client_id, property_id_filter)
    nudges: List[Dict[str, Any]] = []

    for t in trace.get("traces_sample") or []:
        if t.get("eligible_contractor_count", 0) > 0 and t.get("coordination_failure") in (
            "landlord_inaction",
            "orchestration_failure",
        ):
            nudges.append(
                {
                    "nudge_type": "eligible_but_unassigned",
                    "work_order_id": t.get("work_order_id"),
                    "priority": "critical" if (t.get("assignment_age_days") or 0) >= DECAY_DAYS else "high",
                    "headline": f"Eligible contractors available — job unassigned {t.get('assignment_age_days')}d",
                    "recommended_action": "Confirm contractor assignment or choose alternate from assignable list",
                    "escalation_tier": "auto_escalate_stale_unassigned",
                }
            )
        if t.get("coordination_failure") == "support_inaction":
            nudges.append(
                {
                    "nudge_type": "admin_routing_pending",
                    "work_order_id": t.get("work_order_id"),
                    "priority": "high",
                    "headline": "Awaiting admin contractor routing",
                    "recommended_action": "Complete admin routing or return to client confirmation flow",
                }
            )

    inv = await load_operational_inventory(client_id, property_id_filter)
    for w in inv["work_orders"]:
        qm = _quote_momentum_state(w)
        if qm in ("stalled", "abandoned"):
            nudges.append(
                {
                    "nudge_type": "quote_momentum_decay",
                    "work_order_id": w.get("work_order_id"),
                    "priority": "high",
                    "headline": f"Quote momentum {qm} on assigned job",
                    "recommended_action": "Send quote reminder or approve/reject pending quote",
                    "quote_momentum_state": qm,
                }
            )

    decaying = [
        t
        for t in trace.get("traces_sample") or []
        if t.get("execution_momentum_state") in ("decaying", "deadlocked")
    ]
    if decaying:
        nudges.append(
            {
                "nudge_type": "momentum_decay_alert",
                "priority": "critical",
                "headline": f"Operational momentum decaying on {len(decaying)} jobs in sample",
                "recommended_action": "Review coordination failures and execute next authoritative action",
            }
        )

    nudges.sort(key=lambda n: 0 if n.get("priority") == "critical" else 1)
    return {"nudges": nudges[:12], "nudge_count": len(nudges)}


async def build_quote_conversion_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase 4 — quote momentum states and funnel."""
    inv = await load_operational_inventory(client_id, property_id_filter)
    wos = inv["work_orders"]

    quote_states: Dict[str, int] = defaultdict(int)
    hotspots: List[Dict[str, Any]] = []
    request_base = 0
    quoted = 0
    approved = 0
    executing = 0

    for w in wos:
        qm = _quote_momentum_state(w)
        if not qm:
            continue
        quote_states[qm] += 1
        ps = (w.get("price_status") or "").upper()
        if ps:
            request_base += 1
        if ps in ("QUOTED", "APPROVED", "REJECTED"):
            quoted += 1
        if ps == "APPROVED":
            approved += 1
        if qm == "executing":
            executing += 1
        if qm in ("stalled", "abandoned"):
            hotspots.append(
                {
                    "work_order_id": w.get("work_order_id"),
                    "quote_momentum_state": qm,
                    "price_status": ps,
                    "age_days": round(_days_old(w.get("quote_submitted_at") or w.get("assigned_at")) or 0, 1),
                }
            )

    return {
        "quote_momentum_states": dict(quote_states),
        "request_to_quote_conversion": round(quoted / max(request_base, 1), 2),
        "quote_to_approval_conversion": round(approved / max(quoted, 1), 2),
        "approval_to_execution_conversion": round(executing / max(approved, 1), 2),
        "quote_bottleneck_hotspots": sorted(hotspots, key=lambda x: -float(x.get("age_days") or 0))[:10],
        "awaiting_quote_fleet_count": quote_states.get("requested", 0) + quote_states.get("delayed", 0),
    }


async def build_execution_accountability_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Phase 5 — why stuck / who blocks / execution capacity truth."""
    trace = trace or await build_assignment_conversion_trace_v1(client_id, property_id_filter)
    accountability_rows: List[Dict[str, Any]] = []

    for t in trace.get("traces_sample") or []:
        cf = t.get("coordination_failure") or ""
        eligible = t.get("eligible_contractor_count") or 0
        accountability_rows.append(
            {
                "work_order_id": t.get("work_order_id"),
                "why_not_progressed": _why_not_progressed(t),
                "blocking_party": t.get("expected_actor"),
                "execution_capacity_exists": eligible > 0,
                "coordination_failed": cf in (
                    "landlord_inaction",
                    "orchestration_failure",
                    "support_inaction",
                    "escalation_failure",
                ),
                "governance_blocked": cf in ("governance_delay", "quote_bottleneck"),
                "stalled_step": t.get("stalled_step"),
                "execution_momentum_state": t.get("execution_momentum_state"),
            }
        )

    return {
        "accountability_sample": accountability_rows[:12],
        "blockage_truth": (
            "Coordination failure — eligible contractors exist but assignment not completed"
            if trace.get("eligible_but_unassigned_count", 0) >= 5
            else "Mixed execution-capacity and coordination constraints"
        ),
        "dominant_coordination_failure": trace.get("dominant_failure"),
    }


def _why_not_progressed(t: Dict[str, Any]) -> str:
    cf = t.get("coordination_failure") or ""
    if cf == "landlord_inaction":
        return "Client has not confirmed contractor assignment despite eligible supply"
    if cf == "orchestration_failure":
        return "Assignment routing was never completed despite eligible contractors"
    if cf == "support_inaction":
        return "Job escalated to admin routing without resolution"
    if cf == "quote_bottleneck":
        return "Contractor assigned but quote not submitted"
    if cf == "governance_delay":
        return "Quote submitted; awaiting client approval"
    if cf == "routing_failure":
        return "No eligible contractor matches property/trade filters"
    return "Operational momentum stalled — review coordination trace"


async def build_operational_momentum_kpis_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    trace: Optional[Dict[str, Any]] = None,
    momentum: Optional[Dict[str, Any]] = None,
    quote: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Phase 6 — coordination and momentum KPIs."""
    trace = trace or await build_assignment_conversion_trace_v1(client_id, property_id_filter)
    momentum = momentum or await build_execution_momentum_engine_v1(client_id, property_id_filter, trace=trace)
    quote = quote or await build_quote_conversion_v1(client_id, property_id_filter)

    eligible_unassigned = trace.get("eligible_but_unassigned_count") or 0
    total_audited = trace.get("unassigned_audited") or 1
    assignment_conversion_velocity = round(
        1.0 - (eligible_unassigned / max(total_audited, 1)),
        2,
    )

    stalled_ratio = momentum.get("stalled_momentum_ratio") or 0
    execution_momentum_score = round(_clamp01(1.0 - stalled_ratio * 0.85), 2)

    coordination_latency_score = round(
        _clamp01(1.0 - min(1.0, (momentum.get("avg_inactivity_days") or 0) / 21.0)),
        2,
    )

    quote_velocity = round(
        (quote.get("quote_to_approval_conversion") or 0) * 0.5
        + (quote.get("approval_to_execution_conversion") or 0) * 0.5,
        2,
    )

    follow_through_rate = round(
        _clamp01(assignment_conversion_velocity * 0.6 + (1.0 - stalled_ratio) * 0.4),
        2,
    )

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "assignment_conversion_velocity": assignment_conversion_velocity,
        "execution_momentum_score": execution_momentum_score,
        "coordination_latency_score": coordination_latency_score,
        "escalation_responsiveness": momentum.get("avg_escalation_latency_days"),
        "quote_conversion_velocity": quote_velocity,
        "execution_recovery_rate": {"note": "Measure after coordination nudges acted upon"},
        "stalled_momentum_ratio": stalled_ratio,
        "contractor_engagement_score": round(_clamp01(quote.get("request_to_quote_conversion") or 0), 2),
        "operational_follow_through_rate": follow_through_rate,
        "eligible_but_unassigned_remaining": eligible_unassigned,
    }


async def fetch_coordination_momentum_priority_actions(
    client_id: str,
    property_id_filter: Optional[str] = None,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    from services.client_priority_stream import _action

    nudges_block = await build_coordination_nudges_v1(client_id, property_id_filter)
    actions: List[Dict[str, Any]] = []
    for i, n in enumerate(nudges_block.get("nudges") or []):
        score = 91 - i * 2 if n.get("priority") == "critical" else 87 - i
        wid = n.get("work_order_id")
        url = f"/operations/work-orders/{wid}" if wid else "/operations/work-orders"
        actions.append(
            _action(
                "coordination_momentum_nudge",
                n.get("headline", "Coordination action required"),
                n.get("recommended_action", ""),
                score,
                "high" if n.get("priority") == "critical" else "medium",
                related_work_order_id=wid,
                recommended_url=url,
                recommended_action_label="Act now",
                why_matters="Eligible execution capacity exists — momentum is lost without coordination follow-through.",
                recommended_action_detail=n.get("recommended_action"),
            )
        )
    actions.sort(key=lambda a: -(a.get("priority") or 0))
    return actions[:limit]


def merge_coordination_with_urgent(
    coordination: List[Dict[str, Any]],
    existing: List[Dict[str, Any]],
    *,
    cap: int = 24,
) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for a in coordination + existing:
        key = a.get("related_work_order_id") or a.get("title")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(a)
    out.sort(key=lambda x: -(x.get("priority") or 0))
    return out[:cap]


async def build_assignment_execution_momentum_bundle_v1(
    client_id: str,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    import asyncio

    trace = await build_assignment_conversion_trace_v1(client_id, property_id_filter)
    momentum, nudges, quote, accountability, kpis = await asyncio.gather(
        build_execution_momentum_engine_v1(client_id, property_id_filter, trace=trace),
        build_coordination_nudges_v1(client_id, property_id_filter, trace=trace),
        build_quote_conversion_v1(client_id, property_id_filter),
        build_execution_accountability_v1(client_id, property_id_filter, trace=trace),
        build_operational_momentum_kpis_v1(client_id, property_id_filter, trace=trace),
    )
    priority_actions = await fetch_coordination_momentum_priority_actions(client_id, property_id_filter)
    return {
        "programme": PROGRAMME,
        "assignment_conversion_trace_v1": trace,
        "execution_momentum_engine_v1": momentum,
        "coordination_nudges_v1": nudges,
        "quote_conversion_v1": quote,
        "execution_accountability_v1": accountability,
        "operational_momentum_kpis_v1": kpis,
        "coordination_priority_actions": priority_actions,
        "primary_coordination_bottleneck": trace.get("dominant_failure"),
    }
