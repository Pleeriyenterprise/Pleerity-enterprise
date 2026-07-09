"""
Compliance Engine consumer adapter — Graph Service read path (Phase 3).

Routes compliance explain/replay requests through Graph Service when a decision
exists for the scoped object. Never imports graph storage outside service layer.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_evidence_graph.config import graph_admin_consumers_enabled, graph_consumers_enabled
from services.compliance_graph_service.access import ActorContext
from services.compliance_graph_service import service as graph_service
from services.compliance_graph_service.envelopes import insufficient


async def explain_for_scope(
    *,
    scope_type: str,
    scope_id: str,
    client_id: str,
    actor: ActorContext,
) -> Dict[str, Any]:
    """Object-scoped explain wrapper for Explain This panel."""
    if not graph_admin_consumers_enabled():
        return insufficient(
            "explain_for_scope",
            {"scope_type": scope_type, "scope_id": scope_id, "client_id": client_id},
            reason="Graph consumers disabled (COMPLIANCE_EVIDENCE_GRAPH_MODE not shadow/enabled).",
        )

    if scope_type == "decision":
        return await graph_service.explain_decision(scope_id, actor=actor)

    from services.compliance_evidence_graph.storage import decisions as decision_storage

    q_kwargs: Dict[str, Any] = {"client_id": client_id, "limit": 1}
    if scope_type == "requirement":
        q_kwargs["requirement_id"] = scope_id
    elif scope_type == "property":
        q_kwargs["property_id"] = scope_id
    else:
        return insufficient(
            "explain_for_scope",
            {"scope_type": scope_type, "scope_id": scope_id},
            reason=f"Unsupported scope_type: {scope_type}",
        )

    rows = await decision_storage.list_decisions_for_scope(**q_kwargs)
    if not rows:
        return insufficient(
            "explain_for_scope",
            {"scope_type": scope_type, "scope_id": scope_id, "client_id": client_id},
            reason="No compliance decision recorded for this scope.",
        )
    return await graph_service.explain_decision(rows[0]["decision_id"], actor=actor)


async def enrich_admin_compliance_explain(
    explain_payload: Dict[str, Any],
    *,
    client_id: str,
    actor: Optional[ActorContext] = None,
) -> Dict[str, Any]:
    """
    Augment admin KPI explain with latest graph-backed score decision when enabled.
    Called from compliance_explain_admin_service when graph_consumers_enabled().
    """
    if not graph_consumers_enabled():
        explain_payload["graph_service"] = {"enabled": False}
        return explain_payload

    admin_actor = actor or ActorContext(is_admin=True, client_id=client_id)
    from services.compliance_evidence_graph.storage import decisions as decision_storage

    score_decisions = await decision_storage.list_decisions_for_scope(
        client_id=client_id,
        decision_type="compliance_score_change",
        limit=1,
    )
    if not score_decisions:
        explain_payload["graph_service"] = {"enabled": True, "latest_score_decision": None}
        return explain_payload

    did = score_decisions[0].get("decision_id")
    if not did:
        explain_payload["graph_service"] = {"enabled": True, "latest_score_decision": None}
        return explain_payload

    envelope = await graph_service.explain_decision(did, actor=admin_actor)
    explain_payload["graph_service"] = {
        "enabled": True,
        "latest_score_decision": {
            "decision_id": did,
            "insufficient_evidence": envelope.get("insufficient_evidence"),
            "executive_summary": (envelope.get("payload") or {}).get("executive_summary"),
            "authoritative_references": envelope.get("authoritative_references"),
        },
    }
    return explain_payload
