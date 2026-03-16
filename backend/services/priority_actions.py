"""
Priority Action Engine — Orchestration and Copilot layer for Pleerity.
Combines compliance, operations, risk, approvals, and (for admin) incidents and automation
into ranked, actionable priorities for client and admin users.
"""
from typing import Any, Dict, List, Optional
from database import database
import logging

logger = logging.getLogger(__name__)

# --- Action types (for filtering and linking) ---
ACTION_OVERDUE_COMPLIANCE = "overdue_compliance"
ACTION_CERT_EXPIRING_SOON = "certificate_expiring_soon"
ACTION_MISSING_DOCUMENT = "missing_document"
ACTION_RISK_SIGNAL = "risk_signal"
ACTION_WORK_ORDER_NEAR_BREACH = "work_order_near_sla_breach"
ACTION_WORK_ORDER_BREACHED = "work_order_sla_breached"
ACTION_PENDING_APPROVAL = "pending_invoice_approval"
ACTION_OPEN_ISSUE = "open_operational_issue"
ACTION_OPEN_INCIDENT = "open_critical_incident"  # admin only
ACTION_AUTOMATION_DEGRADED = "automation_degraded"  # admin only

# --- Priority weights (higher = more urgent). Used for sorting. ---
SCORE_OVERDUE_COMPLIANCE = 90
SCORE_CERT_EXPIRING_7D = 75
SCORE_HIGH_RISK_SIGNAL = 70
SCORE_WORK_ORDER_NEAR_BREACH = 80
SCORE_WORK_ORDER_BREACHED = 85
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
    recommended_url: str = "",
    recommended_action_label: str = "View",
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a single priority action dict."""
    return {
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


async def _fetch_client_actions(client_id: str, property_id_filter: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """Fetch and build priority actions for a single client (client view)."""
    db = database.get_db()
    actions: List[Dict[str, Any]] = []

    # 1) Overdue compliance
    q_req = {"client_id": client_id, "status": {"$in": ["OVERDUE", "EXPIRED"]}}
    if property_id_filter:
        q_req["property_id"] = property_id_filter
    cursor = db.requirements.find(q_req).limit(limit)
    reqs = await cursor.to_list(limit)
    for r in reqs:
        prop_id = r.get("property_id")
        code = r.get("code") or r.get("requirement_type") or "Requirement"
        actions.append(_action(
            ACTION_OVERDUE_COMPLIANCE,
            f"Overdue: {code}",
            f"Compliance item is overdue at this property.",
            SCORE_OVERDUE_COMPLIANCE,
            SEVERITY_HIGH,
            related_property_id=prop_id,
            recommended_url=f"/properties/{prop_id}" if prop_id else "/compliance-score",
            recommended_action_label="Review compliance",
        ))

    # 2) Certificate expiring soon (EXPIRING_SOON)
    q_exp = {"client_id": client_id, "status": "EXPIRING_SOON"}
    if property_id_filter:
        q_exp["property_id"] = property_id_filter
    cursor = db.requirements.find(q_exp).limit(limit)
    exp_reqs = await cursor.to_list(limit)
    for r in exp_reqs:
        prop_id = r.get("property_id")
        code = r.get("code") or r.get("requirement_type") or "Certificate"
        actions.append(_action(
            ACTION_CERT_EXPIRING_SOON,
            f"Expiring soon: {code}",
            "Certificate or requirement is expiring soon; renew or upload evidence.",
            SCORE_CERT_EXPIRING_7D,
            SEVERITY_MEDIUM,
            related_property_id=prop_id,
            recommended_url=f"/properties/{prop_id}" if prop_id else "/compliance-score",
            recommended_action_label="Review compliance",
        ))

    # 3) Missing required documents (PENDING / MISSING with no evidence)
    q_miss = {"client_id": client_id, "status": {"$in": ["PENDING", "MISSING"]}}
    if property_id_filter:
        q_miss["property_id"] = property_id_filter
    cursor = db.requirements.find(q_miss).limit(limit)
    miss_reqs = await cursor.to_list(limit)
    for r in miss_reqs:
        if r.get("evidence_doc_id"):
            continue
        prop_id = r.get("property_id")
        code = r.get("code") or r.get("requirement_type") or "Document"
        actions.append(_action(
            ACTION_MISSING_DOCUMENT,
            f"Missing document: {code}",
            "Required evidence or document is missing.",
            SCORE_MISSING_DOCUMENT,
            SEVERITY_MEDIUM,
            related_property_id=prop_id,
            recommended_url=f"/properties/{prop_id}" if prop_id else "/compliance-score",
            recommended_action_label="Upload document",
        ))

    # 4) Active risk signals (high/medium)
    try:
        from services import risk_signal_service
        risk_data = await risk_signal_service.get_risk_signals_for_client(
            client_id=client_id,
            property_id_filter=property_id_filter,
            status_filter="active",
            limit=limit,
        )
        signals = risk_data.get("signals") or risk_data.get("highPriority") or []
        for s in signals[:limit]:
            if (s.get("status") or "").lower() != "active":
                continue
            level = (s.get("risk_level") or "").lower()
            score = SCORE_HIGH_RISK_SIGNAL if level in ("high", "critical") else 55
            sig_id = s.get("signal_id") or s.get("risk_signal_id") or s.get("id")
            prop_id = s.get("property_id")
            actions.append(_action(
                ACTION_RISK_SIGNAL,
                s.get("risk_type") or "Risk signal",
                (s.get("recommended_action") or ((s.get("reasons") or [])[0] if isinstance(s.get("reasons"), list) and s.get("reasons") else None)) or "Review risk signal",
                score,
                SEVERITY_HIGH if level in ("high", "critical") else SEVERITY_MEDIUM,
                related_risk_signal_id=sig_id,
                related_property_id=prop_id,
                recommended_url="/operations/risk-signals",
                recommended_action_label="Review risk signal",
            ))
    except Exception as e:
        logger.debug("Priority actions: risk signals fetch failed for client %s: %s", client_id, e)

    # 5) Work orders near SLA breach or breached
    try:
        from services import maintenance_service
        for sla_state, score, label in [
            ("breached", SCORE_WORK_ORDER_BREACHED, "SLA breached"),
            ("near_breach", SCORE_WORK_ORDER_NEAR_BREACH, "Near SLA breach"),
        ]:
            wo_result = await maintenance_service.list_work_orders(
                client_id=client_id,
                property_id=property_id_filter,
                sla_state=sla_state,
                limit=limit,
            )
            for wo in (wo_result.get("work_orders") or [])[:limit]:
                wo_id = wo.get("work_order_id")
                prop_id = wo.get("property_id")
                actions.append(_action(
                    ACTION_WORK_ORDER_BREACHED if sla_state == "breached" else ACTION_WORK_ORDER_NEAR_BREACH,
                    f"Work order {label.lower()}",
                    wo.get("description") or f"Work order {wo_id[:8]}…",
                    score,
                    SEVERITY_HIGH if sla_state == "breached" else SEVERITY_MEDIUM,
                    related_work_order_id=wo_id,
                    related_property_id=prop_id,
                    recommended_url="/operations/work-orders",
                    recommended_action_label="View work order",
                ))
    except Exception as e:
        logger.debug("Priority actions: work orders fetch failed for client %s: %s", client_id, e)

    # 6) Pending invoice approvals
    try:
        from services.approval_service import list_approvals, STATUS_PENDING
        appr_data = await list_approvals(client_id=client_id, status=STATUS_PENDING, limit=limit)
        for inv in (appr_data.get("approvals") or [])[:limit]:
            inv_id = inv.get("invoice_id") or inv.get("id")
            actions.append(_action(
                ACTION_PENDING_APPROVAL,
                "Pending invoice approval",
                inv.get("description") or f"Invoice {str(inv_id)[:8]}…",
                SCORE_PENDING_INVOICE,
                SEVERITY_MEDIUM,
                related_invoice_id=inv_id,
                related_property_id=inv.get("property_id"),
                recommended_url="/operations/approvals",
                recommended_action_label="Approve invoice",
            ))
    except Exception as e:
        logger.debug("Priority actions: approvals fetch failed for client %s: %s", client_id, e)

    # 7) Open operational issues (not resolved/closed)
    try:
        from services import maintenance_issues_service
        open_statuses = [
            maintenance_issues_service.STATUS_OPEN,
            maintenance_issues_service.STATUS_NEW,
            maintenance_issues_service.STATUS_TRIAGED,
            maintenance_issues_service.STATUS_INVESTIGATING,
            maintenance_issues_service.STATUS_READY_FOR_WORK_ORDER,
            maintenance_issues_service.STATUS_IN_PROGRESS,
        ]
        for st in open_statuses:
            issues_result = await maintenance_issues_service.list_issues(
                client_id=client_id,
                property_id=property_id_filter,
                status=st,
                limit=limit,
            )
            for iss in (issues_result.get("issues") or [])[:limit]:
                actions.append(_action(
                    ACTION_OPEN_ISSUE,
                    "Open operational issue",
                    (iss.get("description") or "")[:200] or f"Issue {iss.get('issue_id', '')[:8]}…",
                    SCORE_OPEN_ISSUE,
                    SEVERITY_MEDIUM,
                    related_issue_id=iss.get("issue_id"),
                    related_property_id=iss.get("property_id"),
                    recommended_url="/operations/issues",
                    recommended_action_label="View issue",
                ))
    except Exception as e:
        logger.debug("Priority actions: issues fetch failed for client %s: %s", client_id, e)

    return actions


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
                actions.append(_action(
                    ACTION_WORK_ORDER_BREACHED if sla_state == "breached" else ACTION_WORK_ORDER_NEAR_BREACH,
                    "Work order " + ("SLA breached" if sla_state == "breached" else "near SLA breach"),
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
               a.get("related_property_id"), a.get("client_id"))
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
    Returns { "actions": [...], "total": N }.
    """
    actions = await _fetch_admin_actions(client_id_filter, limit * 2)
    ranked = _dedupe_and_rank(actions, limit)
    if ranked:
        logger.info("Priority actions for admin (client_filter=%s): %d actions", client_id_filter, len(ranked))
    return {"actions": ranked, "total": len(ranked)}
