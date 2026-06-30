"""Priority Engine — deterministic priority assessments (CIE-2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence_engine.constants import (
    DETERMINISTIC_VERSION,
    ENGINE_VERSION,
    TEMPLATE_VERSION_DEFAULT,
)
from services.compliance_intelligence_engine.engines.priority.scoring import compute_priority_score, score_to_band
from services.compliance_intelligence_engine.envelopes import attach_response_hash
from services.compliance_intelligence_engine.hashing import artefact_response_hash
from services.compliance_intelligence_engine.ids import new_artefact_id
from services.compliance_intelligence_engine.persist import persist_artefact_with_provenance
from services.compliance_intelligence_engine.provenance_writer import (
    artefact_inputs_hash,
    build_calculation_trace,
    build_provenance_record,
)
from services.compliance_intelligence_engine.registry.loader import registry_pins_for_recommendation
from services.compliance_intelligence_engine.schema import IntelligenceScope
from services.compliance_intelligence_engine.storage import artefacts as artefact_storage


async def generate_priority_assessment(
    *,
    scope: IntelligenceScope,
    actor: ActorContext,
) -> Dict[str, Any]:
    client_id = scope.client_id
    recommendations = await artefact_storage.list_artefacts(
        client_id=client_id,
        artefact_type="recommendation",
        active_only=True,
        limit=100,
    )
    if scope.property_id:
        recommendations = [r for r in recommendations if (r.get("scope") or {}).get("property_id") == scope.property_id]
    if scope.requirement_id:
        recommendations = [
            r for r in recommendations if (r.get("scope") or {}).get("requirement_id") == scope.requirement_id
        ]

    items: List[Dict[str, Any]] = []
    for rank, rec in enumerate(
        sorted(recommendations, key=lambda r: -(r.get("payload") or {}).get("priority_score", 0)), start=1
    ):
        payload = rec.get("payload") or {}
        items.append(
            {
                "object_type": "recommendation",
                "object_id": rec["artefact_id"],
                "priority_score": payload.get("priority_score", 0),
                "priority_band": payload.get("priority_band", "low"),
                "priority_rank": rank,
                "reason_summary": payload.get("title", ""),
                "factors": payload.get("priority_score_breakdown", []),
                "affected_decisions": rec.get("source_decision_ids", []),
            }
        )

    if not items and not recommendations:
        body = {
            "service": "generate_priority_assessment",
            "enabled": True,
            "engine_version": ENGINE_VERSION,
            "insufficient_evidence": True,
            "reason": "NO_PRIORITY_ITEMS",
            "artefact_type": "priority_assessment",
            "artefacts": [],
            "authoritative_references": {"artefact_ids": [], "provenance_ids": [], "decision_ids": [], "snapshot_ids": []},
            "tier1": None,
            "tier2": None,
        }
        return attach_response_hash(body)

    scope_dict = scope.model_dump()
    source_ids = [r["artefact_id"] for r in recommendations]
    source_decision_ids = sorted(
        {
            did
            for r in recommendations
            for did in (r.get("source_decision_ids") or [])
        }
    )
    ih = artefact_inputs_hash(
        artefact_type="priority_assessment",
        scope=scope_dict,
        source_decision_ids=source_decision_ids,
        source_snapshot_ids=[],
        extra={"source_artefact_ids": sorted(source_ids)},
    )
    artefact_id = new_artefact_id()
    assessment_payload = {
        "snapshot_id": f"pri_snap_{artefact_id[4:12]}",
        "client_id": client_id,
        "scope": "portfolio" if scope.portfolio_root else "property",
        "items": items,
        "weights_version": "weights_v1.0.0",
        "inputs_hash": ih,
    }
    artefact_body = {
        "artefact_id": artefact_id,
        "artefact_type": "priority_assessment",
        "artefact_version": 1,
        "generated_at": datetime.now(timezone.utc),
        "client_id": client_id,
        "scope": scope_dict,
        "engine_version": ENGINE_VERSION,
        "template_version": TEMPLATE_VERSION_DEFAULT,
        "deterministic_version": DETERMINISTIC_VERSION,
        "inputs_hash": ih,
        "source_decision_ids": source_decision_ids,
        "source_snapshot_ids": [],
        "lifecycle_state": "validated",
        "insufficient_evidence": False,
        "payload": assessment_payload,
        "dedupe_key": f"priority_assessment:{client_id}:{scope.property_id or 'portfolio'}",
    }
    artefact_body["response_hash"] = artefact_response_hash(artefact_body)
    trace = build_calculation_trace(
        inputs_hash_value=ih,
        stages_extra=[
            {
                "stage": "priority_calculation",
                "stage_version": "priority_assessment_v1",
                "input_hash": ih,
                "output_hash": artefact_body["response_hash"],
                "registry_refs": {"weight_set_version": "weights_v1.0.0"},
                "metadata": {"item_count": len(items)},
            }
        ],
    )
    provenance = build_provenance_record(
        artefact=artefact_body,
        graph_response_hash=None,
        algorithm_version="priority_algorithm_v1",
        calculation_trace=trace,
        strategy_pins=registry_pins_for_recommendation(),
    )
    artefact_body["provenance_id"] = provenance["provenance_id"]
    artefact_body["response_hash"] = artefact_response_hash(artefact_body)
    provenance["response_hash"] = artefact_body["response_hash"]
    artefact, prov = await persist_artefact_with_provenance(artefact=artefact_body, provenance=provenance)

    body = {
        "service": "generate_priority_assessment",
        "enabled": True,
        "engine_version": ENGINE_VERSION,
        "insufficient_evidence": False,
        "artefact_type": "priority_assessment",
        "artefact_id": artefact["artefact_id"],
        "provenance_id": prov["provenance_id"],
        "artefacts": [artefact],
        "authoritative_references": {
            "artefact_ids": [artefact["artefact_id"]],
            "provenance_ids": [prov["provenance_id"]],
            "decision_ids": [],
            "snapshot_ids": [],
        },
        "tier1": assessment_payload,
        "tier2": None,
    }
    return attach_response_hash(body)
