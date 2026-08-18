"""Canonical customer communication resolver."""

from __future__ import annotations

from typing import Any, Dict, Optional

from lifecycle_communication.completion import completion_wording, next_step_wording
from lifecycle_communication.constants import (
    AUTHORITY_VERSION,
    TONE_PROFESSIONAL,
    TONE_SUPPORTIVE,
    CommunicationChannel,
    CommunicationSurface,
)
from lifecycle_communication.context import (
    attention_kind_for_row,
    infer_communication_family,
    property_display_address,
    requirement_display_name,
    resolve_due_context,
)
from lifecycle_communication.copy import (
    build_reason,
    build_when_text,
    communication_to_template_context,
    digest_posture_labels,
    family_action_bundle,
    primary_cta_label,
    risk_recommended_action,
    secondary_cta_label,
    semantic_line_for_group,
)
from lifecycle_communication.headings import heading_for_family, heading_for_reminder_group, reminder_header_title


def resolve_customer_communication(
    requirement_row: Dict[str, Any],
    *,
    surface: CommunicationSurface = "portal_detail",
    channel: CommunicationChannel = "PORTAL",
    context: Optional[Dict[str, Any]] = None,
    take_action: Optional[Dict[str, Any]] = None,
    is_overdue: bool = False,
    due_date: Optional[str] = None,
    days_remaining: Optional[int] = None,
    days_overdue: Optional[int] = None,
    risk_type: Optional[str] = None,
    reminder_group_key: Optional[str] = None,
    verified: bool = False,
) -> Dict[str, Any]:
    """
    Transform authoritative lifecycle state into governed customer-facing communication.

    Does not determine lifecycle rules — consumes client_lifecycle_label, attention_kind,
    take_action, and requirement metadata only.
    """
    row = requirement_row if isinstance(requirement_row, dict) else {}
    ctx = context if isinstance(context, dict) else {}
    family = infer_communication_family(row)
    req_name = requirement_display_name(row)
    prop_addr = property_display_address(row, ctx)
    client_label = str(row.get("client_lifecycle_label") or "").strip()

    due_text, urgency, overdue_eff = resolve_due_context(
        row,
        context=ctx,
        is_overdue=is_overdue,
        due_date=due_date,
        days_remaining=days_remaining,
        days_overdue=days_overdue,
    )

    actions = family_action_bundle(family)
    ta = take_action if isinstance(take_action, dict) else row.get("take_action")
    ta_primary = ""
    ta_secondary = ""
    if isinstance(ta, dict):
        pri = ta.get("primary") if isinstance(ta.get("primary"), dict) else {}
        sec = ta.get("secondary") if isinstance(ta.get("secondary"), dict) else {}
        ta_primary = str(pri.get("label") or "").strip()
        ta_secondary = str(sec.get("label") or "").strip()

    reason = build_reason(
        family,
        req_name=req_name,
        due_date=due_text,
        is_overdue=overdue_eff,
        days_remaining=days_remaining,
        client_lifecycle_label=client_label,
    )
    when_text = build_when_text(due_text, is_overdue=overdue_eff, days_overdue=days_overdue)
    primary_cta = primary_cta_label(family, take_action_primary_label=ta_primary)
    secondary_cta = ta_secondary or secondary_cta_label(family)
    next_step = next_step_wording(family)
    completion = completion_wording(family, verified=verified)

    if reminder_group_key:
        heading = heading_for_reminder_group(reminder_group_key)
    elif surface in ("reminder_email", "reminder_sms"):
        heading = reminder_header_title(attention_kind_for_row(row))
    else:
        heading = heading_for_family(family, is_overdue=overdue_eff)

    tone = TONE_SUPPORTIVE if urgency in ("overdue", "action_required") else TONE_PROFESSIONAL

    surface_variants: Dict[str, Any] = {}
    if surface == "portal_chip":
        chip_text = client_label or (
            "Overdue" if overdue_eff else ("Due soon" if urgency == "due_soon" else actions["lifecycle_verb"])
        )
        surface_variants["chip_text"] = chip_text
    if surface == "reminder_email":
        surface_variants["intro_html"] = _reminder_intro_html(
            family=family,
            req_name=req_name,
            prop_addr=prop_addr,
            due_date=due_text,
            is_overdue=overdue_eff,
            days_remaining=days_remaining,
        )
        surface_variants["intro_text"] = _reminder_intro_text(
            family=family,
            req_name=req_name,
            prop_addr=prop_addr,
            due_date=due_text,
            is_overdue=overdue_eff,
            days_remaining=days_remaining,
        )
        surface_variants["why_received"] = _why_received(attention_kind_for_row(row))
    if surface == "reminder_sms":
        surface_variants["sms_body"] = _sms_body(family, overdue=overdue_eff)
    if surface == "digest":
        label, note = digest_posture_labels(family, is_overdue=overdue_eff)
        surface_variants["digest_label"] = label
        surface_variants["digest_note"] = note
    if surface == "risk_card" and risk_type:
        surface_variants["recommended_action"] = risk_recommended_action(risk_type)
    if reminder_group_key:
        surface_variants["semantic_line"] = semantic_line_for_group(
            family,
            req_name=req_name,
            due_date=due_text,
            is_overdue=overdue_eff,
        )

    model: Dict[str, Any] = {
        "authority_version": AUTHORITY_VERSION,
        "lifecycle_family": family,
        "lifecycle_verb": actions["lifecycle_verb"],
        "attention_kind": attention_kind_for_row(row),
        "heading": heading,
        "reason": reason,
        "primary_action": actions["primary_action"],
        "when_text": when_text,
        "how_text": actions["how_text"],
        "next_step": next_step,
        "evidence_expectation": actions["evidence_expectation"],
        "urgency": urgency,
        "supporting_explanation": actions["supporting_explanation"],
        "primary_cta": primary_cta,
        "secondary_cta": secondary_cta,
        "completion_wording": completion,
        "tone": tone,
        "surface": surface,
        "channel": channel,
        "surface_variants": surface_variants,
        "requirement_name": req_name,
        "property_address": prop_addr,
        "due_date": due_text,
        "is_overdue": overdue_eff,
    }
    model["template_context"] = communication_to_template_context(model)
    return model


