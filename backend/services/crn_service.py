"""
CRN (Customer Reference Number) service.

Business rules:
- CRN is assigned at intake (before client insert) so customer_reference is never null.
- Also ensured on payment confirmation via ensure_client_crn (idempotent: if already set, returns it).
- Stored only on clients.customer_reference (single source of truth).
- Format: PLE-CVP-YYYY-NNNNNN (6-digit zero-padded sequence per year).
- Idempotent: once set on a client, never change.
- Concurrency-safe: atomic counter in MongoDB (get_next_crn).
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo import ReturnDocument
from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

COUNTERS_COLLECTION = "counters"
CRN_COUNTER_PREFIX = "crn_seq_"
CRN_FORMAT = "PLE-CVP-{year}-{seq:06d}"


async def get_next_crn() -> str:
    """
    Generate the next CRN using an atomic counter.
    Uses counters collection: { _id: "crn_seq_YYYY", seq: N }.
    Returns PLE-CVP-YYYY-NNNNNN.
    """
    db = database.get_db()
    year = datetime.now(timezone.utc).year
    counter_id = f"{CRN_COUNTER_PREFIX}{year}"

    result = await db[COUNTERS_COLLECTION].find_one_and_update(
        {"_id": counter_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = (result or {}).get("seq", 1)

    crn = CRN_FORMAT.format(year=year, seq=seq)
    return crn


async def ensure_client_crn(client_id: str, stripe_event_id: Optional[str] = None) -> str:
    """
    Ensure the client has a customer_reference (CRN). Idempotent.
    If client already has customer_reference, return it. Otherwise generate, update client, audit, return.
    Call this at payment confirmation (e.g. Stripe checkout.session.completed).
    """
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "customer_reference": 1, "client_id": 1},
    )
    if not client:
        raise ValueError(f"Client not found: {client_id}")
    existing = (client.get("customer_reference") or "").strip()
    if existing:
        return existing

    crn = await get_next_crn()
    await db.clients.update_one(
        {"client_id": client_id},
        {"$set": {"customer_reference": crn}},
    )
    logger.info(f"Assigned CRN {crn} to client {client_id}")
    metadata = {"client_id": client_id, "crn": crn, "timestamp": datetime.now(timezone.utc).isoformat()}
    if stripe_event_id:
        metadata["stripe_event_id"] = stripe_event_id
    await create_audit_log(
        action=AuditAction.CRN_ASSIGNED,
        client_id=client_id,
        resource_type="client",
        resource_id=client_id,
        metadata=metadata,
    )
    return crn
