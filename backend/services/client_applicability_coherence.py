"""
Bounded client applicability / authority coherence for surfaced obligations.

Resolves pre-submit contradictions where a requirement remains on the client runtime
surface (actionable) but carries a stale ``NOT_REQUIRED`` evidence_authority blob from an
older applicability snapshot while row ``applicability`` is not ``NOT_REQUIRED``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.applicability_effective_resolver import resolve_applicability_read_model
from services.applicability_provenance_constants import PIPELINE
from services.applicability_state_parse import APPLICABILITY_VALUES, normalize_applicability_state
from services.requirement_evidence_authority import (
    EA_NOT_REQUIRED,
    sync_requirement_evidence_authority,
)


def row_applicability_for_client_coherence(row: Dict[str, Any]) -> str:
    """
    Client runtime surface gates use legacy ``applicability``; pipeline provenance may store
    ``applicability_state`` NOT_REQUIRED while the legacy column remains UNKNOWN.
    """
    raw = row.get("applicability")
    if raw is not None and str(raw).strip():
        st = str(raw).strip().upper()
        if st in APPLICABILITY_VALUES:
            return st
    return normalize_applicability_state(row)


def authority_applicability_not_required_disagrees_with_row(row: Dict[str, Any]) -> bool:
    """Stale NOT_REQUIRED authority blob while row applicability/status are not excluded."""
    if not isinstance(row, dict):
        return False
    row_app = row_applicability_for_client_coherence(row)
    if row_app == "NOT_REQUIRED":
        return False
    status = str(row.get("status") or "").strip().upper()
    if status in ("NOT_REQUIRED", "NOT_APPLICABLE", "WAIVED"):
        return False
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    if str(ea.get("state") or "").strip().upper() != EA_NOT_REQUIRED:
        return False
    return str(ea.get("state_reason") or "").strip() == "applicability_not_required"


def has_stale_not_required_authority_blob(row: Dict[str, Any]) -> bool:
    """
    True when persisted authority says applicability_not_required but the row is not
    marked NOT_REQUIRED (typical: applicability UNKNOWN + client-surface visible).
    """
    if row.get("client_surface_visible") is False:
        return False
    return authority_applicability_not_required_disagrees_with_row(row)


def pipeline_not_required_disagrees_with_surfaced_row(row: Dict[str, Any]) -> bool:
    """Pipeline/effective NOT_REQUIRED while row applicability is not NOT_REQUIRED."""
    if not isinstance(row, dict):
        return False
    row_app = row_applicability_for_client_coherence(row)
    if row_app == "NOT_REQUIRED":
        return False
    read = resolve_applicability_read_model(row)
    if read.get("applicability_resolution_source") != PIPELINE:
        return False
    return str(read.get("effective_applicability_state") or "").strip().upper() == "NOT_REQUIRED"


def apply_client_applicability_presentation_overlay(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Client read-model only: align effective applicability presentation with row truth
    when pipeline snapshot is stale for a surfaced obligation.
    """
    out = dict(row)
    if not pipeline_not_required_disagrees_with_surfaced_row(out):
        return out
    row_app = row_applicability_for_client_coherence(out)
    out["effective_applicability_state"] = row_app
    out["applicability_state"] = row_app
    prov = out.get("applicability_provenance")
    if isinstance(prov, dict):
        prov = dict(prov)
        prov["effective_applicability_state"] = row_app
        out["applicability_provenance"] = prov
    return out


async def refresh_stale_authority_for_client_requirements(
    db,
    requirements: List[Dict[str, Any]],
    *,
    transition_origin: str = "client_applicability_coherence.refresh_stale_authority",
) -> List[Dict[str, Any]]:
    """
    Re-sync authority for surfaced rows with stale NOT_REQUIRED blobs; reload from DB.
    """
    if not requirements:
        return requirements
    refreshed_ids: List[str] = []
    for row in requirements:
        if not has_stale_not_required_authority_blob(row):
            continue
        rid = str(row.get("requirement_id") or "").strip()
        if not rid:
            continue
        await sync_requirement_evidence_authority(
            db,
            rid,
            property_id_hint=str(row.get("property_id") or "") or None,
            transition_origin=transition_origin,
        )
        refreshed_ids.append(rid)
    if not refreshed_ids:
        return requirements
    reloaded: Dict[str, Dict[str, Any]] = {}
    async for doc in db.requirements.find(
        {"requirement_id": {"$in": refreshed_ids}},
        {"_id": 0},
    ):
        rid = str(doc.get("requirement_id") or "")
        if rid:
            reloaded[rid] = doc
    out: List[Dict[str, Any]] = []
    for row in requirements:
        rid = str(row.get("requirement_id") or "")
        out.append(reloaded.get(rid) or row)
    return out


def is_stale_not_required_lifecycle_override(row: Dict[str, Any]) -> bool:
    """Lifecycle should not treat row as NOT_APPLICABLE when authority blob is stale."""
    return authority_applicability_not_required_disagrees_with_row(row)
