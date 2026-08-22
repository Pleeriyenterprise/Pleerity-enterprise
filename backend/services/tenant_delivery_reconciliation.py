"""
Reconcile tenant_delivery_proofs from message_logs (Postmark webhooks + scheduled catch-up).

Only reflects provider-backed fields present on ``message_logs`` — no synthetic opens or deliveries.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

from database import database
from models import AuditAction, UserRole
from utils.audit import create_audit_log

from services.compliance_gap_sync import sync_compliance_gaps_for_requirement
from services.compliance_recalc_queue import (
    ACTOR_CLIENT,
    ACTOR_SYSTEM,
    TRIGGER_PROPERTY_UPDATED,
)
from services.compliance_recalc_lifecycle_transition import (
    enqueue_governed_compliance_recalc as enqueue_compliance_recalc,
)
from utils.compliance_fanout_log import compliance_fanout_extra

logger = logging.getLogger(__name__)

INTENT = "TENANT_COMPLIANCE_PACK"


async def enqueue_property_recalc_after_tenant_delivery_gap_batch(
    *,
    client_id: str,
    property_id: str,
    delivery_id: str,
    actor_type: str,
    actor_id: Optional[str] = None,
) -> None:
    """
    After at least one successful tenant-delivery-driven gap sync for a property, enqueue
    a single compliance recalc (Stream E — score convergence). Idempotent per delivery_id
    via correlation_id TENANT_DELIVERY:{delivery_id}.
    """
    cid = str(client_id or "").strip()
    pid = str(property_id or "").strip()
    did = str(delivery_id or "").strip()
    if not cid or not pid or not did:
        return
    correlation_id = f"TENANT_DELIVERY:{did}"
    try:
        await enqueue_compliance_recalc(
            property_id=pid,
            client_id=cid,
            trigger_reason=TRIGGER_PROPERTY_UPDATED,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.warning(
            "enqueue_compliance_recalc after tenant delivery gap batch failed client_id=%s property_id=%s delivery_id=%s: %s",
            cid,
            pid,
            did,
            exc,
            extra=compliance_fanout_extra(
                op="recalc_enqueue",
                stage="failed",
                client_id=cid,
                property_id=pid,
                correlation_id=correlation_id,
                trigger_reason=TRIGGER_PROPERTY_UPDATED,
                exc_type=type(exc).__name__,
            ),
        )


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def proof_linked_to_message_log(proof: Dict[str, Any], log: Dict[str, Any]) -> bool:
    if proof.get("message_log_id") and proof.get("message_log_id") == log.get("message_id"):
        return True
    pm_log = (log.get("provider_message_id") or log.get("postmark_message_id") or "").strip()
    pm_proof = (proof.get("provider_message_id") or "").strip()
    if pm_log and pm_proof and pm_log == pm_proof:
        return True
    tdid = (log.get("metadata") or {}).get("tenant_delivery_id")
    if tdid and proof.get("delivery_id") == tdid:
        return True
    return False


async def _find_proofs_for_log(db, log: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    meta = log.get("metadata") or {}
    tdid = meta.get("tenant_delivery_id")
    if tdid:
        p = await db.tenant_delivery_proofs.find_one({"delivery_id": tdid}, {"_id": 0})
        if p and p.get("delivery_id") not in seen:
            seen.add(str(p["delivery_id"]))
            out.append(p)
    mid = log.get("message_id")
    if mid:
        p2 = await db.tenant_delivery_proofs.find_one({"message_log_id": mid}, {"_id": 0})
        if p2 and str(p2.get("delivery_id")) not in seen:
            seen.add(str(p2.get("delivery_id")))
            out.append(p2)
    pm = (log.get("provider_message_id") or log.get("postmark_message_id") or "").strip()
    if pm:
        async for p3 in db.tenant_delivery_proofs.find({"provider_message_id": pm}, {"_id": 0}).limit(20):
            if p3.get("delivery_id") and str(p3["delivery_id"]) not in seen:
                seen.add(str(p3["delivery_id"]))
                out.append(p3)
    return [p for p in out if proof_linked_to_message_log(p, log)]


async def _sync_requirements_for_proof(
    db,
    proof: Dict[str, Any],
    *,
    tenant_proof_status: str,
    property_doc: Optional[Dict[str, Any]] = None,
    recalc_actor_type: str = ACTOR_SYSTEM,
    recalc_actor_id: Optional[str] = None,
) -> None:
    cid = proof.get("client_id")
    pid = proof.get("property_id")
    req_ids = proof.get("requirement_ids_covered") or []
    delivery_id = str(proof.get("delivery_id") or "").strip()
    if not cid or not pid or not req_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    await db.requirements.update_many(
        {"client_id": cid, "property_id": pid, "requirement_id": {"$in": req_ids}},
        {"$set": {"tenant_delivery_proof_status": tenant_proof_status, "tenant_last_delivery_id": proof.get("delivery_id"), "updated_at": now}},
    )
    prop = property_doc
    if prop is None:
        prop = await db.properties.find_one({"property_id": pid, "client_id": cid}, {"_id": 0})
    any_gap_sync_ok = False
    for rid in req_ids:
        full = await db.requirements.find_one({"requirement_id": rid}, {"_id": 0})
        if full:
            try:
                await sync_compliance_gaps_for_requirement(db, full, property_doc=prop)
                any_gap_sync_ok = True
            except Exception as e:
                logger.warning(
                    "gap sync after tenant delivery reconcile failed rid=%s: %s",
                    rid,
                    e,
                    extra=compliance_fanout_extra(
                        op="gap_sync",
                        stage="failed",
                        client_id=str(cid) if cid else None,
                        property_id=str(pid) if pid else None,
                        requirement_id=str(rid),
                        exc_type=type(e).__name__,
                    ),
                )
    if any_gap_sync_ok and delivery_id:
        await enqueue_property_recalc_after_tenant_delivery_gap_batch(
            client_id=str(cid),
            property_id=str(pid),
            delivery_id=delivery_id,
            actor_type=recalc_actor_type,
            actor_id=recalc_actor_id,
        )


async def apply_message_log_to_tenant_delivery_proofs(db, log: Dict[str, Any]) -> List[str]:
    """
    Update tenant_delivery_proofs (and mirrored requirement flags) from a single message_logs row.
    Idempotent. Returns affected delivery_ids.
    """
    proofs = await _find_proofs_for_log(db, log)
    if not proofs:
        return []
    st = str(log.get("status") or "").upper()
    opened_at = log.get("opened_at")
    delivered_at = log.get("delivered_at")
    bounced_at = log.get("bounced_at")
    affected: List[str] = []

    for proof in proofs:
        did = str(proof.get("delivery_id") or "")
        if not did:
            continue
        cid = proof.get("client_id")
        pid = proof.get("property_id")
        prop = await db.properties.find_one({"property_id": pid, "client_id": cid}, {"_id": 0}) if cid and pid else None

        if st == "DELIVERED":
            if proof.get("delivery_status") == "DELIVERED" and proof.get("provider_delivered_at"):
                pass
            else:
                now_iso = datetime.now(timezone.utc).isoformat()
                await db.tenant_delivery_proofs.update_one(
                    {"delivery_id": did},
                    {
                        "$set": {
                            "delivery_status": "DELIVERED",
                            "lifecycle_send": "DELIVERED",
                            "provider_delivered_at": _iso(delivered_at) or now_iso,
                            "updated_at": now_iso,
                        }
                    },
                )
                await create_audit_log(
                    action=AuditAction.TENANT_DELIVERY_PROVIDER_DELIVERED,
                    client_id=cid,
                    resource_type="tenant_delivery_proof",
                    resource_id=did,
                    metadata={"message_log_id": log.get("message_id"), "provider_message_id": proof.get("provider_message_id")},
                )
                await _sync_requirements_for_proof(db, {**proof, "delivery_id": did}, tenant_proof_status="DELIVERED", property_doc=prop)
            affected.append(did)

        if st in ("BOUNCED", "FAILED"):
            if proof.get("delivery_status") in ("BOUNCED", "FAILED"):
                pass
            else:
                now_iso = datetime.now(timezone.utc).isoformat()
                new_status = "BOUNCED" if st == "BOUNCED" else "FAILED"
                await db.tenant_delivery_proofs.update_one(
                    {"delivery_id": did},
                    {
                        "$set": {
                            "delivery_status": new_status,
                            "lifecycle_send": new_status,
                            "provider_bounced_at": _iso(bounced_at) if st == "BOUNCED" else None,
                            "last_error": (log.get("error_message") or st)[:2000],
                            "updated_at": now_iso,
                        }
                    },
                )
                await create_audit_log(
                    action=AuditAction.TENANT_DELIVERY_PROVIDER_BOUNCED,
                    client_id=cid,
                    resource_type="tenant_delivery_proof",
                    resource_id=did,
                    metadata={"message_log_id": log.get("message_id"), "message_log_status": st},
                )
                await _sync_requirements_for_proof(db, {**proof, "delivery_id": did}, tenant_proof_status=new_status, property_doc=prop)
                affected.append(did)

        if opened_at and proof.get("provider_opened_at") is None and st not in ("BOUNCED", "FAILED"):
            o_iso = _iso(opened_at)
            if o_iso:
                await db.tenant_delivery_proofs.update_one(
                    {"delivery_id": did},
                    {"$set": {"provider_opened_at": o_iso, "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                await create_audit_log(
                    action=AuditAction.TENANT_DELIVERY_PROVIDER_OPENED,
                    client_id=cid,
                    resource_type="tenant_delivery_proof",
                    resource_id=did,
                    metadata={"message_log_id": log.get("message_id"), "opened_at": o_iso},
                )
                affected.append(did)

    return list(dict.fromkeys(affected))


async def reconcile_tenant_delivery_proofs_for_postmark_message_id(db, postmark_message_id: str) -> List[str]:
    """Load message_logs rows matching Postmark MessageID and reconcile linked tenant delivery proofs."""
    if not postmark_message_id:
        return []
    pm = str(postmark_message_id).strip()
    cursor = db.message_logs.find(
        {"$or": [{"postmark_message_id": pm}, {"provider_message_id": pm}]},
        {"_id": 0},
    ).limit(25)
    logs = await cursor.to_list(25)
    affected: List[str] = []
    for log in logs:
        affected.extend(await apply_message_log_to_tenant_delivery_proofs(db, log))
    return list(dict.fromkeys(affected))


async def reconcile_stale_tenant_delivery_proofs_from_message_logs(
    *,
    hours_back: int = 96,
    limit: int = 500,
) -> Dict[str, Any]:
    """
    Scheduled catch-up: proofs in SENT (or DELIVERED missing opened) whose message_log advanced.
    """
    db = database.get_db()
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    since_iso = since.isoformat()
    q = {
        "delivery_status": {"$in": ["SENT", "DELIVERED"]},
        "message_log_id": {"$exists": True, "$ne": None},
        "updated_at": {"$gte": since_iso},
    }
    cursor = db.tenant_delivery_proofs.find(q, {"_id": 0}).sort("updated_at", -1).limit(limit)
    rows = await cursor.to_list(length=limit)
    touched = 0
    for proof in rows:
        mid = proof.get("message_log_id")
        if not mid:
            continue
        log = await db.message_logs.find_one({"message_id": mid}, {"_id": 0})
        if not log:
            continue
        ids = await apply_message_log_to_tenant_delivery_proofs(db, log)
        if ids:
            touched += 1
    logger.info("tenant_delivery stale reconcile: scanned=%s touched=%s", len(rows), touched)
    return {"scanned": len(rows), "touched": touched}


async def acknowledge_tenant_delivery_for_tenant(
    *,
    delivery_id: str,
    tenant_portal_user_id: str,
    client_id: str,
) -> Dict[str, Any]:
    """Tenant confirms receipt in portal (distinct from provider open tracking)."""
    db = database.get_db()
    proof = await db.tenant_delivery_proofs.find_one(
        {"delivery_id": delivery_id, "client_id": client_id, "tenant_portal_user_id": tenant_portal_user_id},
        {"_id": 0},
    )
    if not proof:
        raise ValueError("delivery_not_found")
    n = await db.tenant_assignments.count_documents({"tenant_id": tenant_portal_user_id})
    if n > 0:
        assn = await db.tenant_assignments.find_one(
            {"tenant_id": tenant_portal_user_id, "property_id": proof.get("property_id")},
            {"_id": 0},
        )
        if not assn:
            raise ValueError("tenant_not_assigned")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.tenant_delivery_proofs.update_one(
        {"delivery_id": delivery_id},
        {"$set": {"tenant_acknowledged_at": now_iso, "updated_at": now_iso}},
    )
    await create_audit_log(
        action=AuditAction.TENANT_DELIVERY_ACKNOWLEDGED,
        actor_id=tenant_portal_user_id,
        actor_role=UserRole.ROLE_TENANT,
        client_id=client_id,
        resource_type="tenant_delivery_proof",
        resource_id=delivery_id,
        metadata={"property_id": proof.get("property_id")},
    )
    await _sync_requirements_for_proof(
        db,
        {**proof, "tenant_acknowledged_at": now_iso},
        tenant_proof_status="ACKNOWLEDGED",
        property_doc=None,
        recalc_actor_type=ACTOR_CLIENT,
        recalc_actor_id=tenant_portal_user_id,
    )
    return {"delivery_id": delivery_id, "tenant_acknowledged_at": now_iso}
