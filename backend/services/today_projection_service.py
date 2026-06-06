"""
Today inbox projection: attach business_actions vs visibility_actions to unified task DTOs.

Compliance-facing task rows originate from the same unified task / priority-action pipeline as Command Centre;
requirement-backed cards must respect ``take_action`` (see ``requirement_action_resolver``). Portfolio KPIs
and overdue semantics for counts live in ``project_requirement_row_client_runtime`` + score stats — do not
re-derive compliance state in Today-only code paths.

Keep this split aligned with docs/CLIENT_PORTAL_WORKFLOW_MATRIX.md (Today page).

Business actions (build_business_actions_for_task):
    Domain CTAs only: navigate to real workflows or carry IDs for POSTs the UI performs elsewhere
    (e.g. upload deep-link from canonical ``take_action``, create compliance job, view requirement/issue/job).
    Requirement-backed cards must not invent labels/routes when ``task.metadata.take_action`` exists — use
    ``services.requirement_action_resolver.resolve_take_action_envelope`` contract (same as unified tasks).

Visibility actions (build_visibility_actions_for_task):
    Snooze 1d / 7d, mark reviewed, dismiss — each maps to POST /api/today/items/{id}/snooze|mark-reviewed|dismiss
    and apply_task_action on client_task_overrides. They do not alter requirement status, jobs, or documents.

Restore:
    Dismissed/hidden tasks appear under the hidden bucket with a synthetic visibility action "restore"
    (build_today_payload_from_unified). POST /api/today/items/{id}/restore clears the override so the task
    can surface again in active sections. Same non-mutation rule as other visibility actions.

Quality (Today-only extensions on enriched copies):
    - urgency: overdue | due_soon | on_track (calendar / overdue_days / cert-expiring / SLA-style action_types;
      not inferred from generic urgency_level alone — avoids over-classifying “due soon”).
    - title: action-oriented where we can derive it (esp. requirement_action_phrase).
    - business_actions: capped (max 2), ordered with the first marked primary: true.
    - Open sections: dedupe by (property_id, requirement_id); drop tasks with no workflow affordance.

See also: services/client_task_state_service.apply_task_action (snooze | dismiss | reviewed | restore).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from presentation.label_service import requirement_action_phrase, today_inbox_action_title
from services.client_priority_stream import (
    ACTION_CERT_EXPIRING_SOON,
    ACTION_PENDING_APPROVAL,
    ACTION_WORK_ORDER_BREACHED,
    ACTION_WORK_ORDER_NEAR_BREACH,
)
from services.compliance_requirement_engine import resolve_engine_payload_from_code
from services.requirement_action_resolver import resolve_take_action_envelope
from services.today_attention_ranking import attention_rank_explanation, today_attention_sort_key

logger = logging.getLogger(__name__)

PROVENANCE_OPERATIONS_TEMPLATE = "operations_template"

# List-view caps: summary counts remain truthful (full bucket sizes); only serialized rows are capped.
TODAY_BUCKET_CAPS: Dict[str, int] = {
    "urgent": 12,
    "upcoming": 8,
    "in_progress": 8,
    "recently_completed": 5,
    "snoozed": 5,
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


def _intent_for_take_action_primary(task: Dict[str, Any], primary: Dict[str, Any]) -> str:
    ex = str(primary.get("intent") or "").strip()
    if ex:
        return ex
    pat = str(task.get("primary_action_type") or task.get("action_context_type") or "").strip()
    if pat:
        return pat
    route = str(primary.get("route") or "")
    if "/documents" in route:
        return "upload_evidence"
    return "view_requirement"


def _resolve_requirement_take_action_for_task(task: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Prefer unified task ``metadata.take_action`` (canonical); else resolve from engine + row skeleton.
    Returns (take_action dict, requirement_action_type or None).
    """
    meta = task.get("metadata") or {}
    existing = meta.get("take_action")
    if isinstance(existing, dict) and (
        existing.get("primary") is not None or existing.get("suppressed") or existing.get("secondary") is not None
    ):
        return existing, str(meta.get("requirement_action_type") or "") or None
    rid = str(task.get("source_entity_id") or task.get("source_id") or "").strip()
    prop_id = task.get("property_id")
    code = meta.get("requirement_code")
    syn: Dict[str, Any] = {
        "requirement_id": rid or None,
        "property_id": prop_id,
        "requirement_code": code,
        "requirement_type": code,
        "jurisdiction": meta.get("jurisdiction"),
    }
    eng = resolve_engine_payload_from_code(str(code or "").strip()) if code else {}
    for k, v in (eng or {}).items():
        if v is not None:
            syn[k] = v
    rm = meta.get("registry_metadata")
    if isinstance(rm, dict) and rm:
        syn["registry_metadata"] = {**(syn.get("registry_metadata") or {}), **rm}
    env = resolve_take_action_envelope(
        syn,
        property_id=str(prop_id) if prop_id else None,
        property_jurisdiction=meta.get("jurisdiction"),
    )
    ta = env.get("take_action") if isinstance(env.get("take_action"), dict) else {}
    return ta, str(env.get("action_type") or "") or None


