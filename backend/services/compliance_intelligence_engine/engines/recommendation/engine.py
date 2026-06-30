"""Recommendation Engine — deterministic CIE-2."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence_engine.constants import (
    DETERMINISTIC_VERSION,
    ENGINE_VERSION,
    TEMPLATE_VERSION_DEFAULT,
)
from services.compliance_intelligence_engine.engines.priority.scoring import (
    compute_priority_score,
    expiry_proximity_raw,
    regulatory_exposure_raw,
)
from services.compliance_intelligence_engine.engines.recommendation.templates import normalize_gaps
from services.compliance_intelligence_engine.envelopes import attach_response_hash
from services.compliance_intelligence_engine.hashing import artefact_response_hash, envelope_hash
from services.compliance_intelligence_engine.ids import new_artefact_id
from services.compliance_intelligence_engine.persist import persist_artefact_with_provenance
from services.compliance_intelligence_engine.provenance_writer import (
    artefact_inputs_hash,
    build_calculation_trace,
    build_provenance_record,
)
from services.compliance_intelligence_engine.read_adapter import fetch_graph_envelope
from services.compliance_intelligence_engine.schema import IntelligenceScope
from services.compliance_intelligence_engine.storage import artefacts as artefact_storage


def _graph_response_hash(graph_env: Dict[str, Any]) -> Optional[str]:
    if not graph_env:
        return None
    body = {k: v for k, v in graph_env.items() if k not in ("generated_at",)}
    return envelope_hash(body)


def _build_recommendation_payload(
    *,
    artefact_id: str,
    client_id: str,
    scope: IntelligenceScope,
    template: Dict[str, Any],
    decision_id: str,
    priority_score: float,
    priority_band: str,
    priority_rank: int,
    factors: List[Dict[str, Any]],
    gap_item: Any,
) -> Dict[str, Any]:
    req_id = scope.requirement_id
    prop_id = scope.property_id
    evidence_ids: List[str] = []
    if isinstance(gap_item, dict) and gap_item.get("document_id"):
        evidence_ids.append(str(gap_item["document_id"]))
    return {
        "recommendation_id": artefact_id,
        "recommendation_type": template["recommendation_type"],
        "recommendation_version": 1,
        "status": "generated",
        "client_id": client_id,
        "property_id": prop_id,
        "requirement_id": req_id,
        "priority_band": priority_band,
        "priority_score": priority_score,
        "priority_rank": priority_rank,
        "title": template["title"],
        "action_summary": template["action_summary"],
        "generation_reason": {
            "code": template["reason_code"],
            "narrative": f"Deterministic template match for gap in decision {decision_id}",
            "decision_ids": [decision_id],
            "snapshot_ids": [],
        },
        "evidence": [],
        "evidence_ids": evidence_ids,
        "applicable_legislation": [],
        "applicable_rules": [],
        "dependencies": {
            "prerequisite_recommendation_ids": [],
            "prerequisite_requirement_ids": [req_id] if req_id else [],
            "blocked_by": [],
            "blocks": [],
        },
        "expected_outcome": {
            "compliance_state": "requirement_satisfied",
            "score_delta_estimate": 0,
            "risk_delta_estimate": 0,
        },
        "priority_score_breakdown": factors,
    }


async def generate_recommendations(
    *,
    scope: IntelligenceScope,
    actor: ActorContext,
) -> Dict[str, Any]:
    client_id = scope.client_id
    graph_env = await fetch_graph_envelope(
        method="find_missing_evidence",
        params={
            "client_id": client_id,
            "property_id": scope.property_id,
            "requirement_id": scope.requirement_id,
        },
        actor=actor,
        client_id=client_id,
    )
    graph_hash = _graph_response_hash(graph_env)
    gap_candidates = normalize_gaps(graph_env)

    if not gap_candidates:
        body = {
            "service": "generate_recommendations",
            "enabled": True,
            "engine_version": ENGINE_VERSION,
            "insufficient_evidence": True,
            "reason": "NO_RECOMMENDATION_GAPS",
            "artefact_type": "recommendation",
            "artefacts": [],
            "graph_service_response_hash": graph_hash,
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

    artefacts_out: List[Dict[str, Any]] = []
    provenance_ids: List[str] = []
    decision_ids: List[str] = []

    for rank, cand in enumerate(gap_candidates, start=1):
        decision_id = cand["decision_id"]
        template = cand["template"]
        dedupe_key = (
            f"recommendation:{template['recommendation_type']}:{scope.requirement_id or scope.property_id or client_id}"
        )
        existing = await artefact_storage.find_active_by_dedupe_key(
            client_id=client_id, dedupe_key=dedupe_key, artefact_type="recommendation"
        )
        if existing:
            artefacts_out.append(existing)
            provenance_ids.append(existing.get("provenance_id", ""))
            decision_ids.append(decision_id)
            continue

        factors = [
            {
                "factor_id": "regulatory_exposure",
                "raw_score": regulatory_exposure_raw(template.get("regulatory_severity", "contractual")),
                "decision_ids": [decision_id],
                "evidence_refs": [],
            },
            {
                "factor_id": "expiry_proximity",
                "raw_score": expiry_proximity_raw(None),
                "decision_ids": [decision_id],
                "evidence_refs": [],
            },
            {
                "factor_id": "missing_evidence_criticality",
                "raw_score": 85.0,
                "decision_ids": [decision_id],
                "evidence_refs": [],
            },
        ]
        priority_score, weighted_factors, priority_band = compute_priority_score(factors=factors)

        artefact_id = new_artefact_id()
        scope_dict = scope.model_dump()
        ih = artefact_inputs_hash(
            artefact_type="recommendation",
            scope=scope_dict,
            source_decision_ids=[decision_id],
            source_snapshot_ids=[],
            extra={"dedupe_key": dedupe_key, "recommendation_type": template["recommendation_type"]},
        )
        payload = _build_recommendation_payload(
            artefact_id=artefact_id,
            client_id=client_id,
            scope=scope,
            template=template,
            decision_id=decision_id,
            priority_score=priority_score,
            priority_band=priority_band,
            priority_rank=rank,
            factors=weighted_factors,
            gap_item=cand.get("gap_item"),
        )
        artefact_body = {
            "artefact_id": artefact_id,
            "artefact_type": "recommendation",
            "artefact_version": 1,
            "generated_at": datetime.now(timezone.utc),
            "client_id": client_id,
            "scope": scope_dict,
            "engine_version": ENGINE_VERSION,
            "template_version": TEMPLATE_VERSION_DEFAULT,
            "deterministic_version": DETERMINISTIC_VERSION,
            "inputs_hash": ih,
            "source_decision_ids": [decision_id],
            "source_snapshot_ids": [],
            "lifecycle_state": "validated",
            "insufficient_evidence": False,
            "payload": payload,
            "dedupe_key": dedupe_key,
            "explainability": {
                "why_exists": template["action_summary"],
                "assumptions": [{"assumption_id": "template_v1", "template_ref": template["recommendation_type"]}],
            },
        }
        artefact_body["response_hash"] = artefact_response_hash(artefact_body)
        trace = build_calculation_trace(
            inputs_hash_value=ih,
            stages_extra=[
                {
                    "stage": "priority_calculation",
                    "stage_version": "priority_v1",
                    "input_hash": ih,
                    "output_hash": artefact_body["response_hash"],
                    "registry_refs": {"weight_set_version": "weights_v1.0.0"},
                    "metadata": {"priority_score": priority_score, "priority_band": priority_band},
                },
                {
                    "stage": "artefact_generation",
                    "stage_version": "recommendation_v1",
                    "input_hash": ih,
                    "output_hash": artefact_body["response_hash"],
                    "metadata": {"recommendation_type": template["recommendation_type"]},
                },
            ],
        )
        provenance = build_provenance_record(
            artefact=artefact_body,
            graph_response_hash=graph_hash,
            algorithm_version="recommendation_algorithm_v1",
            calculation_trace=trace,
        )
        artefact_body["provenance_id"] = provenance["provenance_id"]
        artefact_body["response_hash"] = artefact_response_hash(artefact_body)
        provenance["response_hash"] = artefact_body["response_hash"]

        artefact, prov = await persist_artefact_with_provenance(artefact=artefact_body, provenance=provenance)
        artefacts_out.append(artefact)
        provenance_ids.append(prov["provenance_id"])
        decision_ids.append(decision_id)

    body = {
        "service": "generate_recommendations",
        "enabled": True,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": False,
        "reason": None,
        "artefact_type": "recommendation",
        "artefacts": artefacts_out,
        "graph_service_response_hash": graph_hash,
        "authoritative_references": {
            "artefact_ids": [a["artefact_id"] for a in artefacts_out],
            "provenance_ids": [p for p in provenance_ids if p],
            "decision_ids": decision_ids,
            "snapshot_ids": [],
        },
        "tier1": {"count": len(artefacts_out)},
        "tier2": None,
    }
    return attach_response_hash(body)
