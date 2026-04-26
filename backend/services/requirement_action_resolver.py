"""
Unified Take Action model for client surfaces: one primary action per requirement,
separated from maintenance flows and aligned with compliance_requirement_class / action_type.

Keep in sync with frontend/src/utils/requirementTakeActionResolver.js (labels and routes).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_requirement_engine import resolve_engine_payload_from_code, resolve_engine_payload_from_requirement_row
from presentation.label_service import requirement_label
from services.requirement_action_links import format_client_external_link, get_client_action_links_for_requirement_row

ACTION_DOCUMENT = "DOCUMENT"
ACTION_JOB = "JOB"
ACTION_MAINTENANCE = "MAINTENANCE"
ACTION_OBLIGATION = "OBLIGATION"

# Stable primary CTA intent for client/API parity (Requirements, Today, exports).
INTENT_UPLOAD_EVIDENCE = "upload_evidence"
INTENT_VIEW_GUIDANCE = "view_guidance"
INTENT_MAINTENANCE = "maintenance"
INTENT_BOOK_INSPECTION = "book_inspection"

# Client contract: surfaces must not invent parallel requirement CTA wording when take_action is present.
TAKE_ACTION_CONTRACT_VERSION = "requirement_take_action_v1"
PROVENANCE_PUBLISHED_REGISTRY = "published_registry"
PROVENANCE_ENGINE_DEFAULT = "engine_default"


def _norm_code(req_or_code: Any) -> str:
    if isinstance(req_or_code, dict):
        c = req_or_code.get("requirement_code") or req_or_code.get("requirement_type") or ""
    else:
        c = req_or_code or ""
    return str(c).strip().lower().replace(" ", "_")


def infer_action_type(requirement: Dict[str, Any]) -> str:
    """Persisted action_type wins; else derive from compliance class and flags."""
    stored = str(requirement.get("action_type") or "").strip().upper()
    if stored in (ACTION_DOCUMENT, ACTION_JOB, ACTION_MAINTENANCE, ACTION_OBLIGATION):
        return stored
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    if str(meta.get("primary_action_mode") or "").strip().lower() == "hidden":
        return ACTION_OBLIGATION
    cls = str(requirement.get("compliance_requirement_class") or requirement.get("requirement_class") or "").strip().upper()
    if cls == "JOB":
        return ACTION_JOB
    if cls in ("OBLIGATION", "SYSTEM"):
        return ACTION_OBLIGATION
    if cls == "DOCUMENT":
        return ACTION_DOCUMENT
    if requirement.get("requires_job") and not requirement.get("requires_document"):
        return ACTION_JOB
    if requirement.get("requires_document"):
        return ACTION_DOCUMENT
    return ACTION_DOCUMENT


def _supporting_external_links(
    requirement: Dict[str, Any],
    *,
    property_jurisdiction: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Up to 2 jurisdiction-filtered links from registry (or registry_metadata override)."""
    raw = get_client_action_links_for_requirement_row(
        requirement,
        portfolio_jurisdiction_label=property_jurisdiction or requirement.get("jurisdiction"),
    )
    return [format_client_external_link(x) for x in raw]


def _registry_why_it_matters(requirement: Dict[str, Any]) -> Dict[str, Optional[str]]:
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    short = str(
        requirement.get("why_it_matters_short")
        or meta.get("why_it_matters_short_published")
        or requirement.get("why_it_matters")
        or ""
    ).strip()
    long_text = str(
        requirement.get("why_it_matters_long")
        or meta.get("why_it_matters_long_published")
        or ""
    ).strip()
    return {
        "why_it_matters_short": short or None,
        "why_it_matters_long": long_text or None,
        "why_it_matters": short or long_text or None,
    }


def _primary_label_provenance(requirement: Dict[str, Any]) -> str:
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    if str(meta.get("cta_label_override") or "").strip():
        return PROVENANCE_PUBLISHED_REGISTRY
    return PROVENANCE_ENGINE_DEFAULT


def _supporting_links_provenance(requirement: Dict[str, Any]) -> str:
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    links = meta.get("action_links_published")
    if isinstance(links, list) and len(links) > 0:
        return PROVENANCE_PUBLISHED_REGISTRY
    return PROVENANCE_ENGINE_DEFAULT


def _attach_take_action_contract_metadata(take_action: Dict[str, Any], requirement: Dict[str, Any]) -> None:
    """Mutates take_action dict in place: provenance + contract for client surfaces (Today, lists, etc.)."""
    if not isinstance(take_action, dict):
        return
    take_action["contract"] = TAKE_ACTION_CONTRACT_VERSION
    take_action["provenance"] = {
        "primary_label": _primary_label_provenance(requirement),
        "supporting_links": _supporting_links_provenance(requirement),
        "source_type": "requirement",
    }


