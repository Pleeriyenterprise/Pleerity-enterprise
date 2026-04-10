"""
Composed client Command Center payload: reuses unified tasks, risk signals, compliance score.
Single read-model for dashboard / integrations; does not duplicate prioritisation logic.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.unified_tasks_service import get_unified_tasks_digest, get_unified_tasks_for_client
from services import risk_signal_service

logger = logging.getLogger(__name__)

_LEVEL_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _slim_task(t: Dict[str, Any]) -> Dict[str, Any]:
    metadata = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
    return {
        "id": t.get("id"),
        "task_id": t.get("id"),
        "title": t.get("title"),
        "description": (t.get("description") or "").strip() or None,
        "section": t.get("section"),
        "source_type": t.get("source_type"),
        "source_id": t.get("source_id"),
        "source_entity_type": t.get("source_entity_type") or t.get("source_type"),
        "source_entity_id": t.get("source_entity_id") or t.get("source_id"),
        "property_id": t.get("property_id"),
        "requirement_id": t.get("requirement_id"),
        "work_order_id": t.get("work_order_id"),
        "property_label": t.get("property_label"),
        "priority_level": t.get("urgency_level"),
        "urgency_level": t.get("urgency_level"),
        "due_date": t.get("due_date"),
        "overdue_days": t.get("overdue_days"),
        "impact_score": t.get("impact_score"),
        "impact_label": t.get("impact_label"),
        "filter_tags": t.get("filter_tags"),
        "metadata": metadata,
        "timing_label": metadata.get("timing_label"),
        "action_type": t.get("primary_action_type"),
        "primary_action_type": t.get("primary_action_type"),
        "primary_action_label": t.get("primary_action_label"),
        "primary_cta": {
            "label": t.get("primary_action_label"),
            "route": t.get("primary_action_url"),
            "action_type": t.get("primary_action_type"),
        },
        "secondary_actions": [
            {"action_type": "snooze", "label": "Snooze"},
            {"action_type": "dismiss", "label": "Dismiss"},
            {"action_type": "reviewed", "label": "Mark reviewed"},
        ],
        "audit_metadata": {
            "task_id": t.get("id"),
            "source_type": t.get("source_type"),
            "action_context_type": t.get("action_context_type") or t.get("primary_action_type"),
        },
        "primary_action_url": t.get("primary_action_url"),
        "cta_url": t.get("primary_action_url") or "/tasks",
    }


def _slim_risk(s: Dict[str, Any]) -> Dict[str, Any]:
    sid = s.get("signal_id") or ""
    return {
        "signal_id": sid,
        "risk_type": s.get("risk_type"),
        "risk_type_label_client": s.get("risk_type_label_client"),
        "recommended_action_client": s.get("recommended_action_client"),
        "risk_level": s.get("risk_level"),
        "property_id": s.get("property_id"),
        "description": (s.get("description") or "")[:240] or None,
        "status": s.get("status"),
        "cta_url": f"/operations/risk-signals?signal_id={sid}" if sid else "/operations/risk-signals",
    }


def _risk_sort_key(s: Dict[str, Any]):
    lvl = (s.get("risk_level") or "").lower()
    return (_LEVEL_ORDER.get(lvl, 9), s.get("updated_at") or s.get("generated_at") or "")


async def get_command_center_bundle(
    client_id: str,
    *,
    predictive_enabled: bool,
    property_id_filter: Optional[str] = None,
    portal_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return urgent_actions, upcoming_risks, recent_activity, compliance_status_summary
    plus tasks_digest_summary and freshness for cohesion with /tasks/digest.
    """
    urgent_actions: List[Dict[str, Any]] = []
    digest: Dict[str, Any] = {}
    full_tasks: Dict[str, Any] = {}
    upcoming_risks: List[Dict[str, Any]] = []

    try:
        digest = await get_unified_tasks_digest(
            client_id,
            property_id_filter=property_id_filter,
            activity_limit=20,
            portal_user_id=portal_user_id,
        )
    except Exception as e:
        logger.warning("command_center digest failed: %s", e)
        digest = {"summary": {}, "freshness": {}, "activity_feed": []}

    try:
        full_tasks = await get_unified_tasks_for_client(
            client_id,
            property_id_filter=property_id_filter,
            raw_limit=80,
            portal_user_id=portal_user_id,
        )
        tasks = full_tasks.get("tasks") or {}
        urgent = tasks.get("urgent") or []
        in_prog = tasks.get("in_progress") or []
        for t in (urgent[:10] + in_prog[:6]):
            urgent_actions.append(_slim_task(t))
    except Exception as e:
        logger.warning("command_center unified tasks failed: %s", e)

    if predictive_enabled:
        try:
            r = await risk_signal_service.get_risk_signals_for_client(
                client_id,
                property_id_filter=property_id_filter,
                status_filter=risk_signal_service.STATUS_ACTIVE,
                limit=60,
            )
            signals = [s for s in (r.get("signals") or []) if (s.get("status") or "").lower() == "active"]
            signals.sort(key=_risk_sort_key)
            upcoming_risks = [_slim_risk(s) for s in signals[:18]]
        except Exception as e:
            logger.warning("command_center risk signals failed: %s", e)

    compliance_status_summary: Dict[str, Any] = {}
    prow_scoped: Optional[Dict[str, Any]] = None
    try:
        from services.compliance_score import calculate_compliance_score

        cs = await calculate_compliance_score(client_id)
        stats = cs.get("stats") if isinstance(cs.get("stats"), dict) else {}
        notice = cs.get("jurisdiction_compliance_notice") or {}
        jreq_ids = list(cs.get("jurisdiction_required_property_ids") or [])
        jreq = bool(cs.get("jurisdiction_required"))
        jconf = cs.get("compliance_confidence")
        if property_id_filter:
            aff = [x for x in (notice.get("affected_property_ids") or []) if x == property_id_filter]
            notice = {
                **notice,
                "affected_property_ids": aff,
                "affected_property_count": len(aff),
                "active": bool(aff),
                "compliance_basis": "default_fallback" if aff else None,
            }
            prow_scoped = next(
                (x for x in (cs.get("property_breakdown") or []) if x.get("property_id") == property_id_filter),
                None,
            )
            if prow_scoped is not None:
                jreq = bool(prow_scoped.get("jurisdiction_required"))
                jconf = prow_scoped.get("compliance_confidence")
            else:
                jreq = property_id_filter in jreq_ids
                jconf = "fallback" if jreq else "explicit"
        compliance_status_summary = {
            "score": cs.get("score"),
            "grade": cs.get("grade"),
            "message": cs.get("message"),
            "color": cs.get("color"),
            "properties_count": cs.get("properties_count"),
            "requirements_overdue": stats.get("overdue"),
            "requirements_expiring_soon": stats.get("expiring_soon"),
            "requirements_pending": stats.get("pending"),
            "jurisdiction_compliance_notice": notice,
            "jurisdiction_required": jreq,
            "compliance_confidence": jconf,
            "jurisdiction_fallback_acknowledged": cs.get("jurisdiction_fallback_acknowledged"),
            "client_default_jurisdiction": cs.get("client_default_jurisdiction"),
        }
        if property_id_filter and prow_scoped:
            compliance_status_summary["scoped_property_jurisdiction"] = {
                "property_id": property_id_filter,
                "compliance_basis": prow_scoped.get("compliance_basis"),
                "effective_jurisdiction_label": prow_scoped.get("effective_jurisdiction_label"),
                "jurisdiction_required": prow_scoped.get("jurisdiction_required"),
                "compliance_confidence": prow_scoped.get("compliance_confidence"),
            }
    except Exception as e:
        logger.warning("command_center compliance score failed: %s", e)
        compliance_status_summary = {
            "score": None,
            "grade": None,
            "message": None,
            "jurisdiction_compliance_notice": {
                "active": False,
                "compliance_basis": None,
                "affected_property_ids": [],
                "affected_property_count": 0,
            },
            "jurisdiction_required": None,
            "compliance_confidence": None,
            "jurisdiction_fallback_acknowledged": None,
            "client_default_jurisdiction": None,
        }

    recent_activity = digest.get("activity_feed") or []

    return {
        "urgent_actions": urgent_actions,
        "upcoming_risks": upcoming_risks,
        "recent_activity": recent_activity,
        "compliance_status_summary": compliance_status_summary,
        "tasks_digest_summary": digest.get("summary") or {},
        "freshness": digest.get("freshness") or {},
    }
