"""Provenance writer — immutable calculation lineage for every artefact."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.compliance_intelligence_engine.constants import (
    CALCULATION_VERSION,
    DETERMINISTIC_SEED_VERSION,
    DETERMINISTIC_VERSION,
    ENGINE_VERSION,
    RUNTIME_CONTEXT_VERSION,
    SCORING_MODEL_VERSION,
    TEMPLATE_VERSION_DEFAULT,
)
from services.compliance_intelligence_engine.hashing import (
    artefact_response_hash,
    inputs_hash,
    sha256_digest,
    trace_hash,
)
from services.compliance_intelligence_engine.ids import new_provenance_id
from services.compliance_intelligence_engine.provenance_trace import build_stub_trace
from services.compliance_intelligence_engine.registry.loader import registry_pins_for_recommendation
from services.compliance_intelligence_engine.registry.versions import CONSTRAINT_SET_V1, WEIGHT_SET_V1


def build_calculation_trace(
    *,
    inputs_hash_value: str,
    stages_extra: Optional[List[Dict[str, Any]]] = None,
    insufficient_evidence: bool = False,
) -> List[Dict[str, Any]]:
    trace = build_stub_trace(
        inputs_hash=inputs_hash_value,
        constraint_set_version=CONSTRAINT_SET_V1,
        insufficient_evidence=insufficient_evidence,
    )
    if stages_extra:
        seq = len(trace) + 1
        for s in stages_extra:
            s = dict(s)
            s["sequence"] = seq
            trace.append(s)
            seq += 1
    return trace


def build_provenance_record(
    *,
    artefact: Dict[str, Any],
    graph_response_hash: Optional[str],
    algorithm_version: str,
    calculation_trace: List[Dict[str, Any]],
    strategy_pins: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    pins = strategy_pins or registry_pins_for_recommendation()
    th = trace_hash(calculation_trace)
    prov = {
        "provenance_id": new_provenance_id(),
        "generated_at": datetime.now(timezone.utc),
        "artefact_id": artefact["artefact_id"],
        "artefact_type": artefact["artefact_type"],
        "client_id": artefact["client_id"],
        "engine_version": ENGINE_VERSION,
        "algorithm_version": algorithm_version,
        "template_version": artefact.get("template_version", TEMPLATE_VERSION_DEFAULT),
        "calculation_version": CALCULATION_VERSION,
        "deterministic_seed_version": DETERMINISTIC_SEED_VERSION,
        "inputs_hash": artefact["inputs_hash"],
        "response_hash": artefact["response_hash"],
        "graph_response_hash": graph_response_hash,
        "trace_hash": th,
        "decision_ids_used": list(artefact.get("source_decision_ids") or []),
        "snapshot_ids_used": list(artefact.get("source_snapshot_ids") or []),
        "evidence_ids_used": list((artefact.get("payload") or {}).get("evidence_ids") or []),
        "recommendation_strategy_version": pins.get("recommendation_strategy_version"),
        "priority_strategy_version": pins.get("priority_strategy_version"),
        "weight_set_version": pins.get("weight_set_version") or WEIGHT_SET_V1,
        "constraint_set_version": pins.get("constraint_set_version") or CONSTRAINT_SET_V1,
        "scoring_model_version": SCORING_MODEL_VERSION,
        "runtime_context_version": RUNTIME_CONTEXT_VERSION,
        "calculation_trace": calculation_trace,
        "scope": artefact.get("scope"),
        "as_of": (artefact.get("scope") or {}).get("as_of"),
    }
    return prov


def artefact_inputs_hash(
    *,
    artefact_type: str,
    scope: Dict[str, Any],
    source_decision_ids: List[str],
    source_snapshot_ids: List[str],
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    return inputs_hash(
        artefact_type=artefact_type,
        scope=scope,
        source_decision_ids=source_decision_ids,
        source_snapshot_ids=source_snapshot_ids,
        template_version=TEMPLATE_VERSION_DEFAULT,
        deterministic_version=DETERMINISTIC_VERSION,
        engine_version=ENGINE_VERSION,
        extra=extra,
    )
