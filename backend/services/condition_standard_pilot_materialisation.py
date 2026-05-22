"""
Bounded pilot materialisation for condition-standard requirement rows.

Does NOT enable global planner generation. Only explicitly allowlisted OPS pilot
(client_id, property_id, obligation) tuples may be materialised via this path.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from models import Requirement, RequirementStatus
from services.applicability_provenance_pipeline import apply_provenance_and_audit_after_requirement_patch
from services.compliance_registry_publish_service import fetch_active_published_registry_entries
from services.compliance_requirement_registry import resolve_published_entry_for_requirement
from services.compliance_rules_registry import portfolio_jurisdiction_label
from services.policy_field_normalizer import resolve_policy_facts
from services.portfolio_risk_policy import POLICY_CLASSIFICATION_VERSION
from services.requirement_action_resolver import infer_action_type
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_evidence_authority import normalized_evidence_state_for_policy
from services.requirement_truth import ACTIVE_STANDARD_CODES

logger = logging.getLogger(__name__)

REQUIREMENT_GENERATION_SOURCE_CONDITION_STANDARD_PILOT = "condition_standard_pilot_ops"
MATERIALISATION_PROVENANCE_SOURCE = "CONDITION_STANDARD_PILOT_MATERIALISATION"
RECONCILIATION_SOURCE = "condition_standard_pilot_applicability"
CONDITION_STANDARD_WORKFLOW_FAMILY = "CONDITION_STANDARD_ACTIVE_STANDARD"

# Explicit OPS pilot allowlist — do not widen without governance review.
@dataclass(frozen=True)
class ConditionStandardPilotTarget:
    client_id: str
    property_id: str
    requirement_type: str
    note: str = ""

    @property
    def canonical_code(self) -> str:
        return normalize_requirement_code(self.requirement_type) or self.requirement_type


CONDITION_STANDARD_PILOT_TARGETS: Tuple[ConditionStandardPilotTarget, ...] = (
    ConditionStandardPilotTarget(
        client_id="6bcc43c0-16f4-46a5-adf4-26693a0919d0",
        property_id="3a69dcbd-74fd-4291-839b-3d52750598a1",
        requirement_type="fitness_for_human_habitation",
        note="England AST OPS pilot (david@yopmail.com stack)",
    ),
    ConditionStandardPilotTarget(
        client_id="ec0b091b-105d-4b78-9711-7ab143999cef",
        property_id="def23b30-efa5-41f9-a9cc-7fb69f9e9024",
        requirement_type="repairing_standard",
        note="Scotland tenancy OPS pilot",
    ),
)

# Registry CTA alignment: runtime resolver wins; metadata must not imply upload-primary closure.
_CONDITION_STANDARD_REGISTRY_METADATA_OVERRIDES: Dict[str, Any] = {
    "primary_action_mode": "view_guidance",
    "evidence_resolution": {
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
        "supporting_upload_recommended": True,
        "supporting_upload_required": False,
        "verification_required": False,
    },
}


def canonical_active_standard_code(requirement_type: str) -> str:
    """Registry normalizer may not map active-standard slugs; fall back to lower slug."""
    return normalize_requirement_code(requirement_type) or str(requirement_type or "").strip().lower()


def is_pilot_materialisation_target(client_id: str, property_id: str, requirement_type: str) -> bool:
    cid = str(client_id or "").strip()
    pid = str(property_id or "").strip()
    canon = canonical_active_standard_code(requirement_type)
    if canon not in ACTIVE_STANDARD_CODES:
        return False
    for t in CONDITION_STANDARD_PILOT_TARGETS:
        if t.client_id == cid and t.property_id == pid and t.canonical_code == canon:
            return True
    return False


def evaluate_condition_standard_pilot_runtime_legitimacy(
    row: Dict[str, Any],
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]] = None,
    published_registry_entries: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Bounded runtime legitimacy for client surfaces: explicit OPS pilot rows may pass
    ``filter_requirement_rows_for_client_runtime_surfaces`` without catalog planner membership.

    Fail-closed unless every predicate holds. Does not widen beyond allowlisted pilot targets.
    """
    if row.get("client_surface_visible") is False:
        return False, "client_surface_hidden"
    if (
        str(row.get("requirement_generation_source") or "").strip()
        != REQUIREMENT_GENERATION_SOURCE_CONDITION_STANDARD_PILOT
    ):
        return False, "generation_source_not_condition_standard_pilot_ops"
    wf = str(row.get("workflow_family") or "").strip()
    ops = str(row.get("ops_verification_family") or "").strip()
    if wf != CONDITION_STANDARD_WORKFLOW_FAMILY:
        return False, "workflow_family_not_condition_standard_active_standard"
    if ops != CONDITION_STANDARD_WORKFLOW_FAMILY:
        return False, "ops_verification_family_not_condition_standard_active_standard"
    canon = canonical_active_standard_code(
        str(row.get("requirement_type") or row.get("requirement_code") or "")
    )
    if not canon or canon not in ACTIVE_STANDARD_CODES:
        return False, "obligation_not_active_standard_code"
    cid = str(row.get("client_id") or "").strip()
    pid = str(row.get("property_id") or "").strip()
    if not cid or not pid:
        return False, "missing_client_or_property_id"
    if not is_pilot_materialisation_target(cid, pid, canon):
        return False, "not_allowlisted_pilot_materialisation_target"
    meta = row.get("registry_metadata")
    if not isinstance(meta, dict):
        return False, "missing_registry_metadata"
    prov = meta.get("materialisation_provenance")
    if not isinstance(prov, dict):
        return False, "missing_materialisation_provenance"
    if str(prov.get("source") or "").strip() != MATERIALISATION_PROVENANCE_SOURCE:
        return False, "materialisation_provenance_source_mismatch"
    pl = portfolio_jurisdiction_label(property_doc, client_doc or {})
    ok_jur, jur_msg = _jurisdiction_gate(canon, pl)
    if not ok_jur:
        return False, f"jurisdiction_gate:{jur_msg}"
    if published_registry_entries is not None:
        pe = resolve_published_entry_for_requirement(
            published_registry_entries=published_registry_entries,
            requirement_type=str(row.get("requirement_type") or row.get("requirement_code") or ""),
            portfolio_label=str(pl or ""),
            property_doc=property_doc,
            enforce_conditions=True,
        )
        if not isinstance(pe, dict):
            return False, "no_published_registry_overlay_for_property"
    return True, "condition_standard_pilot_runtime_legitimate"


