"""
Clear stale AI extraction confirmation prompts after admin evidence decisions.

Preserves raw extraction payloads for audit; only updates presentation-related
confirmation flags so client UI does not keep asking for apply/confirm after verify/reject.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ADMIN_DECISION_ACCEPTED = "accepted"
ADMIN_DECISION_REJECTED = "rejected"


def build_extraction_supersession_patch(
    *,
    decision: str,
    actor_id: Optional[str],
    now_iso: str,
    existing_ai_extraction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Mongo $set fields for superseding extraction confirmation after admin evidence review."""
    decision_norm = str(decision or "").strip().lower()
    if decision_norm not in (ADMIN_DECISION_ACCEPTED, ADMIN_DECISION_REJECTED):
        decision_norm = ADMIN_DECISION_ACCEPTED

    review_status = "approved" if decision_norm == ADMIN_DECISION_ACCEPTED else "rejected"
    extraction_status = "CONFIRMED" if decision_norm == ADMIN_DECISION_ACCEPTED else "REJECTED"

    ai = dict(existing_ai_extraction or {})
    ai["review_status"] = review_status
    ai["superseded_by_admin_decision"] = decision_norm
    ai["superseded_by_admin_decision_at"] = now_iso
    if actor_id:
        ai["superseded_by_admin_decision_by"] = actor_id

    return {
        "extraction_status": extraction_status,
        "extraction_confirmation_superseded": True,
        "extraction_confirmation_superseded_at": now_iso,
        "extraction_confirmation_superseded_decision": decision_norm,
        **({"extraction_confirmation_superseded_by": actor_id} if actor_id else {}),
        "ai_extraction": ai,
    }


async def supersede_extraction_confirmation_for_admin_decision(
    db,
    *,
    document_id: str,
    decision: str,
    actor_id: Optional[str] = None,
) -> bool:
    """
    Mark extraction confirmation as superseded by an admin evidence decision.
    Returns True when document was updated.
    """
    doc = await db.documents.find_one(
        {"document_id": document_id},
        {"_id": 0, "ai_extraction": 1, "extraction_id": 1, "extraction_status": 1},
    )
    if not doc:
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    patch = build_extraction_supersession_patch(
        decision=decision,
        actor_id=actor_id,
        now_iso=now_iso,
        existing_ai_extraction=doc.get("ai_extraction") if isinstance(doc.get("ai_extraction"), dict) else None,
    )
    await db.documents.update_one({"document_id": document_id}, {"$set": patch})

    extraction_id = doc.get("extraction_id")
    if extraction_id:
        queue_status = "CONFIRMED" if str(decision).lower() == ADMIN_DECISION_ACCEPTED else "REJECTED"
        await db.extracted_documents.update_one(
            {"extraction_id": str(extraction_id), "status": {"$in": ["NEEDS_REVIEW", "EXTRACTED", "PENDING"]}},
            {
                "$set": {
                    "status": queue_status,
                    "admin_superseded_at": now_iso,
                    "admin_superseded_decision": str(decision).lower(),
                }
            },
        )

    logger.info(
        "extraction_confirmation_superseded document_id=%s decision=%s extraction_id=%s",
        document_id,
        decision,
        extraction_id or "",
    )
    return True
