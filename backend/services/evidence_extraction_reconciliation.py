"""
Idempotent reconciliation for historical documents where evidence review supersedes
stale extraction confirmation fields (pre-supersession rollout).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.document_operational_state import (
    document_needs_extraction_reconciliation,
    infer_supersession_decision,
)
from services.evidence_extraction_supersession import (
    ADMIN_DECISION_ACCEPTED,
    ADMIN_DECISION_REJECTED,
    build_extraction_supersession_patch,
)

logger = logging.getLogger(__name__)

RECONCILIATION_REASON_HISTORICAL = "historical_evidence_review_supersedes_extraction"


def build_reconciliation_patch(
    doc: Dict[str, Any],
    *,
    decision: str,
    actor_id: Optional[str],
    now_iso: str,
    reconciliation_reason: str,
    reconciliation_batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Additive patch: supersession fields + reconciliation audit metadata."""
    ai = doc.get("ai_extraction") if isinstance(doc.get("ai_extraction"), dict) else None
    patch = build_extraction_supersession_patch(
        decision=decision,
        actor_id=actor_id,
        now_iso=now_iso,
        existing_ai_extraction=ai,
    )
    patch["extraction_reconciliation_at"] = now_iso
    patch["extraction_reconciliation_reason"] = reconciliation_reason
    if actor_id:
        patch["extraction_reconciliation_by"] = actor_id
    if reconciliation_batch_id:
        patch["extraction_reconciliation_batch_id"] = reconciliation_batch_id
    return patch


async def reconcile_document_extraction_supersession(
    db,
    *,
    document_id: str,
    actor_id: Optional[str] = None,
    reconciliation_reason: str = RECONCILIATION_REASON_HISTORICAL,
    reconciliation_batch_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Reconcile one document. Returns outcome metadata (idempotent)."""
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        return {"document_id": document_id, "status": "not_found"}

    if not document_needs_extraction_reconciliation(doc):
        return {"document_id": document_id, "status": "skipped", "reason": "already_aligned"}

    decision = infer_supersession_decision(doc)
    if not decision:
        return {"document_id": document_id, "status": "skipped", "reason": "no_evidence_decision"}

    now_iso = datetime.now(timezone.utc).isoformat()
    patch = build_reconciliation_patch(
        doc,
        decision=decision,
        actor_id=actor_id,
        now_iso=now_iso,
        reconciliation_reason=reconciliation_reason,
        reconciliation_batch_id=reconciliation_batch_id,
    )

    if dry_run:
        return {
            "document_id": document_id,
            "status": "would_update",
            "decision": decision,
            "patch_keys": sorted(patch.keys()),
        }

    await db.documents.update_one({"document_id": document_id}, {"$set": patch})

    extraction_id = doc.get("extraction_id")
    if extraction_id:
        queue_status = "CONFIRMED" if decision == ADMIN_DECISION_ACCEPTED else "REJECTED"
        await db.extracted_documents.update_one(
            {"extraction_id": str(extraction_id), "status": {"$in": ["NEEDS_REVIEW", "EXTRACTED", "PENDING"]}},
            {
                "$set": {
                    "status": queue_status,
                    "admin_superseded_at": now_iso,
                    "admin_superseded_decision": decision,
                    "reconciled_at": now_iso,
                    "reconciliation_reason": reconciliation_reason,
                }
            },
        )

    logger.info(
        "extraction_reconciliation_applied document_id=%s decision=%s reason=%s",
        document_id,
        decision,
        reconciliation_reason,
    )
    return {"document_id": document_id, "status": "updated", "decision": decision}


async def scan_extraction_supersession_reconciliation(
    db: Any,
    *,
    limit: int = 500,
    dry_run: bool = True,
    actor_id: Optional[str] = None,
    reconciliation_reason: str = RECONCILIATION_REASON_HISTORICAL,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scan documents and reconcile stale extraction confirmation where evidence review
    already supersedes extraction. Idempotent: skips aligned rows.
    """
    q: Dict[str, Any] = {"deleted": {"$ne": True}}
    if client_id:
        q["client_id"] = client_id

    rows: List[Dict[str, Any]] = await db.documents.find(q, {"_id": 0}).limit(limit).to_list(limit)
    batch_id = uuid4().hex[:16] if not dry_run else ""

    scanned = 0
    needs_reconciliation = 0
    updated = 0
    skipped = 0
    preview: List[Dict[str, Any]] = []

    for doc in rows:
        scanned += 1
        if not document_needs_extraction_reconciliation(doc):
            skipped += 1
            continue
        needs_reconciliation += 1
        doc_id = str(doc.get("document_id") or "")
        if len(preview) < 25:
            preview.append(
                {
                    "document_id": doc_id,
                    "decision": infer_supersession_decision(doc),
                    "extraction_status": doc.get("extraction_status"),
                    "evidence_review_state": doc.get("evidence_review_state"),
                    "status": doc.get("status"),
                }
            )
        if not dry_run and doc_id:
            out = await reconcile_document_extraction_supersession(
                db,
                document_id=doc_id,
                actor_id=actor_id,
                reconciliation_reason=reconciliation_reason,
                reconciliation_batch_id=batch_id,
                dry_run=False,
            )
            if out.get("status") == "updated":
                updated += 1

    return {
        "dry_run": dry_run,
        "limit": limit,
        "client_id": client_id,
        "reconciliation_batch_id": batch_id or None,
        "scanned": scanned,
        "needs_reconciliation": needs_reconciliation,
        "updated": updated,
        "skipped": skipped,
        "preview": preview,
    }
