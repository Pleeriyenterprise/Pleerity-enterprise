"""Calculation trace builder skeleton — CIE-1.5 foundation."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_intelligence_engine.hashing import sha256_digest, trace_hash
from services.compliance_intelligence_engine.provenance_schema import CalculationTraceStage
from services.compliance_intelligence_engine.registry.versions import CONSTRAINT_SET_V1


def build_stub_trace(
    *,
    inputs_hash: str,
    constraint_set_version: str = CONSTRAINT_SET_V1,
    insufficient_evidence: bool = True,
    insufficient_reason: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Minimal trace for foundation stubs — domain stages deferred to CIE-2."""
    norm_out = sha256_digest({"stage": "inputs_normalization", "inputs_hash": inputs_hash})
    constraint_out = sha256_digest(
        {
            "stage": "constraint_resolution",
            "constraint_set_version": constraint_set_version,
            "insufficient_evidence": insufficient_evidence,
        }
    )
    stages = [
        CalculationTraceStage(
            stage="inputs_normalization",
            stage_version="normalization_v1",
            sequence=1,
            input_hash=inputs_hash,
            output_hash=norm_out,
            registry_refs={},
            metadata={},
        ),
        CalculationTraceStage(
            stage="constraint_resolution",
            stage_version="constraint_resolution_v1",
            sequence=2,
            input_hash=norm_out,
            output_hash=constraint_out,
            registry_refs={"constraint_set_version": constraint_set_version},
            insufficient_evidence=insufficient_evidence,
            metadata={"insufficient_reason": insufficient_reason} if insufficient_reason else {},
        ),
    ]
    return [s.model_dump() for s in stages]


def compute_trace_hash_from_stages(stages: List[Dict[str, Any]]) -> str:
    return trace_hash(stages)
