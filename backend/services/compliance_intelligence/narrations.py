"""Audit store for compliance AI narrations (Phase 5)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


async def store_narration(
    *,
    client_id: Optional[str],
    graph_method: str,
    graph_service_response_hash: str,
    envelope: Dict[str, Any],
    narration: Dict[str, Any],
    question: Optional[str] = None,
    model_id: Optional[str] = None,
    actor_admin: bool = True,
    actor_portal_user_id: Optional[str] = None,
) -> str:
    narration_id = f"nar_{uuid.uuid4().hex}"
    decision_id = (envelope.get("authoritative_references") or {}).get("decision_id")
    if not decision_id:
        payload = envelope.get("payload") or {}
        decision = payload.get("decision") or {}
        decision_id = decision.get("decision_id")

    citation_references = [
        p.get("authoritative_references")
        for p in (narration.get("paragraphs") or [])
        if isinstance(p, dict) and p.get("authoritative_references")
    ]

    record: Dict[str, Any] = {
        "narration_id": narration_id,
        "created_at": _utc(),
        "client_id": client_id,
        "decision_id": decision_id,
        "graph_method": graph_method,
        "graph_service_response_hash": graph_service_response_hash,
        "prompt_version": narration.get("prompt_version"),
        "model_id": model_id,
        "question": question,
        "narration": narration,
        "citation_references": citation_references,
        "tier1_service": envelope.get("service"),
        "insufficient_evidence": narration.get("insufficient_evidence"),
        "actor_admin": actor_admin,
        "actor_portal_user_id": actor_portal_user_id,
    }
    db = database.get_db()
    await db.compliance_ai_narrations.insert_one(record)
    return narration_id
