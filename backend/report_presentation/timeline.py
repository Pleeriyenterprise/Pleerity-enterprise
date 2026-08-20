"""Business chronology presentation for audit trails."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from report_presentation.actors import present_actor_label
from report_presentation.constants import (
    COLLAPSIBLE_REGEN_PREFIXES,
    PRIMARY_LAYER_SUPPRESSED_ACTIONS,
    PresentationProfile,
)
from report_presentation.profiles import profile_config
from report_presentation.timestamps import format_customer_timestamp, format_technical_timestamp

_RISK_TYPE_LABELS = {
    "ELECTRICAL": "Electrical safety",
    "ELECTRICAL_RISK": "Electrical safety",
    "GAS": "Gas safety",
    "FIRE": "Fire safety",
    "FIRE_RISK": "Fire safety",
    "MOULD": "Mould and damp",
    "STRUCTURAL": "Structural",
    "LEGIONELLA": "Legionella",
    "ASBESTOS": "Asbestos",
}

_REQUIREMENT_DOC_LABELS = {
    "gas_safety": "Gas Safety Certificate",
    "eicr": "Electrical Installation Condition Report",
    "epc": "Energy Performance Certificate",
    "legionella": "Legionella Risk Assessment",
    "fire_risk": "Fire Risk Assessment",
    "pat_testing": "Portable Appliance Testing",
}


def _md(ev: Dict[str, Any]) -> Dict[str, Any]:
    md = ev.get("metadata")
    return md if isinstance(md, dict) else {}


def _action_code(ev: Dict[str, Any]) -> str:
    return str(ev.get("action") or ev.get("event_type") or "").strip().upper()


def _risk_subject(md: Dict[str, Any]) -> str:
    risk_type = str(md.get("risk_type") or "").strip().upper()
    for key, label in _RISK_TYPE_LABELS.items():
        if key in risk_type or risk_type == key:
            return label
    req = str(md.get("requirement_name") or md.get("requirement_type") or "").strip().lower()
    for key, label in _REQUIREMENT_DOC_LABELS.items():
        if key in req:
            return label
    if risk_type:
        return risk_type.replace("_", " ").title()
    return "compliance"


def _score_delta_phrase(md: Dict[str, Any]) -> str:
    prev = md.get("previous_score")
    new = md.get("new_score")
    if prev is not None and new is not None:
        try:
            p, n = int(prev), int(new)
            if p != n:
                direction = "increased" if n > p else "reduced"
                return f"Compliance score {direction} from {p} to {n}"
        except (TypeError, ValueError):
            pass
    reason = str(md.get("reason") or "").strip()
    if reason:
        return f"Compliance score recalculated ({reason.replace('_', ' ').lower()})"
    return "Compliance score recalculated following a compliance change"


def _business_event_and_summary(ev: Dict[str, Any]) -> Tuple[str, str]:
    """Return (business_event, business_summary) — never duplicate unless no context."""
    action = _action_code(ev)
    md = _md(ev)
    existing_summary = str(md.get("summary") or "").strip()

    if action == "RISK_SIGNAL_CREATED":
        subject = _risk_subject(md)
        event = f"{subject} concern identified"
        level = str(md.get("risk_level") or "").strip().lower()
        summary = f"A new {subject.lower()} concern was recorded"
        if level:
            summary += f" ({level} priority)"
        summary += "."
        return event, summary

    if action == "RISK_SIGNAL_UPDATED":
        subject = _risk_subject(md)
        return (
            f"{subject} concern updated",
            f"The {subject.lower()} concern was updated following a change in property information.",
        )

    if action == "RISK_SIGNAL_RESOLVED":
        subject = _risk_subject(md)
        return (
            f"{subject} concern resolved",
            f"The {subject.lower()} concern was marked resolved after compliance improved.",
        )

    if action == "RISK_SIGNAL_ACKNOWLEDGED":
        subject = _risk_subject(md)
        return (
            f"{subject} concern acknowledged",
            f"The {subject.lower()} concern was reviewed and acknowledged.",
        )

    if action == "RISK_SIGNAL_REGEN_COMPLETED":
        return (
            "Property risk assessment updated",
            "Property risk assessment updated after new compliance information became available.",
        )

    if action == "RISK_SIGNAL_REGEN_STARTED":
        return (
            "Property risk assessment refresh started",
            "Automated risk assessment refresh commenced following a compliance update.",
        )

    if action == "COMPLIANCE_RECALC_SLA_BREACH":
        return (
            "Compliance recalculation delayed",
            "Compliance recalculation exceeded the expected processing time threshold.",
        )

    if action == "COMPLIANCE_RECALC_SLA_RESOLVED":
        return (
            "Compliance recalculation delay resolved",
            "Delayed compliance recalculation completed successfully.",
        )

    if action in ("COMPLIANCE_SCORE_UPDATED", "COMPLIANCE_SCORE_RECALCULATED"):
        event = "Compliance score revised"
        summary = _score_delta_phrase(md)
        req_name = str(md.get("requirement_name") or "").strip()
        if req_name and "following" not in summary.lower():
            summary += f" following a change to {req_name}."
        elif not summary.endswith("."):
            summary += "."
        return event, summary

    if action == "COMPLIANCE_SCORE_DRIFT_DETECTED":
        event = "Compliance score variance detected"
        summary = _score_delta_phrase(md)
        if not summary.endswith("."):
            summary += " during routine monitoring."
        return event, summary

    if action == "COMPLIANCE_GAP_OPENED":
        gap = str(md.get("gap_type") or md.get("requirement_name") or "compliance gap").strip()
        return (
            "New compliance gap identified",
            f"A new compliance gap was recorded: {gap}.",
        )

    if action == "COMPLIANCE_GAP_RESOLVED":
        gap = str(md.get("gap_type") or md.get("requirement_name") or "compliance gap").strip()
        return (
            "Compliance gap resolved",
            f"The compliance gap ({gap}) was resolved.",
        )

    if action == "DOCUMENT_UPLOADED":
        doc = str(md.get("document_name") or md.get("filename") or "compliance document").strip()
        return (
            "Evidence uploaded",
            f"{_professional_doc_label(doc)} uploaded for review.",
        )

    if action == "DOCUMENT_VERIFIED":
        doc = str(md.get("document_name") or md.get("filename") or "compliance document").strip()
        return (
            "Evidence verified",
            f"{_professional_doc_label(doc)} verified and accepted.",
        )

    if action == "DOCUMENT_REJECTED":
        doc = str(md.get("document_name") or md.get("filename") or "document").strip()
        return (
            "Evidence rejected",
            f"{_professional_doc_label(doc)} was rejected — further action may be required.",
        )

    if action == "COMPLIANCE_STATUS_UPDATED":
        req = str(md.get("requirement_name") or "An obligation").strip()
        status = str(md.get("status") or md.get("new_status") or "").strip()
        if status:
            return (
                "Obligation status changed",
                f"{req} status updated to {status.replace('_', ' ').lower()}.",
            )
        return (
            "Obligation status changed",
            f"{req} status was updated.",
        )

    if action == "COMPLIANCE_AUDIT_PACK_GENERATED":
        return (
            "Audit evidence pack generated",
            "A governed audit evidence pack was prepared for external review.",
        )

    if action == "TENANT_DELIVERY_SUCCEEDED":
        return (
            "Tenant compliance pack delivered",
            "Required compliance documents were successfully delivered to the tenant.",
        )

    property_name = str(md.get("property_name") or md.get("property_label") or "").strip()
    job_title = str(md.get("description") or md.get("job_title") or md.get("title") or "").strip()
    contractor_name = str(md.get("contractor_name") or md.get("company_name") or "").strip()
    at_property = f" at {property_name}" if property_name else ""
    job_ref = f"“{job_title[:80]}”" if job_title else "a maintenance job"

    if action in ("WORK_ORDER_CREATED", "WORK_ORDER_CREATED_FROM_RISK_SIGNAL", "COMPLIANCE_EXECUTION_WORK_ORDER_CREATED"):
        return (
            "Maintenance job created",
            f"A job was created for {job_ref}{at_property}.",
        )

    if action == "MAINTENANCE_ISSUE_CREATED":
        return (
            "Maintenance issue recorded",
            f"A maintenance issue was recorded for {job_ref}{at_property}.",
        )

    if action == "CONTRACTOR_ASSIGNED_TO_WORK_ORDER":
        who = contractor_name or "A contractor"
        return (
            "Contractor assigned",
            f"{who} was assigned to {job_ref}{at_property}.",
        )

    if action == "RENT_PAYMENT_RECORDED":
        return (
            "Rent payment recorded",
            f"A rent payment was recorded{at_property}.",
        )

    if action in ("RENT_LEDGER_CREATED", "RENT_LEDGER_UPDATED"):
        return (
            "Rent ledger updated",
            f"The rent ledger was updated{at_property}.",
        )

    if existing_summary and not _looks_like_raw_code(existing_summary):
        titled = existing_summary[:120]
        return titled, _expand_summary(existing_summary, action, md)

    # Fallback: title-case without engineering tone
    words = re.sub(r"[_\-]+", " ", action).strip().lower()
    if not words:
        return "Compliance activity recorded", "A compliance-related activity was recorded."
    event = words.title() if len(words) <= 48 else words[:48].title()
    return event, f"{event} — see supporting detail in this record."


def _looks_like_raw_code(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if t.upper() == t and "_" in t:
        return True
    if t == t.title() and any(
        p in t.lower()
        for p in ("regeneration completed", "recalculated", "drift detected", "signal created")
    ):
        return True
    return False


def _expand_summary(existing: str, action: str, md: Dict[str, Any]) -> str:
    if existing.lower() != action.replace("_", " ").lower() and not _looks_like_raw_code(existing):
        return existing[:200]
    _event, generated = _business_event_and_summary(
        {"action": action, "metadata": md}
    )
    return generated


def _professional_doc_label(name: str) -> str:
    lower = name.lower()
    for key, label in _REQUIREMENT_DOC_LABELS.items():
        if key in lower:
            return label
    if name.lower().endswith((".pdf", ".png", ".jpg")):
        base = name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
        if len(base) > 4:
            return base.title()
    return name[:80] if name else "Compliance document"


def _is_suppressed_from_primary(action: str) -> bool:
    if action in PRIMARY_LAYER_SUPPRESSED_ACTIONS:
        return True
    return any(action.startswith(p) for p in COLLAPSIBLE_REGEN_PREFIXES)


def present_timeline_row(
    ev: Dict[str, Any],
    *,
    profile: PresentationProfile = "evidential",
) -> Dict[str, Any]:
    """Single governed timeline row for primary chronology."""
    md = _md(ev)
    action = _action_code(ev)
    event, summary = _business_event_and_summary(ev)
    cfg = profile_config(profile)
    return {
        "timestamp": format_customer_timestamp(
            ev.get("timestamp"),
            precision=str(cfg.get("timestamp_precision") or "minute"),
        ),
        "business_event": event,
        "actor": present_actor_label(
            ev.get("actor_role") or ev.get("actor"),
            actor_id=ev.get("actor_id"),
            metadata={**md, "action": action},
        ),
        "summary": summary,
        "action_raw": action,
        "resource_id": ev.get("resource_id") or md.get("requirement_id"),
        "event_id": ev.get("event_id") or ev.get("_id") or md.get("correlation_id"),
    }


def present_technical_forensic_row(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Forensic row for technical appendix — preserves original audit detail."""
    md = _md(ev)
    action = _action_code(ev)
    return {
        "technical_timestamp": format_technical_timestamp(ev.get("timestamp")),
        "original_action": action or str(ev.get("action") or ""),
        "actor_id": str(ev.get("actor_id") or "—"),
        "actor_role": str(ev.get("actor_role") or md.get("actor_role") or "—"),
        "resource_id": str(ev.get("resource_id") or "—"),
        "event_id": str(ev.get("event_id") or ev.get("_id") or "—"),
        "metadata_summary": str(md.get("summary") or "—")[:120],
    }


