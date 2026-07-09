"""Governed Graph Service read adapter — CIE consumes Graph Service only."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_graph_service import service as graph_service
from services.compliance_graph_service.access import ActorContext


async def fetch_graph_envelope(
    *,
    method: str,
    params: Dict[str, Any],
    actor: ActorContext,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch to Graph Service; never touches CEG storage directly."""
    cid = client_id or params.get("client_id") or actor.client_id
    m = (method or "").strip().lower()

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
    if m == "explain_decision":
        return await graph_service.explain_decision(params["decision_id"], actor=actor)
    if m == "find_decision_dependencies":
        return await graph_service.find_decision_dependencies(params["decision_id"], actor=actor)

    return {
        "service": method,
        "insufficient_evidence": True,
        "payload": {"reason": f"Unsupported graph method: {method}"},
        "status": "insufficient",
    }
