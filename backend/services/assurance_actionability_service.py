"""
Assurance vs operational actionability — global classification for Today, score cards, and quick actions.

Operational surfaces must not present assurance-confidence gaps as urgent landlord actions when
obligations are already satisfied on file. Scoring may still reflect assurance penalties.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_scoring_v2 import STATUS_ASSURANCE_PENDING, STATUS_SATISFIED_UNVERIFIED

OPERATIONAL_ACTION = "OPERATIONAL_ACTION"
ASSURANCE_CONFIDENCE_OPPORTUNITY = "ASSURANCE_CONFIDENCE_OPPORTUNITY"
INTERNAL_REVIEW_ITEM = "INTERNAL_REVIEW_ITEM"
INFORMATIONAL = "INFORMATIONAL"
STALE_INVALID = "STALE_INVALID"

_ASSURANCE_ACTION_PATTERNS = (
    "self-recorded",
    "awaiting verification",
    "awaiting platform verification",
    "awaiting assurance",
    "assurance confidence",
    "platform verification",
)


def _action_text(action: Dict[str, Any]) -> str:
    return str(action.get("action") or action.get("recommended_action_detail") or "").lower()


def _text_suggests_assurance(action_text: str) -> bool:
    t = (action_text or "").lower()
    return any(p in t for p in _ASSURANCE_ACTION_PATTERNS) or "review compliance evidence" in t


def requirement_has_assurance_confidence_gap(requirement: Dict[str, Any]) -> bool:
    """True when obligation is satisfied but score/assurance confidence can still improve."""
    from services.requirement_satisfaction_service import is_requirement_satisfied

    row = dict(requirement or {})
    if not is_requirement_satisfied(row):
        return False
    life = str(row.get("client_lifecycle_state") or "").upper()
    if life in ("SATISFIED_UNVERIFIED", "PENDING_REVIEW"):
        return True
    tier = str(row.get("assurance_tier") or "").upper()
    if tier in ("SELF_RECORDED", "ASSURANCE_PENDING"):
        return True
    stage = str(row.get("truth_presentation_stage") or "").lower()
    if stage in ("recorded_on_file", "declaration_recorded", "evidence_recorded", "assessment_recorded"):
        if tier != "VERIFIED" and life != "VERIFIED":
            return True
    return False


def classify_score_action(
    action: Dict[str, Any],
    requirement: Optional[Dict[str, Any]],
) -> str:
    """Classify a persisted score recommendation / top_next_action."""
    from services.requirement_truth import requirement_has_active_negative_actionability

    if requirement:
        if requirement_has_active_negative_actionability(requirement):
            return OPERATIONAL_ACTION
        if requirement_has_assurance_confidence_gap(requirement):
            return ASSURANCE_CONFIDENCE_OPPORTUNITY
        return STALE_INVALID
    if _text_suggests_assurance(_action_text(action)):
        return STALE_INVALID
    return STALE_INVALID


def format_client_score_recommendation(
    action: Dict[str, Any],
    requirement: Optional[Dict[str, Any]],
    action_kind: str,
) -> Dict[str, Any]:
    """Normalize recommendation payload for client surfaces."""
    code = action.get("requirement_code") or ""
    pid = str(action.get("property_id") or "")
    rid = str(action.get("requirement_id") or (requirement or {}).get("requirement_id") or "")
    display = action.get("display_label")
    if not display and code:
        from presentation.label_service import requirement_label

        display = requirement_label(code, audience="client")
    raw_action = action.get("action") or f"Improve {display or code or 'compliance evidence'}"
    if action_kind == ASSURANCE_CONFIDENCE_OPPORTUNITY:
        priority = "info"
        if requirement:
            lbl = display or code or "this requirement"
            if "self-recorded" in raw_action.lower() or "awaiting verification" in raw_action.lower():
                action_text = (
                    f"Optional: improve assurance confidence for {lbl} "
                    "(evidence is recorded; platform verification can raise your score)."
                )
            else:
                action_text = (
                    f"Optional: review assurance confidence for {lbl} "
                    "(your obligation is recorded on file)."
                )
        else:
            action_text = raw_action
    else:
        priority = action.get("priority") or "medium"
        if str(priority).lower() in ("high", "critical") and action_kind == OPERATIONAL_ACTION:
            priority = priority
        action_text = raw_action
    return {
        "priority": priority,
        "action": action_text,
        "impact": f"+{int(round(float(action.get('impact_points') or 0)))} points",
        "requirement_code": code or None,
        "display_label": display,
        "property_id": pid or None,
        "requirement_id": rid or None,
        "action_kind": action_kind,
    }


def partition_score_recommendations(
    aggregated_actions: List[Dict[str, Any]],
    req_by_id: Dict[tuple, Dict[str, Any]],
    req_by_code: Dict[tuple, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split persisted score actions into operational recommendations and assurance opportunities."""
    operational: List[Dict[str, Any]] = []
    assurance: List[Dict[str, Any]] = []
    for action in aggregated_actions:
        code = action.get("requirement_code") or ""
        pid = str(action.get("property_id") or "")
        rid = str(action.get("requirement_id") or "")
        match = req_by_id.get((pid, rid)) if rid else None
        if match is None and code:
            match = req_by_code.get((pid, str(code).strip().lower()))
        kind = classify_score_action(action, match)
        if kind == STALE_INVALID:
            continue
        rec = format_client_score_recommendation(action, match, kind)
        if kind == OPERATIONAL_ACTION:
            operational.append(rec)
        elif kind == ASSURANCE_CONFIDENCE_OPPORTUNITY:
            assurance.append(rec)
    return operational[:5], assurance[:5]


