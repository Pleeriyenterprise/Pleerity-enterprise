"""Stateful evidence review transitions (Evidence Review V2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from services.evidence_review_audit import append_evidence_review_event
from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state
from services.evidence_validation_engine import EvidenceValidationEngine, build_validation_context


def correlation_id_new() -> str:
    return str(uuid.uuid4())


def document_is_calendrically_expired(doc: Dict[str, Any]) -> bool:
    """Expiry date strictly before today UTC — independent of DocumentStatus.EXPIRED."""
    from services.evidence_validation_engine import document_is_expired_calendrically

    return document_is_expired_calendrically(doc)


async def transition_review_fields(
    db,
    *,
    document_id: str,
    patch: Dict[str, Any],
    reviewer_id: Optional[str],
    correlation_id: str,
    prev_doc: Dict[str, Any],
    validation_snapshot: Optional[Dict[str, Any]],
    notes: Optional[str],
    decision_reason: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    """Atomic doc patch + ledger append."""
    fs = effective_evidence_review_state(prev_doc)
    ft_before = effective_assurance_tier(prev_doc)
    now_iso = datetime.now(timezone.utc).isoformat()

    merged_patch = dict(patch)
    merged_patch.setdefault("updated_at", now_iso)
    if reviewer_id:
        merged_patch.setdefault("review_decision_at", now_iso)
        merged_patch.setdefault("review_decision_by", reviewer_id)

    await db.documents.update_one({"document_id": document_id}, {"$set": merged_patch})
    next_doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0}) or {}

    ts = effective_evidence_review_state(next_doc)
    tt_after = effective_assurance_tier(next_doc)

    await append_evidence_review_event(
        db,
        document_id=document_id,
        requirement_id=prev_doc.get("requirement_id"),
        property_id=prev_doc.get("property_id"),
        client_id=prev_doc.get("client_id"),
        reviewer_id=reviewer_id,
        from_state=fs,
        to_state=ts,
        from_assurance_tier=ft_before,
        to_assurance_tier=tt_after,
        notes=notes,
        validation_snapshot=validation_snapshot,
        decision_reason=decision_reason,
        correlation_id=correlation_id,
    )
    return ts, next_doc


async def load_requirement_property(db, requirement_id: Optional[str], property_id: Optional[str]) -> Tuple[Optional[Dict], Optional[Dict]]:
    req = None
    prop = None
    if requirement_id:
        req = await db.requirements.find_one({"requirement_id": requirement_id}, {"_id": 0})
    if property_id:
        prop = await db.properties.find_one({"property_id": property_id}, {"_id": 0})
    return req, prop


async def run_validation_for_document(
    db, document: Dict[str, Any]
) -> Dict[str, Any]:
    rid = document.get("requirement_id")
    pid = document.get("property_id")
    req, prop = await load_requirement_property(db, str(rid) if rid else None, str(pid) if pid else None)
    ctx = build_validation_context(requirement=req, document=document, property_doc=prop)
    return EvidenceValidationEngine().evaluate(ctx)
