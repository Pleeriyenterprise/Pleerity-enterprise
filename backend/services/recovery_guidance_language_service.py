"""Human-language recovery guidance — no engineering or AI terminology."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.recovery_constants import (
    RECOVERY_CONTRACTOR_ACTIVATION_STALL,
    RECOVERY_CONTRACTOR_NON_RESPONSE,
    RECOVERY_EVIDENCE_REJECTION_LOOP,
    RECOVERY_OPERATIONAL_DEAD_END,
    RECOVERY_OVERDUE_REQUIREMENT_STALL,
    RECOVERY_QUOTE_NEGOTIATION_LOOP,
    RECOVERY_TENANT_ACTIVATION_STALL,
    RECOVERY_VISIT_RESCHEDULE_LOOP,
    RECOVERY_WAITING_ON_CONTRACTOR_ACTION,
    RECOVERY_WAITING_ON_EVIDENCE_REVIEW,
    RECOVERY_WAITING_ON_LANDLORD_APPROVAL,
    RECOVERY_WORKFLOW_STATE_DRIFT,
    RECOVERY_WORK_ORDER_ABANDONMENT_RISK,
)

_PARTY_LABEL = {
    "landlord": "the landlord",
    "contractor": "the contractor",
    "tenant": "the tenant",
    "reviewer": "evidence review",
    "admin": "support review",
}


def _party_label(party: Optional[str]) -> str:
    return _PARTY_LABEL.get((party or "").lower(), party or "someone involved")


def _hours_phrase(hours: Optional[float]) -> str:
    if hours is None:
        return "some time"
    h = int(hours)
    if h < 24:
        return f"{h} hour{'s' if h != 1 else ''}"
    days = h // 24
    return f"{days} day{'s' if days != 1 else ''}"


def build_recovery_summary(recovery_type: str, *, waiting_on_party: Optional[str], age_hours: Optional[float]) -> str:
    age = _hours_phrase(age_hours)
    party = _party_label(waiting_on_party)
    templates = {
        RECOVERY_CONTRACTOR_NON_RESPONSE: f"The contractor has not responded to the requested quote for {age}.",
        RECOVERY_QUOTE_NEGOTIATION_LOOP: "Quote revisions are continuing without approval progress.",
        RECOVERY_VISIT_RESCHEDULE_LOOP: "This visit has been rescheduled several times without a confirmed date.",
        RECOVERY_EVIDENCE_REJECTION_LOOP: "Evidence for this requirement has been rejected more than once.",
        RECOVERY_TENANT_ACTIVATION_STALL: f"The tenant has not finished portal setup for {age}.",
        RECOVERY_CONTRACTOR_ACTIVATION_STALL: f"The contractor has not finished account setup for {age}.",
        RECOVERY_OVERDUE_REQUIREMENT_STALL: f"A compliance requirement is overdue and still unresolved after {age}.",
        RECOVERY_WORK_ORDER_ABANDONMENT_RISK: f"This job has been inactive for {age} despite reminders.",
        RECOVERY_WAITING_ON_LANDLORD_APPROVAL: f"This job is waiting on {party} to review and decide for {age}.",
        RECOVERY_WAITING_ON_CONTRACTOR_ACTION: f"This job is waiting on {party} to take the next step for {age}.",
        RECOVERY_WAITING_ON_EVIDENCE_REVIEW: f"Uploaded evidence is waiting on review for {age}.",
        RECOVERY_WORKFLOW_STATE_DRIFT: "The job status and next steps no longer line up clearly.",
        RECOVERY_OPERATIONAL_DEAD_END: "This job cannot currently move forward because no next step is available.",
    }
    return templates.get(recovery_type, "This item needs attention before work can continue.")


def build_recovery_explanation(
    recovery_type: str,
    *,
    waiting_on_party: Optional[str],
    age_hours: Optional[float],
    repetition_count: int = 0,
    entity_label: Optional[str] = None,
) -> str:
    label = entity_label or "This item"
    party = _party_label(waiting_on_party)
    age = _hours_phrase(age_hours)
    parts: List[str] = []
    if recovery_type == RECOVERY_CONTRACTOR_NON_RESPONSE:
        parts.append(f"{label} is blocked because the contractor has not submitted a quote.")
        parts.append(f"Progress stopped about {age} ago while waiting on the contractor.")
    elif recovery_type == RECOVERY_QUOTE_NEGOTIATION_LOOP:
        parts.append(f"{label} has gone through {repetition_count or 'multiple'} quote revisions without approval.")
        parts.append("Each revision adds delay and leaves the job waiting on a clear decision.")
    elif recovery_type == RECOVERY_VISIT_RESCHEDULE_LOOP:
        parts.append(f"The visit for {label.lower()} has been moved {repetition_count or 'several'} times.")
        parts.append("Without a confirmed visit, on-site work cannot proceed.")
    elif recovery_type == RECOVERY_EVIDENCE_REJECTION_LOOP:
        parts.append(f"Evidence linked to {label.lower()} was rejected and not yet replaced satisfactorily.")
        parts.append(f"The requirement remains open after {repetition_count or 'repeated'} rejection(s).")
    elif recovery_type == RECOVERY_WORK_ORDER_ABANDONMENT_RISK:
        parts.append(f"{label} has had little or no progress for {age}.")
        parts.append("Reminders have not led to movement, so manual follow-up may be needed.")
    elif recovery_type == RECOVERY_OPERATIONAL_DEAD_END:
        parts.append(f"{label} has no clear next step anyone can take right now.")
        parts.append("Someone may need to review the job and decide how to unblock it.")
    elif recovery_type in (RECOVERY_WAITING_ON_LANDLORD_APPROVAL, RECOVERY_WAITING_ON_CONTRACTOR_ACTION):
        parts.append(f"{label} is waiting on {party}.")
        parts.append(f"It has been waiting for about {age}.")
    elif recovery_type == RECOVERY_WAITING_ON_EVIDENCE_REVIEW:
        parts.append(f"Evidence for {label.lower()} is uploaded but not yet reviewed.")
        parts.append(f"It has been waiting for about {age}.")
    elif recovery_type in (RECOVERY_TENANT_ACTIVATION_STALL, RECOVERY_CONTRACTOR_ACTIVATION_STALL):
        parts.append(f"Account setup is incomplete for {party}.")
        parts.append(f"This has been pending for about {age}.")
    elif recovery_type == RECOVERY_OVERDUE_REQUIREMENT_STALL:
        parts.append(f"{label} is past its due date and still needs resolution.")
        parts.append(f"It has been overdue for about {age}.")
    elif recovery_type == RECOVERY_WORKFLOW_STATE_DRIFT:
        parts.append(f"{label} shows mixed signals about what should happen next.")
        parts.append("Review the job to confirm who should act and what is still required.")
    else:
        parts.append(f"{label} needs attention before work can continue.")
    return " ".join(parts)


def build_recommended_next_steps(recovery_type: str, *, waiting_on_party: Optional[str]) -> List[str]:
    party = (waiting_on_party or "").lower()
    steps_map: Dict[str, List[str]] = {
        RECOVERY_CONTRACTOR_NON_RESPONSE: [
            "Check whether the contractor received the quote request.",
            "Consider contacting the contractor or adding an alternate contractor.",
            "Review the job details to confirm scope is clear.",
        ],
        RECOVERY_QUOTE_NEGOTIATION_LOOP: [
            "Review the latest quote and decide whether to approve or request another revision.",
            "Clarify budget or scope expectations with the contractor if needed.",
            "Consider whether a different contractor may be more suitable.",
        ],
        RECOVERY_VISIT_RESCHEDULE_LOOP: [
            "Confirm a visit date that works for all parties.",
            "Check access arrangements with the tenant if applicable.",
            "Contact the contractor if dates keep slipping.",
        ],
        RECOVERY_EVIDENCE_REJECTION_LOOP: [
            "Review why the evidence was rejected.",
            "Upload a clearer or complete document if you are the uploader.",
            "Open the requirement to see what is still needed.",
        ],
        RECOVERY_WORK_ORDER_ABANDONMENT_RISK: [
            "Review stalled jobs and decide who should follow up.",
            "Contact the party who last had the action.",
            "Consider reassigning or closing the job if it is no longer needed.",
        ],
        RECOVERY_WAITING_ON_LANDLORD_APPROVAL: [
            "Review the pending item and make a decision when ready.",
            "Contact support if you are unsure what is required.",
        ],
        RECOVERY_WAITING_ON_CONTRACTOR_ACTION: [
            "Follow up with the contractor on the outstanding step.",
            "Review whether another contractor should be considered.",
        ],
        RECOVERY_WAITING_ON_EVIDENCE_REVIEW: [
            "Review uploaded evidence when you are ready.",
            "Request a clearer upload if the document is not sufficient.",
        ],
        RECOVERY_OPERATIONAL_DEAD_END: [
            "Open the job and review what has happened so far.",
            "Contact support if no safe next step is visible.",
        ],
        RECOVERY_TENANT_ACTIVATION_STALL: [
            "Resend the tenant portal invite if needed.",
            "Confirm the tenant has the correct email address.",
        ],
        RECOVERY_CONTRACTOR_ACTIVATION_STALL: [
            "Resend the contractor invite if needed.",
            "Review contractor details and confirm contact information.",
        ],
        RECOVERY_OVERDUE_REQUIREMENT_STALL: [
            "Open the requirement and see what evidence or action is still needed.",
            "Upload or arrange missing documentation.",
        ],
        RECOVERY_WORKFLOW_STATE_DRIFT: [
            "Review the job timeline and current status.",
            "Confirm who should take the next step.",
        ],
    }
    base = steps_map.get(recovery_type, ["Review this item and decide the next safe step."])
    if party == "landlord":
        return base
    return base


def build_risk_statement(recovery_type: str, *, age_hours: Optional[float], repetition_count: int) -> str:
    if recovery_type == RECOVERY_WORK_ORDER_ABANDONMENT_RISK:
        return "If ignored, this job may be abandoned and compliance or repair work may slip further."
    if recovery_type == RECOVERY_OVERDUE_REQUIREMENT_STALL:
        return "If ignored, compliance risk may increase and deadlines may be missed."
    if recovery_type in (RECOVERY_QUOTE_NEGOTIATION_LOOP, RECOVERY_VISIT_RESCHEDULE_LOOP):
        return "If ignored, delays may continue and costs or tenant impact may grow."
    if recovery_type == RECOVERY_EVIDENCE_REJECTION_LOOP:
        return "If ignored, the requirement may remain non-compliant until acceptable evidence is provided."
    if age_hours and age_hours >= 72:
        return "If ignored, delays may continue and manual intervention may become necessary."
    if repetition_count >= 3:
        return "Repeated setbacks suggest this may need direct follow-up soon."
    return "If ignored, progress may remain blocked."
