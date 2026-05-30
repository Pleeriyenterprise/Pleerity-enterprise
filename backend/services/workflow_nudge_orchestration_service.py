"""Phase 1 workflow nudge orchestration — notify, prioritise, recommend only."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database

from services.workflow_nudge_guardrails import assert_nudge_action_safe
from services.workflow_nudge_reconciliation_service import (
    nudge_idempotency_key,
    reconcile_activation_nudge,
    reconcile_evidence_review_nudge,
    reconcile_requirement_overdue_nudge,
    reconcile_work_order_nudge,
    record_nudge_sent,
    record_nudge_suppressed,
)
from services.workflow_timer_constants import (
    CTR_ACTIVATION_PENDING_SINCE,
    DOC_AWAITING_EVIDENCE_REVIEW_SINCE,
    REQ_OVERDUE_SINCE,
    TENANT_ACTIVATION_PENDING_SINCE,
)
from services.workflow_timer_service import work_order_stall_context

logger = logging.getLogger(__name__)

TEMPLATE_KEY = "ADMIN_MANUAL"

# Initial nudge ladder (hours, tier, automation type)
WO_NUDGE_RULES: List[Dict[str, Any]] = [
    {
        "nudge_key": "quote_contractor_reminder",
        "stall_type": "awaiting_contractor_quote",
        "waiting_on": "contractor",
        "hours": 24,
        "tier": "T24",
        "automation_type": "auto_notify",
        "audience": "contractor",
        "escalation_level": 1,
    },
    {
        "nudge_key": "quote_revision_contractor_reminder",
        "stall_type": "awaiting_contractor_quote_revision",
        "waiting_on": "contractor",
        "hours": 24,
        "tier": "T24",
        "automation_type": "auto_notify",
        "audience": "contractor",
        "escalation_level": 1,
    },
    {
        "nudge_key": "quote_landlord_escalation",
        "stall_type": "awaiting_landlord_quote_response",
        "waiting_on": "landlord",
        "hours": 72,
        "tier": "T72",
        "automation_type": "auto_prioritise",
        "audience": "landlord",
        "escalation_level": 2,
        "also_notify": True,
    },
    {
        "nudge_key": "visit_landlord_reminder",
        "stall_type": "awaiting_visit_confirmation",
        "waiting_on": "landlord",
        "hours": 24,
        "tier": "T24",
        "automation_type": "auto_notify",
        "audience": "landlord",
        "escalation_level": 1,
    },
    {
        "nudge_key": "visit_contractor_reminder",
        "stall_type": "awaiting_visit_confirmation",
        "waiting_on": "contractor",
        "hours": 24,
        "tier": "T24",
        "automation_type": "auto_notify",
        "audience": "contractor",
        "escalation_level": 1,
    },
    {
        "nudge_key": "visit_escalation_both",
        "stall_type": "awaiting_visit_confirmation",
        "hours": 72,
        "tier": "T72",
        "automation_type": "auto_prioritise",
        "audience": "both",
        "escalation_level": 2,
        "also_notify": True,
    },
]

ACTIVATION_RULES: List[Dict[str, Any]] = [
    {
        "nudge_key": "contractor_activation_reminder",
        "entity_type": "contractor",
        "pending_field": CTR_ACTIVATION_PENDING_SINCE,
        "hours": 24,
        "tier": "T24",
        "automation_type": "auto_notify",
        "audience": "contractor",
        "escalation_level": 1,
    },
    {
        "nudge_key": "contractor_activation_landlord_visibility",
        "entity_type": "contractor",
        "pending_field": CTR_ACTIVATION_PENDING_SINCE,
        "hours": 72,
        "tier": "T72",
        "automation_type": "auto_prioritise",
        "audience": "landlord",
        "escalation_level": 2,
        "also_notify": True,
    },
    {
        "nudge_key": "tenant_activation_reminder",
        "entity_type": "tenant",
        "pending_field": TENANT_ACTIVATION_PENDING_SINCE,
        "hours": 24,
        "tier": "T24",
        "automation_type": "auto_notify",
        "audience": "tenant",
        "escalation_level": 1,
    },
    {
        "nudge_key": "tenant_activation_landlord_visibility",
        "entity_type": "tenant",
        "pending_field": TENANT_ACTIVATION_PENDING_SINCE,
        "hours": 72,
        "tier": "T72",
        "automation_type": "auto_prioritise",
        "audience": "landlord",
        "escalation_level": 2,
        "also_notify": True,
    },
]

EVIDENCE_RULES: List[Dict[str, Any]] = [
    {
        "nudge_key": "evidence_review_reminder",
        "hours": 72,
        "tier": "T72",
        "automation_type": "auto_notify",
        "audience": "reviewer",
        "escalation_level": 2,
    },
]

REQUIREMENT_RULES: List[Dict[str, Any]] = [
    {
        "nudge_key": "requirement_overdue_escalation",
        "hours": 24,
        "tier": "T24",
        "automation_type": "auto_prioritise",
        "audience": "landlord",
        "escalation_level": 2,
        "also_notify": True,
    },
]

_TERMINAL_WO = frozenset({"CANCELLED", "COMPLETED", "VERIFIED", "CLOSED"})


def _metrics_template() -> Dict[str, int]:
    return {
        "nudges_sent": 0,
        "nudges_suppressed": 0,
        "stale_prevented": 0,
        "escalation_triggered": 0,
        "entities_scanned": 0,
    }


def _nudge_copy(
    *,
    nudge_key: str,
    audience: str,
    entity_label: str,
    waiting_on: Optional[str] = None,
) -> tuple[str, str]:
    """Human-language subject + HTML body — no backend terminology."""
    copies = {
        "quote_contractor_reminder": (
            "Reminder: quote still needed",
            f"<p>Your client is waiting for your quote on <strong>{entity_label}</strong>.</p>"
            "<p>Please submit your quote when you can so work can move forward.</p>",
        ),
        "quote_revision_contractor_reminder": (
            "Reminder: revised quote needed",
            f"<p>The client requested changes to your quote for <strong>{entity_label}</strong>.</p>"
            "<p>Please submit a revised quote to keep this job moving.</p>",
        ),
        "quote_landlord_escalation": (
            "Quote awaiting your review",
            f"<p>Your contractor submitted a quote for <strong>{entity_label}</strong> several days ago.</p>"
            "<p>Review the quote when you can so work can proceed.</p>",
        ),
        "visit_landlord_reminder": (
            "Visit time awaiting your confirmation",
            f"<p>Your contractor proposed a visit time for <strong>{entity_label}</strong>.</p>"
            "<p>Please confirm or suggest another time.</p>",
        ),
        "visit_contractor_reminder": (
            "Visit time awaiting your confirmation",
            f"<p>A visit time was proposed for <strong>{entity_label}</strong>.</p>"
            "<p>Please confirm or suggest another time.</p>",
        ),
        "visit_escalation_both": (
            "Visit confirmation overdue",
            f"<p>A proposed visit for <strong>{entity_label}</strong> has been waiting for confirmation.</p>"
            "<p>Please confirm or reschedule so work can continue.</p>",
        ),
        "contractor_activation_reminder": (
            "Complete your contractor portal setup",
            "<p>Your portal invite is still pending.</p>"
            "<p>Set your password to accept jobs and submit quotes.</p>",
        ),
        "contractor_activation_landlord_visibility": (
            "Contractor portal setup pending",
            "<p>A contractor invited to your network has not finished portal setup.</p>"
            "<p>They may need a reminder to complete activation.</p>",
        ),
        "tenant_activation_reminder": (
            "Complete your tenant portal setup",
            "<p>Your portal invite is still pending.</p>"
            "<p>Set your password to access your tenancy information.</p>",
        ),
        "tenant_activation_landlord_visibility": (
            "Tenant portal setup pending",
            "<p>A tenant has not finished portal setup.</p>"
            "<p>They may need a reminder to complete activation.</p>",
        ),
        "evidence_review_reminder": (
            "Evidence awaiting review",
            f"<p>Uploaded evidence for <strong>{entity_label}</strong> is still awaiting review.</p>"
            "<p>Please review when you can.</p>",
        ),
        "requirement_overdue_escalation": (
            "Overdue compliance requirement",
            f"<p><strong>{entity_label}</strong> is overdue and needs attention.</p>"
            "<p>Resolve or upload evidence to stay on track.</p>",
        ),
    }
    subj, body = copies.get(nudge_key, ("Action needed", "<p>Please continue this workflow.</p>"))
    if waiting_on:
        body += f"<p><em>Waiting on: {waiting_on.replace('_', ' ')}</em></p>"
    return subj, body


async def _send_nudge_email(
    *,
    client_id: Optional[str],
    recipient: str,
    subject: str,
    html: str,
    idempotency_key: str,
    event_type: str,
    continuation_url: Optional[str] = None,
) -> Optional[str]:
    if continuation_url:
        html += f'<p><a href="{continuation_url}">Continue</a></p>'
    from services.notification_orchestrator import notification_orchestrator

    result = await notification_orchestrator.send(
        template_key=TEMPLATE_KEY,
        client_id=client_id,
        context={
            "recipient": recipient.strip(),
            "subject": subject,
            "message": html,
            "company_name": "Pleerity Enterprise Ltd",
        },
        idempotency_key=idempotency_key,
        event_type=event_type,
    )
    if result.outcome == "sent":
        return result.message_id
    if result.outcome == "duplicate_ignored":
        return result.message_id
    logger.warning("Workflow nudge send outcome=%s key=%s", result.outcome, idempotency_key)
    return None


async def _client_email(db, client_id: str) -> Optional[str]:
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "contact_email": 1, "email": 1},
    )
    if not client:
        return None
    return (client.get("contact_email") or client.get("email") or "").strip() or None


async def _contractor_email(db, contractor_id: str) -> Optional[str]:
    c = await db.contractors.find_one({"contractor_id": contractor_id}, {"_id": 0, "email": 1})
    return (c.get("email") or "").strip() if c else None


async def _tenant_email(db, portal_user_id: str) -> Optional[str]:
    u = await db.portal_users.find_one({"portal_user_id": portal_user_id}, {"_id": 0, "email": 1})
    return (u.get("email") or "").strip() if u else None


async def _admin_reviewer_email(db) -> Optional[str]:
    admin = await db.portal_users.find_one(
        {"role": "ROLE_ADMIN", "status": "ACTIVE"},
        {"_id": 0, "email": 1},
        sort=[("created_at", 1)],
    )
    return (admin.get("email") or "").strip() if admin else None


async def _process_work_order_nudges(metrics: Dict[str, int]) -> None:
    db = database.get_db()
    cursor = db.work_orders.find(
        {
            "status": {"$nin": list(_TERMINAL_WO)},
            "$or": [
                {"awaiting_quote_since": {"$exists": True, "$ne": None}},
                {"awaiting_landlord_quote_response_since": {"$exists": True, "$ne": None}},
                {"awaiting_contractor_quote_revision_since": {"$exists": True, "$ne": None}},
                {"awaiting_visit_confirmation_since": {"$exists": True, "$ne": None}},
                {"visit_proposed_since": {"$exists": True, "$ne": None}},
            ],
        },
        {"_id": 0},
    )
    async for wo in cursor:
        metrics["entities_scanned"] += 1
        wid = wo.get("work_order_id")
        cid = wo.get("client_id")
        label = (wo.get("title") or wo.get("description") or f"Job {wid}")[:120]
        for rule in WO_NUDGE_RULES:
            assert_nudge_action_safe(automation_type=rule["automation_type"])
            decision = await reconcile_work_order_nudge(
                wo,
                nudge_key=rule["nudge_key"],
                tier=rule["tier"],
                expected_stall_type=rule["stall_type"],
                min_age_hours=rule["hours"],
                waiting_on=rule.get("waiting_on"),
            )
            if not decision.fire:
                if decision.suppress_reason in ("stall_mismatch", "no_active_stall", "entity_terminal", "waiting_on_mismatch"):
                    metrics["stale_prevented"] += 1
                metrics["nudges_suppressed"] += 1
                await record_nudge_suppressed(
                    entity_type="work_order",
                    entity_id=wid,
                    client_id=cid,
                    nudge_key=rule["nudge_key"],
                    tier=rule["tier"],
                    automation_type=rule["automation_type"],
                    suppress_reason=decision.suppress_reason or "unknown",
                )
                continue
            audience = rule.get("audience")
            recipients: List[tuple[Optional[str], str]] = []
            if audience in ("contractor", "both"):
                em = await _contractor_email(db, wo.get("contractor_id") or "")
                if em:
                    recipients.append((None, em))
            if audience in ("landlord", "both"):
                em = await _client_email(db, cid or "")
                if em:
                    recipients.append((cid, em))
            if not recipients and rule.get("also_notify"):
                metrics["nudges_suppressed"] += 1
                continue
            subj, body = _nudge_copy(
                nudge_key=rule["nudge_key"],
                audience=audience or "landlord",
                entity_label=label,
                waiting_on=decision.waiting_on,
            )
            idem = nudge_idempotency_key("wo", wid, rule["nudge_key"], rule["tier"])
            sent_any = False
            for rcid, email in recipients:
                msg_id = await _send_nudge_email(
                    client_id=rcid,
                    recipient=email,
                    subject=subj,
                    html=body,
                    idempotency_key=idem if len(recipients) == 1 else f"{idem}:{email}",
                    event_type=f"workflow_nudge_{rule['nudge_key']}",
                    continuation_url=f"/operations/work-orders/{wid}",
                )
                if msg_id:
                    sent_any = True
            if sent_any or rule["automation_type"] == "auto_prioritise":
                metrics["nudges_sent"] += 1
                if rule["tier"] == "T72":
                    metrics["escalation_triggered"] += 1
                await record_nudge_sent(
                    entity_type="work_order",
                    entity_id=wid,
                    client_id=cid,
                    nudge_key=rule["nudge_key"],
                    tier=rule["tier"],
                    automation_type=rule["automation_type"],
                    idempotency_key=idem,
                    waiting_on=decision.waiting_on,
                    escalation_level=rule.get("escalation_level", 1),
                    metadata={"stall_type": rule["stall_type"]},
                )
                await db.work_orders.update_one(
                    {"work_order_id": wid},
                    {
                        "$set": {
                            "workflow_nudge_last_at": datetime.now(timezone.utc).isoformat(),
                            f"workflow_nudge_{rule['tier']}_{rule['nudge_key']}": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )


async def _process_activation_nudges(metrics: Dict[str, int]) -> None:
    db = database.get_db()
    # Contractors pending activation
    async for ctr in db.contractors.find({CTR_ACTIVATION_PENDING_SINCE: {"$exists": True, "$ne": None}}, {"_id": 0}):
        metrics["entities_scanned"] += 1
        cid_str = ctr.get("contractor_id")
        for rule in ACTIVATION_RULES:
            if rule["entity_type"] != "contractor":
                continue
            assert_nudge_action_safe(automation_type=rule["automation_type"])
            decision = await reconcile_activation_nudge(
                ctr,
                entity_type="contractor",
                entity_id=cid_str,
                nudge_key=rule["nudge_key"],
                tier=rule["tier"],
                min_age_hours=rule["hours"],
                pending_field=rule["pending_field"],
            )
            if not decision.fire:
                if decision.suppress_reason == "activation_complete":
                    metrics["stale_prevented"] += 1
                metrics["nudges_suppressed"] += 1
                await record_nudge_suppressed(
                    entity_type="contractor",
                    entity_id=cid_str,
                    client_id=None,
                    nudge_key=rule["nudge_key"],
                    tier=rule["tier"],
                    automation_type=rule["automation_type"],
                    suppress_reason=decision.suppress_reason or "unknown",
                )
                continue
            email = (ctr.get("email") or "").strip()
            if not email:
                metrics["nudges_suppressed"] += 1
                continue
            subj, body = _nudge_copy(nudge_key=rule["nudge_key"], audience=rule["audience"], entity_label=ctr.get("company_name") or "Contractor")
            idem = nudge_idempotency_key("contractor", cid_str, rule["nudge_key"], rule["tier"])
            await _send_nudge_email(
                client_id=None,
                recipient=email,
                subject=subj,
                html=body,
                idempotency_key=idem,
                event_type=f"workflow_nudge_{rule['nudge_key']}",
            )
            metrics["nudges_sent"] += 1
            if rule["tier"] == "T72":
                metrics["escalation_triggered"] += 1
            await record_nudge_sent(
                entity_type="contractor",
                entity_id=cid_str,
                client_id=None,
                nudge_key=rule["nudge_key"],
                tier=rule["tier"],
                automation_type=rule["automation_type"],
                idempotency_key=idem,
                escalation_level=rule.get("escalation_level", 1),
            )

    # Tenants (portal_users with tenant role)
    async for tenant in db.portal_users.find(
        {TENANT_ACTIVATION_PENDING_SINCE: {"$exists": True, "$ne": None}, "role": "ROLE_TENANT"},
        {"_id": 0},
    ):
        metrics["entities_scanned"] += 1
        pid = tenant.get("portal_user_id")
        client_id = tenant.get("client_id")
        for rule in ACTIVATION_RULES:
            if rule["entity_type"] != "tenant":
                continue
            assert_nudge_action_safe(automation_type=rule["automation_type"])
            decision = await reconcile_activation_nudge(
                tenant,
                entity_type="tenant",
                entity_id=pid,
                nudge_key=rule["nudge_key"],
                tier=rule["tier"],
                min_age_hours=rule["hours"],
                pending_field=rule["pending_field"],
            )
            if not decision.fire:
                metrics["nudges_suppressed"] += 1
                continue
            if rule["audience"] == "landlord":
                email = await _client_email(db, client_id or "")
            else:
                email = await _tenant_email(db, pid or "")
            if not email:
                metrics["nudges_suppressed"] += 1
                continue
            subj, body = _nudge_copy(
                nudge_key=rule["nudge_key"],
                audience=rule["audience"],
                entity_label=tenant.get("full_name") or "Tenant",
            )
            idem = nudge_idempotency_key("tenant", pid, rule["nudge_key"], rule["tier"])
            await _send_nudge_email(
                client_id=client_id if rule["audience"] == "landlord" else None,
                recipient=email,
                subject=subj,
                html=body,
                idempotency_key=idem,
                event_type=f"workflow_nudge_{rule['nudge_key']}",
            )
            metrics["nudges_sent"] += 1
            await record_nudge_sent(
                entity_type="tenant",
                entity_id=pid,
                client_id=client_id,
                nudge_key=rule["nudge_key"],
                tier=rule["tier"],
                automation_type=rule["automation_type"],
                idempotency_key=idem,
                escalation_level=rule.get("escalation_level", 1),
            )


async def _process_evidence_nudges(metrics: Dict[str, int]) -> None:
    db = database.get_db()
    async for doc in db.documents.find(
        {
            DOC_AWAITING_EVIDENCE_REVIEW_SINCE: {"$exists": True, "$ne": None},
            "evidence_review_state": {"$in": ["PENDING_REVIEW", "NEEDS_REVIEW", None, ""]},
        },
        {"_id": 0},
    ):
        metrics["entities_scanned"] += 1
        did = doc.get("document_id")
        cid = doc.get("client_id")
        for rule in EVIDENCE_RULES:
            assert_nudge_action_safe(automation_type=rule["automation_type"])
            decision = await reconcile_evidence_review_nudge(
                doc, nudge_key=rule["nudge_key"], tier=rule["tier"], min_age_hours=rule["hours"]
            )
            if not decision.fire:
                metrics["nudges_suppressed"] += 1
                if decision.suppress_reason == "review_terminal":
                    metrics["stale_prevented"] += 1
                continue
            email = await _admin_reviewer_email(db) or await _client_email(db, cid or "")
            if not email:
                metrics["nudges_suppressed"] += 1
                continue
            label = doc.get("title") or doc.get("document_type") or "Evidence"
            subj, body = _nudge_copy(nudge_key=rule["nudge_key"], audience="reviewer", entity_label=label)
            idem = nudge_idempotency_key("document", did, rule["nudge_key"], rule["tier"])
            await _send_nudge_email(
                client_id=cid,
                recipient=email,
                subject=subj,
                html=body,
                idempotency_key=idem,
                event_type=f"workflow_nudge_{rule['nudge_key']}",
            )
            metrics["nudges_sent"] += 1
            metrics["escalation_triggered"] += 1
            await record_nudge_sent(
                entity_type="document",
                entity_id=did,
                client_id=cid,
                nudge_key=rule["nudge_key"],
                tier=rule["tier"],
                automation_type=rule["automation_type"],
                idempotency_key=idem,
                escalation_level=rule.get("escalation_level", 2),
            )


async def _process_requirement_nudges(metrics: Dict[str, int]) -> None:
    db = database.get_db()
    async for req in db.requirements.find({"status": {"$in": ["OVERDUE", "EXPIRED"]}}, {"_id": 0}):
        metrics["entities_scanned"] += 1
        rid = req.get("requirement_id")
        cid = req.get("client_id")
        if not req.get(REQ_OVERDUE_SINCE) and req.get("due_date"):
            await db.requirements.update_one(
                {"requirement_id": rid},
                {"$set": {REQ_OVERDUE_SINCE: req.get("due_date")}},
            )
            req[REQ_OVERDUE_SINCE] = req.get("due_date")
        for rule in REQUIREMENT_RULES:
            assert_nudge_action_safe(automation_type=rule["automation_type"])
            decision = await reconcile_requirement_overdue_nudge(
                req, nudge_key=rule["nudge_key"], tier=rule["tier"], min_age_hours=rule["hours"]
            )
            if not decision.fire:
                metrics["nudges_suppressed"] += 1
                continue
            email = await _client_email(db, cid or "")
            if not email:
                metrics["nudges_suppressed"] += 1
                continue
            label = req.get("title") or req.get("requirement_code") or "Requirement"
            subj, body = _nudge_copy(nudge_key=rule["nudge_key"], audience="landlord", entity_label=label)
            idem = nudge_idempotency_key("requirement", rid, rule["nudge_key"], rule["tier"])
            await _send_nudge_email(
                client_id=cid,
                recipient=email,
                subject=subj,
                html=body,
                idempotency_key=idem,
                event_type=f"workflow_nudge_{rule['nudge_key']}",
                continuation_url="/dashboard/compliance",
            )
            metrics["nudges_sent"] += 1
            metrics["escalation_triggered"] += 1
            await record_nudge_sent(
                entity_type="requirement",
                entity_id=rid,
                client_id=cid,
                nudge_key=rule["nudge_key"],
                tier=rule["tier"],
                automation_type=rule["automation_type"],
                idempotency_key=idem,
                escalation_level=rule.get("escalation_level", 2),
            )


async def run_workflow_nudge_sweep(*, dry_run: bool = False) -> Dict[str, Any]:
    """Scheduled sweep: reconcile, notify, prioritise — never mutate authority."""
    metrics = _metrics_template()
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    if dry_run:
        return {"run_id": run_id, "dry_run": True, "started_at": started, **metrics}
    try:
        await _process_work_order_nudges(metrics)
        await _process_activation_nudges(metrics)
        await _process_evidence_nudges(metrics)
        await _process_requirement_nudges(metrics)
    except Exception as exc:
        logger.exception("Workflow nudge sweep failed: %s", exc)
        raise
    finished = datetime.now(timezone.utc).isoformat()
    db = database.get_db()
    await db.workflow_nudge_metrics.insert_one(
        {"run_id": run_id, "started_at": started, "finished_at": finished, **metrics}
    )
    return {"run_id": run_id, "started_at": started, "finished_at": finished, **metrics}