def _business_actions_requirement(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Requirement-sourced Today CTAs from canonical take_action (+ optional compliance job affordance)."""
    meta = task.get("metadata") or {}
    rid = str(task.get("source_entity_id") or task.get("source_id") or "").strip()
    prop_id = task.get("property_id")
    take_action, _at = _resolve_requirement_take_action_for_task(task)
    prov = take_action.get("provenance") if isinstance(take_action.get("provenance"), dict) else {}
    contract = str(take_action.get("contract") or "requirement_take_action_v1")
    supporting = list(take_action.get("supporting_external_links") or []) if isinstance(take_action.get("supporting_external_links"), list) else []

    out: List[Dict[str, Any]] = []
    pri = take_action.get("primary") if isinstance(take_action.get("primary"), dict) else None
    if pri and pri.get("route"):
        intent = _intent_for_take_action_primary(task, pri)
        out.append(
            {
                "id": "take_action_primary",
                "label": str(pri.get("label") or "").strip() or "Open",
                "navigate": str(pri.get("route") or "").strip(),
                "intent": intent,
                "action_authority": "take_action",
                "source_type": "requirement",
                "contract": contract,
                "provenance": {**prov, "bundle": "requirement_take_action"},
                "supporting_external_links": supporting,
            }
        )
    elif (
        pri
        and pri.get("kind") in ("guided_evidence_resolution", "direct_evidence_action")
        and pri.get("property_id")
        and pri.get("requirement_id")
    ):
        intent = _intent_for_take_action_primary(task, pri)
        kind = str(pri.get("kind") or "").strip() or "guided_evidence_resolution"
        row: Dict[str, Any] = {
            "id": "take_action_primary",
            "label": str(pri.get("label") or "").strip() or "Open",
            "navigate": "",
            "kind": kind,
            "property_id": str(pri.get("property_id") or "").strip(),
            "requirement_id": str(pri.get("requirement_id") or "").strip(),
            "intent": intent,
            "action_authority": "take_action",
            "source_type": "requirement",
            "contract": contract,
            "provenance": {**prov, "bundle": "requirement_take_action"},
            "supporting_external_links": supporting,
        }
        em = pri.get("evidence_mode")
        if em:
            row["evidence_mode"] = str(em).strip()
        out.append(row)
    sec = take_action.get("secondary") if isinstance(take_action.get("secondary"), dict) else None
    if sec and sec.get("route"):
        sec_route = str(sec.get("route") or "")
        out.append(
            {
                "id": "take_action_secondary",
                "label": str(sec.get("label") or "").strip() or "Open",
                "navigate": sec_route.strip(),
                "intent": "upload_evidence" if "/documents" in sec_route else "view_requirement",
                "action_authority": "take_action",
                "source_type": "requirement",
                "contract": contract,
                "provenance": {**prov, "bundle": "requirement_take_action"},
                "supporting_external_links": [],
            }
        )
    ce = meta.get("compliance_execution_booking") or {}
    eng = meta.get("compliance_engine") or {}
    create_job = bool(eng.get("creates_compliance_job", eng.get("engine_creates_compliance_job", True)))
    if ce.get("eligible") and create_job:
        out.append(
            {
                "id": "create_compliance_work_order",
                "label": "Create compliance job",
                "requirement_id": rid,
                "property_id": ce.get("property_id") or prop_id,
                "requirement_code": ce.get("requirement_code"),
                "compliance_purpose": ce.get("compliance_purpose") or "inspection",
                "compliance_generated_from": ce.get("compliance_generated_from") or "requirement",
                "intent": "create_compliance_job",
                "action_authority": "operations_template",
                "source_type": "requirement",
                "provenance": {
                    "primary_label": PROVENANCE_OPERATIONS_TEMPLATE,
                    "contract": "compliance_execution_booking_v1",
                    "bundle": "compliance_execution",
                },
            }
        )
    return out


def build_visibility_actions_for_task(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Inbox-only actions; delegated to POST /api/today/items/{id}/…"""
    tid = task.get("id") or ""
    _snooze_detail = (
        "Hides this card from Today until the snooze ends. Does not change due dates, requirements, jobs, issues, or documents."
    )
    return [
        {
            "id": "snooze_1",
            "label": "Hide from Today — 1 day",
            "detail": _snooze_detail,
            "task_id": tid,
            "snooze_days": 1,
        },
        {
            "id": "snooze_7",
            "label": "Hide from Today — 7 days",
            "detail": _snooze_detail,
            "task_id": tid,
            "snooze_days": 7,
        },
        {
            "id": "mark_reviewed",
            "label": "Mark reviewed in Today",
            "detail": "Records that you saw this card in Today only. Does not upload documents, satisfy requirements, close jobs, or resolve issues.",
            "task_id": tid,
        },
        {
            "id": "dismiss",
            "label": "Hide from Today",
            "detail": "Hides this card until you restore it (reason required, audited). Does not complete work on the underlying requirement, job, issue, or document.",
            "task_id": tid,
            "requires_reason": True,
        },
    ]


def build_business_actions_for_task(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Domain actions that navigate or trigger real workflows.
    Each item: id, label, and one of: navigate, requirement_id, risk_signal_id, issue_id, work_order_id, approval.
    """
    meta = task.get("metadata") or {}
    source_type = (task.get("source_type") or "").strip()
    prop_id = task.get("property_id")
    source_entity_id = task.get("source_entity_id") or task.get("source_id")

    out: List[Dict[str, Any]] = []

    if source_type == "requirement" and source_entity_id:
        out.extend(_business_actions_requirement(task))

    if source_type == "risk_signal" and source_entity_id:
        sid = str(source_entity_id)
        out.append(
            {
                "id": "review_risk_signal",
                "label": "Review risk signal",
                "navigate": f"/operations/risk-signals?signal_id={sid}",
                "intent": "risk_follow_up",
                "action_authority": "operations_template",
                "source_type": "risk_signal",
                "provenance": {"primary_label": PROVENANCE_OPERATIONS_TEMPLATE, "bundle": "operations"},
            }
        )

    if source_type == "issue" and source_entity_id:
        iid = str(source_entity_id)
        from services.customer_operational_language_service import is_customer_safe_maintenance_escalation

        issue_ctx = {
            **meta,
            "source_type": "issue",
            "created_from": meta.get("issue_created_from"),
            "triggering_rule": meta.get("issue_triggering_rule"),
        }
        if is_customer_safe_maintenance_escalation(issue_ctx):
            out.append(
                {
                    "id": "create_maintenance_job",
                    "label": "Create maintenance job",
                    "issue_id": iid,
                    "hint": "From issue detail you can open a work order when ready.",
                    "intent": "create_maintenance_job",
                    "action_authority": "operations_template",
                    "source_type": "issue",
                    "provenance": {"primary_label": PROVENANCE_OPERATIONS_TEMPLATE, "bundle": "operations"},
                }
            )
        else:
            out.append(
                {
                    "id": "review_evidence",
                    "label": "Review uploaded document",
                    "navigate": task.get("primary_action_url") or f"/documents?property_id={prop_id or ''}",
                    "intent": "upload_evidence",
                    "action_authority": "requirement_resolver",
                    "source_type": "issue",
                    "provenance": {"primary_label": "customer_operational_language", "bundle": "compliance"},
                }
            )
        out.append(
            {
                "id": "view_issue",
                "label": "View issue",
                "navigate": f"/operations/issues/{iid}",
                "intent": "issue",
                "action_authority": "operations_template",
                "source_type": "issue",
                "provenance": {"primary_label": PROVENANCE_OPERATIONS_TEMPLATE, "bundle": "operations"},
            }
        )

    if source_type == "work_order" and source_entity_id:
        wid = str(source_entity_id)
        out.append(
            {
                "id": "view_job",
                "label": "View job",
                "navigate": f"/operations/jobs/{wid}",
                "intent": "work_order",
                "action_authority": "operations_template",
                "source_type": "work_order",
                "provenance": {"primary_label": PROVENANCE_OPERATIONS_TEMPLATE, "bundle": "operations"},
            }
        )

    if source_type == "approval" and source_entity_id:
        inv = str(source_entity_id)
        out.append(
            {
                "id": "view_approval",
                "label": "View approval",
                "navigate": f"/operations/approvals?invoice_id={inv}",
                "intent": "review_approval",
                "action_authority": "operations_template",
                "source_type": "approval",
                "provenance": {"primary_label": PROVENANCE_OPERATIONS_TEMPLATE, "bundle": "operations"},
            }
        )

    # Fallback: primary URL from engine
    if not out and task.get("primary_action_url"):
        out.append(
            {
                "id": "open_primary",
                "label": task.get("primary_action_label") or "Open",
                "navigate": task.get("primary_action_url"),
                "intent": "open_primary",
                "action_authority": "operations_template",
                "source_type": source_type or "priority_action",
                "provenance": {"primary_label": PROVENANCE_OPERATIONS_TEMPLATE, "bundle": "unified_task_fallback"},
            }
        )

    return out


# Lower = earlier in list (more “primary” workflow). view_* / review-only last.
_BUSINESS_ACTION_ORDER: Dict[str, int] = {
    "create_compliance_work_order": 0,
    "take_action_primary": 1,
    "take_action_secondary": 2,
    "upload_certificate": 3,
    "create_maintenance_job": 4,
    "open_primary": 5,
    "review_risk_signal": 6,
    "view_job": 8,
    "view_issue": 8,
    "view_approval": 8,
    "view_requirement": 20,
}


def cap_and_order_business_actions(actions: List[Dict[str, Any]], max_actions: int = 2) -> List[Dict[str, Any]]:
    """Keep at most max_actions, prefer workflow-first CTAs; first item gets primary: True."""
    if not actions:
        return []
    ranked = sorted(
        actions,
        key=lambda a: (_BUSINESS_ACTION_ORDER.get(str(a.get("id") or ""), 6), a.get("label") or ""),
    )
    capped = ranked[: max(1, min(int(max_actions), 2))]
    out: List[Dict[str, Any]] = []
    for i, raw in enumerate(capped):
        a = dict(raw)
        a["primary"] = i == 0
        out.append(a)
    return out


def derive_today_urgency(task: Dict[str, Any], now: datetime) -> str:
    """
    Coarse band for Today UI: overdue | due_soon | on_track.

    due_soon requires a calendar horizon (due within 7d), explicit cert-expiring-soon, or an SLA/billing
    action_type — not bare urgency_level (critical/high), so open jobs and risks are not all “due soon”.
    """
    od = task.get("overdue_days")
    try:
        if od is not None and int(od) > 0:
            return "overdue"
    except (TypeError, ValueError):
        pass

    due_at = task.get("due_date")
    d = _parse_dt(due_at)
    if d:
        today = now.date()
        due_date = d.date()
        if due_date < today:
            return "overdue"
        if due_date >= today:
            if (due_date - today).days <= 7:
                return "due_soon"
        # Future due beyond 7d
        if due_date > today + timedelta(days=7):
            return "on_track"

    meta = task.get("metadata") or {}
    at = (meta.get("action_type") or "").strip()
    if at == ACTION_CERT_EXPIRING_SOON:
        return "due_soon"

    # Operational / billing time pressure without a parsed due_date (do not use urgency_level alone).
    if at in (
        ACTION_WORK_ORDER_BREACHED,
        ACTION_WORK_ORDER_NEAR_BREACH,
        ACTION_PENDING_APPROVAL,
    ):
        return "due_soon"

    stall_tier = meta.get("workflow_stall_escalation_tier")
    if stall_tier == "T72":
        return "overdue"
    if stall_tier == "T24":
        return "due_soon"

    return "on_track"


_PASSIVE_HINTS = (
    "missing",
    " not ",
    "no certificate",
    "no document",
    "expired",
    "required:",
    "non-compliant",
    "non compliant",
    "breach",
    "overdue —",
    "overdue -",
)


def _title_looks_problem_focused(title: str) -> bool:
    low = (title or "").strip().lower()
    if not low:
        return False
    return any(h in low for h in _PASSIVE_HINTS)


def today_action_oriented_title(task: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """
    Returns (new_title_or_none, set_today_action_flag).
    When flag True, clients should prefer title verbatim (see metadata.today_action_title).
    """
    meta = task.get("metadata") or {}
    st = (task.get("source_type") or "").strip()
    code = meta.get("requirement_code")

    if st == "requirement" and code:
        phrase = requirement_action_phrase(code)
        if phrase:
            return phrase, True

    if st == "requirement":
        pl = (task.get("primary_action_label") or "").strip()
        raw = (task.get("title") or "").strip()
        if pl and pl.lower() not in ("view", "open") and len(pl) > 3:
            return pl, True
        if raw and not _title_looks_problem_focused(raw):
            return None, False
        if pl:
            return pl, True
        return None, False

    inbox_title = today_inbox_action_title(st)
    if inbox_title:
        return inbox_title, True

    if st == "tenant_request":
        return None, False

    if st == "priority_action":
        raw = (task.get("title") or "").strip()
        if _title_looks_problem_focused(raw):
            alt = (task.get("primary_action_label") or task.get("primary_recommended_action") or "").strip()
            if alt:
                return alt, True
        return None, False

    raw = (task.get("title") or "").strip()
    if _title_looks_problem_focused(raw):
        alt = (task.get("primary_action_label") or "").strip()
        if alt:
            return alt, True

    return None, False


def _requirement_dedupe_key(task: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """(property_id, requirement_id) when task ties to a requirement row; else None."""
    st = (task.get("source_type") or "").strip()
    pid = str(task.get("property_id") or "").strip()
    if st == "requirement" and task.get("source_entity_id"):
        return (pid, str(task["source_entity_id"]))
    if st == "tenant_request" and task.get("requirement_id"):
        return (pid, str(task["requirement_id"]))
    return None


def dedupe_tasks_by_requirement(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the highest impact_score task per (property_id, requirement_id)."""
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    other: List[Dict[str, Any]] = []
    for t in tasks:
        k = _requirement_dedupe_key(t)
        if k is None:
            other.append(t)
            continue
        cur = best.get(k)
        if cur is None or int(t.get("impact_score") or 0) > int(cur.get("impact_score") or 0):
            best[k] = t
    return other + list(best.values())


def today_task_is_actionable(task: Dict[str, Any]) -> bool:
    """Has at least one business action or primary deep link; suppresses satisfied requirement tasks."""
    from services.assurance_actionability_service import task_is_assurance_only_inbox_item

    if task_is_assurance_only_inbox_item(task):
        return False
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    ta = meta.get("take_action") if isinstance(meta.get("take_action"), dict) else {}
    if ta.get("suppressed"):
        return False
    st = str(task.get("source_type") or "").lower()
    if st == "requirement":
        skeleton = {
            "requirement_id": meta.get("requirement_id") or task.get("source_entity_id"),
            "property_id": task.get("property_id"),
            "truth_presentation_stage": meta.get("truth_presentation_stage"),
            "semantic_state": meta.get("semantic_state"),
            "take_action": ta,
            "status": meta.get("legacy_status") or meta.get("status"),
            "evidence_authority": meta.get("evidence_authority"),
            "client_lifecycle_state": meta.get("client_lifecycle_state"),
            "assurance_tier": meta.get("assurance_tier"),
            "requirement_satisfied": meta.get("requirement_satisfied"),
        }
        from services.requirement_attention_eligibility_service import is_requirement_attention_eligible

        eligible, _, _ = is_requirement_attention_eligible(skeleton)
        if not eligible:
            return False
    acts = task.get("business_actions") or []
    if acts:
        return True
    return bool((task.get("primary_action_url") or "").strip())


def _slim_metadata_for_list(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve CTA / attention fields only — omit heavy registry and display blobs."""
    if not meta:
        return {}
    keep = (
        "action_type",
        "requirement_id",
        "linked_property_requirement_id",
        "related_work_order_id",
        "related_risk_signal_id",
        "requirement_code",
        "requirement_action_type",
        "property_jurisdiction",
        "jurisdiction",
        "timing_label",
        "today_action_title",
        "gap_key",
        "semantic_state",
        "workflow_class",
    )
    out: Dict[str, Any] = {k: meta[k] for k in keep if meta.get(k) is not None}
    ta = meta.get("take_action")
    if isinstance(ta, dict) and ta:
        out["take_action"] = ta
    return out


def compact_task_for_today_list(task: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """Compact inbox row: CTAs and attention preserved; heavy nested blobs omitted."""
    t = dict(task)
    meta = dict(t.get("metadata") or {})
    raw_actions = build_business_actions_for_task(t)
    t["business_actions"] = cap_and_order_business_actions(raw_actions, max_actions=2)
    t["visibility_actions"] = build_visibility_actions_for_task(t)
    t["urgency"] = derive_today_urgency(t, now)
    new_title, action_flag = today_action_oriented_title(t)
    if new_title:
        t["title"] = new_title
    if action_flag:
        meta["today_action_title"] = True
    t["metadata"] = _slim_metadata_for_list(meta)
    desc = (t.get("description") or "").strip()
    if len(desc) > 280:
        t["description"] = desc[:277] + "..."
    rank = attention_rank_explanation(t)
    if isinstance(rank, dict):
        t["attention_rank"] = rank.get("rank")
        t["attention_reason"] = rank.get("reason") or rank.get("summary")
    from services.customer_operational_language_service import sanitize_task_for_customer

    return sanitize_task_for_customer(t)


def enrich_task_for_today(task: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """Shallow copy: business_actions (capped), visibility_actions, urgency, title polish, metadata flag."""
    t = dict(task)
    meta = dict(t.get("metadata") or {})

    raw_actions = build_business_actions_for_task(t)
    t["business_actions"] = cap_and_order_business_actions(raw_actions, max_actions=2)
    t["visibility_actions"] = build_visibility_actions_for_task(t)
    t["urgency"] = derive_today_urgency(t, now)

    new_title, action_flag = today_action_oriented_title(t)
    if new_title:
        t["title"] = new_title
    if action_flag:
        meta["today_action_title"] = True

    t["metadata"] = meta
    return t


def enrich_task_bucket(
    tasks: Optional[List[Dict[str, Any]]],
    now: datetime,
    *,
    filter_non_actionable: bool = False,
    compact: bool = False,
) -> List[Dict[str, Any]]:
    if not tasks:
        return []
    enricher = compact_task_for_today_list if compact else enrich_task_for_today
    enriched = [enricher(dict(x), now) for x in tasks]
    enriched = dedupe_tasks_by_requirement(enriched)
    if filter_non_actionable:
        before = len(enriched)
        enriched = [x for x in enriched if today_task_is_actionable(x)]
        dropped = before - len(enriched)
        if dropped:
            logger.debug("today_projection: dropped %s non-actionable tasks from open bucket", dropped)
    if not compact:
        for t in enriched:
            if not t.get("attention_authority"):
                t["attention_authority"] = attention_rank_explanation(t)
    enriched.sort(key=today_attention_sort_key)
    return enriched


def _cap_bucket(tasks: List[Dict[str, Any]], cap: int) -> Tuple[List[Dict[str, Any]], int]:
    if cap <= 0 or len(tasks) <= cap:
        return tasks, 0
    return tasks[:cap], len(tasks) - cap


def _slim_today_flat_task(t: Dict[str, Any]) -> Dict[str, Any]:
    """Reduced task projection for flat items list (UI reads tasks.* buckets)."""
    meta = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
    return {
        "id": t.get("id"),
        "title": t.get("title"),
        "section": t.get("section"),
        "property_id": t.get("property_id"),
        "source_type": t.get("source_type"),
        "urgency_level": t.get("urgency_level"),
        "primary_action_url": t.get("primary_action_url"),
        "primary_action_type": t.get("primary_action_type"),
        "metadata": {
            k: meta[k]
            for k in (
                "action_type",
                "related_work_order_id",
                "requirement_id",
                "linked_property_requirement_id",
            )
            if meta.get(k) is not None
        },
    }


def build_today_payload_from_unified(
    full: Dict[str, Any],
    *,
    include_flat_items: bool = False,
    compact: bool = True,
) -> Dict[str, Any]:
    """Same shape as GET /client/tasks with enriched tasks + optional flat items list."""
    now = datetime.now(timezone.utc)
    tasks_root = full.get("tasks") or {}
    enriched_tasks = {
        "urgent": enrich_task_bucket(tasks_root.get("urgent"), now, filter_non_actionable=True, compact=compact),
        "upcoming": enrich_task_bucket(tasks_root.get("upcoming"), now, filter_non_actionable=True, compact=compact),
        "in_progress": enrich_task_bucket(tasks_root.get("in_progress"), now, filter_non_actionable=True, compact=compact),
        "recently_completed": enrich_task_bucket(
            tasks_root.get("recently_completed"), now, filter_non_actionable=False, compact=compact
        ),
        "snoozed": enrich_task_bucket(tasks_root.get("snoozed"), now, filter_non_actionable=False, compact=compact),
        "hidden": tasks_root.get("hidden") or [],
    }
    truthful_counts = {
        "urgent_count": len(enriched_tasks["urgent"]),
        "upcoming_count": len(enriched_tasks["upcoming"]),
        "in_progress_count": len(enriched_tasks["in_progress"]),
        "recently_completed_count": len(enriched_tasks["recently_completed"]),
        "snoozed_count": len(enriched_tasks["snoozed"]),
        "hidden_count": len(enriched_tasks["hidden"]),
    }
    continuation: Dict[str, int] = {}
    if compact:
        capped: Dict[str, Any] = {}
        for key, cap in TODAY_BUCKET_CAPS.items():
            rows, overflow = _cap_bucket(enriched_tasks.get(key) or [], cap)
            capped[key] = rows
            if overflow:
                continuation[key] = overflow
        enriched_tasks = {**enriched_tasks, **capped}
    flat: List[Dict[str, Any]] = []
    if include_flat_items:
        for section, key in (
            ("urgent", "urgent"),
            ("upcoming", "upcoming"),
            ("in_progress", "in_progress"),
            ("snoozed", "snoozed"),
        ):
            for t in enriched_tasks.get(key) or []:
                tid = t.get("id")
                if not tid:
                    continue
                flat.append(
                    {
                        "id": tid,
                        "section": section,
                        "title": t.get("title"),
                        "description": t.get("description"),
                        "property_id": t.get("property_id"),
                        "task": _slim_today_flat_task(t),
                        "business_actions": t.get("business_actions") or [],
                        "visibility_actions": t.get("visibility_actions") or [],
                    }
                )
        for h in enriched_tasks.get("hidden") or []:
            tid = h.get("task_id") or h.get("id")
            if not tid:
                continue
            flat.append(
                {
                    "id": tid,
                    "section": "hidden",
                    "title": h.get("title"),
                    "description": None,
                    "property_id": h.get("property_id"),
                    "task": h,
                    "business_actions": [],
                    "visibility_actions": [
                        {"id": "restore", "label": "Restore to inbox", "task_id": tid},
                    ],
                }
            )
    summary = dict(full.get("summary") or {})
    summary.update(truthful_counts)
    habit = dict(summary.get("habit") or {})
    habit["urgent_open_total"] = truthful_counts["urgent_count"]
    summary["habit"] = habit

    feed = full.get("activity_feed") or []
    if compact:
        feed = feed[:6]

    out: Dict[str, Any] = {
        "tasks": enriched_tasks,
        "summary": summary,
        "freshness": full.get("freshness") or {},
        "activity_feed": feed,
        "spend_this_month": full.get("spend_this_month") if not compact else None,
        "items": flat,
        "flat_items_included": include_flat_items,
        "list_projection": "compact" if compact else "full",
    }
    if continuation:
        out["bucket_continuation"] = continuation
    return out
