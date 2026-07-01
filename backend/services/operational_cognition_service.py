"""
Operational Cognition Envelope v1 — read-only server-side orchestration.

Composes authoritative workflow/state signals into a single envelope for UI elevation.
MUST NOT mutate workflow, evidence, compliance, or financial authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

COGNITION_VERSION = "operational_cognition_v1"

# Hard boundary: cognition/AI may never perform these mutations.
FORBIDDEN_MUTATIONS = frozenset(
    {
        "mark_compliant",
        "verify_evidence",
        "clear_obligation",
        "clear_arrears",
        "resolve_workflow",
        "complete_work_order",
        "suppress_degraded_state",
        "suppress_operational_debt",
        "mint_workflow",
        "override_evidence_review",
        "infer_legal_compliance",
    }
)

TRUTH_DISTINCTIONS = {
    "uploaded_not_verified": "Uploaded evidence is not verified compliance.",
    "submitted_not_compliant": "Submitted information is not compliant until review confirms it.",
    "assigned_not_fixed": "Assignment to a contractor does not mean the issue is fixed.",
    "completed_not_compliant": "Job completion is not the same as compliance verification.",
    "acknowledged_not_resolved": "Acknowledgement does not mean the operational issue is resolved.",
}

EA_VERIFIED_STATES = frozenset({"VERIFIED_CURRENT", "EA_VERIFIED_CURRENT"})
EXPIRY_SEMANTICS_STATE_REASON = "document_upload_missing_required_expiry_semantics"


def _ea_blob(req: Dict[str, Any]) -> Dict[str, Any]:
    ea = req.get("evidence_authority")
    return ea if isinstance(ea, dict) else {}


def _ea_state_upper(req: Dict[str, Any]) -> str:
    return str(_ea_blob(req).get("state") or "").upper()


def _requirement_authority_verified(req: Dict[str, Any]) -> bool:
    if _ea_state_upper(req) in EA_VERIFIED_STATES:
        return True
    if str(req.get("truth_presentation_stage") or "").strip().lower() == "verified":
        return True
    if str(req.get("client_lifecycle_state") or "").upper() == "VERIFIED":
        return True
    return False


def _expiry_semantics_pending_only(req: Dict[str, Any]) -> bool:
    ea = _ea_blob(req)
    if str(ea.get("state_reason") or "") != EXPIRY_SEMANTICS_STATE_REASON:
        return False
    if req.get("queue_backed_review") is True:
        return False
    if str(req.get("review_owner") or "") in ("platform_admin", "platform_admin_escalation"):
        return False
    return _ea_state_upper(req) in ("UPLOADED_UNCONFIRMED", "EA_UPLOADED_UNCONFIRMED", "UPLOADED")


def _has_upload_or_linked_document(req: Dict[str, Any]) -> bool:
    """True when an uploaded or linked document is part of the evidence picture."""
    ea = _ea_blob(req)
    if str(ea.get("effective_verified_document_id") or req.get("document_id") or req.get("evidence_doc_id") or "").strip():
        return True
    reason = str(ea.get("state_reason") or "").lower()
    if any(tok in reason for tok in ("document_upload", "document_linked", "linked_document")):
        return True
    ea_state = str(ea.get("state") or "").upper()
    if ea_state in ("UPLOADED", "EA_UPLOADED_UNCONFIRMED", "PENDING_ADMIN_REVIEW", "EA_PENDING_ADMIN_REVIEW"):
        if any(tok in reason for tok in ("guided_declaration", "non_document", "declaration_not")):
            return False
        return True
    return False


def _upload_verification_attention_required(req: Dict[str, Any]) -> bool:
    """Upload-oriented verification warning — not for structured-only declarations."""
    if _requirement_authority_verified(req):
        return False
    if not _has_upload_or_linked_document(req):
        return False
    lifecycle = (req.get("client_lifecycle_state") or "").upper()
    ea = _ea_blob(req)
    ea_state = (ea.get("state") or "").upper()
    if lifecycle == "PENDING_REVIEW" and _has_upload_or_linked_document(req):
        return True
    if ea_state in ("EA_UPLOADED_UNCONFIRMED", "UPLOADED"):
        reason = str(ea.get("state_reason") or "").lower()
        if any(tok in reason for tok in ("guided_declaration", "non_document", "declaration_not")):
            return False
        return True
    return False


def _intel_submission_view_url(req: Dict[str, Any]) -> Optional[str]:
    pid = str(req.get("property_id") or "").strip()
    rid = str(req.get("requirement_id") or "").strip()
    if not pid or not rid:
        return None
    return f"/properties/{pid}?tab=evidence&requirement_id={rid}&open=intel&focus=submission"


def _verified_view_primary_action(req: Dict[str, Any]) -> Dict[str, Any]:
    from services.requirement_action_resolver import (
        INTENT_VIEW_SETTLED_EVIDENCE,
        INTENT_VIEW_SUBMISSION,
    )

    ea = _ea_blob(req)
    doc_id = ea.get("effective_verified_document_id") or req.get("document_id") or req.get("evidence_doc_id")
    pid = str(req.get("property_id") or "").strip()
    rid = str(req.get("requirement_id") or "").strip()
    cer_id = str(ea.get("primary_evidence_record_id") or req.get("primary_evidence_record_id") or "").strip()
    url = None
    intent = INTENT_VIEW_SETTLED_EVIDENCE
    if doc_id and pid and rid:
        url = f"/properties/{pid}?tab=evidence&requirement_id={rid}"
        intent = INTENT_VIEW_SETTLED_EVIDENCE
    elif pid and rid and (cer_id or not doc_id):
        url = _intel_submission_view_url(req)
        intent = INTENT_VIEW_SUBMISSION
    return {
        "key": "view_verified_evidence",
        "label": "View evidence",
        "url": url,
        "intent": intent,
        "hint": "Evidence is verified for this obligation.",
        "source": "operational_cognition_service.verified_authority",
    }


def _primary_from_next_actions(next_actions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not next_actions:
        return None
    a = next_actions[0]
    return {
        "key": a.get("id") or a.get("key") or "next_action",
        "label": a.get("label") or "Continue",
        "hint": a.get("hint") or "",
        "section": a.get("section") or "execution",
        "source": "compliance_workflow_service.next_job_actions",
    }


def _primary_from_continuation(cont: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not cont.get("has_active_lineage"):
        return None
    cta = cont.get("continuation_cta") or {}
    return {
        "key": cta.get("key") or "view_workflow",
        "label": cta.get("label") or "View workflow",
        "url": cta.get("url"),
        "hint": cont.get("user_safe_reason") or "",
        "continuation": True,
        "source": "operational_continuation_service",
    }


def _primary_from_take_action(take_action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(take_action, dict) or take_action.get("suppressed"):
        return None
    pri = take_action.get("primary")
    if not isinstance(pri, dict):
        return None
    return {
        "key": pri.get("intent") or pri.get("action_type") or "take_action",
        "label": pri.get("label") or "Take action",
        "url": pri.get("route") or pri.get("url"),
        "hint": pri.get("description") or "",
        "source": "requirement_action_resolver.take_action",
    }


def _blockers_from_requirement(req: Dict[str, Any]) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    comp = req.get("evidence_completeness") if isinstance(req.get("evidence_completeness"), dict) else {}
    missing = int(comp.get("required_missing_count") or 0)
    if missing > 0:
        blockers.append(
            {
                "code": "DECLARATION_INCOMPLETE",
                "message": f"{missing} required declaration field(s) still missing.",
                "truth_note": TRUTH_DISTINCTIONS["submitted_not_compliant"],
            }
        )
    ea = req.get("evidence_authority") if isinstance(req.get("evidence_authority"), dict) else {}
    ea_state = (ea.get("state") or "").upper()
    if ea_state in ("EA_REJECTED", "REJECTED"):
        blockers.append(
            {
                "code": "EVIDENCE_REJECTED",
                "message": "Evidence was rejected — resubmit or review.",
                "truth_note": TRUTH_DISTINCTIONS["uploaded_not_verified"],
            }
        )
    lifecycle = (req.get("client_lifecycle_state") or "").upper()
    if lifecycle == "PENDING_REVIEW":
        blockers.append(
            {
                "code": "AWAITING_REVIEW",
                "message": "Submission is awaiting review — not yet verified.",
                "truth_note": TRUTH_DISTINCTIONS["uploaded_not_verified"],
            }
        )
    return blockers


def _truth_flags_for_job(job_status: str, raw_status: str, contractor_id: Optional[str]) -> Dict[str, bool]:
    js = (job_status or "").upper()
    rs = (raw_status or "").upper()
    return {
        "assigned_not_fixed": bool(contractor_id) and js not in ("COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"),
        "completed_not_compliant": rs in ("COMPLETED",) and js != "VERIFIED",
        "acknowledged_not_resolved": False,
        "uploaded_not_verified": False,
        "submitted_not_compliant": False,
    }


def _truth_flags_for_requirement(req: Dict[str, Any]) -> Dict[str, bool]:
    if _requirement_authority_verified(req):
        return {
            "uploaded_not_verified": False,
            "submitted_not_compliant": False,
            "assigned_not_fixed": False,
            "completed_not_compliant": False,
            "acknowledged_not_resolved": False,
        }
    lifecycle = (req.get("client_lifecycle_state") or "").upper()
    ea = _ea_blob(req)
    ea_state = (ea.get("state") or "").upper()
    comp = req.get("evidence_completeness") if isinstance(req.get("evidence_completeness"), dict) else {}
    missing = int(comp.get("required_missing_count") or 0)
    expiry_only = _expiry_semantics_pending_only(req)
    return {
        "uploaded_not_verified": not expiry_only and _upload_verification_attention_required(req),
        "submitted_not_compliant": missing > 0 or (lifecycle == "ACTION_REQUIRED" and not expiry_only),
        "assigned_not_fixed": False,
        "completed_not_compliant": False,
        "acknowledged_not_resolved": False,
    }


def build_list_guidance(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Compact row overlay — same authority as detail envelope."""
    primary = envelope.get("primary_action") or {}
    cont = envelope.get("continuation_state") or {}
    esc = envelope.get("escalation_state") or {}
    deg = envelope.get("degraded_state") or {}
    return {
        "recommended_action_label": primary.get("label"),
        "recommended_action_url": primary.get("url"),
        "recommended_action_key": primary.get("key"),
        "continuation_summary": cont.get("summary") or cont.get("mode"),
        "escalation_badge": esc.get("label"),
        "escalation_level": esc.get("level"),
        "stale_warning": (envelope.get("stale_state") or {}).get("active"),
        "degraded_warning": deg.get("active"),
        "blocker_summary": (envelope.get("blockers") or [{}])[0].get("message") if envelope.get("blockers") else None,
        "cognition_version": COGNITION_VERSION,
    }


