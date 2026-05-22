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
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_evidence_authority import (
    EA_NOT_REQUIRED,
    sync_requirement_evidence_authority,
)

# Bounded OPS-VERIFY / Wales HMO: operational applicability projection for surfaced legionella only.
_LEGIONELLA_OPERATIONAL_APPLICABILITY = "REQUIRED"
_LEGIONELLA_RECONCILIATION_SOURCE = "legionella_operational_surfaced_actionable_v1"
_WALES_OCCUPATION_OPERATIONAL_APPLICABILITY = "REQUIRED"
_WALES_OCCUPATION_RECONCILIATION_SOURCE = "wales_occupation_contract_operational_surfaced_actionable_v1"
_SCOTLAND_LANDLORD_REG_OPERATIONAL_APPLICABILITY = "REQUIRED"
_SCOTLAND_LANDLORD_REG_RECONCILIATION_SOURCE = (
    "scotland_landlord_registration_operational_surfaced_actionable_v1"
)
_RENT_SMART_WALES_OPERATIONAL_APPLICABILITY = "REQUIRED"
_RENT_SMART_WALES_RECONCILIATION_SOURCE = "rent_smart_wales_operational_surfaced_actionable_v1"


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


def _legionella_canon(row: Dict[str, Any]) -> str:
    raw = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    return normalize_requirement_code(raw) or raw.lower().replace(" ", "_")


def legionella_operational_applicability_reconciliation_eligible(row: Dict[str, Any]) -> bool:
    """
    Surfaced actionable legionella on client/runtime path where pipeline still says NOT_REQUIRED
    (or UNKNOWN row + NOT_REQUIRED pipeline) while lifecycle is operational.
    """
    if not isinstance(row, dict) or _legionella_canon(row) != "legionella":
        return False
    if row.get("client_surface_visible") is False:
        return False
    from services.client_requirement_lifecycle import (
        ACTION_REQUIRED,
        NOT_APPLICABLE,
        PENDING_REVIEW,
        SATISFIED_UNVERIFIED,
        derive_client_lifecycle_fields,
    )

    lifecycle = derive_client_lifecycle_fields(row)
    life = str(lifecycle.get("client_lifecycle_state") or "").strip().upper()
    if life == NOT_APPLICABLE:
        return False
    if life not in (ACTION_REQUIRED, PENDING_REVIEW, SATISFIED_UNVERIFIED):
        return False
    read = resolve_applicability_read_model(row)
    pipeline = str(read.get("pipeline_applicability_state") or "").strip().upper()
    eff = str(read.get("effective_applicability_state") or "").strip().upper()
    row_app = row_applicability_for_client_coherence(row)
    app_state = str(row.get("applicability_state") or row_app or "").strip().upper()
    if pipeline == "NOT_REQUIRED" or eff == "NOT_REQUIRED" or app_state == "NOT_REQUIRED":
        return True
    if pipeline_not_required_disagrees_with_surfaced_row(row):
        return True
    return False


def _wales_occupation_canon(row: Dict[str, Any]) -> str:
    raw = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw) or raw.lower().replace(" ", "_")
    if canon == "occupation_contract":
        req_jur = str(row.get("jurisdiction") or row.get("property_jurisdiction") or "").strip().lower()
        if req_jur == "wales":
            return "wales_occupation_contract"
    return canon


def wales_occupation_operational_applicability_reconciliation_eligible(row: Dict[str, Any]) -> bool:
    """Surfaced actionable Wales occupation contract on client/runtime path."""
    if not isinstance(row, dict) or _wales_occupation_canon(row) != "wales_occupation_contract":
        return False
    if row.get("client_surface_visible") is False:
        return False
    from services.client_requirement_lifecycle import (
        ACTION_REQUIRED,
        NOT_APPLICABLE,
        PENDING_REVIEW,
        SATISFIED_UNVERIFIED,
        derive_client_lifecycle_fields,
    )

    lifecycle = derive_client_lifecycle_fields(row)
    life = str(lifecycle.get("client_lifecycle_state") or "").strip().upper()
    if life == NOT_APPLICABLE:
        return False
    if life not in (ACTION_REQUIRED, PENDING_REVIEW, SATISFIED_UNVERIFIED):
        return False
    read = resolve_applicability_read_model(row)
    pipeline = str(read.get("pipeline_applicability_state") or "").strip().upper()
    eff = str(read.get("effective_applicability_state") or "").strip().upper()
    row_app = row_applicability_for_client_coherence(row)
    app_state = str(row.get("applicability_state") or row_app or "").strip().upper()
    if pipeline == "NOT_REQUIRED" or eff == "NOT_REQUIRED" or app_state == "NOT_REQUIRED":
        return True
    if row_app == "UNKNOWN" or app_state == "UNKNOWN":
        return True
    if pipeline_not_required_disagrees_with_surfaced_row(row):
        return True
    return False


