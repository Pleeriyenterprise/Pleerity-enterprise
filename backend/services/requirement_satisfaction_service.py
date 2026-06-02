"""
Central requirement satisfaction vs document-gap truth.

Requirement satisfaction must not depend only on uploaded documents.
Surfaces (Documents banner, Requirements counts, Admin panel, Today/CC) must
converge on the same authoritative fields attached during client enrichment.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.cer_governance_presentation import (
    DOCUMENT_PRIMARY_CODES,
    GF_ORG,
    GF_PLATFORM_OPT,
    GF_PLATFORM_VER,
    GF_SELF,
)
from services.client_requirement_lifecycle import (
    ACTION_REQUIRED,
    NOT_APPLICABLE,
    PENDING_REVIEW,
    SATISFIED_UNVERIFIED,
    VERIFIED,
)
from services.compliance_requirement_engine import resolve_engine_payload_from_requirement_row
from services.requirement_attention_eligibility_service import (
    SATISFIED_TRUTH_STAGES,
    is_requirement_attention_eligible,
)
from services.requirement_evidence_authority import (
    EA_NOT_REQUIRED,
    EA_PENDING_ADMIN_REVIEW,
    EA_VERIFIED_CURRENT,
    authority_state,
)

RESOLUTION_RESOLVED = "RESOLVED"
RESOLUTION_UNRESOLVED = "UNRESOLVED"
RESOLUTION_AWAITING_REVIEW = "AWAITING_REVIEW"
RESOLUTION_FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
RESOLUTION_NOT_APPLICABLE = "NOT_APPLICABLE"

MISSING_DOC_NONE = "NONE"
MISSING_DOC_REQUIRED = "REQUIRED_MISSING"
MISSING_DOC_NOT_APPLICABLE = "NOT_REQUIRED"

SOURCE_VERIFIED_DOCUMENT = "verified_document"
SOURCE_ACCEPTED_DECLARATION = "accepted_declaration"
SOURCE_SELF_CERTIFIED = "self_certified_record"
SOURCE_ORG_REVIEW = "org_review"
SOURCE_PLATFORM_VERIFICATION = "platform_verification"
SOURCE_FOLLOW_UP_CLOSURE = "follow_up_closure"
SOURCE_NOT_APPLICABLE = "not_applicable"
SOURCE_CONTRACTOR_CONFIRMATION = "contractor_confirmation"
SOURCE_UNRESOLVED = "unresolved"


def _status_upper(value: Any) -> str:
    return str(value or "").strip().upper()


def non_document_evidence_on_file(row: Dict[str, Any]) -> bool:
    """True when authoritative non-document evidence (CER) is linked on the requirement."""
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    if str(ea.get("primary_evidence_record_id") or row.get("primary_evidence_record_id") or "").strip():
        return True
    truth = str(row.get("truth_presentation_stage") or "").lower()
    return truth in SATISFIED_TRUTH_STAGES and truth not in ("verified",)


def legacy_due_date_blocks_renewal_attention(row: Dict[str, Any]) -> bool:
    """
    Legacy calendar due_date must not force renewal attention on non-document declarations
    when authority carries no effective expiry (e.g. legionella assessment on file).
    """
    if document_upload_required(row):
        return True
    if not non_document_evidence_on_file(row):
        return True
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    return bool(ea.get("effective_expiry_date") or row.get("expiry_date"))


_NON_DOCUMENT_GOVERNANCE_FAMILIES = frozenset({GF_SELF, GF_ORG, GF_PLATFORM_OPT})


def document_upload_required(row: Dict[str, Any]) -> bool:
    """True when Family D / engine policy expects an uploaded document for satisfaction."""
    family = str(row.get("governance_family") or "").strip()
    if family in _NON_DOCUMENT_GOVERNANCE_FAMILIES:
        return False
    if family == GF_PLATFORM_VER:
        return True
    if row.get("document_upload_required") is not None:
        return bool(row.get("document_upload_required"))
    if row.get("requires_document") is not None:
        return bool(row.get("requires_document"))
    engine = resolve_engine_payload_from_requirement_row(row)
    if engine.get("requires_document_evidence") is not None:
        return bool(engine.get("requires_document_evidence"))
    if family == GF_PLATFORM_VER:
        return True
    code = str(row.get("requirement_code") or row.get("requirement_type") or "").strip().lower()
    from services.requirement_code_registry import normalize_requirement_code

    canon = normalize_requirement_code(code) or code.replace(" ", "_")
    if canon in DOCUMENT_PRIMARY_CODES:
        return True
    fulfillment = str(engine.get("fulfillment_mode") or "").lower()
    req_class = str(engine.get("compliance_requirement_class") or engine.get("requirement_class") or "").upper()
    if fulfillment == "document" or req_class == "DOCUMENT":
        return True
    return False


def is_requirement_satisfied(row: Dict[str, Any]) -> bool:
    """Authoritative satisfaction — obligation met by any valid evidence path."""
    r = dict(row or {})
    lifecycle = _status_upper(r.get("client_lifecycle_state"))
    if lifecycle == NOT_APPLICABLE:
        return True

    eligible, _, suppression = is_requirement_attention_eligible(r)
    if eligible:
        return False

    truth_stage = str(r.get("truth_presentation_stage") or "").lower()
    if truth_stage in SATISFIED_TRUTH_STAGES:
        return True

    if lifecycle in (VERIFIED, SATISFIED_UNVERIFIED):
        return True

    ea_st = _status_upper(authority_state(r))
    if ea_st in (EA_VERIFIED_CURRENT, EA_NOT_REQUIRED):
        return True

    if suppression is not None:
        return True

    return False


def derive_satisfaction_source(row: Dict[str, Any]) -> str:
    r = dict(row or {})
    lifecycle = _status_upper(r.get("client_lifecycle_state"))
    if lifecycle == NOT_APPLICABLE or _status_upper(r.get("status")) in ("NOT_APPLICABLE", "NOT_REQUIRED", "WAIVED"):
        return SOURCE_NOT_APPLICABLE

    truth_stage = str(r.get("truth_presentation_stage") or "").lower()
    family = str(r.get("governance_family") or "").strip()
    ea_st = _status_upper(authority_state(r))
    sem = _status_upper(r.get("semantic_state"))

    if truth_stage == "verified" or ea_st == EA_VERIFIED_CURRENT:
        return SOURCE_VERIFIED_DOCUMENT
    if truth_stage == "declaration_recorded" or sem == "DECLARATION_RECORDED":
        if family == "SELF_CERTIFIED":
            return SOURCE_SELF_CERTIFIED
        if family == "ORG_ADMIN_REVIEWED":
            return SOURCE_ORG_REVIEW
        return SOURCE_ACCEPTED_DECLARATION
    if truth_stage in ("evidence_recorded", "assessment_recorded", "recorded_on_file"):
        if family == "SELF_CERTIFIED":
            return SOURCE_SELF_CERTIFIED
        if family == "ORG_ADMIN_REVIEWED":
            return SOURCE_ORG_REVIEW
        if document_upload_required(r):
            return SOURCE_VERIFIED_DOCUMENT if bool(r.get("document_id") or r.get("evidence_doc_id")) else SOURCE_ACCEPTED_DECLARATION
        return SOURCE_ACCEPTED_DECLARATION
    if truth_stage in ("platform_verification_pending", "org_verification_pending") or ea_st == EA_PENDING_ADMIN_REVIEW:
        return SOURCE_PLATFORM_VERIFICATION if family == GF_PLATFORM_VER else SOURCE_ORG_REVIEW
    if truth_stage in ("followup_required", "operational_incomplete"):
        return SOURCE_FOLLOW_UP_CLOSURE if is_requirement_satisfied(r) else SOURCE_UNRESOLVED
    if str(r.get("operational_completion_mode") or "").endswith("contractor"):
        return SOURCE_CONTRACTOR_CONFIRMATION

    if is_requirement_satisfied(r):
        if document_upload_required(r) and bool(r.get("document_id") or r.get("evidence_doc_id")):
            return SOURCE_VERIFIED_DOCUMENT
        if not document_upload_required(r):
            return SOURCE_SELF_CERTIFIED
        return SOURCE_ACCEPTED_DECLARATION
    return SOURCE_UNRESOLVED


def derive_missing_document_status(row: Dict[str, Any]) -> str:
    """Document gap only — not the same as requirement unresolved."""
    if not document_upload_required(row):
        return MISSING_DOC_NOT_APPLICABLE
    has_doc = bool(str(row.get("document_id") or row.get("evidence_doc_id") or "").strip())
    if has_doc:
        return MISSING_DOC_NONE
    if is_requirement_satisfied(row):
        return MISSING_DOC_NONE
    return MISSING_DOC_REQUIRED


def row_counts_as_missing_evidence(row: Dict[str, Any]) -> bool:
    """True when a portal-visible row belongs in the missing-documents bucket (not engine PENDING alone)."""
    r = dict(row or {})
    if r.get("requirement_satisfied") is True:
        return False
    if r.get("missing_required_document") is False:
        return False
    if r.get("missing_required_document") is True:
        return True
    return derive_missing_document_status(r) == MISSING_DOC_REQUIRED


def derive_requirement_resolution_status(row: Dict[str, Any]) -> str:
    r = dict(row or {})
    lifecycle = _status_upper(r.get("client_lifecycle_state"))
    if lifecycle == NOT_APPLICABLE:
        return RESOLUTION_NOT_APPLICABLE

    truth_stage = str(r.get("truth_presentation_stage") or "").lower()
    if truth_stage in ("platform_verification_pending", "org_verification_pending") or lifecycle == PENDING_REVIEW:
        return RESOLUTION_AWAITING_REVIEW
    if truth_stage in ("followup_required", "operational_incomplete"):
        eligible, reason, _ = is_requirement_attention_eligible(r)
        if eligible and reason in ("followup_required", "follow_up_required", "operational_incomplete"):
            return RESOLUTION_FOLLOW_UP_REQUIRED

    if is_requirement_satisfied(r):
        return RESOLUTION_RESOLVED
    eligible, _, _ = is_requirement_attention_eligible(r)
    if eligible or lifecycle == ACTION_REQUIRED:
        return RESOLUTION_UNRESOLVED
    if lifecycle in (VERIFIED, SATISFIED_UNVERIFIED):
        return RESOLUTION_RESOLVED
    return RESOLUTION_UNRESOLVED


def distinguish_document_gap_from_requirement_gap(row: Dict[str, Any]) -> Dict[str, bool]:
    doc_status = derive_missing_document_status(row)
    resolution = derive_requirement_resolution_status(row)
    return {
        "document_gap": doc_status == MISSING_DOC_REQUIRED,
        "requirement_gap": resolution == RESOLUTION_UNRESOLVED,
        "document_not_required": doc_status == MISSING_DOC_NOT_APPLICABLE,
    }


def reconcile_client_lifecycle_with_satisfaction(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reconcile lifecycle state after governance/truth presentation attach.

    Lifecycle is first derived before truth fields exist; this pass aligns
    client_lifecycle_state with authoritative satisfaction truth.
    """
    r = dict(row or {})
    out: Dict[str, Any] = {}
    lifecycle = _status_upper(r.get("client_lifecycle_state"))
    if lifecycle == NOT_APPLICABLE:
        return out

    eligible, attention_reason, _ = is_requirement_attention_eligible(r)
    truth_stage = str(r.get("truth_presentation_stage") or "").lower()
    ea_st = _status_upper(authority_state(r))

    if eligible:
        if attention_reason in ("platform_verification_pending", "org_verification_pending", "review_pending"):
            if lifecycle != PENDING_REVIEW:
                out["client_lifecycle_state"] = PENDING_REVIEW
                out.setdefault("client_lifecycle_reason_codes", list(r.get("client_lifecycle_reason_codes") or []))
                if "SATISFACTION_RECONCILE_PENDING_REVIEW" not in out["client_lifecycle_reason_codes"]:
                    out["client_lifecycle_reason_codes"].append("SATISFACTION_RECONCILE_PENDING_REVIEW")
        elif lifecycle not in (ACTION_REQUIRED, PENDING_REVIEW):
            out["client_lifecycle_state"] = ACTION_REQUIRED
            out.setdefault("client_lifecycle_reason_codes", list(r.get("client_lifecycle_reason_codes") or []))
            if "SATISFACTION_RECONCILE_ACTION_REQUIRED" not in out["client_lifecycle_reason_codes"]:
                out["client_lifecycle_reason_codes"].append("SATISFACTION_RECONCILE_ACTION_REQUIRED")
        return out

    if truth_stage == "verified" or ea_st == EA_VERIFIED_CURRENT:
        if lifecycle != VERIFIED:
            out["client_lifecycle_state"] = VERIFIED
            out.setdefault("client_lifecycle_reason_codes", list(r.get("client_lifecycle_reason_codes") or []))
            out["client_lifecycle_reason_codes"].append("SATISFACTION_RECONCILE_VERIFIED")
        return out

    if is_requirement_satisfied(r):
        if lifecycle == ACTION_REQUIRED:
            out["client_lifecycle_state"] = SATISFIED_UNVERIFIED
            out.setdefault("client_lifecycle_reason_codes", list(r.get("client_lifecycle_reason_codes") or []))
            out["client_lifecycle_reason_codes"].append("SATISFACTION_RECONCILE_SATISFIED")
        return out

    return out