def is_condition_standard_pilot_runtime_legitimate(
    row: Dict[str, Any],
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]] = None,
    published_registry_entries: Optional[Dict[str, Any]] = None,
) -> bool:
    ok, _ = evaluate_condition_standard_pilot_runtime_legitimacy(
        row,
        property_doc=property_doc,
        client_doc=client_doc,
        published_registry_entries=published_registry_entries,
    )
    return ok


def list_condition_standard_pilot_targets() -> List[Dict[str, Any]]:
    return [
        {
            "client_id": t.client_id,
            "property_id": t.property_id,
            "requirement_type": t.requirement_type,
            "canonical_code": t.canonical_code,
            "note": t.note,
        }
        for t in CONDITION_STANDARD_PILOT_TARGETS
    ]


def _jurisdiction_gate(canon: str, portfolio_label: str) -> Tuple[bool, str]:
    pl = str(portfolio_label or "").strip().lower()
    if canon == "repairing_standard":
        if pl != "scotland":
            return False, f"repairing_standard requires Scotland portfolio (got {portfolio_label!r})"
        return True, ""
    if canon == "fitness_for_human_habitation":
        if pl == "scotland":
            return False, "fitness_for_human_habitation must not surface in Scotland via pilot path"
        return True, ""
    return False, f"unsupported obligation {canon}"


def _tenancy_gate(property_doc: Dict[str, Any]) -> Tuple[bool, str]:
    if property_doc.get("tenancy_active") is True:
        return True, ""
    return False, "tenancy_active must be true for condition-standard pilot materialisation"