def build_envelope_for_job(
    serialized_job: Dict[str, Any],
    *,
    degraded: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    next_actions = serialized_job.get("next_actions") or []
    primary = _primary_from_next_actions(next_actions)
    job_status = serialized_job.get("job_status") or ""
    raw_status = serialized_job.get("status") or ""
    contractor_id = serialized_job.get("contractor_id")
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not contractor_id and job_status in ("OPEN", "ASSIGNED"):
        blockers.append(
            {
                "code": "NO_CONTRACTOR",
                "message": "No contractor assigned yet.",
                "truth_note": TRUTH_DISTINCTIONS["assigned_not_fixed"],
            }
        )
    if serialized_job.get("operational_exception"):
        warnings.append(
            {
                "code": "OPERATIONAL_EXCEPTION",
                "message": str(serialized_job.get("operational_exception")),
            }
        )
    if serialized_job.get("sla_breach_risk_at") or serialized_job.get("sla_breached_at"):
        esc_label = "SLA breach risk" if serialized_job.get("sla_breach_risk_at") else "SLA breached"
        escalation = {"active": True, "level": "high", "label": esc_label}
    else:
        escalation = {"active": False, "level": None, "label": None}

    truth = _truth_flags_for_job(job_status, raw_status, contractor_id)
    if truth["assigned_not_fixed"]:
        warnings.append({"code": "ASSIGNED_NOT_FIXED", "message": TRUTH_DISTINCTIONS["assigned_not_fixed"]})
    if truth["completed_not_compliant"]:
        warnings.append({"code": "COMPLETED_NOT_COMPLIANT", "message": TRUTH_DISTINCTIONS["completed_not_compliant"]})

    degraded_state = {"active": False}
    if degraded and degraded.get("degraded"):
        degraded_state = {
            "active": True,
            "reason": degraded.get("reason"),
            "disclosure": "Operational metrics may be incomplete while systems refresh.",
        }

    summary_parts = [primary.get("label") if primary else None, job_status or raw_status]
    user_safe_summary = " — ".join(p for p in summary_parts if p)

    return {
        "cognition_version": COGNITION_VERSION,
        "entity_type": "job",
        "read_only": True,
        "forbidden_mutations": sorted(FORBIDDEN_MUTATIONS),
        "primary_action": primary,
        "continuation_state": {"mode": "job_workflow", "summary": job_status},
        "workflow_state": {"canonical": job_status, "raw": raw_status},
        "progression_state": {"step": job_status, "next_actions_count": len(next_actions)},
        "blockers": blockers,
        "warnings": warnings,
        "review_state": {},
        "escalation_state": escalation,
        "degraded_state": degraded_state,
        "stale_state": {"active": bool(degraded and degraded.get("stale")), "scope": degraded.get("freshness_scope") if degraded else None},
        "operational_truth_flags": truth,
        "recommended_priority": "urgent" if escalation.get("active") else "normal",
        "user_safe_summary": user_safe_summary,
        "list_guidance": {},
    }


def build_envelope_for_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    from services.customer_operational_language_service import (
        derive_customer_safe_cta,
        derive_customer_safe_issue_summary,
        is_customer_safe_maintenance_escalation,
    )

    cont = issue.get("operational_continuation") if isinstance(issue.get("operational_continuation"), dict) else {}
    primary = _primary_from_continuation(cont)
    compliance_issue = not is_customer_safe_maintenance_escalation(issue)
    if not primary and (issue.get("status") or "").lower() not in ("closed", "cancelled", "resolved"):
        if compliance_issue:
            cta = derive_customer_safe_cta({**issue, "related_property_id": issue.get("property_id")})
            primary = {
                "key": "review_evidence",
                "label": cta.get("label") or "Review uploaded document",
                "url": cta.get("url"),
                "hint": "Confirm or replace the uploaded record for this requirement.",
                "source": "customer_operational_language",
            }
        else:
            primary = {
                "key": "create_work_order",
                "label": "Create maintenance job",
                "hint": "No active workflow linked to this issue yet.",
                "source": "maintenance_issues_service",
            }
    blockers: List[Dict[str, Any]] = []
    if (issue.get("status") or "").lower() in ("closed", "cancelled"):
        blockers.append({"code": "ISSUE_TERMINAL", "message": "Issue is closed — creation actions are not valid."})

    envelope = {
        "cognition_version": COGNITION_VERSION,
        "entity_type": "issue",
        "read_only": True,
        "forbidden_mutations": sorted(FORBIDDEN_MUTATIONS),
        "primary_action": primary,
        "continuation_state": {
            "mode": cont.get("mode") or "create",
            "summary": cont.get("continuation_state") or issue.get("status"),
            "has_active_lineage": cont.get("has_active_lineage"),
        },
        "workflow_state": {"issue_status": issue.get("status")},
        "progression_state": {"severity": issue.get("severity"), "priority_score": issue.get("priority_score")},
        "blockers": blockers,
        "warnings": [],
        "review_state": {},
        "escalation_state": {"active": (issue.get("severity") or "").lower() in ("high", "critical"), "level": issue.get("severity"), "label": issue.get("severity")},
        "degraded_state": {"active": False},
        "stale_state": {"active": False},
        "operational_truth_flags": {
            "acknowledged_not_resolved": (issue.get("status") or "").lower() == "acknowledged",
            "uploaded_not_verified": False,
            "submitted_not_compliant": False,
            "assigned_not_fixed": bool(cont.get("has_active_lineage")),
            "completed_not_compliant": False,
        },
        "recommended_priority": "high" if (issue.get("severity") or "").lower() in ("high", "critical") else "normal",
        "user_safe_summary": derive_customer_safe_issue_summary(issue),
    }
    envelope["list_guidance"] = build_list_guidance(envelope)
    return envelope


def build_envelope_for_risk_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    cont = signal.get("operational_continuation") if isinstance(signal.get("operational_continuation"), dict) else {}
    primary = _primary_from_continuation(cont)
    if not primary:
        actions = signal.get("suggested_actions") or []
        if "create_work_order" in actions:
            primary = {"key": "create_work_order", "label": "Start maintenance job", "source": "risk_signal_service"}
        elif "schedule_inspection" in actions:
            primary = {"key": "schedule_inspection", "label": "Start inspection job", "source": "risk_signal_service"}
        else:
            primary = {"key": "review", "label": "Review risk signal", "source": "risk_signal_service"}

    envelope = {
        "cognition_version": COGNITION_VERSION,
        "entity_type": "risk_signal",
        "read_only": True,
        "forbidden_mutations": sorted(FORBIDDEN_MUTATIONS),
        "primary_action": primary,
        "continuation_state": {
            "mode": cont.get("mode") or "create",
            "summary": cont.get("continuation_state"),
            "has_active_lineage": cont.get("has_active_lineage"),
        },
        "workflow_state": {"signal_status": signal.get("status"), "risk_type": signal.get("risk_type")},
        "progression_state": {"recommended_action": signal.get("recommended_action")},
        "blockers": [],
        "warnings": [],
        "review_state": {},
        "escalation_state": {"active": (signal.get("severity") or signal.get("priority") or "").lower() in ("high", "critical"), "level": signal.get("severity"), "label": signal.get("risk_type")},
        "degraded_state": {"active": False},
        "stale_state": {"active": False},
        "operational_truth_flags": {
            "assigned_not_fixed": bool(cont.get("has_active_lineage")),
            "uploaded_not_verified": False,
            "submitted_not_compliant": False,
            "completed_not_compliant": False,
            "acknowledged_not_resolved": False,
        },
        "recommended_priority": signal.get("priority") or "normal",
        "user_safe_summary": cont.get("user_safe_reason") or signal.get("recommended_action") or signal.get("risk_type"),
    }
    envelope["list_guidance"] = build_list_guidance(envelope)
    return envelope


GUIDANCE_VERSION = "requirement_guidance_v1"

_EVIDENCE_MODE_STRENGTH: Dict[str, int] = {
    "DOCUMENT_UPLOAD": 4,
    "CONTRACTOR_CONFIRMATION": 3,
    "INSPECTION_CHECKLIST": 2,
    "STRUCTURED_DECLARATION": 1,
}

_EVIDENCE_MODE_CONFIDENCE: Dict[str, str] = {
    "DOCUMENT_UPLOAD": "high",
    "CONTRACTOR_CONFIRMATION": "medium_high",
    "INSPECTION_CHECKLIST": "medium",
    "STRUCTURED_DECLARATION": "medium_low",
}

_MODE_LABELS: Dict[str, str] = {
    "DOCUMENT_UPLOAD": "Upload valid evidence document",
    "STRUCTURED_DECLARATION": "Complete compliance declaration",
    "CONTRACTOR_CONFIRMATION": "Submit contractor confirmation",
    "INSPECTION_CHECKLIST": "Complete inspection checklist",
}


def _parse_utc_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val.astimezone(timezone.utc)
    try:
        s = (val.replace("Z", "+00:00") if isinstance(val, str) else str(val)).strip()
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _requirement_policy(req: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from services.compliance_evidence_record_service import effective_evidence_resolution

        return effective_evidence_resolution(req)
    except Exception:
        return {}


def _allowed_guided_modes(policy: Dict[str, Any]) -> List[str]:
    modes = []
    for m in policy.get("allowed_evidence_modes") or []:
        tok = str(m or "").strip().upper()
        if tok and tok != "DOCUMENT_UPLOAD":
            modes.append(tok)
    return modes


def _strongest_evidence_method(modes: Sequence[str], policy: Dict[str, Any]) -> Optional[str]:
    if not modes:
        return None
    workflow = str(policy.get("primary_resolution_workflow") or "").strip().upper()
    if workflow == "GUIDED_DECLARATION" and "STRUCTURED_DECLARATION" in modes:
        return "STRUCTURED_DECLARATION"
    if workflow in ("LEGACY_DOCUMENT_UPLOAD", "DOCUMENT_UPLOAD") and "DOCUMENT_UPLOAD" in (
        policy.get("allowed_evidence_modes") or []
    ):
        return "DOCUMENT_UPLOAD"
    ranked = sorted(modes, key=lambda m: _EVIDENCE_MODE_STRENGTH.get(m, 0), reverse=True)
    return ranked[0] if ranked else None


def _has_persisted_submission(req: Dict[str, Any]) -> bool:
    ea = req.get("evidence_authority") if isinstance(req.get("evidence_authority"), dict) else {}
    return bool(str(ea.get("primary_evidence_record_id") or "").strip())


def _workflow_stage(req: Dict[str, Any]) -> str:
    lifecycle = (req.get("client_lifecycle_state") or "").upper()
    ea = _ea_blob(req)
    ea_state = (ea.get("state") or "").upper()
    if lifecycle == "VERIFIED" or ea_state in EA_VERIFIED_STATES:
        return "verified"
    if str(req.get("truth_presentation_stage") or "").strip().lower() == "verified":
        return "verified"

    truth_stage = str(req.get("truth_presentation_stage") or "").strip()
    if truth_stage:
        stage_map = {
            "verified": "verified",
            "platform_verification_pending": "platform_verification_pending",
            "escalation_review": "escalation_review",
            "followup_required": "followup_required",
            "operational_incomplete": "declaration_incomplete",
            "declaration_recorded": "recorded_on_file",
            "assessment_recorded": "recorded_on_file",
            "evidence_recorded": "recorded_on_file",
            "supporting_upload_only": "supporting_uploaded",
            "expiry_confirmation_required": "expiry_confirmation_required",
            "action_required": "no_evidence",
            "collect_evidence": "no_evidence",
        }
        mapped = stage_map.get(truth_stage)
        if mapped:
            return mapped

    comp = req.get("evidence_completeness") if isinstance(req.get("evidence_completeness"), dict) else {}
    missing = int(comp.get("required_missing_count") or 0)

    if ea_state in ("REJECTED", "EA_REJECTED"):
        return "rejected"
    if ea_state in ("MISMATCH_FLAGGED", "EA_MISMATCH_FLAGGED"):
        return "reviewer_feedback"
    if lifecycle == "PENDING_REVIEW" or ea_state in ("PENDING_ADMIN_REVIEW", "EA_PENDING_ADMIN_REVIEW"):
        if req.get("queue_backed_review") is True or req.get("review_owner") in (
            "platform_admin",
            "platform_admin_escalation",
        ):
            return "awaiting_review"
        if _has_persisted_submission(req):
            return "recorded_on_file"
        return "awaiting_review"
    if missing > 0:
        return "declaration_incomplete"
    if _has_persisted_submission(req):
        return "recorded_on_file"
    if ea_state in ("UPLOADED_UNCONFIRMED", "EA_UPLOADED_UNCONFIRMED", "UPLOADED"):
        return "supporting_uploaded"
    if lifecycle == "ACTION_REQUIRED" or ea_state in ("MISSING", "EA_MISSING", ""):
        return "no_evidence"
    return "collect_evidence"


def _stale_review_active(req: Dict[str, Any]) -> bool:
    try:
        from services.cer_governance_presentation import stale_allowed_for_requirement

        if req.get("truth_presentation_stage") and not stale_allowed_for_requirement(req):
            return False
    except Exception:
        pass
    stage = _workflow_stage(req)
    if stage not in ("awaiting_review", "platform_verification_pending", "escalation_review", "followup_required"):
        if stage == "recorded_on_file":
            return False
        return False
    for key in ("updated_at", "submitted_at", "last_review_at"):
        ea = req.get("evidence_authority") if isinstance(req.get("evidence_authority"), dict) else {}
        dt = _parse_utc_dt(ea.get(key)) or _parse_utc_dt(req.get(key))
        if dt is None:
            continue
        age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
        if age_days >= 7:
            return True
    return False


def _progression_steps(req: Dict[str, Any], stage: str, strongest: Optional[str]) -> List[Dict[str, Any]]:
    has_submission = _has_persisted_submission(req)
    uploaded = stage == "supporting_uploaded"
    steps: List[Tuple[str, str]] = [
        ("choose_method", "Choose evidence method"),
        ("complete_form", "Complete structured record"),
        ("optional_supporting", "Attach supporting files (optional)"),
        ("submit", "Submit evidence for review"),
        ("review", "Await verification"),
        ("compliant", "Requirement verified"),
    ]
    status_for = {
        "no_evidence": 0,
        "supporting_uploaded": 1,
        "declaration_incomplete": 1,
        "collect_evidence": 0,
        "rejected": 1,
        "reviewer_feedback": 3,
        "submitted_pending_review": 3,
        "recorded_on_file": 3,
        "followup_required": 3,
        "platform_verification_pending": 4,
        "escalation_review": 4,
        "awaiting_review": 4,
        "verified": 5,
    }
    cursor = status_for.get(stage, 0)
    if stage == "verified":
        cursor = 5
    elif stage in ("awaiting_review", "submitted_pending_review", "platform_verification_pending", "escalation_review"):
        cursor = 4
    elif stage in ("recorded_on_file", "followup_required") and has_submission:
        cursor = max(cursor, 3)
    elif has_submission and stage not in ("rejected", "reviewer_feedback"):
        cursor = max(cursor, 3)
    elif uploaded:
        cursor = max(cursor, 1)
    if not strongest:
        cursor = min(cursor, 0)

    out: List[Dict[str, Any]] = []
    for idx, (sid, label) in enumerate(steps):
        if idx < cursor:
            st = "complete"
        elif idx == cursor:
            st = "current"
        elif stage in ("rejected", "reviewer_feedback") and sid == "review":
            st = "blocked"
        else:
            st = "pending"
        out.append({"id": sid, "label": label, "status": st})
    return out


def build_requirement_guidance_v1(
    req: Dict[str, Any],
    *,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministic requirement/evidence guidance — read-only, server-authoritative."""
    pol = policy if isinstance(policy, dict) else _requirement_policy(req)
    modes = _allowed_guided_modes(pol)
    strongest = _strongest_evidence_method(modes, pol)
    weaker = [m for m in modes if m != strongest]
    stage = _workflow_stage(req)
    lifecycle = (req.get("client_lifecycle_state") or "").upper()
    ea = req.get("evidence_authority") if isinstance(req.get("evidence_authority"), dict) else {}
    ea_state = (ea.get("state") or "").upper()
    comp = req.get("evidence_completeness") if isinstance(req.get("evidence_completeness"), dict) else {}
    missing = int(comp.get("required_missing_count") or 0)
    stale = _stale_review_active(req)
    uploaded_not_submitted = stage == "supporting_uploaded" or (
        ea_state in ("UPLOADED_UNCONFIRMED", "EA_UPLOADED_UNCONFIRMED", "UPLOADED") and not _has_persisted_submission(req)
    )
    submitted_not_verified = (
        lifecycle in ("PENDING_REVIEW", "SATISFIED_UNVERIFIED") or stage in ("awaiting_review",)
    ) and req.get("queue_backed_review") is True
    rejected_requires_action = stage == "rejected"
    reviewer_requested_changes = stage == "reviewer_feedback"
    weak_submission_risk = strongest == "STRUCTURED_DECLARATION" and len(modes) > 1

    missing_actions: List[str] = []
    try:
        from services.cer_actionability_presentation import component_guidance_lines

        missing_actions.extend(component_guidance_lines(req))
    except Exception:
        pass
    if missing > 0 and not missing_actions:
        missing_actions.append(f"Complete {missing} required field(s)")
    if stage == "no_evidence" and strongest:
        missing_actions.append(_MODE_LABELS.get(strongest, "Choose evidence method"))
    if uploaded_not_submitted and strongest:
        missing_actions.append("Submit structured evidence — supporting files alone do not satisfy the obligation")
    if rejected_requires_action:
        missing_actions.append("Review rejection reason and resubmit evidence")
    if reviewer_requested_changes:
        missing_actions.append("Address reviewer feedback and resubmit")

    blocked_paths: List[str] = []
    if submitted_not_verified and not rejected_requires_action:
        blocked_paths.extend(modes)
    if stage == "verified":
        blocked_paths.extend(modes)

    recommended_mode = strongest
    recommended_next_step = "Review requirement status"
    recommended_reason = "Follow the strongest available evidence path for this obligation."
    recommended_outcome = "Verified evidence can satisfy the compliance obligation after review."
    remaining_steps: List[str] = []
    likely_intent = "satisfy_obligation"
    authority_path = strongest or "document_upload"

    try:
        from services.customer_status_projector_v2 import cognition_copy_from_customer_status

        projector_copy = cognition_copy_from_customer_status(req)
    except Exception:
        projector_copy = None

    if projector_copy:
        recommended_next_step, recommended_reason = projector_copy
        recommended_mode = None
        key = str(req.get("customer_status_key") or "")
        if key in ("verified",):
            likely_intent = "monitor_renewal"
        elif key in ("under_review", "rejected"):
            likely_intent = "await_review"
        elif key in ("recorded", "satisfied", "followup_required", "additional_action_required"):
            likely_intent = "operational_closure"
        elif key == "escalation_required":
            likely_intent = "await_review"
        else:
            likely_intent = "satisfy_obligation"
    elif stage == "verified":
        recommended_next_step = "No further evidence required"
        recommended_reason = "Evidence is verified — obligation is satisfied unless other blockers exist."
        recommended_mode = None
        likely_intent = "monitor_renewal"
    elif rejected_requires_action:
        recommended_next_step = "Review rejected evidence and resubmit"
        recommended_reason = "Rejected evidence does not satisfy the obligation until corrected and resubmitted."
        recommended_mode = strongest
        remaining_steps = ["Review rejection details", "Correct evidence", "Submit for review"]
        likely_intent = "recover_from_rejection"
    elif reviewer_requested_changes:
        recommended_next_step = "Address reviewer feedback"
        recommended_reason = "Reviewer requested changes — submitted evidence is not verified yet."
        recommended_mode = strongest
        remaining_steps = ["Read reviewer feedback", "Update submission", "Resubmit for review"]
        likely_intent = "respond_to_review"
    elif submitted_not_verified or stage == "awaiting_review":
        recommended_next_step = "Awaiting review — submission not yet verified"
        recommended_reason = "Submitted evidence is under review. Supporting uploads alone cannot advance verification."
        recommended_mode = None
        remaining_steps = ["Wait for reviewer decision", "Respond if reviewer requests changes"]
        likely_intent = "await_review"
    elif stage == "declaration_incomplete":
        truth_stage = str(req.get("truth_presentation_stage") or "").strip()
        if truth_stage == "operational_incomplete":
            try:
                from services.cer_governance_presentation import cognition_next_step_for_requirement

                recommended_next_step, recommended_reason, remaining_steps = cognition_next_step_for_requirement(req)
                recommended_mode = None
                likely_intent = "operational_closure"
            except Exception:
                recommended_next_step = str(req.get("truth_presentation_label") or "Complete remaining compliance steps")
                recommended_reason = str(req.get("truth_presentation_subline") or "")
                remaining_steps = []
                likely_intent = "operational_closure"
        else:
            recommended_next_step = "Complete missing checklist fields"
            recommended_reason = f"{missing} required field(s) must be completed before submission."
            recommended_mode = strongest or "STRUCTURED_DECLARATION"
            remaining_steps = ["Complete required fields", "Submit evidence for review"]
            likely_intent = "complete_declaration"
    elif stage in ("recorded_on_file", "followup_required", "platform_verification_pending", "escalation_review"):
        try:
            from services.cer_governance_presentation import cognition_next_step_for_requirement

            recommended_next_step, recommended_reason, remaining_steps = cognition_next_step_for_requirement(req)
            recommended_mode = None
            likely_intent = "operational_closure"
        except Exception:
            recommended_next_step = str(req.get("truth_presentation_label") or "Review requirement status")
            recommended_reason = str(req.get("truth_presentation_subline") or "")
            remaining_steps = []
            likely_intent = "operational_closure"
    elif uploaded_not_submitted:
        recommended_next_step = _MODE_LABELS.get(strongest or "", "Complete structured form and submit evidence")
        recommended_reason = "Supporting files are saved to your vault only — complete the structured record and submit."
        recommended_mode = strongest
        remaining_steps = ["Complete structured record", "Submit evidence for review"]
        likely_intent = "submit_authoritative_evidence"
    elif strongest:
        recommended_next_step = _MODE_LABELS.get(strongest, "Add compliance evidence")
        recommended_reason = (
            "This is the strongest evidence path configured for this requirement."
            if _EVIDENCE_MODE_CONFIDENCE.get(strongest) in ("high", "medium_high")
            else "Declaration-only or weaker paths may require additional review before satisfying compliance."
        )
        remaining_steps = ["Complete structured record", "Optionally attach supporting files", "Submit evidence for review"]
        likely_intent = "provide_evidence"
    elif str(pol.get("primary_resolution_workflow") or "").upper() == "LEGACY_DOCUMENT_UPLOAD":
        recommended_next_step = "Upload valid evidence document"
        recommended_reason = "This requirement is satisfied by an authoritative document upload on the Documents page."
        authority_path = "DOCUMENT_UPLOAD"
        likely_intent = "upload_document"

    operational_risk_flags: List[str] = []
    if uploaded_not_submitted:
        operational_risk_flags.append("UPLOADED_NOT_SUBMITTED")
    if submitted_not_verified:
        operational_risk_flags.append("SUBMITTED_NOT_VERIFIED")
    if weak_submission_risk:
        operational_risk_flags.append("WEAK_EVIDENCE_PATH_AVAILABLE")
    if stale:
        operational_risk_flags.append("STALE_REVIEW")
    if (req.get("lifecycle_tier") or "").lower() in ("overdue", "critical"):
        operational_risk_flags.append("OVERDUE_REQUIREMENT")

    return {
        "guidance_version": GUIDANCE_VERSION,
        "read_only": True,
        "likely_intent": likely_intent,
        "recommended_authority_path": authority_path,
        "strongest_evidence_method": strongest,
        "weaker_alternative_methods": weaker,
        "recommended_next_step": recommended_next_step,
        "recommended_next_step_reason": recommended_reason,
        "recommended_evidence_mode": recommended_mode,
        "recommended_outcome": recommended_outcome,
        "remaining_steps": remaining_steps,
        "current_progress_state": stage,
        "workflow_stage": stage,
        "missing_actions": missing_actions,
        "uploaded_not_submitted": uploaded_not_submitted,
        "submitted_not_verified": submitted_not_verified,
        "rejected_requires_action": rejected_requires_action,
        "reviewer_requested_changes": reviewer_requested_changes,
        "authority_confidence_level": _EVIDENCE_MODE_CONFIDENCE.get(strongest or "", "unknown"),
        "progression_steps": _progression_steps(req, stage, strongest),
        "operational_risk_flags": operational_risk_flags,
        "blocked_paths": blocked_paths,
        "weak_submission_risk": weak_submission_risk,
        "missing_required_step": missing_actions[0] if missing_actions else None,
        "review_state": {
            "client_lifecycle": lifecycle,
            "evidence_authority_state": ea_state or None,
            "stale_review": stale,
        },
        "progression_state": stage,
    }


def build_envelope_for_requirement(req: Dict[str, Any]) -> Dict[str, Any]:
    take_action = req.get("take_action") if isinstance(req.get("take_action"), dict) else {}
    primary = _primary_from_take_action(take_action)
    blockers = _blockers_from_requirement(req)
    truth = _truth_flags_for_requirement(req)
    lifecycle = req.get("client_lifecycle_state") or req.get("lifecycle_tier") or ""
    guidance = build_requirement_guidance_v1(req)
    stale = bool((guidance.get("review_state") or {}).get("stale_review"))

    if guidance.get("recommended_next_step") and not primary:
        primary = {
            "key": guidance.get("recommended_evidence_mode") or "requirement_guidance",
            "label": guidance.get("recommended_next_step"),
            "hint": guidance.get("recommended_next_step_reason") or "",
            "source": "requirement_guidance_v1",
        }
    elif guidance.get("recommended_next_step") and guidance.get("current_progress_state") in (
        "no_evidence",
        "supporting_uploaded",
        "declaration_incomplete",
        "rejected",
        "reviewer_feedback",
    ):
        primary = {
            "key": guidance.get("recommended_evidence_mode") or primary.get("key") if primary else "requirement_guidance",
            "label": guidance.get("recommended_next_step"),
            "hint": guidance.get("recommended_next_step_reason") or (primary.get("hint") if primary else ""),
            "url": primary.get("url") if primary else None,
            "source": "requirement_guidance_v1",
        }

    if guidance.get("rejected_requires_action") and not any(b.get("code") == "EVIDENCE_REJECTED" for b in blockers):
        blockers.insert(
            0,
            {
                "code": "EVIDENCE_REJECTED",
                "message": guidance.get("recommended_next_step") or "Evidence rejected — action required.",
                "truth_note": TRUTH_DISTINCTIONS["uploaded_not_verified"],
            },
        )
    if stale:
        owner = req.get("review_owner") or req.get("stale_owner") or "reviewer"
        stale_msg = f"Follow-up outstanding — action may be required ({owner})."
        if owner == "platform_admin":
            stale_msg = "Platform verification has been pending for an extended period."
        elif owner == "platform_admin_escalation":
            stale_msg = "Escalated review has been pending for an extended period."
        blockers.append(
            {
                "code": "STALE_REVIEW",
                "message": stale_msg,
                "truth_note": TRUTH_DISTINCTIONS["submitted_not_compliant"],
            }
        )
    if guidance.get("uploaded_not_submitted"):
        truth = {**truth, "uploaded_not_verified": True}

    if _requirement_authority_verified(req):
        truth = {
            "uploaded_not_verified": False,
            "submitted_not_compliant": False,
            "assigned_not_fixed": False,
            "completed_not_compliant": False,
            "acknowledged_not_resolved": False,
        }
        primary = _verified_view_primary_action(req)
        blockers = [b for b in blockers if b.get("code") not in ("EVIDENCE_REJECTED", "AWAITING_REVIEW")]
        user_safe_summary = "No further evidence required"
    elif _expiry_semantics_pending_only(req):
        truth = {
            **truth,
            "uploaded_not_verified": False,
            "submitted_not_compliant": False,
        }
        expiry_label = str(req.get("truth_presentation_label") or "Add expiry information").strip()
        expiry_hint = str(req.get("truth_presentation_subline") or "").strip()
        primary = {
            "key": "add_expiry_information",
            "label": expiry_label if expiry_label.lower() != "supporting evidence uploaded" else "Add expiry information",
            "hint": expiry_hint or "Add expiry date information for this certificate.",
            "source": "operational_cognition_service.expiry_semantics",
        }
        user_safe_summary = primary.get("label")
    else:
        user_safe_summary = guidance.get("recommended_next_step") or (primary.get("label") if primary else lifecycle)

    envelope = {
        "cognition_version": COGNITION_VERSION,
        "entity_type": "requirement",
        "read_only": True,
        "forbidden_mutations": sorted(FORBIDDEN_MUTATIONS),
        "primary_action": primary,
        "continuation_state": {"mode": "compliance", "summary": lifecycle},
        "workflow_state": {"lifecycle": lifecycle, "status": req.get("status"), "workflow_stage": guidance.get("workflow_stage")},
        "progression_state": {
            "evidence_badge": req.get("evidence_badge_label"),
            "step": guidance.get("progression_state"),
            "steps": guidance.get("progression_steps"),
        },
        "blockers": blockers,
        "warnings": [],
        "review_state": guidance.get("review_state") or {},
        "escalation_state": {
            "active": (req.get("lifecycle_tier") or "").lower() in ("overdue", "critical"),
            "level": req.get("lifecycle_tier"),
            "label": req.get("lifecycle_tier"),
        },
        "degraded_state": {"active": False},
        "stale_state": {"active": stale, "label": "Stale review" if stale else None},
        "operational_truth_flags": truth,
        "recommended_priority": "urgent" if (req.get("lifecycle_tier") or "").lower() == "overdue" else "normal",
        "user_safe_summary": user_safe_summary,
        "requirement_guidance_v1": guidance,
    }
    envelope["list_guidance"] = build_list_guidance(envelope)
    return envelope


def build_envelope_for_rent_ledger(ledger: Dict[str, Any]) -> Dict[str, Any]:
    outstanding = int(ledger.get("outstanding_balance_minor") or 0)
    is_overdue = bool(ledger.get("is_overdue"))
    status = ledger.get("status") or ""
    primary = None
    if outstanding > 0 and status not in ("PAID", "WAIVED"):
        primary = {
            "key": "record_payment",
            "label": "Record payment",
            "url": f"/operations/rent?property_id={ledger.get('property_id')}&tab=ledger&ledger_id={ledger.get('ledger_id')}",
            "hint": f"{ledger.get('period_key')} — outstanding balance due.",
            "source": "rent_attention_projection",
        }
    blockers = []
    if status == "UPCOMING" and not is_overdue:
        blockers.append(
            {
                "code": "FUTURE_PERIOD",
                "message": "Future rent period — not yet due for arrears treatment.",
                "truth_note": "Scheduled forecast is not overdue arrears.",
            }
        )
    envelope = {
        "cognition_version": COGNITION_VERSION,
        "entity_type": "rent_ledger",
        "read_only": True,
        "forbidden_mutations": sorted(FORBIDDEN_MUTATIONS),
        "primary_action": primary,
        "continuation_state": {"mode": "rent_collection", "summary": status},
        "workflow_state": {"ledger_status": status, "period_key": ledger.get("period_key")},
        "progression_state": {"outstanding_minor": outstanding},
        "blockers": blockers,
        "warnings": [],
        "review_state": {},
        "escalation_state": {"active": is_overdue, "level": "high" if is_overdue else None, "label": "Overdue rent" if is_overdue else None},
        "degraded_state": {"active": False},
        "stale_state": {"active": False},
        "operational_truth_flags": {
            "uploaded_not_verified": False,
            "submitted_not_compliant": False,
            "assigned_not_fixed": False,
            "completed_not_compliant": False,
            "acknowledged_not_resolved": False,
        },
        "recommended_priority": "urgent" if is_overdue else "normal",
        "user_safe_summary": f"{ledger.get('tenant_name') or 'Tenant'} — {ledger.get('period_key')} ({status})",
    }
    envelope["list_guidance"] = build_list_guidance(envelope)
    return envelope


async def attach_cognition_to_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    from services.customer_operational_language_service import sanitize_issue_for_customer

    out = sanitize_issue_for_customer(issue)
    out["operational_cognition"] = build_envelope_for_issue(issue)
    return out


async def attach_cognition_to_risk_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(signal)
    out["operational_cognition"] = build_envelope_for_risk_signal(signal)
    return out


async def attach_cognition_to_job_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload)
    out["operational_cognition"] = build_envelope_for_job(payload)
    out["operational_cognition"]["list_guidance"] = build_list_guidance(out["operational_cognition"])
    return out


async def attach_cognition_to_requirement(req: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(req)
    out["operational_cognition"] = build_envelope_for_requirement(req)
    return out


async def attach_cognition_to_rent_ledger(ledger: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(ledger)
    out["operational_cognition"] = build_envelope_for_rent_ledger(ledger)
    return out


def build_envelope_for_unresolved_evidence(doc: Dict[str, Any]) -> Dict[str, Any]:
    review_state = (doc.get("evidence_review_state") or "").upper()
    primary = {
        "key": "disposition",
        "label": "Resolve evidence ownership",
        "hint": "Assign to property/requirement or reject — uploaded evidence is not verified until resolved.",
        "source": "evidence_authority.unresolved_queue",
    }
    blockers = [
        {
            "code": "UNRESOLVED_OWNERSHIP",
            "message": "Evidence ownership is unresolved — compliance cannot be verified.",
            "truth_note": TRUTH_DISTINCTIONS["uploaded_not_verified"],
        }
    ]
    envelope = {
        "cognition_version": COGNITION_VERSION,
        "entity_type": "unresolved_evidence",
        "read_only": True,
        "forbidden_mutations": sorted(FORBIDDEN_MUTATIONS),
        "primary_action": primary,
        "continuation_state": {"mode": "evidence_review", "summary": review_state or "UNRESOLVED"},
        "workflow_state": {"evidence_scope_type": doc.get("evidence_scope_type"), "status": doc.get("status")},
        "progression_state": {"assurance_tier": doc.get("assurance_tier")},
        "blockers": blockers,
        "warnings": [{"code": "UPLOADED_NOT_VERIFIED", "message": TRUTH_DISTINCTIONS["uploaded_not_verified"]}],
        "review_state": {"evidence_review_state": review_state, "review_required": doc.get("review_required")},
        "escalation_state": {"active": bool(doc.get("manual_review_flag")), "level": "high", "label": "Manual review"},
        "degraded_state": {"active": False},
        "stale_state": {"active": False},
        "operational_truth_flags": {
            "uploaded_not_verified": True,
            "submitted_not_compliant": True,
            "assigned_not_fixed": False,
            "completed_not_compliant": False,
            "acknowledged_not_resolved": False,
        },
        "recommended_priority": "urgent",
        "user_safe_summary": doc.get("file_name") or "Unresolved evidence document",
    }
    envelope["list_guidance"] = build_list_guidance(envelope)
    return envelope


def attach_cognition_to_work_order(wo: Dict[str, Any]) -> Dict[str, Any]:
    from services.compliance_workflow_service import serialize_client_job

    payload = serialize_client_job(wo)
    env = build_envelope_for_job(payload)
    env["list_guidance"] = build_list_guidance(env)
    out = dict(wo)
    out["operational_cognition"] = env
    return out


def attach_cognition_to_issue_sync(issue: Dict[str, Any]) -> Dict[str, Any]:
    from services.customer_operational_language_service import sanitize_issue_for_customer

    out = sanitize_issue_for_customer(issue)
    out["operational_cognition"] = build_envelope_for_issue(issue)
    return out


def attach_cognition_to_risk_signal_sync(signal: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(signal)
    out["operational_cognition"] = build_envelope_for_risk_signal(signal)
    return out


def attach_cognition_to_unresolved_evidence(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out["operational_cognition"] = build_envelope_for_unresolved_evidence(doc)
    return out


def assert_cognition_read_only(envelope: Dict[str, Any]) -> None:
    """Guardrail: envelope must never claim mutation authority."""
    if not envelope.get("read_only"):
        raise ValueError("operational_cognition envelope must be read_only")
    if not envelope.get("forbidden_mutations"):
        raise ValueError("operational_cognition envelope must declare forbidden_mutations")
