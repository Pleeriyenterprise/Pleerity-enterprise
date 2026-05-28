"""
Operational Cognition Envelope v1 — read-only server-side orchestration.

Composes authoritative workflow/state signals into a single envelope for UI elevation.
MUST NOT mutate workflow, evidence, compliance, or financial authority.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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
    lifecycle = (req.get("client_lifecycle_state") or "").upper()
    ea = req.get("evidence_authority") if isinstance(req.get("evidence_authority"), dict) else {}
    ea_state = (ea.get("state") or "").upper()
    comp = req.get("evidence_completeness") if isinstance(req.get("evidence_completeness"), dict) else {}
    missing = int(comp.get("required_missing_count") or 0)
    return {
        "uploaded_not_verified": lifecycle in ("PENDING_REVIEW", "SATISFIED_UNVERIFIED", "ACTION_REQUIRED")
        or ea_state in ("EA_UPLOADED_UNCONFIRMED", "UPLOADED"),
        "submitted_not_compliant": missing > 0 or lifecycle == "ACTION_REQUIRED",
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
    cont = issue.get("operational_continuation") if isinstance(issue.get("operational_continuation"), dict) else {}
    primary = _primary_from_continuation(cont)
    if not primary and (issue.get("status") or "").lower() not in ("closed", "cancelled", "resolved"):
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
        "user_safe_summary": primary.get("label") if primary else issue.get("status"),
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


def build_envelope_for_requirement(req: Dict[str, Any]) -> Dict[str, Any]:
    take_action = req.get("take_action") if isinstance(req.get("take_action"), dict) else {}
    primary = _primary_from_take_action(take_action)
    blockers = _blockers_from_requirement(req)
    truth = _truth_flags_for_requirement(req)
    lifecycle = req.get("client_lifecycle_state") or req.get("lifecycle_tier") or ""

    envelope = {
        "cognition_version": COGNITION_VERSION,
        "entity_type": "requirement",
        "read_only": True,
        "forbidden_mutations": sorted(FORBIDDEN_MUTATIONS),
        "primary_action": primary,
        "continuation_state": {"mode": "compliance", "summary": lifecycle},
        "workflow_state": {"lifecycle": lifecycle, "status": req.get("status")},
        "progression_state": {"evidence_badge": req.get("evidence_badge_label")},
        "blockers": blockers,
        "warnings": [],
        "review_state": {
            "client_lifecycle": lifecycle,
            "evidence_authority": (req.get("evidence_authority") or {}).get("state") if isinstance(req.get("evidence_authority"), dict) else None,
        },
        "escalation_state": {
            "active": (req.get("lifecycle_tier") or "").lower() in ("overdue", "critical"),
            "level": req.get("lifecycle_tier"),
            "label": req.get("lifecycle_tier"),
        },
        "degraded_state": {"active": False},
        "stale_state": {"active": False},
        "operational_truth_flags": truth,
        "recommended_priority": "urgent" if (req.get("lifecycle_tier") or "").lower() == "overdue" else "normal",
        "user_safe_summary": primary.get("label") if primary else lifecycle,
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
    out = dict(issue)
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
    out = dict(issue)
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