def portal_renewal_countdown_eligible(row: Dict[str, Any]) -> bool:
    """
    Requirements portal may show days-overdue / days-left only when renewal/expiry
    attention is authoritative — not from stale estimated calendar drift alone.
    """
    eligible, attention_reason, _ = is_requirement_attention_eligible(row)
    if not eligible:
        return False
    return attention_reason in ("expired", "renewal_due")


def attach_satisfaction_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """Attach convergence fields for all client surfaces."""
    r = dict(row or {})
    gaps = distinguish_document_gap_from_requirement_gap(r)
    eligible, attention_reason, suppression = is_requirement_attention_eligible(r)
    doc_required = document_upload_required(r)
    doc_status = derive_missing_document_status(r)
    return {
        "document_upload_required": doc_required,
        "missing_required_document": gaps["document_gap"],
        "requirement_satisfied": is_requirement_satisfied(r),
        "satisfaction_source": derive_satisfaction_source(r),
        "missing_document_status": doc_status,
        "requirement_resolution_status": derive_requirement_resolution_status(r),
        "requirement_attention_eligible": eligible,
        "requirement_attention_reason": attention_reason,
        "requirement_attention_suppression": suppression,
        "portal_renewal_countdown_eligible": portal_renewal_countdown_eligible(r),
        "document_gap": gaps["document_gap"],
        "requirement_gap": gaps["requirement_gap"],
    }


