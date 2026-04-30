"""
PR3: merge pipeline-derived applicability into requirement documents with selector
and optional audit append. Does not change score/PR5/HIUA.

Legacy ``applicability_state`` is dual-written to ``effective_applicability_state`` so
existing readers stay aligned until consumer migration.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional, Tuple

from services.applicability_provenance_backfill import operator_override_from_doc, pipeline_from_legacy_requirement
from services.applicability_provenance_constants import PIPELINE, normalize_applicability_tri_state
from services.applicability_provenance_selector import build_provenance_mongo_set
from services.applicability_resolution_audit import append_applicability_resolution_audit

logger = logging.getLogger(__name__)


def merge_provenance_into_requirement_patch(
    existing: Optional[Dict[str, Any]],
    pipeline_applicability_state: str,
) -> Dict[str, Any]:
    """
    Build $set fields: nested + flat provenance via selector, plus legacy
    ``applicability_state`` mirroring effective (consumer compatibility).
    """
    ex = existing if isinstance(existing, dict) else {}
    active, ov_state = operator_override_from_doc(ex)
    prov = build_provenance_mongo_set(
        pipeline_applicability_state=pipeline_applicability_state,
        operator_override_active=active,
        operator_override_applicability_state=ov_state,
    )
    prov["applicability_state"] = prov["effective_applicability_state"]
    return prov


def _read_pipeline_snapshot(row: Dict[str, Any]) -> str:
    if row.get("pipeline_applicability_state"):
        return normalize_applicability_tri_state(row["pipeline_applicability_state"])
    nested = row.get("applicability_provenance")
    if isinstance(nested, dict) and nested.get("pipeline_applicability_state"):
        return normalize_applicability_tri_state(nested.get("pipeline_applicability_state"))
    return pipeline_from_legacy_requirement(row)


def _read_effective_snapshot(row: Dict[str, Any]) -> str:
    if row.get("effective_applicability_state"):
        return normalize_applicability_tri_state(row["effective_applicability_state"])
    if row.get("applicability_state"):
        return normalize_applicability_tri_state(row["applicability_state"])
    nested = row.get("applicability_provenance")
    if isinstance(nested, dict) and nested.get("effective_applicability_state"):
        return normalize_applicability_tri_state(nested.get("effective_applicability_state"))
    return _read_pipeline_snapshot(row)


def applicability_provenance_signature(row: Dict[str, Any]) -> Tuple[str, str, str, bool]:
    """Logical provenance identity for skip-if-unchanged (ignores timestamps)."""
    nested = row.get("applicability_provenance") if isinstance(row.get("applicability_provenance"), dict) else {}
    ov = nested.get("operator_override") if isinstance(nested.get("operator_override"), dict) else {}
    ov_active = bool(row.get("operator_override_active") or ov.get("active"))
    return (
        _read_pipeline_snapshot(row),
        _read_effective_snapshot(row),
        _read_source_snapshot(row),
        ov_active,
    )


def _read_source_snapshot(row: Dict[str, Any]) -> str:
    if row.get("applicability_resolution_source"):
        return str(row["applicability_resolution_source"]).strip().upper()
    nested = row.get("applicability_provenance")
    if isinstance(nested, dict) and nested.get("applicability_resolution_source"):
        return str(nested.get("applicability_resolution_source")).strip().upper()
    return PIPELINE


def _read_snapshots_from_patch(patch: Dict[str, Any]) -> Tuple[str, str, str]:
    p = normalize_applicability_tri_state(patch.get("pipeline_applicability_state"))
    e = normalize_applicability_tri_state(patch.get("effective_applicability_state"))
    s = str(patch.get("applicability_resolution_source") or PIPELINE).strip().upper()
    return p, e, s


async def maybe_audit_applicability_transition(
    db: Any,
    *,
    client_id: str,
    property_id: Optional[str],
    requirement_id: str,
    before: Dict[str, Any],
    after_patch: Dict[str, Any],
    event_type: str,
    actor: Mapping[str, Any],
) -> None:
    """
    Append audit row if pipeline or effective applicability changed (or resolution source).
    Failures are logged and do not raise (pipeline write already applied).
    """
    bp, be, bs = _read_pipeline_snapshot(before), _read_effective_snapshot(before), _read_source_snapshot(before)
    ap, ae, a_src = _read_snapshots_from_patch(after_patch)
    if bp == ap and be == ae and bs == a_src:
        return
    try:
        await append_applicability_resolution_audit(
            db,
            client_id=client_id,
            property_id=property_id,
            requirement_id=requirement_id,
            event_type=event_type,
            pipeline_applicability_state=ap,
            effective_applicability_state=ae,
            applicability_resolution_source=a_src,
            actor=actor,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "applicability audit append failed client_id=%s requirement_id=%s: %s",
            client_id,
            requirement_id,
            exc,
        )


async def apply_provenance_and_audit_after_requirement_patch(
    db: Any,
    *,
    client_id: str,
    property_id: Optional[str],
    requirement_id: str,
    before: Dict[str, Any],
    pipeline_applicability_state: str,
    event_type: str,
    actor: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Build provenance $set fragment and emit audit if pipeline/effective/source changed.
    Returns the dict to merge into $set (includes legacy applicability_state mirror).
    """
    patch = merge_provenance_into_requirement_patch(before, pipeline_applicability_state)
    await maybe_audit_applicability_transition(
        db,
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        before=before,
        after_patch=patch,
        event_type=event_type,
        actor=actor,
    )
    return patch


__all__ = [
    "applicability_provenance_signature",
    "apply_provenance_and_audit_after_requirement_patch",
    "merge_provenance_into_requirement_patch",
    "maybe_audit_applicability_transition",
]
