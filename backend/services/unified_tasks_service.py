"""
Unified Tasks (Command Centre) — aggregates existing operational/compliance entities into one
normalized task list for the client portal. Prioritization and sectioning are deterministic
and server-side; the frontend renders task DTOs without re-implementing business rules.

Phase 1: read-only tasks. Phase 2: client_task_overrides + activity log (snooze, dismiss, done,
restore) merged server-side; snoozed section + habit metrics from activity.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

from database import database
from presentation.label_service import compliance_requirement_status_label, requirement_label

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
from services.catalog_compliance import get_portfolio_compliance_from_catalog
from services import client_task_state_service as client_task_state
from services.requirement_code_registry import (
    is_bookable_compliance_requirement,
    normalize_requirement_code,
    normalize_requirement_code_strict,
)
from services.compliance_requirement_engine import resolve_engine_payload_from_code
from services.requirement_action_resolver import (
    enrich_take_action_envelope_for_client,
    resolve_take_action_envelope,
    resolve_take_action_for_priority_action,
)
from services.requirement_read_model_guard import get_canonical_requirement_ids_map_for_properties
from services.requirement_client_runtime_surface import project_requirement_row_client_runtime
from services.requirement_truth import requirement_has_active_negative_actionability
from services.compliance_expiry_policy import resolve_expiring_soon_days_for_requirement
from services.today_attention_ranking import attention_rank_explanation, today_attention_sort_key
from utils.compliance_fanout_log import compliance_fanout_extra

logger = logging.getLogger(__name__)


def _canonical_take_action_is_standard_document_navigate(
    take_action: Dict[str, Any],
    *,
    property_id: str,
    requirement_id: str,
) -> bool:
    """
    True when canonical primary CTA matches the hardcoded tenant_request document-vault deep link
    (navigate to /documents with this property_id + requirement_id). Used for mismatch logging only.
    """
    if not isinstance(take_action, dict) or take_action.get("suppressed"):
        return True
    pri = take_action.get("primary")
    if not isinstance(pri, dict):
        return True
    if pri.get("external") is True:
        return False
    kind = str(pri.get("kind") or "").strip().lower()
    if kind in ("guided_evidence_resolution", "direct_evidence_action"):
        return False
    if kind not in ("", "navigate"):
        return False
    route = str(pri.get("route") or "").strip()
    if "/documents" not in route:
        return False
    if property_id and property_id not in route:
        return False
    if requirement_id and requirement_id not in route:
        return False
    return True

# --- Display / domain mapping: priority action -> unified source_type ---
ACTION_TO_SOURCE = {
    ACTION_OVERDUE_COMPLIANCE: "requirement",
    ACTION_CERT_EXPIRING_SOON: "requirement",
    ACTION_MISSING_DOCUMENT: "requirement",
    ACTION_RISK_SIGNAL: "risk_signal",
    ACTION_WORK_ORDER_NEAR_BREACH: "work_order",
    ACTION_WORK_ORDER_BREACHED: "work_order",
    ACTION_OPEN_WORK_ORDER: "work_order",
    ACTION_PENDING_APPROVAL: "approval",
    ACTION_OPEN_ISSUE: "issue",
}


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _property_label(p: Dict[str, Any]) -> str:
    if p.get("nickname"):
        return str(p["nickname"]).strip()
    a1 = (p.get("address_line_1") or "").strip()
    pc = (p.get("postcode") or "").strip()
    if a1 and pc:
        return f"{a1}, {pc}"
    if a1:
        return a1
    if pc:
        return pc
    return p.get("property_id") or ""


def _due_and_overdue(due_at: Optional[str], now: datetime) -> Tuple[Optional[str], Optional[int]]:
    due = _parse_dt(due_at)
    if not due:
        return (due_at, None)
    due_date = due.date()
    today = now.date()
    delta = (today - due_date).days
    overdue_days = delta if delta > 0 else None
    return (due_at, overdue_days)


def _urgency_level(action_type: str, severity: str, overdue_days: Optional[int]) -> str:
    if overdue_days and overdue_days > 0:
        return "critical" if action_type == ACTION_OVERDUE_COMPLIANCE or severity == "critical" else "high"
    if action_type == ACTION_WORK_ORDER_BREACHED or severity == "critical":
        return "critical"
    if severity == "high" or action_type == ACTION_OVERDUE_COMPLIANCE:
        return "high"
    if severity == "medium":
        return "medium"
    return "low"


def _impact_label(action_type: str, severity: str) -> str:
    if action_type in (ACTION_OVERDUE_COMPLIANCE, ACTION_WORK_ORDER_BREACHED):
        return "High compliance / operations impact"
    if action_type == ACTION_RISK_SIGNAL and severity in ("high", "critical"):
        return "Elevated portfolio risk"
    if action_type == ACTION_PENDING_APPROVAL:
        return "Blocks payment and spend visibility"
    if action_type in (ACTION_WORK_ORDER_NEAR_BREACH, ACTION_OPEN_WORK_ORDER):
        return "Contractor response times"
    if action_type == ACTION_OPEN_ISSUE:
        return "Active maintenance issue"
    return "Compliance or operational attention"


def _impact_score(action_type: str, priority: int, overdue_days: Optional[int]) -> int:
    """
    Deterministic composite for sorting (higher = more important).
    Weights: overdue > SLA breach > priority score from priority_actions engine.
    """
    base = int(priority or 0)
    if overdue_days and overdue_days > 0:
        base += min(50, 10 + overdue_days * 2)
    if action_type == ACTION_WORK_ORDER_BREACHED:
        base += 25
    if action_type == ACTION_OVERDUE_COMPLIANCE:
        base += 20
    if action_type == ACTION_PENDING_APPROVAL:
        base += 5
    return min(200, base)


def _secondary_nav_label(source_type: str) -> str:
    return {
        "requirement": "View requirement",
        "risk_signal": "View risk signal",
        "work_order": "View job details",
        "issue": "View issue",
        "approval": "View approval",
        "tenant_message": "Open tenant inbox",
        "priority_action": "View details",
    }.get(source_type, "View details")


def _primary_action_fields(
    a: Dict[str, Any],
    source_type: str,
    *,
    compliance_engine: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str, bool, Optional[str], Optional[str]]:
    """
    primary_action_type, label, url, inline_supported, secondary_label, secondary_url
    Requirement-backed compliance actions use requirement_action_resolver (single primary CTA contract).
    """
    url = (a.get("recommended_url") or "").strip() or "/dashboard"
    label = (a.get("recommended_action_label") or "View").strip()
    at = a.get("action_type") or ""
    inline = False
    sec_label: Optional[str] = None
    sec_url: Optional[str] = None

    if at in (ACTION_MISSING_DOCUMENT, ACTION_OVERDUE_COMPLIANCE, ACTION_CERT_EXPIRING_SOON) and source_type == "requirement":
        resolved = resolve_take_action_for_priority_action(a, compliance_engine=compliance_engine)
        ta_canon = a.get("canonical_take_action") if isinstance(a.get("canonical_take_action"), dict) else {}
        pri_c = ta_canon.get("primary") if isinstance(ta_canon.get("primary"), dict) else {}
        sec_c = ta_canon.get("secondary") if isinstance(ta_canon.get("secondary"), dict) else {}
        # Stream D B2: when canonical_take_action.primary exists, prefer canonical label/route; empty canonical
        # route means no gap recommended_url fallback (guided/direct/resolver-empty stay off gap templates).
        has_canonical_primary = bool(ta_canon) and bool(pri_c)
        if has_canonical_primary:
            canon_label = str(pri_c.get("label") or "").strip()
            canon_route = str(pri_c.get("route") or "").strip()
            if canon_label:
                plabel = canon_label
            else:
                rl = str(resolved.get("primary_action_label") or "").strip()
                plabel = rl if rl else "View"
            if canon_route:
                purl = canon_route
            else:
                rp = resolved.get("primary_action_url")
                purl = "" if rp is None else str(rp)
        else:
            plabel = str(resolved.get("primary_action_label") or label)
            raw_purl = resolved.get("primary_action_url")
            purl = str(url) if raw_purl is None else str(raw_purl)
        slabel = resolved.get("secondary_action_label")
        surl = resolved.get("secondary_action_url")
        if sec_c.get("label"):
            slabel = str(sec_c.get("label") or slabel)
        if sec_c.get("route"):
            surl = str(sec_c.get("route") or surl)
        return (
            str(resolved.get("primary_action_type") or "upload_evidence"),
            plabel,
            purl,
            False,
            slabel,
            surl,
        )
    if at in (ACTION_MISSING_DOCUMENT, ACTION_OVERDUE_COMPLIANCE, ACTION_CERT_EXPIRING_SOON):
        if compliance_engine and not compliance_engine.get("requires_document_evidence", True):
            primary_type = "view_requirement"
            inline = False
        else:
            primary_type = "upload_evidence"
            inline = False
    elif at == ACTION_RISK_SIGNAL:
        primary_type = "risk_follow_up"
        inline = True
    elif at == ACTION_PENDING_APPROVAL:
        primary_type = "review_approval"
        inline = False
    elif at in (ACTION_WORK_ORDER_BREACHED, ACTION_WORK_ORDER_NEAR_BREACH, ACTION_OPEN_WORK_ORDER):
        primary_type = "work_order"
        inline = False
    elif at == ACTION_OPEN_ISSUE:
        primary_type = "issue"
        inline = False
    else:
        primary_type = source_type
    return primary_type, label, url, inline, sec_label, sec_url


def _section_for_action(
    action_type: str,
    severity: str,
    overdue_days: Optional[int],
) -> str:
    """Assign one section: urgent | upcoming | in_progress."""
    if action_type == ACTION_OVERDUE_COMPLIANCE or action_type == ACTION_WORK_ORDER_BREACHED:
        return "urgent"
    if overdue_days and overdue_days > 0:
        return "urgent"
    if action_type == ACTION_RISK_SIGNAL:
        return "urgent"
    if action_type == ACTION_OPEN_ISSUE and severity in ("high", "critical", "urgent"):
        return "urgent"
    if action_type in (ACTION_CERT_EXPIRING_SOON, ACTION_MISSING_DOCUMENT, ACTION_WORK_ORDER_NEAR_BREACH):
        return "upcoming"
    if action_type == ACTION_OPEN_WORK_ORDER:
        return "in_progress"
    if action_type == ACTION_PENDING_APPROVAL:
        return "in_progress"
    if action_type == ACTION_OPEN_ISSUE:
        return "in_progress"
    return "upcoming"


def _compliance_execution_booking_meta(action_type: str, a: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Payload for POST /compliance-execution/work-orders/book when requirement is bookable.
    """
    if action_type not in (ACTION_OVERDUE_COMPLIANCE, ACTION_CERT_EXPIRING_SOON, ACTION_MISSING_DOCUMENT):
        return None
    prop_id = (a.get("related_property_id") or "").strip()
    rid = (a.get("related_requirement_id") or "").strip()
    code_raw = a.get("requirement_code")
    if not prop_id or not rid or code_raw is None or not str(code_raw).strip():
        return None
    canon, err = normalize_requirement_code_strict(str(code_raw).strip())
    eligible = bool(canon and not err and is_bookable_compliance_requirement(canon))
    if action_type == ACTION_CERT_EXPIRING_SOON:
        purpose = "renewal"
    elif action_type == ACTION_MISSING_DOCUMENT:
        purpose = "certification"
    else:
        purpose = "inspection"
    eng = resolve_engine_payload_from_code(str(code_raw or "").strip())
    eligible = bool(eligible and eng.get("creates_compliance_job"))
    return {
        "eligible": eligible,
        "property_id": prop_id,
        "requirement_code": canon or str(code_raw).strip(),
        "linked_property_requirement_id": rid,
        "compliance_purpose": purpose,
        "compliance_generated_from": "requirement",
    }


