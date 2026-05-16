"""
Canonical post-mutation fan-out for client requirement evidence actions.

All guided-evidence and requirement-scoped document paths should call
``propagate_requirement_evidence_outcome`` after persisting evidence so
authority, lifecycle derivation inputs, recalc queue, and client read models stay aligned.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.authority_mutation_fanout import (
    authority_sync_with_transition_observability,
    enqueue_compliance_recalc_with_fanout,
)
from services.client_propagation_notice import build_propagation_notice_from_transition_fanout
from services.compliance_recalc_queue import ACTOR_CLIENT, TRIGGER_DOC_STATUS_CHANGED
from services.requirement_transition_observability import ensure_requirement_transition_correlation_id
from services.requirement_truth import enrich_requirements_for_client

logger = logging.getLogger(__name__)


async def enrich_single_requirement_for_client(
    db,
    *,
    client_id: str,
    requirement_id: str,
) -> Optional[Dict[str, Any]]:
    """Return one client-enriched requirement row after a mutation, or None if missing."""
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "client_id": client_id},
        {"_id": 0},
    )
    if not req:
        return None
    enriched, _ = await enrich_requirements_for_client(db, str(client_id), [req])
    return enriched[0] if enriched else None


async def propagate_requirement_evidence_outcome(
    db,
    *,
    requirement_id: str,
    property_id: str,
    client_id: str,
    actor_user_id: str,
    correlation_base: str,
    transition_origin: str,
    trigger_reason: str = TRIGGER_DOC_STATUS_CHANGED,
    actor_type: str = ACTOR_CLIENT,
) -> Dict[str, Any]:
    """
    Authority sync (with backbone observability) → compliance recalc enqueue → enriched requirement row.

    Returns a client-safe payload including ``authority_synced``, ``propagation_notice``, and ``requirement``.
    """
    transition_fanout: Dict[str, Any] = {}
    sync_correlation_id = ensure_requirement_transition_correlation_id(
        requirement_id=str(requirement_id),
        property_id=str(property_id),
        client_id=str(client_id),
        correlation_id=str(correlation_base or "").strip()
        or f"REQUIREMENT_ACTION:{property_id}:{requirement_id}",
    )

    authority_synced = True
    try:
        await authority_sync_with_transition_observability(
            db,
            requirement_id,
            property_id=property_id,
            client_id=str(client_id),
            correlation_base=sync_correlation_id,
            transition_origin=transition_origin,
            transition_fanout=transition_fanout,
        )
    except Exception as exc:
        authority_synced = False
        logger.warning(
            "propagate_requirement_evidence_outcome authority sync failed requirement_id=%s: %s",
            requirement_id,
            exc,
        )

    recalc_enqueued = False
    if authority_synced:
        try:
            await enqueue_compliance_recalc_with_fanout(
                transition_fanout,
                property_id=property_id,
                client_id=str(client_id),
                trigger_reason=trigger_reason,
                actor_type=actor_type,
                actor_id=str(actor_user_id) if actor_user_id else None,
                correlation_id=sync_correlation_id,
                trigger_origin=transition_origin,
                propagation_stage="post_authority_sync",
            )
            recalc_enqueued = True
        except Exception as exc:
            logger.warning(
                "propagate_requirement_evidence_outcome recalc enqueue failed requirement_id=%s: %s",
                requirement_id,
                exc,
            )

    propagation_notice = build_propagation_notice_from_transition_fanout(transition_fanout)
    requirement = await enrich_single_requirement_for_client(
        db,
        client_id=str(client_id),
        requirement_id=str(requirement_id),
    )

    workflow_complete = bool(authority_synced and requirement)
    message = (
        "Requirement recorded and compliance status is updating."
        if workflow_complete
        else "Evidence saved, but requirement status could not be refreshed. Please refresh or contact support."
    )

    out: Dict[str, Any] = {
        "ok": True,
        "workflow_complete": workflow_complete,
        "authority_synced": authority_synced,
        "recalc_enqueued": recalc_enqueued,
        "message": message,
        "requirement_id": requirement_id,
        "property_id": property_id,
    }
    if requirement:
        out["requirement"] = requirement
    if propagation_notice:
        out["propagation_notice"] = propagation_notice
    return out