def _build_registry_metadata(
    *,
    published_entry: Optional[Dict[str, Any]],
    existing_meta: Optional[Dict[str, Any]],
    pilot_target: ConditionStandardPilotTarget,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    meta.update(_CONDITION_STANDARD_REGISTRY_METADATA_OVERRIDES)
    meta["materialisation_provenance"] = {
        "source": MATERIALISATION_PROVENANCE_SOURCE,
        "pilot_target": {
            "client_id": pilot_target.client_id,
            "property_id": pilot_target.property_id,
            "requirement_type": pilot_target.requirement_type,
            "note": pilot_target.note,
        },
        "materialised_at": datetime.now(timezone.utc).isoformat(),
    }
    if isinstance(published_entry, dict):
        if published_entry.get("why_it_matters_short"):
            meta["why_it_matters_short_published"] = published_entry.get("why_it_matters_short")
        if published_entry.get("why_it_matters_long"):
            meta["why_it_matters_long_published"] = published_entry.get("why_it_matters_long")
        links = published_entry.get("action_links")
        if isinstance(links, list) and links:
            meta["action_links_published"] = [dict(x) for x in links if isinstance(x, dict)]
    return meta


def _description_for(canon: str) -> str:
    if canon == "fitness_for_human_habitation":
        return "Fitness for Human Habitation (operational condition standard)"
    if canon == "repairing_standard":
        return "Repairing Standard (operational condition standard)"
    return "Property condition standard"


async def materialise_condition_standard_pilot_row(
    client_id: str,
    property_id: str,
    requirement_type: str,
    *,
    actor_id: str = "condition_standard_pilot_materialisation",
    force: bool = False,
) -> Dict[str, Any]:
    """
    Upsert a single condition-standard row for an allowlisted pilot property.
    Idempotent per (client_id, property_id, requirement_type).
    """
    cid = str(client_id or "").strip()
    pid = str(property_id or "").strip()
    canon = normalize_requirement_code(requirement_type) or str(requirement_type or "").strip().lower()
    if not is_pilot_materialisation_target(cid, pid, canon):
        return {
            "ok": False,
            "reason": "not_allowlisted_pilot_target",
            "client_id": cid,
            "property_id": pid,
            "requirement_type": canon,
            "allowlisted": list_condition_standard_pilot_targets(),
        }

    pilot = next(
        t for t in CONDITION_STANDARD_PILOT_TARGETS if t.client_id == cid and t.property_id == pid and t.canonical_code == canon
    )
    db = database.get_db()
    property_doc = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0})
    if not property_doc:
        return {"ok": False, "reason": "property_not_found", "client_id": cid, "property_id": pid}

    client_doc = await db.clients.find_one({"client_id": cid}, {"_id": 0, "default_jurisdiction": 1}) or {}
    portfolio_label = portfolio_jurisdiction_label(property_doc, client_doc)
    ok_jur, jur_reason = _jurisdiction_gate(canon, portfolio_label)
    if not ok_jur:
        return {"ok": False, "reason": "jurisdiction_gate_failed", "detail": jur_reason, "portfolio_label": portfolio_label}

    ok_ten, ten_reason = _tenancy_gate(property_doc)
    if not ok_ten:
        return {"ok": False, "reason": "tenancy_gate_failed", "detail": ten_reason}

    published = await fetch_active_published_registry_entries(db)
    published_entry = resolve_published_entry_for_requirement(
        published_registry_entries=published,
        requirement_type=canon,
        portfolio_label=portfolio_label,
        property_doc=property_doc,
        enforce_conditions=False,
    )

    existing = await db.requirements.find_one(
        {"client_id": cid, "property_id": pid, "requirement_type": canon},
        {"_id": 0},
    )
    if existing and not force:
        if str(existing.get("requirement_generation_source") or "") == REQUIREMENT_GENERATION_SOURCE_CONDITION_STANDARD_PILOT:
            return {
                "ok": True,
                "action": "already_materialised",
                "requirement_id": existing.get("requirement_id"),
                "client_id": cid,
                "property_id": pid,
                "requirement_type": canon,
            }

    now = datetime.now(timezone.utc)
    meta = _build_registry_metadata(
        published_entry=published_entry if isinstance(published_entry, dict) else None,
        existing_meta=(existing or {}).get("registry_metadata") if isinstance((existing or {}).get("registry_metadata"), dict) else None,
        pilot_target=pilot,
    )
    policy_seed = {
        **(existing or {}),
        "requirement_code": canon,
        "requirement_type": canon,
        "applicability_state": "REQUIRED",
        "applicability": "REQUIRED",
        "status": RequirementStatus.PENDING.value,
        "is_mandatory": True,
        "policy_criticality": "HIGH",
        "registry_metadata": meta,
    }
    policy_facts = resolve_policy_facts(policy_seed, registry_metadata=meta, catalog_defaults={"is_mandatory": True, "policy_criticality": "HIGH"})

    patch: Dict[str, Any] = {
        "jurisdiction": portfolio_label,
        "description": _description_for(canon),
        "requirement_code": canon,
        "requirement_code_normalized": policy_facts["requirement_code_normalized"],
        "compliance_requirement_class": "OBLIGATION",
        "is_tracked": True,
        "client_surface_visible": True,
        "requires_document": False,
        "requires_job": False,
        "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_CONDITION_STANDARD_PILOT,
        "registry_metadata": meta,
        "is_mandatory": True,
        "policy_criticality": "HIGH",
        "applicability": "REQUIRED",
        "applicability_state": "REQUIRED",
        "evidence_state_normalized": normalized_evidence_state_for_policy(existing or {}),
        "policy_classification_version": POLICY_CLASSIFICATION_VERSION,
        "updated_at": now.isoformat(),
        "workflow_family": "CONDITION_STANDARD_ACTIVE_STANDARD",
        "ops_verification_family": "CONDITION_STANDARD_ACTIVE_STANDARD",
    }
    patch["action_type"] = infer_action_type({**(existing or {}), **patch})

    if existing and existing.get("requirement_id"):
        rid = str(existing["requirement_id"])
        prov_patch = await apply_provenance_and_audit_after_requirement_patch(
            db,
            client_id=cid,
            property_id=pid,
            requirement_id=rid,
            before=dict(existing),
            pipeline_applicability_state="REQUIRED",
            event_type="CONDITION_STANDARD_PILOT_MATERIALISATION_UPDATE",
            actor={"type": "system", "id": actor_id},
        )
        patch.update(prov_patch)
        await db.requirements.update_one({"requirement_id": rid}, {"$set": patch})
        return {
            "ok": True,
            "action": "updated",
            "requirement_id": rid,
            "client_id": cid,
            "property_id": pid,
            "requirement_type": canon,
            "portfolio_label": portfolio_label,
        }

    due = now + timedelta(days=365)
    req = Requirement(
        client_id=cid,
        property_id=pid,
        requirement_type=canon,
        requirement_code=canon,
        jurisdiction=portfolio_label,
        description=_description_for(canon),
        frequency_days=365,
        due_date=due,
        status=RequirementStatus.PENDING,
        compliance_requirement_class="OBLIGATION",
        is_tracked=True,
        client_surface_visible=True,
        requires_document=False,
        requires_job=False,
        requirement_generation_source=REQUIREMENT_GENERATION_SOURCE_CONDITION_STANDARD_PILOT,
        registry_metadata=meta,
        applicability="REQUIRED",
    )
    doc = req.model_dump()
    rid = str(uuid.uuid4())
    doc["requirement_id"] = rid
    doc["workflow_family"] = "CONDITION_STANDARD_ACTIVE_STANDARD"
    doc["ops_verification_family"] = "CONDITION_STANDARD_ACTIVE_STANDARD"
    for key in ("due_date", "created_at", "updated_at"):
        val = doc.get(key)
        if hasattr(val, "isoformat"):
            doc[key] = val.isoformat()
    doc["created_at"] = now.isoformat()
    doc["updated_at"] = now.isoformat()
    await db.requirements.insert_one(doc)
    prov_patch = await apply_provenance_and_audit_after_requirement_patch(
        db,
        client_id=cid,
        property_id=pid,
        requirement_id=rid,
        before={},
        pipeline_applicability_state="REQUIRED",
        event_type="CONDITION_STANDARD_PILOT_MATERIALISATION_INSERT",
        actor={"type": "system", "id": actor_id},
    )
    if prov_patch:
        await db.requirements.update_one({"requirement_id": rid}, {"$set": prov_patch})

    logger.info(
        "condition_standard_pilot_materialised client_id=%s property_id=%s type=%s rid=%s",
        cid,
        pid,
        canon,
        rid,
    )
    return {
        "ok": True,
        "action": "inserted",
        "requirement_id": rid,
        "client_id": cid,
        "property_id": pid,
        "requirement_type": canon,
        "portfolio_label": portfolio_label,
    }


async def materialise_all_condition_standard_pilot_targets(
    *,
    actor_id: str = "condition_standard_pilot_materialisation",
    force: bool = False,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for target in CONDITION_STANDARD_PILOT_TARGETS:
        results.append(
            await materialise_condition_standard_pilot_row(
                target.client_id,
                target.property_id,
                target.requirement_type,
                actor_id=actor_id,
                force=force,
            )
        )
    ok_count = sum(1 for r in results if r.get("ok"))
    return {"ok": ok_count == len(results), "results": results, "targets": len(results)}
