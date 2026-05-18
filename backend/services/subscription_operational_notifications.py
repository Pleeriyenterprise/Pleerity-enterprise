"""Admin notifications for subscription operational events (deduplicated, non-spam)."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _admin_recipients() -> List[str]:
    raw = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    if not raw:
        return []
    return [e.strip() for e in raw.split(",") if e.strip()]


def _format_money(pence: int, currency: str) -> str:
    cur = (currency or "gbp").lower()
    sym = "£" if cur == "gbp" else ""
    amt = f"{sym}{int(pence or 0) / 100:.2f}"
    return amt if sym else f"{amt} {cur.upper()}"


def build_subscription_ops_email_context(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Structured INTERNAL_ALERT context separating payment vs provisioning state."""
    label = doc.get("operational_event_label") or "Subscription operational event"
    severity = (doc.get("operational_severity") or "info").upper()
    client_id = doc.get("client_id") or ""
    customer = doc.get("customer_name") or "Unknown"
    email = doc.get("customer_email") or ""
    plan = doc.get("plan_name") or doc.get("plan_code") or ""
    amount = _format_money(int(doc.get("amount") or 0), doc.get("currency") or "gbp")

    payment_line = doc.get("payment_status_label")
    if not payment_line:
        ps = str(doc.get("payment_status") or "").lower()
        payment_line = {
            "successful": "Payment received: successful",
            "failed": "Payment received: failed",
        }.get(ps, f"Payment received: {ps or 'unknown'}")

    prov_line = doc.get("provisioning_status_label")
    if not prov_line:
        from services.subscription_operational_events import _human_provisioning_status

        prov_line = _human_provisioning_status(doc.get("provisioning_status"))

    recon_line = doc.get("reconciliation_status_label")
    if not recon_line:
        from services.subscription_operational_events import _human_reconciliation_status

        recon_line = _human_reconciliation_status(doc.get("reconciliation_status"))

    recovered = doc.get("recovered_after_failure")
    extra_bits: List[str] = []
    if recovered:
        extra_bits.append("Recovered after previous payment failure.")
    if doc.get("suppressed_repeat_failure"):
        extra_bits.append("(Repeat failure — aggregated; no duplicate alert.)")

    renewal_no = doc.get("renewal_number")
    if renewal_no is not None:
        extra_bits.append(f"Renewal #{renewal_no}.")

    body_lines = [
        f"Customer: {customer}",
        f"Email: {email or '—'}",
        f"Client ID: {client_id}",
        f"Plan: {plan or '—'}",
        f"Amount: {amount}",
        "",
        "— Payment —",
        payment_line,
        "",
        "— Provisioning / entitlements —",
        prov_line,
        recon_line,
    ]
    if doc.get("invoice_id"):
        body_lines.append(f"Invoice: {doc['invoice_id']}")
    if extra_bits:
        body_lines.extend(["", "— Notes —", *extra_bits])

    message = "\n".join(body_lines)
    subject = f"[{severity}] {label}"
    if client_id:
        subject = f"{subject} — {client_id}"

    return {
        "subject": subject,
        "message": message,
        "alert_title": label,
        "severity": severity,
        "component": "Subscription operations",
        "client_id": client_id,
        "operational_event_type": doc.get("operational_event_type"),
    }


async def send_subscription_ops_admin_alert(
    doc: Dict[str, Any],
    *,
    idempotency_suffix: str,
) -> bool:
    recipients = _admin_recipients()
    if not recipients:
        logger.warning("ADMIN_ALERT_EMAILS / OPS_ALERT_EMAIL not set; subscription ops alert skipped")
        return False

    from services.notification_orchestrator import notification_orchestrator
    from services.operational_alert_presentation import build_internal_alert_email_context

    ctx_base = build_subscription_ops_email_context(doc)
    event_type = doc.get("operational_event_type") or "subscription_ops"
    dedupe = doc.get("dedupe_key") or f"{event_type}:{doc.get('client_id')}"
    client_id = doc.get("client_id")
    source_event_id = doc.get("source_event_id") or ""

    sent_any = False
    for addr in recipients[:5]:
        presentation = build_internal_alert_email_context(
            incident_id=dedupe[:48],
            stored_severity=doc.get("operational_severity") or "info",
            title=ctx_base["alert_title"],
            description=ctx_base["message"],
            source="subscription_operations",
            metadata={"operational_event_type": event_type, "client_id": client_id},
            related_job_name=None,
            related_job_run_id=None,
            last_finished_at=None,
            last_successful_at=None,
            is_degraded_alert=False,
            expected_interval=None,
            current_status=ctx_base["message"][:500],
            suggested_action="Review Billing admin and reconcile entitlements if provisioning is pending.",
            component="Subscription operations",
            possible_impact="Subscription revenue or customer access may be affected.",
            timestamp=None,
        )
        presentation["recipient"] = addr
        presentation["subject"] = ctx_base["subject"]
        presentation["message"] = ctx_base["message"]
        idempotency_key = f"SUB_OPS_{dedupe}_{idempotency_suffix}_{addr}"[:200]
        try:
            result = await notification_orchestrator.send(
                template_key="INTERNAL_ALERT",
                client_id=None,
                context=dict(presentation),
                idempotency_key=idempotency_key,
                event_type=f"subscription_ops_{event_type.lower()}",
            )
            if result.outcome in ("sent", "duplicate_ignored"):
                sent_any = True
        except Exception as exc:
            logger.warning("Subscription ops admin alert failed for %s: %s", addr, exc)
    return sent_any
