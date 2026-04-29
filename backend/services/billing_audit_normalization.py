from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def _as_utc_iso(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def normalized_billing_audit_metadata(
    *,
    machine_event_type: str,
    human_label: str,
    severity: str = "info",
    actor_type: str = "system",
    actor_id: Optional[str] = None,
    affected_entity_type: str = "client_billing",
    affected_entity_id: Optional[str] = None,
    client_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    stripe_invoice_id: Optional[str] = None,
    stripe_checkout_session_id: Optional[str] = None,
    support_explanation: Optional[str] = None,
    occurred_at: Any = None,
    correlation_id: Optional[str] = None,
    **extras: Any,
) -> Dict[str, Any]:
    """
    Additive normalized metadata for billing audit rows.
    Existing metadata keys stay untouched by callers.
    """
    out: Dict[str, Any] = {
        "machine_event_type": machine_event_type,
        "human_label": human_label,
        "severity": severity,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "affected_entity_type": affected_entity_type,
        "affected_entity_id": affected_entity_id or client_id,
        "client_id": client_id,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_invoice_id": stripe_invoice_id,
        "stripe_checkout_session_id": stripe_checkout_session_id,
        "support_explanation": support_explanation,
        "occurred_at_utc": _as_utc_iso(occurred_at),
        "correlation_id": correlation_id or f"billing-audit-{uuid4()}",
    }
    out.update(extras)
    return {k: v for k, v in out.items() if v is not None}
