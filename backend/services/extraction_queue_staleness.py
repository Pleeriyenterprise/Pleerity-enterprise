"""Extraction queue staleness: queue rows whose document_id no longer exists in documents."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STALE_QUEUE_STATUS = "STALE_QUEUE"
STALE_DETAIL_CODE = "STALE_QUEUE_DOCUMENT_NOT_FOUND"


async def document_exists(db, document_id: Optional[str]) -> bool:
    if not document_id:
        return False
    hit = await db.documents.find_one({"document_id": document_id}, {"_id": 1})
    return hit is not None


async def mark_queue_row_stale(db, *, extraction_id: str, document_id: Optional[str], reason: str) -> None:
    if not extraction_id:
        return
    now = datetime.now(timezone.utc)
    await db.extracted_documents.update_one(
        {"extraction_id": extraction_id},
        {
            "$set": {
                "status": STALE_QUEUE_STATUS,
                "queue_stale": True,
                "queue_stale_reason": reason[:500],
                "audit.updated_at": now,
            }
        },
    )
    if document_id:
        logger.info(
            "extraction_queue_stale_marked extraction_id=%s document_id=%s reason=%s",
            extraction_id,
            document_id,
            reason,
        )


async def enrich_extraction_queue_item(db, row: Dict[str, Any], *, auto_mark_stale: bool = True) -> Dict[str, Any]:
    """Attach document_exists / queue_actionable; optionally mark DB row stale when document missing."""
    document_id = row.get("document_id")
    exists = await document_exists(db, document_id)
    out = dict(row)
    out["document_exists"] = exists
    stale = not exists or row.get("status") == STALE_QUEUE_STATUS or row.get("queue_stale") is True
    out["queue_stale"] = stale
    out["queue_actionable"] = (
        exists
        and not stale
        and (row.get("status") or "") in ("NEEDS_REVIEW", "FAILED")
    )
    if auto_mark_stale and document_id and not exists and row.get("extraction_id"):
        await mark_queue_row_stale(
            db,
            extraction_id=str(row["extraction_id"]),
            document_id=str(document_id),
            reason=STALE_DETAIL_CODE,
        )
        out["status"] = STALE_QUEUE_STATUS
        out["queue_stale"] = True
        out["queue_actionable"] = False
    return out
