"""
Unified Take Action model for client surfaces: one primary action per requirement,
separated from maintenance flows and aligned with compliance_requirement_class / action_type.

Keep in sync with frontend/src/utils/requirementTakeActionResolver.js (labels and routes).

JOB-class rows: primary routes to the property compliance matrix to record external assessment and evidence;
optional secondary document upload. Multi-mode DOCUMENT rows use a single guided primary (document upload
is chosen inside the guided flow / Documents; no competing upload secondary on the same card).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from services.compliance_requirement_engine import resolve_engine_payload_from_code, resolve_engine_payload_from_requirement_row
from presentation.label_service import requirement_label
from services.requirement_action_links import format_client_external_link, get_client_action_links_for_requirement_row
from services.requirement_code_registry import normalize_requirement_code

from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW,
    EVIDENCE_MODE_INSPECTION_CHECKLIST,
    EVIDENCE_MODE_STRUCTURED_DECLARATION,
    GUIDED_DECLARATION_WORKFLOW,
    REGISTRATION_TRACKING_WORKFLOW,
    TENANT_DELIVERY_WORKFLOW,
    effective_evidence_resolution,
)

ACTION_DOCUMENT = "DOCUMENT"
ACTION_JOB = "JOB"
ACTION_MAINTENANCE = "MAINTENANCE"
ACTION_OBLIGATION = "OBLIGATION"

# Stable primary CTA intent for client/API parity (Requirements, Today, exports).
INTENT_UPLOAD_EVIDENCE = "upload_evidence"
INTENT_VIEW_GUIDANCE = "view_guidance"
INTENT_MAINTENANCE = "maintenance"
# Stable intent: external inspection arranged by landlord/professional; platform coordinates + evidence.
INTENT_COORDINATE_INSPECTION_EVIDENCE = "coordinate_inspection_evidence"
INTENT_BOOK_INSPECTION = INTENT_COORDINATE_INSPECTION_EVIDENCE  # legacy alias
INTENT_GUIDED_EVIDENCE = "guided_evidence_resolution"
INTENT_GUIDED_EVIDENCE_UNAVAILABLE = "guided_evidence_unavailable"
INTENT_DIRECT_EVIDENCE = "direct_evidence_action"

# Client contract: surfaces must not invent parallel requirement CTA wording when take_action is present.
TAKE_ACTION_CONTRACT_VERSION = "requirement_take_action_v1"
PROVENANCE_PUBLISHED_REGISTRY = "published_registry"
PROVENANCE_ENGINE_DEFAULT = "engine_default"

# Obligation-class tenancy codes that still use registry/policy-driven evidence (skip guidance-only routing).
_TENANCY_EVIDENCE_FIRST_CODES = frozenset(
    {
        "how_to_rent",
        "deposit_pi",
        "deposit_prescribed_info",
        "right_to_rent",
        "wales_occupation_contract",
        "tenancy_agreement",
    }
)
_ACTIVE_STANDARD_CODES = frozenset(
    {
        "fitness_for_human_habitation",
        "repairing_standard",
    }
)


def _tenancy_registry_evidence_overrides_informational(requirement: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    code = _norm_code(requirement)
    canon = normalize_requirement_code(code) or code
    # `occupation_contract` is treated as Wales-context alias only; never force evidence-first outside Wales.
    if canon == "occupation_contract":
        req_jur = str(requirement.get("jurisdiction") or requirement.get("property_jurisdiction") or "").strip().lower()
        if req_jur != "wales":
            return False
        canon = "wales_occupation_contract"
    if canon not in _TENANCY_EVIDENCE_FIRST_CODES:
        return False
    modes = [str(m or "").strip().upper() for m in (policy.get("allowed_evidence_modes") or []) if m]
    return len(modes) >= 1


def _norm_code(req_or_code: Any) -> str:
    if isinstance(req_or_code, dict):
        cc = req_or_code.get("canonical_requirement_code")
        if isinstance(cc, str) and cc.strip():
            return str(cc).strip().lower().replace(" ", "_")
        c = req_or_code.get("requirement_code") or req_or_code.get("requirement_type") or ""
    else:
        c = req_or_code or ""
    return str(c).strip().lower().replace(" ", "_")


def _is_active_condition_standard(requirement: Dict[str, Any]) -> bool:
    canon = normalize_requirement_code(_norm_code(requirement)) or _norm_code(requirement)
    return canon in _ACTIVE_STANDARD_CODES


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


def _ordered_unique_evidence_modes(modes: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for m in modes or []:
        u = str(m or "").strip().upper()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _single_non_document_cta_label(mode: str) -> str:
    m = str(mode or "").strip().upper()
    if m == EVIDENCE_MODE_STRUCTURED_DECLARATION:
        return "Submit compliance declaration"
    if m == EVIDENCE_MODE_CONTRACTOR_CONFIRMATION:
        return "Add contractor confirmation"
    if m == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        return "Complete inspection checklist"
    return "Add compliance evidence"


def _document_upload_primary_label(requirement: Dict[str, Any], meta: Dict[str, Any], fallback: str) -> str:
    """cta_label_override applies only to document-upload primary (backward compatible)."""
    cta = str(meta.get("cta_label_override") or "").strip()
    if cta:
        return cta
    code = _norm_code(requirement)
    if "gas" in code or code in ("cp12", "gas_safety", "gas_safety_certificate"):
        return "Upload Gas Safety Certificate"
    if "eicr" in code or "electrical_safety" in code or "electrical_installation" in code:
        return "Upload EICR Certificate"
    if "hmo" in code and "licen" in code:
        return "Upload HMO Licence"
    if "legionella" in code:
        return "Upload assessment report"
    if code in ("lead_testing", "lead_testing_scotland"):
        return "Upload test report"
    if code == "how_to_rent":
        return "Upload delivery proof"
    if code == "right_to_rent":
        return "Upload supporting evidence"
    return fallback


def _guided_multi_mode_primary_label(policy: Dict[str, Any]) -> str:
    s = str(policy.get("guided_primary_cta_label") or "").strip()
    if s:
        return s
    return "Add compliance evidence"


def _is_registration_tracking_policy(policy: Dict[str, Any]) -> bool:
    return str(policy.get("primary_resolution_workflow") or "").strip().upper() == REGISTRATION_TRACKING_WORKFLOW


def _is_tenant_delivery_policy(policy: Dict[str, Any]) -> bool:
    return str(policy.get("primary_resolution_workflow") or "").strip().upper() == TENANT_DELIVERY_WORKFLOW


def _is_guided_declaration_workflow_policy(policy: Dict[str, Any]) -> bool:
    return str(policy.get("primary_resolution_workflow") or "").strip().upper() == GUIDED_DECLARATION_WORKFLOW


def _is_external_assessment_evidence_workflow_policy(policy: Dict[str, Any]) -> bool:
    return (
        str(policy.get("primary_resolution_workflow") or "").strip().upper()
        == EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW
    )


def _legionella_job_guided_structured_access(
    requirement: Dict[str, Any],
    *,
    is_job: bool,
    pid: Optional[str],
    rid: Optional[str],
) -> bool:
    """Bounded OPS-VERIFY: JOB-class legionella with external assessment + structured declaration."""
    if not is_job or not pid or not rid:
        return False
    canon = normalize_requirement_code(_norm_code(requirement)) or _norm_code(requirement)
    if canon != "legionella":
        return False
    policy = effective_evidence_resolution(requirement)
    if not _is_external_assessment_evidence_workflow_policy(policy):
        return False
    modes = {str(m or "").strip().upper() for m in (policy.get("allowed_evidence_modes") or []) if m}
    return EVIDENCE_MODE_STRUCTURED_DECLARATION in modes


def _legionella_job_guided_take_action(
    requirement: Dict[str, Any],
    *,
    pid: str,
    rid: str,
    needs_doc: bool,
    property_jurisdiction: Optional[str],
) -> Dict[str, Any]:
    """JOB semantics preserved; primary opens guided structured declaration (legionella pilot only)."""
    policy = effective_evidence_resolution(requirement)
    doc_route = f"/documents?property_id={pid}&requirement_id={rid}"
    supporting = _supporting_external_links(requirement, property_jurisdiction=property_jurisdiction)
    why_fields = _registry_why_it_matters(requirement)
    sec_upload = None
    if needs_doc:
        sec_lbl = str(policy.get("guided_secondary_upload_label") or "").strip() or "Upload assessment report"
        sec_upload = {
            "label": sec_lbl,
            "route": doc_route,
            "kind": "navigate",
            "handler": "navigate",
            "external": False,
            "intent": INTENT_UPLOAD_EVIDENCE,
        }
    ta_job_guided: Dict[str, Any] = {
        "primary": {
            "label": job_primary_label(requirement),
            "route": None,
            "kind": "guided_evidence_resolution",
            "handler": "guided_evidence",
            "intent": INTENT_GUIDED_EVIDENCE,
            "property_id": str(pid),
            "requirement_id": str(rid),
        },
        "secondary": sec_upload,
        "supporting_external_links": supporting,
    }
    _attach_take_action_contract_metadata(ta_job_guided, requirement)
    return {
        "action_type": ACTION_JOB,
        **why_fields,
        "take_action": ta_job_guided,
    }


def job_primary_label(requirement: Dict[str, Any]) -> str:
    """
    JOB-class primary CTA: evidence-first copy for off-platform professional work; platform does not
    book inspections. Routes to property compliance context to record assessment and upload evidence.
    """
    code = _norm_code(requirement)
    if "eicr" in code or code == "electrical_safety":
        return "Record external assessment evidence — upload EICR"
    if "gas" in code or code in ("cp12", "gas_safety", "gas_safety_certificate"):
        return "Record external assessment evidence — upload Gas Safety certificate"
    if "epc" in code:
        return "Record external assessment evidence — upload EPC"
    if "fire" in code and "risk" in code:
        return "Add fire risk assessment evidence"
    if "pat" in code or "portable_appliance" in code:
        return "Record external assessment evidence — upload PAT evidence"
    if "legionella" in code:
        return "Record Legionella risk assessment"
    if code in ("lead_testing", "lead_testing_scotland"):
        return "Record lead risk assessment"
    disp = str(requirement.get("display_label") or "").strip()
    if disp and disp.lower() not in ("requirement", ""):
        return f"Record external assessment evidence — {disp}"
    rl = requirement_label(requirement.get("requirement_code") or requirement.get("requirement_type") or "")
    if rl and rl.lower() != "requirement":
        return f"Record external assessment evidence — {rl}"
    return "Record external assessment evidence"


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
    if str(meta.get("primary_action_mode") or "").strip().lower() == "hidden" or requirement.get("client_surface_visible") is False:
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
    # Persisted / inferred action_type wins over engine obligation posture: external-assessment specs use
    # fulfillment_mode=obligation while rows may still be DOCUMENT for guided evidence (e.g. lead_testing).
    if action_type in (ACTION_DOCUMENT, ACTION_JOB, ACTION_MAINTENANCE):
        informational = False
    req_for_gate = {
        **requirement,
        "property_jurisdiction": property_jurisdiction or requirement.get("property_jurisdiction"),
    }
    policy_for_informational_gate = effective_evidence_resolution(req_for_gate)
    if informational and _tenancy_registry_evidence_overrides_informational(req_for_gate, policy_for_informational_gate):
        informational = False

    if _is_active_condition_standard(req_for_gate):
        issues_route = f"/operations/issues?property_id={pid}" if pid else "/operations/issues"
        wo_route = f"/operations/work-orders?property_id={pid}" if pid else "/operations/work-orders"
        supporting = _supporting_external_links(requirement, property_jurisdiction=property_jurisdiction)
        why_fields = _registry_why_it_matters(requirement)
        ta_active = {
            "primary": {
                "label": "Manage related issues",
                "route": issues_route,
                "kind": "navigate",
                "handler": "navigate",
                "intent": INTENT_VIEW_GUIDANCE,
            },
            "secondary": {
                "label": "Review remediation progress",
                "route": wo_route,
                "kind": "navigate",
                "handler": "navigate",
                "external": False,
                "intent": INTENT_MAINTENANCE,
            },
            "supporting_external_links": supporting,
        }
        _attach_take_action_contract_metadata(ta_active, requirement)
        return {
            "action_type": ACTION_OBLIGATION,
            **why_fields,
            "take_action": ta_active,
        }

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
        if _legionella_job_guided_structured_access(requirement, is_job=True, pid=pid, rid=rid):
            return _legionella_job_guided_take_action(
                requirement,
                pid=str(pid),
                rid=str(rid),
                needs_doc=needs_doc,
                property_jurisdiction=property_jurisdiction,
            )
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
                "intent": INTENT_COORDINATE_INSPECTION_EVIDENCE,
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

    policy = effective_evidence_resolution(requirement)
    modes = [str(m or "").strip().upper() for m in (policy.get("allowed_evidence_modes") or []) if m]
    ordered_modes = _ordered_unique_evidence_modes(modes)
    non_doc_modes = [m for m in modes if m != EVIDENCE_MODE_DOCUMENT_UPLOAD]
    has_doc_mode = EVIDENCE_MODE_DOCUMENT_UPLOAD in set(modes)

    if non_doc_modes and not (pid and rid):
        logger.warning(
            "resolve_take_action_envelope: non-document evidence modes configured but property_id "
            "or requirement_id missing (code=%s); refusing silent primary fallback to document upload",
            code or "(none)",
        )
        ta_gbroken: Dict[str, Any] = {
            "primary": {
                "label": "Guided resolution unavailable",
                "route": None,
                "kind": "guided_evidence_resolution",
                "handler": "guided_evidence_unavailable",
                "intent": INTENT_GUIDED_EVIDENCE_UNAVAILABLE,
                "metadata_incomplete": True,
            },
            "secondary": (
                {
                    "label": upload_label,
                    "route": doc_route,
                    "kind": "navigate",
                    "handler": "navigate",
                    "external": False,
                    "intent": INTENT_UPLOAD_EVIDENCE,
                }
                if has_doc_mode
                else None
            ),
            "supporting_external_links": supporting,
        }
        _attach_take_action_contract_metadata(ta_gbroken, requirement)
        return {
            "action_type": ACTION_DOCUMENT,
            **why_fields,
            "take_action": ta_gbroken,
        }

    # Single allowed mode: DOCUMENT_UPLOAD — direct upload CTA (registry cta_label_override may refine label).
    if len(ordered_modes) == 1 and ordered_modes[0] == EVIDENCE_MODE_DOCUMENT_UPLOAD:
        doc_primary = _document_upload_primary_label(requirement, meta, upload_label)
        ta_doc_only: Dict[str, Any] = {
            "primary": {
                "label": doc_primary,
                "route": doc_route,
                "kind": "navigate",
                "handler": "navigate",
                "intent": INTENT_UPLOAD_EVIDENCE,
            },
            "secondary": None,
            "supporting_external_links": supporting,
        }
        _attach_take_action_contract_metadata(ta_doc_only, requirement)
        return {
            "action_type": ACTION_DOCUMENT,
            **why_fields,
            "take_action": ta_doc_only,
        }

    # Single allowed non-document mode — one direct CTA (opens selector pre-focused; no per-mode buttons on cards).
    if len(ordered_modes) == 1 and ordered_modes[0] != EVIDENCE_MODE_DOCUMENT_UPLOAD and pid and rid:
        only_mode = ordered_modes[0]
        ta_direct: Dict[str, Any] = {
            "primary": {
                "label": _single_non_document_cta_label(only_mode),
                "route": None,
                "kind": "direct_evidence_action",
                "handler": "direct_evidence",
                "intent": INTENT_DIRECT_EVIDENCE,
                "property_id": str(pid),
                "requirement_id": str(rid),
                "evidence_mode": only_mode,
            },
            "secondary": None,
            "supporting_external_links": supporting,
        }
        _attach_take_action_contract_metadata(ta_direct, requirement)
        return {
            "action_type": ACTION_DOCUMENT,
            **why_fields,
            "take_action": ta_direct,
        }

    # Multiple allowed evidence modes — single guided primary; document paths live in guided modal / Documents.
    if len(ordered_modes) >= 2 and pid and rid and non_doc_modes:
        guided_label = _guided_multi_mode_primary_label(policy)
        ta_guided: Dict[str, Any] = {
            "primary": {
                "label": guided_label,
                "route": None,
                "kind": "guided_evidence_resolution",
                "handler": "guided_evidence",
                "intent": INTENT_GUIDED_EVIDENCE,
                "property_id": str(pid),
                "requirement_id": str(rid),
            },
            "secondary": None,
            "supporting_external_links": supporting,
        }
        if _is_registration_tracking_policy(policy) and has_doc_mode:
            ta_guided["secondary"] = {
                "label": "Upload registration evidence",
                "route": doc_route,
                "kind": "navigate",
                "handler": "navigate",
                "external": False,
                "intent": INTENT_UPLOAD_EVIDENCE,
            }
        elif _is_tenant_delivery_policy(policy) and has_doc_mode:
            ta_guided["secondary"] = {
                "label": "Upload delivery proof",
                "route": doc_route,
                "kind": "navigate",
                "handler": "navigate",
                "external": False,
                "intent": INTENT_UPLOAD_EVIDENCE,
            }
        elif _is_guided_declaration_workflow_policy(policy) and has_doc_mode:
            sec_lbl = str(policy.get("guided_secondary_upload_label") or "").strip() or "Upload supporting evidence"
            ta_guided["secondary"] = {
                "label": sec_lbl,
                "route": doc_route,
                "kind": "navigate",
                "handler": "navigate",
                "external": False,
                "intent": INTENT_UPLOAD_EVIDENCE,
            }
        elif _is_external_assessment_evidence_workflow_policy(policy) and has_doc_mode:
            sec_lbl = str(policy.get("guided_secondary_upload_label") or "").strip() or "Upload assessment report"
            ta_guided["secondary"] = {
                "label": sec_lbl,
                "route": doc_route,
                "kind": "navigate",
                "handler": "navigate",
                "external": False,
                "intent": INTENT_UPLOAD_EVIDENCE,
            }
        _attach_take_action_contract_metadata(ta_guided, requirement)
        return {
            "action_type": ACTION_DOCUMENT,
            **why_fields,
            "take_action": ta_guided,
        }

    ta_doc = {
        "primary": {
            "label": _document_upload_primary_label(requirement, meta, upload_label),
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
    elif isinstance(pri, dict) and pri.get("kind") in ("guided_evidence_resolution", "direct_evidence_action"):
        primary_type = "guided_evidence_resolution"
    else:
        primary_type = "upload_evidence"

    if primary_type == "guided_evidence_resolution":
        primary_action_url = ""
    else:
        raw_route = pri.get("route") if isinstance(pri, dict) else None
        primary_action_url = str(raw_route or "").strip() or "/dashboard"

    out: Dict[str, Any] = {
        "primary_action_type": primary_type,
        "primary_action_label": pri.get("label") or "View",
        "primary_action_url": primary_action_url,
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


def enrich_take_action_envelope_for_client(
    env: Dict[str, Any],
    requirement: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Attach workflow_class, allowed_evidence_modes, and guidance_target so clients can rely on server
    metadata instead of duplicating policy inference.
    """
    merged: Dict[str, Any] = dict(env)
    policy = effective_evidence_resolution(requirement)
    merged["allowed_evidence_modes"] = _ordered_unique_evidence_modes(
        [str(m or "").strip().upper() for m in (policy.get("allowed_evidence_modes") or []) if m]
    )
    wf = str(policy.get("primary_resolution_workflow") or "").strip()
    at = env.get("action_type")
    ta = env.get("take_action") or {}
    pri = ta.get("primary") if isinstance(ta.get("primary"), dict) else {}
    intent = str(pri.get("intent") or "").strip()

    if intent == INTENT_VIEW_GUIDANCE:
        merged["workflow_class"] = "GUIDANCE_ONLY"
    elif isinstance(pri, dict) and pri.get("kind") in ("guided_evidence_resolution", "direct_evidence_action"):
        wf_u = str(wf or "").strip().upper()
        if wf_u == REGISTRATION_TRACKING_WORKFLOW:
            merged["workflow_class"] = REGISTRATION_TRACKING_WORKFLOW
        elif wf_u == TENANT_DELIVERY_WORKFLOW:
            merged["workflow_class"] = TENANT_DELIVERY_WORKFLOW
        elif wf_u == GUIDED_DECLARATION_WORKFLOW:
            merged["workflow_class"] = GUIDED_DECLARATION_WORKFLOW
        elif wf_u == EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW:
            merged["workflow_class"] = EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW
        else:
            modes_list = merged.get("allowed_evidence_modes") or []
            pub_cwc = str(policy.get("client_workflow_class") or "").strip().upper()
            if pub_cwc == "MULTI_EVIDENCE":
                merged["workflow_class"] = "MULTI_EVIDENCE"
            elif isinstance(modes_list, list) and len(modes_list) >= 2 and wf_u in ("", "GUIDED_EVIDENCE_RESOLUTION"):
                merged["workflow_class"] = "MULTI_EVIDENCE"
            else:
                merged["workflow_class"] = wf or "GUIDED_EVIDENCE_RESOLUTION"
    elif at == ACTION_JOB:
        merged["workflow_class"] = "REMEDIATION_JOB"
    elif str(wf or "").strip().upper() == REGISTRATION_TRACKING_WORKFLOW:
        merged["workflow_class"] = REGISTRATION_TRACKING_WORKFLOW
    elif str(wf or "").strip().upper() == TENANT_DELIVERY_WORKFLOW:
        merged["workflow_class"] = TENANT_DELIVERY_WORKFLOW
    elif str(wf or "").strip().upper() == GUIDED_DECLARATION_WORKFLOW:
        merged["workflow_class"] = GUIDED_DECLARATION_WORKFLOW
    elif str(wf or "").strip().upper() == EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW:
        merged["workflow_class"] = EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW
    elif wf:
        merged["workflow_class"] = wf
    else:
        merged["workflow_class"] = "LEGACY_DOCUMENT_UPLOAD"

    route = pri.get("route") if pri else None
    if intent == INTENT_VIEW_GUIDANCE and route:
        merged["guidance_target"] = {
            "type": "property_compliance_tab",
            "route": str(route),
            "hash": "compliance",
        }
    elif intent == INTENT_VIEW_GUIDANCE:
        merged["guidance_target"] = {"type": "requirements_list", "route": "/requirements"}
    else:
        merged["guidance_target"] = None

    return merged