def requirement_skeleton_from_task_metadata(
    task: Dict[str, Any],
) -> Dict[str, Any]:
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    st = str(task.get("source_type") or "").lower()
    rid = meta.get("requirement_id") or meta.get("linked_property_requirement_id")
    if not rid and st == "requirement":
        rid = task.get("source_entity_id")
    return {
        "requirement_id": rid,
        "property_id": task.get("property_id"),
        "truth_presentation_stage": meta.get("truth_presentation_stage"),
        "semantic_state": meta.get("semantic_state"),
        "take_action": meta.get("take_action"),
        "status": meta.get("legacy_status") or meta.get("status"),
        "evidence_authority": meta.get("evidence_authority"),
        "client_lifecycle_state": meta.get("client_lifecycle_state"),
        "assurance_tier": meta.get("assurance_tier"),
        "requirement_satisfied": meta.get("requirement_satisfied"),
        "client_surface_visible": meta.get("client_surface_visible"),
    }


def task_is_assurance_only_inbox_item(task: Dict[str, Any]) -> bool:
    """
    True when a Today/inbox task should not appear as landlord operational urgency.
    """
    from services.requirement_attention_eligibility_service import is_requirement_attention_eligible
    from services.requirement_truth import requirement_has_active_negative_actionability

    st = str(task.get("source_type") or "").lower()
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    skeleton = requirement_skeleton_from_task_metadata(task)

    if st == "requirement":
        eligible, _, _ = is_requirement_attention_eligible(skeleton)
        return not eligible

    rid = skeleton.get("requirement_id")
    if rid:
        if requirement_has_active_negative_actionability(skeleton):
            return False
        if requirement_has_assurance_confidence_gap(skeleton):
            return True
        eligible, _, _ = is_requirement_attention_eligible(skeleton)
        if not eligible:
            return True

    if st in ("issue", "priority_action"):
        trigger = str(meta.get("issue_triggering_rule") or meta.get("triggering_rule") or "").upper()
        if trigger in (
            "MISMATCHED_EVIDENCE",
            "RECONCILIATION_PENDING",
            "AUTHORITY_UNSYNCED",
            "EVIDENCE_UPLOADED_UNCONFIRMED",
        ):
            if rid and requirement_has_assurance_confidence_gap(skeleton):
                return True
            if rid and not requirement_has_active_negative_actionability(skeleton):
                return True
        if _text_suggests_assurance(str(task.get("title") or "") + " " + str(task.get("description") or "")):
            if rid and not requirement_has_active_negative_actionability(skeleton):
                return True
    return False


def build_score_confidence_explanation(
    *,
    score: Optional[float],
    semantic_counts: Dict[str, int],
) -> Dict[str, Any]:
    """Client copy explaining sub-100 scores driven by assurance confidence."""
    from services.reporting_semantics_v1 import (
        METRIC_SCORE_TRACKED,
        METRIC_TRACKED,
        METRIC_SELF_RECORDED,
        METRIC_VERIFIED,
    )

    tracked = int(semantic_counts.get(METRIC_TRACKED) or 0)
    score_tracked = int(semantic_counts.get(METRIC_SCORE_TRACKED) or 0)
    self_recorded = int(semantic_counts.get(METRIC_SELF_RECORDED) or 0)
    verified = int(semantic_counts.get(METRIC_VERIFIED) or 0)
    score_val = float(score) if score is not None else None
    below_100 = score_val is not None and score_val < 100
    obligations_met = tracked > 0 and self_recorded >= 0 and (tracked - verified) <= self_recorded + 2

    headline = "Your requirements are satisfied." if obligations_met and below_100 else None
    detail = None
    achievability = "100/100 is achievable when evidence is platform-verified where verification applies."
    if below_100 and self_recorded > 0:
        detail = (
            "Your score is below 100 because some evidence is self-recorded or awaiting assurance review. "
            "This reflects assurance confidence, not an active compliance breach."
        )
    elif below_100:
        detail = (
            "Your score is below 100 due to assurance-confidence weighting on tracked obligations. "
            "Completing verification where available can improve your score."
        )

    return {
        "score": score_val,
        "headline": headline,
        "detail": detail,
        "achievability_note": achievability,
        "tracked_requirement_count": tracked,
        "score_tracked_requirement_count": score_tracked,
        "self_recorded_count": self_recorded,
        "verified_requirement_count": verified,
        "obligations_satisfied_on_file": obligations_met,
        "assurance_explains_sub_100": bool(below_100 and (self_recorded > 0 or obligations_met)),
    }
