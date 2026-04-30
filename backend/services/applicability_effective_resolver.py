"""
PR5: read-time applicability model for obligation semantics vs pipeline diagnostics.

- ``effective_applicability_state`` — what runtime policy/gap/HIUA should treat as applicable (operator + selector).
- ``pipeline_applicability_state`` — pipeline/materialization truth (quality / drift diagnostics).
- ``applicability_resolution_source`` — PIPELINE | OPERATOR_OVERRIDE (v1).

Use ``resolve_applicability_read_model`` for structured reads; ``resolve_policy_facts`` consumes this for
``applicability_state`` when stored provenance exists.
"""
from __future__ import annotations

from typing import Any, Dict

from services.applicability_provenance_constants import (
    OPERATOR_OVERRIDE,
    PIPELINE,
    normalize_applicability_tri_state,
)
from services.applicability_state_parse import normalize_applicability_state


def _nested(row: Dict[str, Any]) -> Dict[str, Any]:
    n = row.get("applicability_provenance")
    return n if isinstance(n, dict) else {}


def has_provenance_storage(row: Dict[str, Any]) -> bool:
    """True when PR1+ provenance fields exist (skip legacy registry/catalog merge on read)."""
    if not isinstance(row, dict):
        return False
    if row.get("pipeline_applicability_state") is not None or row.get("effective_applicability_state") is not None:
        return True
    n = _nested(row)
    return n.get("pipeline_applicability_state") is not None or n.get("effective_applicability_state") is not None


def resolve_applicability_read_model(requirement_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return pipeline, effective, source, and whether stored provenance governs policy reads.

    Does not call registry/catalog — pipeline snapshot is whatever is stored or legacy-normalized.
    """
    req = requirement_row if isinstance(requirement_row, dict) else {}
    n = _nested(req)

    pipeline: str
    if req.get("pipeline_applicability_state") is not None and str(req.get("pipeline_applicability_state") or "").strip():
        pipeline = normalize_applicability_tri_state(req["pipeline_applicability_state"])
    elif n.get("pipeline_applicability_state") is not None and str(n.get("pipeline_applicability_state") or "").strip():
        pipeline = normalize_applicability_tri_state(n.get("pipeline_applicability_state"))
    else:
        pipeline = normalize_applicability_state(req)

    effective: str
    if req.get("effective_applicability_state") is not None and str(req.get("effective_applicability_state") or "").strip():
        effective = normalize_applicability_tri_state(req["effective_applicability_state"])
    elif n.get("effective_applicability_state") is not None and str(n.get("effective_applicability_state") or "").strip():
        effective = normalize_applicability_tri_state(n.get("effective_applicability_state"))
    elif req.get("applicability_state") is not None and str(req.get("applicability_state") or "").strip():
        effective = normalize_applicability_tri_state(req["applicability_state"])
    else:
        effective = pipeline

    src = PIPELINE
    raw_src = req.get("applicability_resolution_source") or n.get("applicability_resolution_source")
    if raw_src is not None and str(raw_src).strip():
        u = str(raw_src).strip().upper()
        if u in (PIPELINE, OPERATOR_OVERRIDE):
            src = u

    storage = has_provenance_storage(req)
    return {
        "has_provenance_storage": storage,
        "pipeline_applicability_state": pipeline,
        "effective_applicability_state": effective,
        "applicability_resolution_source": src,
    }


__all__ = [
    "has_provenance_storage",
    "resolve_applicability_read_model",
]