def summarize_client_compliance_diagnostics(
    enriched_requirements: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Admin control panel diagnostics from enriched requirement truth."""
    missing_required_documents = 0
    requirements_unresolved = 0
    satisfied_by_declaration = 0
    awaiting_org_platform_review = 0
    follow_up_required = 0
    satisfied_without_uploaded_document = 0
    visible = 0

    declaration_sources = {
        SOURCE_ACCEPTED_DECLARATION,
        SOURCE_SELF_CERTIFIED,
        SOURCE_ORG_REVIEW,
    }

    for row in enriched_requirements or []:
        if row.get("client_surface_visible") is False:
            continue
        app = _status_upper(row.get("applicability"))
        if app == "NOT_REQUIRED":
            continue
        visible += 1

        if row.get("missing_required_document"):
            missing_required_documents += 1
        resolution = str(row.get("requirement_resolution_status") or derive_requirement_resolution_status(row))
        if resolution == RESOLUTION_UNRESOLVED:
            requirements_unresolved += 1
        elif resolution == RESOLUTION_AWAITING_REVIEW:
            awaiting_org_platform_review += 1
        elif resolution == RESOLUTION_FOLLOW_UP_REQUIRED:
            follow_up_required += 1

        src = str(row.get("satisfaction_source") or derive_satisfaction_source(row))
        if row.get("requirement_satisfied") and src in declaration_sources:
            satisfied_by_declaration += 1

        if row.get("requirement_satisfied") and not document_upload_required(row):
            satisfied_without_uploaded_document += 1
        elif (
            row.get("requirement_satisfied")
            and not bool(str(row.get("document_id") or row.get("evidence_doc_id") or "").strip())
            and not row.get("missing_required_document")
        ):
            satisfied_without_uploaded_document += 1

    return {
        "missing_required_documents": missing_required_documents,
        "requirements_unresolved": requirements_unresolved,
        "satisfied_by_declaration": satisfied_by_declaration,
        "awaiting_org_platform_review": awaiting_org_platform_review,
        "follow_up_required": follow_up_required,
        "satisfied_without_uploaded_document": satisfied_without_uploaded_document,
        "visible_requirements_count": visible,
        # Legacy alias — count only document-required gaps, not all PENDING rows.
        "missing_documents": missing_required_documents,
    }
