"""
Compliance Graph Service — sole supported public interface for the Evidence Graph.

Consumers must not import compliance_evidence_graph.storage directly.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_evidence_graph.storage import decisions as decision_storage
from services.compliance_evidence_graph.storage import edges as edge_storage
from services.compliance_evidence_graph.storage import nodes as node_storage
from services.compliance_evidence_graph.storage import snapshots as snapshot_storage
from services.compliance_graph_service.access import ActorContext, enforce_decision_tenant, enforce_tenant_access
from services.compliance_graph_service.envelopes import base_envelope, insufficient


def _decision_lineage(decision: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "decision_id": decision.get("decision_id"),
        "previous_decision_id": decision.get("previous_decision_id"),
        "superseding_decision_id": decision.get("superseding_decision_id"),
        "chain": [x for x in [decision.get("previous_decision_id"), decision.get("decision_id")] if x],
    }


def _refs_from_decision(decision: Dict[str, Any], snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    evidence = (decision.get("evidence_set") or {})
    return {
        "decision_id": decision.get("decision_id"),
        "snapshot_id": decision.get("snapshot_id"),
        "decision_ids": [decision.get("decision_id")],
        "node_ids": evidence.get("evidence_node_ids") or [],
        "edge_ids": [],
        "source_pointers": [decision.get("source")] if decision.get("source") else [],
    }


async def explain_decision(decision_id: str, *, actor: ActorContext) -> Dict[str, Any]:
    request = {"decision_id": decision_id}
    decision = await decision_storage.get_decision(decision_id)
    if not decision:
        return insufficient("explain_decision", request)
    enforce_decision_tenant(actor, decision)
    snapshot = await snapshot_storage.get_snapshot_by_decision(decision_id)
    if not snapshot:
        return insufficient("explain_decision", request, "Decision snapshot not found.")

    reasoning_inputs = snapshot.get("decision_reasoning_inputs") or {}
    steps: List[Dict[str, Any]] = []
    if decision.get("summary"):
        steps.append(
            {
                "step": 1,
                "statement": decision["summary"],
                "authoritative_references": {"decision_id": decision_id, "snapshot_id": snapshot.get("snapshot_id")},
                "confidence": (decision.get("decision_confidence") or {}).get("score", 100),
            }
        )
    if reasoning_inputs:
        steps.append(
            {
                "step": len(steps) + 1,
                "statement": "Decision reasoning inputs preserved at decision time",
                "authoritative_references": {"snapshot_fields": ["decision_reasoning_inputs"]},
                "confidence": (decision.get("decision_confidence") or {}).get("score", 100),
            }
        )

    payload = {
        "executive_summary": decision.get("summary") or "Compliance decision recorded.",
        "decision": {
            "decision_id": decision.get("decision_id"),
            "decision_type": decision.get("decision_type"),
            "decision_outcome": decision.get("decision_outcome"),
            "decision_timestamp": decision.get("decision_timestamp"),
            "decision_authority": decision.get("decision_authority"),
        },
        "decision_reasoning": steps,
        "snapshot_summary": {
            "snapshot_id": snapshot.get("snapshot_id"),
            "snapshot_timestamp": snapshot.get("snapshot_timestamp"),
            "snapshot_hash": snapshot.get("snapshot_hash"),
        },
        "evidence_used": snapshot.get("evidence_version") or {},
        "applicable_legislation": snapshot.get("applicable_legislation") or [],
        "applicable_local_rules": (snapshot.get("applicable_jurisdiction") or {}).get("council_requirements") or [],
        "timeline": snapshot.get("timeline_references") or [],
        "operational_history": snapshot.get("operational_context") or {},
        "confidence_assessment": decision.get("decision_confidence") or {},
        "outstanding_uncertainty": [],
        "recommended_actions": [],
    }

    return base_envelope(
        service="explain_decision",
        request=request,
        payload=payload,
        authoritative_references=_refs_from_decision(decision, snapshot),
        evidence_lineage=[
            {"type": "snapshot", "snapshot_id": snapshot.get("snapshot_id")},
        ],
        decision_lineage=_decision_lineage(decision),
        confidence_metadata=decision.get("decision_confidence") or {},
        applicable_legislation=snapshot.get("applicable_legislation") or [],
        applicable_rules=[decision.get("rules_version")] if decision.get("rules_version") else [],
        historical_references={
            "snapshot_id": snapshot.get("snapshot_id"),
            "snapshot_timestamp": snapshot.get("snapshot_timestamp"),
        },
        operational_references={
            "correlation_id": decision.get("operational_correlation_id"),
            "operational_event_ids": (snapshot.get("operational_context") or {}).get("operational_event_ids") or [],
        },
    )


async def replay_decision(decision_id: str, *, actor: ActorContext) -> Dict[str, Any]:
    request = {"decision_id": decision_id}
    decision = await decision_storage.get_decision(decision_id)
    if not decision:
        return insufficient("replay_decision", request)
    enforce_decision_tenant(actor, decision)
    snapshot = await snapshot_storage.get_snapshot_by_decision(decision_id)
    if not snapshot:
        return insufficient("replay_decision", request)

    nodes = await node_storage.list_nodes_for_decision(decision_id)
    edges = await edge_storage.list_edges_for_decision(decision_id)

    phases = []
    if snapshot.get("rules_version") or snapshot.get("applicable_jurisdiction"):
        phases.append({"phase": "requirements_determined", "source": "snapshot"})
    if snapshot.get("evidence_version"):
        phases.append({"phase": "evidence_collected", "source": "snapshot"})
    if snapshot.get("ai_extraction_results"):
        phases.append({"phase": "extraction_applied", "source": "snapshot"})
    if snapshot.get("human_approvals"):
        phases.append({"phase": "human_review", "source": "snapshot"})
    if snapshot.get("decision_reasoning_inputs"):
        phases.append({"phase": "authority_sync", "source": "snapshot"})
    if snapshot.get("compliance_score"):
        phases.append({"phase": "score_recalculated", "source": "snapshot"})
    if snapshot.get("risk_score"):
        phases.append({"phase": "risk_updated", "source": "snapshot"})
    phases.append({"phase": "decision_recorded", "source": "compliance_decisions", "decision_id": decision_id})

    timeline = sorted(
        (snapshot.get("timeline_references") or [])
        + [{"occurred_at": n.get("occurred_at"), "node_id": n.get("node_id"), "summary": n.get("summary")} for n in nodes],
        key=lambda x: x.get("occurred_at") or "",
    )

    payload = {
        "decision_id": decision_id,
        "snapshot_id": snapshot.get("snapshot_id"),
        "phases": phases,
        "timeline": timeline,
        "graph_nodes": nodes,
        "graph_edges": edges,
    }

    return base_envelope(
        service="replay_decision",
        request=request,
        payload=payload,
        authoritative_references=_refs_from_decision(decision, snapshot),
        decision_lineage=_decision_lineage(decision),
        historical_references={
            "snapshot_id": snapshot.get("snapshot_id"),
            "snapshot_timestamp": snapshot.get("snapshot_timestamp"),
        },
    )


def _diff_value(before: Any, after: Any) -> Optional[Dict[str, Any]]:
    if before == after:
        return None
    return {"before": before, "after": after}


async def compare_decision(
    left_decision_id: str,
    right_decision_id: str,
    *,
    actor: ActorContext,
) -> Dict[str, Any]:
    request = {"left_decision_id": left_decision_id, "right_decision_id": right_decision_id}
    left = await decision_storage.get_decision(left_decision_id)
    right = await decision_storage.get_decision(right_decision_id)
    if not left or not right:
        return insufficient("compare_decision", request)
    enforce_decision_tenant(actor, left)
    enforce_decision_tenant(actor, right)
    if left.get("client_id") != right.get("client_id"):
        return insufficient("compare_decision", request, "Decisions belong to different tenants.")

    left_snap = await snapshot_storage.get_snapshot_by_decision(left_decision_id)
    right_snap = await snapshot_storage.get_snapshot_by_decision(right_decision_id)
    if not left_snap or not right_snap:
        return insufficient("compare_decision", request)

    diff: Dict[str, Any] = {}
    for key in ("decision_outcome",):
        d = _diff_value(left.get(key), right.get(key))
        if d:
            diff[key] = d
    cs = _diff_value((left_snap.get("compliance_score") or {}), (right_snap.get("compliance_score") or {}))
    if cs:
        diff["compliance_score"] = cs
    rs = _diff_value((left_snap.get("risk_score") or {}), (right_snap.get("risk_score") or {}))
    if rs:
        diff["risk_score"] = rs
    rv = _diff_value(left.get("rules_version"), right.get("rules_version"))
    if rv:
        diff["rules_version"] = rv
    lv = _diff_value(left.get("legislation_version"), right.get("legislation_version"))
    if lv:
        diff["legislation_version"] = lv

    payload = {
        "left_decision_id": left_decision_id,
        "right_decision_id": right_decision_id,
        "left_snapshot_id": left_snap.get("snapshot_id"),
        "right_snapshot_id": right_snap.get("snapshot_id"),
        "outcome_changed": left.get("decision_outcome") != right.get("decision_outcome"),
        "diff": diff,
        "decision_chain": [left_decision_id, right_decision_id],
    }

    return base_envelope(
        service="compare_decision",
        request=request,
        payload=payload,
        authoritative_references={
            "decision_ids": [left_decision_id, right_decision_id],
            "snapshot_id": right_snap.get("snapshot_id"),
        },
        historical_references={
            "left_snapshot_id": left_snap.get("snapshot_id"),
            "right_snapshot_id": right_snap.get("snapshot_id"),
        },
    )


async def compare_decision_snapshots(
    left_snapshot_id: str,
    right_snapshot_id: str,
    *,
    actor: ActorContext,
) -> Dict[str, Any]:
    request = {"left_snapshot_id": left_snapshot_id, "right_snapshot_id": right_snapshot_id}
    left = await snapshot_storage.get_snapshot(left_snapshot_id)
    right = await snapshot_storage.get_snapshot(right_snapshot_id)
    if not left or not right:
        return insufficient("compare_decision_snapshots", request)
    if left.get("client_id"):
        enforce_tenant_access(actor, client_id=left["client_id"])
    if right.get("client_id") and right.get("client_id") != left.get("client_id"):
        return insufficient("compare_decision_snapshots", request, "Snapshots belong to different tenants.")

    diff: Dict[str, Any] = {}
    for key in ("compliance_score", "risk_score", "applicable_legislation", "rules_version", "evidence_version"):
        d = _diff_value(left.get(key), right.get(key))
        if d:
            diff[key] = d

    payload = {
        "left_snapshot_id": left_snapshot_id,
        "right_snapshot_id": right_snapshot_id,
        "diff": diff,
        "left_snapshot_hash": left.get("snapshot_hash"),
        "right_snapshot_hash": right.get("snapshot_hash"),
    }

    return base_envelope(
        service="compare_decision_snapshots",
        request=request,
        payload=payload,
        historical_references={
            "left_snapshot_id": left_snapshot_id,
            "right_snapshot_id": right_snapshot_id,
        },
    )


async def find_historical_decision(
    *,
    client_id: str,
    as_of: str,
    actor: ActorContext,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    decision_type: Optional[str] = None,
) -> Dict[str, Any]:
    request = {
        "client_id": client_id,
        "as_of": as_of,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "decision_type": decision_type,
    }
    enforce_tenant_access(actor, client_id=client_id)
    decision = await decision_storage.find_decision_at_or_before(
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        as_of=as_of,
        decision_type=decision_type,
    )
    if not decision:
        return insufficient("find_historical_decision", request)

    snapshot = await snapshot_storage.get_snapshot_by_decision(decision["decision_id"])
    payload = {
        "decision_id": decision.get("decision_id"),
        "snapshot_id": decision.get("snapshot_id"),
        "decision_timestamp": decision.get("decision_timestamp"),
        "decision_outcome": decision.get("decision_outcome"),
        "as_of": as_of,
    }
    return base_envelope(
        service="find_historical_decision",
        request=request,
        payload=payload,
        authoritative_references=_refs_from_decision(decision, snapshot),
        historical_references={
            "snapshot_id": decision.get("snapshot_id"),
            "as_of": as_of,
            "resolved_decision_timestamp": decision.get("decision_timestamp"),
        },
    )


async def trace_evidence(
    *,
    anchor_type: str,
    anchor_id: str,
    actor: ActorContext,
    client_id: str,
    limit: int = 50,
) -> Dict[str, Any]:
    request = {"anchor_type": anchor_type, "anchor_id": anchor_id, "client_id": client_id}
    enforce_tenant_access(actor, client_id=client_id)
    decisions = await decision_storage.list_decisions_for_scope(client_id=client_id, limit=limit)
    matched = [
        d
        for d in decisions
        if (d.get("evidence_set") or {}).get("document_ids")
        and anchor_id in ((d.get("evidence_set") or {}).get("document_ids") or [])
    ]
    if not matched and anchor_type == "decision":
        d = await decision_storage.get_decision(anchor_id)
        if d:
            matched = [d]
    if not matched:
        return insufficient("trace_evidence", request)

    payload = {"matches": [{"decision_id": d.get("decision_id"), "summary": d.get("summary")} for d in matched]}
    return base_envelope(
        service="trace_evidence",
        request=request,
        payload=payload,
        authoritative_references={"decision_ids": [d.get("decision_id") for d in matched]},
    )


async def trace_requirement(
    requirement_id: str,
    *,
    actor: ActorContext,
    client_id: str,
    limit: int = 50,
) -> Dict[str, Any]:
    request = {"requirement_id": requirement_id, "client_id": client_id}
    enforce_tenant_access(actor, client_id=client_id)
    decisions = await decision_storage.list_decisions_for_scope(
        client_id=client_id, requirement_id=requirement_id, limit=limit
    )
    if not decisions:
        return insufficient("trace_requirement", request)
    payload = {
        "requirement_id": requirement_id,
        "decisions": [
            {
                "decision_id": d.get("decision_id"),
                "decision_type": d.get("decision_type"),
                "decision_outcome": d.get("decision_outcome"),
                "decision_timestamp": d.get("decision_timestamp"),
            }
            for d in decisions
        ],
    }
    return base_envelope(
        service="trace_requirement",
        request=request,
        payload=payload,
        authoritative_references={"decision_ids": [d.get("decision_id") for d in decisions]},
    )


async def find_decision_dependencies(decision_id: str, *, actor: ActorContext) -> Dict[str, Any]:
    request = {"decision_id": decision_id}
    decision = await decision_storage.get_decision(decision_id)
    if not decision:
        return insufficient("find_decision_dependencies", request)
    enforce_decision_tenant(actor, decision)
    snapshot = await snapshot_storage.get_snapshot_by_decision(decision_id)
    edges = await edge_storage.list_edges_for_decision(decision_id)
    payload = {
        "decision_id": decision_id,
        "rules_version": decision.get("rules_version"),
        "jurisdiction_version": decision.get("jurisdiction_version"),
        "legislation_version": decision.get("legislation_version"),
        "previous_decision_id": decision.get("previous_decision_id"),
        "evidence_set": decision.get("evidence_set"),
        "reasoning_inputs": (snapshot or {}).get("decision_reasoning_inputs"),
        "edges": edges,
    }
    return base_envelope(
        service="find_decision_dependencies",
        request=request,
        payload=payload,
        authoritative_references=_refs_from_decision(decision, snapshot),
        decision_lineage=_decision_lineage(decision),
    )


async def find_affected_properties(decision_id: str, *, actor: ActorContext) -> Dict[str, Any]:
    request = {"decision_id": decision_id}
    decision = await decision_storage.get_decision(decision_id)
    if not decision:
        return insufficient("find_affected_properties", request)
    enforce_decision_tenant(actor, decision)
    pid = decision.get("property_id")
    payload = {"decision_id": decision_id, "property_ids": [pid] if pid else []}
    return base_envelope(service="find_affected_properties", request=request, payload=payload)


async def find_affected_requirements(decision_id: str, *, actor: ActorContext) -> Dict[str, Any]:
    request = {"decision_id": decision_id}
    decision = await decision_storage.get_decision(decision_id)
    if not decision:
        return insufficient("find_affected_requirements", request)
    enforce_decision_tenant(actor, decision)
    rid = decision.get("requirement_id")
    payload = {"decision_id": decision_id, "requirement_ids": [rid] if rid else []}
    return base_envelope(service="find_affected_requirements", request=request, payload=payload)


async def find_missing_evidence(
    *,
    client_id: str,
    actor: ActorContext,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
) -> Dict[str, Any]:
    request = {"client_id": client_id, "property_id": property_id, "requirement_id": requirement_id}
    enforce_tenant_access(actor, client_id=client_id)
    decisions = await decision_storage.list_decisions_for_scope(
        client_id=client_id, property_id=property_id, requirement_id=requirement_id, limit=5
    )
    gaps: List[Dict[str, Any]] = []
    for d in decisions:
        snap = await snapshot_storage.get_snapshot_by_decision(d["decision_id"])
        if not snap:
            continue
        inputs = snap.get("decision_reasoning_inputs") or {}
        missing = inputs.get("missing_dependencies") or inputs.get("missing_evidence") or []
        if missing:
            gaps.append({"decision_id": d["decision_id"], "missing": missing})
    if not gaps:
        return insufficient("find_missing_evidence", request, "No missing evidence recorded in decision snapshots.")
    return base_envelope(service="find_missing_evidence", request=request, payload={"gaps": gaps})


async def find_superseded_evidence(
    *,
    client_id: str,
    actor: ActorContext,
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    request = {"client_id": client_id, "property_id": property_id}
    enforce_tenant_access(actor, client_id=client_id)
    decisions = await decision_storage.list_decisions_for_scope(client_id=client_id, property_id=property_id, limit=20)
    superseded: List[Dict[str, Any]] = []
    for d in decisions:
        snap = await snapshot_storage.get_snapshot_by_decision(d["decision_id"])
        if not snap:
            continue
        ev = snap.get("evidence_version") or {}
        for item in ev.get("documents_superseded") or []:
            superseded.append({"decision_id": d["decision_id"], **item})
    if not superseded:
        return insufficient("find_superseded_evidence", request)
    return base_envelope(service="find_superseded_evidence", request=request, payload={"superseded": superseded})


async def trace_operational_impact(decision_id: str, *, actor: ActorContext) -> Dict[str, Any]:
    request = {"decision_id": decision_id}
    decision = await decision_storage.get_decision(decision_id)
    if not decision:
        return insufficient("trace_operational_impact", request)
    enforce_decision_tenant(actor, decision)
    snapshot = await snapshot_storage.get_snapshot_by_decision(decision_id)
    op = (snapshot or {}).get("operational_context") or {}
    payload = {
        "decision_id": decision_id,
        "correlation_id": decision.get("operational_correlation_id"),
        "operational_context": op,
    }
    return base_envelope(
        service="trace_operational_impact",
        request=request,
        payload=payload,
        operational_references={
            "correlation_id": decision.get("operational_correlation_id"),
            "operational_event_ids": op.get("operational_event_ids") or [],
        },
    )
