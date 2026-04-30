"""
Single selector for applicability provenance: computes effective applicability
and resolution source, and builds nested + flat Mongo $set fragments.

PR1 does not wire this into materialization/reconciliation; consumers unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from services.applicability_provenance_constants import (
    OPERATOR_OVERRIDE,
    PIPELINE,
    normalize_applicability_tri_state,
    validate_resolution_source_for_persist,
)


def select_effective_applicability(
    *,
    pipeline_applicability_state: str,
    operator_override_active: bool,
    operator_override_applicability_state: Optional[str],
) -> Tuple[str, str]:
    """
    Return (effective_applicability_state, applicability_resolution_source).

    v1: only PIPELINE or OPERATOR_OVERRIDE. Never returns reserved sources.
    If operator_override_active is True but override state is missing or not
    REQUIRED/NOT_REQUIRED, treat as data defect: fall back to pipeline + PIPELINE.
    """
    pipeline = normalize_applicability_tri_state(pipeline_applicability_state)
    if operator_override_active:
        ov = normalize_applicability_tri_state(operator_override_applicability_state)
        if ov in ("REQUIRED", "NOT_REQUIRED"):
            return ov, OPERATOR_OVERRIDE
    return pipeline, PIPELINE


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_operator_override_block(
    *,
    active: bool,
    applicability_state: Optional[str] = None,
) -> Dict[str, Any]:
    """Default nested operator_override subdocument for PR1 (inactive)."""
    st: Optional[str] = None
    if active and applicability_state:
        n = normalize_applicability_tri_state(applicability_state)
        if n in ("REQUIRED", "NOT_REQUIRED"):
            st = n
    return {
        "active": bool(active),
        "applicability_state": st,
    }


def build_applicability_provenance_document(
    *,
    pipeline_applicability_state: str,
    effective_applicability_state: str,
    applicability_resolution_source: str,
    operator_override_active: bool,
    operator_override_applicability_state: Optional[str] = None,
    pipeline_updated_at: Optional[datetime] = None,
    effective_updated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Canonical nested applicability_provenance object (+ consistency checks)."""
    ok, err = validate_resolution_source_for_persist(applicability_resolution_source)
    if not ok:
        raise ValueError(err)
    p = normalize_applicability_tri_state(pipeline_applicability_state)
    e = normalize_applicability_tri_state(effective_applicability_state)
    src = str(applicability_resolution_source).strip().upper()
    ov_active = bool(operator_override_active)
    ov_block = build_operator_override_block(
        active=ov_active,
        applicability_state=operator_override_applicability_state if ov_active else None,
    )
    now = _utcnow()
    return {
        "pipeline_applicability_state": p,
        "pipeline_updated_at": pipeline_updated_at or now,
        "effective_applicability_state": e,
        "effective_updated_at": effective_updated_at or now,
        "applicability_resolution_source": src,
        "operator_override": ov_block,
    }


def build_provenance_mongo_set(
    *,
    pipeline_applicability_state: str,
    operator_override_active: bool,
    operator_override_applicability_state: Optional[str] = None,
    pipeline_updated_at: Optional[datetime] = None,
    effective_updated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Run selector and return flat + nested fields for $set (single write surface).

    Does not set legacy applicability_state (unchanged in PR1).
    """
    eff, src = select_effective_applicability(
        pipeline_applicability_state=pipeline_applicability_state,
        operator_override_active=operator_override_active,
        operator_override_applicability_state=operator_override_applicability_state,
    )
    nested = build_applicability_provenance_document(
        pipeline_applicability_state=pipeline_applicability_state,
        effective_applicability_state=eff,
        applicability_resolution_source=src,
        operator_override_active=operator_override_active,
        operator_override_applicability_state=operator_override_applicability_state,
        pipeline_updated_at=pipeline_updated_at,
        effective_updated_at=effective_updated_at,
    )
    return {
        "applicability_provenance": nested,
        "pipeline_applicability_state": nested["pipeline_applicability_state"],
        "effective_applicability_state": nested["effective_applicability_state"],
        "applicability_resolution_source": nested["applicability_resolution_source"],
        "operator_override_active": bool(operator_override_active),
    }


def provenance_flat_fields_in_sync(doc: Dict[str, Any]) -> bool:
    """True if flat mirrors match nested applicability_provenance when present."""
    nested = doc.get("applicability_provenance")
    if not isinstance(nested, dict):
        return False
    try:
        if doc.get("pipeline_applicability_state") != nested.get("pipeline_applicability_state"):
            return False
        if doc.get("effective_applicability_state") != nested.get("effective_applicability_state"):
            return False
        if str(doc.get("applicability_resolution_source") or "").upper() != str(
            nested.get("applicability_resolution_source") or ""
        ).upper():
            return False
        ov = nested.get("operator_override") if isinstance(nested.get("operator_override"), dict) else {}
        active = bool(ov.get("active"))
        if bool(doc.get("operator_override_active")) != active:
            return False
    except Exception:
        return False
    return True


__all__ = [
    "build_applicability_provenance_document",
    "build_provenance_mongo_set",
    "provenance_flat_fields_in_sync",
    "select_effective_applicability",
]