def _stable_source_id(a: Dict[str, Any], source_type: str) -> str:
    if source_type == "requirement" and a.get("related_requirement_id"):
        return str(a["related_requirement_id"])
    if source_type == "risk_signal" and a.get("related_risk_signal_id"):
        return str(a["related_risk_signal_id"])
    if source_type == "work_order" and a.get("related_work_order_id"):
        return str(a["related_work_order_id"])
    if source_type == "approval" and a.get("related_invoice_id"):
        return str(a["related_invoice_id"])
    if source_type == "issue" and a.get("related_issue_id"):
        return str(a["related_issue_id"])
    pid = a.get("related_property_id") or ""
    return f"fallback-{a.get('action_type')}-{hash((a.get('title'), pid))}"


def _action_to_task(
    a: Dict[str, Any],
    property_labels: Dict[str, str],
    now: datetime,
) -> Dict[str, Any]:
    action_type = a.get("action_type") or ""
    source_type = ACTION_TO_SOURCE.get(action_type, "priority_action")
    source_id = _stable_source_id(a, source_type)
    task_id = f"{source_type}:{source_id}"
    prop_id = a.get("related_property_id")
    related_rid = (a.get("related_requirement_id") or "").strip() or None
    prop_label = property_labels.get(prop_id or "", "") if prop_id else ""
    due_at, overdue_days = _due_and_overdue(a.get("due_at"), now)
    severity = (a.get("severity") or "medium").lower()
    urgency = _urgency_level(action_type, severity, overdue_days)
    section = _section_for_action(action_type, severity, overdue_days)
    req_engine: Optional[Dict[str, Any]] = None
    if source_type == "requirement":
        req_engine = resolve_engine_payload_from_code(str(a.get("requirement_code") or "").strip())
    pri_type, pri_label, pri_url, inline_ok, sec_l, sec_u = _primary_action_fields(
        a, source_type, compliance_engine=req_engine
    )
    is_req_stream = source_type == "requirement" and action_type in (
        ACTION_MISSING_DOCUMENT,
        ACTION_OVERDUE_COMPLIANCE,
        ACTION_CERT_EXPIRING_SOON,
    )
    if is_req_stream:
        secondary_label, secondary_url = sec_l, sec_u
    elif sec_l and sec_u:
        secondary_label, secondary_url = sec_l, sec_u
    else:
        secondary_label, secondary_url = _secondary_nav_label(source_type), pri_url
    freshness = a.get("source_updated_at")

    task_metadata: Dict[str, Any] = {
        "action_type": action_type,
        "severity": severity,
        "timing_label": None,
        "requirement_code": a.get("requirement_code"),
        "related_risk_signal_id": a.get("related_risk_signal_id"),
        "related_invoice_id": a.get("related_invoice_id"),
        "related_work_order_id": a.get("related_work_order_id"),
        "related_issue_id": a.get("related_issue_id"),
    }
    if req_engine is not None:
        task_metadata["compliance_engine"] = req_engine
    ce_book = _compliance_execution_booking_meta(action_type, a)
    if ce_book:
        task_metadata["compliance_execution_booking"] = ce_book
    gk = a.get("gap_key")
    if gk:
        task_metadata["gap_key"] = str(gk)
    if action_type == ACTION_PENDING_APPROVAL:
        task_metadata["domain"] = "billing"
        task_metadata["billing_milestone_type"] = "pending_invoice_approval"

    if is_req_stream and prop_id and related_rid:
        task_metadata["requirement_id"] = related_rid
        task_metadata["property_jurisdiction"] = a.get("jurisdiction")
        if a.get("semantic_state") is not None:
            task_metadata["semantic_state"] = a.get("semantic_state")
        for k in ("workflow_class", "guidance_target", "allowed_evidence_modes"):
            if a.get(k) is not None:
                task_metadata[k] = a.get(k)
        if isinstance(a.get("registry_metadata"), dict) and a.get("registry_metadata"):
            task_metadata["registry_metadata"] = dict(a["registry_metadata"])
        if isinstance(a.get("canonical_take_action"), dict) and a.get("canonical_take_action"):
            task_metadata["take_action"] = dict(a["canonical_take_action"])
            if a.get("canonical_requirement_action_type"):
                task_metadata["requirement_action_type"] = a.get("canonical_requirement_action_type")
        else:
            eng = req_engine or {}
            syn: Dict[str, Any] = {
                "requirement_id": related_rid,
                "property_id": prop_id,
                "requirement_code": a.get("requirement_code"),
                "requirement_type": a.get("requirement_code"),
                "jurisdiction": a.get("jurisdiction"),
            }
            for k, v in eng.items():
                if v is not None:
                    syn[k] = v
            rm = a.get("registry_metadata")
            if isinstance(rm, dict) and rm:
                syn["registry_metadata"] = {**(syn.get("registry_metadata") or {}), **rm}
            if a.get("display_label") is not None:
                syn["display_label"] = a.get("display_label")
            env_take = enrich_take_action_envelope_for_client(
                resolve_take_action_envelope(
                    syn,
                    property_id=prop_id,
                    property_jurisdiction=a.get("jurisdiction"),
                ),
                syn,
            )
            task_metadata["take_action"] = env_take.get("take_action")
            task_metadata["requirement_action_type"] = env_take.get("action_type")
            for k in ("workflow_class", "guidance_target", "allowed_evidence_modes"):
                if env_take.get(k) is not None:
                    task_metadata[k] = env_take[k]
        if isinstance(a.get("evidence_completeness"), dict) and a.get("evidence_completeness"):
            task_metadata["evidence_completeness"] = dict(a["evidence_completeness"])
        if isinstance(a.get("evidence_authority"), dict) and a.get("evidence_authority"):
            task_metadata["evidence_authority"] = dict(a["evidence_authority"])
        if isinstance(a.get("requirement_display"), dict) and a.get("requirement_display"):
            task_metadata["requirement_display"] = dict(a["requirement_display"])
        else:
            from presentation.requirement_display_contract import build_requirement_display

            _canon = normalize_requirement_code(str(task_metadata.get("requirement_code") or "").strip())
            syn_rd = {
                "requirement_code": task_metadata.get("requirement_code"),
                "requirement_type": task_metadata.get("requirement_type") or task_metadata.get("requirement_code"),
                "canonical_requirement_code": _canon,
                "take_action": task_metadata.get("take_action"),
            }
            task_metadata["requirement_display"] = build_requirement_display(syn_rd, audience="client")

    timing_label = None
    if overdue_days and overdue_days > 0:
        timing_label = f"Overdue by {overdue_days} day{'s' if overdue_days != 1 else ''}"
    elif due_at:
        d = _parse_dt(due_at)
        if d:
            days = (d.date() - now.date()).days
            if days > 0:
                timing_label = f"Due in {days} day{'s' if days != 1 else ''}"
            elif days == 0:
                timing_label = "Due today"

    task_metadata["timing_label"] = timing_label

    out_task: Dict[str, Any] = {
        "id": task_id,
        "source_type": source_type,
        "source_id": source_id,
        "source_entity_type": source_type,
        "source_entity_id": source_id,
        "action_context_type": pri_type,
        "primary_recommended_action": pri_label,
        "title": a.get("title") or "Task",
        "description": (a.get("description") or "").strip(),
        "property_id": prop_id,
        "property_label": prop_label or None,
        "urgency_level": urgency,
        "due_date": due_at,
        "overdue_days": overdue_days,
        "impact_label": _impact_label(action_type, severity),
        "impact_score": _impact_score(action_type, int(a.get("priority") or 0), overdue_days),
        "status": "open",
        "section": section,
        "primary_action_type": pri_type,
        "primary_action_label": pri_label,
        "primary_action_url": pri_url,
        "inline_action_supported": inline_ok,
        "secondary_action_label": secondary_label,
        "secondary_action_url": secondary_url,
        "metadata": task_metadata,
        "why_matters": a.get("why_matters"),
        "recommended_action": a.get("recommended_action_detail") or a.get("description"),
        "freshness_timestamp": freshness,
        "created_at": freshness,
        "updated_at": freshness,
        "filter_tags": _filter_tags(source_type, action_type, overdue_days),
    }
    if source_type == "requirement" and related_rid:
        out_task["requirement_id"] = related_rid
        jur = a.get("jurisdiction")
        if jur:
            out_task["jurisdiction"] = jur
            out_task["property_jurisdiction"] = jur
    return out_task


