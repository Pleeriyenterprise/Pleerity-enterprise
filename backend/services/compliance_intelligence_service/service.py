"""Intelligence Service Layer — public consumer API."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence_engine.comparison import dispatch_compare
from services.compliance_intelligence_engine.config import intelligence_engine_enabled
from services.compliance_intelligence_engine.orchestrator import (
    dispatch_explain,
    dispatch_generate,
    dispatch_get,
    dispatch_get_provenance,
    dispatch_list,
)
from services.compliance_intelligence_engine.replay import dispatch_replay
from services.compliance_intelligence_engine.schema import IntelligenceScope
from services.compliance_intelligence_service.access import resolve_client_id
from services.compliance_intelligence_service.envelopes import not_implemented_envelope, unavailable_envelope


async def _stub_dispatch(
    service: str,
    actor: ActorContext,
    *,
    client_id: Optional[str] = None,
    artefact_type: Optional[str] = None,
    scope_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cid = resolve_client_id(actor, client_id)
    scope = IntelligenceScope(client_id=cid, **(scope_kwargs or {}))
    return await dispatch_generate(service=service, artefact_type=artefact_type, scope=scope, actor=actor)


async def generate_intelligence(
    *,
    artefact_type: str,
    actor: ActorContext,
    client_id: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return await _stub_dispatch(
        "generate_intelligence",
        actor,
        client_id=client_id,
        artefact_type=artefact_type,
        scope_kwargs=params,
    )


async def generate_recommendations(
    *, actor: ActorContext, client_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return await _stub_dispatch(
        "generate_recommendations",
        actor,
        client_id=client_id,
        artefact_type="recommendation",
        scope_kwargs=params,
    )


async def generate_priority_assessment(
    *, actor: ActorContext, client_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return await _stub_dispatch(
        "generate_priority_assessment",
        actor,
        client_id=client_id,
        artefact_type="priority_assessment",
        scope_kwargs=params,
    )


async def generate_portfolio_insights(
    *, actor: ActorContext, client_id: Optional[str] = None, as_of: Optional[str] = None
) -> Dict[str, Any]:
    return await _stub_dispatch(
        "generate_portfolio_insights",
        actor,
        client_id=client_id,
        artefact_type="portfolio_insight",
        scope_kwargs={"as_of": as_of} if as_of else None,
    )


async def generate_decision_impact(
    *, artefact_id: Optional[str], actor: ActorContext, client_id: Optional[str] = None
) -> Dict[str, Any]:
    return await _stub_dispatch(
        "generate_decision_impact",
        actor,
        client_id=client_id,
        artefact_type="decision_impact_assessment",
    )


async def generate_regulatory_impact(
    *, rule_change_event: Dict[str, Any], actor: ActorContext
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope("generate_regulatory_impact", artefact_type="regulatory_impact_assessment")
    return not_implemented_envelope("generate_regulatory_impact", artefact_type="regulatory_impact_assessment")


async def generate_forecast(
    *, actor: ActorContext, client_id: Optional[str] = None, window_days: int = 30
) -> Dict[str, Any]:
    return await _stub_dispatch(
        "generate_forecast",
        actor,
        client_id=client_id,
        artefact_type="workload_forecast",
    )


async def generate_readiness(
    *, actor: ActorContext, client_id: Optional[str] = None, kind: str = "audit"
) -> Dict[str, Any]:
    artefact_type = "audit_readiness_assessment" if kind == "audit" else "insurance_readiness_assessment"
    return await _stub_dispatch(
        "generate_readiness",
        actor,
        client_id=client_id,
        artefact_type=artefact_type,
    )


async def generate_dependency_chain(
    *,
    anchor_type: str,
    anchor_id: str,
    actor: ActorContext,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    return await _stub_dispatch(
        "generate_dependency_chain",
        actor,
        client_id=client_id,
        artefact_type="dependency_chain",
    )


async def generate_remediation_strategy(
    *, actor: ActorContext, client_id: Optional[str] = None
) -> Dict[str, Any]:
    return await _stub_dispatch(
        "generate_remediation_strategy",
        actor,
        client_id=client_id,
        artefact_type="remediation_strategy",
    )


async def list_intelligence(
    *,
    actor: ActorContext,
    client_id: Optional[str] = None,
    artefact_type: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    active_only: bool = True,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope("list_intelligence", artefact_type=artefact_type)
    cid = resolve_client_id(actor, client_id)
    return await dispatch_list(
        client_id=cid,
        artefact_type=artefact_type,
        lifecycle_state=lifecycle_state,
        active_only=active_only,
    )


async def get_intelligence(*, artefact_id: str, actor: ActorContext) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope("get_intelligence")
    cid = resolve_client_id(actor, None) if not actor.is_admin else None
    return await dispatch_get(artefact_id=artefact_id, client_id=cid)


async def compare_intelligence(
    *, left_id: str, right_id: str, actor: ActorContext, compare_mode: str = "full"
) -> Dict[str, Any]:
    resolve_client_id(actor, None)
    return await dispatch_compare(left_id=left_id, right_id=right_id, compare_mode=compare_mode)


async def explain_intelligence(*, artefact_id: str, actor: ActorContext) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope("explain_intelligence")
    cid = resolve_client_id(actor, None) if not actor.is_admin else None
    return await dispatch_explain(artefact_id=artefact_id, client_id=cid)


async def get_intelligence_lifecycle(*, artefact_id: str, actor: ActorContext) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope("get_intelligence_lifecycle")
    return not_implemented_envelope("get_intelligence_lifecycle")


async def transition_intelligence(
    *,
    artefact_id: str,
    to_state: str,
    actor: ActorContext,
    reason_code: str,
    reason_summary: Optional[str] = None,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope("transition_intelligence")
    return not_implemented_envelope("transition_intelligence")


async def get_intelligence_provenance(*, artefact_id: str, actor: ActorContext) -> Dict[str, Any]:
    resolve_client_id(actor, None)
    if not intelligence_engine_enabled():
        return unavailable_envelope("get_intelligence_provenance")
    cid = resolve_client_id(actor, None) if not actor.is_admin else None
    return await dispatch_get_provenance(artefact_id=artefact_id, client_id=cid)


async def replay_intelligence(
    *,
    actor: ActorContext,
    replay_type: str,
    provenance_id: Optional[str] = None,
    as_of: Optional[str] = None,
    artefact_type: Optional[str] = None,
    engine_version: Optional[str] = None,
    client_id: Optional[str] = None,
    persist_result: bool = False,
) -> Dict[str, Any]:
    cid = resolve_client_id(actor, client_id)
    return await dispatch_replay(
        replay_type=replay_type,
        provenance_id=provenance_id,
        as_of=as_of,
        artefact_type=artefact_type,
        engine_version=engine_version,
        client_id=cid,
        persist_result=persist_result,
    )
