"""Daily subscription operations digest for admin visibility."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.subscription_operational_constants import (
    CHARGEBACK_RECEIVED,
    PAYMENT_RECONCILIATION_MISMATCH,
    REFUND_ISSUED,
    SUBSCRIPTION_CANCELLED,
    SUBSCRIPTION_DOWNGRADED,
    SUBSCRIPTION_RENEWAL_FAILED,
    SUBSCRIPTION_RENEWED,
    SUBSCRIPTION_UPGRADED,
    TRIAL_CONVERTED,
)
from services.subscription_operational_events import COLLECTION, _format_money

logger = logging.getLogger(__name__)


def _admin_recipients() -> List[str]:
    raw = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    if not raw:
        return []
    return [e.strip() for e in raw.split(",") if e.strip()]


async def build_digest_summary(*, digest_date: str) -> Dict[str, Any]:
    """Aggregate operational events for a UTC calendar day (YYYY-MM-DD)."""
    db = database.get_db()
    day_start = datetime.fromisoformat(f"{digest_date}T00:00:00+00:00")
    day_end = day_start + timedelta(days=1)

    query = {
        "$or": [
            {"digest_date": digest_date},
            {"occurred_at": {"$gte": day_start, "$lt": day_end}},
        ]
    }
    cursor = db.subscription_operational_events.find(query, {"_id": 0})
    events = await cursor.to_list(length=5000)

    renewed = 0
    renewal_revenue_pence = 0
    failed = 0
    recovered = 0
    cancellations = 0
    upgrades = 0
    downgrades = 0
    trials = 0
    refunds = 0
    chargebacks = 0
    provisioning_mismatches = 0
    reconciliation_mismatches = 0
    at_risk: List[str] = []
    pending_recon_clients: List[str] = []

    for ev in events:
        et = ev.get("operational_event_type")
        cid = ev.get("client_id") or ""
        amt = int(ev.get("amount") or 0)
        if et == SUBSCRIPTION_RENEWED:
            renewed += 1
            renewal_revenue_pence += amt
            if ev.get("recovered_after_failure"):
                recovered += 1
        elif et == SUBSCRIPTION_RENEWAL_FAILED:
            failed += 1
            if cid and cid not in at_risk:
                at_risk.append(cid)
        elif et == SUBSCRIPTION_CANCELLED:
            cancellations += 1
        elif et == SUBSCRIPTION_UPGRADED:
            upgrades += 1
        elif et == SUBSCRIPTION_DOWNGRADED:
            downgrades += 1
        elif et == TRIAL_CONVERTED:
            trials += 1
        elif et == REFUND_ISSUED:
            refunds += 1
        elif et == CHARGEBACK_RECEIVED:
            chargebacks += 1
        elif et == PAYMENT_RECONCILIATION_MISMATCH:
            reconciliation_mismatches += 1
            if cid and cid not in pending_recon_clients:
                pending_recon_clients.append(cid)

        prov = str(ev.get("provisioning_status") or "").lower()
        if prov in ("pending", "pending_reconciliation"):
            provisioning_mismatches += 1
            if cid and cid not in pending_recon_clients:
                pending_recon_clients.append(cid)

    return {
        "digest_date": digest_date,
        "subscriptions_renewed": renewed,
        "renewal_revenue_display": _format_money(renewal_revenue_pence, "gbp"),
        "renewal_revenue_pence": renewal_revenue_pence,
        "failed_renewals": failed,
        "recovered_subscriptions": recovered,
        "cancellations": cancellations,
        "upgrades": upgrades,
        "downgrades": downgrades,
        "trial_conversions": trials,
        "refunds": refunds,
        "chargebacks": chargebacks,
        "provisioning_mismatches": provisioning_mismatches,
        "reconciliation_mismatches": reconciliation_mismatches,
        "at_risk_accounts_count": len(at_risk),
        "pending_entitlement_reconciliation_count": len(pending_recon_clients),
        "event_count": len(events),
    }


def format_digest_text(summary: Dict[str, Any]) -> str:
    d = summary.get("digest_date", "")
    lines = [
        f"Subscription operations digest — {d}",
        "",
        f"Subscriptions renewed: {summary.get('subscriptions_renewed', 0)}",
        f"Renewal revenue: {summary.get('renewal_revenue_display', '£0.00')}",
        f"Failed renewals: {summary.get('failed_renewals', 0)}",
        f"Recovered subscriptions: {summary.get('recovered_subscriptions', 0)}",
        f"Cancellations: {summary.get('cancellations', 0)}",
        f"Upgrades: {summary.get('upgrades', 0)}",
        f"Downgrades: {summary.get('downgrades', 0)}",
        f"Trial conversions: {summary.get('trial_conversions', 0)}",
        f"Refunds: {summary.get('refunds', 0)}",
        f"Chargebacks: {summary.get('chargebacks', 0)}",
        f"Provisioning mismatches: {summary.get('provisioning_mismatches', 0)}",
        f"Reconciliation mismatches: {summary.get('reconciliation_mismatches', 0)}",
        f"At-risk accounts: {summary.get('at_risk_accounts_count', 0)}",
        f"Pending entitlement reconciliation: {summary.get('pending_entitlement_reconciliation_count', 0)}",
    ]
    return "\n".join(lines)


async def send_subscription_ops_digest(*, digest_date: Optional[str] = None) -> Dict[str, Any]:
    """Send daily digest to ADMIN_ALERT_EMAILS. Suppresses empty digests."""
    recipients = _admin_recipients()
    if not recipients:
        return {
            "message": "Subscription ops digest skipped: no admin recipients configured",
            "outcome_status": "success",
            "count": 0,
        }

    if not digest_date:
        digest_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    summary = await build_digest_summary(digest_date=digest_date)
    if summary.get("event_count", 0) == 0:
        logger.info("Subscription ops digest suppressed: no events on %s", digest_date)
        return {
            "message": f"Subscription ops digest suppressed (no events on {digest_date})",
            "outcome_status": "success",
            "count": 0,
            "outcome_metrics": {"suppression_reason": "ZERO_EVENTS", "digest_date": digest_date},
        }

    body = format_digest_text(summary)
    subject = f"Subscription operations digest — {digest_date}"
    from services.notification_orchestrator import notification_orchestrator

    sent = 0
    for addr in recipients[:5]:
        try:
            result = await notification_orchestrator.send(
                template_key="INTERNAL_ALERT",
                client_id=None,
                context={
                    "recipient": addr,
                    "subject": subject,
                    "message": body,
                    "alert_title": subject,
                    "severity": "INFO",
                    "component": "Subscription operations",
                },
                idempotency_key=f"SUB_OPS_DIGEST_{digest_date}_{addr}",
                event_type="subscription_ops_digest",
            )
            if result.outcome in ("sent", "duplicate_ignored"):
                sent += 1
        except Exception as exc:
            logger.warning("Subscription ops digest send failed to %s: %s", addr, exc)

    return {
        "message": f"Subscription ops digest sent for {digest_date} to {sent} recipient(s)",
        "count": sent,
        "outcome_status": "success",
        "outcome_metrics": {**summary, "recipients_sent": sent},
    }
