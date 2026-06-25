"""
Customer status projector v2 — authoritative customer obligation status at enrich time.

S2: Maps enrich signals to CUSTOMER_STATUS_VOCABULARY.json terms only.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from services import customer_status_vocabulary as vocab
from services.cer_governance_presentation import (
    DOCUMENT_PRIMARY_CODES,
    GF_PLATFORM_OPT,
    GF_PLATFORM_VER,
    GF_SELF,
    _components_incomplete,
    _followup_unresolved,
    _has_persisted_submission,
    _is_escalation_active,
    resolve_governance_meta,
)
from services.customer_status_projector_config import (
    ProjectorMode,
    get_customer_status_projector_mode,
    is_customer_status_projector_active,
)
from services.customer_status_projector_shadow import (
    compare_legacy_vs_projector,
    log_projector_divergence,
)
from services.requirement_code_registry import normalize_requirement_code

logger = logging.getLogger(__name__)

PROJECTOR_VERSION = "2.0.0"

_EA_VERIFIED = frozenset({"VERIFIED_CURRENT", "EA_VERIFIED_CURRENT"})
_EA_REJECTED = frozenset({"REJECTED", "EA_REJECTED"})
_EA_UPLOADED = frozenset({"UPLOADED_UNCONFIRMED", "EA_UPLOADED_UNCONFIRMED", "UPLOADED"})
_EA_RECORDED = frozenset(
    {
        "RECORDED_CURRENT",
        "EA_RECORDED_CURRENT",
        "SATISFIED_UNVERIFIED",
        "EA_SATISFIED_UNVERIFIED",
    }
)
_EA_PENDING_ADMIN = frozenset({"PENDING_ADMIN_REVIEW", "EA_PENDING_ADMIN_REVIEW"})

_SUBLINE_BY_KEY: Dict[str, str] = {
    vocab.RECORDED: (
        "Self-recorded declaration — auditable and timestamped; no independent reviewer required."
    ),
    vocab.SATISFIED: "Obligation met based on recorded evidence.",
    vocab.UNDER_REVIEW: "Our team is verifying your uploaded certificate",
    vocab.VERIFIED: "Requirement satisfied.",
    vocab.REJECTED: "Please upload a valid certificate or contact support.",
    vocab.FOLLOWUP_REQUIRED: (
        "Complete remaining assessment or remediation steps to close this obligation."
    ),
    vocab.ADDITIONAL_ACTION_REQUIRED: "Some required evidence components are still missing.",
    vocab.EXPIRY_DATE_NEEDED: (
        "Add expiry date information so this certificate can count as fully valid."
    ),
    vocab.ESCALATION_REQUIRED: "This submission was flagged for Pleerity investigation.",
    vocab.ESCALATION_RESOLVED: "The flagged issue has been resolved.",
    vocab.UPLOADED: "Certificate file received; verification will begin once queued.",
    vocab.ACTION_REQUIRED: "",
}

_SUPPORTING_UPLOAD_SUBLINE = "Supporting files alone do not complete this obligation."

_STATUS_KEY_TO_STAGE: Dict[str, str] = {
    vocab.RECORDED: "declaration_recorded",
    vocab.UNDER_REVIEW: "platform_verification_pending",
    vocab.VERIFIED: "verified",
    vocab.REJECTED: "rejected",
    vocab.FOLLOWUP_REQUIRED: "followup_required",
    vocab.ADDITIONAL_ACTION_REQUIRED: "operational_incomplete",
    vocab.EXPIRY_DATE_NEEDED: "expiry_confirmation_required",
    vocab.ESCALATION_REQUIRED: "escalation_review",
    vocab.ESCALATION_RESOLVED: "escalation_review",
    vocab.UPLOADED: "collect_evidence",
    vocab.SATISFIED: "declaration_recorded",
    vocab.ACTION_REQUIRED: "action_required",
    vocab.SUBMITTED: "collect_evidence",
}


def _canon(requirement: Dict[str, Any]) -> str:
    raw = str(requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip()
    return normalize_requirement_code(raw) or raw.lower().replace(" ", "_")


def resolve_obligation_class(requirement: Dict[str, Any]) -> str:
    """Return A (self-cert) or B (document verification)."""
    meta = resolve_governance_meta(requirement)
    family = str(meta.get("governance_family") or "")
    if family == GF_PLATFORM_VER:
        return "B"
    canon = _canon(requirement)
    if canon in DOCUMENT_PRIMARY_CODES:
        return "B"
    wf = str(requirement.get("workflow_class") or requirement.get("primary_resolution_workflow") or "").upper()
    if wf in ("DOCUMENT_UPLOAD", "LEGACY_DOCUMENT_UPLOAD"):
        return "B"
    return "A"


def _ea(requirement: Dict[str, Any]) -> Dict[str, Any]:
    ea = requirement.get("evidence_authority")
    return ea if isinstance(ea, dict) else {}


def _ea_state(requirement: Dict[str, Any]) -> str:
    return str(_ea(requirement).get("state") or "").upper()


def _lifecycle(requirement: Dict[str, Any]) -> str:
    return str(requirement.get("client_lifecycle_state") or "").upper()


def _satisfaction_state(requirement: Dict[str, Any]) -> str:
    return str(requirement.get("satisfaction_state") or "").upper()


def _is_supporting_upload_only(
    requirement: Dict[str, Any],
    ea_state: str,
    has_sub: bool,
    obligation_class: str,
) -> bool:
    if obligation_class == "B":
        return False
    if has_sub:
        return False
    if ea_state in _EA_UPLOADED:
        return True
    stage = str(requirement.get("truth_presentation_stage") or "").strip()
    return stage == "supporting_upload_only"


def _emit_under_review(requirement: Dict[str, Any], obligation_class: str) -> bool:
    if obligation_class != "B":
        return False
    if requirement.get("queue_backed_review") is not True:
        return False
    owner = str(requirement.get("review_owner") or "").strip()
    if owner == "platform_admin_escalation":
        return False
    if owner and owner != "platform_admin":
        return False
    linked = requirement.get("linked_primary_document")
    doc_status = ""
    if isinstance(linked, dict):
        doc_status = str(linked.get("status") or "").upper()
    if doc_status == "UPLOADED":
        return True
    if _ea_state(requirement) in _EA_PENDING_ADMIN:
        return True
    return False


def _emit_expiry_needed(requirement: Dict[str, Any], ea: Dict[str, Any]) -> bool:
    from services.lifecycle_scoring_gates import emit_expiry_needed_overlay

    return emit_expiry_needed_overlay(requirement, ea)


def _emit_escalation_resolved(requirement: Dict[str, Any], ea: Dict[str, Any]) -> bool:
    if _is_escalation_active(requirement, ea):
        return False
    semantic = str(ea.get("semantic_state") or requirement.get("semantic_state") or "").upper()
    if semantic in ("ESCALATION_RESOLVED", "ISSUE_RESOLVED"):
        return True
    reason = str(ea.get("state_reason") or "").lower()
    return "escalation_resolved" in reason or "escalation_cleared" in reason


def _pick_overlay(
    requirement: Dict[str, Any],
    *,
    obligation_class: str,
    ea: Dict[str, Any],
    has_sub: bool,
) -> Tuple[Optional[str], List[str]]:
    """Return (overlay_key, reason_codes) per overlay_precedence."""
    reasons: List[str] = []

    if _is_escalation_active(requirement, ea):
        reasons.append("ESCALATION_ACTIVE")
        return vocab.ESCALATION_REQUIRED, reasons

    if obligation_class == "B" and _ea_state(requirement) in _EA_REJECTED:
        reasons.append("ADMIN_REJECT")
        return vocab.REJECTED, reasons

    if _emit_under_review(requirement, obligation_class):
        reasons.append("QUEUE_PROVEN")
        return vocab.UNDER_REVIEW, reasons

    if _emit_expiry_needed(requirement, ea):
        reasons.append("EXPIRY_CONFIRMATION_REQUIRED")
        return vocab.EXPIRY_DATE_NEEDED, reasons

    if _followup_unresolved(requirement, ea):
        family = str(requirement.get("governance_family") or "")
        if family == GF_PLATFORM_OPT or obligation_class == "A":
            reasons.append("FOLLOWUP_UNRESOLVED")
            return vocab.FOLLOWUP_REQUIRED, reasons

    if _components_incomplete(requirement) and obligation_class == "A":
        reasons.append("COMPONENTS_INCOMPLETE")
        return vocab.ADDITIONAL_ACTION_REQUIRED, reasons

    if _emit_escalation_resolved(requirement, ea):
        reasons.append("ESCALATION_CLEARED")
        return vocab.ESCALATION_RESOLVED, reasons

    return None, reasons


def _base_path_key(
    requirement: Dict[str, Any],
    *,
    obligation_class: str,
    ea: Dict[str, Any],
    has_sub: bool,
    ea_state: str,
    lifecycle: str,
) -> Tuple[str, List[str]]:
    reasons: List[str] = []

    if _is_supporting_upload_only(requirement, ea_state, has_sub, obligation_class):
        reasons.append("SUPPORTING_UPLOAD_ONLY")
        return vocab.ACTION_REQUIRED, reasons

    if obligation_class == "B":
        if ea_state in _EA_VERIFIED or lifecycle == "VERIFIED":
            reasons.append("EA_VERIFIED")
            return vocab.VERIFIED, reasons
        if _emit_under_review(requirement, obligation_class):
            reasons.append("QUEUE_PROVEN")
            return vocab.UNDER_REVIEW, reasons
        if ea_state in _EA_UPLOADED or ea_state in _EA_PENDING_ADMIN:
            reasons.append("DOCUMENT_UPLOADED")
            return vocab.UPLOADED, reasons
        reasons.append("NO_ACCEPTABLE_CERTIFICATE")
        return vocab.ACTION_REQUIRED, reasons

    # Class A
    sat = _satisfaction_state(requirement)
    if sat == "SATISFIED" or lifecycle == "SATISFIED":
        reasons.append("GOVERNANCE_GUARDS_PASS")
        return vocab.SATISFIED, reasons
    if has_sub or ea_state in _EA_RECORDED or lifecycle in ("SATISFIED_UNVERIFIED", "PENDING_REVIEW"):
        reasons.append("HAS_PERSISTED_SUBMISSION")
        return vocab.RECORDED, reasons
    reasons.append("NO_EVIDENCE")
    return vocab.ACTION_REQUIRED, reasons


def _assert_no_retired_phrases(label: str, subline: str) -> None:
    combined = f"{label} {subline}".lower()
    for phrase in vocab.RETIRED_REVIEW_PHRASES:
        if phrase.lower() in combined:
            raise ValueError(f"retired phrase in projector output: {phrase!r}")


def _assert_class_invariants(key: str, obligation_class: str) -> None:
    if obligation_class == "A" and key in vocab.CLASS_A_FORBIDDEN_PRIMARY_BADGES:
        raise ValueError(f"class A forbidden badge: {key}")
    if obligation_class == "B" and key in vocab.CLASS_B_FORBIDDEN_PRIMARY_BADGES:
        raise ValueError(f"class B forbidden badge: {key}")


def project_customer_status(
    requirement: Dict[str, Any],
    *,
    linked_primary_document: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return customer_status_* fields (does not mutate requirement)."""
    row = dict(requirement)
    if linked_primary_document is not None:
        row["linked_primary_document"] = linked_primary_document

    ea = _ea(row)
    ea_state = _ea_state(row)
    has_sub = _has_persisted_submission(row)
    lifecycle = _lifecycle(row)
    obligation_class = resolve_obligation_class(row)

    overlay_key, overlay_reasons = _pick_overlay(
        row, obligation_class=obligation_class, ea=ea, has_sub=has_sub
    )
    base_key, base_reasons = _base_path_key(
        row,
        obligation_class=obligation_class,
        ea=ea,
        has_sub=has_sub,
        ea_state=ea_state,
        lifecycle=lifecycle,
    )

    if overlay_key:
        status_key = overlay_key
        reasons = overlay_reasons + base_reasons
        overlay = overlay_key
    else:
        status_key = base_key
        reasons = base_reasons
        overlay = None

    # Follow-up open supersedes satisfied display (coverage audit AMB-05).
    if overlay_key == vocab.FOLLOWUP_REQUIRED and base_key == vocab.SATISFIED:
        status_key = vocab.FOLLOWUP_REQUIRED
        overlay = vocab.FOLLOWUP_REQUIRED

    label = vocab.CUSTOMER_STATUS_LABEL_BY_KEY.get(status_key, "Action required")
    subline = _SUBLINE_BY_KEY.get(status_key, "")
    if status_key == vocab.ACTION_REQUIRED and "SUPPORTING_UPLOAD_ONLY" in reasons:
        subline = _SUPPORTING_UPLOAD_SUBLINE

    try:
        _assert_no_retired_phrases(label, subline)
        _assert_class_invariants(status_key, obligation_class)
    except ValueError as exc:
        logger.warning("customer_status_projector_invariant_violation: %s", exc)
        status_key = vocab.ACTION_REQUIRED
        label = vocab.CUSTOMER_STATUS_LABEL_BY_KEY[vocab.ACTION_REQUIRED]
        subline = ""
        overlay = None
        reasons = ["PROJECTOR_FALLBACK"]

    return {
        "customer_status_key": status_key,
        "customer_status_label": label,
        "customer_status_subline": subline,
        "customer_status_class": obligation_class,
        "customer_status_reason": reasons,
        "customer_status_overlay": overlay,
        "vocabulary_version": vocab.VOCABULARY_VERSION,
        "customer_status_projector_version": PROJECTOR_VERSION,
    }


