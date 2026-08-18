"""Infer communication family and extract context from authoritative requirement rows."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from lifecycle_communication.constants import LifecycleFamily

_ATTENTION_TO_FAMILY: Dict[str, str] = {
    "CERTIFICATE_EXPIRING": "EXPIRY_BASED",
    "REVIEW_DUE": "REVIEW_BASED",
    "EVENT_ACTION_REQUIRED": "EVENT_BASED",
    "TENANCY_TERM_ENDING": "TENANCY_LIFECYCLE",
    "OCCUPANCY_REVIEW_DUE": "OCCUPANCY_LIFECYCLE",
    "OPERATIONAL_ACTION_REQUIRED": "OPERATIONAL",
}

_SEMANTICS_TO_FAMILY: Dict[str, str] = {
    "EXPIRY_BASED": "EXPIRY_BASED",
    "REVIEW_BASED": "REVIEW_BASED",
    "EVENT_BASED": "EVENT_BASED",
    "DECLARATION_BASED": "DECLARATION_BASED",
    "TENANCY_LIFECYCLE": "TENANCY_LIFECYCLE",
    "OCCUPANCY_LIFECYCLE": "OCCUPANCY_LIFECYCLE",
    "OPERATIONAL": "OPERATIONAL",
}


def _norm_code(requirement: Dict[str, Any]) -> str:
    return str(
        requirement.get("requirement_code")
        or requirement.get("requirement_type")
        or ""
    ).strip().lower()


def _primary_evidence_mode(requirement: Dict[str, Any]) -> str:
    modes = requirement.get("allowed_evidence_modes")
    if isinstance(modes, list) and modes:
        return str(modes[0] or "").strip().upper()
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    mode = meta.get("primary_evidence_mode") or meta.get("evidence_mode")
    return str(mode or "").strip().upper()


def _workflow_class(requirement: Dict[str, Any]) -> str:
    return str(requirement.get("workflow_class") or "").strip().upper()


def infer_communication_family(requirement: Dict[str, Any]) -> LifecycleFamily:
    """
    Map authoritative row fields to a communication family without reclassifying requirements.
    """
    row = requirement if isinstance(requirement, dict) else {}
    attention = str(
        row.get("lifecycle_attention_kind")
        or row.get("attention_kind")
        or ""
    ).strip().upper()
    if attention in _ATTENTION_TO_FAMILY:
        base = _ATTENTION_TO_FAMILY[attention]
        if base == "EXPIRY_BASED":
            return _refine_expiry_family(row)
        return base  # type: ignore[return-value]

    semantics = str(row.get("lifecycle_semantics") or "").strip().upper()
    if semantics == "EXPIRY_BASED":
        return _refine_expiry_family(row)
    if semantics in _SEMANTICS_TO_FAMILY:
        fam = _SEMANTICS_TO_FAMILY[semantics]
        if fam == "DECLARATION_BASED":
            return _refine_declaration_family(row)
        return fam  # type: ignore[return-value]

    mode = _primary_evidence_mode(row)
    if mode in ("STRUCTURED_DECLARATION", "GUIDED_DECLARATION"):
        return _refine_declaration_family(row)
    if mode == "INSPECTION_CHECKLIST":
        return "INSPECTION"
    if mode in ("CONTRACTOR_CONFIRMATION",):
        return "DOCUMENT_EVIDENCE"

    wf = _workflow_class(row)
    if wf == "GUIDED_DECLARATION":
        return _refine_declaration_family(row)
    if wf == "EXTERNAL_ASSESSMENT_EVIDENCE":
        return "ASSESSMENT"
    if wf in ("REGISTRATION_TRACKING",):
        return "REGISTRATION"
    if wf in ("TENANT_DELIVERY",):
        return "TENANCY_LIFECYCLE"

    action_type = str(row.get("action_type") or "").strip().upper()
    if action_type == "MAINTENANCE":
        return "OPERATIONAL"

    cls = str(row.get("compliance_requirement_class") or "").strip().upper()
    if cls == "OPERATIONAL":
        return "OPERATIONAL"

    return "DOCUMENT_EVIDENCE"


def _refine_expiry_family(row: Dict[str, Any]) -> LifecycleFamily:
    code = _norm_code(row)
    if "licen" in code or code in ("hmo_license", "hmo_licence"):
        return "LICENSING"
    if "registration" in code or "register" in code:
        return "REGISTRATION"
    wf = _workflow_class(row)
    if wf == "EXTERNAL_ASSESSMENT_EVIDENCE":
        return "ASSESSMENT"
    if wf in ("MULTI_EVIDENCE", "REGISTRATION_TRACKING"):
        return "DOCUMENT_EVIDENCE" if wf == "MULTI_EVIDENCE" else "REGISTRATION"
    if code in ("hmo_fire_risk", "hmo_fire_risk_evidence", "fire_risk_assessment") or "hmo_fire" in code:
        return "DOCUMENT_EVIDENCE"
    mode = _primary_evidence_mode(row)
    if mode == "EXTERNAL_ASSESSMENT_EVIDENCE":
        return "ASSESSMENT"
    return "EXPIRY_BASED"


def _refine_declaration_family(row: Dict[str, Any]) -> LifecycleFamily:
    code = _norm_code(row)
    if "self" in code and "cert" in code:
        return "SELF_CERTIFIED"
    mode = _primary_evidence_mode(row)
    if mode == "STRUCTURED_DECLARATION":
        return "STRUCTURED_EVIDENCE"
    return "DECLARATION_BASED"


def requirement_display_name(requirement: Dict[str, Any]) -> str:
    name = str(requirement.get("requirement_name") or "").strip()
    if name:
        return name
    code = str(requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip()
    if code:
        try:
            from presentation.label_service import requirement_label

            return requirement_label(code, audience="client")
        except Exception:
            pass
        return code.replace("_", " ").title()
    return "Compliance obligation"


def property_display_address(requirement: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
    ctx = context if isinstance(context, dict) else {}
    for key in ("property_address", "prop_addr", "address"):
        val = str(ctx.get(key) or requirement.get(key) or "").strip()
        if val:
            return val
    return "your property"


def resolve_due_context(
    requirement: Dict[str, Any],
    *,
    context: Optional[Dict[str, Any]] = None,
    is_overdue: bool = False,
    due_date: Optional[str] = None,
    days_remaining: Optional[int] = None,
    days_overdue: Optional[int] = None,
) -> Tuple[str, str, bool]:
    """Return (due_date_text, urgency, is_overdue_effective)."""
    ctx = context if isinstance(context, dict) else {}
    date_text = str(
        due_date
        or ctx.get("due_date")
        or ctx.get("expiry_date")
        or requirement.get("due_date")
        or requirement.get("expiry_date")
        or requirement.get("next_review_date")
        or ""
    ).strip()

    status = str(requirement.get("status") or "").strip().upper()
    lc_state = str(requirement.get("client_lifecycle_state") or "").strip().upper()
    overdue_effective = bool(is_overdue) or status in ("OVERDUE", "EXPIRED", "FAILED")
    if lc_state == "ACTION_REQUIRED" and status in ("OVERDUE", "EXPIRED"):
        overdue_effective = True

    if days_overdue is not None and int(days_overdue) > 0:
        overdue_effective = True
    if days_remaining is not None and int(days_remaining) < 0:
        overdue_effective = True

    if overdue_effective:
        urgency = "overdue"
    elif status == "EXPIRING_SOON" or (days_remaining is not None and 0 <= int(days_remaining) <= 30):
        urgency = "due_soon"
    elif lc_state == "ACTION_REQUIRED":
        urgency = "action_required"
    elif lc_state == "PENDING_REVIEW":
        urgency = "awaiting_review"
    elif lc_state in ("VERIFIED", "SATISFIED_UNVERIFIED"):
        urgency = "satisfied"
    else:
        urgency = "monitoring"

    return date_text, urgency, overdue_effective


def attention_kind_for_row(requirement: Dict[str, Any]) -> Optional[str]:
    kind = str(
        requirement.get("lifecycle_attention_kind")
        or requirement.get("attention_kind")
        or ""
    ).strip().upper()
    if kind:
        return kind
    family = infer_communication_family(requirement)
    family_to_attention = {
        "EXPIRY_BASED": "CERTIFICATE_EXPIRING",
        "LICENSING": "CERTIFICATE_EXPIRING",
        "REGISTRATION": "CERTIFICATE_EXPIRING",
        "REVIEW_BASED": "REVIEW_DUE",
        "EVENT_BASED": "EVENT_ACTION_REQUIRED",
        "TENANCY_LIFECYCLE": "TENANCY_TERM_ENDING",
        "OCCUPANCY_LIFECYCLE": "OCCUPANCY_REVIEW_DUE",
        "OPERATIONAL": "OPERATIONAL_ACTION_REQUIRED",
    }
    return family_to_attention.get(family)
