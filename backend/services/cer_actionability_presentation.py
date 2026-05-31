"""
CER actionability presentation — Phase 1.1 safe repairs (CTA specificity, guidance, modal copy).

Reuses governance truth from cer_governance_presentation; does not alter authority or scoring.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.requirement_code_registry import normalize_requirement_code

_GENERIC_GUIDED = "Add compliance evidence"

_FIRE_RISK_CODES = frozenset(
    {
        "fire_risk_assessment",
        "hmo_fire_risk",
        "hmo_fire_risk_evidence",
    }
)


def _canon(requirement: Dict[str, Any]) -> str:
    raw = str(requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip()
    return normalize_requirement_code(raw) or raw.lower().replace(" ", "_")


def _truth_stage(requirement: Dict[str, Any]) -> str:
    return str(requirement.get("truth_presentation_stage") or "").strip()


def _missing_components(requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
    comp = requirement.get("evidence_completeness") if isinstance(requirement.get("evidence_completeness"), dict) else {}
    raw = comp.get("missing_components") or []
    return [m for m in raw if isinstance(m, dict)]


def component_guidance_lines(requirement: Dict[str, Any]) -> List[str]:
    """Specific missing-item lines for guidance panels and cognition."""
    lines: List[str] = []
    stage = _truth_stage(requirement)
    canon = _canon(requirement)
    comp = requirement.get("evidence_completeness") if isinstance(requirement.get("evidence_completeness"), dict) else {}

    for m in _missing_components(requirement):
        label = str(m.get("label") or "").strip()
        key = str(m.get("key") or "").strip()
        if label:
            lines.append(f"{label} still required")
        elif key == "co_alarm":
            lines.append("Carbon monoxide alarm evidence still required")
        elif key == "smoke_alarm":
            lines.append("Smoke alarm evidence still required")

    summary = str(comp.get("summary_label") or "").strip()
    if summary and summary.lower() not in ("complete", "") and not lines:
        if "smoke" in summary.lower():
            lines.append("Smoke alarm location or test details still required")
        elif "co" in summary.lower():
            lines.append("CO alarm evidence still required")
        else:
            lines.append(summary)

    if stage == "followup_required":
        if canon == "legionella":
            lines.append("Risk mitigation actions still required for the Legionella assessment")
        elif canon == "lead_testing":
            lines.append("Follow-up actions for the lead assessment still required")
        elif canon in _FIRE_RISK_CODES:
            lines.append("Additional fire-risk actions still need to be completed")
        elif not lines:
            lines.append("Supporting evidence for the assessment is still required")

    if stage == "supporting_upload_only":
        lines.append("Complete the structured record — supporting files alone do not satisfy this obligation")

    if stage == "operational_incomplete" and canon in _FIRE_RISK_CODES and not lines:
        lines.append("Additional fire-risk evidence components still need to be completed")

    return list(dict.fromkeys(lines))


def resolve_actionability_primary_cta_label(
    requirement: Dict[str, Any],
    *,
    fallback: Optional[str] = None,
) -> Optional[str]:
    """
    Return a specific primary CTA when truth/completeness signals allow; else None (caller uses fallback).
    Takes precedence over generic guided labels when incomplete or follow-up is known.
    """
    stage = _truth_stage(requirement)
    canon = _canon(requirement)
    fb = str(fallback or _GENERIC_GUIDED).strip()

    if stage == "supporting_upload_only":
        return "Upload supporting evidence"

    missing = _missing_components(requirement)
    comp = requirement.get("evidence_completeness") if isinstance(requirement.get("evidence_completeness"), dict) else {}

    if stage == "operational_incomplete" or (comp.get("is_complete") is False and comp.get("evaluated")):
        if canon in _FIRE_RISK_CODES and stage == "operational_incomplete":
            return "Add missing fire-risk actions"
        if missing:
            key = str(missing[0].get("key") or "").strip()
            if key == "co_alarm":
                return "Complete CO alarm details"
            if key == "smoke_alarm":
                return "Complete smoke alarm details"
        summary = str(comp.get("summary_label") or "").lower()
        if "co alarm" in summary or "co_alarm" in summary:
            return "Complete CO alarm details"
        if "smoke" in summary:
            return "Complete smoke alarm details"
        if canon in _FIRE_RISK_CODES:
            return "Add missing fire-risk actions"
        if stage == "operational_incomplete":
            return "Complete missing evidence components"

    if stage == "followup_required":
        if canon == "legionella":
            return "Update Legionella assessment"
        if canon == "lead_testing":
            return "Update lead assessment"
        if canon in _FIRE_RISK_CODES:
            return "Add missing fire-risk actions"
        return "Complete follow-up evidence"

    if stage == "action_required" and canon == "smoke_heat_alarms":
        return "Complete smoke alarm details"

    return None if fb == _GENERIC_GUIDED else None


def resolve_existing_submission_banner_copy(requirement: Dict[str, Any]) -> Optional[str]:
    """
    Modal banner when an authoritative submission already exists.
    Queue-backed review wording only when a real review owner/queue exists.
    """
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    has_sub = bool(
        str(ea.get("primary_evidence_record_id") or requirement.get("evidence_record_id") or "").strip()
        or requirement.get("evidence_doc_id")
        or str(requirement.get("document_id") or "").strip()
    )
    if not has_sub:
        return None

    queue_backed = requirement.get("queue_backed_review") is True
    review_owner = str(requirement.get("review_owner") or "").strip()
    stage = _truth_stage(requirement)

    if queue_backed and review_owner:
        if review_owner == "platform_admin":
            return "Submission on file — platform verification in progress."
        if review_owner == "org_admin":
            return "Submission on file — organisation review in progress."
        if review_owner == "platform_admin_escalation":
            return "Submission on file — escalated for platform review."
        return "Submission on file — awaiting review."

    if stage == "followup_required":
        return "Assessment on file — additional follow-up information is still required. You can update your submission below."
    if stage == "operational_incomplete":
        return "Submission on file — additional information is still required. You can update your submission below."
    if stage == "supporting_upload_only":
        return "Supporting evidence has already been uploaded. Complete the structured record below."
    return "Submission on file. You can update your submission below."


def build_reopen_prefill_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured pre-fill payload from an existing CER for follow-up reopen."""
    if not isinstance(record, dict):
        return {}
    mode = str(record.get("evidence_mode") or "").strip().upper()
    payload = record.get("evidence_payload") if isinstance(record.get("evidence_payload"), dict) else {}
    out: Dict[str, Any] = {
        "evidence_mode": mode,
        "evidence_record_id": record.get("evidence_record_id"),
        "declaration_statement": payload.get("declaration_statement") or "",
    }
    if mode == "STRUCTURED_DECLARATION":
        fields = payload.get("structured_fields") if isinstance(payload.get("structured_fields"), dict) else {}
        prefill: Dict[str, Any] = {}
        for key, val in fields.items():
            if not isinstance(val, dict):
                continue
            prefill[key] = {
                "answer": val.get("answer"),
                "notes": val.get("notes"),
                "observation": val.get("observation"),
            }
        out["structured_fields_prefill"] = prefill
    elif mode == "INSPECTION_CHECKLIST":
        answers = payload.get("checklist_answers") if isinstance(payload.get("checklist_answers"), dict) else {}
        prefill = {}
        for key, val in answers.items():
            if isinstance(val, dict):
                prefill[key] = dict(val)
        out["checklist_answers_prefill"] = prefill
    return out
