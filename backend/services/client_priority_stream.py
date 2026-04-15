"""
Single client priority generator for portal-facing priority streams.
This module is the canonical backend implementation used by unified tasks.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from urllib.parse import quote as _url_quote
import logging

from database import database
from presentation.label_service import (
    issue_status_label,
    requirement_label,
    sla_state_label,
    work_order_status_label,
)
from services.compliance_requirement_engine import requirement_row_in_client_priority_stream

logger = logging.getLogger(__name__)

ACTION_OVERDUE_COMPLIANCE = "overdue_compliance"
ACTION_CERT_EXPIRING_SOON = "certificate_expiring_soon"
ACTION_MISSING_DOCUMENT = "missing_document"
ACTION_RISK_SIGNAL = "risk_signal"
ACTION_WORK_ORDER_NEAR_BREACH = "work_order_near_sla_breach"
ACTION_WORK_ORDER_BREACHED = "work_order_sla_breached"
ACTION_OPEN_WORK_ORDER = "open_work_order"
ACTION_PENDING_APPROVAL = "pending_invoice_approval"
ACTION_OPEN_ISSUE = "open_operational_issue"

SCORE_OVERDUE_COMPLIANCE = 90
SCORE_CERT_EXPIRING_7D = 75
SCORE_HIGH_RISK_SIGNAL = 70
SCORE_WORK_ORDER_NEAR_BREACH = 80
SCORE_WORK_ORDER_BREACHED = 85
SCORE_OPEN_WORK_ORDER = 42
SCORE_PENDING_INVOICE = 50
SCORE_MISSING_DOCUMENT = 40
SCORE_OPEN_ISSUE = 45

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"


def _iso_or_none(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.isoformat()
    s = str(val).strip()
    return s or None


def _requirement_effective_due_iso(r: Dict[str, Any]) -> Optional[str]:
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
    related_requirement_id: Optional[str] = None,
    requirement_code: Optional[str] = None,
    due_at: Optional[str] = None,
    source_updated_at: Optional[str] = None,
    why_matters: Optional[str] = None,
    recommended_action_detail: Optional[str] = None,
    recommended_url: str = "",
    recommended_action_label: str = "View",
    portfolio_jurisdiction: Optional[str] = None,
) -> Dict[str, Any]:
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
        "recommended_url": recommended_url,
        "recommended_action_label": recommended_action_label,
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
    if portfolio_jurisdiction:
        out["jurisdiction"] = portfolio_jurisdiction
    return out


async def fetch_client_priority_actions(client_id: str, property_id_filter: Optional[str], limit: int) -> List[Dict[str, Any]]:
    db = database.get_db()
    actions: List[Dict[str, Any]] = []

    q_req = {"client_id": client_id, "status": {"$in": ["OVERDUE", "EXPIRED"]}}
    if property_id_filter:
        q_req["property_id"] = property_id_filter
    reqs = await db.requirements.find(q_req).limit(limit).to_list(limit)
    for r in reqs:
        ok, _eng = requirement_row_in_client_priority_stream(r, kind="overdue")
        if not ok:
            continue
        prop_id = r.get("property_id")
        code_raw = r.get("code") or r.get("requirement_type") or ""
        disp = requirement_label(code_raw) if code_raw else "Compliance item"
        req_code = _requirement_code_for_hash(r) or code_raw or None
        rid = r.get("requirement_id")
        due_iso = _requirement_effective_due_iso(r)
        src_upd = _iso_or_none(r.get("updated_at"))
        hash_frag = f"#req={_url_quote(req_code, safe='')}" if req_code and prop_id else ""
        actions.append(_action(
            ACTION_OVERDUE_COMPLIANCE, f"Overdue: {disp}", f"{disp} is overdue at this property.",
            SCORE_OVERDUE_COMPLIANCE, SEVERITY_HIGH, related_property_id=prop_id, related_requirement_id=rid,
            requirement_code=req_code or None, due_at=due_iso, source_updated_at=src_upd,
            why_matters="Overdue statutory or contractual obligations can invalidate insurance and attract enforcement.",
            recommended_action_detail="Upload valid evidence or renew the certificate, then confirm dates.",
            recommended_url=(f"/properties/{prop_id}{hash_frag}" if prop_id else "/compliance-score"),
            recommended_action_label="Review compliance",
            portfolio_jurisdiction=r.get("jurisdiction"),
        ))

    q_exp = {"client_id": client_id, "status": "EXPIRING_SOON"}
    if property_id_filter:
        q_exp["property_id"] = property_id_filter
    exp_reqs = await db.requirements.find(q_exp).limit(limit).to_list(limit)
    for r in exp_reqs:
        ok, _eng = requirement_row_in_client_priority_stream(r, kind="expiring")
        if not ok:
            continue
        prop_id = r.get("property_id")
        code_raw = r.get("code") or r.get("requirement_type") or ""
        disp = requirement_label(code_raw) if code_raw else "Certificate"
        req_code = _requirement_code_for_hash(r) or code_raw or None
        rid = r.get("requirement_id")
        due_iso = _requirement_effective_due_iso(r)
        src_upd = _iso_or_none(r.get("updated_at"))
        hash_frag = f"#req={_url_quote(req_code, safe='')}" if req_code and prop_id else ""
        actions.append(_action(
            ACTION_CERT_EXPIRING_SOON, f"Due soon: {disp}", f"{disp} is due to expire soon; renew or upload evidence.",
            SCORE_CERT_EXPIRING_7D, SEVERITY_MEDIUM, related_property_id=prop_id, related_requirement_id=rid,
            requirement_code=req_code or None, due_at=due_iso, source_updated_at=src_upd,
            why_matters="Expiry reduces your compliance score and increases enforcement and void-risk exposure.",
            recommended_action_detail="Renew or schedule renewal and upload evidence with confirmed expiry dates.",
            recommended_url=(f"/properties/{prop_id}{hash_frag}" if prop_id else "/compliance-score"),
            recommended_action_label="Review compliance",
            portfolio_jurisdiction=r.get("jurisdiction"),
        ))

    q_miss = {"client_id": client_id, "status": {"$in": ["PENDING", "MISSING"]}}
    if property_id_filter:
        q_miss["property_id"] = property_id_filter
    miss_reqs = await db.requirements.find(q_miss).limit(limit).to_list(limit)
    for r in miss_reqs:
        if r.get("evidence_doc_id"):
            continue
        ok, _eng = requirement_row_in_client_priority_stream(r, kind="missing")
        if not ok:
            continue
        prop_id = r.get("property_id")
        code_raw = r.get("code") or r.get("requirement_type") or ""
        disp = requirement_label(code_raw) if code_raw else "Document"
        req_code = _requirement_code_for_hash(r) or code_raw or None
        rid = r.get("requirement_id")
        due_iso = _requirement_effective_due_iso(r)
        src_upd = _iso_or_none(r.get("updated_at"))
        hash_frag = f"#req={_url_quote(req_code, safe='')}" if req_code and prop_id else ""
        actions.append(_action(
            ACTION_MISSING_DOCUMENT, f"Evidence needed: {disp}", f"Required evidence for {disp} is missing.",
            SCORE_MISSING_DOCUMENT, SEVERITY_MEDIUM, related_property_id=prop_id, related_requirement_id=rid,
            requirement_code=req_code or None, due_at=due_iso, source_updated_at=src_upd,
            why_matters="Without evidence, the platform cannot confirm compliance for this obligation.",
            recommended_action_detail="Upload the certificate or statutory document and confirm extracted dates.",
            recommended_url=(f"/properties/{prop_id}{hash_frag}" if prop_id else "/documents"),
            recommended_action_label="Upload document",
            portfolio_jurisdiction=r.get("jurisdiction"),
        ))

    try:
        from services import risk_signal_service
        risk_data = await risk_signal_service.get_risk_signals_for_client(
            client_id=client_id, property_id_filter=property_id_filter, status_filter="active", limit=limit
        )
        signals = risk_data.get("signals") or risk_data.get("highPriority") or []
        for s in signals[:limit]:
            if (s.get("status") or "").lower() != "active":
                continue
            level = (s.get("risk_level") or "").lower()
            score = SCORE_HIGH_RISK_SIGNAL if level in ("high", "critical") else 55
            sig_id = s.get("signal_id") or s.get("risk_signal_id") or s.get("id")
            prop_id = s.get("property_id")
            sig_upd = _iso_or_none(s.get("updated_at") or s.get("generated_at"))
            rec_url = f"/operations/risk-signals?signal_id={sig_id}" if sig_id else "/operations/risk-signals"
            actions.append(_action(
                ACTION_RISK_SIGNAL,
                s.get("risk_type_label_client") or s.get("risk_type") or "Risk signal",
                s.get("recommended_action_client") or s.get("recommended_action") or "Review this insight and choose the next step.",
                score,
                SEVERITY_HIGH if level in ("high", "critical") else SEVERITY_MEDIUM,
                related_risk_signal_id=sig_id,
                related_property_id=prop_id,
                source_updated_at=sig_upd,
                why_matters="Early action on risk signals reduces costly failures and compliance drift.",
                recommended_action_detail=s.get("recommended_action_client") or s.get("recommended_action"),
                recommended_url=rec_url,
                recommended_action_label="Review risk signal",
            ))
    except Exception as e:
        logger.debug("Priority stream: risk signals fetch failed for client %s: %s", client_id, e)

    try:
        from services import maintenance_service as ms
        for sla_state, score, action in [
            ("breached", SCORE_WORK_ORDER_BREACHED, ACTION_WORK_ORDER_BREACHED),
            ("near_breach", SCORE_WORK_ORDER_NEAR_BREACH, ACTION_WORK_ORDER_NEAR_BREACH),
        ]:
            wo_result = await ms.list_work_orders(
                client_id=client_id, property_id=property_id_filter, sla_state=sla_state, limit=limit
            )
            for wo in (wo_result.get("work_orders") or [])[:limit]:
                wo_id = wo.get("work_order_id")
                prop_id = wo.get("property_id")
                wo_upd = _iso_or_none(wo.get("updated_at"))
                wo_url = f"/operations/work-orders?work_order_id={wo_id}" if wo_id else "/operations/work-orders"
                state_key = "breached" if sla_state == "breached" else "near_breach"
                actions.append(_action(
                    action, f"Work order — {sla_state_label(state_key, 'client')}",
                    wo.get("description") or f"Work order {str(wo_id)[:8]}…",
                    score, SEVERITY_HIGH if sla_state == "breached" else SEVERITY_MEDIUM,
                    related_work_order_id=wo_id, related_property_id=prop_id, source_updated_at=wo_upd,
                    why_matters="Missed response targets can affect tenant safety, contracts, and satisfaction.",
                    recommended_action_detail=f"Status: {work_order_status_label(wo.get('status'), 'client')}. Update the work order or reassign the contractor.",
                    recommended_url=wo_url, recommended_action_label="View work order",
                ))
    except Exception as e:
        logger.debug("Priority stream: SLA work orders fetch failed for client %s: %s", client_id, e)

    seen_wo_ids = {a.get("related_work_order_id") for a in actions if a.get("related_work_order_id")}
    try:
        from services import maintenance_service as ms
        for st in (ms.STATUS_OPEN, ms.STATUS_ASSIGNED, ms.STATUS_IN_PROGRESS):
            wo_result = await ms.list_work_orders(
                client_id=client_id, property_id=property_id_filter, status=st, sla_state=None, limit=limit
            )
            for wo in (wo_result.get("work_orders") or [])[:limit]:
                wo_id = wo.get("work_order_id")
                if not wo_id or wo_id in seen_wo_ids:
                    continue
                seen_wo_ids.add(wo_id)
                actions.append(_action(
                    ACTION_OPEN_WORK_ORDER, f"Open work order ({work_order_status_label(wo.get('status') or st, 'client')})",
                    wo.get("description") or f"Work order {str(wo_id)[:8]}…", SCORE_OPEN_WORK_ORDER, SEVERITY_MEDIUM,
                    related_work_order_id=wo_id, related_property_id=wo.get("property_id"),
                    due_at=_iso_or_none(wo.get("sla_complete_by") or wo.get("sla_respond_by")),
                    source_updated_at=_iso_or_none(wo.get("updated_at")),
                    why_matters="Open work orders should be progressed or closed to avoid SLA drift and tenant issues.",
                    recommended_action_detail=f"Status: {work_order_status_label(wo.get('status') or st, 'client')}. Assign, update, or complete the work order.",
                    recommended_url=f"/operations/work-orders?work_order_id={wo_id}",
                    recommended_action_label="View work order",
                ))
    except Exception as e:
        logger.debug("Priority stream: open work orders fetch failed for client %s: %s", client_id, e)

    try:
        from services.approval_service import list_approvals, STATUS_PENDING
        appr_data = await list_approvals(client_id=client_id, status=STATUS_PENDING, limit=limit)
        for inv in (appr_data.get("approvals") or [])[:limit]:
            inv_id = inv.get("invoice_id") or inv.get("id")
            actions.append(_action(
                ACTION_PENDING_APPROVAL, "Pending invoice approval",
                inv.get("description") or f"Invoice {str(inv_id)[:8]}…",
                SCORE_PENDING_INVOICE, SEVERITY_MEDIUM,
                related_invoice_id=inv_id, related_property_id=inv.get("property_id"),
                source_updated_at=_iso_or_none(inv.get("submitted_at") or inv.get("updated_at")),
                why_matters="Unapproved invoices block accurate spend tracking and contractor payment.",
                recommended_action_detail="Compare to benchmark, then approve, reject, or request more information.",
                recommended_url=f"/operations/approvals?invoice_id={inv_id}" if inv_id else "/operations/approvals",
                recommended_action_label="Review approval",
            ))
    except Exception as e:
        logger.debug("Priority stream: approvals fetch failed for client %s: %s", client_id, e)

    try:
        from services import maintenance_issues_service as mis
        for st in (
            mis.STATUS_OPEN, mis.STATUS_NEW, mis.STATUS_TRIAGED,
            mis.STATUS_INVESTIGATING, mis.STATUS_READY_FOR_WORK_ORDER, mis.STATUS_IN_PROGRESS,
        ):
            issues_result = await mis.list_issues(client_id=client_id, property_id=property_id_filter, status=st, limit=limit)
            for iss in (issues_result.get("issues") or [])[:limit]:
                iid = iss.get("issue_id")
                actions.append(_action(
                    ACTION_OPEN_ISSUE, "Open operational issue",
                    (iss.get("description") or "")[:200] or f"Issue {str(iid)[:8]}…",
                    SCORE_OPEN_ISSUE, SEVERITY_MEDIUM,
                    related_issue_id=iid, related_property_id=iss.get("property_id"),
                    source_updated_at=_iso_or_none(iss.get("updated_at")),
                    why_matters="Unresolved issues can escalate into property damage, complaints, or statutory risk.",
                    recommended_action_detail=f"Status: {issue_status_label(iss.get('status'), 'client')}. Triage, assign, or create a work order.",
                    recommended_url=f"/operations/issues/{iid}" if iid else "/operations/issues",
                    recommended_action_label="View issue",
                ))
    except Exception as e:
        logger.debug("Priority stream: issues fetch failed for client %s: %s", client_id, e)

    return actions

