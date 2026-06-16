"""
CER actionability presentation — Phase 1.1 safe repairs (CTA specificity, guidance, modal copy).

Reuses governance truth from cer_governance_presentation; does not alter authority or scoring.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.requirement_code_registry import normalize_requirement_code

_GENERIC_GUIDED = "Add compliance evidence"

_GENERIC_FALLBACK_LABELS = frozenset(
    {
        _GENERIC_GUIDED,
        "Complete inspection checklist",
        "Add contractor confirmation",
        "Submit compliance declaration",
        "Complete follow-up evidence",
        "Complete missing evidence components",
    }
)

_DOMESTIC_ALARM_CANON = frozenset({"smoke_heat_alarms", "fire_alarm", "fire_detection", "smoke_alarms", "co_alarms"})

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


def _is_domestic_alarm_canon(canon: str) -> bool:
    return canon in _DOMESTIC_ALARM_CANON or normalize_requirement_code(canon) == "smoke_heat_alarms"


def _resolve_missing_component_cta(
    missing: List[Dict[str, Any]],
    *,
    comp: Dict[str, Any],
    canon: str,
    stage: str,
) -> Optional[str]:
    """Component-aware CTA from missing_components keys/labels and completeness summary."""
    if not missing:
        summary = str(comp.get("summary_label") or "").lower()
        if "co alarm" in summary or "co_alarm" in summary:
            return "Complete CO alarm details"
        if "smoke" in summary:
            return "Complete smoke alarm details"
        if stage == "operational_incomplete" and _is_domestic_alarm_canon(canon):
            return "Complete smoke alarm details"
        return None

    first = missing[0] if isinstance(missing[0], dict) else {}
    key = str(first.get("key") or "").strip().lower()
    label = str(first.get("label") or "").strip().lower()

    if key == "smoke_alarm" or ("smoke" in label and "alarm" in label):
        if any(t in label for t in ("location", "test", "detail")):
            return "Complete smoke alarm details"
        if any(t in label for t in ("count", "installation", "installed")):
            return "Complete alarm installation details"
        return "Complete smoke alarm details"
    if key == "co_alarm" or "carbon monoxide" in label:
        return "Complete CO alarm details"
    if any(t in label for t in ("remediation", "action", "mitigation")) or key in ("remediation", "follow_up_actions"):
        if canon in _FIRE_RISK_CODES:
            return "Add missing fire-risk actions"
        return "Complete follow-up evidence"
    if key and _is_domestic_alarm_canon(canon):
        return "Add missing smoke alarm information"
    return None


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

    if stage == "supporting_upload_only":
        return "Upload supporting evidence"

    missing = _missing_components(requirement)
    comp = requirement.get("evidence_completeness") if isinstance(requirement.get("evidence_completeness"), dict) else {}

    if stage == "operational_incomplete" or (comp.get("is_complete") is False and comp.get("evaluated")):
        if canon in _FIRE_RISK_CODES and stage == "operational_incomplete":
            return "Add missing fire-risk actions"
        component_cta = _resolve_missing_component_cta(missing, comp=comp, canon=canon, stage=stage)
        if component_cta:
            return component_cta
        if canon in _FIRE_RISK_CODES:
            return "Add missing fire-risk actions"
        if stage == "operational_incomplete" and _is_domestic_alarm_canon(canon):
            return "Complete fire alarm compliance details"
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

    if stage == "action_required" and _is_domestic_alarm_canon(canon):
        return "Complete smoke alarm details"

    return None


def apply_actionability_cta_override(requirement: Dict[str, Any]) -> bool:
    """
    Re-apply specific primary CTA after governance/completeness enrichment.

    take_action is resolved earlier in enrich_requirement_dict before truth_presentation_stage
    and evidence_completeness exist; this restores component-specific labels for client surfaces.
    """
    specific = resolve_actionability_primary_cta_label(requirement)
    if not specific:
        return False
    ta = requirement.get("take_action")
    if not isinstance(ta, dict):
        return False
    pri = ta.get("primary")
    if not isinstance(pri, dict):
        return False
    current = str(pri.get("label") or "").strip()
    if current == specific:
        return False

    stage = _truth_stage(requirement)
    missing = _missing_components(requirement)
    has_operational_specificity = bool(missing) or stage in (
        "operational_incomplete",
        "followup_required",
        "supporting_upload_only",
    )
    if not has_operational_specificity:
        return False

    # Component-specific and follow-up CTAs always beat generic guided fallback.
    if missing or stage in ("operational_incomplete", "followup_required", "supporting_upload_only"):
        pri["label"] = specific
        return True
    if current in _GENERIC_FALLBACK_LABELS:
        pri["label"] = specific
        return True
    return False


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

    try:
        from services.customer_status_projector_config import is_customer_status_projector_active

        if is_customer_status_projector_active():
            subline = str(requirement.get("customer_status_subline") or "").strip()
            key = str(requirement.get("customer_status_key") or "").strip()
            if key == "under_review" and subline:
                return f"Submission on file — {subline}"
            if key == "escalation_required" and subline:
                return f"Submission on file — {subline}"
            if key == "followup_required":
                return (
                    "Assessment on file — additional follow-up information is still required. "
                    "You can update your submission below."
                )
            if key == "additional_action_required":
                return (
                    "Submission on file — additional information is still required. "
                    "You can update your submission below."
                )
            if subline:
                return f"Submission on file. {subline}"
            return "Submission on file. You can update your submission below."
    except Exception:
        pass

    queue_backed = requirement.get("queue_backed_review") is True
    review_owner = str(requirement.get("review_owner") or "").strip()
    stage = _truth_stage(requirement)

    if queue_backed and review_owner == "platform_admin":
        return "Submission on file — our team is verifying your uploaded certificate."
    if queue_backed and review_owner == "platform_admin_escalation":
        return "Submission on file — flagged for Pleerity investigation."

    if stage == "followup_required":
        return "Assessment on file — additional follow-up information is still required. You can update your submission below."
    if stage == "operational_incomplete":
        return "Submission on file — additional information is still required. You can update your submission below."
    if stage == "supporting_upload_only":
        return "Supporting evidence has already been uploaded. Complete the structured record below."
    return "Submission on file. You can update your submission below."


def build_reopen_prefill_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured pre-fill payload from an existing CER for modal reopen."""
    if not isinstance(record, dict):
        return {}

    def _structured_field_entry(val: Any) -> Dict[str, Any]:
        if isinstance(val, dict):
            return {
                "answer": val.get("answer"),
                "notes": val.get("notes"),
                "observation": val.get("observation"),
            }
        return {"answer": val, "notes": None, "observation": None}

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
            prefill[key] = _structured_field_entry(val)
        out["structured_fields_prefill"] = prefill
    elif mode == "INSPECTION_CHECKLIST":
        answers = payload.get("checklist_answers") if isinstance(payload.get("checklist_answers"), dict) else {}
        prefill = {}
        for key, val in answers.items():
            if isinstance(val, dict):
                prefill[key] = dict(val)
            else:
                prefill[key] = {"answer": val}
        out["checklist_answers_prefill"] = prefill
        if payload.get("inspection_date"):
            out["inspection_date"] = payload.get("inspection_date")
        if payload.get("responsible_person"):
            out["responsible_person"] = payload.get("responsible_person")
        if payload.get("optional_notes"):
            out["optional_notes"] = payload.get("optional_notes")
    elif mode == "CONTRACTOR_CONFIRMATION":
        out["contractor_confirmation_prefill"] = {
            key: payload.get(key)
            for key in (
                "contractor_name",
                "company_name",
                "completion_date",
                "work_summary",
                "contractor_email",
                "contractor_phone",
                "trade_type",
                "accreditation_number",
            )
            if payload.get(key) is not None
        }
    return out


def build_reopen_context_for_requirement(
    requirement: Dict[str, Any],
    *,
    evidence_record: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Build guided-evidence modal prefill from the primary CER.

    Used for follow-up reopen and voluntary updates/renewals when a prior
    structured submission exists on file.
    """
    if not isinstance(evidence_record, dict) or not str(evidence_record.get("evidence_record_id") or "").strip():
        return None
    out = build_reopen_prefill_from_record(evidence_record)
    if not str(out.get("evidence_mode") or "").strip():
        return None
    stage = str(requirement.get("truth_presentation_stage") or "").strip()
    if stage:
        out["truth_presentation_stage"] = stage
    if stage in ("followup_required", "operational_incomplete"):
        out["reopen_reason"] = "follow_up_update"
    else:
        out["reopen_reason"] = "prior_submission_update"
    return out
