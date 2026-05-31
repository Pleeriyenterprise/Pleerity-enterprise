"""
CER governance presentation — Phase 1 truth-surface fields (read-only enrichment).

Source: PRELAUNCH-CER-AUTHORITY-GOVERNANCE-DECISION-01 / cer_governance_matrix.json
Does not mutate evidence authority or scoring.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.requirement_code_registry import normalize_requirement_code

GF_SELF = "SELF_CERTIFIED"
GF_ORG = "ORG_ADMIN_REVIEWED"
GF_PLATFORM_OPT = "PLATFORM_OVERSIGHT_OPTIONAL"
GF_PLATFORM_VER = "PLATFORM_VERIFIED"
GF_ESCALATION = "ESCALATION_REVIEW_ONLY"

DOCUMENT_PRIMARY_CODES = frozenset(
    {
        "gas_safety",
        "eicr",
        "epc",
        "fire_alarm",
        "portable_appliance_test",
        "pat",
        "electrical_installation_condition_report",
        "energy_performance_certificate",
        "hmo_licence",
        "selective_licence",
        "asbestos",
        "oil_tank",
        "emergency_lighting",
        "fire_door",
        "lift_inspection",
    }
)

_GOVERNANCE_META: Dict[str, Dict[str, Any]] = {
    "smoke_heat_alarms": {
        "governance_family": GF_SELF,
        "review_authority": "automated_governance_guards",
        "review_visibility": "none",
        "operational_completion_mode": "governance_guard_auto_close",
    },
    "how_to_rent": {
        "governance_family": GF_SELF,
        "review_authority": "automated_governance_guards",
        "review_visibility": "none",
        "operational_completion_mode": "tenant_delivery_record_guard",
    },
    "right_to_rent": {
        "governance_family": GF_ORG,
        "review_authority": "org_admin",
        "review_visibility": "org_admin_queue",
        "operational_completion_mode": "declaration_recorded_plus_org_verify_optional",
    },
    "deposit_pi": {
        "governance_family": GF_ORG,
        "review_authority": "org_admin",
        "review_visibility": "org_admin_queue",
        "operational_completion_mode": "declaration_recorded_plus_org_verify_optional",
    },
    "wales_occupation_contract": {
        "governance_family": GF_ORG,
        "review_authority": "org_admin",
        "review_visibility": "org_admin_queue",
        "operational_completion_mode": "declaration_recorded_plus_org_verify_optional",
    },
    "tenancy_agreement": {
        "governance_family": GF_ORG,
        "review_authority": "org_admin",
        "review_visibility": "org_admin_queue",
        "operational_completion_mode": "declaration_recorded_plus_org_verify_optional",
    },
    "landlord_registration": {
        "governance_family": GF_ORG,
        "review_authority": "org_admin",
        "review_visibility": "org_admin_queue",
        "operational_completion_mode": "registration_tracking_record_guard",
    },
    "scotland_landlord_registration": {
        "governance_family": GF_ORG,
        "review_authority": "org_admin",
        "review_visibility": "org_admin_queue",
        "operational_completion_mode": "registration_tracking_record_guard",
    },
    "landlord_registration_ni": {
        "governance_family": GF_ORG,
        "review_authority": "org_admin",
        "review_visibility": "org_admin_queue",
        "operational_completion_mode": "registration_tracking_record_guard",
    },
    "rent_smart_wales": {
        "governance_family": GF_ORG,
        "review_authority": "org_admin",
        "review_visibility": "org_admin_queue",
        "operational_completion_mode": "registration_tracking_record_guard",
    },
    "legionella": {
        "governance_family": GF_PLATFORM_OPT,
        "review_authority": "landlord_operational_followup",
        "review_visibility": "none_default",
        "operational_completion_mode": "external_assessment_followup_guard",
    },
    "lead_testing": {
        "governance_family": GF_PLATFORM_OPT,
        "review_authority": "landlord_operational_followup",
        "review_visibility": "none_default",
        "operational_completion_mode": "external_assessment_followup_guard",
    },
    "hmo_fire_risk": {
        "governance_family": GF_PLATFORM_OPT,
        "review_authority": "landlord_operational_followup",
        "review_visibility": "none_default",
        "operational_completion_mode": "multi_evidence_governance_guard",
    },
    "hmo_fire_risk_evidence": {
        "governance_family": GF_PLATFORM_OPT,
        "review_authority": "landlord_operational_followup",
        "review_visibility": "none_default",
        "operational_completion_mode": "multi_evidence_governance_guard",
    },
    "fire_risk_assessment": {
        "governance_family": GF_PLATFORM_OPT,
        "review_authority": "landlord_operational_followup",
        "review_visibility": "none_default",
        "operational_completion_mode": "multi_evidence_governance_guard",
    },
}

_PLATFORM_VER_META = {
    "governance_family": GF_PLATFORM_VER,
    "review_authority": "platform_admin",
    "review_visibility": "platform_admin_documents_queue",
    "operational_completion_mode": "admin_document_verify_plus_authority_sync",
}

FOLLOWUP_SEMANTICS = frozenset(
    {
        "ASSESSMENT_FOLLOWUP_REQUIRED",
        "EXTERNAL_ASSESSMENT_FOLLOWUP_REQUIRED",
    }
)
FOLLOWUP_STATE_REASONS = frozenset(
    {
        "external_assessment_remediation_or_followup_unresolved",
        "multi_evidence_components_incomplete",
    }
)


def resolve_governance_meta(requirement: Dict[str, Any]) -> Dict[str, Any]:
    raw = str(requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw) or raw
    if canon in _GOVERNANCE_META:
        return dict(_GOVERNANCE_META[canon])
    wf = str(requirement.get("workflow_class") or requirement.get("primary_resolution_workflow") or "").upper()
    if wf in ("DOCUMENT_UPLOAD", "LEGACY_DOCUMENT_UPLOAD") or canon in DOCUMENT_PRIMARY_CODES:
        return dict(_PLATFORM_VER_META)
    from services.compliance_evidence_record_service import effective_evidence_resolution

    pol = effective_evidence_resolution(requirement)
    pwf = str(pol.get("primary_resolution_workflow") or "").upper()
    if pwf in ("DOCUMENT_UPLOAD", "LEGACY_DOCUMENT_UPLOAD"):
        return dict(_PLATFORM_VER_META)
    if pwf == "TENANT_DELIVERY":
        return dict(_GOVERNANCE_META["how_to_rent"])
    if pwf == "GUIDED_DECLARATION":
        return dict(_GOVERNANCE_META.get("right_to_rent", _GOVERNANCE_META["deposit_pi"]))
    if pwf == "EXTERNAL_ASSESSMENT_EVIDENCE":
        return dict(_GOVERNANCE_META["legionella"])
    if pwf == "REGISTRATION_TRACKING":
        return dict(_GOVERNANCE_META["landlord_registration"])
    if pwf == "GUIDED_EVIDENCE_RESOLUTION":
        return dict(_GOVERNANCE_META["smoke_heat_alarms"])
    return {
        "governance_family": GF_SELF,
        "review_authority": "automated_governance_guards",
        "review_visibility": "none",
        "operational_completion_mode": "governance_guard_auto_close",
    }


def _has_persisted_submission(req: Dict[str, Any]) -> bool:
    ea = req.get("evidence_authority") if isinstance(req.get("evidence_authority"), dict) else {}
    if str(ea.get("primary_evidence_record_id") or "").strip():
        return True
    if str(req.get("evidence_record_id") or "").strip():
        return True
    if req.get("evidence_doc_id") or str(req.get("document_id") or "").strip():
        return True
    return False


def _is_escalation_active(req: Dict[str, Any], ea: Dict[str, Any]) -> bool:
    if ea.get("manual_review_flag") is True:
        return True
    if str(ea.get("state") or "").upper() in ("MISMATCH_FLAGGED", "EA_MISMATCH_FLAGGED"):
        return True
    if str(req.get("evidence_state") or "").upper() == "MISMATCH_FLAGGED":
        return True
    return False


def _components_incomplete(req: Dict[str, Any]) -> bool:
    comp = req.get("evidence_completeness") if isinstance(req.get("evidence_completeness"), dict) else {}
    if comp.get("is_complete") is False:
        return True
    if int(comp.get("required_missing_count") or 0) > 0:
        return True
    return False


def _followup_unresolved(req: Dict[str, Any], ea: Dict[str, Any]) -> bool:
    semantic = str(ea.get("semantic_state") or req.get("semantic_state") or "").upper()
    if semantic in FOLLOWUP_SEMANTICS:
        return True
    reason = str(ea.get("state_reason") or "").lower()
    return reason in FOLLOWUP_STATE_REASONS or "followup" in reason or "follow_up" in reason


def derive_truth_presentation(
    requirement: Dict[str, Any],
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    ea_state = str(ea.get("state") or "").upper()
    lifecycle = str(requirement.get("client_lifecycle_state") or "").upper()
    family = str(meta.get("governance_family") or "")
    has_sub = _has_persisted_submission(requirement)
    escalation = _is_escalation_active(requirement, ea)
    incomplete = _components_incomplete(requirement)
    followup = _followup_unresolved(requirement, ea)
    platform_pending = ea_state in ("PENDING_ADMIN_REVIEW", "EA_PENDING_ADMIN_REVIEW") or lifecycle == "PENDING_REVIEW"

    review_owner: Optional[str] = None
    stale_owner: Optional[str] = None
    stage = "collect_evidence"
    label = "Action required"
    subline: Optional[str] = None
    tier_supplement: Optional[str] = None

    if escalation:
        review_owner = "platform_admin_escalation"
        stale_owner = "platform_admin_escalation"
        stage = "escalation_review"
        label = "Escalated for platform review"
        subline = "This submission was flagged for Pleerity review."
    elif ea_state in ("VERIFIED_CURRENT", "EA_VERIFIED_CURRENT") or lifecycle == "VERIFIED":
        stage = "verified"
        label = "Verified"
        subline = "Requirement satisfied."
    elif platform_pending and family == GF_PLATFORM_VER:
        review_owner = "platform_admin"
        stale_owner = "platform_admin"
        stage = "platform_verification_pending"
        label = "Platform verification pending"
        subline = "Our team will verify your uploaded certificate."
    elif followup and family == GF_PLATFORM_OPT:
        stage = "followup_required"
        label = "Follow-up evidence required"
        subline = "Complete remaining assessment or remediation steps to close this obligation."
        stale_owner = "landlord"
        tier_supplement = "Remediation or follow-up may remain open"
    elif incomplete:
        stage = "operational_incomplete"
        label = "Additional action still required"
        subline = "Some required evidence components are still missing."
        stale_owner = "landlord"
    elif has_sub and family == GF_SELF:
        stage = "declaration_recorded"
        label = "Declaration recorded"
        subline = "Your submission is recorded. No platform review is required for this obligation."
    elif has_sub and family == GF_ORG:
        stage = "evidence_recorded"
        label = "Evidence recorded"
        subline = "Recorded for compliance tracking; not platform certificate verification."
        tier_supplement = "Organisation verification optional"
    elif has_sub and family == GF_PLATFORM_OPT:
        stage = "assessment_recorded"
        label = "Assessment recorded"
        subline = "Your assessment is on file. Complete any open follow-up actions."
    elif ea_state in ("UPLOADED_UNCONFIRMED", "UPLOADED") and not has_sub:
        stage = "supporting_upload_only"
        label = "Supporting evidence uploaded"
        subline = "Supporting files alone do not complete this obligation."
    elif lifecycle == "SATISFIED_UNVERIFIED":
        stage = "evidence_recorded"
        label = "Evidence recorded"
    elif lifecycle == "ACTION_REQUIRED" or ea_state in ("MISSING", ""):
        stage = "action_required"
        label = "Action required"

    if review_owner is None and stale_owner is None and family == GF_ORG and has_sub:
        stale_owner = None
    elif review_owner is None and has_sub and family in (GF_SELF, GF_PLATFORM_OPT) and not followup and not incomplete:
        stale_owner = None

    return {
        "truth_presentation_stage": stage,
        "truth_presentation_label": label,
        "truth_presentation_subline": subline,
        "truth_presentation_tier_supplement": tier_supplement,
        "review_owner": review_owner,
        "stale_owner": stale_owner,
        "queue_backed_review": review_owner in ("platform_admin", "platform_admin_escalation", "org_admin"),
    }


def attach_cer_governance_presentation(requirement: Dict[str, Any]) -> Dict[str, Any]:
    """Return governance + truth presentation fields for client enrichment."""
    meta = resolve_governance_meta(requirement)
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    semantic = ea.get("semantic_state") or requirement.get("semantic_state")
    truth = derive_truth_presentation(requirement, meta)
    return {
        "governance_family": meta.get("governance_family"),
        "review_authority": meta.get("review_authority"),
        "review_visibility": meta.get("review_visibility"),
        "operational_completion_mode": meta.get("operational_completion_mode"),
        "semantic_state": semantic,
        "review_owner": truth.get("review_owner"),
        "stale_owner": truth.get("stale_owner"),
        "queue_backed_review": truth.get("queue_backed_review"),
        **truth,
    }


def stale_allowed_for_requirement(requirement: Dict[str, Any]) -> bool:
    gov = requirement.get("stale_owner") or requirement.get("review_owner")
    if not gov:
        return False
    if gov == "landlord":
        return _followup_unresolved(
            requirement,
            requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {},
        ) or _components_incomplete(requirement)
    return gov in ("platform_admin", "platform_admin_escalation", "org_admin")


def cognition_next_step_for_requirement(requirement: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    """Owner-qualified recommended next step for operational cognition."""
    label = str(requirement.get("truth_presentation_label") or "Review requirement status")
    subline = str(requirement.get("truth_presentation_subline") or "")
    stage = str(requirement.get("truth_presentation_stage") or "")
    owner = requirement.get("review_owner") or requirement.get("stale_owner")
    remaining: List[str] = []

    if stage == "verified":
        return "No further evidence required", "Evidence is verified for this obligation.", []
    if stage == "platform_verification_pending":
        return (
            "Platform verification in progress",
            "Pleerity will verify your uploaded certificate.",
            ["Wait for platform verification"],
        )
    if stage == "escalation_review":
        return (
            "Escalated for platform review",
            subline or "Pleerity will review this flagged submission.",
            ["Wait for Pleerity review team"],
        )
    if stage == "followup_required":
        return (
            "Complete follow-up evidence",
            subline or "Finish open assessment or remediation steps.",
            ["Complete follow-up actions", "Update your submission if needed"],
        )
    if stage == "operational_incomplete":
        return (
            "Complete remaining compliance steps",
            subline or "Required evidence components are still missing.",
            ["Complete missing checklist or component evidence", "Submit when complete"],
        )
    if stage == "declaration_recorded":
        return (
            "Declaration on file",
            subline or "No further action unless renewal or updates are required.",
            [],
        )
    if stage == "assessment_recorded":
        return (
            "Assessment on file — check follow-up items",
            subline or "Review any open follow-up actions.",
            ["Complete follow-up if shown"],
        )
    if stage == "evidence_recorded" and owner == "org_admin":
        return (
            "Evidence recorded",
            subline or "Organisation admin may verify when required.",
            ["Optional: organisation admin verification"],
        )
    if stage == "supporting_upload_only":
        return (
            "Complete structured submission",
            "Supporting files alone do not satisfy this obligation.",
            ["Complete structured record", "Submit evidence"],
        )
    if stage == "action_required":
        return label, subline or "Provide evidence for this obligation.", ["Choose evidence method", "Submit evidence"]
    return label, subline, remaining