def _filter_tags(source_type: str, action_type: str, overdue_days: Optional[int]) -> List[str]:
    tags = []
    if source_type == "requirement" or action_type in (
        ACTION_OVERDUE_COMPLIANCE,
        ACTION_CERT_EXPIRING_SOON,
        ACTION_MISSING_DOCUMENT,
    ):
        tags.append("compliance")
    if source_type in ("issue", "work_order"):
        tags.append("operations")
    if source_type == "approval":
        tags.append("approvals")
    if action_type == ACTION_PENDING_APPROVAL:
        tags.append("billing")
    if source_type == "risk_signal":
        tags.append("risks")
    if overdue_days and overdue_days > 0:
        tags.append("overdue")
    return list(dict.fromkeys(tags))


async def _tenant_message_tasks(
    client_id: str,
    property_id_filter: Optional[str],
    limit: int = 12,
) -> List[Dict[str, Any]]:
    """
    Surface recent tenant → landlord portal messages on the unified inbox (Today / priorities).
    """
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id}
    if property_id_filter:
        q["property_id"] = property_id_filter
    try:
        cur = (
            db.tenant_messages.find(
                q,
                {
                    "_id": 0,
                    "message_id": 1,
                    "property_id": 1,
                    "property_address": 1,
                    "subject": 1,
                    "message": 1,
                    "tenant_name": 1,
                    "created_at": 1,
                },
            )
            .sort("created_at", -1)
            .limit(max(1, min(limit, 25)))
        )
        rows = await cur.to_list(length=25)
    except Exception as e:
        logger.debug("unified_tasks: tenant_messages load failed: %s", e)
        return []

    if not rows:
        return []

    prop_ids = [r.get("property_id") for r in rows if r.get("property_id")]
    labels = await _load_property_labels(client_id, [str(x) for x in prop_ids if x])
    out: List[Dict[str, Any]] = []
    for r in rows:
        mid = r.get("message_id")
        if not mid:
            continue
        pid = r.get("property_id")
        created = _parse_dt(r.get("created_at"))
        freshness = created.isoformat() if created else None
        subj = (r.get("subject") or "Tenant message").strip()
        tenant_name = (r.get("tenant_name") or "Tenant").strip()
        preview = (r.get("message") or "")[:160]
        title = f"Tenant message: {subj}"
        desc = f"From {tenant_name}. {preview}".strip()
        out.append({
            "id": f"tenant_message:{mid}",
            "source_type": "tenant_message",
            "source_id": str(mid),
            "source_entity_type": "tenant_message",
            "source_entity_id": str(mid),
            "action_context_type": "view",
            "primary_recommended_action": "Open tenant inbox",
            "title": title,
            "description": desc,
            "property_id": pid,
            "property_label": labels.get(pid or "") if pid else (r.get("property_address") or None),
            "urgency_level": "medium",
            "due_date": None,
            "overdue_days": None,
            "impact_label": "Tenant communication",
            "impact_score": 52,
            "status": "open",
            "section": "in_progress",
            "primary_action_type": "view",
            "primary_action_label": "Open tenant inbox",
            "primary_action_url": "/tenants",
            "inline_action_supported": False,
            "secondary_action_label": None,
            "secondary_action_url": None,
            "metadata": {
                "action_type": "tenant_contact_landlord",
                "message_id": str(mid),
            },
            "why_matters": "Tenants expect a timely response when they use the portal.",
            "recommended_action": "Review the message and reply or arrange follow-up.",
            "freshness_timestamp": freshness,
            "created_at": freshness,
            "updated_at": freshness,
            "filter_tags": ["tenant", "operations"],
        })
    return out