def job_primary_label(requirement: Dict[str, Any]) -> str:
    code = _norm_code(requirement)
    if "eicr" in code or code == "electrical_safety":
        return "Book electrical inspection"
    if "gas" in code or code in ("cp12", "gas_safety", "gas_safety_certificate"):
        return "Book gas safety inspection"
    if "epc" in code:
        return "Book EPC assessment"
    if "fire" in code and "risk" in code:
        return "Book fire risk assessment"
    if "pat" in code or "portable_appliance" in code:
        return "Book PAT testing"
    if "legionella" in code:
        return "Book legionella assessment"
    disp = str(requirement.get("display_label") or "").strip()
    if disp and disp.lower() not in ("requirement", ""):
        return f"Book inspection — {disp}"
    rl = requirement_label(requirement.get("requirement_code") or requirement.get("requirement_type") or "")
    if rl and rl.lower() != "requirement":
        return f"Book inspection — {rl}"
    return "Book inspection / arrange compliance"


def _engine(requirement: Dict[str, Any]) -> Dict[str, Any]:
    if requirement.get("engine_fulfillment_mode") is not None or requirement.get("compliance_requirement_class"):
        return resolve_engine_payload_from_requirement_row(requirement)
    code = requirement.get("requirement_code") or requirement.get("requirement_type")
    if code:
        return resolve_engine_payload_from_code(str(code).strip())
    return {}


