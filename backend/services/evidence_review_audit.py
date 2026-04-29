"""Append-only ledger for evidence review transitions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


async def append_evidence_review_event(
    db,
    *,
    document_id: str,
    requirement_id: Optional[str],
    property_id: Optional[str],
    client_id: Optional[str],
    reviewer_id: Optional[str],
    from_state: str,
    to_state: str,
    from_assurance_tier: str,
    to_assurance_tier: str,
    notes: Optional[str],
    validation_snapshot: Optional[Dict[str, Any]],
    decision_reason: Optional[str],
    correlation_id: str,
) -> str:
    """Returns event_id."""
    event_id = str(uuid.uuid4())
    row = {
        "event_id": event_id,
        "document_id": document_id,
        "requirement_id": requirement_id,
        "property_id": property_id,
        "client_id": client_id,
        "reviewer_id": reviewer_id,
        "from_state": from_state,
        "to_state": to_state,
        "from_assurance_tier": from_assurance_tier,
        "to_assurance_tier": to_assurance_tier,
        "notes": notes,
        "validation_snapshot": validation_snapshot,
        "decision_reason": decision_reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
    }
    await db.evidence_review_events.insert_one(row)
    return event_id
