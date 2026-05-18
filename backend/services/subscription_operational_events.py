"""
Operational subscription events — business-level signals for admin visibility.

Webhook events are ingested elsewhere; this layer records deduplicated operational
events and decides whether an immediate admin email is warranted.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from services.plan_registry import plan_registry, EntitlementStatus
from services.subscription_operational_constants import (
    CHARGEBACK_RECEIVED,
    IMMEDIATE_EMAIL_EVENT_TYPES,
    OPERATIONAL_EVENT_LABELS,
    OPERATIONAL_EVENT_SEVERITY,
    PAYMENT_RECONCILIATION_MISMATCH,
    REFUND_ISSUED,
    SUBSCRIPTION_CANCELLED,
    SUBSCRIPTION_DOWNGRADED,
    SUBSCRIPTION_REACTIVATED,
    SUBSCRIPTION_RENEWAL_FAILED,
    SUBSCRIPTION_RENEWED,
    SUBSCRIPTION_UPGRADED,
    TRIAL_CONVERTED,
)
from services.subscription_renewal_metadata import (
    load_renewal_metadata,
    record_failed_payment_metadata,
    record_successful_renewal_metadata,
)

logger = logging.getLogger(__name__)

COLLECTION = "subscription_operational_events"
HIGH_AMOUNT_PENCE = int(os.getenv("SUBSCRIPTION_OPS_HIGH_AMOUNT_PENCE", "50000") or "50000")
FAILURE_SUPPRESSION_HOURS = int(os.getenv("SUBSCRIPTION_OPS_FAILURE_SUPPRESS_HOURS", "24") or "24")

_PILOT_HIGH_PRIORITY_STATUSES = frozenset({"active", "extended", "converted_to_paid", "comped"})


def _admin_recipients() -> List[str]:
    raw = (os.getenv("ADMIN_ALERT_EMAILS") or os.getenv("OPS_ALERT_EMAIL") or "").strip()
    if not raw:
        return []
    return [e.strip() for e in raw.split(",") if e.strip()]


def operational_label(event_type: str) -> str:
    return OPERATIONAL_EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())


def _format_money(pence: int, currency: str) -> str:
    cur = (currency or "gbp").lower()
    sym = "£" if cur == "gbp" else ""
    amt = f"{sym}{pence / 100:.2f}"
    return amt if sym else f"{amt} {cur.upper()}"


async def _load_client_context(db, client_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    return client, billing


def _resolve_plan_display(billing: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    pc = billing.get("current_plan_code")
    plan_enum = plan_registry.resolve_plan_code(pc) if pc else None
    plan_name = billing.get("current_plan_display") or (plan_enum.value if plan_enum else None)
    try:
        plan_def = plan_registry.get_plan(plan_enum) if plan_enum else {}
        plan_name = plan_def.get("name") or plan_name
    except Exception:
        pass
    interval = (billing.get("billing_interval") or "month")
    if isinstance(interval, str):
        interval = interval.strip().lower()
    return pc, plan_name, interval


def _payment_and_provisioning_status(
    billing: Dict[str, Any],
    *,
    payment_ok: bool,
    lifecycle_sync_failed: bool = False,
) -> Tuple[str, str, str]:
    """Returns payment_status, provisioning_status, reconciliation_status."""
    recon_needed = bool(billing.get("billing_reconciliation_needed"))
    ent = (billing.get("entitlement_status") or "").upper()
    payment_status = "successful" if payment_ok else "failed"
    if recon_needed or lifecycle_sync_failed:
        reconciliation_status = "pending"
        provisioning_status = "pending_reconciliation"
    elif ent and ent != EntitlementStatus.ENABLED.value:
        reconciliation_status = "verified"
        provisioning_status = "pending"
    else:
        reconciliation_status = "verified"
        provisioning_status = "completed"
    return payment_status, provisioning_status, reconciliation_status


def _is_high_priority_client(client: Dict[str, Any]) -> bool:
    ps = str(client.get("pilot_status") or "").lower()
    if ps in _PILOT_HIGH_PRIORITY_STATUSES:
        return True
    if client.get("pilot_program_type"):
        return True
    return False


def _normalize_event_doc(
    *,
    operational_event_type: str,
    client: Dict[str, Any],
    billing: Dict[str, Any],
    occurred_at: datetime,
    amount_pence: int = 0,
    currency: str = "gbp",
    invoice_id: Optional[str] = None,
    payment_status: str = "unknown",
    provisioning_status: str = "unknown",
    reconciliation_status: str = "unknown",
    triggered_by_webhook: bool = True,
    source_event_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    renewal_meta: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pc, plan_name, interval = _resolve_plan_display(billing)
    meta = renewal_meta or {}
    customer_name = (
        client.get("contact_name") or client.get("full_name") or client.get("company_name") or "Unknown"
    )
    customer_email = (client.get("email") or client.get("contact_email") or "").strip()
    clv = meta.get("customer_lifetime_value_pence") or billing.get("subscription_ops_customer_lifetime_value_pence")
    doc: Dict[str, Any] = {
        "operational_event_type": operational_event_type,
        "operational_event_label": operational_label(operational_event_type),
        "operational_severity": OPERATIONAL_EVENT_SEVERITY.get(operational_event_type, "info"),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "client_id": client.get("client_id"),
        "stripe_customer_id": stripe_customer_id or billing.get("stripe_customer_id"),
        "stripe_subscription_id": stripe_subscription_id or billing.get("stripe_subscription_id"),
        "plan_code": pc,
        "plan_name": plan_name,
        "billing_interval": interval,
        "renewal_number": meta.get("renewal_number"),
        "months_active": meta.get("months_active"),
        "customer_lifetime_value": clv,
        "amount": amount_pence,
        "currency": (currency or "gbp").lower(),
        "invoice_id": invoice_id,
        "payment_status": payment_status,
        "provisioning_status": provisioning_status,
        "reconciliation_status": reconciliation_status,
        "triggered_by_webhook": triggered_by_webhook,
        "source_event_id": source_event_id,
        "occurred_at": occurred_at,
        "dedupe_key": dedupe_key,
        "created_at": datetime.now(timezone.utc),
    }
    if extra:
        doc.update(extra)
    return doc


async def _insert_operational_event(db, doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Insert if dedupe_key absent; return (created, existing_id)."""
    dedupe = doc.get("dedupe_key")
    if dedupe:
        existing = await db.subscription_operational_events.find_one({"dedupe_key": dedupe}, {"_id": 1})
        if existing:
            return False, str(existing["_id"])
    result = await db.subscription_operational_events.insert_one(doc)
    return True, str(result.inserted_id)


