"""Idempotent Evidence Review V2 backfill helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from services.evidence_review_migration import legacy_status_to_review_and_tier


def _legacy_status(doc: Dict[str, Any]) -> str:
    return str(doc.get("status") or "").strip().upper()


def _should_patch(doc: Dict[str, Any], *, force: bool) -> bool:
    if force:
        return True
    has_state = bool(str(doc.get("evidence_review_state") or "").strip())
    has_tier = bool(str(doc.get("assurance_tier") or "").strip())
    return not (has_state and has_tier)


def compute_v2_backfill_patch(doc: Dict[str, Any], *, force: bool = False) -> Dict[str, Any]:
    """
    Compute patch for review fields only.
    Default mode is additive and does not overwrite both already-present V2 fields.
    """
    if not _should_patch(doc, force=force):
        return {}
    st, tier = legacy_status_to_review_and_tier(doc.get("status"))
    return {
        "evidence_review_state": st,
        "assurance_tier": tier,
    }


async def scan_evidence_review_backfill(
    db: Any,
    *,
    limit: int = 500,
    force: bool = False,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Backfill evidence_review_state / assurance_tier for existing documents.
    Safe and idempotent:
    - default: no overwrite when both fields already exist
    - force: overwrite mapping explicitly
    """
    q: Dict[str, Any] = {"deleted": {"$ne": True}}
    rows: List[Dict[str, Any]] = await db.documents.find(q, {"_id": 0}).limit(limit).to_list(limit)

    scanned = 0
    planned_updates = 0
    updated = 0
    by_legacy_status: Dict[str, int] = {}
    by_mapped_state: Dict[str, int] = {}
    preview: List[Dict[str, Any]] = []

    for doc in rows:
        scanned += 1
        legacy_status = _legacy_status(doc) or "UNKNOWN"
        by_legacy_status[legacy_status] = by_legacy_status.get(legacy_status, 0) + 1

        patch = compute_v2_backfill_patch(doc, force=force)
        if not patch:
            continue

        mapped_state = str(patch.get("evidence_review_state") or "UNKNOWN")
        by_mapped_state[mapped_state] = by_mapped_state.get(mapped_state, 0) + 1
        planned_updates += 1
        if len(preview) < 25:
            preview.append(
                {
                    "document_id": doc.get("document_id"),
                    "legacy_status": legacy_status,
                    "mapped_state": mapped_state,
                    "mapped_assurance_tier": patch.get("assurance_tier"),
                }
            )
        if not dry_run:
            await db.documents.update_one({"document_id": doc.get("document_id")}, {"$set": patch})
            updated += 1

    return {
        "dry_run": dry_run,
        "force": force,
        "limit": limit,
        "scanned": scanned,
        "planned_updates": planned_updates,
        "updated": updated,
        "counts_by_legacy_status": by_legacy_status,
        "counts_by_mapped_state": by_mapped_state,
        "preview": preview,
    }

