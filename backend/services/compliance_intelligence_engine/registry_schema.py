"""Pydantic models for registry documents."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class StrategyRegistryEntry(BaseModel):
    strategy_id: str
    strategy_family: str
    semantic_version: str
    status: str = "active"
    description: str
    constraint_set_binding: Optional[str] = None
    weight_set_binding: Optional[str] = None
    content_hash: str

    @field_validator("content_hash")
    @classmethod
    def _hash_prefix(cls, v: str) -> str:
        if not (v or "").startswith("sha256:"):
            raise ValueError("hash_must_be_sha256_prefixed")
        return v


class WeightRegistryEntry(BaseModel):
    weight_set_id: str
    semantic_version: str
    status: str = "active"
    description: str
    scope: Dict[str, Any] = Field(default_factory=dict)
    weights: Dict[str, float]
    normalization_rule: str = "sum_to_1.0"
    content_hash: str

    @field_validator("content_hash")
    @classmethod
    def _hash_prefix(cls, v: str) -> str:
        if not (v or "").startswith("sha256:"):
            raise ValueError("hash_must_be_sha256_prefixed")
        return v


class ConstraintDefinition(BaseModel):
    constraint_id: str
    constraint_type: str
    severity: str
    failure_code: str


class ConstraintRegistryEntry(BaseModel):
    constraint_set_id: str
    semantic_version: str
    status: str = "active"
    description: str
    constraints: List[ConstraintDefinition]
    content_hash: str

    @field_validator("content_hash")
    @classmethod
    def _hash_prefix(cls, v: str) -> str:
        if not (v or "").startswith("sha256:"):
            raise ValueError("hash_must_be_sha256_prefixed")
        return v
