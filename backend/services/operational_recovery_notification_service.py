"""Recovery notification sweep — explain blockage, never mutate authority."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from database import database

from services.operational_recovery_reconciliation_service import (
    reconcile_recovery_notification,
    record_recovery_sent,
    record_recovery_suppressed,
    recovery_idempotency_key,
)
from services.operational_recovery_service import detect_workflow_recovery_candidates
from services.recovery_constants import (
    RECOVERY_CONTRACTOR_NON_RESPONSE,
    RECOVERY_EVIDENCE_REJECTION_LOOP,
    RECOVERY_QUOTE_NEGOTIATION_LOOP,
    RECOVERY_VISIT_RESCHEDULE_LOOP,
    RECOVERY_WORK_ORDER_ABANDONMENT_RISK,
)
from services.recovery_guardrails import assert_no_authority_mutation_in_payload

logger = logging.getLogger(__name__)

TEMPLATE_KEY = "ADMIN_MANUAL"

NOTIFY_RECOVERY_TYPES = frozenset(
    {
        RECOVERY_CONTRACTOR_NON_RESPONSE,
        RECOVERY_QUOTE_NEGOTIATION_LOOP,
        RECOVERY_VISIT_RESCHEDULE_LOOP,
        RECOVERY_EVIDENCE_REJECTION_LOOP,
        RECOVERY_WORK_ORDER_ABANDONMENT_RISK,
    }
)


async def _client_email(db, client_id: str) -> Optional[str]:
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "contact_email": 1, "email": 1})
    if not client:
        return None
    return (client.get("contact_email") or client.get("email") or "").strip() or None


async def _contractor_email(db, contractor_id: str) -> Optional[str]:
    c = await db.contractors.find_one({"contractor_id": contractor_id}, {"_id": 0, "email": 1})
    return (c.get("email") or "").strip() if c else None


async def _send_recovery_email(
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
    if result.outcome in ("sent", "duplicate_ignored"):
        return result.message_id
    logger.warning("Recovery notification outcome=%s key=%s", result.outcome, idempotency_key)
    return None


def _notification_subject(recovery: Dict[str, Any]) -> str:
    summary = (recovery.get("recovery_summary") or "An item needs your attention.").strip()
    if len(summary) > 80:
        summary = summary[:77] + "..."
    return summary


async def run_operational_recovery_sweep(*, client_id: Optional[str] = None) -> Dict[str, Any]:
    db = database.get_db()
    metrics: Dict[str, int] = {
        "clients_scanned": 0,
        "candidates_found": 0,
        "notifications_sent": 0,
        "notifications_suppressed": 0,
        "stale_prevented": 0,
    }
    client_ids: List[str] = []
    if client_id:
        client_ids = [client_id]
    else:
        async for c in db.clients.find({"status": {"$ne": "ARCHIVED"}}, {"_id": 0, "client_id": 1}).limit(500):
            cid = c.get("client_id")
            if cid:
                client_ids.append(cid)

    for cid in client_ids:
        metrics["clients_scanned"] += 1
        candidates = await detect_workflow_recovery_candidates(cid, limit=30)
        metrics["candidates_found"] += len(candidates)
        for rec in candidates:
            rtype = rec.get("recovery_type")
            if rtype not in NOTIFY_RECOVERY_TYPES:
                continue
            assert_no_authority_mutation_in_payload({})
            decision = await reconcile_recovery_notification(rec)
            et = rec.get("entity_type") or ""
            eid = rec.get("entity_id") or ""
            if not decision.fire:
                metrics["notifications_suppressed"] += 1
                if decision.suppress_reason in ("stall_resolved", "entity_terminal", "recovery_type_mismatch"):
                    metrics["stale_prevented"] += 1
                await record_recovery_suppressed(
                    entity_type=et,
                    entity_id=eid,
                    client_id=cid,
                    recovery_type=rtype or "",
                    suppress_reason=decision.suppress_reason or "unknown",
                )
                continue

            waiting = (rec.get("waiting_on_party") or "").lower()
            recipients: List[tuple[Optional[str], str]] = []
            if waiting == "contractor" and et == "work_order":
                wo = await db.work_orders.find_one({"work_order_id": eid}, {"_id": 0, "contractor_id": 1})
                em = await _contractor_email(db, (wo or {}).get("contractor_id") or "")
                if em:
                    recipients.append((None, em))
            if waiting == "landlord" or not recipients:
                em = await _client_email(db, cid)
                if em:
                    recipients.append((cid, em))
            if not recipients:
                metrics["notifications_suppressed"] += 1
                continue

            subj = _notification_subject(rec)
            body = f"<p>{rec.get('recovery_explanation') or rec.get('recovery_summary')}</p>"
            steps = rec.get("recommended_next_steps") or []
            if steps:
                body += "<ul>" + "".join(f"<li>{s}</li>" for s in steps[:3]) + "</ul>"
            idem = recovery_idempotency_key(et, eid, rtype or "")
            url = None
            if et == "work_order":
                url = f"/operations/work-orders/{eid}"
            for rcid, email in recipients:
                await _send_recovery_email(
                    client_id=rcid,
                    recipient=email,
                    subject=subj,
                    html=body,
                    idempotency_key=idem,
                    event_type=f"workflow_recovery_{(rtype or '').lower()}",
                    continuation_url=url,
                )
            metrics["notifications_sent"] += 1
            await record_recovery_sent(
                entity_type=et,
                entity_id=eid,
                client_id=cid,
                recovery_type=rtype or "",
                idempotency_key=idem,
            )

    return metrics
