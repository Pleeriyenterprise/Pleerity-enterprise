"""Pydantic models for Compliance Intelligence Artefacts and scopes."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from services.compliance_intelligence_engine.artefact_types import is_registered_artefact_type
from services.compliance_intelligence_engine.constants import (
    DETERMINISTIC_VERSION,
    ENGINE_VERSION,
    TEMPLATE_VERSION_DEFAULT,
)
from services.compliance_intelligence_engine.lifecycle import is_valid_lifecycle_state


class IntelligenceScope(BaseModel):
    client_id: str
    property_id: Optional[str] = None
    requirement_id: Optional[str] = None
    portfolio_root: bool = True
    as_of: Optional[str] = None


class ConfidenceMetadata(BaseModel):
    score: int = Field(ge=0, le=100, default=0)
    label: str = "insufficient"
    factors: List[Dict[str, Any]] = Field(default_factory=list)


class ExplainabilityBlock(BaseModel):
    why_exists: Optional[str] = None
    assumptions: List[Dict[str, Any]] = Field(default_factory=list)


class IntelligenceArtefactBase(BaseModel):
    artefact_id: Optional[str] = None
    provenance_id: str
    artefact_type: str
    artefact_version: int = 1
    generated_at: Optional[datetime] = None
    client_id: str
    scope: IntelligenceScope
    engine_version: str = ENGINE_VERSION
    template_version: str = TEMPLATE_VERSION_DEFAULT
    deterministic_version: str = DETERMINISTIC_VERSION
    inputs_hash: str
    response_hash: str
    source_decision_ids: List[str] = Field(default_factory=list)
    source_snapshot_ids: List[str] = Field(default_factory=list)
    source_graph_references: Dict[str, List[str]] = Field(
        default_factory=lambda: {"node_ids": [], "edge_ids": []}
    )
    confidence: ConfidenceMetadata = Field(default_factory=ConfidenceMetadata)
    operational_correlation_ids: List[str] = Field(default_factory=list)
    generation_decision_id: Optional[str] = None
    lifecycle_state: str = "generated"
    supersedes_artefact_id: Optional[str] = None
    superseded_by_artefact_id: Optional[str] = None
    insufficient_evidence: bool = False
    insufficient_reason: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    commercial: Dict[str, Any] = Field(default_factory=dict)
    explainability: ExplainabilityBlock = Field(default_factory=ExplainabilityBlock)
    dedupe_key: Optional[str] = None
    environment: Optional[str] = None
    build_sha: Optional[str] = None

    @field_validator("artefact_type")
    @classmethod
    def _artefact_type_registered(cls, v: str) -> str:
        if not is_registered_artefact_type(v):
            raise ValueError(f"unregistered_artefact_type:{v}")
        return v.strip().lower()

    @field_validator("lifecycle_state")
    @classmethod
    def _lifecycle_state_valid(cls, v: str) -> str:
        if not is_valid_lifecycle_state(v):
            raise ValueError(f"invalid_lifecycle_state:{v}")
        return v.strip().lower()

    @field_validator("inputs_hash", "response_hash")
    @classmethod
    def _hash_prefix(cls, v: str) -> str:
        if not (v or "").startswith("sha256:"):
            raise ValueError("hash_must_be_sha256_prefixed")
        return v

    @field_validator("provenance_id")
    @classmethod
    def _provenance_id_prefix(cls, v: str) -> str:
        if not (v or "").startswith("cip_"):
            raise ValueError("provenance_id_must_have_cip_prefix")
        return v


class IntelligenceTransitionBase(BaseModel):
    transition_id: Optional[str] = None
    artefact_id: str
    artefact_type: str
    from_state: str
    to_state: str
    transitioned_at: Optional[datetime] = None
    transition_decision_id: Optional[str] = None
    actor_type: str = "system"
    actor_id: Optional[str] = None
    consumer_id: Optional[str] = None
    reason_code: str
    reason_summary: Optional[str] = None
    client_id: str
    correlation_id: Optional[str] = None
    inputs_hash: Optional[str] = None

    @field_validator("artefact_type")
    @classmethod
    def _transition_artefact_type(cls, v: str) -> str:
        if not is_registered_artefact_type(v):
            raise ValueError(f"unregistered_artefact_type:{v}")
        return v.strip().lower()

    @field_validator("from_state", "to_state")
    @classmethod
    def _transition_states(cls, v: str) -> str:
        if not is_valid_lifecycle_state(v):
            raise ValueError(f"invalid_lifecycle_state:{v}")
        return v.strip().lower()
