"""Dispatch intelligence intents to Graph Service methods (never storage)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_graph_service.access import ActorContext
from services.compliance_graph_service import service as graph_service


async def dispatch_graph_method(
    *,
    method: str,
    params: Dict[str, Any],
    actor: ActorContext,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    cid = client_id or params.get("client_id") or actor.client_id
    m = (method or "").strip().lower()

    if m == "explain_decision":
        return await graph_service.explain_decision(params["decision_id"], actor=actor)
    if m == "replay_decision":
        return await graph_service.replay_decision(params["decision_id"], actor=actor)
    if m == "compare_decision":
        return await graph_service.compare_decision(params["left"], params["right"], actor=actor)
    if m == "compare_decision_snapshots":
        return await graph_service.compare_decision_snapshots(params["left"], params["right"], actor=actor)
    if m == "find_historical_decision":
        return await graph_service.find_historical_decision(
            client_id=cid,
            as_of=params["as_of"],
            actor=actor,
            property_id=params.get("property_id"),
            requirement_id=params.get("requirement_id"),
            decision_type=params.get("decision_type"),
        )
    if m == "trace_evidence":
        return await graph_service.trace_evidence(
            anchor_type=params["anchor_type"],
            anchor_id=params["anchor_id"],
            actor=actor,
            client_id=cid,
            limit=int(params.get("limit") or 50),
        )
    if m == "trace_requirement":
        return await graph_service.trace_requirement(
            params["requirement_id"],
            actor=actor,
            client_id=cid,
            limit=int(params.get("limit") or 50),
        )
    if m == "find_decision_dependencies":
        return await graph_service.find_decision_dependencies(params["decision_id"], actor=actor)
    if m == "find_affected_properties":
        return await graph_service.find_affected_properties(params["decision_id"], actor=actor)
    if m == "find_affected_requirements":
        return await graph_service.find_affected_requirements(params["decision_id"], actor=actor)
    if m == "find_missing_evidence":
        return await graph_service.find_missing_evidence(
            client_id=cid,
            actor=actor,
            property_id=params.get("property_id"),
            requirement_id=params.get("requirement_id"),
        )
    if m == "find_superseded_evidence":
        return await graph_service.find_superseded_evidence(
            client_id=cid,
            actor=actor,
            property_id=params.get("property_id"),
        )
    if m == "trace_operational_impact":
        return await graph_service.trace_operational_impact(params["decision_id"], actor=actor)
    if m == "list_decisions":
        return await graph_service.list_decisions(
            actor=actor,
            client_id=cid,
            property_id=params.get("property_id"),
            requirement_id=params.get("requirement_id"),
            decision_type=params.get("decision_type"),
            since=params.get("since"),
            until=params.get("until"),
            limit=int(params.get("limit") or 50),
        )

    return {
        "service": method,
        "insufficient_evidence": True,
        "payload": {"reason": f"Unsupported graph method: {method}"},
        "status": "insufficient",
    }
