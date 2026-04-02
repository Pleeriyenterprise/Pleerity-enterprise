"""
Priority Action Engine — Orchestration and Copilot layer for Pleerity.
Combines compliance, operations, risk, approvals, and (for admin) incidents and automation
into ranked, actionable priorities for client and admin users.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from urllib.parse import quote as _url_quote
from database import database
import logging

from presentation.label_service import (
    issue_status_label,
    requirement_label,
    sla_state_label,
    work_order_status_label,
)
from services.client_priority_stream import (
    fetch_client_priority_actions,
    ACTION_OVERDUE_COMPLIANCE,
    ACTION_CERT_EXPIRING_SOON,
    ACTION_MISSING_DOCUMENT,
    ACTION_RISK_SIGNAL,
    ACTION_WORK_ORDER_NEAR_BREACH,
    ACTION_WORK_ORDER_BREACHED,
    ACTION_OPEN_WORK_ORDER,
    ACTION_PENDING_APPROVAL,
    ACTION_OPEN_ISSUE,
)

logger = logging.getLogger(__name__)


def _iso_or_none(val: Any) -> Optional[str]:
    """Normalize datetime-like values to ISO-8601 string for API consumers."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.isoformat()
    s = str(val).strip()
    return s or None


def _requirement_effective_due_iso(r: Dict[str, Any]) -> Optional[str]:
    """Best-effort compliance due / expiry for prioritization and task display."""
    for key in ("confirmed_expiry_date", "due_date", "extracted_expiry_date", "expires_at"):
        v = r.get(key)
        if v is None:
            continue
        iso = _iso_or_none(v)
        if iso:
            return iso
    return None


def _requirement_code_for_hash(r: Dict[str, Any]) -> str:
    return (r.get("code") or r.get("requirement_code") or r.get("requirement_type") or "").strip()

# --- Action types (for filtering and linking) ---
ACTION_OPEN_INCIDENT = "open_critical_incident"  # admin only
ACTION_AUTOMATION_DEGRADED = "automation_degraded"  # admin only

# --- Priority weights (higher = more urgent). Used for sorting. ---
SCORE_OVERDUE_COMPLIANCE = 90
SCORE_CERT_EXPIRING_7D = 75
SCORE_HIGH_RISK_SIGNAL = 70
SCORE_WORK_ORDER_NEAR_BREACH = 80
SCORE_WORK_ORDER_BREACHED = 85
SCORE_OPEN_WORK_ORDER = 42
SCORE_PENDING_INVOICE = 50
SCORE_MISSING_DOCUMENT = 40
SCORE_OPEN_ISSUE = 45
SCORE_OPEN_P0_P1_INCIDENT = 95
SCORE_AUTOMATION_DEGRADED = 60

# Severity display (critical / high / medium / low)
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"


