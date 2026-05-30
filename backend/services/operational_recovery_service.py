"""Phase 2A operational recovery engine — detect, explain, recommend; no authority mutations."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from database import database

from services.recovery_constants import (
    ABANDONMENT_MIN_NUDGES,
    ABANDONMENT_RISK_HOURS,
    CONTRACTOR_NON_RESPONSE_HOURS,
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
from services.recovery_guardrails import (
    assert_recovery_guidance_safe,
    filter_authority_safe_actions,
    is_authority_safe_recovery_action,
)
from services.recovery_guidance_language_service import (
    build_recovery_explanation,
    build_recovery_summary,
    build_recommended_next_steps,
    build_risk_statement,
)
from services.recovery_intelligence_service import enrich_recovery_intelligence
from services.workflow_stall_priority_service import CONTINUATION_CTA
from services.workflow_timer_constants import (
    CTR_ACTIVATION_PENDING_SINCE,
    DOC_AWAITING_EVIDENCE_REVIEW_SINCE,
    REQ_OVERDUE_SINCE,
    TENANT_ACTIVATION_PENDING_SINCE,
)
from services.workflow_timer_service import work_order_stall_context

logger = logging.getLogger(__name__)

_TERMINAL_WO = frozenset({"CANCELLED", "COMPLETED", "VERIFIED", "CLOSED"})
_OVERDUE_REQ = frozenset({"OVERDUE", "EXPIRED"})

_STALL_TO_RECOVERY = {
    "awaiting_contractor_quote": RECOVERY_WAITING_ON_CONTRACTOR_ACTION,
    "awaiting_contractor_quote_revision": RECOVERY_WAITING_ON_CONTRACTOR_ACTION,
    "awaiting_landlord_quote_response": RECOVERY_WAITING_ON_LANDLORD_APPROVAL,
    "awaiting_visit_confirmation": RECOVERY_WAITING_ON_CONTRACTOR_ACTION,
    "awaiting_visit_reschedule": RECOVERY_WAITING_ON_CONTRACTOR_ACTION,
    "completion_proof_pending": RECOVERY_WAITING_ON_CONTRACTOR_ACTION,
    "awaiting_completion_review": RECOVERY_WAITING_ON_LANDLORD_APPROVAL,
    "invoice_pending": RECOVERY_WAITING_ON_CONTRACTOR_ACTION,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now().isoformat()


def _quote_revision_count(wo: Dict[str, Any]) -> int:
    history = wo.get("quote_negotiation_history") or []
    rev = sum(1 for e in history if (e.get("event") or "").lower() in ("revision_requested", "quote_rejected"))
    if rev:
        return rev
    if wo.get("quote_revision_requested_at"):
        return 1
    return 0


def _severity(age_hours: Optional[float], repetition_count: int, recovery_type: str) -> str:
    if recovery_type in (RECOVERY_OPERATIONAL_DEAD_END, RECOVERY_WORK_ORDER_ABANDONMENT_RISK):
        return "high"
    if repetition_count >= 3 or (age_hours or 0) >= 72:
        return "high"
    if repetition_count >= 2 or (age_hours or 0) >= 24:
        return "medium"
    return "low"


def classify_recovery_state(
    entity_type: str,
    entity: Dict[str, Any],
    *,
    stall: Optional[Dict[str, Any]] = None,
    nudge_count: int = 0,
    evidence_rejection_count: int = 0,
) -> Optional[str]:
    """Deterministic recovery category for a single entity."""
    if entity_type == "work_order":
        wo = entity
        st = (wo.get("status") or "").upper()
        if st in _TERMINAL_WO:
            return None
        stall = stall or work_order_stall_context(wo)
        if not stall:
            if not wo.get("contractor_id"):
                return RECOVERY_WORKFLOW_STATE_DRIFT
            return None
        age = stall.get("age_hours") or 0
        stype = stall.get("stall_type") or ""
        waiting = stall.get("waiting_on") or "landlord"
        reschedule_count = int(wo.get("reschedule_count") or 0)
        rev_count = _quote_revision_count(wo)

        if age >= ABANDONMENT_RISK_HOURS and nudge_count >= ABANDONMENT_MIN_NUDGES:
            return RECOVERY_WORK_ORDER_ABANDONMENT_RISK
        if stype == "awaiting_contractor_quote" and age >= CONTRACTOR_NON_RESPONSE_HOURS:
            ctr_status = (wo.get("contractor_status") or "").lower()
            if ctr_status not in ("suspended", "archived"):
                return RECOVERY_CONTRACTOR_NON_RESPONSE
        if rev_count > 2 and stype in ("awaiting_contractor_quote_revision", "awaiting_landlord_quote_response"):
            return RECOVERY_QUOTE_NEGOTIATION_LOOP
        if reschedule_count > 2 or (stype == "awaiting_visit_reschedule" and reschedule_count >= 2):
            return RECOVERY_VISIT_RESCHEDULE_LOOP

        cta = CONTINUATION_CTA.get(stype, {})
        has_cta = bool(cta.get(waiting) or cta.get("landlord") or cta.get("contractor"))
        if not has_cta and age >= 24:
            return RECOVERY_OPERATIONAL_DEAD_END

        if stype == "awaiting_landlord_quote_response":
            return RECOVERY_WAITING_ON_LANDLORD_APPROVAL
        if waiting == "contractor":
            return RECOVERY_WAITING_ON_CONTRACTOR_ACTION
        return _STALL_TO_RECOVERY.get(stype, RECOVERY_WAITING_ON_LANDLORD_APPROVAL)

    if entity_type == "contractor":
        if entity.get(CTR_ACTIVATION_PENDING_SINCE):
            return RECOVERY_CONTRACTOR_ACTIVATION_STALL
        return None

    if entity_type == "tenant":
        if entity.get(TENANT_ACTIVATION_PENDING_SINCE):
            return RECOVERY_TENANT_ACTIVATION_STALL
        return None

    if entity_type == "requirement":
        status = (entity.get("status") or "").upper()
        if status in _OVERDUE_REQ:
            if evidence_rejection_count >= 2:
                return RECOVERY_EVIDENCE_REJECTION_LOOP
            return RECOVERY_OVERDUE_REQUIREMENT_STALL
        if evidence_rejection_count >= 2:
            return RECOVERY_EVIDENCE_REJECTION_LOOP
        return None

    if entity_type == "document":
        review = (entity.get("evidence_review_state") or "").upper()
        if review in ("PENDING_REVIEW", "NEEDS_REVIEW", ""):
            if entity.get(DOC_AWAITING_EVIDENCE_REVIEW_SINCE):
                return RECOVERY_WAITING_ON_EVIDENCE_REVIEW
        if review == "REJECTED" and evidence_rejection_count >= 2:
            return RECOVERY_EVIDENCE_REJECTION_LOOP
        return None

    return None


def derive_recovery_risk(recovery_type: str, *, age_hours: Optional[float], repetition_count: int) -> str:
    return build_risk_statement(recovery_type, age_hours=age_hours, repetition_count=repetition_count)


def generate_recovery_actions(
    recovery_type: str,
    *,
    waiting_on_party: Optional[str],
    entity_type: str,
    entity_id: str,
) -> List[Dict[str, Any]]:
    party = (waiting_on_party or "").lower()
    actions: List[Dict[str, Any]] = []
    mapping: Dict[str, List[tuple[str, str]]] = {
        RECOVERY_CONTRACTOR_NON_RESPONSE: [
            ("review_contractor", "Review contractor"),
            ("add_alternate_contractor", "Add alternate contractor"),
            ("open_job", "Open job"),
            ("contact_support", "Contact support"),
        ],
        RECOVERY_QUOTE_NEGOTIATION_LOOP: [
            ("review_quote", "Review quote"),
            ("open_job", "Open job"),
            ("contact_support", "Contact support"),
        ],
        RECOVERY_VISIT_RESCHEDULE_LOOP: [
            ("request_another_date", "Request another date"),
            ("confirm_proposed_visit", "Confirm proposed visit"),
            ("open_job", "Open job"),
        ],
        RECOVERY_EVIDENCE_REJECTION_LOOP: [
            ("review_rejected_evidence", "Review rejected evidence"),
            ("upload_clearer_document", "Upload clearer document"),
            ("open_requirement", "Open requirement"),
        ],
        RECOVERY_WORK_ORDER_ABANDONMENT_RISK: [
            ("review_stalled_jobs", "Review stalled jobs"),
            ("open_job", "Open job"),
            ("contact_support", "Contact support"),
        ],
        RECOVERY_WAITING_ON_LANDLORD_APPROVAL: [
            ("review_quote", "Review quote"),
            ("open_job", "Open job"),
        ],
        RECOVERY_WAITING_ON_CONTRACTOR_ACTION: [
            ("open_job", "Open job"),
            ("submit_quote", "Submit quote"),
            ("submit_revised_quote", "Submit revised quote"),
            ("propose_visit", "Propose visit"),
        ],
        RECOVERY_WAITING_ON_EVIDENCE_REVIEW: [
            ("review_uploaded_evidence", "Review uploaded evidence"),
            ("open_requirement", "Open requirement"),
        ],
        RECOVERY_TENANT_ACTIVATION_STALL: [
            ("resend_invite", "Resend invite"),
            ("contact_support", "Contact support"),
        ],
        RECOVERY_CONTRACTOR_ACTIVATION_STALL: [
            ("resend_invite", "Resend invite"),
            ("review_contractor", "Review contractor"),
        ],
        RECOVERY_OVERDUE_REQUIREMENT_STALL: [
            ("open_requirement", "Open requirement"),
            ("continue_requirement_resolution", "Continue requirement resolution"),
        ],
        RECOVERY_OPERATIONAL_DEAD_END: [
            ("open_job", "Open job"),
            ("contact_support", "Contact support"),
        ],
        RECOVERY_WORKFLOW_STATE_DRIFT: [
            ("open_job", "Open job"),
            ("review_stalled_jobs", "Review stalled jobs"),
        ],
    }
    for aid, label in mapping.get(recovery_type, [("contact_support", "Contact support")]):
        if is_authority_safe_recovery_action(aid):
            url = f"/operations/work-orders/{entity_id}" if entity_type == "work_order" else None
            if entity_type == "requirement":
                url = f"/compliance/requirements/{entity_id}"
            actions.append({"action_id": aid, "label": label, "url": url, "preparatory": True})
    if party == "contractor" and recovery_type == RECOVERY_WAITING_ON_CONTRACTOR_ACTION:
        actions = [a for a in actions if a["action_id"] in ("submit_quote", "submit_revised_quote", "propose_visit", "open_job")]
    return filter_authority_safe_actions(actions)


def generate_recovery_guidance(
    recovery_type: str,
    *,
    waiting_on_party: Optional[str],
    age_hours: Optional[float],
    repetition_count: int = 0,
    entity_label: Optional[str] = None,
    entity_type: str = "work_order",
    entity_id: str = "",
) -> Dict[str, Any]:
    summary = build_recovery_summary(recovery_type, waiting_on_party=waiting_on_party, age_hours=age_hours)
    explanation = build_recovery_explanation(
        recovery_type,
        waiting_on_party=waiting_on_party,
        age_hours=age_hours,
        repetition_count=repetition_count,
        entity_label=entity_label,
    )
    steps = build_recommended_next_steps(recovery_type, waiting_on_party=waiting_on_party)
    actions = generate_recovery_actions(
        recovery_type,
        waiting_on_party=waiting_on_party,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    state = {
        "recovery_type": recovery_type,
        "severity": _severity(age_hours, repetition_count, recovery_type),
        "waiting_on_party": waiting_on_party,
        "age_hours": age_hours,
        "repetition_count": repetition_count,
        "escalation_level": 0,
        "recovery_confidence": "LOW",
        "operational_risk": derive_recovery_risk(recovery_type, age_hours=age_hours, repetition_count=repetition_count),
        "recovery_summary": summary,
        "recovery_explanation": explanation,
        "recommended_next_steps": steps,
        "suggested_actions": actions,
        "suppression_state": None,
        "authority_safe": True,
        "generated_at": _iso_now(),
    }
    assert_recovery_guidance_safe(state)
    return state


def suppress_invalid_recovery_guidance(
    recovery: Dict[str, Any],
    *,
    entity_terminal: bool = False,
    stall_resolved: bool = False,
    recovery_type_mismatch: bool = False,
) -> Dict[str, Any]:
    out = dict(recovery)
    if entity_terminal:
        out["suppression_state"] = "entity_terminal"
        out["suppressed"] = True
    elif stall_resolved:
        out["suppression_state"] = "stall_resolved"
        out["suppressed"] = True
    elif recovery_type_mismatch:
        out["suppression_state"] = "recovery_type_mismatch"
        out["suppressed"] = True
    else:
        out["suppression_state"] = None
        out["suppressed"] = False
    return out


async def _nudge_count_for_entity(entity_type: str, entity_id: str) -> int:
    db = database.get_db()
    if db is None or not entity_id:
        return 0
    return await db.workflow_nudge_audit.count_documents(
        {"entity_type": entity_type, "entity_id": entity_id, "outcome": "sent"}
    )


async def _evidence_rejection_count_for_requirement(requirement_id: str) -> int:
    db = database.get_db()
    if db is None or not requirement_id:
        return 0
    return await db.documents.count_documents(
        {
            "requirement_id": requirement_id,
            "evidence_review_state": "REJECTED",
        }
    )


def _build_recovery_record(
    *,
    entity_type: str,
    entity_id: str,
    client_id: Optional[str],
    recovery_type: str,
    waiting_on_party: Optional[str],
    age_hours: Optional[float],
    repetition_count: int,
    nudge_count: int,
    entity_label: Optional[str],
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    guidance = generate_recovery_guidance(
        recovery_type,
        waiting_on_party=waiting_on_party,
        age_hours=age_hours,
        repetition_count=repetition_count,
        entity_label=entity_label,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    guidance["entity_type"] = entity_type
    guidance["entity_id"] = entity_id
    guidance["client_id"] = client_id
    guidance["property_id"] = property_id
    enrich_recovery_intelligence(
        guidance,
        nudge_count=nudge_count,
        has_safe_action=bool(guidance.get("suggested_actions")),
    )
    return guidance


async def detect_workflow_recovery_candidates(
    client_id: str,
    *,
    property_id_filter: Optional[str] = None,
    limit: int = 50,
    fast_mode: bool = False,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    candidates: List[Dict[str, Any]] = []
    wo_q: Dict[str, Any] = {"client_id": client_id, "status": {"$nin": list(_TERMINAL_WO)}}
    if property_id_filter:
        wo_q["property_id"] = property_id_filter
    scan_limit = limit * 2 if fast_mode else limit * 4
    async for wo in db.work_orders.find(wo_q, {"_id": 0}).limit(scan_limit):
        wid = wo.get("work_order_id")
        stall = work_order_stall_context(wo)
        nudge_count = 0 if fast_mode else await _nudge_count_for_entity("work_order", wid or "")
        rtype = classify_recovery_state("work_order", wo, stall=stall, nudge_count=nudge_count)
        if not rtype:
            continue
        rep = max(_quote_revision_count(wo), int(wo.get("reschedule_count") or 0))
        rec = _build_recovery_record(
            entity_type="work_order",
            entity_id=wid,
            client_id=client_id,
            recovery_type=rtype,
            waiting_on_party=(stall or {}).get("waiting_on"),
            age_hours=(stall or {}).get("age_hours"),
            repetition_count=rep,
            nudge_count=nudge_count,
            entity_label=(wo.get("title") or wo.get("description") or f"Job {wid}")[:120],
            property_id=wo.get("property_id"),
        )
        candidates.append(rec)
        if len(candidates) >= limit:
            break

    req_q: Dict[str, Any] = {"client_id": client_id, "status": {"$in": list(_OVERDUE_REQ)}}
    if property_id_filter:
        req_q["property_id"] = property_id_filter
    async for req in db.requirements.find(req_q, {"_id": 0}).limit(limit):
        rid = req.get("requirement_id")
        rej = await _evidence_rejection_count_for_requirement(rid or "")
        rtype = classify_recovery_state("requirement", req, evidence_rejection_count=rej)
        if not rtype:
            continue
        since = req.get(REQ_OVERDUE_SINCE) or req.get("due_date")
        from services.workflow_nudge_reconciliation_service import _age_hours

        age = _age_hours(since)
        rec = _build_recovery_record(
            entity_type="requirement",
            entity_id=rid,
            client_id=client_id,
            recovery_type=rtype,
            waiting_on_party="landlord",
            age_hours=age,
            repetition_count=rej,
            nudge_count=0,
            entity_label=req.get("title") or req.get("requirement_type") or "Requirement",
            property_id=req.get("property_id"),
        )
        candidates.append(rec)

    candidates.sort(key=lambda r: (-(r.get("escalation_level") or 0), -(r.get("age_hours") or 0)))
    return candidates[:limit]


def build_operational_recovery_summary(candidates: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    by_type: Dict[str, int] = {}
    high_risk = 0
    blocked = 0
    waiting = 0
    for c in candidates:
        if c.get("suppressed"):
            continue
        rt = c.get("recovery_type") or "unknown"
        by_type[rt] = by_type.get(rt, 0) + 1
        if c.get("severity") == "high":
            high_risk += 1
        if rt in (RECOVERY_OPERATIONAL_DEAD_END, RECOVERY_WORK_ORDER_ABANDONMENT_RISK):
            blocked += 1
        elif rt.startswith("WAITING_"):
            waiting += 1
        elif "WAITING_ON" in rt:
            waiting += 1
    return {
        "total_candidates": len(candidates),
        "high_risk_count": high_risk,
        "blocked_count": blocked,
        "waiting_count": waiting,
        "by_recovery_type": by_type,
        "generated_at": _iso_now(),
        "has_recovery_attention": len(candidates) > 0,
    }
