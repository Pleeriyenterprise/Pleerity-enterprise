"""Provenance and calculation trace schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from services.compliance_intelligence_engine.artefact_types import is_registered_artefact_type
from services.compliance_intelligence_engine.constants import (
    CALCULATION_VERSION,
    DETERMINISTIC_SEED_VERSION,
    ENGINE_VERSION,
    RUNTIME_CONTEXT_VERSION,
    SCORING_MODEL_VERSION,
)
from services.compliance_intelligence_engine.schema import IntelligenceScope


class VersionRef(BaseModel):
    rule_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None
    legislation_id: Optional[str] = None
    version: str


class CalculationTraceStage(BaseModel):
    stage: str
    stage_version: str
    sequence: int = Field(ge=1)
    input_hash: str
    output_hash: str
    registry_refs: Dict[str, Optional[str]] = Field(default_factory=dict)
    insufficient_evidence: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_hash", "output_hash")
    @classmethod
    def _hash_prefix(cls, v: str) -> str:
        if not (v or "").startswith("sha256:"):
            raise ValueError("hash_must_be_sha256_prefixed")
        return v


class IntelligenceProvenanceBase(BaseModel):
    provenance_id: Optional[str] = None
    generated_at: Optional[datetime] = None
    artefact_id: str
    artefact_type: str
    client_id: str
    engine_version: str = ENGINE_VERSION
    algorithm_version: str = "unassigned_v1"
    template_version: str = "cie-templates-unassigned"
    calculation_version: str = CALCULATION_VERSION
    deterministic_seed_version: str = DETERMINISTIC_SEED_VERSION
    inputs_hash: str
    response_hash: str
    graph_response_hash: Optional[str] = None
    trace_hash: str
    decision_ids_used: List[str] = Field(default_factory=list)
    snapshot_ids_used: List[str] = Field(default_factory=list)
    rule_versions_used: List[VersionRef] = Field(default_factory=list)
    jurisdiction_versions_used: List[VersionRef] = Field(default_factory=list)
    legislation_versions_used: List[VersionRef] = Field(default_factory=list)
    evidence_ids_used: List[str] = Field(default_factory=list)
    operational_event_references: List[str] = Field(default_factory=list)
    graph_node_references: List[str] = Field(default_factory=list)
    graph_edge_references: List[str] = Field(default_factory=list)
    recommendation_strategy_version: Optional[str] = None
    priority_strategy_version: Optional[str] = None
    portfolio_strategy_version: Optional[str] = None
    regulatory_strategy_version: Optional[str] = None
    commercial_strategy_version: Optional[str] = None
    dependency_strategy_version: Optional[str] = None
    impact_strategy_version: Optional[str] = None
    forecast_strategy_version: Optional[str] = None
    weight_set_version: Optional[str] = None
    scoring_model_version: str = SCORING_MODEL_VERSION
    constraint_set_version: str
    runtime_context_version: str = RUNTIME_CONTEXT_VERSION
    calculation_trace: List[CalculationTraceStage]
    as_of: Optional[str] = None
    scope: IntelligenceScope
    environment: Optional[str] = None
    build_sha: Optional[str] = None
    generation_decision_id: Optional[str] = None

    @field_validator("artefact_type")
    @classmethod
    def _artefact_type_registered(cls, v: str) -> str:
        if not is_registered_artefact_type(v):
            raise ValueError(f"unregistered_artefact_type:{v}")
        return v.strip().lower()

    @field_validator(
        "inputs_hash",
        "response_hash",
        "trace_hash",
    )
    @classmethod
    def _hash_prefix(cls, v: str) -> str:
        if not (v or "").startswith("sha256:"):
            raise ValueError("hash_must_be_sha256_prefixed")
        return v

    @field_validator("graph_response_hash")
    @classmethod
    def _optional_hash_prefix(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith("sha256:"):
            raise ValueError("hash_must_be_sha256_prefixed")
        return v