def mirror_legacy_truth_fields_from_projector(
    requirement: Dict[str, Any],
    projection: Dict[str, Any],
) -> None:
    """When flag=active, mirror legacy truth_* from projector for API compat."""
    key = str(projection.get("customer_status_key") or "")
    label = str(projection.get("customer_status_label") or "")
    subline = str(projection.get("customer_status_subline") or "")
    stage = _STATUS_KEY_TO_STAGE.get(key, "collect_evidence")
    requirement["customer_status_key"] = key
    requirement["customer_status_label"] = label
    requirement["customer_status_subline"] = subline
    requirement["customer_status_class"] = projection.get("customer_status_class")
    requirement["customer_status_reason"] = projection.get("customer_status_reason")
    requirement["customer_status_overlay"] = projection.get("customer_status_overlay")
    requirement["vocabulary_version"] = projection.get("vocabulary_version")
    requirement["customer_status_projector_version"] = projection.get("customer_status_projector_version")
    requirement["truth_presentation_label"] = label
    requirement["truth_presentation_subline"] = subline
    requirement["truth_presentation_stage"] = stage
    requirement["client_lifecycle_label"] = label


def apply_customer_status_projection(
    requirement: Dict[str, Any],
    *,
    linked_primary_document: Optional[Dict[str, Any]] = None,
    mode: Optional[ProjectorMode] = None,
) -> None:
    """Mutate requirement per flag mode; log shadow divergence when shadow|active."""
    mode = mode or get_customer_status_projector_mode()
    if mode == "disabled":
        return

    legacy_snapshot = {
        "truth_presentation_label": requirement.get("truth_presentation_label"),
        "truth_presentation_subline": requirement.get("truth_presentation_subline"),
        "truth_presentation_stage": requirement.get("truth_presentation_stage"),
        "client_lifecycle_label": requirement.get("client_lifecycle_label"),
    }

    projection = project_customer_status(
        requirement, linked_primary_document=linked_primary_document
    )

    if mode == "shadow":
        requirement.update(projection)
        comparison = compare_legacy_vs_projector(requirement, legacy_snapshot, projection)
        if comparison:
            requirement["_customer_status_shadow"] = comparison
            log_projector_divergence(requirement, legacy_snapshot, projection, comparison)
        return

    if mode == "active":
        mirror_legacy_truth_fields_from_projector(requirement, projection)
        comparison = compare_legacy_vs_projector(requirement, legacy_snapshot, projection)
        if comparison:
            requirement["_customer_status_shadow"] = comparison
            log_projector_divergence(requirement, legacy_snapshot, projection, comparison)


def customer_status_fields_present(requirement: Dict[str, Any]) -> bool:
    return bool(str(requirement.get("customer_status_key") or "").strip())


def cognition_copy_from_customer_status(requirement: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """Recommended next step + reason from projector output when active."""
    if not is_customer_status_projector_active():
        return None
    if not customer_status_fields_present(requirement):
        return None
    label = str(requirement.get("customer_status_label") or "").strip()
    subline = str(requirement.get("customer_status_subline") or "").strip()
    key = str(requirement.get("customer_status_key") or "")
    if key == vocab.VERIFIED:
        return "No further evidence required", "Evidence is verified for this obligation."
    if key == vocab.RECORDED and requirement.get("customer_status_class") == "A":
        step = label or "Recorded on file"
        reason = subline or (
            "Self-recorded evidence on file — not independently verified by Pleerity."
        )
        return step, reason
    if label:
        return label, subline
    return None