def _scotland_landlord_registration_canon(row: Dict[str, Any]) -> str:
    raw = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    return normalize_requirement_code(raw) or raw.lower().replace(" ", "_")


def scotland_landlord_registration_operational_applicability_reconciliation_eligible(
    row: Dict[str, Any],
) -> bool:
    """Surfaced actionable Scotland landlord registration on client/runtime path."""
    if not isinstance(row, dict) or _scotland_landlord_registration_canon(row) != "scotland_landlord_registration":
        return False
    if row.get("client_surface_visible") is False:
        return False
    from services.client_requirement_lifecycle import (
        ACTION_REQUIRED,
        NOT_APPLICABLE,
        PENDING_REVIEW,
        SATISFIED_UNVERIFIED,
        derive_client_lifecycle_fields,
    )

    lifecycle = derive_client_lifecycle_fields(row)
    life = str(lifecycle.get("client_lifecycle_state") or "").strip().upper()
    if life == NOT_APPLICABLE:
        return False
    if life not in (ACTION_REQUIRED, PENDING_REVIEW, SATISFIED_UNVERIFIED):
        return False
    read = resolve_applicability_read_model(row)
    pipeline = str(read.get("pipeline_applicability_state") or "").strip().upper()
    eff = str(read.get("effective_applicability_state") or "").strip().upper()
    row_app = row_applicability_for_client_coherence(row)
    app_state = str(row.get("applicability_state") or row_app or "").strip().upper()
    if pipeline == "NOT_REQUIRED" or eff == "NOT_REQUIRED" or app_state == "NOT_REQUIRED":
        return True
    if row_app == "UNKNOWN" or app_state == "UNKNOWN":
        return True
    if pipeline_not_required_disagrees_with_surfaced_row(row):
        return True
    return False


def reconcile_scotland_landlord_registration_operational_applicability(
    row: Dict[str, Any],
) -> Dict[str, Any]:
    """Client/runtime projection for Scotland landlord registration operational truth."""
    if not scotland_landlord_registration_operational_applicability_reconciliation_eligible(row):
        return row
    out = dict(row)
    read = resolve_applicability_read_model(out)
    prior = {
        "applicability": out.get("applicability"),
        "applicability_state": out.get("applicability_state"),
        "effective_applicability_state": read.get("effective_applicability_state"),
        "pipeline_applicability_state": read.get("pipeline_applicability_state"),
        "applicability_resolution_source": read.get("applicability_resolution_source"),
    }
    out["applicability"] = _SCOTLAND_LANDLORD_REG_OPERATIONAL_APPLICABILITY
    out["applicability_state"] = _SCOTLAND_LANDLORD_REG_OPERATIONAL_APPLICABILITY
    out["effective_applicability_state"] = _SCOTLAND_LANDLORD_REG_OPERATIONAL_APPLICABILITY
    prov = out.get("applicability_provenance")
    if isinstance(prov, dict):
        prov = dict(prov)
    else:
        prov = {}
    prov["effective_applicability_state"] = _SCOTLAND_LANDLORD_REG_OPERATIONAL_APPLICABILITY
    prov["operational_applicability_reconciliation"] = {
        "source": _SCOTLAND_LANDLORD_REG_RECONCILIATION_SOURCE,
        "prior": prior,
    }
    out["applicability_provenance"] = prov
    return out


def _rent_smart_wales_canon(row: Dict[str, Any]) -> str:
    raw = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    return normalize_requirement_code(raw) or raw.lower().replace(" ", "_")


def rent_smart_wales_operational_applicability_reconciliation_eligible(row: Dict[str, Any]) -> bool:
    """Surfaced actionable Rent Smart Wales registration on client/runtime path."""
    if not isinstance(row, dict) or _rent_smart_wales_canon(row) != "rent_smart_wales":
        return False
    if row.get("client_surface_visible") is False:
        return False
    from services.client_requirement_lifecycle import (
        ACTION_REQUIRED,
        NOT_APPLICABLE,
        PENDING_REVIEW,
        SATISFIED_UNVERIFIED,
        derive_client_lifecycle_fields,
    )

    lifecycle = derive_client_lifecycle_fields(row)
    life = str(lifecycle.get("client_lifecycle_state") or "").strip().upper()
    if life == NOT_APPLICABLE:
        return False
    if life not in (ACTION_REQUIRED, PENDING_REVIEW, SATISFIED_UNVERIFIED):
        return False
    read = resolve_applicability_read_model(row)
    pipeline = str(read.get("pipeline_applicability_state") or "").strip().upper()
    eff = str(read.get("effective_applicability_state") or "").strip().upper()
    row_app = row_applicability_for_client_coherence(row)
    app_state = str(row.get("applicability_state") or row_app or "").strip().upper()
    if pipeline == "NOT_REQUIRED" or eff == "NOT_REQUIRED" or app_state == "NOT_REQUIRED":
        return True
    if row_app == "UNKNOWN" or app_state == "UNKNOWN":
        return True
    if pipeline_not_required_disagrees_with_surfaced_row(row):
        return True
    return False


