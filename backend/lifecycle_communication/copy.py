"""Governed communication copy per lifecycle family."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from lifecycle_communication.constants import LifecycleFamily
from lifecycle_communication.verbs import governed_verb

# (primary_action, evidence_expectation, how_text, supporting_explanation)
_FAMILY_ACTIONS: Dict[str, Tuple[str, str, str, str]] = {
    "EXPIRY_BASED": (
        "Renew the certificate and upload updated evidence",
        "Upload renewed certificate",
        "Open the requirement, arrange renewal with your contractor if needed, then upload the renewed certificate with the correct dates.",
        "This reflects the expiry date recorded for your certificate.",
    ),
    "LICENSING": (
        "Renew the licence and upload updated evidence",
        "Upload renewed licence",
        "Open the requirement, complete licence renewal with the issuing authority, then upload the renewed licence.",
        "This reflects the renewal date recorded for your licence.",
    ),
    "REGISTRATION": (
        "Renew the registration and upload updated evidence",
        "Upload renewed registration evidence",
        "Open the requirement, complete registration renewal, then upload confirmation with the correct dates.",
        "This reflects the renewal date recorded for your registration.",
    ),
    "DECLARATION_BASED": (
        "Complete the required declaration",
        "Record declaration",
        "Open the requirement and complete the declaration with the information requested.",
        "Declarations confirm compliance obligations that do not rely on a certificate expiry date.",
    ),
    "SELF_CERTIFIED": (
        "Complete the self-certification declaration",
        "Record self-certification declaration",
        "Open the requirement and complete the self-certification declaration.",
        "Self-certifications confirm compliance without uploading a certificate.",
    ),
    "STRUCTURED_EVIDENCE": (
        "Submit the compliance declaration",
        "Submit compliance declaration",
        "Open the requirement and complete the structured declaration form.",
        "Structured declarations capture compliance confirmations in a guided format.",
    ),
    "TENANCY_LIFECYCLE": (
        "Upload the required tenancy document",
        "Upload signed tenancy agreement",
        "Open the requirement and upload the tenancy agreement or milestone evidence requested.",
        "Tenancy records confirm key tenancy milestones for your property.",
    ),
    "OCCUPANCY_LIFECYCLE": (
        "Record occupancy verification",
        "Record occupancy verification",
        "Open the requirement and record the occupancy verification details requested.",
        "Occupancy verification confirms who is living at the property when required.",
    ),
    "REVIEW_BASED": (
        "Complete the required review",
        "Provide review outcome or supporting evidence",
        "Open the requirement, complete the review, and upload any supporting evidence requested.",
        "Reviews confirm ongoing compliance between certificate renewals.",
    ),
    "EVENT_BASED": (
        "Record the required compliance event",
        "Record event evidence",
        "Open the requirement and record the event with the date and details requested.",
        "Event-based obligations are tied to a specific action or milestone.",
    ),
    "DOCUMENT_EVIDENCE": (
        "Upload the required evidence",
        "Upload supporting evidence",
        "Open the requirement and upload the document or evidence requested.",
        "Evidence confirms that this obligation has been met.",
    ),
    "INSPECTION": (
        "Arrange the inspection and upload the report",
        "Upload inspection report",
        "Arrange the inspection with a qualified provider, then upload the inspection report.",
        "Inspection evidence confirms the property or asset has been checked.",
    ),
    "ASSESSMENT": (
        "Complete the assessment",
        "Upload assessment evidence",
        "Open the requirement, complete the assessment, and upload the outcome.",
        "Assessments confirm risk or safety obligations that are not simple certificate renewals.",
    ),
    "OPERATIONAL": (
        "Resolve the operational issue",
        "Provide supporting evidence or resolution notes",
        "Open the requirement or linked issue and complete the follow-up action requested.",
        "Operational items need landlord action to close out a property issue or task.",
    ),
}


def family_action_bundle(family: LifecycleFamily) -> Dict[str, str]:
    primary, evidence, how_text, supporting = _FAMILY_ACTIONS.get(
        str(family or ""),
        _FAMILY_ACTIONS["DOCUMENT_EVIDENCE"],
    )
    return {
        "primary_action": primary,
        "evidence_expectation": evidence,
        "how_text": how_text,
        "supporting_explanation": supporting,
        "lifecycle_verb": governed_verb(family),
    }


def _client_label_usable(family: str, label: str) -> bool:
    """Use API label only when it does not conflict with inferred communication family."""
    if not label or label in ("Action required", "Evidence required"):
        return False
    low = label.lower()
    fam = str(family or "")
    if fam in ("EXPIRY_BASED", "LICENSING", "REGISTRATION"):
        return True
    if any(token in low for token in ("renewal", "expires", "expiring", "certificate")):
        return False
    return True


def build_reason(
    family: LifecycleFamily,
    *,
    req_name: str,
    due_date: str = "",
    is_overdue: bool = False,
    days_remaining: int | None = None,
    client_lifecycle_label: str = "",
) -> str:
    """Specific WHY copy — avoid generic 'Action required' when family is known."""
    name = req_name or "this obligation"
    if _client_label_usable(family, client_lifecycle_label):
        if is_overdue:
            return f"{client_lifecycle_label} for {name}."
        if due_date:
            return f"{client_lifecycle_label} for {name} by {due_date}."
        return f"{client_lifecycle_label} for {name}."

    fam = str(family or "")
    if fam in ("EXPIRY_BASED", "LICENSING", "REGISTRATION"):
        if is_overdue:
            if fam == "LICENSING":
                return f"Licence renewal is overdue for {name}."
            if fam == "REGISTRATION":
                return f"Registration renewal is overdue for {name}."
            return f"Certificate renewal is overdue for {name}."
        if due_date:
            if days_remaining is not None and days_remaining >= 0:
                return f"{name} expires in {days_remaining} days on {due_date}."
            if fam == "LICENSING":
                return f"{name} licence renewal is due on {due_date}."
            if fam == "REGISTRATION":
                return f"{name} registration renewal is due on {due_date}."
            return f"{name} is due on {due_date}."
        return f"Certificate renewal is required for {name}."

    if fam in ("DECLARATION_BASED", "SELF_CERTIFIED", "STRUCTURED_EVIDENCE"):
        return f"Required declaration has not been completed for {name}."

    if fam == "TENANCY_LIFECYCLE":
        if is_overdue:
            return f"Required tenancy document is overdue for {name}."
        if due_date:
            return f"Tenancy milestone for {name} is due on {due_date}."
        return f"Required tenancy agreement has not been uploaded for {name}."

    if fam == "OCCUPANCY_LIFECYCLE":
        if is_overdue:
            return f"Occupancy verification is overdue for {name}."
        if due_date:
            return f"Occupancy verification for {name} is due on {due_date}."
        return f"Occupancy verification is outstanding for {name}."

    if fam == "REVIEW_BASED":
        if is_overdue:
            return f"Review for {name} is now overdue."
        if due_date:
            return f"{name} has a review due on {due_date}."
        return f"Assessment review is now due for {name}."

    if fam == "ASSESSMENT":
        if is_overdue:
            return f"Assessment for {name} is overdue."
        if due_date:
            return f"Assessment for {name} is due on {due_date}."
        return f"Assessment for {name} needs to be completed."

    if fam == "INSPECTION":
        if is_overdue:
            return f"Inspection for {name} is overdue."
        return f"Inspection needs to be arranged for {name}."

    if fam == "OPERATIONAL":
        if is_overdue:
            return f"Operational issue for {name} requires urgent attention."
        return f"Operational issue requires your attention for {name}."

    if fam == "EVENT_BASED":
        if due_date:
            return f"{name} requires action by {due_date}."
        return f"A required compliance event needs to be recorded for {name}."

    if is_overdue:
        return f"Supporting evidence for {name} is overdue."
    if due_date:
        return f"Supporting evidence for {name} is due by {due_date}."
    return f"Supporting evidence is required for {name}."


def build_when_text(due_date: str, *, is_overdue: bool = False, days_overdue: int | None = None) -> str:
    if is_overdue:
        if days_overdue is not None and int(days_overdue) > 0:
            return f"This was due {days_overdue} day(s) ago."
        if due_date:
            return f"This was due on {due_date}."
        return "This is overdue."
    if due_date:
        return f"Complete this by {due_date}."
    return "Complete this as soon as possible."


def primary_cta_label(
    family: LifecycleFamily,
    *,
    take_action_primary_label: str = "",
) -> str:
    if take_action_primary_label:
        return take_action_primary_label
    fam = str(family or "")
    defaults = {
        "EXPIRY_BASED": "Renew certificate",
        "LICENSING": "Renew licence",
        "REGISTRATION": "Renew registration",
        "DECLARATION_BASED": "Complete declaration",
        "SELF_CERTIFIED": "Complete declaration",
        "STRUCTURED_EVIDENCE": "Complete declaration",
        "TENANCY_LIFECYCLE": "Upload tenancy agreement",
        "OCCUPANCY_LIFECYCLE": "Record occupancy verification",
        "REVIEW_BASED": "Review assessment",
        "EVENT_BASED": "Record event",
        "DOCUMENT_EVIDENCE": "Upload evidence",
        "INSPECTION": "Arrange inspection",
        "ASSESSMENT": "Complete assessment",
        "OPERATIONAL": "Resolve operational issue",
    }
    return defaults.get(fam, "Upload evidence")


def secondary_cta_label(family: LifecycleFamily) -> str:
    fam = str(family or "")
    if fam in ("EXPIRY_BASED", "LICENSING", "REGISTRATION"):
        return "View evidence"
    if fam in ("DECLARATION_BASED", "SELF_CERTIFIED", "STRUCTURED_EVIDENCE"):
        return "Review declaration"
    if fam == "OPERATIONAL":
        return "View issue"
    return "Review document"


def semantic_line_for_group(
    family: LifecycleFamily,
    *,
    req_name: str,
    due_date: str = "",
    is_overdue: bool = False,
) -> str:
    """Short line for grouped reminder lists."""
    reason = build_reason(
        family,
        req_name=req_name,
        due_date=due_date,
        is_overdue=is_overdue,
    )
    return reason


def digest_posture_labels(
    family: LifecycleFamily,
    *,
    is_overdue: bool = False,
) -> tuple[str, str]:
    """Short label and operational note for monthly digest."""
    fam = str(family or "")
    if is_overdue:
        if fam in ("EXPIRY_BASED", "LICENSING", "REGISTRATION"):
            return "Renewal overdue", "Renewal or replacement evidence may be required — review obligation dates."
        if fam == "REVIEW_BASED":
            return "Review overdue", "Complete the review and upload any supporting evidence."
        if fam in ("DECLARATION_BASED", "SELF_CERTIFIED", "STRUCTURED_EVIDENCE"):
            return "Declaration overdue", "Complete the declaration to bring this obligation up to date."
        if fam == "OPERATIONAL":
            return "Operational follow-up overdue", "Resolve the operational issue to close this item."
        return "Action overdue", "Complete the required action and upload any supporting evidence."
    if fam in ("EXPIRY_BASED", "LICENSING", "REGISTRATION"):
        return "Renewal approaching", "Plan renewal before the recorded due date."
    if fam == "REVIEW_BASED":
        return "Review approaching", "Plan the review before the recorded due date."
    if fam in ("DECLARATION_BASED", "SELF_CERTIFIED", "STRUCTURED_EVIDENCE"):
        return "Declaration due", "Complete the declaration before the recorded due date."
    if fam == "TENANCY_LIFECYCLE":
        return "Tenancy milestone approaching", "Upload the tenancy document before the recorded date."
    if fam == "OCCUPANCY_LIFECYCLE":
        return "Occupancy review approaching", "Record occupancy verification before the recorded date."
    if fam == "ASSESSMENT":
        return "Assessment due", "Complete the assessment before the recorded due date."
    if fam == "OPERATIONAL":
        return "Operational follow-up due", "Resolve the operational issue before the recorded date."
    return "Action due soon", "Complete the required action before the recorded due date."


def risk_recommended_action(risk_type: str) -> str:
    """Governed risk card recommended actions — no certificate leakage into operational risks."""
    rt = str(risk_type or "").strip().upper()
    mapping = {
        "BOILER_FAILURE": "Arrange a qualified gas engineer inspection externally, or start a compliance job from Operations if your account uses jobs for inspections.",
        "DAMP_MOISTURE": "Arrange a damp inspection externally and plan work to fix the underlying cause.",
        "ELECTRICAL": "Review your electrical safety obligation and arrange an external inspection if it is due or out of date.",
        "RECURRING_REPAIRS": "Investigate the root cause instead of repeat patch repairs.",
        "SLA_BREACH": "Review open jobs with your contractor and re-prioritise anything that is overdue.",
        "COMPLIANCE_CHURN": "Upload missing evidence and complete outstanding obligations so your portfolio stays up to date.",
        "MAINTENANCE_FREQUENCY": "Review property condition and inspect assets that are generating repeat reports.",
        "CERTIFICATE_EXPIRY_SOON": "Renew the certificate before expiry and upload the new document with correct dates.",
    }
    return mapping.get(rt, "Review this item and complete the recommended follow-up action.")


def communication_to_template_context(communication: Dict[str, Any]) -> Dict[str, str]:
    """Flatten communication model for enablement / email template substitution."""
    return {
        "lca_heading": str(communication.get("heading") or ""),
        "lca_reason": str(communication.get("reason") or ""),
        "lca_what": str(communication.get("primary_action") or ""),
        "lca_when": str(communication.get("when_text") or ""),
        "lca_how": str(communication.get("how_text") or ""),
        "lca_next_step": str(communication.get("next_step") or ""),
        "lca_evidence": str(communication.get("evidence_expectation") or ""),
        "lca_primary_cta": str(communication.get("primary_cta") or ""),
        "lca_urgency": str(communication.get("urgency") or ""),
        "comm_heading": str(communication.get("heading") or ""),
        "comm_reason": str(communication.get("reason") or ""),
        "comm_what": str(communication.get("primary_action") or ""),
        "comm_when": str(communication.get("when_text") or ""),
        "comm_how": str(communication.get("how_text") or ""),
        "comm_next_step": str(communication.get("next_step") or ""),
    }
