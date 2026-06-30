"""CIE orchestrator — routes to domain engines when enabled."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence_engine.config import intelligence_engine_enabled
from services.compliance_intelligence_engine.constants import ENGINE_VERSION
from services.compliance_intelligence_engine.envelopes import attach_response_hash, build_stub_envelope
from services.compliance_intelligence_engine.engines.priority.engine import generate_priority_assessment
from services.compliance_intelligence_engine.engines.recommendation.engine import generate_recommendations
from services.compliance_intelligence_engine.schema import IntelligenceScope
from services.compliance_intelligence_engine.storage import artefacts as artefact_storage
from services.compliance_intelligence_engine.storage import provenance as provenance_storage


def unavailable_envelope(
    *,
    service: str,
    reason: str = "COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED",
    artefact_type: Optional[str] = None,
) -> Dict[str, Any]:
    return build_stub_envelope(
        service=service,
        enabled=False,
        insufficient_evidence=True,
        reason=reason,
        artefact_type=artefact_type,
    )


def not_implemented_envelope(
    *,
    service: str,
    artefact_type: Optional[str] = None,
) -> Dict[str, Any]:
    return build_stub_envelope(
        service=service,
        enabled=True,
        insufficient_evidence=True,
        reason="CIE_DOMAIN_ENGINE_NOT_IMPLEMENTED",
        artefact_type=artefact_type,
    )


async def dispatch_generate(
    *,
    service: str,
    artefact_type: Optional[str],
    scope: IntelligenceScope,
    actor: Optional[ActorContext] = None,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope(service=service, artefact_type=artefact_type)
    if actor is None:
        from services.compliance_graph_service.access import ActorContext as AC

        actor = AC(is_admin=True, client_id=scope.client_id)

    if service in ("generate_recommendations",) or artefact_type == "recommendation":
        return await generate_recommendations(scope=scope, actor=actor)
    if service in ("generate_priority_assessment",) or artefact_type == "priority_assessment":
        return await generate_priority_assessment(scope=scope, actor=actor)

    return not_implemented_envelope(service=service, artefact_type=artefact_type)


async def dispatch_list(
    *,
    client_id: str,
    artefact_type: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope(service="list_intelligence", artefact_type=artefact_type)
    artefacts = await artefact_storage.list_artefacts(
        client_id=client_id,
        artefact_type=artefact_type,
        lifecycle_state=lifecycle_state,
        active_only=active_only,
        limit=limit,
    )
    body = {
        "service": "list_intelligence",
        "enabled": True,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": len(artefacts) == 0,
        "reason": "NO_ARTEFACTS" if not artefacts else None,
        "artefact_type": artefact_type,
        "artefacts": artefacts,
        "authoritative_references": {
            "artefact_ids": [a["artefact_id"] for a in artefacts],
            "provenance_ids": [a.get("provenance_id") for a in artefacts if a.get("provenance_id")],
            "decision_ids": [],
            "snapshot_ids": [],
        },
        "tier1": {"count": len(artefacts)},
        "tier2": None,
    }
    return attach_response_hash(body)


async def dispatch_get(
    *,
    artefact_id: str,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope(service="get_intelligence")
    artefact = await artefact_storage.find_artefact_by_id(artefact_id, client_id=client_id)
    if not artefact:
        body = {
            "service": "get_intelligence",
            "enabled": True,
            "engine_version": ENGINE_VERSION,
            "insufficient_evidence": True,
            "reason": "ARTEFACT_NOT_FOUND",
            "artefact_id": artefact_id,
            "artefacts": [],
            "authoritative_references": {
                "artefact_ids": [],
                "provenance_ids": [],
                "decision_ids": [],
                "snapshot_ids": [],
            },
            "tier1": None,
            "tier2": None,
        }
        return attach_response_hash(body)
    body = {
        "service": "get_intelligence",
        "enabled": True,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": artefact.get("insufficient_evidence", False),
        "reason": None,
        "artefact_id": artefact_id,
        "provenance_id": artefact.get("provenance_id"),
        "artefact_type": artefact.get("artefact_type"),
        "artefacts": [artefact],
        "authoritative_references": {
            "artefact_ids": [artefact_id],
            "provenance_ids": [artefact.get("provenance_id")] if artefact.get("provenance_id") else [],
            "decision_ids": list(artefact.get("source_decision_ids") or []),
            "snapshot_ids": list(artefact.get("source_snapshot_ids") or []),
        },
        "tier1": artefact.get("payload"),
        "tier2": None,
    }
    return attach_response_hash(body)


async def dispatch_explain(
    *,
    artefact_id: str,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope(service="explain_intelligence")
    artefact = await artefact_storage.find_artefact_by_id(artefact_id, client_id=client_id)
    if not artefact:
        body = {
            "service": "explain_intelligence",
            "enabled": True,
            "engine_version": ENGINE_VERSION,
            "insufficient_evidence": True,
            "reason": "ARTEFACT_NOT_FOUND",
            "artefact_id": artefact_id,
            "artefacts": [],
            "authoritative_references": {
                "artefact_ids": [],
                "provenance_ids": [],
                "decision_ids": [],
                "snapshot_ids": [],
            },
            "tier1": None,
            "tier2": None,
        }
        return attach_response_hash(body)
    provenance = await provenance_storage.find_provenance_by_artefact_id(
        artefact_id, client_id=client_id or artefact.get("client_id")
    )
    explainability = artefact.get("explainability") or {}
    tier1 = {
        "artefact_id": artefact_id,
        "artefact_type": artefact.get("artefact_type"),
        "why_exists": explainability.get("why_exists"),
        "assumptions": explainability.get("assumptions", []),
        "generation_reason": (artefact.get("payload") or {}).get("generation_reason"),
        "priority_score_breakdown": (artefact.get("payload") or {}).get("priority_score_breakdown"),
        "provenance_id": artefact.get("provenance_id"),
        "trace_hash": (provenance or {}).get("trace_hash"),
        "weight_set_version": (provenance or {}).get("weight_set_version"),
        "deterministic": True,
    }
    body = {
        "service": "explain_intelligence",
        "enabled": True,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": False,
        "reason": None,
        "artefact_id": artefact_id,
        "provenance_id": artefact.get("provenance_id"),
        "artefact_type": artefact.get("artefact_type"),
        "artefacts": [artefact],
        "authoritative_references": {
            "artefact_ids": [artefact_id],
            "provenance_ids": [artefact.get("provenance_id")] if artefact.get("provenance_id") else [],
            "decision_ids": list(artefact.get("source_decision_ids") or []),
            "snapshot_ids": list(artefact.get("source_snapshot_ids") or []),
        },
        "tier1": tier1,
        "tier2": None,
    }
    return attach_response_hash(body)


async def dispatch_get_provenance(
    *,
    artefact_id: str,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope(service="get_intelligence_provenance")
    artefact = await artefact_storage.find_artefact_by_id(artefact_id, client_id=client_id)
    if not artefact:
        body = {
            "service": "get_intelligence_provenance",
            "enabled": True,
            "engine_version": ENGINE_VERSION,
            "insufficient_evidence": True,
            "reason": "ARTEFACT_NOT_FOUND",
            "artefact_id": artefact_id,
            "artefacts": [],
            "authoritative_references": {
                "artefact_ids": [],
                "provenance_ids": [],
                "decision_ids": [],
                "snapshot_ids": [],
            },
            "tier1": None,
            "tier2": None,
        }
        return attach_response_hash(body)
    provenance = await provenance_storage.find_provenance_by_artefact_id(
        artefact_id, client_id=client_id or artefact.get("client_id")
    )
    if not provenance:
        body = {
            "service": "get_intelligence_provenance",
            "enabled": True,
            "engine_version": ENGINE_VERSION,
            "insufficient_evidence": True,
            "reason": "PROVENANCE_NOT_FOUND",
            "artefact_id": artefact_id,
            "artefacts": [],
            "authoritative_references": {"artefact_ids": [artefact_id], "provenance_ids": [], "decision_ids": [], "snapshot_ids": []},
            "tier1": None,
            "tier2": None,
        }
        return attach_response_hash(body)
    body = {
        "service": "get_intelligence_provenance",
        "enabled": True,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": False,
        "reason": None,
        "artefact_id": artefact_id,
        "provenance_id": provenance.get("provenance_id"),
        "artefact_type": artefact.get("artefact_type"),
        "artefacts": [],
        "authoritative_references": {
            "artefact_ids": [artefact_id],
            "provenance_ids": [provenance["provenance_id"]],
            "decision_ids": list(provenance.get("decision_ids_used") or []),
            "snapshot_ids": list(provenance.get("snapshot_ids_used") or []),
        },
        "tier1": provenance,
        "tier2": None,
    }
    return attach_response_hash(body)