def resolve_group_semantic_line(
    *,
    group_key: str,
    requirement_row: Dict[str, Any],
    semantic_line: str = "",
    due_date: str = "",
    is_overdue: bool = False,
) -> str:
    """Governed replacement for email_service._safe_reminder_semantic_line fallbacks."""
    line = str(semantic_line or "").strip()
    if line and not _is_forbidden_semantic(line):
        return line
    family = infer_communication_family(requirement_row)
    return semantic_line_for_group(
        family,
        req_name=requirement_display_name(requirement_row),
        due_date=due_date,
        is_overdue=is_overdue,
    )


def _is_forbidden_semantic(line: str) -> bool:
    low = line.lower()
    forbidden = (
        "blocking compliance",
        "externally verified",
        "legally validated",
        "verified",
        "certified",
        "operationally safe",
        "remediated",
        "remediation complete",
        "upload complete",
        "document-complete",
        "document complete",
        "upload-only complete",
        "action required",
        "compliance action required",
        "issue detected",
    )
    return any(f in low for f in forbidden)


def _why_received(attention_kind: Optional[str]) -> str:
    kind = str(attention_kind or "CERTIFICATE_EXPIRING")
    mapping = {
        "CERTIFICATE_EXPIRING": "compliance monitoring and expiry reminders are enabled for your account.",
        "REVIEW_DUE": "compliance monitoring and review reminders are enabled for your account.",
        "EVENT_ACTION_REQUIRED": "compliance monitoring and action reminders are enabled for your account.",
        "TENANCY_TERM_ENDING": "compliance monitoring and tenancy reminders are enabled for your account.",
        "OCCUPANCY_REVIEW_DUE": "compliance monitoring and occupancy review reminders are enabled for your account.",
        "OPERATIONAL_ACTION_REQUIRED": "compliance monitoring and operational reminders are enabled for your account.",
    }
    return mapping.get(kind, mapping["CERTIFICATE_EXPIRING"])


