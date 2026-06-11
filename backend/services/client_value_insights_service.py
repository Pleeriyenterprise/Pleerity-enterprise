"""
Client-facing value / monetisation insights: real counts from Mongo + plan_registry entitlements.
Used for dashboard "what you achieved", "what's at risk", and contextual upgrade copy.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.plan_registry import FEATURE_MATRIX, PLAN_DEFINITIONS, PlanCode, plan_registry

logger = logging.getLogger(__name__)

PLAN_UPGRADE_ORDER = [PlanCode.PLAN_1_SOLO, PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO]

FEATURE_UNLOCK_LABELS = {
    "document_upload_bulk_zip": "Bulk ZIP document upload",
    "reports_pdf": "PDF reports and exports",
    "scheduled_reports": "Scheduled automated reports",
    "sms_reminders": "SMS expiry reminders",
    "ai_extraction_advanced": "Advanced AI document extraction",
    "extraction_review_ui": "Extraction review workspace",
    "reports_csv": "CSV data export",
    "tenant_portal": "Tenant portal access",
    "webhooks": "Webhooks and API automation",
    "white_label_reports": "White-label branded reports",
    "audit_log_export": "Audit log export",
}


def _next_plan_code(current: PlanCode) -> Optional[PlanCode]:
    try:
        idx = PLAN_UPGRADE_ORDER.index(current)
    except ValueError:
        return PlanCode.PLAN_2_PORTFOLIO if current == PlanCode.PLAN_1_SOLO else None
    if idx + 1 < len(PLAN_UPGRADE_ORDER):
        return PLAN_UPGRADE_ORDER[idx + 1]
    return None


def _build_upgrade_nudge_reasons(
    *,
    at_property_limit: bool,
    nxt: Optional[PlanCode],
    overdue: int,
    expiring: int,
    urgent_open: int,
    docs_period: int,
    wo_completed_period: int,
) -> List[Dict[str, str]]:
    """Context-specific upgrade copy: answers why upgrade now (limits, risk stack, usage)."""
    if nxt is None:
        return []
    reasons: List[Dict[str, str]] = []
    if at_property_limit:
        reasons.append(
            {
                "code": "PROPERTY_LIMIT",
                "headline": "You've reached your property limit",
                "why_now": "New properties cannot be added on your current plan. Upgrade now so portfolio growth and compliance tracking stay in one system.",
            }
        )
    if overdue >= 3 or (overdue >= 1 and expiring >= 5):
        reasons.append(
            {
                "code": "REPEATED_COMPLIANCE_RISK",
                "headline": "Compliance risk is stacking up",
                "why_now": (
                    f"You have {overdue} overdue and {expiring} expiring-soon requirements. "
                    "A higher tier adds automation and reporting to clear the backlog before more items slip."
                ),
            }
        )
    if urgent_open >= 5:
        reasons.append(
            {
                "code": "HIGH_TASK_LOAD",
                "headline": "Your priority inbox is under heavy load",
                "why_now": (
                    f"{urgent_open} urgent items need attention. "
                    "Upgrading unlocks capabilities that reduce manual triage at this volume."
                ),
            }
        )
    if docs_period >= 15:
        reasons.append(
            {
                "code": "HIGH_DOCUMENT_VOLUME",
                "headline": "Document volume is elevated",
                "why_now": (
                    f"{docs_period} uploads in the last 30 days. "
                    "The next tier includes stronger bulk and review tooling so this pace stays manageable."
                ),
            }
        )
    if wo_completed_period >= 8:
        reasons.append(
            {
                "code": "HIGH_JOB_VOLUME",
                "headline": "Job throughput is high",
                "why_now": (
                    f"{wo_completed_period} jobs completed in 30 days. "
                    "Upgrade to align contractor workflows, approvals, and limits with current operational load."
                ),
            }
        )
    seen = set()
    out: List[Dict[str, str]] = []
    for r in reasons:
        c = r.get("code")
        if c and c not in seen:
            seen.add(c)
            out.append(r)
    return out[:5]


def _unlock_highlights(current: PlanCode, nxt: PlanCode) -> List[str]:
    lines: List[str] = []
    cur_def = PLAN_DEFINITIONS.get(current, PLAN_DEFINITIONS[PlanCode.PLAN_1_SOLO])
    nxt_def = PLAN_DEFINITIONS.get(nxt, PLAN_DEFINITIONS[PlanCode.PLAN_3_PRO])
    cap_cur = int(cur_def.get("max_properties") or 0)
    cap_nxt = int(nxt_def.get("max_properties") or 0)
    if cap_nxt > cap_cur:
        lines.append(f"More properties — up to {cap_nxt} (your plan: {cap_cur})")
    cur_f = FEATURE_MATRIX.get(current, FEATURE_MATRIX[PlanCode.PLAN_1_SOLO])
    next_f = FEATURE_MATRIX.get(nxt, FEATURE_MATRIX[PlanCode.PLAN_3_PRO])
    for key, enabled_next in next_f.items():
        if not enabled_next or cur_f.get(key):
            continue
        label = FEATURE_UNLOCK_LABELS.get(key)
        if label:
            lines.append(label)
    return lines[:10]


async def get_value_insights(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    ent = await plan_registry.get_client_entitlements(client_id)
    plan_str = ent.get("plan") or "PLAN_1_SOLO"
    current_pc = plan_registry.resolve_plan_code(plan_str)
    nxt = _next_plan_code(current_pc)

    prop_count = await db.properties.count_documents({"client_id": client_id})
    max_p = int(ent.get("max_properties") or 0)
    at_property_limit = max_p > 0 and prop_count >= max_p

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=30)

    total_req = 0
    compliant = 0
    overdue = 0
    expiring = 0
    try:
        from services.compliance_score import calculate_compliance_score

        score_block = await calculate_compliance_score(client_id)
        st = score_block.get("stats") or {}
        total_req = int(st.get("total_requirements") or 0)
        compliant = int(st.get("compliant") or 0)
        overdue = int(st.get("overdue") or 0)
        expiring = int(st.get("expiring_soon") or 0)
    except Exception as e:
        logger.warning("value_insights compliance_score failed client=%s: %s", client_id, e)

    doc_count = await db.documents.count_documents({"client_id": client_id})
    docs_period = await db.documents.count_documents(
        {"client_id": client_id, "uploaded_at": {"$gte": period_start.isoformat()}}
    )

    wo_completed_period = await db.work_orders.count_documents(
        {
            "client_id": client_id,
            "status": "COMPLETED",
            "$or": [
                {"completed_at": {"$gte": period_start.isoformat()}},
                {"updated_at": {"$gte": period_start.isoformat()}},
            ],
        }
    )

    urgent_open = 0
    upcoming_open = 0
    task_count_resolution: Dict[str, Any] = {}
    try:
        from services.unified_tasks_service import resolve_value_insights_task_counts

        task_count_resolution = await resolve_value_insights_task_counts(client_id, activity_limit=3)
        urgent_open = int(task_count_resolution.get("urgent_count") or 0)
        upcoming_open = int(task_count_resolution.get("upcoming_count") or 0)
    except Exception as e:
        logger.warning("value_insights task counts failed client=%s: %s", client_id, e)

    unlocks: List[str] = []
    upgrade_plan = None
    upgrade_plan_name = None
    if nxt:
        unlocks = _unlock_highlights(current_pc, nxt)
        upgrade_plan = nxt.value
        upgrade_plan_name = PLAN_DEFINITIONS.get(nxt, {}).get("display_name") or PLAN_DEFINITIONS.get(nxt, {}).get("name")

    upgrade_nudge_reasons = _build_upgrade_nudge_reasons(
        at_property_limit=at_property_limit,
        nxt=nxt,
        overdue=overdue,
        expiring=expiring,
        urgent_open=urgent_open,
        docs_period=docs_period,
        wo_completed_period=wo_completed_period,
    )

    cur_def = PLAN_DEFINITIONS.get(current_pc, PLAN_DEFINITIONS[PlanCode.PLAN_1_SOLO])
    nxt_def = PLAN_DEFINITIONS.get(nxt, {}) if nxt else {}
    plan_comparison: Dict[str, Any] = {
        "current": {
            "plan_code": plan_str,
            "display_name": ent.get("plan_display_name")
            or ent.get("plan_name")
            or cur_def.get("display_name")
            or cur_def.get("name"),
            "max_properties": max_p,
        },
        "next": None,
        "you_get_on_next_tier": unlocks,
        "immediate_benefit_line": None,
    }
    if nxt:
        cap_nxt = int(nxt_def.get("max_properties") or 0)
        plan_comparison["next"] = {
            "plan_code": upgrade_plan,
            "display_name": upgrade_plan_name,
            "max_properties": cap_nxt,
        }
        plan_comparison["immediate_benefit_line"] = (
            unlocks[0]
            if unlocks
            else f"Upgrade to {upgrade_plan_name or upgrade_plan} for higher limits and more capabilities."
        )

    return {
        "client_id": client_id,
        "plan": plan_str,
        "plan_display_name": ent.get("plan_display_name") or ent.get("plan_name"),
        "property_count": prop_count,
        "max_properties": max_p,
        "at_property_limit": at_property_limit,
        "show_upgrade_for_property_cap": at_property_limit and nxt is not None,
        "achievements": {
            "requirements_compliant": compliant,
            "requirements_total_tracked": total_req,
            "documents_on_file": doc_count,
            "documents_uploaded_last_30_days": docs_period,
            "work_orders_completed_last_30_days": wo_completed_period,
            "properties_on_record": prop_count,
        },
        "at_risk": {
            "overdue_requirements": overdue,
            "expiring_soon_requirements": expiring,
            "command_centre_urgent_open": urgent_open,
            "command_centre_upcoming_open": upcoming_open,
        },
        "upgrade_path": {
            "next_plan_code": upgrade_plan,
            "next_plan_display_name": upgrade_plan_name,
            "unlocks_on_next_tier": unlocks,
            "at_highest_public_tier": nxt is None,
        },
        "upgrade_nudge_reasons": upgrade_nudge_reasons,
        "plan_comparison": plan_comparison,
        "task_count_resolution": task_count_resolution,
        "generated_at": now.isoformat(),
    }