async def _load_property_labels(client_id: str, property_ids: List[str]) -> Dict[str, str]:
    if not property_ids:
        return {}
    db = database.get_db()
    cursor = db.properties.find(
        {"client_id": client_id, "property_id": {"$in": list(set(property_ids))}},
        {"_id": 0, "property_id": 1, "nickname": 1, "address_line_1": 1, "postcode": 1},
    )
    out: Dict[str, str] = {}
    async for p in cursor:
        out[p["property_id"]] = _property_label(p)
    return out


async def _tenant_request_tasks(
    client_id: str,
    property_id_filter: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Surface actionable tenant certificate requests in unified tasks so dashboard and today
    priorities derive from the same command-center read model.
    """
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id, "status": {"$in": ["PENDING", "IN_PROGRESS"]}}
    if property_id_filter:
        q["property_id"] = property_id_filter
    try:
        rows = await db.tenant_requests.find(
            q,
            {
                "_id": 0,
                "request_id": 1,
                "property_id": 1,
                "status": 1,
                "requested_doc_type": 1,
                "requirement_id": 1,
                "requirement_code": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        ).sort("updated_at", -1).limit(max(1, min(int(limit), 50))).to_list(length=max(1, min(int(limit), 50)))
    except Exception as e:
        logger.debug("unified_tasks: tenant_requests load failed: %s", e)
        return []

    prop_ids = [str(r.get("property_id")) for r in rows if r.get("property_id")]
    labels = await _load_property_labels(client_id, prop_ids)
    out: List[Dict[str, Any]] = []
    for r in rows:
        rid = str(r.get("request_id") or "").strip()
        if not rid:
            continue
        prop_id = str(r.get("property_id") or "").strip() or None
        req_id = str(r.get("requirement_id") or "").strip() or None
        req_code = str(r.get("requirement_code") or r.get("requested_doc_type") or "").strip()
        status = str(r.get("status") or "").upper()
        in_prog = status == "IN_PROGRESS"
        title = f"Tenant certificate request: {requirement_label(req_code) if req_code else 'Certificate'}"
        metadata: Dict[str, Any] = {
            "domain": "tenant",
            "tenant_request_id": rid,
            "requirement_id": req_id,
            "requirement_code": req_code or None,
            "related_property_id": prop_id,
        }
        if prop_id and req_id:
            try:
                req_row = await db.requirements.find_one(
                    {"requirement_id": req_id, "property_id": prop_id, "client_id": client_id},
                    {"_id": 0},
                )
                if isinstance(req_row, dict) and req_row.get("requirement_id"):
                    pj = str(req_row.get("jurisdiction") or "").strip() or None
                    env = enrich_take_action_envelope_for_client(
                        resolve_take_action_envelope(
                            req_row,
                            property_id=prop_id,
                            property_jurisdiction=pj,
                        ),
                        req_row,
                    )
                    ta = env.get("take_action")
                    if isinstance(ta, dict) and ta:
                        metadata["take_action"] = ta
                        for k in ("workflow_class", "guidance_target", "allowed_evidence_modes"):
                            if env.get(k) is not None:
                                metadata[k] = env[k]
                        # Convergence pass-through: preserve requirement-facing semantic contract fields
                        # that are already available on canonical requirement rows.
                        for key in ("semantic_state", "requirement_display", "evidence_authority", "evidence_completeness"):
                            val = req_row.get(key)
                            if isinstance(val, dict) and val:
                                metadata[key] = dict(val)
                            elif key == "semantic_state" and val is not None:
                                metadata[key] = val
                        if not _canonical_take_action_is_standard_document_navigate(
                            ta, property_id=prop_id, requirement_id=req_id
                        ):
                            pri = ta.get("primary") if isinstance(ta.get("primary"), dict) else {}
                            kind = str(pri.get("kind") or "").strip() or "none"
                            logger.warning(
                                "tenant_request unified task: hardcoded primary CTA unchanged; "
                                "canonical take_action is not standard document navigate (kind=%s)",
                                kind,
                                extra=compliance_fanout_extra(
                                    op="tenant_request_cta",
                                    stage="partial",
                                    client_id=client_id,
                                    property_id=prop_id,
                                    requirement_id=req_id,
                                    correlation_id=f"tenant_request:{rid}",
                                    trigger_reason="canonical_primary_non_standard_document_navigate",
                                ),
                            )
            except Exception as exc:
                logger.debug("unified_tasks: tenant_request take_action metadata enrich failed: %s", exc)

        out.append(
            {
                "id": f"tenant_request:{rid}",
                "source_type": "tenant_request",
                "source_id": rid,
                "source_entity_type": "tenant_request",
                "source_entity_id": rid,
                "property_id": prop_id,
                "requirement_id": req_id,
                "work_order_id": None,
                "property_label": labels.get(prop_id) if prop_id else None,
                "title": title,
                "description": "Tenant is waiting for compliance evidence or a compliance job.",
                "section": "in_progress" if in_prog else "upcoming",
                "urgency_level": "medium" if in_prog else "low",
                "impact_score": 46 if in_prog else 34,
                "due_date": None,
                "overdue_days": None,
                "primary_action_type": "upload_evidence",
                "primary_action_label": "Upload document",
                "primary_action_url": (
                    f"/documents?property_id={prop_id}&requirement_id={req_id}" if (prop_id and req_id) else "/tenants"
                ),
                "secondary_action_label": "View details",
                "secondary_action_url": "/tenants",
                "action_context_type": "tenant_request_certificate",
                "primary_recommended_action": "Upload document",
                "metadata": metadata,
                "filter_tags": ["tenant", "compliance"],
            }
        )
    return out


async def _recently_completed_tasks(client_id: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Lightweight completion feed from requirements and invoices (last state transitions)."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    since_req = now - timedelta(days=7)
    since_inv = now - timedelta(days=7)
    out: List[Dict[str, Any]] = []

    req_cursor = db.requirements.find(
        {
            "client_id": client_id,
            "updated_at": {"$gte": since_req},
        },
        {"_id": 0},
    ).sort("updated_at", -1).limit(limit * 3)
    raw_reqs = await req_cursor.to_list(length=limit * 3)
    props_surface = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(500)
    client_row_ut = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    raw_reqs = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=raw_reqs,
        client_doc=client_row_ut,
        properties=props_surface,
    )
    reqs = []
    for r in raw_reqs:
        proj = project_requirement_row_client_runtime(r)
        st = proj.get("status")
        if str(st or "").upper() in ("COMPLIANT", "VALID"):
            reqs.append({**r, "status": st})
        if len(reqs) >= limit:
            break
    prop_ids = [r.get("property_id") for r in reqs if r.get("property_id")]
    labels = await _load_property_labels(client_id, [x for x in prop_ids if x])

    for r in reqs:
        rid = r.get("requirement_id")
        pid = r.get("property_id")
        code = r.get("code") or r.get("requirement_type")
        disp = requirement_label(code) if code else "Requirement"
        upd = _parse_dt(r.get("updated_at"))
        out.append({
            "id": f"requirement_completed:{rid}",
            "source_type": "requirement",
            "source_id": str(rid),
            "source_entity_type": "requirement",
            "source_entity_id": str(rid),
            "action_context_type": "view",
            "primary_recommended_action": "View property",
            "title": f"Requirement satisfied: {disp}",
            "description": f"Status is now {compliance_requirement_status_label(r.get('status') or 'COMPLIANT')}.",
            "property_id": pid,
            "property_label": labels.get(pid or "") if pid else None,
            "urgency_level": "low",
            "due_date": None,
            "overdue_days": None,
            "impact_label": "Compliance",
            "impact_score": 10,
            "status": "completed",
            "section": "recently_completed",
            "primary_action_type": "view",
            "primary_action_label": "View property",
            "primary_action_url": f"/properties/{pid}" if pid else "/requirements",
            "inline_action_supported": False,
            "secondary_action_label": None,
            "secondary_action_url": None,
            "metadata": {"action_type": "requirement_satisfied"},
            "why_matters": None,
            "recommended_action": None,
            "freshness_timestamp": upd.isoformat() if upd else None,
            "created_at": upd.isoformat() if upd else None,
            "updated_at": upd.isoformat() if upd else None,
            "filter_tags": ["compliance"],
        })

    inv_cursor = (
        db.invoices.find(
            {
                "client_id": client_id,
                "status": {"$in": ["approved", "paid"]},
                "$or": [
                    {"reviewed_at": {"$gte": since_inv}},
                    {"paid_at": {"$gte": since_inv}},
                ],
            },
            {"_id": 0, "invoice_id": 1, "property_id": 1, "reference": 1, "status": 1, "reviewed_at": 1, "paid_at": 1},
        )
        .sort([("paid_at", -1), ("reviewed_at", -1)])
        .limit(8)
    )
    invs = await inv_cursor.to_list(length=8)
    prop_ids2 = [i.get("property_id") for i in invs if i.get("property_id")]
    labels2 = await _load_property_labels(client_id, [x for x in prop_ids2 if x])
    for inv in invs:
        iid = inv.get("invoice_id")
        pid = inv.get("property_id")
        ref = inv.get("reference") or str(iid)[:8]
        st = inv.get("status")
        title = f"Invoice {st}: {ref}"
        pt = _parse_dt(inv.get("paid_at")) or _parse_dt(inv.get("reviewed_at"))
        out.append({
            "id": f"invoice_{st}:{iid}",
            "source_type": "approval",
            "source_id": str(iid),
            "source_entity_type": "approval",
            "source_entity_id": str(iid),
            "action_context_type": "review_approval",
            "primary_recommended_action": "View in approvals",
            "title": title,
            "description": "Approval workspace update.",
            "property_id": pid,
            "property_label": labels2.get(pid or "") if pid else None,
            "urgency_level": "low",
            "due_date": None,
            "overdue_days": None,
            "impact_label": "Spend / approvals",
            "impact_score": 8,
            "status": "completed",
            "section": "recently_completed",
            "primary_action_type": "review_approval",
            "primary_action_label": "View in approvals",
            "primary_action_url": f"/operations/approvals?invoice_id={iid}" if iid else "/operations/approvals",
            "inline_action_supported": False,
            "secondary_action_label": None,
            "secondary_action_url": None,
            "metadata": {"action_type": f"invoice_{st}"},
            "why_matters": None,
            "recommended_action": None,
            "freshness_timestamp": pt.isoformat() if pt else None,
            "created_at": pt.isoformat() if pt else None,
            "updated_at": pt.isoformat() if pt else None,
            "filter_tags": ["approvals", "operations"],
        })

    out.sort(key=lambda t: (t.get("updated_at") or ""), reverse=True)
    return out[:limit]


async def _freshness_block(client_id: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    score_at = None
    try:
        catalog = await get_portfolio_compliance_from_catalog(client_id)
        if catalog:
            score_at = catalog.get("updated_at")
    except Exception as e:
        logger.debug("unified_tasks: portfolio compliance freshness failed: %s", e)

    risk_at = None
    try:
        db = database.get_db()
        doc = await db.risk_signals.find_one(
            {"client_id": client_id},
            sort=[("updated_at", -1)],
            projection={"_id": 0, "updated_at": 1, "generated_at": 1},
        )
        if doc:
            risk_at = doc.get("updated_at") or doc.get("generated_at")
            if hasattr(risk_at, "isoformat"):
                risk_at = risk_at.isoformat()
    except Exception as e:
        logger.debug("unified_tasks: risk freshness failed: %s", e)

    auto_score = None
    auto_risk = None
    try:
        from services.automation_status_service import get_record as _auto_get

        rec = await _auto_get(client_id)
        auto_score = rec.get("last_score_recalc_at")
        auto_risk = rec.get("last_risk_refresh_at")
    except Exception as e:
        logger.debug("unified_tasks: automation_status freshness failed: %s", e)

    return {
        "score_updated_at": score_at,
        "risk_signals_updated_at": risk_at,
        "last_automation_score_recalc_at": auto_score,
        "last_automation_risk_refresh_at": auto_risk,
        "tasks_refreshed_at": now,
    }


def _sort_tasks(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """ATTENTION_AUTHORITY_RULES ordering, then impact_score / title / id tie-breakers."""
    for t in items:
        t["attention_authority"] = attention_rank_explanation(t)
    return sorted(items, key=today_attention_sort_key)


def _task_requirement_identity(task: Dict[str, Any]) -> Tuple[str, str]:
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    pid = str(task.get("property_id") or meta.get("related_property_id") or "").strip()
    rid = str(
        task.get("requirement_id")
        or task.get("source_entity_id")
        or task.get("source_id")
        or meta.get("requirement_id")
        or ""
    ).strip()
    return pid, rid


async def _enforce_canonical_requirement_task_guard(
    *,
    client_id: str,
    tasks: List[Dict[str, Any]],
    db: Any,
) -> List[Dict[str, Any]]:
    """
    Priority-1 trust guard:
    If a task is requirement-like, it must map to a canonical materialised requirement_id for that property.
    Invalid rows are reclassified as diagnostics (not requirement cards) and kept visible.
    """
    if not tasks:
        return tasks
    candidate_idx: List[int] = []
    property_ids: Set[str] = set()
    for i, t in enumerate(tasks):
        st = str(t.get("source_type") or "").strip().lower()
        if st != "requirement":
            continue
        pid, _rid = _task_requirement_identity(t)
        if pid:
            property_ids.add(pid)
        candidate_idx.append(i)
    if not candidate_idx:
        return tasks

    canonical_map = await get_canonical_requirement_ids_map_for_properties(client_id, property_ids, db=db)
    client_doc: Dict[str, Any] = {}
    prop_by_id: Dict[str, Dict[str, Any]] = {}
    row_by_requirement_id: Dict[str, Dict[str, Any]] = {}
    try:
        client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
        props = await db.properties.find(
            {"client_id": client_id, "property_id": {"$in": list(property_ids)}},
            {"_id": 0, "property_id": 1, "jurisdiction": 1, "tenancy_active": 1, "furnished": 1, "is_hmo": 1},
        ).to_list(length=max(1, len(property_ids) * 2))
        prop_by_id = {str(p.get("property_id") or "").strip(): p for p in props if str(p.get("property_id") or "").strip()}
        candidate_requirement_ids: Set[str] = set()
        for i in candidate_idx:
            pid, rid = _task_requirement_identity(tasks[i])
            if pid and rid and rid in (canonical_map.get(pid) or set()):
                candidate_requirement_ids.add(rid)
        requirement_rows = await db.requirements.find(
            {"client_id": client_id, "requirement_id": {"$in": list(candidate_requirement_ids)}},
            {"_id": 0},
        ).to_list(length=max(1, len(candidate_requirement_ids) * 2))
        for rr in requirement_rows:
            rid = str(rr.get("requirement_id") or "").strip()
            pid = str(rr.get("property_id") or "").strip()
            if rid and pid and rid in (canonical_map.get(pid) or set()):
                row_by_requirement_id[rid] = project_requirement_row_client_runtime(rr)
    except Exception as e:
        logger.debug("unified_tasks: lifecycle requirement row load skipped: %s", e)

    out: List[Dict[str, Any]] = []
    for i, t in enumerate(tasks):
        if i not in candidate_idx:
            out.append(t)
            continue
        pid, rid = _task_requirement_identity(t)
        valid = bool(pid and rid and rid in (canonical_map.get(pid) or set()))
        if valid:
            req_row = row_by_requirement_id.get(rid)
            if isinstance(req_row, dict):
                window_days = resolve_expiring_soon_days_for_requirement(
                    req_row,
                    property_doc=prop_by_id.get(pid) if isinstance(prop_by_id.get(pid), dict) else None,
                    client_doc=client_doc if isinstance(client_doc, dict) else None,
                )
                if not requirement_has_active_negative_actionability(
                    req_row,
                    now=datetime.now(timezone.utc),
                    expiring_window_days=window_days,
                ):
                    logger.info(
                        "unified_tasks: dropped non-actionable requirement task by lifecycle guard",
                        extra=compliance_fanout_extra(
                            op="requirement_lifecycle_guard",
                            stage="partial",
                            client_id=client_id,
                            property_id=pid or None,
                            requirement_id=rid or None,
                            correlation_id=str(t.get("id") or ""),
                            trigger_reason="non_actionable_valid_requirement",
                        ),
                    )
                    continue
            out.append(t)
            continue

        tt = dict(t)
        md = dict(tt.get("metadata") or {})
        # Keep signal visible, but stop presenting it as a canonical requirement card.
        tt["source_type"] = "priority_action"
        tt["source_entity_type"] = "priority_action"
        tt.pop("requirement_id", None)
        md.pop("requirement_id", None)
        md.pop("take_action", None)
        md.pop("requirement_action_type", None)
        md["canonical_guard"] = {
            "reclassified": True,
            "reason": "missing_or_noncanonical_requirement_id",
            "property_id": pid or None,
            "requirement_id": rid or None,
        }
        tt["metadata"] = md
        if not str(tt.get("primary_action_label") or "").strip():
            tt["primary_action_label"] = "View details"
        if not str(tt.get("primary_action_type") or "").strip():
            tt["primary_action_type"] = "view_details"
        out.append(tt)
        logger.warning(
            "unified_tasks: requirement-like task reclassified by canonical guard",
            extra=compliance_fanout_extra(
                op="canonical_requirement_guard",
                stage="partial",
                client_id=client_id,
                property_id=pid or None,
                requirement_id=rid or None,
                correlation_id=str(tt.get("id") or ""),
                trigger_reason="orphan_requirement_like_task",
            ),
        )
    return out


def digest_from_unified_tasks_full(
    full: Dict[str, Any],
    *,
    activity_limit: int = 8,
) -> Dict[str, Any]:
    """Derive digest fields from an already-built unified tasks payload (avoids duplicate rebuild)."""
    feed = full.get("activity_feed") or []
    cap = max(1, min(int(activity_limit), 25))
    digest_out: Dict[str, Any] = {
        "summary": full.get("summary") or {},
        "freshness": full.get("freshness") or {},
        "activity_feed": feed[:cap],
    }
    meta = full.get("trust_surface_operational_metadata")
    if meta is not None:
        digest_out["trust_surface_operational_metadata"] = meta
    return digest_out


async def get_unified_tasks_for_client(
    client_id: str,
    property_id_filter: Optional[str] = None,
    raw_limit: int = 120,
    portal_user_id: Optional[str] = None,
    *,
    trust_surface_composition_context: Optional[Dict[str, Any]] = None,
    bypass_cache: bool = False,
) -> Dict[str, Any]:
    """
    Build unified task list + sections + summary + freshness + spend (when invoicing data exists).

    Prioritization: ATTENTION_AUTHORITY_RULES (``today_attention_ranking``) then impact_score tie-breakers.
    """
    from services.operational_surface_cache import (
        get_cached_unified_tasks,
        set_cached_unified_tasks,
        unified_tasks_cache_key,
    )

    cache_key = unified_tasks_cache_key(client_id, property_id_filter, portal_user_id, raw_limit)
    if not bypass_cache:
        cached = get_cached_unified_tasks(cache_key)
        if cached:
            out = dict(cached["payload"])
            freshness = dict(out.get("freshness") or {})
            freshness["cache_hit"] = True
            freshness["cached_at"] = cached["cached_at"]
            freshness["cache_ttl_seconds"] = cached["ttl_seconds"]
            out["freshness"] = freshness
            return out

    now = datetime.now(timezone.utc)
    db = database.get_db()
    actions = await fetch_client_priority_actions(client_id, property_id_filter, raw_limit)
    prop_ids = [a.get("related_property_id") for a in actions if a.get("related_property_id")]
    property_labels = await _load_property_labels(client_id, [str(x) for x in prop_ids if x])

    seen = set()
    tasks: List[Dict[str, Any]] = []
    for a in actions:
        t = _action_to_task(a, property_labels, now)
        if t["id"] in seen:
            continue
        seen.add(t["id"])
        tasks.append(t)

    for tm in await _tenant_message_tasks(client_id, property_id_filter, limit=12):
        if tm["id"] in seen:
            continue
        seen.add(tm["id"])
        tasks.append(tm)
    for tr in await _tenant_request_tasks(client_id, property_id_filter, limit=16):
        if tr["id"] in seen:
            continue
        seen.add(tr["id"])
        tasks.append(tr)

    tasks = await _enforce_canonical_requirement_task_guard(
        client_id=client_id,
        tasks=tasks,
        db=db,
    )

    overrides = await client_task_state.load_active_overrides(client_id, portal_user_id=portal_user_id)
    visible, snoozed = client_task_state.partition_tasks_by_override(tasks, overrides, now)
    snoozed_sorted = sorted(
        snoozed,
        key=lambda x: (x.get("snoozed_until") or "", x.get("title") or ""),
    )

    urgent = _sort_tasks([t for t in visible if t.get("section") == "urgent"])
    upcoming = _sort_tasks([t for t in visible if t.get("section") == "upcoming"])
    in_progress = _sort_tasks([t for t in visible if t.get("section") == "in_progress"])
    system_recent = await _recently_completed_tasks(client_id, limit=12)
    activity_rows = await client_task_state.list_recent_activity(
        client_id,
        limit=40,
        portal_user_id=portal_user_id,
    )
    recent = client_task_state.merge_user_acknowledgements_into_recent(
        system_recent, activity_rows, limit=22
    )

    week_end = now + timedelta(days=7)
    due_soon = 0
    for t in visible:
        d = _parse_dt(t.get("due_date"))
        if d and now.date() <= d.date() <= week_end.date():
            due_soon += 1

    seven_ago = now - timedelta(days=7)
    ack_7d = await client_task_state.count_activity_since(
        client_id,
        seven_ago,
        [
            client_task_state.ACTION_DISMISS,
            client_task_state.ACTION_DONE,
            client_task_state.ACTION_REVIEWED,
        ],
        portal_user_id=portal_user_id,
    )

    hidden_inbox = await client_task_state.list_hidden_inbox_items(
        client_id,
        limit=40,
        portal_user_id=portal_user_id,
    )

    summary = {
        "urgent_count": len(urgent),
        "upcoming_count": len(upcoming),
        "in_progress_count": len(in_progress),
        "recently_completed_count": len(recent),
        "snoozed_count": len(snoozed_sorted),
        "hidden_count": len(hidden_inbox),
        "habit": {
            "urgent_open_total": len(urgent),
            "items_due_or_expiring_in_7_days": due_soon,
            "tasks_acknowledged_last_7_days": ack_7d,
        },
    }

    spend = None
    try:
        from services import approval_service

        spend = await approval_service.get_maintenance_invoice_spend_this_month(client_id)
    except Exception as e:
        logger.debug("unified_tasks: spend failed: %s", e)

    freshness = await _freshness_block(client_id)
    activity_feed = activity_rows[:25]

    out: Dict[str, Any] = {
        "tasks": {
            "urgent": urgent,
            "upcoming": upcoming,
            "in_progress": in_progress,
            "recently_completed": recent,
            "snoozed": snoozed_sorted,
            "hidden": hidden_inbox,
        },
        "summary": summary,
        "freshness": freshness,
        "spend_this_month": spend,
        "activity_feed": activity_feed,
    }
    if trust_surface_composition_context is not None:
        from services.trust_surface_observability import build_unified_tasks_trust_surface_metadata

        out["trust_surface_operational_metadata"] = build_unified_tasks_trust_surface_metadata(
            client_id=client_id,
            composition_context=trust_surface_composition_context,
            freshness=freshness,
            summary=summary,
        )
    if not bypass_cache:
        set_cached_unified_tasks(cache_key, out)
    return out


async def get_unified_tasks_digest(
    client_id: str,
    property_id_filter: Optional[str] = None,
    *,
    activity_limit: int = 8,
    portal_user_id: Optional[str] = None,
    trust_surface_composition_context: Optional[Dict[str, Any]] = None,
    unified_tasks_full: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Lightweight dashboard payload: same prioritisation as full tasks, but no task lists
    (summary, freshness, truncated activity only).

    When ``unified_tasks_full`` is supplied, derives digest without rebuilding unified tasks.
    """
    if unified_tasks_full is not None:
        return digest_from_unified_tasks_full(unified_tasks_full, activity_limit=activity_limit)
    full = await get_unified_tasks_for_client(
        client_id,
        property_id_filter=property_id_filter,
        raw_limit=60,
        portal_user_id=portal_user_id,
        trust_surface_composition_context=trust_surface_composition_context,
    )
    return digest_from_unified_tasks_full(full, activity_limit=activity_limit)