def _reminder_intro_html(
    *,
    family: str,
    req_name: str,
    prop_addr: str,
    due_date: str,
    is_overdue: bool,
    days_remaining: int | None = None,
) -> str:
    reason = build_reason(
        family,
        req_name=req_name,
        due_date=due_date,
        is_overdue=is_overdue,
        days_remaining=days_remaining,
    )
    if prop_addr:
        return (
            f"This is a reminder about <strong>{req_name}</strong> for your property at "
            f"<strong>{prop_addr}</strong>. {reason}"
        )
    return f"This is a reminder about <strong>{req_name}</strong>. {reason}"


def _reminder_intro_text(
    *,
    family: str,
    req_name: str,
    prop_addr: str,
    due_date: str,
    is_overdue: bool,
    days_remaining: int | None = None,
) -> str:
    reason = build_reason(
        family,
        req_name=req_name,
        due_date=due_date,
        is_overdue=is_overdue,
        days_remaining=days_remaining,
    )
    if prop_addr:
        return f"This is a reminder about {req_name} for your property at {prop_addr}. {reason}"
    return f"This is a reminder about {req_name}. {reason}"


def _sms_body(family: str, *, overdue: bool) -> str:
    fam = str(family or "")
    if fam == "REVIEW_BASED":
        noun = "compliance review(s)"
    elif fam == "TENANCY_LIFECYCLE":
        noun = "tenancy milestone(s)"
    elif fam == "OCCUPANCY_LIFECYCLE":
        noun = "occupancy review(s)"
    elif fam == "OPERATIONAL":
        noun = "operational item(s)"
    elif fam in ("DECLARATION_BASED", "SELF_CERTIFIED", "STRUCTURED_EVIDENCE"):
        noun = "declaration(s)"
    elif fam in ("LICENSING", "REGISTRATION"):
        noun = "renewal(s)"
    else:
        noun = "compliance item(s)"
    state = "overdue" if overdue else "due soon"
    return f"Pleerity: {{count}} {noun} {state}. View: {{portal_link}}"


def resolve_reminder_subject(
    requirement_row: Dict[str, Any],
    *,
    is_overdue: bool = False,
    days_remaining: int | None = None,
) -> str:
    family = infer_communication_family(requirement_row)
    req_name = requirement_display_name(requirement_row)
    fam = str(family)
    if is_overdue:
        return f"{req_name} is overdue"

    if days_remaining is not None:
        n = int(days_remaining)
        if n <= 0:
            timing = "today"
        elif n == 1:
            timing = "tomorrow"
        else:
            timing = f"in {n} days"
    else:
        timing = "soon"

    if fam in ("REVIEW_BASED", "OCCUPANCY_LIFECYCLE", "OCCUPANCY_REVIEW_DUE"):
        return f"{req_name} is due {timing}"
    if fam in ("TENANCY_LIFECYCLE",):
        return f"{req_name} requires attention"
    if fam in ("OPERATIONAL", "EVENT_BASED"):
        return f"{req_name} requires attention"
    if fam in ("DECLARATION_BASED", "SELF_CERTIFIED", "STRUCTURED_EVIDENCE"):
        return f"{req_name} is due {timing}"
    if fam in ("DOCUMENT_EVIDENCE", "ASSESSMENT", "INSPECTION"):
        return f"{req_name} is due {timing}"
    if fam == "REGISTRATION":
        return f"{req_name} is due {timing}"
    if fam == "LICENSING":
        return f"{req_name} is due {timing}"
    if fam == "EXPIRY_BASED":
        if days_remaining is not None:
            n = int(days_remaining)
            if n <= 0:
                return f"Your {req_name} expires today"
            if n == 1:
                return f"Your {req_name} expires tomorrow"
            return f"Your {req_name} expires in {n} days"
        return f"{req_name} is due soon"
    return f"{req_name} is due {timing}"