async def record_subscription_renewed(
    *,
    client_id: str,
    invoice: Dict[str, Any],
    event: Dict[str, Any],
    recovered: bool = False,
    lifecycle_sync_failed: bool = False,
    old_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Record successful renewal; notify admins only when rules match."""
    db = database.get_db()
    client, billing = await _load_client_context(db, client_id)
    inv_id = (invoice.get("id") or "").strip()
    amount_pence = int(invoice.get("amount_paid") or 0)
    currency = (invoice.get("currency") or "gbp").lower()
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")

    meta = await record_successful_renewal_metadata(
        db,
        client_id=client_id,
        amount_pence=amount_pence,
        paid_at=occurred_at,
        recovered_after_failure=recovered,
    )
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or billing
    payment_status, provisioning_status, reconciliation_status = _payment_and_provisioning_status(
        billing, payment_ok=True, lifecycle_sync_failed=lifecycle_sync_failed
    )

    dedupe_key = f"ops_renewed:{client_id}:{inv_id}" if inv_id else f"ops_renewed:{client_id}:{source_event_id}"
    mismatch = reconciliation_status != "verified" or provisioning_status != "completed"
    if mismatch and inv_id:
        await _record_reconciliation_mismatch(
            client_id=client_id,
            invoice_id=inv_id,
            amount_pence=amount_pence,
            currency=currency,
            event=event,
            billing=billing,
            client=client,
            payment_status=payment_status,
            provisioning_status=provisioning_status,
            reconciliation_status=reconciliation_status,
        )

    _, plan_name, interval = _resolve_plan_display(billing)
    renewal_number = int(meta.get("renewal_number") or 1)
    is_annual = interval in ("year", "annual", "yearly")
    if not is_annual and invoice:
        try:
            from services.billing_period_utils import billing_period_from_stripe_invoice_dict

            bp_start, bp_end = billing_period_from_stripe_invoice_dict(invoice)
            if bp_start and bp_end and (bp_end - bp_start).days > 60:
                is_annual = True
        except Exception:
            pass
    is_high_amount = amount_pence >= HIGH_AMOUNT_PENCE
    is_first = renewal_number <= 1
    is_reactivation = str(old_status or "").upper() in ("CANCELED", "CANCELLED", "UNPAID", "PAST_DUE") and not recovered
    high_priority = _is_high_priority_client(client)

    notify_immediate = bool(
        recovered
        or is_first
        or is_annual
        or is_high_amount
        or is_reactivation
        or mismatch
        or high_priority
    )

    doc = _normalize_event_doc(
        operational_event_type=SUBSCRIPTION_RENEWED,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        amount_pence=amount_pence,
        currency=currency,
        invoice_id=inv_id,
        payment_status=payment_status,
        provisioning_status=provisioning_status,
        reconciliation_status=reconciliation_status,
        source_event_id=source_event_id,
        stripe_customer_id=str(invoice.get("customer") or ""),
        stripe_subscription_id=str(invoice.get("subscription") or ""),
        renewal_meta=meta,
        dedupe_key=dedupe_key,
        extra={
            "recovered_after_failure": recovered,
            "immediate_admin_notify": notify_immediate,
            "digest_date": occurred_at.strftime("%Y-%m-%d"),
        },
    )
    created, event_id = await _insert_operational_event(db, doc)
    if created and notify_immediate:
        from services.subscription_operational_notifications import send_subscription_ops_admin_alert

        await send_subscription_ops_admin_alert(doc, idempotency_suffix="renewed_immediate")
    return {
        "created": created,
        "event_id": event_id,
        "immediate_admin_notify": notify_immediate and created,
        "operational_event_type": SUBSCRIPTION_RENEWED,
    }


async def _record_reconciliation_mismatch(**kwargs) -> Dict[str, Any]:
    return await record_payment_reconciliation_mismatch(**kwargs)


async def record_payment_reconciliation_mismatch(
    *,
    client_id: str,
    invoice_id: Optional[str] = None,
    amount_pence: int = 0,
    currency: str = "gbp",
    event: Optional[Dict] = None,
    billing: Optional[Dict] = None,
    client: Optional[Dict] = None,
    payment_status: str = "successful",
    provisioning_status: str = "pending_reconciliation",
    reconciliation_status: str = "pending",
) -> Dict[str, Any]:
    db = database.get_db()
    if not client or not billing:
        client, billing = await _load_client_context(db, client_id)
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")
    dedupe_key = f"ops_recon_mismatch:{client_id}:{invoice_id or source_event_id}"
    doc = _normalize_event_doc(
        operational_event_type=PAYMENT_RECONCILIATION_MISMATCH,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        amount_pence=amount_pence,
        currency=currency,
        invoice_id=invoice_id,
        payment_status=payment_status,
        provisioning_status=provisioning_status,
        reconciliation_status=reconciliation_status,
        source_event_id=source_event_id,
        dedupe_key=dedupe_key,
        extra={"digest_date": occurred_at.strftime("%Y-%m-%d"), "immediate_admin_notify": True},
    )
    created, event_id = await _insert_operational_event(db, doc)
    if created:
        from services.subscription_operational_notifications import send_subscription_ops_admin_alert

        await send_subscription_ops_admin_alert(doc, idempotency_suffix="recon_mismatch")
    return {"created": created, "event_id": event_id}


async def record_subscription_renewal_failed(
    *,
    client_id: str,
    invoice: Dict[str, Any],
    event: Dict[str, Any],
    lifecycle_sync_failed: bool = False,
) -> Dict[str, Any]:
    db = database.get_db()
    client, billing = await _load_client_context(db, client_id)
    inv_id = (invoice.get("id") or "").strip()
    amount_pence = int(invoice.get("amount_due") or invoice.get("amount_remaining") or 0)
    currency = (invoice.get("currency") or "gbp").lower()
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")

    fail_meta = await record_failed_payment_metadata(db, client_id=client_id, failed_at=occurred_at)
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or billing
    payment_status, provisioning_status, reconciliation_status = _payment_and_provisioning_status(
        billing, payment_ok=False, lifecycle_sync_failed=lifecycle_sync_failed
    )

    incident_key = fail_meta.get("incident_key") or f"renewal_fail:{client_id}"
    dedupe_key = f"ops_fail_incident:{client_id}"
    existing_incident = await db.subscription_operational_events.find_one({"dedupe_key": dedupe_key}, {"_id": 1})
    suppress_notify = existing_incident is not None

    doc = _normalize_event_doc(
        operational_event_type=SUBSCRIPTION_RENEWAL_FAILED,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        amount_pence=amount_pence,
        currency=currency,
        invoice_id=inv_id,
        payment_status=payment_status,
        provisioning_status=provisioning_status,
        reconciliation_status=reconciliation_status,
        source_event_id=source_event_id,
        stripe_customer_id=str(invoice.get("customer") or ""),
        stripe_subscription_id=str(invoice.get("subscription") or ""),
        renewal_meta=await load_renewal_metadata(db, client_id=client_id),
        dedupe_key=dedupe_key,
        extra={
            "failure_incident_key": incident_key,
            "immediate_admin_notify": not suppress_notify,
            "suppressed_repeat_failure": suppress_notify,
            "digest_date": occurred_at.strftime("%Y-%m-%d"),
        },
    )
    created, event_id = await _insert_operational_event(db, doc)
    if created and not suppress_notify:
        from services.subscription_operational_notifications import send_subscription_ops_admin_alert

        await send_subscription_ops_admin_alert(doc, idempotency_suffix="renewal_failed")
    return {
        "created": created,
        "event_id": event_id,
        "immediate_admin_notify": created and not suppress_notify,
        "suppressed": suppress_notify,
    }


async def record_subscription_cancelled(
    *,
    client_id: str,
    event: Dict[str, Any],
    stripe_subscription_id: Optional[str] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    client, billing = await _load_client_context(db, client_id)
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")
    dedupe_key = f"ops_cancelled:{client_id}:{source_event_id or stripe_subscription_id}"
    payment_status, provisioning_status, reconciliation_status = _payment_and_provisioning_status(
        billing, payment_ok=False
    )
    doc = _normalize_event_doc(
        operational_event_type=SUBSCRIPTION_CANCELLED,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        source_event_id=source_event_id,
        stripe_subscription_id=stripe_subscription_id,
        payment_status=payment_status,
        provisioning_status=provisioning_status,
        reconciliation_status=reconciliation_status,
        dedupe_key=dedupe_key,
        extra={"digest_date": occurred_at.strftime("%Y-%m-%d"), "immediate_admin_notify": True},
    )
    created, event_id = await _insert_operational_event(db, doc)
    if created:
        from services.subscription_operational_notifications import send_subscription_ops_admin_alert

        await send_subscription_ops_admin_alert(doc, idempotency_suffix="cancelled")
    return {"created": created, "event_id": event_id}


async def record_subscription_reactivated(
    *,
    client_id: str,
    event: Dict[str, Any],
) -> Dict[str, Any]:
    db = database.get_db()
    client, billing = await _load_client_context(db, client_id)
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")
    dedupe_key = f"ops_reactivated:{client_id}:{source_event_id}"
    payment_status, provisioning_status, reconciliation_status = _payment_and_provisioning_status(
        billing, payment_ok=True
    )
    doc = _normalize_event_doc(
        operational_event_type=SUBSCRIPTION_REACTIVATED,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        source_event_id=source_event_id,
        payment_status=payment_status,
        provisioning_status=provisioning_status,
        reconciliation_status=reconciliation_status,
        dedupe_key=dedupe_key,
        extra={"digest_date": occurred_at.strftime("%Y-%m-%d"), "immediate_admin_notify": True},
    )
    created, event_id = await _insert_operational_event(db, doc)
    if created:
        from services.subscription_operational_notifications import send_subscription_ops_admin_alert

        await send_subscription_ops_admin_alert(doc, idempotency_suffix="reactivated")
    return {"created": created, "event_id": event_id}


async def record_plan_change(
    *,
    client_id: str,
    event: Dict[str, Any],
    is_upgrade: bool,
    is_downgrade: bool,
    old_plan: Optional[str],
    new_plan: Optional[str],
) -> Dict[str, Any]:
    if not is_upgrade and not is_downgrade:
        return {"created": False, "skipped": True}
    db = database.get_db()
    client, billing = await _load_client_context(db, client_id)
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")
    op_type = SUBSCRIPTION_UPGRADED if is_upgrade else SUBSCRIPTION_DOWNGRADED
    dedupe_key = f"ops_plan:{client_id}:{source_event_id}:{op_type}"
    payment_status, provisioning_status, reconciliation_status = _payment_and_provisioning_status(
        billing, payment_ok=True
    )
    doc = _normalize_event_doc(
        operational_event_type=op_type,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        source_event_id=source_event_id,
        payment_status=payment_status,
        provisioning_status=provisioning_status,
        reconciliation_status=reconciliation_status,
        dedupe_key=dedupe_key,
        extra={
            "old_plan": old_plan,
            "new_plan": new_plan,
            "digest_date": occurred_at.strftime("%Y-%m-%d"),
            "immediate_admin_notify": False,
        },
    )
    created, event_id = await _insert_operational_event(db, doc)
    return {"created": created, "event_id": event_id, "operational_event_type": op_type}


async def record_trial_converted(
    *,
    client_id: str,
    event: Dict[str, Any],
    amount_pence: int = 0,
    currency: str = "gbp",
) -> Dict[str, Any]:
    db = database.get_db()
    client, billing = await _load_client_context(db, client_id)
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")
    dedupe_key = f"ops_trial_converted:{client_id}:{source_event_id}"
    payment_status, provisioning_status, reconciliation_status = _payment_and_provisioning_status(
        billing, payment_ok=True
    )
    doc = _normalize_event_doc(
        operational_event_type=TRIAL_CONVERTED,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        amount_pence=amount_pence,
        currency=currency,
        source_event_id=source_event_id,
        payment_status=payment_status,
        provisioning_status=provisioning_status,
        reconciliation_status=reconciliation_status,
        dedupe_key=dedupe_key,
        extra={"digest_date": occurred_at.strftime("%Y-%m-%d"), "immediate_admin_notify": False},
    )
    created, event_id = await _insert_operational_event(db, doc)
    return {"created": created, "event_id": event_id}


async def record_refund_issued(
    *,
    client_id: str,
    event: Dict[str, Any],
    amount_pence: int = 0,
    currency: str = "gbp",
    charge_id: Optional[str] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    client, billing = await _load_client_context(db, client_id)
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")
    dedupe_key = f"ops_refund:{client_id}:{source_event_id or charge_id}"
    doc = _normalize_event_doc(
        operational_event_type=REFUND_ISSUED,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        amount_pence=amount_pence,
        currency=currency,
        source_event_id=source_event_id,
        dedupe_key=dedupe_key,
        extra={"digest_date": occurred_at.strftime("%Y-%m-%d"), "immediate_admin_notify": True},
    )
    created, event_id = await _insert_operational_event(db, doc)
    if created:
        from services.subscription_operational_notifications import send_subscription_ops_admin_alert

        await send_subscription_ops_admin_alert(doc, idempotency_suffix="refund")
    return {"created": created, "event_id": event_id}


async def record_chargeback_received(
    *,
    client_id: str,
    event: Dict[str, Any],
    amount_pence: int = 0,
    currency: str = "gbp",
) -> Dict[str, Any]:
    db = database.get_db()
    client, billing = await _load_client_context(db, client_id)
    occurred_at = datetime.now(timezone.utc)
    source_event_id = (event or {}).get("id")
    dedupe_key = f"ops_chargeback:{client_id}:{source_event_id}"
    doc = _normalize_event_doc(
        operational_event_type=CHARGEBACK_RECEIVED,
        client=client,
        billing=billing,
        occurred_at=occurred_at,
        amount_pence=amount_pence,
        currency=currency,
        source_event_id=source_event_id,
        dedupe_key=dedupe_key,
        extra={"digest_date": occurred_at.strftime("%Y-%m-%d"), "immediate_admin_notify": True},
    )
    created, event_id = await _insert_operational_event(db, doc)
    if created:
        from services.subscription_operational_notifications import send_subscription_ops_admin_alert

        await send_subscription_ops_admin_alert(doc, idempotency_suffix="chargeback")
    return {"created": created, "event_id": event_id}


async def list_recent_operational_events(
    *,
    limit: int = 50,
    client_id: Optional[str] = None,
    severity: Optional[str] = None,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    query: Dict[str, Any] = {}
    if client_id:
        query["client_id"] = client_id
    if severity:
        query["operational_severity"] = severity
    cursor = db.subscription_operational_events.find(query, {"_id": 0}).sort("occurred_at", -1).limit(min(limit, 200))
    rows = await cursor.to_list(length=limit)
    for row in rows:
        if isinstance(row.get("occurred_at"), datetime):
            row["occurred_at"] = row["occurred_at"].isoformat()
        if isinstance(row.get("created_at"), datetime):
            row["created_at"] = row["created_at"].isoformat()
        row["payment_status_label"] = _human_payment_status(row.get("payment_status"))
        row["provisioning_status_label"] = _human_provisioning_status(row.get("provisioning_status"))
        row["reconciliation_status_label"] = _human_reconciliation_status(row.get("reconciliation_status"))
    return rows


def _human_payment_status(status: Optional[str]) -> str:
    m = {
        "successful": "Payment successful",
        "failed": "Payment failed",
        "pending": "Payment pending",
    }
    return m.get(str(status or "").lower(), "Payment status unknown")


def _human_provisioning_status(status: Optional[str]) -> str:
    m = {
        "completed": "Entitlement provisioning: completed",
        "pending": "Entitlement provisioning: pending",
        "pending_reconciliation": "Entitlement provisioning: pending reconciliation",
    }
    return m.get(str(status or "").lower(), "Entitlement provisioning: unknown")


def _human_reconciliation_status(status: Optional[str]) -> str:
    m = {
        "verified": "Reconciliation: verified",
        "pending": "Reconciliation: pending",
    }
    return m.get(str(status or "").lower(), "Reconciliation: unknown")