def _action(
    action_type: str,
    title: str,
    description: str,
    priority: int,
    severity: str,
    *,
    related_property_id: Optional[str] = None,
    related_issue_id: Optional[str] = None,
    related_work_order_id: Optional[str] = None,
    related_risk_signal_id: Optional[str] = None,
    related_invoice_id: Optional[str] = None,
    related_incident_id: Optional[str] = None,
    related_requirement_id: Optional[str] = None,
    requirement_code: Optional[str] = None,
    due_at: Optional[str] = None,
    source_updated_at: Optional[str] = None,
    why_matters: Optional[str] = None,
    recommended_action_detail: Optional[str] = None,
    recommended_url: str = "",
    recommended_action_label: str = "View",
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a single priority action dict."""
    out: Dict[str, Any] = {
        "action_type": action_type,
        "title": title,
        "description": description,
        "priority": priority,
        "severity": severity,
        "related_property_id": related_property_id,
        "related_issue_id": related_issue_id,
        "related_work_order_id": related_work_order_id,
        "related_risk_signal_id": related_risk_signal_id,
        "related_invoice_id": related_invoice_id,
        "related_incident_id": related_incident_id,
        "recommended_url": recommended_url,
        "recommended_action_label": recommended_action_label,
        "client_id": client_id,
    }
    if related_requirement_id:
        out["related_requirement_id"] = related_requirement_id
    if requirement_code:
        out["requirement_code"] = requirement_code
    if due_at:
        out["due_at"] = due_at
    if source_updated_at:
        out["source_updated_at"] = source_updated_at
    if why_matters:
        out["why_matters"] = why_matters
    if recommended_action_detail:
        out["recommended_action_detail"] = recommended_action_detail
    return out


async def _fetch_client_actions(client_id: str, property_id_filter: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """Compatibility wrapper: canonical generator lives in client_priority_stream."""
    return await fetch_client_priority_actions(client_id, property_id_filter, limit)


async def _fetch_admin_actions(client_id_filter: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """Fetch and build priority actions for admin (cross-client or single client)."""
    db = database.get_db()
    actions: List[Dict[str, Any]] = []

    # Resolve client_ids to iterate
    if client_id_filter:
        client_ids = [client_id_filter]
    else:
        cursor = db.clients.find({}, {"_id": 0, "client_id": 1})
        client_ids = [c["client_id"] async for c in cursor]

    # 1) Clients with urgent compliance failures (overdue)
    for cid in client_ids[:50]:
        overdue_count = await db.requirements.count_documents(
            {"client_id": cid, "status": {"$in": ["OVERDUE", "EXPIRED"]}}
        )
        if overdue_count > 0:
            actions.append(_action(
                ACTION_OVERDUE_COMPLIANCE,
                f"Client has {overdue_count} overdue compliance item(s)",
                "Address overdue compliance to avoid regulatory risk.",
                SCORE_OVERDUE_COMPLIANCE,
                SEVERITY_HIGH,
                recommended_url=f"/admin/clients/{cid}" if cid else "/admin/ops/compliance",
                recommended_action_label="View client",
                client_id=cid,
            ))

    # 2) Work orders near breach / breached (admin view)
    try:
        from services import maintenance_service
        q_wo = {}
        if client_id_filter:
            q_wo["client_id"] = client_id_filter
        for sla_state, score in [("breached", SCORE_WORK_ORDER_BREACHED), ("near_breach", SCORE_WORK_ORDER_NEAR_BREACH)]:
            wo_result = await maintenance_service.list_work_orders(
                client_id=q_wo.get("client_id"),
                sla_state=sla_state,
                limit=limit,
            )
            for wo in (wo_result.get("work_orders") or [])[:limit]:
                sla_key = "breached" if sla_state == "breached" else "near_breach"
                actions.append(_action(
                    ACTION_WORK_ORDER_BREACHED if sla_state == "breached" else ACTION_WORK_ORDER_NEAR_BREACH,
                    f"Work order — {sla_state_label(sla_key, 'admin')}",
                    wo.get("description") or wo.get("work_order_id", "")[:8],
                    score,
                    SEVERITY_HIGH if sla_state == "breached" else SEVERITY_MEDIUM,
                    related_work_order_id=wo.get("work_order_id"),
                    related_property_id=wo.get("property_id"),
                    recommended_url="/admin/ops/maintenance",
                    recommended_action_label="View work orders",
                    client_id=wo.get("client_id"),
                ))
    except Exception as e:
        logger.debug("Priority actions: admin work orders fetch failed: %s", e)

    # 3) Open P0/P1 incidents
    try:
        from services.incident_service import list_incidents
        for sev in ["P0", "P1"]:
            inc_data = await list_incidents(status="open", severity=sev, limit=limit)
            for inc in (inc_data.get("items") or [])[:limit]:
                inc_id = inc.get("id")
                actions.append(_action(
                    ACTION_OPEN_INCIDENT,
                    f"[{sev}] {inc.get('title', 'Incident')}",
                    inc.get("description") or "",
                    SCORE_OPEN_P0_P1_INCIDENT,
                    SEVERITY_CRITICAL,
                    related_incident_id=inc_id,
                    recommended_url="/admin/incidents",
                    recommended_action_label="View incident",
                ))
    except Exception as e:
        logger.debug("Priority actions: admin incidents fetch failed: %s", e)

    # 4) Approval bottlenecks (pending count per client)
    try:
        from services.approval_service import list_approvals, STATUS_PENDING
        for cid in client_ids[:30]:
            appr_data = await list_approvals(client_id=cid, status=STATUS_PENDING, limit=5)
            count = len(appr_data.get("approvals") or [])
            if count > 0:
                actions.append(_action(
                    ACTION_PENDING_APPROVAL,
                    f"Client has {count} pending invoice(s)",
                    "Review and approve or reject pending invoices.",
                    SCORE_PENDING_INVOICE,
                    SEVERITY_MEDIUM,
                    recommended_url="/admin/clients/" + cid if cid else "/admin/ops",
                    recommended_action_label="View approvals",
                    client_id=cid,
                ))
    except Exception as e:
        logger.debug("Priority actions: admin approvals fetch failed: %s", e)

    # 5) Risk hotspots (admin summary: clients/properties with high risk signals)
    try:
        from services import risk_signal_service
        risk_summary = await risk_signal_service.get_risk_signals_admin_summary(
            client_id_filter=client_id_filter,
            risk_level="high",
            status_filter="active",
            limit_signals=limit,
        )
        signals = risk_summary.get("recentSignals") or risk_summary.get("signals") or []
        for s in signals[:limit]:
            actions.append(_action(
                ACTION_RISK_SIGNAL,
                s.get("risk_type") or "High-risk signal",
                (s.get("recommended_action") or "Review risk")[:200],
                SCORE_HIGH_RISK_SIGNAL,
                SEVERITY_HIGH,
                related_risk_signal_id=s.get("signal_id") or s.get("risk_signal_id") or s.get("id"),
                related_property_id=s.get("property_id"),
                recommended_url="/admin/ops/risk",
                recommended_action_label="View risk dashboard",
                client_id=s.get("client_id"),
            ))
    except Exception as e:
        logger.debug("Priority actions: admin risk summary fetch failed: %s", e)

    # 6) Stale or degraded automation (admin)
    try:
        from services.job_schedule_registry import get_critical_job_ids
        from services.job_run_service import STATUS_FAILED, STATUS_DEGRADED
        critical_ids = get_critical_job_ids()
        jobs_detail = {}
        for job_name in critical_ids[:20]:
            last_run = await db.job_runs.find_one(
                {"job_name": job_name},
                {"_id": 0, "finished_at": 1, "status": 1},
                sort=[("finished_at", -1)],
            )
            last_fail = await db.job_runs.find_one(
                {"job_name": job_name, "status": STATUS_FAILED},
                {"_id": 0, "finished_at": 1},
                sort=[("finished_at", -1)],
            )
            last_degraded = await db.job_runs.find_one(
                {"job_name": job_name, "status": STATUS_DEGRADED},
                {"_id": 0, "finished_at": 1},
                sort=[("finished_at", -1)],
            )
            jobs_detail[job_name] = {
                "last_completed": last_run.get("finished_at") if last_run else None,
                "last_run_status": last_run.get("status") if last_run else None,
                "last_failure": last_fail.get("finished_at") if last_fail else None,
                "last_degraded": last_degraded.get("finished_at") if last_degraded else None,
            }
        # Simple state: if last run failed/degraded or never ran (no last_completed), add action
        for jid in critical_ids[:15]:
            detail = jobs_detail.get(jid, {})
            last_completed = detail.get("last_completed")
            last_status = (detail.get("last_run_status") or "").strip().lower()
            if last_status == "failed":
                actions.append(_action(
                    ACTION_AUTOMATION_DEGRADED,
                    f"Job failed: {jid}",
                    "Automation job failed; review logs and recover.",
                    SCORE_AUTOMATION_DEGRADED,
                    SEVERITY_HIGH,
                    recommended_url="/admin/ops",
                    recommended_action_label="View system health",
                ))
            elif last_status == "degraded":
                actions.append(_action(
                    ACTION_AUTOMATION_DEGRADED,
                    f"Job degraded: {jid}",
                    "Automation job completed with degraded outcome.",
                    SCORE_AUTOMATION_DEGRADED - 10,
                    SEVERITY_MEDIUM,
                    recommended_url="/admin/ops",
                    recommended_action_label="View system health",
                ))
            elif not last_completed:
                actions.append(_action(
                    ACTION_AUTOMATION_DEGRADED,
                    f"Job never run / overdue: {jid}",
                    "Critical job has not run or is overdue.",
                    SCORE_AUTOMATION_DEGRADED,
                    SEVERITY_HIGH,
                    recommended_url="/admin/ops",
                    recommended_action_label="View system health",
                ))
    except Exception as e:
        logger.debug("Priority actions: admin automation state fetch failed: %s", e)

    return actions


def _dedupe_and_rank(actions: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """Deduplicate by (action_type, related_* id) and sort by priority desc, then take top limit."""
    seen = set()
    out = []
    for a in sorted(actions, key=lambda x: (-x["priority"], x.get("title") or "")):
        key = (a["action_type"], a.get("related_work_order_id"), a.get("related_risk_signal_id"),
               a.get("related_invoice_id"), a.get("related_issue_id"), a.get("related_incident_id"),
               a.get("related_property_id"), a.get("related_requirement_id"), a.get("client_id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
        if len(out) >= limit:
            break
    return out


async def get_priority_actions_for_client(
    client_id: str,
    property_id_filter: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Get ranked priority actions for a client user.
    Returns { "actions": [...], "total": N }.
    """
    actions = await _fetch_client_actions(client_id, property_id_filter, limit * 2)
    ranked = _dedupe_and_rank(actions, limit)
    if ranked:
        logger.info("Priority actions for client %s: %d actions", client_id, len(ranked))
    return {"actions": ranked, "total": len(ranked)}


async def get_priority_actions_for_admin(
    client_id_filter: Optional[str] = None,
    limit: int = 30,
) -> Dict[str, Any]:
    """
    Get ranked priority actions for an admin (action queue / operational priorities).
    When client_id_filter is set, only actions for that client (or without client_id) are returned.
    Returns { "actions": [...], "total": N }.
    """
    actions = await _fetch_admin_actions(client_id_filter, limit * 2)
    ranked = _dedupe_and_rank(actions, limit)
    if client_id_filter:
        cid = client_id_filter.strip()
        if cid:
            # When a client is selected, show only that client's actions (exclude global/no-client items)
            ranked = [a for a in ranked if a.get("client_id") == cid]
    if ranked:
        logger.info("Priority actions for admin (client_filter=%s): %d actions", client_id_filter, len(ranked))
    return {"actions": ranked, "total": len(ranked)}
