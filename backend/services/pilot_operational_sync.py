"""Orchestrate pilot operational state: domains, health, risk, anomalies."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from database import database
from services.pilot_conversion_risk import compute_conversion_risk_flags
from services.pilot_lifecycle_domains import sync_lifecycle_domains_to_client
from services.pilot_operational_anomalies import detect_and_persist_anomalies
from services.pilot_operational_health import compute_pilot_health_async

logger = logging.getLogger(__name__)


async def sync_pilot_operational_state(
    client_id: str,
    *,
    client: Optional[Dict[str, Any]] = None,
    billing: Optional[Dict[str, Any]] = None,
    emit_notifications: bool = True,
) -> Dict[str, Any]:
    db = database.get_db()
    if client is None:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise ValueError("CLIENT_NOT_FOUND")
    if not client.get("pilot_status") and not client.get("pilot_program_type"):
        return {"skipped": True, "reason": "not_pilot"}

    if billing is None:
        billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}

    domains = await sync_lifecycle_domains_to_client(client_id, client=client, billing=billing)
    client = {**client, **domains}

    health = await compute_pilot_health_async(client, billing=billing)
    risk = compute_conversion_risk_flags(client, billing=billing)

    patch = {
        "pilot_health_score": health["pilot_health_score"],
        "pilot_health_band": health["pilot_health_band"],
        "pilot_health_flags": health["pilot_health_flags"],
        "pilot_conversion_risk": risk,
        "pilot_operational_updated_at": domains.get("pilot_lifecycle_domains_updated_at"),
    }
    await db.clients.update_one({"client_id": client_id}, {"$set": patch})
    client = {**client, **patch}

    anomaly_ids = await detect_and_persist_anomalies(client_id, client=client, billing=billing)

    if emit_notifications:
        await _maybe_emit_operational_notifications(client_id, client, risk)

    return {
        "domains": domains,
        "health": health,
        "conversion_risk": risk,
        "anomaly_ids": anomaly_ids,
    }


async def _maybe_emit_operational_notifications(
    client_id: str,
    client: Dict[str, Any],
    risk: Dict[str, Any],
) -> None:
    from services.pilot_operational_notifications import emit_pilot_operational_event

    try:
        if risk.get("missing_payment_method") and risk.get("approaching_paid_transition"):
            await emit_pilot_operational_event(
                event_type="missing_payment_method",
                client_id=client_id,
                context={"days_remaining": risk.get("days_remaining")},
            )
        days = risk.get("days_remaining")
        if days is not None and days <= 7:
            await emit_pilot_operational_event(
                event_type="pilot_expiring_soon",
                client_id=client_id,
                context={"days_remaining": days},
            )
        if str(client.get("pilot_governance_status") or "") == "converted":
            await emit_pilot_operational_event(
                event_type="pilot_converted",
                client_id=client_id,
                context={},
                idempotency_key=f"pilot_converted:{client_id}",
            )
    except Exception as ex:
        logger.debug("Pilot operational notification hooks skipped: %s", ex)