def reconcile_rent_smart_wales_operational_applicability(row: Dict[str, Any]) -> Dict[str, Any]:
    """Client/runtime projection for Rent Smart Wales registration operational truth."""
    if not rent_smart_wales_operational_applicability_reconciliation_eligible(row):
        return row
    out = dict(row)
    read = resolve_applicability_read_model(out)
    prior = {
        "applicability": out.get("applicability"),
        "applicability_state": out.get("applicability_state"),
        "effective_applicability_state": read.get("effective_applicability_state"),
        "pipeline_applicability_state": read.get("pipeline_applicability_state"),
        "applicability_resolution_source": read.get("applicability_resolution_source"),
    }
    out["applicability"] = _RENT_SMART_WALES_OPERATIONAL_APPLICABILITY
    out["applicability_state"] = _RENT_SMART_WALES_OPERATIONAL_APPLICABILITY
    out["effective_applicability_state"] = _RENT_SMART_WALES_OPERATIONAL_APPLICABILITY
    prov = out.get("applicability_provenance")
    if isinstance(prov, dict):
        prov = dict(prov)
    else:
        prov = {}
    prov["effective_applicability_state"] = _RENT_SMART_WALES_OPERATIONAL_APPLICABILITY
    prov["operational_applicability_reconciliation"] = {
        "source": _RENT_SMART_WALES_RECONCILIATION_SOURCE,
        "prior": prior,
    }
    out["applicability_provenance"] = prov
    return out


def reconcile_wales_occupation_operational_applicability(row: Dict[str, Any]) -> Dict[str, Any]:
    """Client/runtime projection for Wales occupation contract operational truth."""
    if not wales_occupation_operational_applicability_reconciliation_eligible(row):
        return row
    out = dict(row)
    read = resolve_applicability_read_model(out)
    prior = {
        "applicability": out.get("applicability"),
        "applicability_state": out.get("applicability_state"),
        "effective_applicability_state": read.get("effective_applicability_state"),
        "pipeline_applicability_state": read.get("pipeline_applicability_state"),
        "applicability_resolution_source": read.get("applicability_resolution_source"),
    }
    out["applicability"] = _WALES_OCCUPATION_OPERATIONAL_APPLICABILITY
    out["applicability_state"] = _WALES_OCCUPATION_OPERATIONAL_APPLICABILITY
    out["effective_applicability_state"] = _WALES_OCCUPATION_OPERATIONAL_APPLICABILITY
    prov = out.get("applicability_provenance")
    if isinstance(prov, dict):
        prov = dict(prov)
    else:
        prov = {}
    prov["effective_applicability_state"] = _WALES_OCCUPATION_OPERATIONAL_APPLICABILITY
    prov["operational_applicability_reconciliation"] = {
        "source": _WALES_OCCUPATION_RECONCILIATION_SOURCE,
        "prior": prior,
    }
    out["applicability_provenance"] = prov
    return out


def reconcile_legionella_operational_applicability(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Client/runtime operational projection: one truthful applicability for surfaced actionable legionella.
    Does not mutate persisted pipeline provenance or registry materialisation.
    """
    if not legionella_operational_applicability_reconciliation_eligible(row):
        return row
    out = dict(row)
    read = resolve_applicability_read_model(out)
    prior = {
        "applicability": out.get("applicability"),
        "applicability_state": out.get("applicability_state"),
        "effective_applicability_state": read.get("effective_applicability_state"),
        "pipeline_applicability_state": read.get("pipeline_applicability_state"),
        "applicability_resolution_source": read.get("applicability_resolution_source"),
    }
    out["applicability"] = _LEGIONELLA_OPERATIONAL_APPLICABILITY
    out["applicability_state"] = _LEGIONELLA_OPERATIONAL_APPLICABILITY
    out["effective_applicability_state"] = _LEGIONELLA_OPERATIONAL_APPLICABILITY
    prov = out.get("applicability_provenance")
    if isinstance(prov, dict):
        prov = dict(prov)
    else:
        prov = {}
    prov["effective_applicability_state"] = _LEGIONELLA_OPERATIONAL_APPLICABILITY
    prov["operational_applicability_reconciliation"] = {
        "source": _LEGIONELLA_RECONCILIATION_SOURCE,
        "prior": prior,
    }
    out["applicability_provenance"] = prov
    return out


def apply_client_applicability_presentation_overlay(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Client read-model only: align effective applicability presentation with row truth
    when pipeline snapshot is stale for a surfaced obligation.
    """
    out = reconcile_legionella_operational_applicability(dict(row))
    out = reconcile_wales_occupation_operational_applicability(out)
    out = reconcile_scotland_landlord_registration_operational_applicability(out)
    out = reconcile_rent_smart_wales_operational_applicability(out)
    if (out.get("applicability_provenance") or {}).get("operational_applicability_reconciliation"):
        return out
    if pipeline_not_required_disagrees_with_surfaced_row(out):
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