def resolve_take_action_envelope(
    requirement: Dict[str, Any],
    *,
    property_id: Optional[str] = None,
    property_jurisdiction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single client-facing action contract for a requirement row (enriched or raw).

    Returns:
      action_type, take_action: { primary: {label, route, kind, handler}, secondary?: {...},
      contract, provenance }
    """
    pid = property_id or requirement.get("property_id")
    rid = requirement.get("requirement_id")
    code = requirement.get("requirement_code") or requirement.get("requirement_type") or ""
    eng = _engine(requirement)
    action_type = infer_action_type(requirement)
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    if str(meta.get("primary_action_mode") or "").strip().lower() == "hidden":
        why_fields = _registry_why_it_matters(requirement)
        ta_hidden = {
            "primary": None,
            "secondary": None,
            "supporting_external_links": [],
            "suppressed": True,
        }
        _attach_take_action_contract_metadata(ta_hidden, requirement)
        return {
            "action_type": ACTION_OBLIGATION,
            **why_fields,
            "take_action": ta_hidden,
        }

    cls = str(eng.get("compliance_requirement_class") or requirement.get("compliance_requirement_class") or "").upper()
    ff = str(eng.get("fulfillment_mode") or eng.get("engine_fulfillment_mode") or "").lower()
    informational = (
        action_type == ACTION_OBLIGATION
        or cls in ("OBLIGATION", "SYSTEM")
        or eng.get("engine_informational") is True
        or str(eng.get("engine_client_visibility") or "").lower() == "informational"
        or ff == "obligation"
    )
    if informational:
        route = f"/properties/{pid}#compliance" if pid else "/requirements"
        supporting = _supporting_external_links(requirement, property_jurisdiction=property_jurisdiction)
        why_fields = _registry_why_it_matters(requirement)
        ta_inf = {
            "primary": {
                "label": "View guidance",
                "route": route,
                "kind": "navigate",
                "handler": "navigate",
                "intent": INTENT_VIEW_GUIDANCE,
            },
            "secondary": None,
            "supporting_external_links": supporting,
        }
        _attach_take_action_contract_metadata(ta_inf, requirement)
        return {
            "action_type": ACTION_OBLIGATION,
            **why_fields,
            "take_action": ta_inf,
        }

    if action_type == ACTION_MAINTENANCE:
        route = f"/operations/issues/new?property_id={pid}" if pid else "/operations/issues"
        why_fields = _registry_why_it_matters(requirement)
        ta_maint = {
            "primary": {
                "label": "Log issue",
                "route": route,
                "kind": "navigate",
                "handler": "navigate",
                "intent": INTENT_MAINTENANCE,
            },
            "secondary": None,
            "supporting_external_links": [],
        }
        _attach_take_action_contract_metadata(ta_maint, requirement)
        return {
            "action_type": ACTION_MAINTENANCE,
            **why_fields,
            "take_action": ta_maint,
        }

    is_job = cls == "JOB" or ff == "job"
    needs_doc = eng.get("requires_document_evidence", True) is not False

    if is_job:
        hash_frag = f"#req={code}" if code else ""
        primary_route = f"/properties/{pid}{hash_frag}" if pid else "/requirements"
        sec_upload = None
        if needs_doc and pid and rid:
            sec_upload = {
                "label": "Upload document",
                "route": f"/documents?property_id={pid}&requirement_id={rid}",
                "kind": "navigate",
                "handler": "navigate",
                "external": False,
                "intent": INTENT_UPLOAD_EVIDENCE,
            }
        supporting = _supporting_external_links(requirement, property_jurisdiction=property_jurisdiction)
        why_fields = _registry_why_it_matters(requirement)
        ta_job = {
            "primary": {
                "label": job_primary_label(requirement),
                "route": primary_route,
                "kind": "navigate",
                "handler": "navigate",
                "intent": INTENT_BOOK_INSPECTION,
            },
            "secondary": sec_upload,
            "supporting_external_links": supporting,
        }
        _attach_take_action_contract_metadata(ta_job, requirement)
        return {
            "action_type": ACTION_JOB,
            **why_fields,
            "take_action": ta_job,
        }

    doc_route = f"/documents?property_id={pid}&requirement_id={rid}" if (pid and rid) else (f"/documents?property_id={pid}" if pid else "/documents")
    supporting = _supporting_external_links(requirement, property_jurisdiction=property_jurisdiction)
    why_fields = _registry_why_it_matters(requirement)
    cta = str(meta.get("cta_label_override") or "").strip()
    upload_label = cta if cta else "Upload document"
    ta_doc = {
        "primary": {
            "label": upload_label,
            "route": doc_route,
            "kind": "navigate",
            "handler": "navigate",
            "intent": INTENT_UPLOAD_EVIDENCE,
        },
        "secondary": None,
        "supporting_external_links": supporting,
    }
    _attach_take_action_contract_metadata(ta_doc, requirement)
    return {
        "action_type": ACTION_DOCUMENT,
        **why_fields,
        "take_action": ta_doc,
    }


def resolve_take_action_for_priority_action(
    action_row: Dict[str, Any],
    *,
    compliance_engine: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Map client_priority_stream row + optional engine payload to primary/secondary URLs and labels
    for unified_tasks_service (requirement-sourced actions only).
    """
    prop_id = (action_row.get("related_property_id") or "").strip() or None
    rid = (action_row.get("related_requirement_id") or "").strip() or None
    code = str(action_row.get("requirement_code") or "").strip()
    eng = compliance_engine
    if not eng and code:
        eng = resolve_engine_payload_from_code(code)
    if not eng:
        eng = {}

    synthetic: Dict[str, Any] = {
        "requirement_id": rid,
        "property_id": prop_id,
        "requirement_code": code,
        "requirement_type": code,
        "jurisdiction": action_row.get("jurisdiction"),
    }
    rm = action_row.get("registry_metadata")
    if isinstance(rm, dict) and rm:
        merged_rm = {**(synthetic.get("registry_metadata") or {}), **rm}
        synthetic["registry_metadata"] = merged_rm
    disp = action_row.get("display_label")
    if disp and not synthetic.get("display_label"):
        synthetic["display_label"] = disp
    for k, v in eng.items():
        if v is not None:
            synthetic[k] = v
    synthetic["compliance_requirement_class"] = eng.get("compliance_requirement_class") or synthetic.get("compliance_requirement_class")

    env = resolve_take_action_envelope(
        synthetic,
        property_id=prop_id,
        property_jurisdiction=action_row.get("jurisdiction"),
    )
    ta = env.get("take_action") or {}
    pri = ta.get("primary") or {}
    sec = ta.get("secondary")
    at = env.get("action_type")
    if at == ACTION_OBLIGATION:
        primary_type = "view_requirement"
    elif at == ACTION_JOB:
        primary_type = "work_order"
    else:
        primary_type = "upload_evidence"

    out: Dict[str, Any] = {
        "primary_action_type": primary_type,
        "primary_action_label": pri.get("label") or "View",
        "primary_action_url": pri.get("route") or "/dashboard",
        "why_it_matters_short": env.get("why_it_matters_short"),
        "why_it_matters_long": env.get("why_it_matters_long"),
    }
    if sec and sec.get("route"):
        out["secondary_action_label"] = sec.get("label")
        out["secondary_action_url"] = sec.get("route")
        out["secondary_action_external"] = bool(sec.get("external"))
    else:
        out["secondary_action_label"] = None
        out["secondary_action_url"] = None
        out["secondary_action_external"] = False
    out["supporting_external_links"] = list(ta.get("supporting_external_links") or [])
    return out


def persist_default_action_type(requirement: Dict[str, Any]) -> str:
    """Value to set on new/updated requirement documents when action_type omitted."""
    return infer_action_type(requirement)