def build_layered_timeline(
    events: List[Dict[str, Any]],
    *,
    report_class: str = "audit_trail",
    profile: Optional[PresentationProfile] = None,
) -> Dict[str, Any]:
    """
    Build primary business chronology + optional technical appendix rows.
    Does not modify input events.
    """
    from report_presentation.profiles import resolve_profile

    prof = resolve_profile(report_class, override=profile)
    cfg = profile_config(prof)
    max_rows = int(cfg.get("max_timeline_rows") or 60)

    primary: List[Dict[str, Any]] = []
    technical: List[Dict[str, Any]] = []
    suppressed_count = 0

    for ev in events:
        action = _action_code(ev)
        technical.append(present_technical_forensic_row(ev))
        if _is_suppressed_from_primary(action):
            suppressed_count += 1
            continue
        primary.append(present_timeline_row(ev, profile=prof))

    omitted = max(0, len(primary) - max_rows)
    shown_primary = primary[:max_rows]

    return {
        "profile": prof,
        "primary_rows": shown_primary,
        "technical_rows": technical,
        "primary_total": len(primary),
        "primary_shown": len(shown_primary),
        "primary_omitted": omitted,
        "suppressed_from_primary": suppressed_count,
        "include_technical_appendix": bool(cfg.get("include_technical_appendix")),
        "section_intro": (
            "Chronological record of compliance-related activity affecting this property or portfolio. "
            "Events describe business impact; forensic audit codes are listed in the technical appendix "
            "where provided."
        ),
    }


def humanize_audit_event_action(action: Optional[str]) -> str:
    """Backward-compatible business event label for legacy callers."""
    ev = {"action": action, "metadata": {}}
    event, _ = _business_event_and_summary(ev)
    return event
